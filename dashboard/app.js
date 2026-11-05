"use strict";

const svgNamespace = "http://www.w3.org/2000/svg";
const skills = [
  ["identify_crises", "Identify crises"],
  ["describe_988", "Describe 988"],
  ["know_when_to_use_988", "Know when to use 988"],
];
const directions = [["up", "Up"], ["same", "Same"], ["down", "Down"]];
const integer = new Intl.NumberFormat("en-US");
const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });
const dashboard = document.querySelector("#dashboard");
const banner = document.querySelector("#draft-banner");
const status = document.querySelector("#load-status");

function html(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function svg(tag, attributes, className) {
  const node = document.createElementNS(svgNamespace, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (className) node.setAttribute("class", className);
  return node;
}

function chart() {
  const plot = svg("svg", { viewBox: "0 0 1000 40", preserveAspectRatio: "none", "aria-hidden": "true" }, "plot");
  plot.append(svg("rect", { x: 8, y: 15, width: 984, height: 10, rx: 5 }, "track"));
  return plot;
}

function xPosition(fraction) {
  return 8 + 984 * fraction;
}

function bar(plot, start, end, className) {
  if (end > start) {
    plot.append(svg("rect", { x: xPosition(start), y: 15, width: 984 * (end - start), height: 10 }, className));
  }
}

function line(plot, x1, y1, x2, y2, className, attributes = {}) {
  plot.append(svg("line", { x1, y1, x2, y2, "vector-effect": "non-scaling-stroke", ...attributes }, className));
}

function allResponses(metric) {
  return metric?.dimensions?.cohort === "all_responses";
}

function metricFor(ledger, id, dimensions) {
  return ledger.find((metric) => allResponses(metric) && metric.metric_id === id &&
    Object.entries(dimensions).every(([key, value]) => metric.dimensions[key] === value));
}

function isCount(value) {
  return Number.isSafeInteger(value) && value >= 0;
}

function isShare(value) {
  return Number.isFinite(value) && value >= 0 && value <= 1;
}

function visibleShare(metric) {
  return metric?.suppressed === false && isShare(metric.value) && isCount(metric.n) && metric.n > 0;
}

function withheld(minimum) {
  return `n<${minimum} withheld`;
}

function unavailable(metric, minimum) {
  return metric?.suppressed === true ? withheld(minimum) : "Unavailable";
}

function percentage(metric) {
  return `${percent.format(metric.value)} (n=${integer.format(metric.n)})`;
}

function interval(metric) {
  const ci = metric.ci;
  if (isShare(ci?.lower) && isShare(ci?.upper) && ci.lower <= ci.upper) return ci;
  return null;
}

function row(name) {
  const node = html("div", "", "chart-row");
  node.append(html("h3", name));
  return node;
}

function agreementSeries(plot, metric, y, className) {
  const ci = interval(metric);
  if (ci) {
    const lower = xPosition(ci.lower);
    const upper = xPosition(ci.upper);
    line(plot, lower, y, upper, y, `${className} whisker`);
    line(plot, lower, y - 5, lower, y + 5, `${className} whisker`);
    line(plot, upper, y - 5, upper, y + 5, `${className} whisker`);
  }
  const point = xPosition(metric.value);
  line(plot, point, y - 1, point, y + 1, className, { "stroke-width": 7, "stroke-linecap": "round" });
}

function renderObjectives(ledger, minimum) {
  const section = document.querySelector("#objectives");
  section.replaceChildren();
  for (const [skill, label] of skills) {
    const card = row(label);
    const before = metricFor(ledger, "agree_before", { skill });
    const after = metricFor(ledger, "agree_after", { skill });
    const plot = chart();
    if (visibleShare(before) && visibleShare(after)) {
      line(plot, xPosition(before.value), 11, xPosition(after.value), 29, "connector");
    }
    const values = html("div", "", "values");
    for (const [metric, title, series, y] of [[before, "Before", "before", 11], [after, "After", "after", 29]]) {
      let label = unavailable(metric, minimum);
      if (visibleShare(metric)) {
        const ci = interval(metric);
        label = percentage(metric);
        if (ci) label += ` · CI ${percent.format(ci.lower)}–${percent.format(ci.upper)}`;
        agreementSeries(plot, metric, y, series);
      }
      values.append(html("span", `${title} ${label}`, `measure measure-${series}`));
    }
    card.append(values, plot);
    section.append(card);
  }
}

function renderGaps(ledger, minimum) {
  const section = document.querySelector("#remaining-gap");
  section.replaceChildren();
  for (const [skill, label] of skills) {
    const card = row(label);
    const metric = metricFor(ledger, "below_agree_after", { skill });
    if (visibleShare(metric) && isCount(metric.numerator)) {
      const plot = chart();
      bar(plot, 0, metric.value, "bar-gap");
      card.append(html("p", `${percentage(metric)} · ${integer.format(metric.numerator)} below Agree`), plot);
    } else {
      card.append(html("p", unavailable(metric, minimum)));
    }
    section.append(card);
  }
}

function renderMovement(ledger, minimum) {
  const section = document.querySelector("#movement");
  section.replaceChildren();
  for (const [skill, label] of skills) {
    const card = row(label);
    const entries = directions.map(([key, title]) => [key, title, metricFor(ledger, `movement_${key}`, { skill })]);
    if (entries.every(([, , metric]) => visibleShare(metric) && isCount(metric.numerator))) {
      const plot = chart();
      const values = html("div", "", "values");
      let start = 0;
      for (const [key, title, metric] of entries) {
        const end = Math.min(1, start + metric.value);
        bar(plot, start, end, `bar-${key}`);
        start = end;
        values.append(html("span", `${title} ${percentage(metric)} · ${integer.format(metric.numerator)} responses`,
          `measure measure-${key}`));
      }
      card.append(values, plot);
    } else {
      const hidden = entries.some(([, , metric]) => metric?.suppressed === true);
      card.append(html("p", hidden ? "Movement breakdown withheld" : "Movement breakdown unavailable"));
    }
    section.append(card);
  }
}

function renderCoverage(ledger, minimum) {
  const calling = document.querySelector("#calling-coverage");
  calling.replaceChildren();
  const coverage = metricFor(ledger, "calling_coverage", { group_by: "overall", group: "Overall" });
  if (visibleShare(coverage) && isCount(coverage.numerator) && isCount(coverage.denominator)) {
    const plot = chart();
    bar(plot, 0, coverage.value, "bar-coverage");
    calling.append(html("p", `${integer.format(coverage.numerator)}/${integer.format(coverage.denominator)} answered · ` +
      percentage(coverage)), plot);
  } else {
    calling.append(html("p", unavailable(coverage, minimum)));
  }

  const months = document.querySelector("#training-months");
  months.replaceChildren();
  const entries = ledger.filter((metric) => allResponses(metric) && metric.metric_id === "subgroup_response_count" &&
    metric.dimensions.group_by === "training_month" && /^\d{4}-(0[1-9]|1[0-2])$/.test(metric.dimensions.group));
  entries.sort((a, b) => a.dimensions.group.localeCompare(b.dimensions.group));
  if (!entries.length) months.append(html("p", "Training-month coverage is unavailable in this report."));
  const visibleCount = (metric) => metric.suppressed === false && isCount(metric.value);
  const max = entries.reduce((largest, metric) => visibleCount(metric) ? Math.max(largest, metric.value) : largest, 1);
  for (const metric of entries) {
    const item = html("div", "", "chart-row");
    const heading = html("div", "", "month-label");
    heading.append(html("strong", metric.dimensions.group), html("span", visibleCount(metric) ?
      `n=${integer.format(metric.value)}` : unavailable(metric, minimum), "month-count-value"));
    item.append(heading);
    if (visibleCount(metric)) {
      const plot = chart();
      bar(plot, 0, metric.value / max, "month-count");
      item.append(plot);
    }
    months.append(item);
  }
}

function render(report) {
  if (!report || !Array.isArray(report.metrics)) throw new Error("Expected a report with a metric ledger");
  const configured = report.suppression_policy?.minimum_n;
  const minimum = isCount(configured) && configured > 0 ? configured : 10;
  renderObjectives(report.metrics, minimum);
  renderGaps(report.metrics, minimum);
  renderMovement(report.metrics, minimum);
  renderCoverage(report.metrics, minimum);
  banner.hidden = report.data_kind !== "synthetic";
  dashboard.hidden = false;
  status.textContent = "Report loaded.";
}

let requestNumber = 0;
async function load(readReport) {
  const current = ++requestNumber;
  try {
    const report = await readReport();
    if (current === requestNumber) render(report);
  } catch {
    if (current !== requestNumber) return;
    dashboard.hidden = true;
    banner.hidden = true;
    status.textContent = "Could not read a report. Choose a report JSON file or serve the repository and reopen the dashboard.";
  }
}

document.querySelector("#report-picker").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file) load(async () => JSON.parse(await file.text()));
});

if (location.protocol === "file:") {
  status.textContent = "Choose a report JSON file, or serve the repository to load the sample automatically.";
} else {
  load(async () => {
    let response = await fetch("./report.json");
    if (response.status === 404) response = await fetch("../fixtures/report.sample.json");
    if (!response.ok) throw new Error("Report fetch failed");
    return response.json();
  });
}
