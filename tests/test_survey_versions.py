from collections import Counter

import pandas as pd
import pytest

from everymind_insight.config import OBJECTIVE_ITEMS, PRESENTER_ITEMS, load_config
from everymind_insight.ingestion import ingest
from everymind_insight.normalization import normalize
from everymind_insight.quality import build_quality_report
from everymind_insight.survey_versions import analyze_survey_versions


def _frame(dates, answers, *, counties=None, roles=None):
    n = len(dates)
    return pd.DataFrame({
        "training_date": pd.to_datetime(dates),
        "calling_score": pd.array(answers, dtype="Int64"),
        "county": counties if counties is not None else ["Anne Arundel"] * n,
        "role_groups": roles if roles is not None else [("Student",)] * n,
        "is_usable_id": [True] * n,
        "is_flagged": [False] * n,
        "recommend_score": [8] * n,
        **{item: [4] * n for item in (*PRESENTER_ITEMS, *OBJECTIVE_ITEMS)},
    })


def _analyze(frame):
    return analyze_survey_versions(
        frame, input_hash="a" * 64, config_hash="b" * 64,
        known_roles={"Student", "School staff member"}, seed=12, shuffles=999,
    )


def _metric(analysis, metric_id, *, cohort="all_responses", **dimensions):
    return next(metric for metric in analysis.metrics if metric.metric_id == metric_id and metric.dimensions == {
        "cohort": cohort, **dimensions,
    })


def test_calling_coverage_flags_mixed_dates_and_keeps_unknown_date_separate():
    dates = ["2026-01-01"] * 12 + ["2026-01-02"] * 12 + ["2026-01-03"] * 12 + [None] * 2
    frame = _frame(dates, [7] * 16 + [None] * 20 + [10, None])
    frame.loc[12:15, "is_flagged"] = True
    result = _analyze(frame)
    fingerprints = {item.training_date: item for item in result.fingerprints}
    assert {date: item.calling_status for date, item in fingerprints.items()} == {
        "2026-01-01": "all_answered", "2026-01-02": "mixed", "2026-01-03": "no_answers", None: "unknown_date",
    }
    assert fingerprints[None].version_id is None
    assert len({fingerprints[date].version_id for date in dates[:36:12]}) == 3
    mixed = _metric(result, "calling_date_mixed", training_date="2026-01-02")
    assert (mixed.value, mixed.n, mixed.suppressed) == (1, 12, False)
    unknown = _metric(result, "calling_date_mixed", training_date="Unknown date")
    assert unknown.suppressed and unknown.value is None and unknown.n is None

    coverage = _metric(result, "calling_coverage", group_by="overall", group="Overall")
    assert (coverage.numerator, coverage.denominator) == (17, 38)
    assert coverage.ci.lower < coverage.value < coverage.ci.upper
    proxy = _metric(result, "calling_possible_exposure_coverage", group_by="overall", group="Overall")
    assert (proxy.numerator, proxy.denominator) == (16, 24)
    filtered = _metric(result, "calling_possible_exposure_coverage", cohort="excluding_flagged", group_by="overall", group="Overall")
    assert (filtered.numerator, filtered.denominator) == (12, 20)
    intent = _metric(result, "calling_intent_mean", group_by="overall", group="Overall")
    assert (intent.numerator, intent.denominator, intent.n) == (122, 17, 17)
    assert intent.value == pytest.approx(122 / 17)

    p_value = _metric(result, "calling_date_shuffle_p_value")
    assert p_value.n == 36
    assert 0 < p_value.value < 0.01
    reordered = _analyze(frame.sample(frac=1, random_state=988))
    assert _metric(reordered, "calling_date_shuffle_p_value") == p_value


@pytest.mark.parametrize(("group_by", "group", "comparison"), [
    pytest.param("county", "Prince George's", "Anne Arundel", id="county"),
    pytest.param("role", "Student", "School staff member", id="role"),
])
def test_county_or_role_is_inseparable_when_one_session_dominates(group_by, group, comparison):
    dates = ["2026-01-01"] * 20 + ["2026-01-02"] * 2 + ["2026-01-01"] * 11 + ["2026-01-02"] * 11
    result = _analyze(_frame(
        dates, [7] * 44,
        counties=["Prince George's"] * 22 + ["Anne Arundel"] * 22,
        roles=[("Student",)] * 22 + [("School staff member",)] * 22,
    ))
    groups = {item.group: item for item in result.session_concentration if item.group_by == group_by}
    assert groups[group].inseparable
    assert groups[group].reasons == ("dominant_session",)
    assert groups[group].dominant_date == "2026-01-01"
    assert not groups[comparison].inseparable
    assert _metric(result, "calling_group_inseparable", group_by=group_by, group=group).value == 1
    assert _metric(result, "calling_group_inseparable", group_by=group_by, group=comparison).value == 0
    assert _metric(result, "calling_date_shuffle_p_value").reason == "no_variation_in_answer_status"


def test_reference_calling_coverage_and_date_fingerprints(survey_workbook):
    config = load_config()
    raw = ingest(survey_workbook, config.registry)
    normalized = normalize(raw.frame, config.normalization, config.registry)
    frame = build_quality_report(normalized, config.quality).frame
    result = analyze_survey_versions(
        frame, input_hash=raw.audit["input_hash"], config_hash="b" * 64,
        known_roles=set(config.normalization.role_aliases.values()),
    )
    assert Counter(item.calling_status for item in result.fingerprints) == {
        "all_answered": 12, "mixed": 9, "no_answers": 25, "unknown_date": 1,
    }
    coverage = _metric(result, "calling_coverage", group_by="overall", group="Overall")
    assert (coverage.numerator, coverage.denominator) == (293, 1299)
    intent = _metric(result, "calling_intent_mean", group_by="overall", group="Overall")
    assert intent.n == 293
    p_value = _metric(result, "calling_date_shuffle_p_value")
    assert p_value.n == 1296 and 0 < p_value.value < 0.01
