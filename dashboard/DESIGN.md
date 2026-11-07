# Training insights

EveryMind training staff need to compare participant learning, inspect its evidence,
and decide what to review with trainers. This is an analysis workspace.

## Direction

The compact mockup is the visual reference: one horizontal navigation bar, a modest
page heading, a dominant comparison chart, and a narrower interpretation column.
The editorial alternative informs only the wordmark and warmer palette. Generated
mockup numbers, quotes, and extra charts are never a source of report data.

Use white, pine green, and warm gray. Platform sans-serif carries the interface;
Georgia gives the wordmark a quiet editorial character. Headings are 22–36px,
body copy 14–16px, and chart metadata at least 12px. Use a single 6–8px corner system,
hairline dividers, and consistent content edges. Avoid oversized marketing headings,
repeated KPI cards, decorative status dots, and nested chart containers.

## Composition and interaction

- The overview gives the chart most of the width and places the remaining gap beside it.
- Agreement and individual rating movement share one chart workspace.
- Keep agreement on a fixed 0–100% scale. Both series have exact values and response bases.
- Confidence intervals are optional, with their actual level shown. Detailed outcomes give numeric ranges.
- Objective and finding links land on the selected evidence. Cohort and community filters live in the URL; Back and reload restore them.
- Filter changes preserve control focus and announce the updated context.
- Mobile uses a native section menu and stacked comparisons. Tables scroll inside a labelled, keyboard-accessible region.

## Motion

Chart bars enter once when the comparison first opens. Labels remain stable.
Navigation uses a moving underline and a short, interruptible section transition.
Filter updates fade only the result, leaving controls immediate. Buttons respond
on press; internal links reveal a small directional cue. No repeating animation,
auto-changing chart, number counter, parallax, or scroll-triggered data replay.

Use transform and opacity for motion. Respect reduced motion in both CSS and the
Web Animations API, plus increased contrast and reduced transparency preferences.

## Data boundaries

The sample notice remains visible for synthetic reports. Preserve exact metric
references, cohort boundaries, suppression, response bases, and retrospective-rating
limitations. Findings and actions are report-supplied and hidden if supporting
metrics are unavailable or withheld. Never reconstruct suppressed values, invent
participant quotes, or send selected files to a service.

Validate metadata, provenance, and references before rendering. Build the next
report in a detached DOM tree so a rendering failure preserves the current report.

## References

- [Apple chart guidance](https://developer.apple.com/design/human-interface-guidelines/charts): legible evidence, direct descriptions, accessible alternatives.
- [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines): semantics, focus, state in URLs, motion preferences, and resilient layouts.
- [Emil Kowalski](https://github.com/emilkowalski/skills): purposeful motion and immediate interaction feedback.
- [Awesome DESIGN.md](https://github.com/VoltAgent/awesome-design-md): Apple, Linear, and Mercury composition studies; adapted to an analysis tool.
- [Taste Skill](https://github.com/Leonxlnx/taste-skill) and [image-to-code](https://github.com/Leonxlnx/imagegen-skills): consistent visual direction, mockup-first implementation, and browser comparison.

Reference branding and assets are not included in the application.
