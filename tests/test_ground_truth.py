import hashlib
import json
from functools import cache
from pathlib import Path

import pytest

from everymind_insight.config import load_config
from everymind_insight.ingestion import ingest
from everymind_insight.metrics import analyze_objectives
from everymind_insight.normalization import normalize
from everymind_insight.quality import build_quality_report


REFERENCE_INPUT_HASH = "72b08ff71ede02e4d6203e6096ee49904dd47fc1b74bb1f4e8539c8d263c6b26"
REFERENCE_N = 1299


@cache
def _reference_metrics(workbook: Path):
    config = load_config()
    config_bytes = json.dumps(config.model_dump(mode="json"), sort_keys=True).encode()
    incoming = ingest(workbook, config.registry)
    assert incoming.audit["input_hash"] == REFERENCE_INPUT_HASH, (
        "Use the original reference export for the frozen Phase 2 counts."
    )
    normalized = normalize(incoming.frame, config.normalization, config.registry)
    quality = build_quality_report(normalized, config.quality)
    return analyze_objectives(
        quality.frame,
        normalized.objective_columns,
        input_hash=REFERENCE_INPUT_HASH,
        config_hash=hashlib.sha256(config_bytes).hexdigest(),
    )


@pytest.mark.parametrize(
    ("skill", "agree_before", "agree_after", "before_display", "after_display", "up", "same", "down", "gap", "ceiling"),
    [
        pytest.param("identify_crises", 938, 1168, "72.2%", "89.9%", 571, 668, 60, 131, 235, id="identify-crises"),
        pytest.param("describe_988", 604, 1175, "46.5%", "90.5%", 861, 383, 55, 124, 182, id="describe-988"),
        pytest.param("know_when_to_use_988", 723, 1199, "55.7%", "92.3%", 759, 488, 52, 100, 281, id="know-when-to-use-988"),
    ],
)
def test_reference_objective_counts(
    survey_workbook, skill, agree_before, agree_after, before_display, after_display, up, same, down, gap, ceiling
):
    metrics = {
        metric.metric_id: metric
        for metric in _reference_metrics(survey_workbook)
        if metric.dimensions == {"skill": skill, "cohort": "all_responses"}
    }
    expected = {
        "agree_before": agree_before,
        "agree_after": agree_after,
        "movement_up": up,
        "movement_same": same,
        "movement_down": down,
        "below_agree_after": gap,
        "ceiling_share": ceiling,
    }
    for metric_id, count in expected.items():
        metric = metrics[metric_id]
        assert (metric.numerator, metric.denominator, metric.n) == (count, REFERENCE_N, REFERENCE_N)
        assert metric.value == pytest.approx(count / REFERENCE_N)
    before = metrics["agree_before"]
    after = metrics["agree_after"]
    assert f"{before.value:.1%}" == before_display
    assert f"{after.value:.1%}" == after_display
    gain = metrics["agreement_gain"]
    assert (gain.numerator, gain.denominator) == (agree_after - agree_before, REFERENCE_N)
    assert gain.value == pytest.approx(100 * (agree_after - agree_before) / REFERENCE_N)
    gap_order = ("identify_crises", "describe_988", "know_when_to_use_988")
    gain_order = ("describe_988", "know_when_to_use_988", "identify_crises")
    assert metrics["gap_rank"].value == gap_order.index(skill) + 1
    assert metrics["gain_rank"].value == gain_order.index(skill) + 1
    print(
        f"\n{skill} | n={before.n:,} | agree before {before.numerator:,} ({before.value:.1%})"
        f" | agree after {after.numerator:,} ({after.value:.1%})"
        f" | up/same/down {metrics['movement_up'].numerator}/{metrics['movement_same'].numerator}/"
        f"{metrics['movement_down'].numerator} | below Agree after {metrics['below_agree_after'].numerator}"
        f" | ceiling count {metrics['ceiling_share'].numerator}"
    )


def test_reference_know_when_transitions(survey_workbook):
    transitions = {
        (metric.dimensions["before_score"], metric.dimensions["after_score"]): metric
        for metric in _reference_metrics(survey_workbook)
        if metric.metric_id == "transition_count"
        and metric.dimensions["skill"] == "know_when_to_use_988"
        and metric.dimensions["cohort"] == "all_responses"
    }
    expected = {("5", "1"): 4, ("1", "5"): 66, ("4", "5"): 247, ("5", "5"): 255}
    for cell, count in expected.items():
        metric = transitions[cell]
        assert (metric.value, metric.numerator, metric.denominator, metric.n) == (count, count, REFERENCE_N, REFERENCE_N)
    print("\nKnow when to use 988 transitions | 5->1: 4 | 1->5: 66 | 4->5: 247 | 5->5: 255")
