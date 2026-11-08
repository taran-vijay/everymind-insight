# Training insights

EveryMind training staff need to compare participant learning, inspect its evidence,
and decide what to review with trainers. This is an analysis workspace.

## Direction

The user's Pacer Intelligence reference sets the visual direction: deep forest
surfaces, light sans-serif headings, compact monospace metadata, and fine square
panel borders. A forest-video opening leads into one continuous report, from the
overview through outcomes, community comparisons, feedback, and methods.
Reference-site claims and assets are not report content.

Use #101a14 as the page base, stepped forest panels, off-white text, and restrained
mint accents. Locally bundled Inter sets the hero title and the five main report
headings, as requested by the user. The hero title stays on one line with fluid
type sizing. Platform sans-serif sets remaining prose and subheadings; locally
bundled Chivo Mono sets short technical labels and response bases.
Keep chart metadata at least 12px and use fluid display type, hairline dividers,
0–4px corners, and consistent content edges. Summary figures come from the report.
Keep text contrast, direct labels, and the synthetic-data notice legible on dark
surfaces. Printed reports use light surfaces and dark text.

## Composition and interaction

- The forest hero fills the opening viewport with only the title. Navigation begins below it and becomes sticky as the report scrolls. The hero scrolls away with the document; its lower-edge fade meets the page background without a hard edge.
- Navigation links scroll to report sections rather than replacing content. Scroll position updates the active link with `aria-current="location"`.
- The six main titles use title case. The outcomes heading shares a compact row with its cohort selector, with 24px before the first outcome card; the row stacks on phones.
- The overview gives the chart most of the width and places the remaining gap beside it.
- Agreement and individual rating movement share one chart workspace.
- Keep agreement on a fixed 0–100% scale. Both series have exact values and response bases.
- The overview uses paired bars for agreement and stacked bars for rating movement. Each outcome card pairs a 2×2 metric grid on the left with a larger doughnut on the right, showing higher/unchanged/lower ratings with direct labels and response counts.
- Monthly response counts use bars. Withheld months have dashed slots without numeric height, and released zero counts stay at zero.
- Key numeric values have a quiet 1px frame, separated from their labels and calculation notes.
- Available confidence intervals always appear, with their actual level shown. Detailed outcomes give numeric ranges.
- File selection and data options appear inside the Open report dialog, keeping the report workspace focused on results.
- Filtering uses four checkboxes and one report-opening action. The durations are fixed at under 30 seconds and over two hours; the other options are four-point drops and missing/invalid training dates. File selection is a separate collapsed disclosure. Counts and privacy messages stay visible; advanced rules, category controls, Reset, Undo, and export controls are absent from this dialog.
- Objective and finding links land on the selected evidence. Cohort and community filters live in the URL; Back and reload restore them.
- Filter changes preserve control focus and announce the updated context.
- Mobile uses a native section menu and stacked comparisons. Tables scroll inside a labelled, keyboard-accessible region.

## Motion

Bars grow from their baseline over 800ms and doughnut colours draw clockwise over
1000ms, accelerating from slow to fast with the standard ease-in curve. Charts
replay on entering the viewport after fully leaving it. A small threshold keeps
partially visible charts from repeatedly restarting. Numbers and labels remain
visible throughout. Chart reveals run automatically without a toggle or saved
on/off preference, following the user's explicit request for automatic fills.
Printing shows every chart in its completed form. Other interface transitions
continue to respect reduced motion.
Navigation uses a moving underline while every report section remains available.
Filter updates fade only the result, leaving controls immediate. Buttons respond
on press; internal links reveal a small directional cue.

The decorative forest video plays automatically whenever visible, as explicitly
requested by the user, and pauses offscreen or while the document is hidden.
It keeps its original colors, without brightness or saturation filters. The
desktop asset preserves the source's 4K resolution; a 1080p version serves narrow
screens. Only the lower edge fades into the page. A poster covers loading and
failed playback. Chart motion preferences remain independent of video playback.

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
- [Inter](https://github.com/google/fonts/tree/main/ofl/inter): bundled variable font, with its SIL Open Font License in `assets/inter-OFL.txt`.
- [Forest footage by Zulfugar Karimov](https://www.pexels.com/video/sunlight-streaming-through-forest-trees-38773226/): selected by the user, used under the Pexels License; source and asset details are recorded in `assets/forest-hero-LICENSE.md`.
- [Apple chart guidance](https://developer.apple.com/design/human-interface-guidelines/charts): legible evidence, direct descriptions, accessible alternatives.
- [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines): semantics, focus, state in URLs, motion preferences, and resilient layouts.
- [Emil Kowalski](https://github.com/emilkowalski/skills): purposeful motion and immediate interaction feedback.
- [Awesome DESIGN.md](https://github.com/VoltAgent/awesome-design-md): Apple, Linear, and Mercury composition studies; adapted to an analysis tool.
- [Taste Skill](https://github.com/Leonxlnx/taste-skill) and [image-to-code](https://github.com/Leonxlnx/imagegen-skills): consistent visual direction, mockup-first implementation, and browser comparison.

Pacer branding and footage are not included in the application.
