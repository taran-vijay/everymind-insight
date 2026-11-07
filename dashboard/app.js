"use strict";

const Data = ReportData;
const skills = [
  ["identify_crises", "Identify crises"],
  ["describe_988", "Describe 988"],
  ["know_when_to_use_988", "Know when to use 988"],
];
const views = {
  overview: "Training insights",
  learning: "Learning outcomes",
  community: "Community reach",
  feedback: "Participant feedback",
  methods: "Data & methods",
};
const integer = new Intl.NumberFormat("en-US");
const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });
const decimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const dateFormat = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
const monthFormat = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
const motionEasing = getComputedStyle(document.documentElement).getPropertyValue("--ease-out").trim() || "ease-out";
let renderRoot = document;
const $ = (selector) => renderRoot.querySelector(selector);
let report = null;
let requestNumber = 0;
const rememberedRoutes = {};
let activeView = "";
let activeTarget = "";

function route() {
  const [requested, query = ""] = location.hash.slice(1).split("?");
  return { view: Object.hasOwn(views, requested) ? requested : "overview", params: new URLSearchParams(query) };
}
function destination(view, values = {}) {
  const query = new URLSearchParams(Object.entries(values).filter(([, value]) => value));
  return `#${view}${query.size ? `?${query}` : ""}`;
}
function setRoute(values) {
  const current = route();
  for (const [key, value] of Object.entries(values)) {
    if (value) current.params.set(key, value);
    else current.params.delete(key);
  }
  location.hash = destination(current.view, Object.fromEntries(current.params));
}
function animateResult(node) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  for (const animation of node.getAnimations()) animation.cancel();
  node.animate([{ opacity: .72 }, { opacity: 1 }], { duration: 180, easing: motionEasing });
}
function announce(text) { $("#interaction-status").textContent = text; }
function positionIndicator() {
  const selected = document.querySelector('nav a[aria-current="page"]');
  const indicator = document.querySelector("#nav-indicator");
  if (!selected || !indicator) return;
  const width = selected.offsetWidth;
  const left = selected.offsetLeft;
  indicator.style.transform = `translateX(${left}px) scaleX(${width})`;
}

function html(tag, text = "", className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}
function svg(tag, attrs, className = "") {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (className) node.setAttribute("class", className);
  return node;
}
function link(text, destination) {
  const node = html("a", text, "text-link");
  node.href = destination;
  return node;
}
function empty(title, text) {
  const node = html("div", "", "empty-state");
  node.append(html("h3", title));
  if (text) node.append(html("p", text));
  return node;
}
function metric(id, dimensions = {}, cohort = "all_responses") {
  return Data.find(report.metrics, id, { ...dimensions, cohort });
}
function refMetric(ref) {
  return Data.find(report.metrics, ref.metric_id, ref.dimensions);
}
function unavailable(entry) {
  return entry?.suppressed ? "Withheld" : "Unavailable";
}
function shareText(entry) {
  return Data.visibleShare(entry) ? percent.format(entry.value) : unavailable(entry);
}
function countText(entry) {
  return Data.visibleCount(entry) ? integer.format(entry.value) : unavailable(entry);
}
function gainText(entry) {
  if (!Data.released(entry) || entry.unit !== "percentage_point") return unavailable(entry);
  return `${entry.value > 0 ? "+" : ""}${decimal.format(entry.value)} pp`;
}
function intervalText(entry) {
  const ci = Data.interval(entry);
  return ci ? `${percent.format(ci.level)} interval: ${percent.format(ci.lower)}–${percent.format(ci.upper)}` : "Interval unavailable";
}
function baseText(entry) {
  return Data.released(entry) ? `n=${integer.format(entry.n)}` : unavailable(entry);
}
function metricText(entry) {
  if (!Data.released(entry)) return unavailable(entry);
  if (entry.unit === "proportion") return shareText(entry);
  if (entry.unit === "percentage_point") return gainText(entry);
  return entry.unit === "count" ? integer.format(entry.value) : decimal.format(entry.value);
}
function stat(label, value, note) {
  const node = html("div");
  const number = html("dd", "", "stat-value");
  number.append(html("span", value, "metric-number"));
  node.append(html("dt", label), number);
  if (note) node.append(html("div", note, "stat-note"));
  return node;
}
function monthLabel(value) {
  return /^\d{4}-(0[1-9]|1[0-2])$/.test(value) ? monthFormat.format(new Date(`${value}-01T00:00:00Z`)) : value;
}

function navigate(focus = false, initial = false) {
  const { view, params } = route();
  if (report && view === "learning" && params.has("cohort")
    && (params.get("cohort") !== "excluding_flagged" || $("#learning-cohort option[value=excluding_flagged]").disabled)) {
    params.delete("cohort");
    history.replaceState(null, "", destination(view, Object.fromEntries(params)));
  }
  const changed = view !== activeView;
  if (changed) announce("");
  rememberedRoutes[view] = destination(view, Object.fromEntries(params));
  $("#section-picker").value = view;
  $("#main-content").dataset.view = view;
  for (const node of document.querySelectorAll(".view")) node.hidden = node.id !== `view-${view}`;
  for (const node of document.querySelectorAll("nav [data-view]")) {
    node.href = rememberedRoutes[node.dataset.view] || `#${node.dataset.view}`;
    if (node.dataset.view === view) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  }
  $("#page-title").textContent = views[view];
  document.title = `${views[view]} · EveryMind`;
  if (report) {
    if (view === "overview") {
      const movement = params.get("chart") === "movement";
      $("#agreement-chart").hidden = movement;
      $("#rating-chart").hidden = !movement;
      $("#show-intervals").checked = params.get("intervals") !== "off";
      $("#show-intervals").closest("label").hidden = movement;
      for (const button of document.querySelectorAll("[data-chart]")) button.setAttribute("aria-pressed", String(button.dataset.chart === (movement ? "movement" : "agreement")));
      $("#chart-description").textContent = movement ? "Change in paired ratings" : "Agree or Strongly agree";
      renderObjectives(changed || initial);
    } else if (view === "learning") {
      const filtered = params.get("cohort") === "excluding_flagged" && !$("#learning-cohort option[value=excluding_flagged]").disabled;
      $("#learning-cohort").value = filtered ? "excluding_flagged" : "all_responses";
      renderLearning();
    } else if (view === "community") {
      const group = params.get("group");
      $("#community-group").value = ["county", "role", "language", "training_month"].includes(group) ? group : "county";
      $("#community-skill").value = skills.some(([id]) => id === params.get("skill")) ? params.get("skill") : skills[0][0];
      renderCommunity();
    }
  }
  const target = report && (view === "learning" ? document.getElementById(`outcome-${params.get("skill")}`) : view === "feedback" ? document.getElementById(`finding-${params.get("finding")}`) : null);
  const targetKey = target?.id || "";
  if ((focus && (changed || targetKey !== activeTarget)) || (initial && target)) {
    if (target) {
      if (focus) target.focus({ preventScroll: true });
      target.scrollIntoView({ block: "start", behavior: "instant" });
    } else {
      $("#main-content").focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: "instant" });
    }
  }
  if (focus) {
    const section = $(`#view-${view}`);
    if (changed) {
      if (!matchMedia("(prefers-reduced-motion: reduce)").matches) section.animate([{ opacity: 0, transform: "translateY(5px)" }, { opacity: 1, transform: "none" }], { duration: 220, easing: motionEasing });
    } else if (view === "learning" || view === "community") animateResult($(view === "learning" ? "#learning-details" : "#community-results"));
    if (view === "learning") announce(`Learning outcomes updated. ${$("#learning-cohort").selectedOptions[0].textContent}.`);
    if (view === "community") announce(`Community comparison updated. ${$("#community-skill").selectedOptions[0].textContent}, by ${$("#community-group").selectedOptions[0].textContent.toLowerCase()}.`);
    if (view === "overview" && !changed) announce(params.get("chart") === "movement" ? "Rating movement chart." : `Agreement chart. Intervals ${$("#show-intervals").checked ? "shown" : "hidden"}.`);
  }
  activeView = view;
  activeTarget = targetKey;
  positionIndicator();
}

function renderSummary() {
  const total = Data.find(report.metrics, "usable_responses");
  const months = report.metrics.filter((entry) => entry.metric_id === "subgroup_response_count"
    && entry.dimensions.cohort === "all_responses" && entry.dimensions.group_by === "training_month"
    && /^\d{4}-(0[1-9]|1[0-2])$/.test(entry.dimensions.group));
  $("#report-summary").replaceChildren(
    stat("survey responses", countText(total)),
    stat("training months", months.length ? integer.format(months.length) : "Unavailable"),
  );
}

function comparisonPlot(before, after, showIntervals) {
  const plot = svg("svg", { viewBox: "0 0 300 64", preserveAspectRatio: "none", "aria-hidden": "true" }, "plot");
  const x = (value) => 7 + value * 286;
  const line = (x1, y1, x2, y2, className) => plot.append(svg("line", { x1, y1, x2, y2, "vector-effect": "non-scaling-stroke" }, className));
  for (const tick of [0, .25, .5, .75, 1]) line(x(tick), 0, x(tick), 64, "gridline");
  for (const [entry, y, series] of [[before, 19, "before"], [after, 45, "after"]]) {
    if (!Data.visibleShare(entry)) continue;
    plot.append(svg("rect", { x: x(0), y: y - 5, width: entry.value * 286, height: 10, rx: 1 }, `${series} bar-mark`));
    const ci = Data.interval(entry);
    if (showIntervals && ci) {
      line(x(ci.lower), y, x(ci.upper), y, `${series} whisker`);
      line(x(ci.lower), y - 4, x(ci.lower), y + 4, `${series} whisker`);
      line(x(ci.upper), y - 4, x(ci.upper), y + 4, `${series} whisker`);
    }
  }
  return plot;
}

function renderObjectives(animate = false) {
  const container = $("#objectives");
  container.replaceChildren();
  const intervals = skills.flatMap(([skill]) => [metric("agree_before", { skill }), metric("agree_after", { skill })]).map(Data.interval).filter(Boolean);
  const levels = [...new Set(intervals.map((ci) => percent.format(ci.level)))];
  $("#interval-explanation").textContent = levels.length === 1 ? `${levels[0]} confidence intervals` : "Confidence levels in Outcomes";
  $("#interval-explanation").hidden = !$("#show-intervals").checked || !intervals.length;
  for (const [index, [skill, label]] of skills.entries()) {
    const before = metric("agree_before", { skill });
    const after = metric("agree_after", { skill });
    const gain = metric("agreement_gain", { skill });
    const row = html("div", "", `comparison-row${animate ? " chart-animate" : ""}`);
    row.style.setProperty("--row", index);
    const name = html("div", "", "objective-name");
    const objectiveLink = link(label, destination("learning", { skill }));
    objectiveLink.className = "objective-link";
    name.append(objectiveLink, html("small", `${shareText(before)} before · ${baseText(after)}`));
    const chart = html("div", "", "comparison-plot");
    chart.append(comparisonPlot(before, after, $("#show-intervals").checked));
    const current = html("div", shareText(after), "metric-value");
    const change = html("div", gainText(gain), `gain${gain?.value < 0 ? " negative" : ""}`);
    const accessible = html("span", `Recalled before ${shareText(before)}, ${baseText(before)}. ${intervalText(before)}. Current ${shareText(after)}, ${baseText(after)}. ${intervalText(after)}. Change ${gainText(gain)}.`, "sr-only");
    chart.append(accessible);
    row.append(name, chart, current, change);
    container.append(row);
  }
  const scale = html("div", "", "comparison-scale");
  scale.setAttribute("aria-hidden", "true");
  const axis = html("div", "", "axis");
  for (const tick of ["0", "25", "50", "75", "100%"]) axis.append(html("span", tick));
  scale.append(html("span"), axis, html("span"), html("span"));
  container.append(scale);
}

function renderFocus() {
  const panel = $("#focus-panel");
  const introduction = html("div", "", "focus-intro");
  const heading = html("h2", "Remaining gap");
  heading.id = "focus-heading";
  introduction.append(heading);
  panel.replaceChildren(introduction);
  const gaps = skills.map(([skill, label]) => ({ skill, label, entry: metric("below_agree_after", { skill }) }));
  if (!gaps.every(({ entry }) => Data.visibleShare(entry))) {
    panel.append(html("p", "Some gap estimates are unavailable or withheld.", "focus-description"), link("View outcomes", "#learning"));
    return;
  }
  gaps.sort((a, b) => b.entry.value - a.entry.value);
  const largest = gaps[0];
  const tied = gaps.filter(({ entry }) => Math.abs(entry.value - largest.entry.value) < 1e-10).length > 1;
  heading.textContent = tied ? "Joint-largest gap" : "Largest remaining gap";
  const evidence = html("div", "", "focus-evidence");
  evidence.append(html("div", percent.format(largest.entry.value), "focus-stat"));
  const description = html("p", "", "focus-description");
  description.append(html("span", "rated their ability to "), html("span", largest.label.toLowerCase(), "focus-skill"), html("span", ` below Agree after training (${baseText(largest.entry)}).`));
  evidence.append(description);
  panel.append(evidence);
  const finding = report.findings.find((entry) => Data.safeFinding(entry, report.metrics)
    && entry.metric_refs.some((ref) => ref.metric_id === "below_agree_after" && ref.dimensions.skill === largest.skill
      && ref.dimensions.cohort === "all_responses"));
  const action = html("div", "", "focus-action");
  action.append(html("h3", finding ? "Recommendation" : "Review"),
    html("p", finding ? finding.action : "Review participant feedback for this objective."));
  if (finding) {
    action.append(html("span", `${finding.confidence[0].toUpperCase() + finding.confidence.slice(1)} confidence`, "confidence-tag"));
    action.append(link("View evidence →", destination("feedback", { finding: String(report.findings.indexOf(finding)) })));
  } else action.append(link("View feedback →", "#feedback"));
  panel.append(action);
}

function movementRow(skill, label, cohort, asBars = false) {
  const row = html("div", "", "movement-row");
  const entries = Data.movement(report.metrics, skill, cohort);
  const header = html("div", "", "movement-label");
  header.append(html("h3", label));
  row.append(header);
  if (!entries) {
    const anySuppressed = ["up", "same", "down"].some((direction) => metric(`movement_${direction}`, { skill }, cohort)?.suppressed);
    row.append(html("p", anySuppressed ? "Movement breakdown withheld" : "Movement breakdown unavailable", "unavailable"));
    return row;
  }
  const distribution = html("div", "", asBars ? "movement-bar-distribution" : "movement-distribution");
  const graphic = asBars ? html("div", "", "stacked-bar")
    : svg("svg", { viewBox: "0 0 104 104" }, "movement-ring");
  graphic.setAttribute("aria-hidden", "true");
  if (asBars) header.append(html("span", `n=${integer.format(entries[0].n)}`));
  else graphic.append(svg("circle", { cx: 52, cy: 52, r: 42 }, "ring-track"));
  const values = html("div", "", "movement-values");
  let offset = 0;
  entries.forEach((entry, index) => {
    const direction = ["up", "same", "down"][index];
    if (asBars) {
      const segment = html("span", "", direction);
      segment.style.flex = `${entry.value} 1 0%`;
      graphic.append(segment);
    } else graphic.append(svg("circle", { cx: 52, cy: 52, r: 42, pathLength: 100,
      "stroke-dasharray": `${entry.value * 100} ${100 - entry.value * 100}`,
      "stroke-dashoffset": -offset, transform: "rotate(-90 52 52)" }, `ring-segment ${direction}`));
    offset += entry.value * 100;
    const text = html("span", "", "movement-value");
    const key = html("span", "", "movement-key");
    const swatch = html("i", "", direction);
    swatch.setAttribute("aria-hidden", "true");
    key.append(swatch, document.createTextNode(["Higher", "Unchanged", "Lower"][index]));
    text.append(key, html("strong", percent.format(entry.value), "number"));
    text.title = `${integer.format(entry.numerator)} of ${integer.format(entry.denominator)} responses`;
    values.append(text);
  });
  if (!asBars) {
    const base = svg("text", { x: 52, y: 55, "text-anchor": "middle" }, "ring-base");
    base.textContent = `n=${integer.format(entries[0].n)}`;
    graphic.append(base);
  }
  values.append(html("span", `${integer.format(entries[0].n)} paired responses`, "sr-only"));
  distribution.append(graphic, values);
  row.append(distribution);
  return row;
}

function renderMonths() {
  const container = $("#training-months");
  const months = report.metrics.filter((entry) => entry.metric_id === "subgroup_response_count"
    && entry.dimensions.cohort === "all_responses" && entry.dimensions.group_by === "training_month"
    && /^\d{4}-(0[1-9]|1[0-2])$/.test(entry.dimensions.group))
    .sort((a, b) => a.dimensions.group.localeCompare(b.dimensions.group));
  container.replaceChildren();
  if (!months.length) container.append(empty("No monthly data"));
  const maximum = Math.max(1, ...months.filter(Data.visibleCount).map((entry) => entry.value));
  for (const entry of months) {
    const visible = Data.visibleCount(entry);
    const column = html("div", "", `month-column${visible && entry.value === maximum ? " peak" : ""}`);
    const track = html("div", "", "month-track");
    if (visible) {
      const bar = html("div", "", "month-bar");
      bar.style.height = `${entry.value / maximum * 150}px`;
      if (entry.value === 0) bar.style.minHeight = "0";
      track.append(html("span", integer.format(entry.value), "month-count"), bar);
    } else {
      track.append(html("span", unavailable(entry), "month-hidden"), html("div", "", "withheld-slot"));
    }
    const label = html("span", "", "month-label");
    const [month, year] = monthLabel(entry.dimensions.group).split(" ");
    label.append(html("span", month), html("span", year, "month-year"));
    column.append(track, label);
    container.append(column);
  }
  $("#month-note").textContent = `Counts below ${report.suppression_policy.minimum_n} and related cells are withheld.`;
}

function renderLearning() {
  const cohort = $("#learning-cohort").value;
  const container = $("#learning-details");
  container.replaceChildren();
  for (const [skill, label] of skills) {
    const before = metric("agree_before", { skill }, cohort);
    const after = metric("agree_after", { skill }, cohort);
    const gap = metric("below_agree_after", { skill }, cohort);
    const gain = metric("agreement_gain", { skill }, cohort);
    const panel = html("article", "", "panel detail-card");
    panel.id = `outcome-${skill}`;
    panel.tabIndex = -1;
    const header = html("div", "", "detail-header");
    header.append(html("h2", label), html("span", Data.visibleShare(after) ? `${integer.format(after.n)} complete pairs` : unavailable(after)));
    const stats = html("dl", "", "detail-stats");
    for (const [title, entry, value, note] of [
      ["Recalled before", before, shareText(before), intervalText(before)],
      ["Current agreement", after, shareText(after), intervalText(after)],
      ["Change in agreement", gain, gainText(gain), "Percentage points"],
      ["Remaining gap", gap, shareText(gap), Data.visibleShare(gap) && Data.count(gap.numerator) ? `${integer.format(gap.numerator)} of ${integer.format(gap.denominator)} below Agree` : unavailable(gap)],
    ]) {
      const item = stat(title, value);
      if (!Data.released(entry)) item.querySelector("dd").classList.add("withheld-value");
      item.querySelector("dd").append(html("small", note));
      stats.append(item);
    }
    const details = html("details");
    details.append(html("summary", "See calculation bases & context"));
    const list = html("ul");
    for (const [title, entry] of [["Recalled before", before], ["Current", after]]) {
      list.append(html("li", Data.visibleShare(entry) && Data.count(entry.numerator)
        ? `${title}: ${integer.format(entry.numerator)} of ${integer.format(entry.denominator)} selected Agree or Strongly agree. ${intervalText(entry)}.`
        : `${title}: ${unavailable(entry)}.`));
    }
    const ceiling = metric("ceiling_share", { skill }, cohort);
    list.append(html("li", `Already at the highest rating before training: ${shareText(ceiling)} (${baseText(ceiling)}).`));
    details.append(list, html("p", "Both ratings were collected after training. Recall, response-shift bias, and the lack of a control group limit interpretation. A percentage-point change is not a percent increase."));
    const body = html("div", "", "detail-body");
    body.append(stats, movementRow(skill, "Individual rating changes", cohort));
    panel.append(header, body, details);
    container.append(panel);
  }
}

function makeTable(headings, rows, caption) {
  const wrap = html("div", "", "table-wrap");
  wrap.tabIndex = 0;
  wrap.setAttribute("role", "region");
  wrap.setAttribute("aria-label", caption);
  const table = html("table");
  table.append(html("caption", caption, "sr-only"));
  const head = html("thead");
  const headRow = html("tr");
  for (const text of headings) {
    const cell = html("th", text);
    cell.scope = "col";
    headRow.append(cell);
  }
  head.append(headRow);
  const body = html("tbody");
  for (const values of rows) {
    const row = html("tr");
    for (const [index, value] of values.entries()) {
      const cell = html(index === 0 ? "th" : "td");
      if (index === 0) cell.scope = "row";
      if (typeof value === "string") cell.textContent = value;
      else cell.append(value);
      row.append(cell);
    }
    body.append(row);
  }
  table.append(head, body);
  wrap.append(table);
  return wrap;
}

function renderCommunity() {
  const groupBy = $("#community-group").value;
  const skill = $("#community-skill").value;
  const container = $("#community-results");
  const groups = [...new Set(report.metrics.filter((entry) => entry.dimensions.cohort === "all_responses"
    && entry.dimensions.group_by === groupBy && entry.metric_id === "subgroup_agree_after"
    && entry.dimensions.skill === skill).map((entry) => entry.dimensions.group))].sort();
  container.replaceChildren();
  if (!groups.length) {
    container.append(empty("No group data", "Open a report with subgroup results."));
    return;
  }
  const rows = groups.map((group) => {
    const dimensions = { group_by: groupBy, group, skill };
    const before = metric("subgroup_agree_before", dimensions);
    const after = metric("subgroup_agree_after", dimensions);
    const gap = metric("subgroup_below_agree_after", dimensions);
    const gain = metric("subgroup_agreement_gain", dimensions);
    const current = html("span", shareText(after));
    if (Data.visibleShare(after)) current.append(html("small", intervalText(after)));
    return [groupBy === "training_month" ? monthLabel(group) : group, baseText(after), shareText(before), current, gainText(gain), shareText(gap)];
  });
  container.append(makeTable(["Group", "Complete pairs", "Before", "Current", "Change", "Remaining gap"], rows, "Unadjusted learning outcomes by selected community group"));
}

function renderCoverage() {
  const container = $("#calling-coverage");
  const entry = metric("calling_coverage", { group_by: "overall", group: "Overall" });
  container.replaceChildren();
  if (!Data.visibleShare(entry) || !Data.count(entry.numerator) || !Data.count(entry.denominator)) {
    container.append(html("p", `Calling-question coverage: ${unavailable(entry)}`, "chart-footnote"));
    return;
  }
  const content = html("div", "", "coverage-content");
  const track = html("div", "", "coverage-track");
  track.setAttribute("aria-hidden", "true");
  const fill = html("span");
  fill.style.width = `${entry.value * 100}%`;
  track.append(fill);
  content.append(html("strong", percent.format(entry.value), "number"), track,
    html("p", `${integer.format(entry.numerator)} of ${integer.format(entry.denominator)} eligible responses answered.`));
  container.append(content);
}

function renderFindings() {
  const container = $("#findings");
  container.replaceChildren();
  if (!report.findings.length) container.append(empty("No recommendations in this report"));
  for (const [index, finding] of report.findings.entries()) {
    const panel = html("article", "", "finding");
    panel.id = `finding-${index}`;
    panel.tabIndex = -1;
    if (!Data.safeFinding(finding, report.metrics)) {
      panel.append(html("h3", "Finding unavailable"), html("p", "Supporting evidence is unavailable or withheld."));
      container.append(panel);
      continue;
    }
    const header = html("div", "", "finding-top");
    header.append(html("h3", finding.observation), html("span", `${finding.confidence[0].toUpperCase() + finding.confidence.slice(1)} confidence`, "confidence-tag"));
    const action = html("div", "", "action-line");
    action.append(html("strong", "Recommendation"), html("span", finding.action));
    const details = html("details");
    details.append(html("summary", "Supporting evidence & limitations"));
    const list = html("ul");
    for (const ref of finding.metric_refs) {
      const entry = refMetric(ref);
      const label = skills.find(([skill]) => skill === ref.dimensions.skill)?.[1] || "Report metric";
      list.append(html("li", `${label}: ${entry.definition} ${metricText(entry)} (${baseText(entry)}).`));
    }
    details.append(list);
    for (const id of finding.caveat_ids) {
      const caveat = report.caveats.find((entry) => entry.id === id);
      if (caveat) details.append(html("p", `${caveat.label}: ${caveat.explanation}`));
    }
    panel.append(header, html("p", finding.interpretation), action, details);
    container.append(panel);
  }
}

function renderThemes() {
  const container = $("#themes");
  container.replaceChildren();
  if (report.theme_data.status !== "available" || !report.theme_data.questions.length) {
    container.append(empty("No coded themes in this report"));
    return;
  }
  for (const question of report.theme_data.questions) {
    const panel = html("article", "", "panel");
    const answered = refMetric(question.answered);
    panel.append(html("h3", question.label), html("p", Data.visibleCount(answered)
      ? `${countText(answered)} valid answers` : `Answer count ${unavailable(answered).toLowerCase()}`, "theme-base"));
    if (!question.themes.length) panel.append(html("p", "No coded themes supplied for this question.", "chart-footnote"));
    for (const theme of question.themes) {
      for (const ref of theme.prevalence) {
        const entry = refMetric(ref);
        const row = html("div", "", "theme-row");
        const label = html("div", "", "theme-label");
        label.append(html("strong", theme.label), html("span", shareText(entry), "number"));
        row.append(label);
        if (Data.visibleShare(entry)) {
          const track = html("div", "", "theme-track");
          track.setAttribute("aria-hidden", "true");
          const fill = html("span");
          fill.style.width = `${entry.value * 100}%`;
          track.append(fill);
          row.append(track, html("p", `${baseText(entry)} · ${theme.method === "embedding" ? "embedding" : "codebook"}`, "chart-footnote"));
        }
        panel.append(row);
      }
    }
    panel.append(html("p", "Shares of valid answers. Themes may overlap.", "chart-footnote"));
    container.append(panel);
  }
}

function renderThemePreview() {
  const container = $("#theme-preview");
  container.replaceChildren();
  const questions = report.theme_data.status === "available" ? report.theme_data.questions : [];
  let shown = 0;
  for (const question of questions) {
    for (const theme of question.themes) {
      if (shown >= 3) break;
      const entry = theme.prevalence.map(refMetric).find(Data.visibleShare);
      if (!entry) continue;
      const row = html("div", "", "preview-theme");
      const label = html("div", "", "theme-label");
      label.append(html("strong", theme.label), html("span", shareText(entry), "number"));
      const track = html("div", "", "theme-track");
      track.setAttribute("aria-hidden", "true");
      const fill = html("span");
      fill.style.width = `${entry.value * 100}%`;
      track.append(fill);
      row.append(label, html("p", `${question.label} · ${baseText(entry)}`), track);
      container.append(row);
      shown++;
    }
  }
  if (!shown) container.append(empty("No coded themes in this report"));
  else container.append(html("p", "Shares of valid answers. Themes may overlap.", "chart-footnote"));
}

function renderMethods() {
  const quality = $("#quality-summary");
  quality.replaceChildren();
  const labels = { usable_responses: "Usable response IDs", flagged_responses: "Responses flagged for review", invalid_training_dates: "Unparsed training dates" };
  for (const ref of report.quality_report.metrics) {
    const entry = refMetric(ref);
    quality.append(stat(labels[ref.metric_id] || entry.definition, metricText(entry)));
  }
  $("#quality-notes").replaceChildren(...report.quality_report.notes.map((note) => html("p", note, "quality-notes")));
  const privacy = html("p", `Groups below ${report.suppression_policy.minimum_n} are withheld. Complementary suppression can also hide larger cells to protect small groups. A withheld cell never means zero.`, "quality-notes");
  $("#quality-notes").append(privacy);
  $("#caveats").replaceChildren(...report.caveats.map((caveat) => {
    const node = html("article");
    node.append(html("h3", caveat.label), html("p", caveat.explanation));
    return node;
  }));
  const definitions = $("#definitions");
  definitions.replaceChildren();
  for (const [id, definition] of Object.entries(report.definitions)) {
    const node = html("details");
    node.append(html("summary", id.replaceAll("_", " ")), html("p", definition));
    definitions.append(node);
  }
  $("#provenance").textContent = `Report format ${report.schema_version}. Input fingerprint: ${report.input_hash || "not supplied"}.`;
}

function render(nextReport) {
  const previous = report;
  const liveMain = $("#main-content");
  const stagedMain = liveMain.cloneNode(true);
  report = nextReport;
  renderRoot = stagedMain;
  try {
    renderSummary();
    renderObjectives();
    renderFocus();
    $("#movement").replaceChildren(...skills.map(([skill, label]) => movementRow(skill, label, "all_responses", true)));
    renderMonths();
    $("#learning-cohort").value = "all_responses";
    $("#learning-cohort option[value=excluding_flagged]").disabled = !report.metrics.some((entry) => entry.dimensions.cohort === "excluding_flagged");
    renderLearning();
    renderCommunity();
    renderCoverage();
    renderFindings();
    renderThemes();
    renderThemePreview();
    renderMethods();
    const generated = new Date(report.generated_at);
    const time = html("time", dateFormat.format(generated));
    time.dateTime = generated.toISOString();
    $("#report-date").replaceChildren(html("span", "Report generated"), time);
    $("#draft-banner").hidden = report.data_kind !== "synthetic";
    $("#dashboard").hidden = false;
    $("#initial-state").hidden = true;
    $("#load-status").textContent = "";
  } catch (error) {
    report = previous;
    throw error;
  } finally {
    renderRoot = document;
  }
  liveMain.replaceWith(stagedMain);
  bindMainControls();
  $("#print-report").disabled = false;
  navigate(false, true);
}

async function load(readReport) {
  const current = ++requestNumber;
  const status = $("#load-status");
  status.classList.remove("error");
  status.textContent = "Opening the report…";
  try {
    const nextReport = Data.validate(await readReport());
    if (current !== requestNumber) return;
    render(nextReport);
    $("#load-status").textContent = "";
    const total = Data.find(report.metrics, "usable_responses");
    announce(`Report opened.${Data.visibleCount(total) ? ` ${countText(total)} survey responses.` : ""}${report.data_kind === "synthetic" ? " Fictional sample data." : ""}`);
  } catch {
    if (current !== requestNumber) return;
    status.classList.add("error");
    status.textContent = report
      ? "That file could not be opened as a valid aggregate report. Your current report is unchanged. Choose a version 1.0.0 report JSON to try again."
      : "Choose a version 1.0.0 aggregate report JSON using “Open report”. To explore the sample, serve the repository locally and reopen this page.";
    $("#initial-state").hidden = Boolean(report);
  }
}

$("#report-picker").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file) load(async () => JSON.parse(await file.text()));
  event.target.value = "";
});
$("#print-report").addEventListener("click", () => window.print());
$(".skip-link").addEventListener("click", (event) => {
  event.preventDefault();
  $("#main-content").focus();
  $("#main-content").scrollIntoView();
});
function bindMainControls() {
  $("#show-intervals").addEventListener("change", () => { if (report) setRoute({ intervals: $("#show-intervals").checked ? "" : "off" }); });
  for (const button of document.querySelectorAll("[data-chart]")) button.addEventListener("click", () => {
    if (!report || button.getAttribute("aria-pressed") === "true") return;
    setRoute({ chart: button.dataset.chart === "agreement" ? "" : "movement" });
    animateResult(button.dataset.chart === "agreement" ? $("#agreement-chart") : $("#rating-chart"));
  });
  $("#learning-cohort").addEventListener("change", () => { if (report) setRoute({ cohort: $("#learning-cohort").value === "all_responses" ? "" : $("#learning-cohort").value }); });
  for (const id of ["#community-group", "#community-skill"]) $(id).addEventListener("change", () => {
    if (report) setRoute({ group: $("#community-group").value, skill: $("#community-skill").value });
  });
}
bindMainControls();
$("#section-picker").addEventListener("change", () => { location.hash = rememberedRoutes[$("#section-picker").value] || `#${$("#section-picker").value}`; });
window.addEventListener("resize", positionIndicator);
window.addEventListener("hashchange", () => navigate(true));
navigate();
if (location.protocol === "file:") {
  $("#load-status").textContent = "Open an aggregate report JSON to get started. Files are read in this browser.";
  $("#initial-state").hidden = false;
} else {
  load(async () => {
    let response = await fetch("./report.json");
    if (response.status === 404) response = await fetch("../fixtures/report.sample.json");
    if (!response.ok) throw new Error("Report fetch failed");
    return response.json();
  });
}
