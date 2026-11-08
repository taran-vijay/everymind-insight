"use strict";

// Anchor navigation restores the requested section, including the opening hero.
// Prevent the browser's later scroll restoration from overriding that position.
if ("scrollRestoration" in history) history.scrollRestoration = "manual";

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
const chartGrowthEasing = getComputedStyle(document.documentElement).getPropertyValue("--ease-in").trim() || "ease-in";
let renderRoot = document;
const $ = (selector) => renderRoot.querySelector(selector);
$('#download-report').hidden = true;
let report = null;
let reportDownloadURL = null;
let requestNumber = 0;
const rememberedRoutes = {};
const renderedRoutes = {};
let ringRevealId = 0;
const reducedChartMotion = matchMedia("(prefers-reduced-motion: reduce)");
const revealedCharts = new Set();
const chartAnimations = new Map();
const chartObserver = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (!entry.target.isConnected) continue;
    // Reset only after the graphic has fully left the viewport. A partial exit
    // must not interrupt a chart someone is still reading.
    if (!entry.isIntersecting) {
      resetChart(entry.target);
      continue;
    }
    if (entry.intersectionRatio >= .15 && entry.target.isConnected && entry.target.getClientRects().length
      && entry.target.dataset.chartState === "pending") {
      revealChart(entry.target);
    }
  }
}, { threshold: [0, .15] }) : null;

function chartGraphic(node, key, kind) {
  node.dataset.chartReveal = key;
  node.dataset.chartKind = kind;
  return node;
}
function finishChartAnimations() {
  for (const [node, animations] of chartAnimations) {
    node.dataset.chartState = "complete";
    for (const animation of animations) animation.cancel();
  }
  chartAnimations.clear();
}
function resetChart(node) {
  for (const animation of chartAnimations.get(node) || []) animation.cancel();
  chartAnimations.delete(node);
  revealedCharts.delete(node.dataset.chartReveal);
  node.dataset.chartState = "pending";
}
function revealChart(node) {
  revealedCharts.add(node.dataset.chartReveal);
  node.dataset.chartState = "playing";
  const options = { duration: 800, easing: chartGrowthEasing, fill: "both" };
  let animations;
  if (node.dataset.chartKind === "comparison") {
    animations = [...node.querySelectorAll(".bar-mark")].map((bar) => bar.animate(
      [{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], options));
    animations.push(...[...node.querySelectorAll(".whisker")].map((whisker) => whisker.animate(
      [{ opacity: 0 }, { opacity: 0, offset: .75 }, { opacity: 1 }], options)));
  } else if (node.dataset.chartKind === "ring") {
    animations = [node.querySelector(".ring-reveal").animate(
      [{ strokeDashoffset: 100 }, { strokeDashoffset: 0 }], { ...options, duration: 1000 })];
  } else {
    const axis = node.dataset.chartKind === "vertical" ? "Y" : "X";
    animations = [node.querySelector(".chart-fill").animate(
      [{ transform: `scale${axis}(0)` }, { transform: `scale${axis}(1)` }], options)];
  }
  chartAnimations.set(node, animations);
  const complete = () => {
    if (animations.every((animation) => animation.playState === "finished")) {
      node.dataset.chartState = "complete";
      for (const animation of animations) animation.cancel();
      chartAnimations.delete(node);
    }
  };
  for (const animation of animations) animation.onfinish = complete;
  complete();
}
function watchCharts(reset = false) {
  chartObserver?.disconnect();
  finishChartAnimations();
  if (reset) revealedCharts.clear();
  document.documentElement.dataset.chartMotion = "on";
  for (const node of document.querySelectorAll("[data-chart-reveal]")) {
    const key = node.dataset.chartReveal;
    if (!chartObserver || revealedCharts.has(key)) {
      node.dataset.chartState = "complete";
      revealedCharts.add(key);
    } else {
      node.dataset.chartState = "pending";
    }
    chartObserver?.observe(node);
  }
}
function completeCharts() {
  chartObserver?.disconnect();
  finishChartAnimations();
  for (const node of document.querySelectorAll("[data-chart-reveal]")) {
    node.dataset.chartState = "complete";
    revealedCharts.add(node.dataset.chartReveal);
  }
}
window.addEventListener("beforeprint", completeCharts);
window.addEventListener("afterprint", () => watchCharts());

function route() {
  const [requested, query = ""] = location.hash.slice(1).split("?");
  return { view: Object.hasOwn(views, requested) ? requested : "overview", params: new URLSearchParams(query) };
}
function destination(view, values = {}) {
  const query = new URLSearchParams(Object.entries(values).filter(([, value]) => value));
  return `#${view}${query.size ? `?${query}` : ""}`;
}
function setRoute(view, values) {
  const current = { view, params: new URLSearchParams((rememberedRoutes[view] || "").split("?")[1] || "") };
  for (const [key, value] of Object.entries(values)) {
    if (value) current.params.set(key, value);
    else current.params.delete(key);
  }
  history.pushState(null, "", destination(current.view, Object.fromEntries(current.params)));
  // Filters update their own section without scrolling or resetting other charts.
  navigate();
}
function animateResult(node) {
  if (reducedChartMotion.matches) return;
  for (const animation of node.getAnimations()) animation.cancel();
  node.animate([{ opacity: .72 }, { opacity: 1 }], { duration: 180, easing: motionEasing });
}
function announce(text) { $("#interaction-status").textContent = text; }
function positionIndicator() {
  const selected = document.querySelector('nav a[aria-current="location"]');
  const indicator = document.querySelector("#nav-indicator");
  if (!selected || !indicator) return;
  const width = selected.offsetWidth;
  const left = selected.offsetLeft;
  indicator.style.transform = `translateX(${left}px) scaleX(${width})`;
}

function selectSection(view) {
  $("#section-picker").value = view;
  for (const node of document.querySelectorAll("nav [data-view]")) {
    node.href = rememberedRoutes[node.dataset.view] || `#${node.dataset.view}`;
    if (node.dataset.view === view) node.setAttribute("aria-current", "location");
    else node.removeAttribute("aria-current");
  }
  positionIndicator();
}

let scrollFrame = 0;
function updateScrollSection() {
  scrollFrame = 0;
  if (!report) return;
  const line = document.querySelector(".site-header").getBoundingClientRect().bottom + 120;
  let current = "overview";
  for (const view of Object.keys(views)) {
    if (document.getElementById(`view-${view}`).getBoundingClientRect().top <= line) current = view;
  }
  selectSection(current);
}
window.addEventListener("scroll", () => {
  if (!scrollFrame) scrollFrame = requestAnimationFrame(updateScrollSection);
}, { passive: true });

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
  if (view === "overview" && params.has("intervals")) {
    params.delete("intervals");
    history.replaceState(null, "", destination(view, Object.fromEntries(params)));
  }
  if (report && view === "learning" && params.has("cohort")
    && (params.get("cohort") !== "excluding_flagged" || $("#learning-cohort option[value=excluding_flagged]").disabled)) {
    params.delete("cohort");
    history.replaceState(null, "", destination(view, Object.fromEntries(params)));
  }
  if (location.hash !== "#home") rememberedRoutes[view] = destination(view, Object.fromEntries(params));
  const updated = [];
  if (report) {
    for (const section of ["overview", "learning", "community"]) {
      const saved = rememberedRoutes[section] || `#${section}`;
      if (!initial && renderedRoutes[section] === saved) continue;
      const settings = new URLSearchParams(saved.split("?")[1] || "");
      if (section === "overview") {
        const movement = settings.get("chart") === "movement";
        $("#agreement-chart").hidden = movement;
        $("#rating-chart").hidden = !movement;
        for (const button of document.querySelectorAll("[data-chart]")) button.setAttribute("aria-pressed", String(button.dataset.chart === (movement ? "movement" : "agreement")));
        $("#chart-description").textContent = movement ? "Change in paired ratings" : "Agree or Strongly agree";
        renderObjectives();
      } else if (section === "learning") {
        const filtered = settings.get("cohort") === "excluding_flagged" && !$("#learning-cohort option[value=excluding_flagged]").disabled;
        $("#learning-cohort").value = filtered ? "excluding_flagged" : "all_responses";
        renderLearning();
      } else if (section === "community") {
        const group = settings.get("group");
        $("#community-group").value = ["county", "role", "language", "training_month"].includes(group) ? group : "county";
        $("#community-skill").value = skills.some(([id]) => id === settings.get("skill")) ? settings.get("skill") : skills[0][0];
        renderCommunity();
      }
      renderedRoutes[section] = saved;
      updated.push(section);
    }
  }
  const target = report && (view === "learning" ? document.getElementById(`outcome-${params.get("skill")}`) : view === "feedback" ? document.getElementById(`finding-${params.get("finding")}`) : null);
  if (focus || (initial && location.hash)) {
    const anchor = location.hash === "#home" ? $("#home") : target || $(view === "overview" ? "#main-content" : `#view-${view}`);
    if (focus) anchor.focus({ preventScroll: true });
    anchor.scrollIntoView({ block: "start", behavior: "instant" });
  }
  if (!initial && updated.includes(view)) {
    if (view === "learning" || view === "community") animateResult($(view === "learning" ? "#learning-details" : "#community-results"));
    if (view === "learning") announce(`Learning outcomes updated. ${$("#learning-cohort").selectedOptions[0].textContent}.`);
    if (view === "community") announce(`Community comparison updated. ${$("#community-skill").selectedOptions[0].textContent}, by ${$("#community-group").selectedOptions[0].textContent.toLowerCase()}.`);
    if (view === "overview") announce(params.get("chart") === "movement" ? "Rating movement chart." : "Agreement chart with available confidence intervals.");
  }
  selectSection(view);
  updateFilterNotices();
  if (initial || updated.length) watchCharts(initial);
  updateScrollSection();
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

function comparisonPlot(before, after) {
  const plot = svg("svg", { viewBox: "0 0 300 64", preserveAspectRatio: "none", "aria-hidden": "true" }, "plot");
  const x = (value) => 7 + value * 286;
  const line = (x1, y1, x2, y2, className) => plot.append(svg("line", { x1, y1, x2, y2, "vector-effect": "non-scaling-stroke" }, className));
  for (const tick of [0, .25, .5, .75, 1]) line(x(tick), 0, x(tick), 64, "gridline");
  for (const [entry, y, series] of [[before, 19, "before"], [after, 45, "after"]]) {
    if (!Data.visibleShare(entry)) continue;
    plot.append(svg("rect", { x: x(0), y: y - 5, width: entry.value * 286, height: 10, rx: 1 }, `${series} bar-mark`));
    const ci = Data.interval(entry);
    if (ci) {
      line(x(ci.lower), y, x(ci.upper), y, `${series} whisker`);
      line(x(ci.lower), y - 4, x(ci.lower), y + 4, `${series} whisker`);
      line(x(ci.upper), y - 4, x(ci.upper), y + 4, `${series} whisker`);
    }
  }
  return plot;
}

function renderObjectives() {
  const container = $("#objectives");
  container.replaceChildren();
  const intervals = skills.flatMap(([skill]) => [metric("agree_before", { skill }), metric("agree_after", { skill })]).map(Data.interval).filter(Boolean);
  const levels = [...new Set(intervals.map((ci) => percent.format(ci.level)))];
  $("#interval-explanation").textContent = levels.length === 1 ? `${levels[0]} confidence intervals` : "Confidence levels in Outcomes";
  $("#interval-explanation").hidden = !intervals.length;
  for (const [skill, label] of skills) {
    const before = metric("agree_before", { skill });
    const after = metric("agree_after", { skill });
    const gain = metric("agreement_gain", { skill });
    const row = html("div", "", "comparison-row");
    const name = html("div", "", "objective-name");
    const objectiveLink = link(label, destination("learning", { skill }));
    objectiveLink.className = "objective-link";
    name.append(objectiveLink, html("small", `${shareText(before)} before · ${baseText(after)}`));
    const chart = html("div", "", "comparison-plot");
    chart.append(chartGraphic(comparisonPlot(before, after), `agreement:${skill}`, "comparison"));
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
  action.append(html("h3", finding ? (report.release_metadata ? "Recommendation draft" : "Recommendation") : "Review"),
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
    const movements = ["up", "same", "down"].map((direction) => metric(`movement_${direction}`, { skill }, cohort));
    const anySuppressed = movements.some((entry) => entry?.suppressed);
    const comparisonProtected = movements.some((entry) => entry?.reason === "filter_comparison_protection");
    const status = anySuppressed ? "Withheld" : "Unavailable";
    const explanation = anySuppressed
      ? comparisonProtected ? "Withheld to protect small groups when comparing this view with the full report." : "Withheld to protect small groups."
      : "Not enough released data to show rating changes.";
    if (asBars) row.append(html("p", explanation, "unavailable"));
    else {
      // Keep the chart space stable without drawing or inferring protected segments.
      const distribution = html("div", "", "movement-distribution");
      const graphic = svg("svg", { viewBox: "0 0 104 104", "aria-hidden": "true" }, "movement-ring movement-placeholder");
      graphic.append(svg("circle", { cx: 52, cy: 52, r: 42 }, "ring-track"));
      const text = svg("text", { x: 52, y: 55, "text-anchor": "middle" }, "ring-base");
      text.textContent = status;graphic.append(text);
      distribution.append(graphic, html("p", explanation, "unavailable"));row.append(distribution);
    }
    return row;
  }
  const distribution = html("div", "", asBars ? "movement-bar-distribution" : "movement-distribution");
  const graphic = asBars ? html("div", "", "stacked-bar")
    : svg("svg", { viewBox: "0 0 104 104" }, "movement-ring");
  const animationKey = `movement:${asBars ? "overview" : "outcomes"}:${cohort}:${skill}`;
  if (asBars) {
    chartGraphic(distribution, animationKey, "horizontal");
    graphic.classList.add("chart-fill");
  } else chartGraphic(graphic, animationKey, "ring");
  graphic.setAttribute("aria-hidden", "true");
  if (asBars) header.append(html("span", `n=${integer.format(entries[0].n)}`));
  else graphic.append(svg("circle", { cx: 52, cy: 52, r: 42 }, "ring-track"));
  let segments = graphic;
  if (!asBars) {
    const maskId = `ring-reveal-${++ringRevealId}`;
    const defs = svg("defs", {});
    const mask = svg("mask", { id: maskId, maskUnits: "userSpaceOnUse", x: 0, y: 0, width: 104, height: 104 });
    mask.append(svg("circle", { cx: 52, cy: 52, r: 42, pathLength: 100, transform: "rotate(-90 52 52)" }, "ring-reveal"));
    defs.append(mask);
    segments = svg("g", { mask: `url(#${maskId})` }, "ring-colors");
    graphic.append(defs, segments);
  }
  const values = html("div", "", "movement-values");
  let offset = 0;
  entries.forEach((entry, index) => {
    const direction = ["up", "same", "down"][index];
    if (asBars) {
      const segment = html("span", "", direction);
      segment.style.flex = `${entry.value} 1 0%`;
      graphic.append(segment);
    } else segments.append(svg("circle", { cx: 52, cy: 52, r: 42, pathLength: 100,
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
      bar.classList.add("chart-fill");
      if (entry.value > 0) chartGraphic(track, `month:${entry.dimensions.group}`, "vertical");
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
  const fill = html("span", "", "chart-fill");
  fill.style.width = `${entry.value * 100}%`;
  if (entry.value > 0) chartGraphic(track, "calling-coverage", "horizontal");
  track.append(fill);
  content.append(html("strong", percent.format(entry.value), "number"), track,
    html("p", `${integer.format(entry.numerator)} of ${integer.format(entry.denominator)} eligible responses answered.`));
  const intent = metric("calling_intent_mean", { group_by: "overall", group: "Overall" });
  if (Data.released(intent)) {
    content.append(html("p", `Mean stated willingness: ${decimal.format(intent.value)} out of 10, among ${integer.format(intent.n)} valid answers. This does not measure actual calls.`));
  }
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
    action.append(html("strong", report.release_metadata ? "Recommendation draft" : "Recommendation"), html("span", finding.action));
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
      ? `${countText(answered)} ${report.release_metadata ? "nonblank" : "valid"} answers` : `Answer count ${unavailable(answered).toLowerCase()}`, "theme-base"));
    for (const ref of question.diagnostics || []) {
      const diagnostic = refMetric(ref);
      panel.append(html("p", `${diagnostic.definition} ${metricText(diagnostic)}.`, "chart-footnote"));
    }
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
          const fill = html("span", "", "chart-fill");
          fill.style.width = `${entry.value * 100}%`;
          if (entry.value > 0) chartGraphic(track, `theme:feedback:${Data.key(entry.metric_id, entry.dimensions)}`, "horizontal");
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
      const fill = html("span", "", "chart-fill");
      fill.style.width = `${entry.value * 100}%`;
      if (entry.value > 0) chartGraphic(track, `theme:overview:${Data.key(entry.metric_id, entry.dimensions)}`, "horizontal");
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
    $("#report-kind").textContent = report.data_kind === "synthetic" ? "SYNTHETIC DEMO — illustrative values" : "SURVEY REPORT — calculated from survey responses";
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
  if (reportDownloadURL) URL.revokeObjectURL(reportDownloadURL);
  reportDownloadURL = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
  $("#download-report").href = reportDownloadURL;
  $("#download-report").hidden = false;
  bindMainControls();
  $("#print-report").disabled = false;
  navigate(false, true);
}

async function load(readReport, { rowSource = false } = {}) {
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
    window.EveryMindDataOptions?.reportOpened(report, rowSource);
    return true;
  } catch {
    if (current !== requestNumber) return;
    status.classList.add("error");
    status.textContent = report
      ? "That file could not be opened as a valid aggregate report. Your current report is unchanged. Choose a version 1.0.0 report JSON to try again."
      : "Choose a version 1.0.0 aggregate report JSON using “Open report”, or explicitly select “Load synthetic demo”. No demo was substituted.";
    $("#initial-state").hidden = Boolean(report);
    return false;
  }
}

function updateFilterNotices() {
  const banner = report?.filter_provenance?.banner || "";
  const global = document.querySelector('#filtered-banner');
  global.textContent = banner;
  global.hidden = !banner;
  const targets = new Set([...document.querySelectorAll('#agreement-chart, #rating-chart, #theme-preview, #training-months, #learning-details article, #community-results, #calling-coverage, #themes article, #findings article')].map(n => n.id === 'training-months' ? n.closest('section') : n));
  for (const node of targets) {
    let notice = node.querySelector(':scope > [data-filter-notice]');
    if (!banner) { notice?.remove(); continue; }
    if (!notice) { notice = html('p','','filter-notice'); notice.dataset.filterNotice = ''; node.prepend(notice); }
    notice.textContent = banner;
  }
}
function openSyntheticDemo() { load(async () => {
  let response = await fetch("./report.synthetic.json");
  if (response.status === 404) response = await fetch("../fixtures/report.sample.json");
  if (!response.ok) throw new Error("Demo unavailable");
  const demo = await response.json();
  if (demo.data_kind !== "synthetic") throw new Error("Demo must be synthetic");
  return demo;
}); }
$("#print-report").addEventListener("click", () => window.print());
$(".skip-link").addEventListener("click", (event) => {
  event.preventDefault();
  $("#main-content").focus();
  $("#main-content").scrollIntoView();
});
function bindMainControls() {
  $("#load-demo").addEventListener("click", openSyntheticDemo);
  for (const button of document.querySelectorAll("[data-chart]")) button.addEventListener("click", () => {
    if (!report || button.getAttribute("aria-pressed") === "true") return;
    setRoute("overview", { chart: button.dataset.chart === "agreement" ? "" : "movement" });
    animateResult(button.dataset.chart === "agreement" ? $("#agreement-chart") : $("#rating-chart"));
  });
  $("#learning-cohort").addEventListener("change", () => { if (report) setRoute("learning", { cohort: $("#learning-cohort").value === "all_responses" ? "" : $("#learning-cohort").value }); });
  for (const id of ["#community-group", "#community-skill"]) $(id).addEventListener("change", () => {
    if (report) setRoute("community", { group: $("#community-group").value, skill: $("#community-skill").value });
  });
}
bindMainControls();
function jumpTo(hash) {
  if (location.hash !== hash) history.pushState(null, "", hash);
  navigate(true);
}
document.addEventListener("click", (event) => {
  const anchor = event.target.closest("a[href^='#']");
  if (!anchor || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const hash = anchor.getAttribute("href");
  if (!/^#(?:home|overview|learning|community|feedback|methods)(?:\?|$)/.test(hash)) return;
  event.preventDefault();
  jumpTo(hash);
});
$("#section-picker").addEventListener("change", () => jumpTo(rememberedRoutes[$("#section-picker").value] || `#${$("#section-picker").value}`));
window.addEventListener("resize", updateScrollSection);
window.addEventListener("hashchange", () => navigate(true));
window.addEventListener("popstate", () => navigate(true));

const heroVideo = document.querySelector("#hero-video");
let heroVisible = false;
function updateHeroPlayback() {
  // The requested decorative loop follows visibility independently of chart motion.
  // Keep the poster if the browser blocks playback or the media cannot load.
  if (heroVisible && !document.hidden) heroVideo.play().catch(() => {});
  else heroVideo.pause();
}
if ("IntersectionObserver" in window) {
  new IntersectionObserver(([entry]) => {
    heroVisible = entry.isIntersecting;
    updateHeroPlayback();
  }).observe(heroVideo);
} else { heroVisible = true; updateHeroPlayback(); }
document.addEventListener("visibilitychange", updateHeroPlayback);
navigate();
window.EveryMindReport = { load, current: () => report };
window.everymindBackendReady = (async () => {
  if (location.protocol === 'file:') return null;
  try { const response = await fetch('./api/fields'); return response.ok ? await response.json() : null; }
  catch { return null; }
})();
if (location.protocol === "file:") {
  $("#load-status").textContent = "Open an aggregate report JSON to get started. Files are read in this browser.";
  $("#initial-state").hidden = false;
} else {
  window.everymindBackendReady.then((backend) => {
    if (backend) {
      $('#load-status').textContent = 'Choose Open report to review data options. Nothing is excluded by default.';
      $('#initial-state').hidden = true;
      return;
    }
    return load(async () => {
    let response = await fetch("./report.json");
    if (!response.ok) throw new Error("Report fetch failed");
    return response.json();
    });
  });
}
