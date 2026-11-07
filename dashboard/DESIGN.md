# Training insights

EveryMind training staff need to compare participant learning, inspect its evidence,
and decide what to review with trainers. This is an analysis workspace.

## Direction

The user's Pacer Intelligence reference sets the visual direction: deep forest
surfaces, light sans-serif headings, compact monospace metadata, and fine square
panel borders. A spacious heading leads into the real comparison chart and a
narrower interpretation column. The chart carries the visual emphasis of this
analysis workspace. Reference-site claims and assets are not report content.

Use #101a14 as the page base, stepped forest panels, off-white text, and restrained
mint accents. Platform sans-serif is a license-free substitute for the reference's
display face; locally bundled Chivo Mono sets short technical labels and response bases.
Keep chart metadata at least 12px and use fluid display type, hairline dividers,
0–4px corners, and consistent content edges. Summary figures come from the report.
Keep text contrast, direct labels, and the synthetic-data notice legible on dark
surfaces. Printed reports use light surfaces and dark text.

## Composition and interaction

- The overview gives the chart most of the width and places the remaining gap beside it.
- Agreement and individual rating movement share one chart workspace.
- Keep agreement on a fixed 0–100% scale. Both series have exact values and response bases.
- The overview uses paired bars for agreement and stacked bars for rating movement. Each outcome card pairs a 2×2 metric grid on the left with a larger doughnut on the right, showing higher/unchanged/lower ratings with direct labels and response counts.
- Monthly response counts use bars. Withheld months have dashed slots without numeric height, and released zero counts stay at zero.
- Key numeric values have a quiet 1px frame, separated from their labels and calculation notes.
- Confidence intervals are optional, with their actual level shown. Detailed outcomes give numeric ranges.
- Objective and finding links land on the selected evidence. Cohort and community filters live in the URL; Back and reload restore them.
- Filter changes preserve control focus and announce the updated context.
- Mobile uses a native section menu and stacked comparisons. Tables scroll inside a labelled, keyboard-accessible region.

## Motion

Chart values and labels remain stable while the comparison is read.
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

- [Pacer Intelligence](https://pacer-intelligence.com/): the user's visual reference for the forest palette, technical typography, and panel system.
- [Chivo Mono](https://github.com/google/fonts/tree/main/ofl/chivomono): bundled variable font, with its SIL Open Font License in `assets/chivo-mono-OFL.txt`.
- [Apple chart guidance](https://developer.apple.com/design/human-interface-guidelines/charts): legible evidence, direct descriptions, accessible alternatives.
- [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines): semantics, focus, state in URLs, motion preferences, and resilient layouts.
- [Emil Kowalski](https://github.com/emilkowalski/skills): purposeful motion and immediate interaction feedback.
- [Awesome DESIGN.md](https://github.com/VoltAgent/awesome-design-md): Apple, Linear, and Mercury composition studies; adapted to an analysis tool.
- [Taste Skill](https://github.com/Leonxlnx/taste-skill) and [image-to-code](https://github.com/Leonxlnx/imagegen-skills): consistent visual direction, mockup-first implementation, and browser comparison.

Reference branding and assets are not included in the application.
