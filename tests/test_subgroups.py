from functools import cache

import pandas as pd
import pytest

from everymind_insight.config import load_config
from everymind_insight.ingestion import ingest
from everymind_insight.normalization import normalize
from everymind_insight.quality import build_quality_report
from everymind_insight.subgroups import analyze_subgroups


_PAIR = {"identify_crises": {"before": "before", "after": "after"}}


def _metric(ledger, metric_id, group, *, grouping="county", skill="identify_crises", cohort="all_responses"):
    return next(
        metric for metric in ledger
        if metric.metric_id == metric_id
        and metric.dimensions.get("group_by") == grouping
        and metric.dimensions.get("group") == group
        and metric.dimensions.get("skill") == skill
        and metric.dimensions.get("cohort") == cohort
    )


def _analyze(frame):
    return analyze_subgroups(
        frame, _PAIR, load_config().normalization, input_hash="a" * 64, config_hash="b" * 64
    )


def _row(county, role, agrees, day):
    return {
        "is_usable_id": True, "is_flagged": False, "before": 3, "after": 4 if agrees else 3,
        "county": county, "role_group": role, "role_groups": (role,), "language": "English",
        "training_date": pd.Timestamp(2026, 1, day),
    }


@cache
def _reference_subgroups(survey_workbook):
    config = load_config()
    source = ingest(survey_workbook, config.registry)
    normalized = normalize(source.frame, config.normalization, config.registry)
    quality = build_quality_report(normalized, config.quality)
    return analyze_subgroups(
        quality.frame, normalized.objective_columns, config.normalization,
        input_hash=source.audit["input_hash"], config_hash="b" * 64,
    )


@pytest.fixture
def reference_subgroups(survey_workbook):
    return _reference_subgroups(survey_workbook)


@pytest.mark.parametrize("month", ["2025-11", "2026-02", "2026-07", "2026-08"])
def test_reference_training_month_below_minimum_is_suppressed(reference_subgroups, month):
    entries = [
        metric for metric in reference_subgroups
        if metric.dimensions.get("group_by") == "training_month" and metric.dimensions["group"] == month
    ]
    assert {entry.dimensions["cohort"] for entry in entries} == {"all_responses", "excluding_flagged"}
    assert {entry.metric_id for entry in entries} == {
        "subgroup_response_count", "subgroup_agree_before", "subgroup_agree_after",
        "subgroup_below_agree_after", "subgroup_agreement_gain",
    }
    for entry in entries:
        assert entry.suppressed and entry.reason == "below_minimum_n"
        assert (entry.value, entry.n, entry.numerator, entry.denominator, entry.ci) == (None,) * 5


def test_training_month_complementary_suppression_withholds_entire_estimate_row():
    rows = [
        _row("Anne Arundel", "Student", True, 1) | {"training_date": pd.Timestamp(2026, month, 1)}
        for month, n in ((1, 7), (2, 12), (3, 25)) for _ in range(n)
    ]
    ledger = _analyze(pd.DataFrame(rows))
    for month, reason in (("2026-01", "below_minimum_n"), ("2026-02", "complementary_suppression")):
        estimate = _metric(ledger, "subgroup_agree_after", month, grouping="training_month")
        count = _metric(ledger, "subgroup_response_count", month, grouping="training_month", skill=None)
        assert estimate.reason == count.reason == reason
        assert estimate.suppressed and count.suppressed
        assert estimate.n is count.n is None
    published = _metric(ledger, "subgroup_agree_after", "2026-03", grouping="training_month")
    assert published.n == 25 and published.ci.method == "wilson"


@pytest.fixture
def composition_rows():
    return pd.DataFrame([
        _row(county, role, index % 5 < agrees_out_of_five, index % 10 + 1)
        for county, role, n, agrees_out_of_five in (
            ("Anne Arundel", "Student", 40, 4), ("Anne Arundel", "Caregiver/parent", 20, 2),
            ("Prince George's", "Student", 20, 4), ("Prince George's", "Caregiver/parent", 40, 2),
        ) for index in range(n)
    ])


def test_role_standardization_removes_synthetic_composition_gap(composition_rows):
    ledger = _analyze(composition_rows)
    county = "Prince George's"
    adjusted = _metric(ledger, "county_role_standardized_agree_after", county)
    assert adjusted.value == pytest.approx(0.6)
    assert adjusted.numerator == pytest.approx(72) and adjusted.denominator == 120 and adjusted.n == 60
    assert adjusted.ci.lower < adjusted.value < adjusted.ci.upper
    assert _metric(ledger, "county_unadjusted_gap", county).value == pytest.approx(-13.33333333)
    gap = _metric(ledger, "county_standardized_gap", county)
    assert gap.value == pytest.approx(0)
    assert "consistent with a composition effect" in gap.provenance.parameters["interpretation"]
    model = _metric(ledger, "county_model_odds_ratio", county)
    assert model.value == pytest.approx(1)
    assert model.ci.method == "training_date_cluster_robust_t"
    assert model.provenance.parameters["training_date_clusters"] == 10


def test_county_model_reports_separation_and_too_few_dates(composition_rows):
    county = "Prince George's"
    separated = composition_rows.copy()
    separated.loc[separated["county"].eq(county), "after"] = 4
    separated_model = _metric(_analyze(separated), "county_model_odds_ratio", county)
    assert separated_model.value is None and separated_model.reason == "separated_outcome"
    few_dates = composition_rows.assign(training_date=pd.Timestamp(2026, 1, 1))
    few_dates_model = _metric(_analyze(few_dates), "county_model_odds_ratio", county)
    assert few_dates_model.value is None and few_dates_model.reason == "too_few_training_date_clusters"


def test_standardization_withholds_estimate_if_a_target_role_is_absent(composition_rows):
    county = "Prince George's"
    rows = composition_rows.loc[~(composition_rows["county"].eq(county) & composition_rows["role_group"].eq("Student"))]
    ledger = _analyze(rows)
    adjusted = _metric(ledger, "county_role_standardized_agree_after", county)
    assert adjusted.value is None and adjusted.reason == "incomplete_role_overlap"
    support = _metric(ledger, "county_role_standardization_support", county)
    assert support.numerator == 60 and support.denominator == 100


def test_standardization_target_keeps_eligible_roles_without_skill_pairs(composition_rows):
    extra = pd.DataFrame([_row("Anne Arundel", "Other", True, 1) | {"before": None}] * 5)
    ledger = _analyze(pd.concat([composition_rows, extra], ignore_index=True))
    for county in ("Anne Arundel", "Prince George's"):
        adjusted = _metric(ledger, "county_role_standardized_agree_after", county)
        assert adjusted.value is None and adjusted.reason == "incomplete_role_overlap"
        support = _metric(ledger, "county_role_standardization_support", county)
        assert support.numerator == 120 and support.denominator == 125


def test_unobserved_roles_preserve_raw_county_estimates_and_disable_adjustment(composition_rows):
    rows = composition_rows.assign(role_group=None, role_groups=[()] * len(composition_rows))
    ledger = _analyze(rows)
    county = "Prince George's"
    assert _metric(ledger, "subgroup_agree_after", county).value == pytest.approx(32 / 60)
    for metric_id in ("county_role_standardized_agree_after", "county_standardized_gap", "county_model_odds_ratio"):
        metric = _metric(ledger, metric_id, county)
        assert metric.value is None and metric.reason == "no_observed_roles"


def test_role_memberships_respect_policy_and_hide_unapproved_labels():
    rows = pd.DataFrame([
        _row("Anne Arundel", "Multiple roles", True, 1) | {"role_groups": ("Student", "Caregiver/parent")}
        for _ in range(12)
    ] + [
        _row("Anne Arundel", "Multiple roles", False, 1) | {"role_groups": ("New unapproved", "Another unapproved")}
        for _ in range(12)
    ])
    overlapping = _analyze(rows)
    assert not any("unapproved" in str(entry.dimensions) for entry in overlapping)
    for group in ("Student", "Caregiver/parent", "Unknown role"):
        count = _metric(overlapping, "subgroup_response_count", group, grouping="role", skill=None)
        assert count.value == 12
    disjoint = _analyze(rows.assign(role_groups=[("Multiple roles",)] * len(rows)))
    count = _metric(disjoint, "subgroup_response_count", "Multiple roles", grouping="role", skill=None)
    assert count.value == 24
