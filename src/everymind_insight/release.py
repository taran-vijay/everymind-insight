"""Explicit public surface and table-level guards, separate from private analysis."""

import re
from collections import defaultdict

from .schemas import Metric, ReportBundle
from .suppression import suppress_metric

POLICY_VERSION = "1.0.0"
MINIMUM = 10
OBJECTIVES = {"agree_before", "agree_after", "below_agree_after", "movement_up", "movement_same", "movement_down", "agreement_gain", "ceiling_share", "mean_ordinal_change"}
SUBGROUPS = {"subgroup_response_count", "subgroup_agree_before", "subgroup_agree_after", "subgroup_below_agree_after", "subgroup_agreement_gain"}
QUALITY = {"usable_responses", "flagged_responses", "invalid_training_dates"}
COMMENTS = {"comment_answered", "comment_unclassified", "comment_coding_coverage", "theme_prevalence"}
CALLING = {"calling_coverage", "calling_intent_mean"}
DELIVERY = {"presenter_answered", "presenter_coverage", "presenter_agreement", "recommend_answered", "recommend_coverage", "recommend_segment"}
PUBLIC_IDS = OBJECTIVES | SUBGROUPS | QUALITY | COMMENTS | CALLING | DELIVERY
GROUPS = {
    "county": {"Anne Arundel", "Prince George's", "Other counties", "Missing county"},
    "role": {"Student", "Other", "Caregiver/parent", "School staff member", "Multiple roles", "Unknown role", "Missing role"},
    "language": {"English", "Spanish", "Unknown language", "Missing language"},
}


def small(value, minimum):
    return value is not None and 0 < value < minimum


def sensitive_share(metric, minimum):
    return metric.value is not None and metric.unit == "proportion" and (
        small(metric.numerator, minimum) or small(metric.denominator - metric.numerator, minimum)
    )


def sensitive_count(metric, minimum):
    return metric.value is not None and metric.unit == "count" and (
        small(metric.value, minimum) or (
            metric.denominator is not None and small(metric.denominator - metric.value, minimum)
        )
    )


def safe_dimensions(metric):
    dims = metric.dimensions
    identifier = metric.metric_id
    if identifier in OBJECTIVES:
        expected = {"cohort", "skill"}
    elif identifier in SUBGROUPS:
        expected = {"cohort", "group_by", "group"} | ({"skill"} if identifier != "subgroup_response_count" else set())
    elif identifier in QUALITY:
        expected = set()
    elif identifier in COMMENTS:
        expected = {"question"} | ({"theme"} if identifier == "theme_prevalence" else set())
    elif identifier in CALLING:
        expected = {"cohort", "group_by", "group"}
    elif identifier in DELIVERY:
        expected = {"cohort"} | ({"item"} if identifier.startswith("presenter_") else ({"segment"} if identifier == "recommend_segment" else set()))
    else:
        return False
    if set(dims) != expected:
        return False
    allowed = {"cohort", "skill", "group_by", "group", "question", "theme", "item", "segment"}
    if set(dims) - allowed:
        return False
    if "cohort" in dims and dims["cohort"] not in {"all_responses", "excluding_flagged"}:
        return False
    if "skill" in dims and dims["skill"] not in {"identify_crises", "describe_988", "know_when_to_use_988"}:
        return False
    if "group_by" in dims:
        grouping, group = dims["group_by"], dims.get("group", "")
        if grouping == "overall":
            if group != "Overall": return False
        elif grouping == "training_month":
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", group) and group != "Missing training month": return False
        elif group not in GROUPS.get(grouping, set()):
            return False
    if "question" in dims and dims["question"] not in {"valuable_comment", "improve_comment"}: return False
    if "theme" in dims and dims["theme"] not in {"understanding_988", "recognizing_crises", "supporting_others", "resources", "practice", "pacing", "materials", "no_change"}: return False
    if "item" in dims and dims["item"] not in {"presenter_engaged", "presenter_knew_subject", "presenter_organized"}: return False
    if "segment" in dims and dims["segment"] not in {"detractor", "passive", "promoter"}: return False
    return True


def release_metrics(metrics: list[Metric], *, minimum: int):
    minimum = max(MINIMUM, minimum)
    released = []
    # Keep private exact-date/model diagnostics and overlapping delivery tables out.
    for metric in metrics:
        if metric.metric_id not in PUBLIC_IDS or not safe_dimensions(metric):
            continue
        if metric.metric_id in SUBGROUPS | CALLING | DELIVERY and metric.dimensions.get("cohort") != "all_responses":
            continue
        if metric.metric_id in CALLING and metric.dimensions.get("group_by") != "overall":
            continue
        if not metric.suppressed and ((metric.n is not None and metric.n < minimum) or sensitive_share(metric, minimum) or sensitive_count(metric, minimum)):
            metric = suppress_metric(metric, "small_cell_or_complement")
        released.append(metric)

    def hide(index, reason):
        if not released[index].suppressed:
            released[index] = suppress_metric(released[index], reason)

    totals = {(m.dimensions.get("group_by"), m.dimensions.get("group")): m.value
              for m in released if m.metric_id == "subgroup_response_count" and not m.suppressed}
    overall_n = next((m.value for m in released if m.metric_id == "usable_responses" and not m.suppressed), None)
    for i, metric in enumerate(released):
        if metric.suppressed or metric.n is None: continue
        if metric.metric_id in OBJECTIVES and metric.dimensions.get("cohort") == "all_responses" and overall_n is not None:
            if small(overall_n - metric.n, minimum): hide(i, "small_missing_pair_partition")
        if metric.metric_id in SUBGROUPS - {"subgroup_response_count"}:
            total = totals.get((metric.dimensions.get("group_by"), metric.dimensions.get("group")))
            if total is not None and small(total - metric.n, minimum): hide(i, "small_missing_pair_partition")

    for family in (CALLING, {name for name in DELIVERY if name.startswith("recommend_")}):
        indexes = [i for i, m in enumerate(released) if m.metric_id in family]
        if any(released[i].metric_id.endswith("coverage") and released[i].suppressed for i in indexes):
            for i in indexes: hide(i, "related_answer_partition")
    for item in ("presenter_engaged", "presenter_knew_subject", "presenter_organized"):
        indexes = [i for i, m in enumerate(released) if m.metric_id in DELIVERY and m.dimensions.get("item") == item]
        if any(released[i].metric_id == "presenter_coverage" and released[i].suppressed for i in indexes):
            for i in indexes: hide(i, "related_answer_partition")

    # A paired gain is derived from before and after. Do not release it if one
    # source share is hidden, or release a third movement cell by subtraction.
    buckets = defaultdict(list)
    for index, metric in enumerate(released):
        if metric.metric_id in OBJECTIVES:
            buckets[tuple(sorted(metric.dimensions.items()))].append(index)
    for indexes in buckets.values():
        entries = {released[i].metric_id: i for i in indexes}
        for family in ({"agree_before", "agree_after", "below_agree_after", "agreement_gain"}, {"movement_up", "movement_same", "movement_down"}):
            selected = [entries[key] for key in family if key in entries]
            if any(released[i].suppressed for i in selected):
                for i in selected: hide(i, "related_cell_protection")

    # Nested cohorts: release the overall statistic; withhold the clean
    # counterpart if their difference reveals a positive small excluded count.
    baseline = {(m.metric_id, m.dimensions.get("skill")): m for m in released
                if m.metric_id in OBJECTIVES and m.dimensions.get("cohort") == "all_responses"}
    for i, metric in enumerate(released):
        if metric.metric_id not in OBJECTIVES or metric.dimensions.get("cohort") != "excluding_flagged": continue
        base = baseline.get((metric.metric_id, metric.dimensions.get("skill")))
        if base is None or base.suppressed or metric.suppressed: continue
        protect = small(base.n - metric.n, minimum)
        if metric.unit == "proportion" and base.numerator is not None and metric.numerator is not None:
            protect |= small(base.numerator - metric.numerator, minimum)
            protect |= small((base.denominator - base.numerator) - (metric.denominator - metric.numerator), minimum)
        if protect: hide(i, "nested_cohort_protection")
    # Reapply derived-family guard after nested-cohort protection.
    for indexes in buckets.values():
        for family in ({"agree_before", "agree_after", "below_agree_after", "agreement_gain"}, {"movement_up", "movement_same", "movement_down"}):
            selected = [i for i in indexes if released[i].metric_id in family]
            if any(released[i].suppressed for i in selected):
                for i in selected: hide(i, "related_cell_protection")

    # Publish subgroup outcomes only for all responses. Hide paired row
    # families together and a companion row in additive tables so a released
    # total cannot identify a lone hidden outcome row.
    tables = defaultdict(lambda: defaultdict(list))
    for i, metric in enumerate(released):
        if metric.metric_id in SUBGROUPS - {"subgroup_response_count"}:
            d = metric.dimensions
            tables[d["group_by"], d["skill"]][d["group"]].append(i)
    for (grouping, _), groups in tables.items():
        hidden = [group for group, indexes in groups.items() if any(released[i].suppressed for i in indexes)]
        for group in hidden:
            for i in groups[group]: hide(i, "related_cell_protection")
        companion_exists = any(released[i].reason == "complementary_suppression" for indexes in groups.values() for i in indexes)
        if hidden and grouping != "role" and not companion_exists:
            # Do not count zero/unavailable rows as protective companions.
            candidates = [(released[indexes[0]].n or 0, group) for group, indexes in groups.items() if group not in hidden]
            if candidates:
                _, companion = min(candidates)
                for i in groups[companion]: hide(i, "complementary_suppression")
    return released


def validate_release(bundle: ReportBundle):
    """Validate an export, not just its schema. This is not an anonymity proof."""
    ReportBundle.model_validate_json(bundle.model_dump_json())
    if bundle.data_kind == "synthetic":
        return bundle
    if bundle.release_metadata is None or bundle.release_metadata.policy_version != POLICY_VERSION:
        raise ValueError("Survey report requires release-policy metadata.")
    minimum = bundle.suppression_policy.minimum_n
    if minimum < MINIMUM: raise ValueError("Public threshold must be at least 10.")
    for metric in bundle.metrics:
        if metric.metric_id not in PUBLIC_IDS or not safe_dimensions(metric):
            raise ValueError("Report contains a private metric or dimension.")
        if not metric.suppressed and ((metric.n is not None and metric.n < minimum) or sensitive_share(metric, minimum) or sensitive_count(metric, minimum)):
            raise ValueError("Report contains an unprotected small cell.")
        if metric.value is not None and metric.unit in {"proportion", "percentage_point"}:
            if metric.numerator != int(metric.numerator) or metric.denominator != int(metric.denominator):
                raise ValueError("Released public proportions require whole-response calculation bases.")
    by_key = {metric.key(): metric for metric in bundle.metrics}
    for finding in bundle.findings:
        if not finding.metric_refs or any(by_key[ref.key()].suppressed or by_key[ref.key()].value is None for ref in finding.metric_refs):
            raise ValueError("Findings must reference released evidence.")
    if release_metrics(bundle.metrics, minimum=minimum) != bundle.metrics:
        raise ValueError("Report has unprotected related cells or nested cohorts.")
    return bundle
