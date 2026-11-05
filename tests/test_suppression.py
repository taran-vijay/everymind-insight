from hypothesis import given, strategies as st

from everymind_insight.schemas import ConfidenceInterval, Metric, Provenance
from everymind_insight.suppression import suppress_metric, table_suppressions


def test_additive_table_gets_a_companion_but_overlapping_groups_do_not():
    counts = {"small": 3, "next": 12, "large": 60}
    assert table_suppressions(counts) == {
        "small": "below_minimum_n", "next": "complementary_suppression",
    }
    assert table_suppressions(counts, additive=False) == {"small": "below_minimum_n"}
    assert table_suppressions({"empty": 0, "empty also": 0, "other": 12}) == {
        "empty": "below_minimum_n", "empty also": "below_minimum_n", "other": "complementary_suppression",
    }


@given(st.lists(st.integers(min_value=0, max_value=40), min_size=1, max_size=8))
def test_within_table_remaining_counts_do_not_force_a_primary_cell(counts):
    by_group = {str(index): count for index, count in enumerate(counts)}
    hidden = table_suppressions(by_group)
    if not hidden or len(hidden) == len(counts):
        # The table withholds its own total when it has no visible rows.
        return
    primary = [key for key, reason in hidden.items() if reason == "below_minimum_n"]
    secondary_n = len(hidden) - len(primary)
    residual = sum(by_group[key] for key in hidden)
    for _ in primary:
        other_min = 10 * secondary_n
        other_max = residual if secondary_n else 9 * (len(primary) - 1)
        assert max(0, residual - other_max) < min(9, residual - other_min)


def test_suppression_clears_fields_that_could_disclose_a_cell():
    metric = Metric(
        metric_id="share", value=0.5, numerator=2, denominator=4, n=4,
        ci=ConfidenceInterval(lower=0.15, upper=0.85, level=0.95, method="wilson"),
        unit="proportion", definition="Share of responses.",
        provenance=Provenance(
            input_hash="a" * 64, config_hash="b" * 64, method="share", population="eligible",
            parameters={"support": 4},
        ),
    )
    hidden = suppress_metric(metric, "below_minimum_n")
    assert hidden.suppressed
    assert (hidden.value, hidden.numerator, hidden.denominator, hidden.n, hidden.ci) == (None,) * 5
    assert hidden.provenance.parameters == {}
