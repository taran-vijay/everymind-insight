"""Paired objective statistics for normalized survey responses."""

from fractions import Fraction

import numpy as np
import pandas as pd
from scipy.stats import PermutationMethod, binomtest, rankdata, wilcoxon
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.proportion import proportion_confint

from .schemas import ConfidenceInterval, Metric, MetricUnit, Provenance


_LEVEL = 0.95
_SCORES = np.arange(1, 6)
_CHANGE = _SCORES[None, :] - _SCORES[:, None]
_AGREE = 4
_POPULATIONS = {
    "all_responses": "Responses with usable IDs, including responses with quality flags.",
    "excluding_flagged": "Responses with usable IDs and no response-quality flags.",
}


def _wilson(numerator: int, denominator: int) -> ConfidenceInterval:
    low, high = proportion_confint(numerator, denominator, alpha=1 - _LEVEL, method="wilson")
    return ConfidenceInterval(lower=float(low), upper=float(high), level=_LEVEL, method="wilson")


def _paired_mean_ci(changes: np.ndarray, seed: int, resamples: int) -> ConfidenceInterval:
    # Resampling the histogram draws the same change distribution as resampling whole pairs.
    support, counts = np.unique(changes, return_counts=True)
    samples = np.random.default_rng(seed).multinomial(len(changes), counts / len(changes), size=resamples)
    tail = (1 - _LEVEL) / 2
    low, high = np.quantile(samples @ support / len(changes), [tail, 1 - tail])
    return ConfidenceInterval(lower=float(low), upper=float(high), level=_LEVEL, method="paired_percentile_bootstrap")


def _objective_metrics(
    frame: pd.DataFrame,
    skill: str,
    pair: dict[str, str],
    cohort: str,
    input_hash: str,
    config_hash: str,
    seed: int,
    resamples: int,
) -> list[Metric]:
    n_eligible = len(frame)
    paired = frame[[pair["before"], pair["after"]]].dropna().to_numpy(dtype=np.int64)
    before, after = paired.T
    n_pairs = len(paired)
    matrix = np.bincount((before - 1) * 5 + after - 1, minlength=25).reshape(5, 5)
    changes = after - before
    agree_before = int(matrix[_AGREE - 1 :, :].sum())
    agree_after = int(matrix[:, _AGREE - 1 :].sum())
    below_after = n_pairs - agree_after
    up = int(matrix[_CHANGE > 0].sum())
    same = int(matrix[_CHANGE == 0].sum())
    down = int(matrix[_CHANGE < 0].sum())
    output: list[Metric] = []

    def add(
        metric_id: str,
        value: float | int | None,
        definition: str,
        unit: MetricUnit,
        *,
        n: int = n_pairs,
        numerator: float | int | None = None,
        denominator: float | int | None = None,
        ci: ConfidenceInterval | None = None,
        method: str = "paired_transition_counts",
        reason: str = "no_complete_pairs",
        dimensions: dict[str, str] | None = None,
        parameters: dict[str, str | int | float | bool] | None = None,
    ) -> None:
        output.append(Metric(
            metric_id=metric_id,
            dimensions={"skill": skill, "cohort": cohort, **(dimensions or {})},
            value=value,
            numerator=numerator,
            denominator=denominator,
            ci=ci,
            n=n,
            reason=reason if value is None else None,
            definition=definition,
            unit=unit,
            provenance=Provenance(
                input_hash=input_hash,
                config_hash=config_hash,
                method=method,
                population=_POPULATIONS[cohort],
                parameters=parameters or {},
            ),
        ))

    add(
        "paired_coverage", n_pairs / n_eligible if n_eligible else None,
        "Share of eligible responses with valid recalled-before and current ratings for the skill.",
        "proportion", n=n_eligible, numerator=n_pairs, denominator=n_eligible, reason="no_eligible_responses",
        method="complete_pair_count",
    )
    shares = (
        ("agree_before", agree_before, "Share selecting Agree or Strongly agree in the recalled-before rating.", True),
        ("agree_after", agree_after, "Share selecting Agree or Strongly agree in the current rating.", True),
        ("movement_up", up, "Share with a higher current rating than recalled-before rating.", False),
        ("movement_same", same, "Share with equal current and recalled-before ratings.", False),
        ("movement_down", down, "Share with a lower current rating than recalled-before rating.", False),
        ("below_agree_after", below_after, "Share selecting below Agree in the current rating.", True),
        (
            "ceiling_share", int(matrix[-1, :].sum()),
            "Share selecting Strongly agree in the recalled-before rating.", False,
        ),
    )
    for metric_id, count, definition, use_wilson in shares:
        add(
            metric_id, count / n_pairs if n_pairs else None, definition, "proportion",
            numerator=count, denominator=n_pairs, ci=_wilson(count, n_pairs) if use_wilson and n_pairs else None,
        )

    net_agree = agree_after - agree_before
    add(
        "agreement_gain", 100 * net_agree / n_pairs if n_pairs else None,
        "Current agreement share minus recalled-before agreement share, in percentage points.",
        "percentage_point", numerator=net_agree, denominator=n_pairs,
    )
    sum_change = int(changes.sum())
    add(
        "mean_ordinal_change", sum_change / n_pairs if n_pairs else None,
        "Mean current minus recalled-before ordinal rating in paired responses.", "ordinal_point",
        numerator=sum_change, denominator=n_pairs,
        ci=_paired_mean_ci(changes, seed, resamples) if n_pairs else None,
        method="paired_mean", parameters={"bootstrap_seed": seed, "bootstrap_resamples": resamples},
    )
    n_headroom = int(matrix[:-1].sum())
    normalized_changes = _CHANGE[:-1] / (5 - _SCORES[:-1, None])
    sum_normalized = float((matrix[:-1] * normalized_changes).sum())
    add(
        "normalized_gain", sum_normalized / n_headroom if n_headroom else None,
        "Mean paired change divided by available rating points for each response with a recalled-before rating below 5. "
        "Negative changes are included.",
        "ratio", n=n_headroom, numerator=sum_normalized, denominator=n_headroom,
        method="mean_of_response_level_normalized_changes", reason="no_headroom" if n_pairs else "no_complete_pairs",
    )

    nonzero = changes[changes != 0]
    n_nonzero = len(nonzero)
    signed_rank = signed_rank_p = rank_difference = rank_total = None
    signed_rank_method = "two_sided_wilcoxon_signed_rank"
    if n_nonzero:
        if n_nonzero == 1:
            method = "exact"
            signed_rank_method += "_exact"
        elif n_nonzero <= 13:
            method = PermutationMethod(n_resamples=np.inf)
            signed_rank_method += "_exhaustive_sign_permutation"
        else:
            method = "asymptotic"
            signed_rank_method += "_normal_approximation"
        result = wilcoxon(nonzero, method=method)
        signed_rank, signed_rank_p = float(result.statistic), float(result.pvalue)
        ranks = rankdata(np.abs(nonzero))
        rank_difference = float(ranks[nonzero > 0].sum() - ranks[nonzero < 0].sum())
        rank_total = float(ranks.sum())
    zero_reason = "no_nonzero_changes" if n_pairs else "no_complete_pairs"
    for metric_id, value, definition, unit in (
        (
            "wilcoxon_statistic", signed_rank,
            "Smaller of the two sums of signed-rank magnitudes for nonzero paired changes.", "statistic",
        ),
        (
            "wilcoxon_p_value", signed_rank_p,
            "Two-sided Wilcoxon signed-rank p-value for symmetry of nonzero paired changes around zero.", "p_value",
        ),
    ):
        add(metric_id, value, definition, unit, n=n_nonzero, reason=zero_reason, method=signed_rank_method)
    add(
        "rank_biserial", rank_difference / rank_total if rank_total else None,
        "Matched-pairs rank-biserial correlation. The positive rank sum minus the negative rank sum, "
        "divided by total rank magnitude. Ties in absolute change receive average ranks.",
        "ratio", n=n_nonzero, numerator=rank_difference, denominator=rank_total,
        method="average_absolute_change_ranks", reason=zero_reason,
    )
    add(
        "sign_test_statistic", up if n_nonzero else None,
        "Number of positive paired changes in the exact sign test.", "statistic",
        n=n_nonzero, method="two_sided_exact_binomial", reason=zero_reason,
    )
    add(
        "sign_test_p_value", float(binomtest(up, n_nonzero).pvalue) if n_nonzero else None,
        "Two-sided exact sign test p-value for equally likely positive and negative changes among changed pairs.",
        "p_value", n=n_nonzero, method="two_sided_exact_binomial", reason=zero_reason,
    )

    agrees = slice(_AGREE - 1, None)
    below = slice(None, _AGREE - 1)
    agreement_table = np.array([
        [matrix[below, below].sum(), matrix[below, agrees].sum()],
        [matrix[agrees, below].sum(), matrix[agrees, agrees].sum()],
    ])
    n_discordant = int(agreement_table[0, 1] + agreement_table[1, 0])
    result = mcnemar(agreement_table, exact=True) if n_discordant else None
    for metric_id, value, definition, unit in (
        (
            "mcnemar_statistic", int(result.statistic) if result else None,
            "Smaller count of the two directions of paired change across Agree.", "statistic",
        ),
        (
            "mcnemar_p_value", float(result.pvalue) if result else None,
            "Two-sided exact McNemar p-value for equally likely directions of change among pairs "
            "that cross the Agree threshold.", "p_value",
        ),
    ):
        add(
            metric_id, value, definition, unit, n=n_discordant, method="two_sided_exact_mcnemar",
            reason="no_discordant_agreement_pairs" if n_pairs else "no_complete_pairs",
        )

    reversal = int(matrix[4, 0])
    add(
        "large_reversal", reversal if n_pairs else None,
        "Count of Strongly agree recalled-before ratings followed by Strongly disagree current ratings. "
        "A large reversal is a review flag.",
        "count", numerator=reversal, denominator=n_pairs,
    )
    for recalled_score, row in enumerate(matrix, start=1):
        for current_score, cell in enumerate(row, start=1):
            add(
                "transition_count", int(cell) if n_pairs else None,
                "Count of complete pairs for the displayed recalled-before and current ratings.",
                "count", numerator=int(cell), denominator=n_pairs,
                dimensions={"before_score": str(recalled_score), "after_score": str(current_score)},
            )
    return output


def _rank_metrics(entries: list[Metric]) -> list[Metric]:
    results = []
    for source_id, rank_id, definition in (
        ("below_agree_after", "gap_rank", "Rank by share below Agree in the current rating, highest gap first."),
        ("agreement_gain", "gain_rank", "Rank by percentage-point increase in agreement, highest increase first."),
    ):
        source = [metric for metric in entries if metric.metric_id == source_id]
        scores = {
            metric.dimensions["skill"]: Fraction(int(metric.numerator), int(metric.denominator))
            for metric in source if metric.value is not None
        }
        for metric in source:
            score = scores.get(metric.dimensions["skill"])
            rank = 1 + sum(other > score for other in scores.values()) if score is not None else None
            results.append(Metric(
                metric_id=rank_id,
                dimensions=metric.dimensions,
                value=rank,
                n=metric.n,
                reason="no_complete_pairs" if rank is None else None,
                definition=definition + " Tied skills share the same rank.",
                unit="rank",
                provenance=metric.provenance.model_copy(update={"method": "descending_competition_rank"}),
            ))
    return results


def _flag_sensitivity_deltas(entries: list[Metric]) -> list[Metric]:
    measures = {"agree_before", "agree_after", "below_agree_after"}
    baseline = {
        (metric.dimensions["skill"], metric.metric_id): metric
        for metric in entries
        if metric.dimensions["cohort"] == "all_responses" and metric.metric_id in measures
    }
    deltas = []
    for filtered in entries:
        if filtered.dimensions["cohort"] != "excluding_flagged" or filtered.metric_id not in measures:
            continue
        skill = filtered.dimensions["skill"]
        unfiltered = baseline[skill, filtered.metric_id]
        numerator = denominator = value = None
        if filtered.value is not None and unfiltered.value is not None:
            numerator = (
                int(filtered.numerator) * int(unfiltered.denominator)
                - int(unfiltered.numerator) * int(filtered.denominator)
            )
            denominator = int(filtered.denominator) * int(unfiltered.denominator)
            value = 100 * numerator / denominator
        deltas.append(Metric(
            metric_id="flag_sensitivity_delta",
            dimensions={"skill": skill, "cohort": "excluding_minus_all", "measure": filtered.metric_id},
            value=value,
            numerator=numerator,
            denominator=denominator,
            n=filtered.n,
            reason="no_complete_pairs_in_one_or_both_cohorts" if value is None else None,
            definition=(
                "Percentage-point difference between the share excluding flagged responses and the share including them."
            ),
            unit="percentage_point",
            provenance=Provenance(
                input_hash=filtered.provenance.input_hash,
                config_hash=filtered.provenance.config_hash,
                method="difference_of_complete_pair_proportions",
                population="Complete pairs in each cohort. The reported n is the number of unflagged pairs.",
            ),
        ))
    return deltas


def analyze_objectives(
    frame: pd.DataFrame,
    objective_columns: dict[str, dict[str, str]],
    *,
    input_hash: str,
    config_hash: str,
    seed: int = 988,
    bootstrap_resamples: int = 2000,
) -> list[Metric]:
    """Analyze complete pairs per skill, with and without flagged usable responses."""
    if seed < 0 or bootstrap_resamples < 1:
        raise ValueError("Use a nonnegative bootstrap seed and at least one bootstrap resample.")

    usable = frame.loc[frame["is_usable_id"]]
    ledger: list[Metric] = []
    for cohort, subset in (
        ("all_responses", usable),
        ("excluding_flagged", usable.loc[~usable["is_flagged"]]),
    ):
        entries: list[Metric] = []
        for skill in sorted(objective_columns):
            entries.extend(_objective_metrics(
                subset, skill, objective_columns[skill], cohort, input_hash, config_hash, seed, bootstrap_resamples,
            ))
        ledger.extend(entries)
        ledger.extend(_rank_metrics(entries))
    ledger.extend(_flag_sensitivity_deltas(ledger))
    return ledger
