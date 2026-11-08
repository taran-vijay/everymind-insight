"""Survey export to a validated, deliberately scoped dashboard report."""

import hashlib
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from dataclasses import dataclass
from pathlib import Path

from .config import OBJECTIVE_ITEMS, load_config
from .delivery import analyze_delivery
from .ingestion import ingest
from .metrics import analyze_objectives
from .normalization import normalize
from .quality import build_quality_report
from .release import release_metrics, small, validate_release
from .schemas import (Caveat, Finding, Metric, MetricReference, Provenance, PublicQualityReport,
                      ReleaseMetadata, ReportBundle, SuppressionPolicy)
from .subgroups import analyze_subgroups
from .suppression import suppress_metric
from .survey_versions import analyze_survey_versions
from .themes import analyze_themes, codebook

SOFTWARE_VERSION = "0.2.0-backend-fixes"
SKILLS = {"identify_crises": "identify crises", "describe_988": "describe 988", "know_when_to_use_988": "know when to use 988"}


def reference(metric):
    return MetricReference(metric_id=metric.metric_id, dimensions=metric.dimensions)


def draft_findings(metrics):
    """Controlled templates grounded only in visible evidence; never invent an AI review."""
    usable = [metric for metric in metrics if not metric.suppressed and metric.value is not None]
    findings = []
    gaps = [m for m in usable if m.metric_id == "below_agree_after" and m.dimensions.get("cohort") == "all_responses"]
    if gaps:
        gap = max(gaps, key=lambda m: (m.value, m.dimensions["skill"]))
        if gap.value > 0:
            skill = SKILLS[gap.dimensions["skill"]]
            tied = sum(m.value == gap.value for m in gaps) > 1
            findings.append(Finding(
                id="priority_remaining_gap", confidence="moderate",
                observation=f"{gap.value:.1%} of complete-pair respondents remained below Agree on ability to {skill}.",
                interpretation=("This is a joint-largest observed remaining gap. " if tied else "This is the largest observed remaining gap among released skills. ") + "It identifies a topic for review, not a causal training effect.",
                action=f"Program lead: review the {skill} module before the next training cycle and pilot a focused practice activity. At the next monthly review, compare the same gap measure, complete-pair base and response mix before deciding whether to expand the change.",
                metric_refs=[reference(gap)], caveat_ids=["retrospective", "selection"],
            ))
    themes = [m for m in usable if m.metric_id == "theme_prevalence" and m.dimensions.get("question") == "improve_comment" and m.dimensions.get("theme") != "no_change" and m.value > 0]
    if themes:
        theme = max(themes, key=lambda m: (m.value, m.dimensions["theme"]))
        label = {"practice": "examples, scenarios and practice", "pacing": "timing and pacing", "materials": "materials and accessibility"}[theme.dimensions["theme"]]
        findings.append(Finding(
            id="feedback_review", confidence="low",
            observation=f"{theme.value:.1%} of nonblank improvement comments mentioned {label}.",
            interpretation="This is a keyword-topic count, not a sentiment estimate or proof that participants requested the same change. Topics can overlap.",
            action=f"Training lead: manually check a sample of the privately located comments about {label}, including unmatched and negated examples. If confirmed, pilot one change in the next cycle; track that topic's share, comment response rate and relevant skill gap in the next monthly review.",
            metric_refs=[reference(theme)], caveat_ids=["coding", "selection"],
        ))
    coverage = next((m for m in usable if m.metric_id == "calling_coverage"), None)
    if coverage and coverage.value < 1:
        findings.append(Finding(
            id="calling_coverage", confidence="moderate",
            observation=f"The calling-intent question had valid answers for {coverage.value:.1%} of eligible responses.",
            interpretation="Blank answers do not establish unwillingness to call. Question availability and survey versions may explain part of the missingness.",
            action="Survey owner: record which survey version and questions each training used, and separate not-asked, skipped and invalid answers. Review coverage by version at the next monthly refresh before comparing stated intent across communities.",
            metric_refs=[reference(coverage)], caveat_ids=["calling"],
        ))
    county = [m for m in usable if m.metric_id == "subgroup_below_agree_after" and m.dimensions.get("group_by") == "county" and m.dimensions.get("group") in {"Anne Arundel", "Prince George's"}]
    comparable = [m for m in county if len([x for x in county if x.dimensions["skill"] == m.dimensions["skill"]]) == 2]
    if comparable:
        gap = max(comparable, key=lambda m: (m.value, m.dimensions["group"], m.dimensions["skill"]))
        if gap.value > 0:
            findings.append(Finding(
                id="community_followup", confidence="low",
                observation=f"A released county result shows {gap.value:.1%} below Agree on ability to {SKILLS[gap.dimensions['skill']]} in {gap.dimensions['group']}.",
                interpretation="This is an unadjusted descriptive result. Role composition, training dates and respondent selection may explain differences; it does not rank community need or training quality.",
                action="Community education lead: discuss delivery and access barriers with the local partner, then have an analyst check role mix and shared training dates before targeting changes. Evaluate any pilot with comparable survey wording, complete-pair bases and feedback in the next cycle.",
                metric_refs=[reference(gap)], caveat_ids=["communities", "selection"],
            ))
    return findings


@dataclass
class PreparedReport:
    config: object
    incoming: object
    normalized: object
    quality: object


def prepare_report(source: Path | bytes, *, suffix=None, sheet=None, config_dir=None, role_policy=None):
    config = load_config(config_dir)
    if role_policy is not None:
        config.normalization.role_policy = role_policy
    from .ingestion import ingest_bytes
    incoming = ingest_bytes(source, suffix, config.registry, sheet=sheet) if isinstance(source, bytes) else ingest(source, config.registry, sheet=sheet)
    present = set(incoming.audit["present_columns"])
    if not {"id", *OBJECTIVE_ITEMS}.issubset(present):
        raise ValueError("Required ID or paired skill questions are missing or ambiguous. Use check for a private schema audit.")
    normalized = normalize(incoming.frame, config.normalization, config.registry)
    quality = build_quality_report(normalized, config.quality)
    quality.frame['_response_group'] = incoming.response_groups
    return PreparedReport(config, incoming, normalized, quality)


def build_report(source: Path | None = None, *, sheet=None, config_dir=None, synthetic=False, role_policy=None,
                 prepared=None, filters=None, public_only=False):
    prepared = prepared or prepare_report(source, sheet=sheet, config_dir=config_dir, role_policy=role_policy)
    config, incoming, normalized, quality = prepared.config, prepared.incoming, prepared.normalized, prepared.quality
    present = set(incoming.audit["present_columns"])
    frame = quality.frame
    if filters is not None:
        from .filters import selection
        frame = frame.loc[frame.is_usable_id]
        kept, _, _ = selection(frame, filters)
        frame = frame.loc[kept]
    usable = frame.loc[frame.is_usable_id]
    if usable.empty:
        raise ValueError("No usable IDs. Check for missing or duplicate response IDs.")
    book, book_hash = codebook()
    config_hash = hashlib.sha256(json.dumps({
        "settings": config.model_dump(mode="json"), "codebook_hash": book_hash,
        "release_policy": "1.0.0", "software_version": SOFTWARE_VERSION,
        **({"filter_spec": filters.canonical()} if filters is not None and filters.active else {}),
    }, sort_keys=True).encode()).hexdigest()
    settings = config.phase3
    minimum = max(10, settings.minimum_n)
    hashes = {"input_hash": incoming.audit["input_hash"], "config_hash": config_hash}
    objectives = analyze_objectives(frame, normalized.objective_columns, seed=settings.seed,
                                    bootstrap_resamples=settings.bootstrap_resamples, **hashes)
    subgroups = analyze_subgroups(frame, normalized.objective_columns, config.normalization,
                                  minimum_n=minimum, minimum_clusters=settings.minimum_clusters, public_only=public_only, **hashes)
    versions = analyze_survey_versions(frame, known_roles=set(config.normalization.role_aliases.values()),
                                       minimum_n=minimum, seed=settings.seed, shuffles=settings.shuffles,
                                       dominance_threshold=settings.dominance_threshold, public_only=public_only, **hashes)
    delivery = analyze_delivery(frame, normalized.objective_columns, minimum_n=minimum,
                                seed=settings.seed, bootstrap_resamples=settings.bootstrap_resamples, public_only=public_only, **hashes)
    comments, themes, review = analyze_themes(frame, present_questions=present,
                                             source_record_numbers=incoming.audit["source_record_numbers"], **hashes)
    # Keep small comment response/missingness counts from being inferred via n.
    for question in themes.questions:
        answer = next(m for m in comments if m.key() == question.answered.key())
        if small(len(usable) - answer.value, minimum):
            comments = [suppress_metric(m, "comment_response_partition") if m.dimensions.get("question") == question.question_id else m for m in comments]
    provenance = Provenance(**hashes, method="usable_id_quality_counts", population="Responses with usable, nonduplicate IDs.")
    quality_metrics = [Metric(metric_id=identifier, value=count, n=len(usable), denominator=len(usable),
                              unit="count", definition=definition, provenance=provenance)
                       for identifier, count, definition in [
                           ("usable_responses", len(usable), "Responses with usable, nonduplicate IDs."),
                           ("flagged_responses", int(usable.is_flagged.sum()), "Usable responses flagged for review, not automatically invalidated."),
                           ("invalid_training_dates", int(usable.is_invalid_training_date.sum()), "Usable responses with an unparsed training date.")]]
    candidates = objectives + subgroups + versions.metrics + delivery + comments + quality_metrics
    # A missing question is unavailable, never evidence of a zero answer rate.
    unavailable = {"calling_score": {"calling_coverage", "calling_intent_mean"},
                   "recommend_score": {m.metric_id for m in delivery if m.metric_id.startswith("recommend_")}}
    for question, identifiers in unavailable.items():
        if question not in present:
            candidates = [Metric.model_validate({**m.model_dump(), "value": None, "numerator": None,
                          "denominator": None, "n": None, "ci": None, "suppressed": False,
                          "reason": "question_missing_or_ambiguous"}) if m.metric_id in identifiers else m for m in candidates]
    for item in ("presenter_engaged", "presenter_knew_subject", "presenter_organized"):
        if item not in present:
            candidates = [Metric.model_validate({**m.model_dump(), "value": None, "numerator": None,
                          "denominator": None, "n": None, "ci": None, "suppressed": False,
                          "reason": "question_missing_or_ambiguous"}) if m.dimensions.get("item") == item else m for m in candidates]
    public = release_metrics(candidates, minimum=minimum)
    notes = [
        "Each skill uses its own complete recalled-before/current pairs. Missing and duplicate IDs are excluded.",
        "Quality flags are review signals. Compare both skill cohorts; the all-response cohort is the descriptive starting point.",
        "Only all-response subgroup and delivery tables are released. Exact-date tables, transition matrices, models and diagnostic tests remain private.",
        "Topics use an English keyword codebook, not an AI sentiment model. Translated, negated and ambiguous comments require human review. Topic shares use nonblank answers and may overlap.",
        "Recommendations are automatically drafted from released metrics for staff review; no human approval is implied.",
        "Small cells, their complements and related results are protected. Zero, unavailable and withheld are distinct states. Review linked releases before sharing; this is not a formal anonymity guarantee.",
        "Missingness in optional questions may reflect not asked, skipped or invalid responses. The export does not identify these separately.",
    ]
    if set(config.registry.questions) - present:
        notes.append("Some optional questions are missing or ambiguous; see the separate private schema audit.")
    bundle = ReportBundle(
        generated_at=datetime.now(timezone.utc), input_hash=hashes["input_hash"],
        data_kind="synthetic" if synthetic else "survey", metrics=public, findings=draft_findings(public),
        theme_data=themes, quality_report=PublicQualityReport(metrics=[reference(m) for m in public if m.metric_id in {"usable_responses", "flagged_responses", "invalid_training_dates"}], notes=notes),
        suppression_policy=SuppressionPolicy(minimum_n=minimum),
        definitions={"agreement": "Score 4 or 5 on the five-point skill scale, among complete before/current pairs.",
                     "uncertainty": "Agreement uses 95% Wilson intervals; mean ordinal change uses a seeded paired bootstrap. These intervals do not account for all survey biases.",
                     "calling_intent": "Mean stated likelihood on the 0–10 scale among valid answers; not actual calls or demonstrated behavior.",
                     "traceability": "Metrics carry input/settings hashes, method, population and calculation base. Release metadata records software, library and codebook versions.",
                     "topic_coding": "One deterministic keyword codebook labels topics, not sentiment. It is English-only and requires private manual validation before operational recommendations."},
        caveats=[Caveat(id=identifier, label=label, explanation=text) for identifier, label, text in [
            ("retrospective", "Self-reported, retrospective ratings", "Both ratings were collected after training. Recall bias, response shift and no control group prevent causal claims."),
            ("selection", "Selection and response quality", "Respondents and complete pairs may differ from nonrespondents. Flags are not proof of invalidity."),
            ("calling", "Calling-question exposure is uncertain", "Blank answers cannot distinguish not asked from skipped. Stated willingness does not measure calls."),
            ("communities", "Descriptive community comparisons", "Public subgroup comparisons are unadjusted. Role groups overlap; dates and response composition may differ. Do not sum role counts as unique people."),
            ("coding", "Keyword topics require review", "Automated English keyword matches can miss meaning, negation and other languages. Review private source-row locators, including unmatched comments. No raw comments are published."),
            ("privacy", "Review before external sharing", "Table and cohort guards reduce disclosure risk but do not provide differential privacy or guarantee protection across linked reports and external information.")]],
        release_metadata=ReleaseMetadata(software_version=SOFTWARE_VERSION, python_version=platform.python_version(),
                                         library_versions={name: version(name) for name in ("numpy", "pandas", "scipy", "statsmodels", "pydantic")},
                                         codebook_version=book["version"], codebook_hash=book_hash),
    )
    validate_release(bundle)
    audit = {"visibility": "private_local_diagnostics", "config_hash": config_hash,
             "ingestion": incoming.audit, **quality.report,
             "comment_review": {"status": "human_review_required", "codebook_version": book["version"],
                                "instructions": "source_record means Excel worksheet row or logical CSV record (header is 1; multiline CSV records are not physical line numbers). Blank records are accounted for. Compare labels against the PRIVATE source. Check matches, nonmatches, negation and non-English responses. Record disagreements separately; no review has been claimed by the software.",
                                "rows": review}}
    return bundle, audit
