# Dashboard verification — November 6, 2026

## Automated checks

- `node --check dashboard/app.js`: passed.
- `node --test tests/dashboard.test.cjs`: 14 passed.
- `.venv/bin/python -m pytest -q tests --survey-workbook=…`: 52 passed using the supplied workbook.
- `git diff --check`: passed.

The browser validator also accepts the sample after a Pydantic deserialize/serialize
round trip (299 metrics). Regression tests cover malformed metadata, mixed source
fingerprints, broken references, and suppressed numeric values.

## Browser checks

Checked in the in-app Chromium browser:

- All five report sections at 320px and 1024px: no horizontal page overflow.
- Overview at 390px, 768px, and 1440px: chart labels, shared percentage axis,
  interpretation, and supporting charts inspected.
- All six sample months fit at 390px; withheld months have nonnumeric dashed slots.
- Agreement/movement controls work by mouse and keyboard; exact labels remain stable.
- Hiding confidence intervals removes whiskers; reload restores that choice from the URL.
- Skip link moves focus to main content without changing the active report section.
- Objective drill-down focuses the selected article below the sticky header.
- Cohort changes preserve control focus; Back restores the previous cohort and values.
- An unavailable filtered cohort disables its option and removes the stale URL parameter.
- Community filters update the URL; a test bundle shows a released group and a fully withheld group.
- Missing subgroup outcomes display an explicit empty state.
- A withheld supporting metric hides the associated finding and action.
- Invalid suppressed metrics and malformed timestamp objects are rejected; the current report and sample notice remain intact.
- Repeated successful imports rebind controls and announce completion.
- Very long, unbroken report labels in overview, feedback, and methods stay within the 320px layout.
- Browser console: no warnings or errors during these checks.

Reduced motion guards, transform/opacity animation, live regions, semantic controls,
focus treatment, contrast, and report text handling received a source review against
Vercel's Web Interface Guidelines. OS preference toggles and a separate screen-reader
application were not exercised. Other browser engines were not run.

Test bundles are synthetic temporary files outside the repository. The workbook
was used by local tests and is not included in this commit.
