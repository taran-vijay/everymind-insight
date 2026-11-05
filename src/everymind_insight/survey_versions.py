"""Survey-date missingness, calling coverage, and descriptive session diagnostics."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import t
from statsmodels.stats.proportion import proportion_confint

from .config import OBJECTIVE_ITEMS, PRESENTER_ITEMS
from .schemas import ConfidenceInterval, Metric, Provenance
from .subgroups import county_groups, role_groups
from .suppression import suppress_metric, table_suppressions


_FINGERPRINT_ITEMS = ("calling_score", "recommend_score", *PRESENTER_ITEMS, *OBJECTIVE_ITEMS)
_UNKNOWN_DATE = "Unknown date"
_LEVEL = 0.95
Missingness = Literal["all_answered", "mixed", "no_answers"]
CallingDateStatus = Literal["all_answered", "mixed", "no_answers", "unknown_date"]


@dataclass(frozen=True)
class DateFingerprint:
    """Private pattern summary, based on valid answers across the full sample."""

    training_date: str | None
    version_id: str | None
    item_states: dict[str, Missingness]

    @property
    def calling_status(self) -> CallingDateStatus:
        return self.item_states["calling_score"] if self.training_date else "unknown_date"


@dataclass(frozen=True)
class SessionConcentration:
    """Private diagnostic for the separation of group and training-date patterns."""

    group_by: str
    group: str
    dominant_date: str | None
    reasons: tuple[str, ...]

    @property
    def inseparable(self) -> bool:
        return bool(self.reasons)


@dataclass(frozen=True)
class SurveyVersionAnalysis:
    metrics: list[Metric]
    fingerprints: list[DateFingerprint]
    session_concentration: list[SessionConcentration]


def _fingerprints(frame: pd.DataFrame) -> list[DateFingerprint]:
    symbols = {"all_answered": "A", "mixed": "M", "no_answers": "N"}
    fingerprints = []
    for date, rows in frame.groupby("_date", sort=True):
        counts = rows[list(_FINGERPRINT_ITEMS)].count()
        states: dict[str, Missingness] = {
            item: "all_answered" if count == len(rows) else "mixed" if count else "no_answers"
            for item, count in counts.items()
        }
        known = date != _UNKNOWN_DATE
        fingerprints.append(DateFingerprint(
            training_date=date if known else None,
            version_id="v-" + "".join(symbols[states[item]] for item in _FINGERPRINT_ITEMS) if known else None,
            item_states=states,
        ))
    return fingerprints


def _share(
    metric_id: str, dimensions: dict[str, str], answered: int, total: int, definition: str, provenance: Provenance,
) -> Metric:
    ci = None
    if total:
        lower, upper = proportion_confint(answered, total, alpha=1 - _LEVEL, method="wilson")
        ci = ConfidenceInterval(lower=float(lower), upper=float(upper), level=_LEVEL, method="wilson")
    return Metric(
        metric_id=metric_id, dimensions=dimensions, value=answered / total if total else None,
        numerator=answered, denominator=total, n=total, ci=ci, unit="proportion",
        reason=None if total else "no_eligible_responses", definition=definition, provenance=provenance,
    )


def _calling_mean(scores: pd.Series, dimensions: dict[str, str], provenance: Provenance) -> Metric:
    answered = int(scores.count())
    score_sum = int(scores.sum())
    mean = score_sum / answered if answered else None
    ci = None
    if answered > 1:
        half_width = float(t.ppf((1 + _LEVEL) / 2, answered - 1) * scores.sem())
        ci = ConfidenceInterval(
            lower=max(0.0, mean - half_width), upper=min(10.0, mean + half_width),
            level=_LEVEL, method="student_t_bounded_to_scale",
        )
    return Metric(
        metric_id="calling_intent_mean", dimensions=dimensions, value=mean, numerator=score_sum,
        denominator=answered, n=answered, ci=ci, unit="ordinal_point",
        reason=None if answered else "no_valid_calling_answers",
        definition="Mean stated likelihood of calling 988, on the 0 to 10 scale, among valid answers.",
        provenance=provenance.model_copy(update={"method": "observed_answer_mean"}),
    )


def _date_coverage(
    frame: pd.DataFrame, cohort: str, provenance: Provenance, minimum_n: int,
    statuses: dict[str, CallingDateStatus],
) -> list[Metric]:
    dates = list(frame.groupby("_date", sort=True))
    suppressed = table_suppressions({date: len(rows) for date, rows in dates}, minimum_n)
    output = []
    for date, rows in dates:
        for item, answered in rows[list(_FINGERPRINT_ITEMS)].count().items():
            metric = _share(
                "date_item_coverage", {"cohort": cohort, "training_date": date, "item": item},
                int(answered), len(rows), "Share of eligible responses on this date with a valid answer to this item.",
                provenance,
            )
            output.append(suppress_metric(metric, suppressed[date]) if date in suppressed else metric)
        if cohort == "all_responses":
            status = statuses[date]
            mixed = Metric(
                metric_id="calling_date_mixed", dimensions={"cohort": cohort, "training_date": date},
                value=None if status == "unknown_date" else int(status == "mixed"), n=len(rows),
                reason="unknown_training_date" if status == "unknown_date" else None,
                definition="Indicator for a known date with both valid calling answers and rows without a valid answer.",
                unit="statistic", provenance=provenance,
            )
            output.append(suppress_metric(mixed, suppressed[date]) if date in suppressed else mixed)
    return output


def _calling_by_group(
    groups: dict[str, pd.DataFrame], group_by: str, cohort: str, proxy_dates: set[str],
    provenance: Provenance, minimum_n: int, *, additive: bool,
) -> list[Metric]:
    proxy_groups = {group: rows.loc[rows["_date"].isin(proxy_dates)] for group, rows in groups.items()}
    coverage_mask = table_suppressions({group: len(rows) for group, rows in groups.items()}, minimum_n, additive=additive)
    proxy_mask = table_suppressions({group: len(rows) for group, rows in proxy_groups.items()}, minimum_n, additive=additive)
    mean_mask = table_suppressions(
        {group: int(rows["calling_score"].count()) for group, rows in groups.items()}, minimum_n, additive=additive,
    )
    output = []
    for group, rows in groups.items():
        dimensions = {"cohort": cohort, "group_by": group_by, "group": group}
        proxy = proxy_groups[group]
        coverage = _share(
            "calling_coverage", dimensions, int(rows["calling_score"].count()), len(rows),
            "Valid calling answers divided by eligible survey responses. Item exposure is unknown for blank responses.",
            provenance,
        )
        proxy_coverage = _share(
            "calling_possible_exposure_coverage", dimensions, int(proxy["calling_score"].count()), len(proxy),
            "Valid calling answers divided by responses on known dates with any valid answer in the full sample. This is a date-level exposure proxy.",
            provenance,
        )
        intent = _calling_mean(rows["calling_score"], dimensions, provenance)
        for metric, mask in ((coverage, coverage_mask), (proxy_coverage, proxy_mask), (intent, mean_mask)):
            output.append(suppress_metric(metric, mask[group]) if group in mask else metric)
    return output


def _shuffle_test(
    frame: pd.DataFrame, cohort: str, provenance: Provenance, minimum_n: int, seed: int, shuffles: int,
) -> list[Metric]:
    dates = frame.loc[frame["_date"].ne(_UNKNOWN_DATE)].groupby("_date", sort=True)["calling_score"].agg(["size", "count"])
    sizes = dates["size"].to_numpy(dtype=np.int64)
    observed = dates["count"].to_numpy(dtype=np.int64)
    total, answers = int(sizes.sum()), int(observed.sum())
    statistic = p_value = exceedances = None
    reason = None
    if len(dates) < 2:
        reason = "fewer_than_two_known_dates"
    elif not 0 < answers < total:
        reason = "no_variation_in_answer_status"
    else:
        rate = answers / total
        expected = sizes * rate
        variance = expected * (1 - rate)
        statistic = float(np.sum((observed - expected) ** 2 / variance))
        simulated = np.random.default_rng(seed).multivariate_hypergeometric(sizes, answers, size=shuffles)
        simulated_statistics = np.sum((simulated - expected) ** 2 / variance, axis=1)
        exceedances = int(np.count_nonzero(simulated_statistics >= statistic - 1e-12))
        p_value = (exceedances + 1) / (shuffles + 1)

    test_provenance = provenance.model_copy(update={
        "method": "fixed_date_sizes_answer_shuffle",
        "parameters": {"seed": seed, "shuffles": shuffles},
    })
    dimensions = {"cohort": cohort}
    metrics = [
        Metric(
            metric_id="calling_date_shuffle_statistic", dimensions=dimensions, value=statistic, n=total,
            reason=reason, definition="Pearson statistic for concentration of valid calling answers across known dates.",
            unit="statistic", provenance=test_provenance,
        ),
        Metric(
            metric_id="calling_date_shuffle_p_value", dimensions=dimensions, value=p_value, n=total,
            numerator=exceedances + 1 if exceedances is not None else None,
            denominator=shuffles + 1 if exceedances is not None else None, reason=reason, unit="p_value",
            definition="Shuffle p-value for calling-answer clustering. The shuffles preserve known date sizes and the total number of valid calling answers.",
            provenance=test_provenance,
        ),
    ]
    return [suppress_metric(metric, "below_minimum_n") for metric in metrics] if total < minimum_n else metrics


def _groups(frame: pd.DataFrame, labels: pd.Series) -> dict[str, pd.DataFrame]:
    return {group: frame.loc[rows.index] for group, rows in labels.groupby(labels, sort=True)}


def _concentration(
    groups: dict[str, pd.DataFrame], group_by: str, dominance_threshold: float,
) -> list[SessionConcentration]:
    dates_by_group = {
        group: rows.loc[rows["_date"].ne(_UNKNOWN_DATE), "_date"].value_counts(sort=False).sort_index()
        for group, rows in groups.items()
    }
    output = []
    for group, counts in dates_by_group.items():
        reasons = []
        dominant_date = str(counts.idxmax()) if len(counts) else None
        if dominant_date is not None:
            if counts[dominant_date] / len(groups[group]) >= dominance_threshold:
                reasons.append("dominant_session")
            other_dates = set().union(*(set(dates.index) for other, dates in dates_by_group.items() if other != group))
            if other_dates and other_dates.isdisjoint(counts.index):
                reasons.append("no_shared_dates")
        output.append(SessionConcentration(group_by, group, dominant_date, tuple(reasons)))
    return output


def _concentration_metrics(
    diagnostics: list[SessionConcentration], groups: dict[str, pd.DataFrame], provenance: Provenance,
    minimum_n: int, dominance_threshold: float, *, additive: bool,
) -> list[Metric]:
    suppressed = table_suppressions({group: len(rows) for group, rows in groups.items()}, minimum_n, additive=additive)
    provenance = provenance.model_copy(update={
        "method": "descriptive_training_date_concentration",
        "parameters": {"dominance_threshold": dominance_threshold},
    })
    output = []
    for diagnostic in diagnostics:
        group = diagnostic.group
        dimensions = {"cohort": "all_responses", "group_by": diagnostic.group_by, "group": group}
        for metric_id, flagged, definition in (
            ("calling_group_inseparable", diagnostic.inseparable,
             "Indicator for a group dominated by one training date or with known dates entirely distinct from other groups."),
            ("calling_group_dominant_session", "dominant_session" in diagnostic.reasons,
             "Indicator for a group whose most common known date reaches the configured share of all group responses."),
        ):
            missing = diagnostic.dominant_date is None
            metric = Metric(
                metric_id=metric_id, dimensions=dimensions, value=None if missing else int(flagged),
                n=len(groups[group]), reason="no_known_training_dates" if missing else None,
                definition=definition, unit="statistic", provenance=provenance,
            )
            output.append(suppress_metric(metric, suppressed[group]) if group in suppressed else metric)
    return output


def analyze_survey_versions(
    frame: pd.DataFrame, *, input_hash: str, config_hash: str, known_roles: set[str],
    minimum_n: int = 10, seed: int = 988, shuffles: int = 2000, dominance_threshold: float = 0.8,
) -> SurveyVersionAnalysis:
    """Analyze observed item coverage without assigning exposure to blank answers."""
    if minimum_n < 1 or seed < 0 or shuffles < 1 or not 0.5 < dominance_threshold <= 1:
        raise ValueError("Use a positive minimum and shuffle count, a nonnegative seed, and a dominance threshold above one-half.")

    usable = frame.loc[frame["is_usable_id"]].reset_index(drop=True)
    usable = usable.assign(_date=usable["training_date"].dt.strftime("%Y-%m-%d").fillna(_UNKNOWN_DATE))
    fingerprints = _fingerprints(usable)
    statuses = {fingerprint.training_date or _UNKNOWN_DATE: fingerprint.calling_status for fingerprint in fingerprints}
    proxy_dates = {
        fingerprint.training_date for fingerprint in fingerprints
        if fingerprint.training_date is not None and fingerprint.calling_status in ("all_answered", "mixed")
    }
    concentration = []
    output = []
    for cohort, rows in (
        ("all_responses", usable), ("excluding_flagged", usable.loc[~usable["is_flagged"]]),
    ):
        provenance = Provenance(
            input_hash=input_hash, config_hash=config_hash, method="valid_answer_counts",
            population="Responses with usable IDs" + (" and no quality flags." if cohort == "excluding_flagged" else "."),
        )
        output.extend(_date_coverage(rows, cohort, provenance, minimum_n, statuses))
        output.extend(_shuffle_test(rows, cohort, provenance, minimum_n, seed, shuffles))
        role_labels = role_groups(rows, known_roles)
        for group_by, groups, additive in (
            ("overall", {"Overall": rows}, True),
            ("county", _groups(rows, county_groups(rows["county"])), True),
            ("role", _groups(rows, role_labels), not role_labels.index.has_duplicates),
        ):
            output.extend(_calling_by_group(groups, group_by, cohort, proxy_dates, provenance, minimum_n, additive=additive))
            if cohort == "all_responses" and group_by != "overall":
                diagnostics = _concentration(groups, group_by, dominance_threshold)
                concentration.extend(diagnostics)
                output.extend(_concentration_metrics(
                    diagnostics, groups, provenance, minimum_n, dominance_threshold, additive=additive,
                ))
    return SurveyVersionAnalysis(output, fingerprints, concentration)
