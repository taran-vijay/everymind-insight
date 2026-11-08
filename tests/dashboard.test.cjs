const { test } = require("node:test");
const assert = require("node:assert/strict");
const Data = require("../dashboard/report-data.js");
const fixture = require("../fixtures/report.sample.json");
const sample = () => structuredClone(fixture);

test("accepts the shipped public report without changing its values", () => {
  const report = sample();
  assert.equal(Data.validate(report), report);
  assert.deepEqual(report, fixture);
});
test("rejects malformed metadata and JSON objects that would throw during rendering", () => {
  for (const [field, values] of [
    ["generated_at", [null, 0, {}, { toString: null, valueOf: null }, "not a date", "2030-01-01", "2030-01-01T12:00:00", "2030-02-30T12:00:00Z", "2030-01-01T24:00:00Z"]],
    ["input_hash", [null, 123, {}, { toString: null, valueOf: null }, "", "a".repeat(63), "G".repeat(64)]],
  ]) {
    for (const value of values) {
      const incoming = sample();
      incoming[field] = value;
      // Use JSON round-tripping so these regressions exercise actual uploaded values.
      assert.throws(() => Data.validate(JSON.parse(JSON.stringify(incoming))), /aggregate report bundle/);
    }
    const missing = sample();
    delete missing[field];
    assert.throws(() => Data.validate(missing), /aggregate report bundle/);
  }
});
test("accepts generated timezone-aware timestamps including offsets and microseconds", () => {
  for (const generated_at of ["2030-01-01T00:00:00Z", "2030-01-01T00:00:00.123456+00:00", "2030-01-01T10:30:00-05:00", "2028-02-29T23:59:59+05:30"]) {
    const report = sample();
    report.generated_at = generated_at;
    assert.equal(Data.validate(report), report);
    assert.equal(report.generated_at, generated_at);
  }
});
test("rejects missing or malformed ledger provenance and mixed input fingerprints", () => {
  for (const mutate of [
    (metric) => { delete metric.provenance; },
    (metric) => { metric.provenance = null; },
    (metric) => { metric.provenance.input_hash = "a".repeat(64); },
    (metric) => { metric.provenance.config_hash = "invalid"; },
    (metric) => { metric.provenance.method = {}; },
    (metric) => { metric.provenance.population = []; },
    (metric) => { metric.provenance.parameters = null; },
    (metric) => { metric.provenance.parameters = { seed: {} }; },
  ]) {
    const report = sample();
    mutate(report.metrics[0]);
    assert.throws(() => Data.validate(report), /provenance|fingerprint/);
  }
  const report = sample();
  delete report.metrics[0].provenance.parameters;
  report.metrics[1].provenance.parameters = { seed: 988, threshold: .8, adjusted: false, method: "bootstrap" };
  assert.equal(Data.validate(report), report);
});
test("checks theme diagnostic references while allowing the schema's empty default", () => {
  const valid = sample();
  const question = valid.theme_data.questions[0];
  question.diagnostics = [structuredClone(question.answered)];
  assert.equal(Data.validate(valid), valid);
  delete question.diagnostics;
  assert.equal(Data.validate(valid), valid);
  for (const diagnostics of [null, {}, [{ metric_id: "absent", dimensions: {} }], [{ ...question.answered, dimensions: { question: "other_question" } }]]) {
    const report = sample();
    report.theme_data.questions[0].diagnostics = diagnostics;
    assert.throws(() => Data.validate(report), /theme references/);
  }
});
test("rejects every numeric field on a suppressed metric", () => {
  for (const field of ["value", "numerator", "denominator", "n", "ci"]) {
    const report = sample();
    const entry = report.metrics.find((metric) => metric.suppressed);
    entry[field] = field === "ci" ? { lower: 1, upper: 2, level: .95 } : 123456789;
    assert.throws(() => Data.validate(report), /Suppressed metrics/);
  }
});
test("keeps released zero counts distinct from withheld and missing values", () => {
  const zero = { suppressed: false, unit: "count", value: 0, n: 0 };
  assert.equal(Data.visibleCount(zero), true);
  assert.equal(Data.visibleCount({ ...zero, suppressed: true, value: null, n: null }), false);
  assert.equal(Data.visibleCount({ ...zero, value: null }), false);
});
test("cannot borrow a value from a different cohort or subgroup", () => {
  const entries = [
    { metric_id: "agree_after", dimensions: { skill: "a", cohort: "all_responses" }, value: .9 },
    { metric_id: "agree_after", dimensions: { skill: "a", cohort: "excluding_flagged" }, value: .7 },
    { metric_id: "agree_after", dimensions: { skill: "a", cohort: "all_responses", group: "X" }, value: .4 },
  ];
  assert.equal(Data.find(entries, "agree_after", { cohort: "excluding_flagged", skill: "a" }).value, .7);
  assert.equal(Data.find(entries, "agree_after", { skill: "a" }), undefined);
});
test("does not reconstruct a missing movement segment", () => {
  const report = sample();
  const dimensions = { skill: "identify_crises", cohort: "all_responses" };
  assert.equal(Data.movement(report.metrics, dimensions.skill, dimensions.cohort).length, 3);
  const withheld = Data.find(report.metrics, "movement_down", dimensions);
  Object.assign(withheld, { suppressed: true, value: null, numerator: null, denominator: null, ci: null, n: null });
  assert.equal(Data.movement(report.metrics, dimensions.skill, dimensions.cohort), null);
});
test("requires movement percentages to share a population and sum to one", () => {
  const report = sample();
  const entry = Data.find(report.metrics, "movement_same", { skill: "identify_crises", cohort: "all_responses" });
  entry.n = 449;
  assert.equal(Data.movement(report.metrics, "identify_crises", "all_responses"), null);
  entry.n = 450;
  entry.value = .1;
  assert.equal(Data.movement(report.metrics, "identify_crises", "all_responses"), null);
});
test("withholds findings whose supporting evidence is withheld or missing", () => {
  const report = sample();
  const finding = report.findings[0];
  assert.equal(Data.safeFinding(finding, report.metrics), true);
  const ref = finding.metric_refs[0];
  Data.find(report.metrics, ref.metric_id, ref.dimensions).suppressed = true;
  assert.equal(Data.safeFinding(finding, report.metrics), false);
  assert.equal(Data.safeFinding({ metric_refs: [] }, report.metrics), false);
  assert.equal(Data.safeFinding(finding, []), false);
});
test("rejects broken references and duplicates even with reordered dimensions", () => {
  const missing = sample();
  missing.findings[0].metric_refs[0].metric_id = "absent";
  assert.throws(() => Data.validate(missing), /references/);
  const duplicate = sample();
  const entry = structuredClone(duplicate.metrics[0]);
  entry.dimensions = Object.fromEntries(Object.entries(entry.dimensions).reverse());
  duplicate.metrics.push(entry);
  assert.throws(() => Data.validate(duplicate), /Duplicate/);
});
test("rejects inconsistent shares and non-finite values", () => {
  for (const value of [1.1, NaN, Infinity, .123456]) {
    const report = sample();
    report.metrics.find((entry) => entry.unit === "proportion").value = value;
    assert.throws(() => Data.validate(report));
  }
});
test("rejects unsupported formats and malformed written content before rendering", () => {
  for (const mutate of [
    (report) => { report.schema_version = "9.0.0"; },
    (report) => { report.caveats = [null]; },
    (report) => { report.quality_report.notes = [{}]; },
    (report) => { report.theme_data.questions[0].themes[0].method = "unknown"; },
    (report) => { report.theme_data.status = "unknown"; },
  ]) {
    const report = sample();
    mutate(report);
    assert.throws(() => Data.validate(report));
  }
});

test("rejects unavailable metrics without reasons", () => {
  const report = sample();
  const metric = report.metrics.find((entry) => entry.suppressed);
  metric.reason = " ";
  assert.throws(() => Data.validate(report), /reason/);
});
test("checks optional release metadata without requiring it on legacy samples", () => {
  const report = sample();
  report.release_metadata = {
    policy_version: "1.0.0", software_version: "test", python_version: "3.11",
    codebook_version: "1.0.0", codebook_hash: "a".repeat(64),
    library_versions: { pandas: "test" }, recommendation_status: "automated_draft_for_staff_review",
  };
  assert.equal(Data.validate(report), report);
  report.release_metadata.codebook_hash = "invalid";
  assert.throws(() => Data.validate(report), /release metadata/);
});
