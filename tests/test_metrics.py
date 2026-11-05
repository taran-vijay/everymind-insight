import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from everymind_insight.metrics import analyze_objectives


SKILL = "identify_crises"
OBJECTIVES = {SKILL: {"before": "identify_crises_before", "after": "identify_crises_after"}}


def _frame(pairs, *, usable=None, flagged=None):
    return pd.DataFrame(
        {
            "identify_crises_before": pd.array([before for before, _ in pairs], dtype="Int64"),
            "identify_crises_after": pd.array([after for _, after in pairs], dtype="Int64"),
            "is_usable_id": [True] * len(pairs) if usable is None else usable,
            "is_flagged": [False] * len(pairs) if flagged is None else flagged,
        }
    )


def _analyze(frame):
    return analyze_objectives(
        frame,
        OBJECTIVES,
        input_hash="a" * 64,
        config_hash="b" * 64,
        bootstrap_resamples=100,
    )


def _rows(ledger, cohort="all_responses"):
    return {
        row.metric_id: row
        for row in ledger
        if row.dimensions == {"skill": SKILL, "cohort": cohort}
    }


@settings(max_examples=30, deadline=None)
@given(st.lists(st.tuples(st.integers(1, 5), st.integers(1, 5)), min_size=1, max_size=40))
def test_paired_counts_and_partition_shares_reconcile(pairs):
    ledger = _analyze(_frame(pairs))
    rows = _rows(ledger)
    movement = [rows[name] for name in ("movement_up", "movement_same", "movement_down")]
    expected_movement = [
        sum(after > before for before, after in pairs),
        sum(after == before for before, after in pairs),
        sum(after < before for before, after in pairs),
    ]
    assert [metric.numerator for metric in movement] == expected_movement
    assert all(metric.n == metric.denominator == len(pairs) for metric in movement)
    assert sum(metric.numerator for metric in movement) == len(pairs)
    assert sum(metric.value for metric in movement) == pytest.approx(1)
    assert rows["agree_after"].numerator + rows["below_agree_after"].numerator == len(pairs)
    assert rows["agree_after"].value + rows["below_agree_after"].value == pytest.approx(1)

    transitions = {
        (int(row.dimensions["before_score"]), int(row.dimensions["after_score"])): row.value
        for row in ledger
        if row.metric_id == "transition_count" and row.dimensions["cohort"] == "all_responses"
    }
    assert transitions == {
        (before, after): pairs.count((before, after))
        for before in range(1, 6)
        for after in range(1, 6)
    }


def test_paired_statistics_match_hand_calculations():
    frame = _frame([(1, 4), (2, 2), (3, 2), (4, 3), (5, 4)])
    ledger = _analyze(frame)
    rows = _rows(ledger)

    assert rows["mean_ordinal_change"].value == pytest.approx(0)
    assert rows["normalized_gain"].value == pytest.approx(-0.1875)
    assert rows["normalized_gain"].n == 4
    assert rows["ceiling_share"].value == pytest.approx(0.2)
    assert rows["rank_biserial"].value == pytest.approx(-0.2)
    assert rows["wilcoxon_statistic"].value == pytest.approx(4)
    assert rows["sign_test_p_value"].value == pytest.approx(0.625)
    assert rows["mcnemar_p_value"].value == pytest.approx(1)
    assert rows["agreement_gain"].value == pytest.approx(0)
    agree_interval = rows["agree_before"].ci
    assert agree_interval is not None
    assert agree_interval.method == "wilson"
    assert (agree_interval.lower, agree_interval.upper) == pytest.approx((0.1176207742, 0.7692757187))
    change_interval = rows["mean_ordinal_change"].ci
    assert change_interval is not None
    assert change_interval.method == "paired_percentile_bootstrap"
    assert change_interval.lower < rows["mean_ordinal_change"].value < change_interval.upper
    assert _analyze(frame) == ledger


def test_exact_tests_use_their_own_discordant_pairs():
    # Six ordinal gains include one gain that stays above the Agree threshold.
    rows = _rows(_analyze(_frame([(1, 4)] * 5 + [(4, 5), (5, 1)])))
    assert rows["sign_test_p_value"].value == pytest.approx(0.125)
    assert rows["mcnemar_p_value"].value == pytest.approx(0.21875)
    assert rows["large_reversal"].value == 1


def test_cohorts_use_pairwise_coverage_and_keep_flagged_responses_in_primary():
    frame = _frame(
        [(1, 5), (5, 2), (None, 5), (3, 5)],
        usable=[True, True, True, False],
        flagged=[False, True, False, True],
    )
    original = frame.copy()
    ledger = _analyze(frame)
    pd.testing.assert_frame_equal(frame, original)
    all_rows = _rows(ledger)
    clean = _rows(ledger, "excluding_flagged")

    assert (all_rows["paired_coverage"].numerator, all_rows["paired_coverage"].denominator) == (2, 3)
    assert (clean["paired_coverage"].numerator, clean["paired_coverage"].denominator) == (1, 2)
    assert all_rows["agree_after"].denominator == 2
    assert clean["agree_after"].denominator == 1
    assert all_rows["agreement_gain"].value == pytest.approx(0)
    assert clean["agreement_gain"].value == pytest.approx(100)


def test_unavailable_statistics_are_explicit():
    no_pairs = _rows(_analyze(_frame([(None, 4)])))
    assert no_pairs["paired_coverage"].value == 0
    assert no_pairs["agree_before"].value is None
    assert no_pairs["agree_before"].reason == "no_complete_pairs"

    ceiling_ties = _rows(_analyze(_frame([(5, 5), (5, 5)])))
    assert ceiling_ties["movement_same"].value == 1
    assert ceiling_ties["normalized_gain"].value is None
    assert ceiling_ties["normalized_gain"].reason == "no_headroom"
    assert ceiling_ties["sign_test_p_value"].value is None
    assert ceiling_ties["sign_test_p_value"].reason == "no_nonzero_changes"
    assert ceiling_ties["mcnemar_p_value"].value is None
    assert ceiling_ties["mcnemar_p_value"].reason == "no_discordant_agreement_pairs"
