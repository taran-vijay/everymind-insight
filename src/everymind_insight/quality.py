"""Audit response quality and check the impact of a presenter-label decision."""

from collections import Counter
from dataclasses import dataclass

import pandas as pd

from .config import PRESENTER_ITEMS, SCORE_ITEMS, QualityConfig
from .normalization import NormalizationResult


@dataclass(frozen=True)
class QualityResult:
    frame: pd.DataFrame
    report: dict


def _invalid_values(frame: pd.DataFrame, field: str) -> pd.Series:
    answered = frame[field + "_raw"].astype("string").str.strip().fillna("").ne("")
    return (answered & frame[field].isna()).astype(bool)


def _objective_headlines(
    frame: pd.DataFrame,
    objective_columns: dict[str, dict[str, str]],
    *,
    exclude_flagged: bool = False,
) -> dict[str, dict[str, int]]:
    eligible = frame["is_usable_id"]
    if exclude_flagged:
        eligible = eligible & ~frame["is_flagged"]
    headlines = {}
    for skill, pair in objective_columns.items():
        before = frame[pair["before"]]
        after = frame[pair["after"]]
        paired = eligible & before.notna() & after.notna()
        before = before[paired]
        after = after[paired]
        headlines[skill] = {
            "n": len(after),
            "agree_before": int(before.ge(4).sum()),
            "agree_after": int(after.ge(4).sum()),
            "up": int(after.gt(before).sum()),
            "same": int(after.eq(before).sum()),
            "down": int(after.lt(before).sum()),
            "below_agree_after": int(after.lt(4).sum()),
        }
    return headlines


def _presenter_items(frame: pd.DataFrame, sensitivity_masks: dict[str, pd.Series]) -> dict:
    usable = frame["is_usable_id"]
    return {
        item: {
            "n_answered": int(frame.loc[usable, item].notna().sum()),
            "agree_count": int(frame.loc[usable, item].ge(4).sum()),
            "n_label_responses": int((usable & sensitivity_masks[item]).sum()),
        }
        for item in PRESENTER_ITEMS
    }


def _presenter_sensitivity(frame: pd.DataFrame, normalized: NormalizationResult) -> dict:
    alternative = frame.assign(
        **{item: frame[item].mask(normalized.sensitivity_masks[item]) for item in PRESENTER_ITEMS}
    )
    configured_headlines = _objective_headlines(frame, normalized.objective_columns)
    alternative_headlines = _objective_headlines(alternative, normalized.objective_columns)
    return {
        "label": normalized.sensitivity_label,
        "mappings": {
            "as_configured": {
                "label_score": normalized.sensitivity_score,
                "presenter_items": _presenter_items(frame, normalized.sensitivity_masks),
                "objective_headlines": configured_headlines,
            },
            "excluded": {
                "label_score": None,
                "presenter_items": _presenter_items(alternative, normalized.sensitivity_masks),
                "objective_headlines": alternative_headlines,
            },
        },
        "objective_headlines_unchanged": configured_headlines == alternative_headlines,
    }


def build_quality_report(normalized: NormalizationResult, config: QualityConfig) -> QualityResult:
    """Annotate response rows and return only counts and private category diagnostics."""
    frame = normalized.frame.copy()
    frame["is_missing_id"] = frame["id"].isna()
    frame["is_duplicate_id"] = frame["id"].duplicated(keep=False) & ~frame["is_missing_id"]
    frame["is_usable_id"] = ~(frame["is_missing_id"] | frame["is_duplicate_id"])

    # Source timestamps have microsecond precision. Subtracting at that resolution
    # also supports corrupt timestamp pairs more than 292 years apart.
    elapsed = frame["completion_time"].astype("datetime64[us]") - frame["start_time"].astype(
        "datetime64[us]"
    )
    duration = elapsed.dt.total_seconds().astype("Float64")
    frame["duration_seconds"] = duration
    frame["is_speeder"] = (duration.gt(0) & duration.lt(config.speeder_seconds)).fillna(False)
    frame["is_impossible_timestamp"] = duration.le(0).fillna(False)
    frame["is_implausible_duration"] = (
        duration.lt(config.min_duration_seconds) | duration.gt(config.max_duration_seconds)
    ).fillna(False)
    frame["is_invalid_timestamp"] = _invalid_values(frame, "start_time") | _invalid_values(
        frame, "completion_time"
    )
    frame["is_invalid_training_date"] = _invalid_values(frame, "training_date")
    frame["is_invalid_score"] = _invalid_values(frame, SCORE_ITEMS[0]) | _invalid_values(
        frame, SCORE_ITEMS[1]
    )

    objective_ids = [
        field for pair in normalized.objective_columns.values() for field in pair.values()
    ]
    objective_scores = frame[objective_ids]
    frame["is_straightliner"] = objective_scores.notna().all(axis=1) & objective_scores.eq(
        objective_scores.iloc[:, 0], axis=0
    ).all(axis=1)
    reversals = pd.DataFrame(
        {
            skill: (frame[pair["before"]] - frame[pair["after"]])
            .ge(config.large_reversal_min_drop)
            .fillna(False)
            for skill, pair in normalized.objective_columns.items()
        },
        index=frame.index,
    )
    frame["is_large_reversal"] = reversals.any(axis=1)
    flags = (
        "is_missing_id",
        "is_duplicate_id",
        "is_speeder",
        "is_impossible_timestamp",
        "is_implausible_duration",
        "is_invalid_timestamp",
        "is_invalid_training_date",
        "is_invalid_score",
        "is_straightliner",
        "is_large_reversal",
    )
    frame["is_flagged"] = frame[list(flags)].any(axis=1)
    flag_counts = {flag: int(frame[flag].sum()) for flag in (*flags, "is_flagged")}
    flag_combinations = Counter(
        tuple(flag for flag, active in zip(flags, row) if active)
        for row in frame.loc[frame["is_flagged"], list(flags)].itertuples(index=False, name=None)
    )

    measured = duration.dropna()
    presenter_sensitivity = _presenter_sensitivity(frame, normalized)
    objective_headlines = presenter_sensitivity["mappings"]["as_configured"]["objective_headlines"]
    excluding_flagged = _objective_headlines(
        frame, normalized.objective_columns, exclude_flagged=True
    )
    return QualityResult(
        frame,
        {
            "n_rows": len(frame),
            "n_usable": int(frame["is_usable_id"].sum()),
            "n_flagged_usable": int((frame["is_flagged"] & frame["is_usable_id"]).sum()),
            "normalization": normalized.diagnostics,
            "flags": flag_counts,
            "n_flag_assignments": sum(flag_counts[flag] for flag in flags),
            "flag_combinations": [
                {"flags": list(combination), "n_rows": count}
                for combination, count in sorted(flag_combinations.items())
            ],
            "duration": {
                "n_measurable": len(measured),
                "min_seconds": float(measured.min()) if len(measured) else None,
                "max_seconds": float(measured.max()) if len(measured) else None,
                "speeder_below_seconds": config.speeder_seconds,
                "plausible_min_seconds": config.min_duration_seconds,
                "plausible_max_seconds": config.max_duration_seconds,
            },
            "large_reversals_by_skill": {
                skill: int(reversals[skill].sum()) for skill in reversals
            },
            "straightliner_score_counts": {
                str(score): int(objective_scores.iloc[:, 0][frame["is_straightliner"]].eq(score).sum())
                for score in range(1, 6)
            },
            "objective_headlines": objective_headlines,
            "objective_flag_sensitivity": {
                "all_responses": objective_headlines,
                "excluding_flagged": excluding_flagged,
                "delta_excluding_minus_all": {
                    skill: {
                        metric: excluding_flagged[skill][metric] - count
                        for metric, count in metrics.items()
                    }
                    for skill, metrics in objective_headlines.items()
                },
            },
            "presenter_sensitivity": presenter_sensitivity,
        },
    )
