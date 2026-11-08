"""Objective summaries by subgroup and county comparisons adjusted for role mix."""

from dataclasses import dataclass
from math import exp, isclose
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import linprog
from statsmodels.stats.proportion import proportion_confint
from statsmodels.tools.sm_exceptions import PerfectSeparationError, PerfectSeparationWarning

from .config import NormalizationConfig
from .metrics import _wilson
from .schemas import ConfidenceInterval, Metric, MetricUnit, Provenance
from .suppression import suppress_metric, table_suppressions


_COUNTIES = ("Anne Arundel", "Prince George's", "Other counties")
_REFERENCE = _COUNTIES[0]
_UNOBSERVED_ROLES = {"Unknown role", "Missing role"}


def county_groups(county: pd.Series) -> pd.Series:
    """Use the two named counties, a bucket for other reported counties, and a missing bucket."""
    return county.where(county.isin(_COUNTIES), "Other counties").where(county.notna(), "Missing county")


def _approved_labels(values: pd.Series, known: set[str], unknown: str, missing: str) -> pd.Series:
    return values.where(values.isin(known), unknown).where(values.notna(), missing)


def role_groups(frame: pd.DataFrame, known_roles: set[str]) -> pd.Series:
    """Expand configured role memberships without exposing unapproved labels."""
    expanded = _approved_labels(
        frame["role_groups"].explode(), known_roles | {"Multiple roles"}, "Unknown role", "Missing role"
    )
    memberships = pd.DataFrame({"row": expanded.index, "group": expanded.array}).drop_duplicates()
    return memberships.set_index("row")["group"]


@dataclass(frozen=True)
class _Scope:
    provenance: Provenance
    cohort: str
    minimum_n: int

    def metric(
        self, metric_id: str, value: int | float | None, n: int, unit: MetricUnit,
        definition: str, dimensions: dict[str, str], method: str, *,
        numerator: int | float | None = None, denominator: int | float | None = None,
        ci: ConfidenceInterval | None = None, reason: str | None = None,
        parameters: dict[str, str | int | float | bool] | None = None,
        suppression: str | None = None,
    ) -> Metric:
        metric = Metric(
            metric_id=metric_id, dimensions={"cohort": self.cohort, **dimensions}, value=value,
            n=n, unit=unit, definition=definition, numerator=numerator, denominator=denominator,
            ci=ci, reason=reason, provenance=self.provenance.model_copy(update={
                "method": method, "parameters": parameters or {},
            }),
        )
        return suppress_metric(metric, suppression) if suppression else metric


def _memberships(frame: pd.DataFrame, normalization: NormalizationConfig) -> dict[str, pd.Series]:
    return {
        "county": county_groups(frame["county"]),
        "role": role_groups(frame, set(normalization.role_aliases.values())),
        "language": _approved_labels(
            frame["language"], set(normalization.language_aliases.values()), "Unknown language", "Missing language"
        ),
        "training_month": frame["training_date"].dt.strftime("%Y-%m").fillna("Missing training month"),
    }


def _group_tables(
    scope: _Scope, frame: pd.DataFrame, memberships: dict[str, pd.Series],
    objective_columns: dict[str, dict[str, str]], labels: dict[str, list[str]],
) -> tuple[list[Metric], dict[str, dict[str, str]]]:
    ledger = []
    county_suppressions = {}
    for grouping, groups in memberships.items():
        indexes = groups.groupby(groups, sort=True).groups
        subgroup_frames = {group: frame.loc[indexes.get(group, [])] for group in labels[grouping]}
        additive = not groups.index.has_duplicates
        totals = {group: len(subgroup) for group, subgroup in subgroup_frames.items()}
        withheld_totals = table_suppressions(totals, scope.minimum_n, additive=additive)
        for group, n in totals.items():
            ledger.append(scope.metric(
                "subgroup_response_count", n, n, "count", "Usable responses assigned to this subgroup.",
                {"group_by": grouping, "group": group}, "subgroup_count",
                suppression=withheld_totals.get(group),
            ))

        for skill, pair in sorted(objective_columns.items()):
            paired = {
                group: subgroup[[pair["before"], pair["after"]]].dropna()
                for group, subgroup in subgroup_frames.items()
            }
            withheld = table_suppressions(
                {group: len(rows) for group, rows in paired.items()}, scope.minimum_n, additive=additive
            )
            if grouping == "county":
                county_suppressions[skill] = withheld
            for group, rows in paired.items():
                n = len(rows)
                before = int(rows[pair["before"]].ge(4).sum())
                after = int(rows[pair["after"]].ge(4).sum())
                dimensions = {"group_by": grouping, "group": group, "skill": skill}
                reason = "no_complete_pairs" if not n else None
                for metric_id, count, definition in (
                    ("subgroup_agree_before", before, "Recalled-before agreement among complete pairs."),
                    ("subgroup_agree_after", after, "Current agreement among complete pairs."),
                    ("subgroup_below_agree_after", n - after, "Current share below Agree among complete pairs."),
                ):
                    ledger.append(scope.metric(
                        metric_id, count / n if n else None, n, "proportion", definition,
                        dimensions, "complete_pair_proportion", numerator=count, denominator=n,
                        ci=_wilson(count, n) if n else None, reason=reason, suppression=withheld.get(group),
                    ))
                gain = after - before
                ledger.append(scope.metric(
                    "subgroup_agreement_gain", 100 * gain / n if n else None, n, "percentage_point",
                    "Current agreement minus recalled-before agreement among complete pairs, in percentage points.",
                    dimensions, "paired_agreement_difference", numerator=gain, denominator=n,
                    reason=reason, suppression=withheld.get(group),
                ))
    return ledger, county_suppressions


def _standardization(
    scope: _Scope, rows: pd.DataFrame, target: pd.Series, skill: str, withheld: dict[str, str],
) -> tuple[list[Metric], dict[str, Metric]]:
    target_n = int(target.sum())
    observed_roles = set(target.index) - _UNOBSERVED_ROLES
    adjusted = {}
    ledger = []
    for county in _COUNTIES:
        local = rows.loc[rows["county"].eq(county)]
        n = len(local)
        strata = local.groupby("role")["agrees"].agg(["size", "sum"]).reindex(target.index, fill_value=0)
        support = int(target[strata["size"].gt(0)].sum())
        sparse = bool(strata["size"].between(1, scope.minimum_n - 1).any())
        suppression = withheld.get(county) or ("below_minimum_n" if n < scope.minimum_n else None)
        dimensions = {"group_by": "county", "group": county, "skill": skill}
        ledger.append(scope.metric(
            "county_role_standardization_support", support / target_n if observed_roles else None, target_n,
            "proportion", "Share of the eligible cohort's role distribution represented in this county's paired responses.",
            dimensions, "observed_role_stratum_coverage", numerator=support, denominator=target_n,
            reason=("no_complete_pairs" if not target_n else "no_observed_roles") if not observed_roles else None,
            parameters={"has_sparse_role_strata": sparse}, suppression=suppression,
        ))
        weighted_agreement = interval = None
        reason = "no_complete_pairs" if not n else "incomplete_role_overlap"
        if n and not observed_roles:
            reason = "no_observed_roles"
        elif n and support == target_n:
            weighted_agreement = float((target * strata["sum"] / strata["size"]).sum())
            # Treat observed target weights as fixed. Simultaneous stratum bounds
            # give conservative weighted limits even for all-Agree strata.
            lower, upper = proportion_confint(
                strata["sum"].to_numpy(), strata["size"].to_numpy(), alpha=0.05 / len(target), method="beta"
            )
            interval = ConfidenceInterval(
                lower=float(target @ lower / target_n), upper=float(target @ upper / target_n),
                level=0.95, method="weighted_bonferroni_clopper_pearson",
            )
            reason = None
        metric = scope.metric(
            "county_role_standardized_agree_after", weighted_agreement / target_n if reason is None else None,
            n, "proportion", "Current agreement standardized to the eligible cohort's role distribution.",
            dimensions, "direct_role_standardization", numerator=weighted_agreement, denominator=target_n,
            ci=interval, reason=reason, parameters={"has_sparse_role_strata": sparse}, suppression=suppression,
        )
        adjusted[county] = metric
        ledger.append(metric)
    return ledger, adjusted


def _county_gaps(
    scope: _Scope, rows: pd.DataFrame, skill: str, adjusted: dict[str, Metric], withheld: dict[str, str],
) -> list[Metric]:
    ledger = []
    raw = rows.groupby("county")["agrees"].agg(["size", "sum"])
    for county in _COUNTIES[1:]:
        dimensions = {"group_by": "county", "group": county, "reference": _REFERENCE, "skill": skill}
        local_n, local_agree = (int(number) for number in raw.loc[county]) if county in raw.index else (0, 0)
        reference_n, reference_agree = (
            (int(number) for number in raw.loc[_REFERENCE]) if _REFERENCE in raw.index else (0, 0)
        )
        suppression = withheld.get(county) or withheld.get(_REFERENCE)
        n = min(local_n, reference_n)
        if n < scope.minimum_n:
            suppression = suppression or "below_minimum_n"
        raw_denominator = local_n * reference_n
        raw_numerator = local_agree * reference_n - reference_agree * local_n
        raw_gap = 100 * raw_numerator / raw_denominator if raw_denominator else None
        ledger.append(scope.metric(
            "county_unadjusted_gap", raw_gap, n, "percentage_point",
            "Current agreement difference from Anne Arundel before role adjustment, in percentage points. "
            "The reported n is the smaller of the two county samples.",
            dimensions, "difference_of_complete_pair_proportions", numerator=raw_numerator,
            denominator=raw_denominator, reason="no_complete_pairs_in_one_or_both_counties" if not n else None,
            suppression=suppression,
        ))
        local, reference = adjusted[county], adjusted[_REFERENCE]
        adjusted_denominator = local.denominator
        adjusted_numerator = adjusted_gap = None
        unavailable_reason = local.reason or reference.reason or "incomplete_role_overlap"
        interpretation = (
            "Role adjustment requires observed roles."
            if unavailable_reason == "no_observed_roles"
            else "Insufficient overlap to compare the counties at the same role mix."
        )
        if local.value is not None and reference.value is not None:
            adjusted_numerator = local.numerator - reference.numerator
            adjusted_gap = 100 * adjusted_numerator / adjusted_denominator
            if raw_gap * adjusted_gap < 0 and min(abs(raw_gap), abs(adjusted_gap)) >= 0.1:
                interpretation = "The direction of the observed difference reversed after equalizing the role mix."
            elif isclose(abs(raw_gap), abs(adjusted_gap), abs_tol=0.1):
                interpretation = "The size of the observed difference changed by less than 0.1 percentage points."
            elif abs(adjusted_gap) < abs(raw_gap):
                interpretation = "The observed difference narrowed at the same role mix, consistent with a composition effect."
            else:
                interpretation = "The observed difference widened at the same role mix."
        ledger.append(scope.metric(
            "county_standardized_gap", adjusted_gap, n, "percentage_point",
            "Current agreement difference from Anne Arundel at the same overall role mix, in percentage points. "
            "The reported n is the smaller of the two county samples.",
            dimensions, "difference_of_directly_standardized_proportions", numerator=adjusted_numerator,
            denominator=adjusted_denominator, reason=unavailable_reason if adjusted_gap is None else None,
            parameters={"interpretation": interpretation}, suppression=suppression,
        ))
    return ledger


def _separated(design: np.ndarray, agrees: np.ndarray) -> bool:
    """Check for a direction classifying all outcomes weakly and some strictly."""
    signed = np.unique(np.where(agrees[:, None], design, -design), axis=0)
    fit = linprog(-signed.sum(axis=0), A_ub=-signed, b_ub=np.zeros(len(signed)), bounds=(-1, 1), method="highs")
    return fit.success and -fit.fun > 1e-7


def _fit_county_model(rows: pd.DataFrame, minimum_clusters: int) -> tuple[object | None, str | None]:
    if _REFERENCE not in set(rows["county"]) or rows["county"].nunique() < 2:
        return None, "county_comparison_unavailable"
    if not set(rows["role"]) - _UNOBSERVED_ROLES:
        return None, "no_observed_roles"
    if rows["training_date"].nunique() < minimum_clusters:
        return None, "too_few_training_date_clusters"
    county = pd.get_dummies(rows["county"], prefix="county", dtype=float).drop(columns=f"county_{_REFERENCE}")
    roles = pd.get_dummies(rows["role"], prefix="role", dtype=float).iloc[:, 1:]
    design = sm.add_constant(pd.concat([county, roles], axis=1), has_constant="add")
    design_values = design.to_numpy()
    if np.linalg.matrix_rank(design_values) != design.shape[1]:
        return None, "county_and_role_are_collinear"
    if _separated(design_values, rows["agrees"].to_numpy()):
        return None, "separated_outcome"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", PerfectSeparationWarning)
            fit = sm.GLM(rows["agrees"].astype(int), design, family=sm.families.Binomial()).fit(
                cov_type="cluster", cov_kwds={"groups": rows["training_date"], "use_correction": True}, use_t=True
            )
    except (PerfectSeparationError, PerfectSeparationWarning):
        return None, "separated_outcome"
    except (ValueError, np.linalg.LinAlgError):
        return None, "cluster_covariance_unavailable"
    return (fit, None) if fit.converged else (None, "model_did_not_converge")


def _model_metrics(
    scope: _Scope, paired: pd.DataFrame, skill: str, withheld: dict[str, str], minimum_clusters: int,
) -> list[Metric]:
    rows = paired.loc[paired["county"].isin(_COUNTIES)].dropna(subset=["training_date"])
    training_dates = rows.groupby("county")["training_date"].nunique()
    county_counts = rows["county"].value_counts()
    counties_with_roles = set(rows.loc[~rows["role"].isin(_UNOBSERVED_ROLES), "county"])
    cluster_count = rows["training_date"].nunique()
    fit, model_reason = _fit_county_model(rows, minimum_clusters)
    entries = []
    for county in _COUNTIES[1:]:
        dimensions = {"group_by": "county", "group": county, "reference": _REFERENCE, "skill": skill}
        suppression = withheld.get(county) or withheld.get(_REFERENCE)
        if min(county_counts.get(county, 0), county_counts.get(_REFERENCE, 0)) < scope.minimum_n:
            suppression = suppression or "below_minimum_n"
        reason = model_reason
        term = f"county_{county}"
        odds_ratio = p_value = interval = None
        if fit is not None:
            if not {county, _REFERENCE} <= counties_with_roles:
                reason = "no_observed_roles_for_one_or_both_counties"
            elif term not in fit.params or min(training_dates.get(county, 0), training_dates.get(_REFERENCE, 0)) < 2:
                reason = "too_few_county_training_date_clusters"
            else:
                lower, upper = fit.conf_int().loc[term]
                estimate = fit.params[term]
                p_value = float(fit.pvalues[term])
                if not np.isfinite([lower, upper, estimate, p_value]).all() or upper > 709 or lower < -708 or upper <= lower:
                    p_value = None
                    reason = "cluster_covariance_unavailable"
                else:
                    odds_ratio = exp(estimate)
                    interval = ConfidenceInterval(
                        lower=exp(lower), upper=exp(upper), level=0.95, method="training_date_cluster_robust_t"
                    )
        parameters = {"training_date_clusters": int(cluster_count), "minimum_clusters": minimum_clusters}
        method = "logistic_county_plus_role_clustered_by_training_date"
        entries.extend([
            scope.metric(
                "county_model_odds_ratio", odds_ratio, len(rows), "ratio",
                "Odds ratio for current agreement relative to Anne Arundel, adjusted for role. "
                "Standard errors are clustered by training date. n is the model sample across included counties.",
                dimensions, method, ci=interval, reason=reason, parameters=parameters, suppression=suppression,
            ),
            scope.metric(
                "county_model_p_value", p_value, len(rows), "p_value",
                "Two-sided cluster-robust test of the role-adjusted county contrast relative to Anne Arundel.",
                dimensions, method, reason=reason, parameters=parameters, suppression=suppression,
            ),
        ])
    return entries


def analyze_subgroups(
    frame: pd.DataFrame, objective_columns: dict[str, dict[str, str]], normalization: NormalizationConfig, *,
    input_hash: str, config_hash: str, minimum_n: int = 10, minimum_clusters: int = 8, public_only: bool = False,
) -> list[Metric]:
    """Summarize paired skills and role-adjusted county contrasts in both quality cohorts."""
    if minimum_n < 1 or minimum_clusters < 2:
        raise ValueError("Use a minimum subgroup size of at least one and at least two model clusters.")
    usable = frame.loc[frame["is_usable_id"]].reset_index(drop=True)
    labels = {grouping: sorted(groups.unique()) for grouping, groups in _memberships(usable, normalization).items()}
    ledger = []
    for cohort, subset, population in (
        ("all_responses", usable, "Responses with usable IDs, including quality-flagged responses."),
        ("excluding_flagged", usable.loc[~usable["is_flagged"]], "Responses with usable IDs and no quality flags."),
    ):
        if public_only and cohort != "all_responses": continue
        scope = _Scope(Provenance(input_hash=input_hash, config_hash=config_hash, method="subgroup_analysis",
                                  population=population), cohort, minimum_n)
        memberships = _memberships(subset, normalization)
        entries, withheld = _group_tables(scope, subset, memberships, objective_columns, labels)
        ledger.extend(entries)
        if public_only: continue
        disjoint_role = _approved_labels(
            subset["role_group"], set(normalization.role_aliases.values()) | {"Multiple roles"},
            "Unknown role", "Missing role",
        )
        role_target = disjoint_role.value_counts().sort_index()
        for skill, pair in sorted(objective_columns.items()):
            pairs = subset.loc[subset[[pair["before"], pair["after"]]].notna().all(axis=1)]
            rows = pd.DataFrame({
                "county": memberships["county"].loc[pairs.index], "role": disjoint_role.loc[pairs.index],
                "agrees": pairs[pair["after"]].ge(4).astype(bool), "training_date": pairs["training_date"],
            })
            adjustment, adjusted = _standardization(scope, rows, role_target, skill, withheld[skill])
            ledger.extend(adjustment)
            ledger.extend(_county_gaps(scope, rows, skill, adjusted, withheld[skill]))
            ledger.extend(_model_metrics(scope, rows, skill, withheld[skill], minimum_clusters))
    return ledger
