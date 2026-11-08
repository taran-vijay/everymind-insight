/* Shared, DOM-free rules for reading the public aggregate report. */
(function (root) {
  "use strict";
  const count = (value) => Number.isSafeInteger(value) && value >= 0;
  const share = (value) => Number.isFinite(value) && value >= 0 && value <= 1;
  const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
  const digest = (value) => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
  function awareDateTime(value) {
    if (typeof value !== "string") return false;
    const parts = /^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?([Zz]|[+-](\d{2}):(\d{2}))$/.exec(value);
    if (!parts) return false;
    const [year, month, day, hour, minute, second] = parts.slice(1, 7).map(Number);
    const monthDays = [31, year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    return year > 0 && month >= 1 && month <= 12 && day >= 1 && day <= monthDays[month - 1]
      && hour < 24 && minute < 60 && second < 60
      && (parts[8] === undefined || (Number(parts[8]) < 24 && Number(parts[9]) < 60))
      && Number.isFinite(Date.parse(value));
  }
  const key = (id, dimensions) => JSON.stringify([id, Object.entries(dimensions).sort(([a], [b]) => a.localeCompare(b))]);
  const find = (metrics, id, dimensions = {}) => metrics.find((metric) => key(metric.metric_id, metric.dimensions) === key(id, dimensions));
  const released = (metric) => metric?.suppressed === false && Number.isFinite(metric.value) && count(metric.n);
  const visibleShare = (metric) => released(metric) && metric.unit === "proportion" && share(metric.value) && metric.n > 0;
  const visibleCount = (metric) => released(metric) && metric.unit === "count" && count(metric.value);
  function interval(metric) {
    const ci = metric?.ci;
    return visibleShare(metric) && ci && share(ci.lower) && share(ci.upper) && ci.lower <= ci.upper
      && Number.isFinite(ci.level) && ci.level > 0 && ci.level < 1 ? ci : null;
  }
  function validate(report) {
    if (!object(report) || report.schema_version !== "1.0.0" || !Array.isArray(report.metrics)
      || !awareDateTime(report.generated_at) || !digest(report.input_hash)
      || !["survey", "synthetic"].includes(report.data_kind)
      || !Array.isArray(report.findings) || !object(report.theme_data) || !Array.isArray(report.theme_data.questions)
      || !["available", "unavailable"].includes(report.theme_data.status)
      || !object(report.quality_report) || !Array.isArray(report.quality_report.metrics)
      || !Array.isArray(report.quality_report.notes) || !Array.isArray(report.caveats)
      || !report.caveats.every((caveat) => object(caveat) && ["id", "label", "explanation"].every((field) => typeof caveat[field] === "string"))
      || !report.quality_report.notes.every((note) => typeof note === "string")
      || !object(report.definitions) || !Object.values(report.definitions).every((value) => typeof value === "string")
      || !object(report.suppression_policy)
      || !count(report.suppression_policy.minimum_n) || report.suppression_policy.minimum_n < 1) {
      throw new Error("Choose a version 1.0.0 aggregate report bundle.");
    }
    const seen = new Set();
    for (const metric of report.metrics) {
      if (!object(metric) || typeof metric.metric_id !== "string" || !object(metric.dimensions)
        || Object.values(metric.dimensions).some((value) => typeof value !== "string")
        || typeof metric.suppressed !== "boolean" || typeof metric.definition !== "string"
        || !["count", "proportion", "percentage_point", "ordinal_point", "ratio", "p_value", "statistic", "rank"].includes(metric.unit)) throw new Error("Invalid metric ledger.");
      const provenance = metric.provenance;
      if (!object(provenance) || !digest(provenance.input_hash) || !digest(provenance.config_hash)
        || provenance.input_hash !== report.input_hash
        || typeof provenance.method !== "string" || typeof provenance.population !== "string"
        || (provenance.parameters !== undefined && (!object(provenance.parameters)
          || Object.values(provenance.parameters).some((value) => !["string", "boolean"].includes(typeof value) && !Number.isFinite(value))))) {
        throw new Error("Invalid metric provenance or mismatched input fingerprint.");
      }
      const id = key(metric.metric_id, metric.dimensions);
      if (seen.has(id)) throw new Error("Duplicate metric in the report.");
      seen.add(id);
      if (metric.suppressed && ["value", "numerator", "denominator", "ci", "n"].some((field) => metric[field] != null)) {
        throw new Error("Suppressed metrics must omit all numeric fields.");
      }
      if (metric.value == null && (typeof metric.reason !== "string" || !metric.reason.trim())) {
        throw new Error("Unavailable or suppressed metrics require a reason.");
      }
      if (!metric.suppressed) {
        if (metric.n != null && !count(metric.n)) throw new Error("Invalid response count.");
        for (const field of ["value", "numerator", "denominator"]) {
          if (metric[field] != null && !Number.isFinite(metric[field])) throw new Error("Invalid metric value.");
        }
        if (metric.ci != null && (!object(metric.ci) || !Number.isFinite(metric.ci.lower) || !Number.isFinite(metric.ci.upper)
          || metric.ci.lower > metric.ci.upper || !(metric.ci.level > 0 && metric.ci.level < 1))) throw new Error("Invalid interval.");
        if (metric.unit === "proportion" && metric.value != null && !share(metric.value)) throw new Error("Invalid proportion.");
        if (metric.unit === "count" && metric.value != null && !count(metric.value)) throw new Error("Invalid count.");
        if (["proportion", "percentage_point"].includes(metric.unit) && metric.value != null) {
          const scale = metric.unit === "percentage_point" ? 100 : 1;
          if (!(metric.denominator > 0) || !Number.isFinite(metric.numerator)
            || Math.abs(metric.value - scale * metric.numerator / metric.denominator) > 1e-10) {
            throw new Error("A metric does not reconcile to its calculation base.");
          }
        }
      }
    }
    const reference = (ref) => object(ref) && typeof ref.metric_id === "string" && object(ref.dimensions)
      && Object.values(ref.dimensions).every((value) => typeof value === "string")
      && seen.has(key(ref.metric_id, ref.dimensions));
    const caveatIds = new Set(report.caveats.map((caveat) => caveat?.id));
    for (const finding of report.findings) {
      if (!object(finding) || !["observation", "interpretation", "action"].every((field) => typeof finding[field] === "string")
        || !["low", "moderate", "high"].includes(finding.confidence)
        || !Array.isArray(finding.metric_refs) || !finding.metric_refs.every(reference)
        || !Array.isArray(finding.caveat_ids) || finding.caveat_ids.some((id) => !caveatIds.has(id))) {
        throw new Error("Invalid finding references.");
      }
    }
    for (const question of report.theme_data.questions) {
      if (!object(question) || typeof question.label !== "string" || !reference(question.answered)
        || (question.diagnostics !== undefined && (!Array.isArray(question.diagnostics) || !question.diagnostics.every(reference)))
        || !Array.isArray(question.themes) || question.themes.some((theme) => !object(theme)
          || typeof theme.label !== "string" || !["codebook", "embedding"].includes(theme.method)
          || !Array.isArray(theme.prevalence) || !theme.prevalence.every(reference))) {
        throw new Error("Invalid theme references.");
      }
    }
    if (!report.quality_report.metrics.every(reference)) throw new Error("Invalid quality references.");
    if (report.release_metadata != null) {
      const meta = report.release_metadata;
      if (!object(meta) || meta.policy_version !== "1.0.0"
        || !["software_version", "python_version", "codebook_version"].every((name) => typeof meta[name] === "string")
        || !digest(meta.codebook_hash) || !object(meta.library_versions)
        || !Object.values(meta.library_versions).every((value) => typeof value === "string")
        || meta.recommendation_status !== "automated_draft_for_staff_review") throw new Error("Invalid release metadata.");
    }
    return report;
  }
  function safeFinding(finding, metrics) {
    return finding.metric_refs.length > 0 && finding.metric_refs.every((ref) => released(find(metrics, ref.metric_id, ref.dimensions)));
  }
  function movement(metrics, skill, cohort) {
    const entries = ["up", "same", "down"].map((direction) => find(metrics, `movement_${direction}`, { skill, cohort }));
    if (!entries.every((metric) => visibleShare(metric) && count(metric.numerator))) return null;
    if (!entries.every((metric) => metric.n === entries[0].n && metric.denominator === entries[0].denominator)
      || Math.abs(entries.reduce((sum, metric) => sum + metric.value, 0) - 1) > 1e-8) return null;
    return entries;
  }
  const api = { count, share, key, find, released, visibleShare, visibleCount, interval, validate, safeFinding, movement };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReportData = api;
})(globalThis);
