"""Presenter ratings and recommendation scores, with descriptive associations."""

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from .config import PRESENTER_ITEMS
from .metrics import _wilson
from .schemas import ConfidenceInterval, Metric, Provenance
from .suppression import suppress_metric, table_suppressions


_RECOMMEND = "recommend_score"
_MIN_BOOTSTRAP_VALID_SHARE = 0.8
_NEIGHBORHOOD_NULL = 1 / 3


def _binary_suppression(numerator: int, denominator: int, minimum_n: int) -> str | None:
    # The opposite count follows directly from the denominator in a binary share.
    return "below_minimum_n" if min(numerator, denominator - numerator) < minimum_n else None


def _share(
    metric_id: str,
    dimensions: dict[str, str],
    numerator: int,
    denominator: int,
    definition: str,
    provenance: Provenance,
    *,
    interval: bool = False,
    suppression: str | None = None,
) -> Metric:
    metric = Metric(
        metric_id=metric_id,
        dimensions=dimensions,
        value=numerator / denominator if denominator else None,
        numerator=numerator,
        denominator=denominator,
        ci=_wilson(numerator, denominator) if interval and denominator else None,
        n=denominator,
        reason=None if denominator else "no_responses_in_denominator",
        unit="proportion",
        definition=definition,
        provenance=provenance,
    )
    return suppress_metric(metric, suppression) if suppression else metric


def _distribution(
    counts: dict[str, int],
    metric_id: str,
    dimension: str,
    dimensions: dict[str, str],
    definition: str,
    provenance: Provenance,
    minimum_n: int,
    *,
    interval: bool = False,
) -> list[Metric]:
    n = sum(counts.values())
    reasons = table_suppressions(counts, minimum_n)
    return [
        _share(
            metric_id, {**dimensions, dimension: cell}, count, n, definition, provenance,
            interval=interval, suppression="below_minimum_n" if n < minimum_n else reasons.get(cell),
        )
        for cell, count in counts.items()
    ]


def _ratings(
    scores: pd.Series, item: str, cohort: str, provenance: Provenance, minimum_n: int,
) -> list[Metric]:
    is_presenter = item != _RECOMMEND
    prefix = "presenter" if is_presenter else "recommend"
    dimensions = {"cohort": cohort, "item": item} if is_presenter else {"cohort": cohort}
    values = scores.dropna().to_numpy(dtype=np.int64)
    n = len(values)
    answered = Metric(
        metric_id=f"{prefix}_answered", dimensions=dimensions, value=n, n=n, unit="count",
        definition="Number of valid answers to this item.", provenance=provenance,
    )
    if n < minimum_n:
        answered = suppress_metric(answered, "below_minimum_n")
    coverage = _share(
        f"{prefix}_coverage", dimensions, n, len(scores),
        "Share of eligible responses with a valid answer to this item.", provenance,
        interval=True, suppression=_binary_suppression(n, len(scores), minimum_n),
    )
    # Normalization validates integer scale ranges before this analysis.
    bins = np.bincount(values, minlength=6 if is_presenter else 11)
    counts = {str(score): int(bins[score]) for score in range(1 if is_presenter else 0, len(bins))}
    distribution = _distribution(
        counts, f"{prefix}_distribution", "score", dimensions,
        "Share of valid answers with the displayed score.", provenance, minimum_n,
    )
    if is_presenter:
        agree = int(bins[4:].sum())
        agreement = _share(
            "presenter_agreement", dimensions, agree, n,
            "Share of valid presenter ratings scored Agree or Strongly agree.", provenance,
            interval=True, suppression=_binary_suppression(agree, n, minimum_n),
        )
        return [answered, coverage, agreement, *distribution]

    segments = _distribution(
        {"detractor": int(bins[:7].sum()), "passive": int(bins[7:9].sum()), "promoter": int(bins[9:].sum())},
        "recommend_segment", "segment", dimensions,
        "Share of valid recommendation scores in the segment. Detractors are 0–6, passives 7–8, and promoters 9–10.",
        provenance, minimum_n, interval=True,
    )
    return [answered, coverage, *distribution, *segments, *_heaping(bins, dimensions, provenance, minimum_n)]


def _heaping(
    bins: np.ndarray, dimensions: dict[str, str], provenance: Provenance, minimum_n: int,
) -> list[Metric]:
    at_five = int(bins[5])
    nearby = int(bins[4:7].sum())
    suppression = _binary_suppression(at_five, nearby, minimum_n)
    share = _share(
        "recommend_heaping_local_share", dimensions, at_five, nearby,
        "Share of valid scores of 4, 5, or 6 that are exactly 5.", provenance,
        interval=True, suppression=suppression,
    )
    test = Metric(
        metric_id="recommend_heaping_p_value", dimensions=dimensions,
        value=float(binomtest(at_five, nearby, p=_NEIGHBORHOOD_NULL, alternative="greater").pvalue) if nearby else None,
        n=nearby, unit="p_value", reason=None if nearby else "no_scores_from_four_to_six",
        definition=(
            "One-sided exact test for excess scores at 5 among scores of 4, 5, or 6. The reference assumes "
            "that the probability of 5 equals the average probability of its two neighbors. "
            "The result describes score concentration."
        ),
        provenance=provenance.model_copy(update={
            "method": "one_sided_exact_binomial_local_midpoint",
            "parameters": {"null_center_share": _NEIGHBORHOOD_NULL},
        }),
    )
    return [share, suppress_metric(test, suppression) if suppression else test]


def _spearman_from_tables(tables: np.ndarray) -> np.ndarray:
    """Calculate Pearson correlations on tied midranks from paired score counts."""
    rating_counts = tables.sum(axis=-1)
    gain_counts = tables.sum(axis=-2)
    n = rating_counts.sum(axis=-1)[..., None]
    rating_ranks = rating_counts.cumsum(axis=-1) - (rating_counts + n) / 2
    gain_ranks = gain_counts.cumsum(axis=-1) - (gain_counts + n) / 2
    cross_product = np.einsum("...i,...ij,...j->...", rating_ranks, tables, gain_ranks)
    rating_squares = (rating_counts * rating_ranks**2).sum(axis=-1)
    gain_squares = (gain_counts * gain_ranks**2).sum(axis=-1)
    scale = np.sqrt(rating_squares * gain_squares)
    correlations = np.divide(cross_product, scale, out=np.full_like(scale, np.nan), where=scale > 0)
    return np.clip(correlations, -1, 1)


def _spearman_interval(
    table: np.ndarray, seed: int, resamples: int,
) -> ConfidenceInterval | None:
    # A multinomial over the joint table is equivalent to resampling whole respondent pairs.
    n = int(table.sum())
    draws = np.random.default_rng(seed).multinomial(n, table.ravel() / n, size=resamples)
    coefficients = _spearman_from_tables(draws.reshape(-1, *table.shape))
    defined = coefficients[np.isfinite(coefficients)]
    if len(defined) < _MIN_BOOTSTRAP_VALID_SHARE * resamples:
        return None
    low, high = np.quantile(defined, [0.025, 0.975])
    return ConfidenceInterval(lower=float(low), upper=float(high), level=0.95, method="paired_percentile_bootstrap")


def _association(
    scores: pd.Series,
    gain: pd.Series,
    dimensions: dict[str, str],
    provenance: Provenance,
    seed: int,
    resamples: int,
    minimum_n: int,
) -> Metric:
    presenter = scores.name != _RECOMMEND
    pairs = pd.DataFrame({"score": scores, "gain": gain}).dropna().to_numpy(dtype=np.int64)
    n = len(pairs)
    value = ci = None
    reason = "fewer_than_three_complete_rating_gain_pairs"
    if n >= max(3, minimum_n):
        rating, change = pairs.T
        width = 5 if presenter else 11
        index = rating - int(presenter)
        table = np.bincount(index * 9 + change + 4, minlength=width * 9).reshape(width, 9)
        coefficient = float(_spearman_from_tables(table))
        if np.isfinite(coefficient):
            value = coefficient
            ci = _spearman_interval(table, seed, resamples)
            reason = None if ci else "too_many_degenerate_bootstrap_resamples"
        else:
            reason = "constant_score_or_skill_change"

    metric = Metric(
        metric_id="presenter_gain_spearman" if presenter else "recommend_gain_spearman",
        dimensions=dimensions, value=value, ci=ci, n=n, reason=reason, unit="ratio",
        definition=(
            "Spearman association between the rating and paired current-minus-recalled skill change. "
            "The interval resamples whole complete rating-and-change pairs and uses defined replicates "
            "when at least 80% are nondegenerate."
        ),
        provenance=provenance.model_copy(update={
            "method": "spearman_tied_midranks_paired_bootstrap",
            "parameters": {"bootstrap_seed": seed, "bootstrap_resamples": resamples},
        }),
    )
    return suppress_metric(metric, "below_minimum_n") if n < minimum_n else metric


def analyze_delivery(
    frame: pd.DataFrame,
    objective_columns: dict[str, dict[str, str]],
    *,
    input_hash: str,
    config_hash: str,
    seed: int = 988,
    bootstrap_resamples: int = 2000,
    minimum_n: int = 10,
    public_only: bool = False,
) -> list[Metric]:
    """Analyze valid delivery and recommendation ratings with and without flagged responses."""
    if seed < 0 or bootstrap_resamples < 1 or minimum_n < 1:
        raise ValueError("Use a nonnegative seed and positive resample and minimum sample counts.")

    usable = frame.loc[frame["is_usable_id"]]
    ledger = []
    for cohort, subset, population in (
        ("all_responses", usable, "Responses with usable IDs, including responses with quality flags."),
        ("excluding_flagged", usable.loc[~usable["is_flagged"]], "Responses with usable IDs and no quality flags."),
    ):
        if public_only and cohort != "all_responses": continue
        provenance = Provenance(
            input_hash=input_hash, config_hash=config_hash, method="valid_score_counts", population=population,
        )
        gains = {
            skill: subset[pair["after"]] - subset[pair["before"]]
            for skill, pair in sorted(objective_columns.items())
        }
        for item in (*PRESENTER_ITEMS, _RECOMMEND):
            scores = subset[item]
            ledger.extend(_ratings(scores, item, cohort, provenance, minimum_n))
            if public_only: continue
            for skill, gain in gains.items():
                dimensions = {"cohort": cohort, "skill": skill}
                if item != _RECOMMEND:
                    dimensions["item"] = item
                ledger.append(_association(scores, gain, dimensions, provenance, seed, bootstrap_resamples, minimum_n))
    return ledger
