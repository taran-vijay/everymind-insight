"""Primary and complementary suppression for one aggregate table at a time."""

from collections.abc import Mapping

from .schemas import Metric


def table_suppressions(
    counts: Mapping[str, int], minimum_n: int = 10, *, additive: bool = True,
) -> dict[str, str]:
    """Identify small rows and a companion row when an additive total could reveal them."""
    if minimum_n < 1 or any(count < 0 for count in counts.values()):
        raise ValueError("Suppression requires a positive threshold and nonnegative counts")
    hidden = {key: "below_minimum_n" for key, count in counts.items() if count < minimum_n}
    if not additive or not hidden:
        return hidden

    remaining = [(count, key) for key, count in counts.items() if key not in hidden]
    hidden_total = sum(counts[key] for key in hidden)
    # A total discloses a lone hidden cell, or multiple hidden cells when their
    # total is at an extreme of the range allowed by primary suppression.
    if remaining and (len(hidden) == 1 or hidden_total in (0, len(hidden) * (minimum_n - 1))):
        choices = [(count, key) for count, key in remaining if hidden_total or count > minimum_n]
        if choices:
            _, key = min(choices)
            hidden[key] = "complementary_suppression"
        else:
            # A zero subtotal plus a companion at exactly the threshold still
            # reveals zero. Hide every row so its own denominator is withheld.
            hidden.update({key: "complementary_suppression" for _, key in remaining})
    return hidden


def suppress_metric(metric: Metric, reason: str) -> Metric:
    """Remove a protected value, its support and any run parameters from the public cell."""
    return Metric.model_validate({
        **metric.model_dump(),
        "value": None,
        "numerator": None,
        "denominator": None,
        "ci": None,
        "n": None,
        "suppressed": True,
        "reason": reason,
        "provenance": metric.provenance.model_copy(update={"parameters": {}}),
    })
