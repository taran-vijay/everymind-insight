import numpy as np
import pandas as pd
import pytest
from scipy.stats import binomtest, spearmanr

from everymind_insight.config import OBJECTIVE_SKILLS, PRESENTER_ITEMS, load_config
from everymind_insight.delivery import analyze_delivery
from everymind_insight.ingestion import ingest
from everymind_insight.normalization import normalize
from everymind_insight.quality import build_quality_report


PAIRS = {skill: {"before": f"{skill}_before", "after": f"{skill}_after"} for skill in OBJECTIVE_SKILLS}


def _frame():
    recommendations = [score for score in range(11) for _ in range(12)] + [5] * 12 + [None] * 12
    n = len(recommendations)
    frame = pd.DataFrame({
        "recommend_score": pd.array(recommendations, dtype="Int64"),
        "is_usable_id": True,
        "is_flagged": np.arange(n) < 12,
    })
    for offset, item in enumerate(PRESENTER_ITEMS):
        frame[item] = pd.array([None if i >= n - 15 else (i + offset) % 5 + 1 for i in range(n)], dtype="Int64")
    for offset, pair in enumerate(PAIRS.values()):
        frame[pair["before"]] = pd.array([(i + offset) % 5 + 1 for i in range(n)], dtype="Int64")
        frame[pair["after"]] = pd.array(
            [None if i % 19 == 0 else (i // (4 + offset)) % 5 + 1 for i in range(n)], dtype="Int64",
        )
    return frame


def _ledger(frame):
    return analyze_delivery(frame, PAIRS, input_hash="a" * 64, config_hash="b" * 64, bootstrap_resamples=200)


def _metric(ledger, metric_id, *, cohort="all_responses", **dimensions):
    return next(
        metric for metric in ledger
        if metric.metric_id == metric_id and metric.dimensions == {"cohort": cohort, **dimensions}
    )


def test_recommendation_distribution_segments_and_heaping_reconcile():
    ledger = _ledger(_frame())
    coverage = _metric(ledger, "recommend_coverage")
    assert (coverage.numerator, coverage.denominator) == (144, 156)
    assert _metric(ledger, "recommend_answered", cohort="excluding_flagged").value == 132
    bins = [_metric(ledger, "recommend_distribution", score=str(score)) for score in range(11)]
    assert [entry.numerator for entry in bins] == [12, 12, 12, 12, 12, 24, 12, 12, 12, 12, 12]
    assert sum(entry.value for entry in bins) == pytest.approx(1)
    segments = [
        _metric(ledger, "recommend_segment", segment=segment) for segment in ("detractor", "passive", "promoter")
    ]
    assert [entry.numerator for entry in segments] == [96, 24, 24]
    assert all(entry.ci.method == "wilson" and entry.n == 144 for entry in segments)
    assert sum(entry.value for entry in segments) == pytest.approx(1)
    heaping = _metric(ledger, "recommend_heaping_local_share")
    assert (heaping.numerator, heaping.denominator) == (24, 48)
    p_value = _metric(ledger, "recommend_heaping_p_value")
    assert p_value.value == pytest.approx(binomtest(24, 48, p=1 / 3, alternative="greater").pvalue)


def test_presenter_association_matches_scipy_tied_ranks_on_complete_pairs():
    frame = _frame()
    ledger = _ledger(frame)
    item = PRESENTER_ITEMS[0]
    skill = OBJECTIVE_SKILLS[0]
    answered = _metric(ledger, "presenter_answered", item=item)
    assert answered.value == answered.n == 141
    agreement = _metric(ledger, "presenter_agreement", item=item)
    assert (agreement.numerator, agreement.denominator) == (56, 141)
    assert agreement.ci.method == "wilson"
    paired = frame[[item, *PAIRS[skill].values()]].dropna()
    expected = spearmanr(paired[item], paired[PAIRS[skill]["after"]] - paired[PAIRS[skill]["before"]]).statistic
    actual = _metric(ledger, "presenter_gain_spearman", item=item, skill=skill)
    assert actual.value == pytest.approx(expected)
    assert actual.n == len(paired)
    assert actual.ci.method == "paired_percentile_bootstrap"
    assert actual.ci.lower <= actual.value <= actual.ci.upper
    assert _ledger(frame.iloc[::-1]) == ledger


def test_small_bins_get_complementary_suppression_and_constant_scores_are_unavailable():
    frame = _frame()
    frame.loc[3:11, "recommend_score"] = 5
    frame[PRESENTER_ITEMS[0]] = 4
    ledger = _ledger(frame)
    primary = _metric(ledger, "recommend_distribution", score="0")
    companion = _metric(ledger, "recommend_distribution", score="1")
    assert primary.reason == "below_minimum_n"
    assert companion.reason == "complementary_suppression"
    for metric in (primary, companion):
        assert metric.suppressed
        assert metric.value is metric.numerator is metric.denominator is metric.n is metric.ci is None
    constant = _metric(ledger, "presenter_gain_spearman", item=PRESENTER_ITEMS[0], skill=OBJECTIVE_SKILLS[0])
    assert constant.reason == "constant_score_or_skill_change"
    assert constant.value is None
    assert not constant.suppressed
    agreement = _metric(ledger, "presenter_agreement", item=PRESENTER_ITEMS[0])
    assert agreement.suppressed and agreement.reason == "below_minimum_n"


def test_reference_presenter_and_recommendation_denominators(survey_workbook):
    config = load_config()
    incoming = ingest(survey_workbook, config.registry)
    normalized = normalize(incoming.frame, config.normalization, config.registry)
    quality = build_quality_report(normalized, config.quality)
    ledger = _ledger(quality.frame)
    assert [_metric(ledger, "presenter_answered", item=item).value for item in PRESENTER_ITEMS] == [1148, 1145, 1141]
    assert _metric(ledger, "recommend_answered").value == 1266
    assert _metric(ledger, "recommend_distribution", score="5").numerator == 151
    associations = [
        row for row in ledger
        if row.metric_id.endswith("_gain_spearman") and row.dimensions["cohort"] == "all_responses"
    ]
    assert len(associations) == 12
    assert all(row.ci is not None and row.n <= 1266 for row in associations)
