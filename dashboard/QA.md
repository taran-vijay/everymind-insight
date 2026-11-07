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

## Chart reveals — November 7, 2026

- Checked bar growth between scale 0 and 1, and clockwise coloured-ring reveals between dash offsets 100 and 0 in the browser.
- Completed charts retain their full shape after interval changes. Section changes reset reveals so charts replay on each return visit. Offscreen rings wait for visibility, and a different cohort gets its own reveal.
- Invalid imports keep the current report. Successful imports reset reveal eligibility, retain the motion preference, and generate distinct ring-mask IDs.
- The browser reports reduced motion enabled. With the default setting, charts show their final values. Explicitly enabling Animate charts allows the requested fills, and disabling it immediately completes all charts.
- All five sections fit at 320px, and the browser console has no warnings or errors during these checks.
- JavaScript syntax, 14 data-contract tests, and whitespace checks pass. Print completion was reviewed in source. A physical print and other browser engines were not tested.

## Continuous report and forest hero — November 7, 2026

- All five sections remain visible in one document. Header links and the mobile menu jump to the selected section; the active navigation label follows scrolling.
- The licensed forest clip loads at 1920×1080, scrolls away normally, and fades into the exact page background. The source and license are recorded with the assets.
- Native Play/Pause works, playback pauses when the hero leaves the viewport, and resumes on return when enabled. The browser's reduced-motion default shows the poster until Play is selected.
- Bars and rings return to their initial state after fully leaving the viewport and fill again on return. The slow-to-fast curve is preserved. Turning off Animate charts immediately completes all graphics.
- Cohort and community selections remain independent while navigating the page. Filter updates preserve the scroll position. All and excluding-flagged cohorts show their expected 450 and 423 paired-response bases.
- Successful sample imports preserve the page structure and rebind controls. Invalid imports retain the current report, filters, summary, and sample notice.
- No page overflow at effective 320px and 390px widths. The narrow hero and desktop hero/report transition were inspected visually. Mobile outcome positions were checked in the DOM; narrow viewport screenshots of scrolled content were unreliable in this browser session.
- The browser console is empty. Screenshot: `outputs/everymind-forest-scroll.jpg` in the chat workspace. Viewport override was reset after verification.
- JavaScript syntax, 14 data-contract tests, and whitespace checks pass. Print and video-error fallback were reviewed in source; other browser engines and physical printing were not tested.

## Full-screen natural-color opening — November 7, 2026

- The opening hero matches the viewport height at desktop, 390px, and 320px widths. Only the forest and title are visible; the navigation begins immediately below it and becomes sticky when scrolling.
- Desktop playback selects the 3840×2160 source; phones select the 1920×1080 source. The computed video filter is `none`. Both versions preserve the source's colors, and only the lower edge receives a fade into the page.
- The video starts without a button, pauses after scrolling offscreen, and resumes on return. This follows the user's explicit autoplay request independently of the chart motion setting.
- Home navigation and reload place the hero at scroll position zero. Page overflow is zero at the checked widths. Report anchors and the five-section continuous layout still work.
- Browser console is empty. Screenshot: `outputs/everymind-fullscreen-forest.jpg` in the chat workspace. The viewport override was reset.
- JavaScript syntax, 14 data-contract tests, and whitespace checks pass. No changes were pushed or merged.

## Inter titles — November 7, 2026

- All six requested title elements resolve to the locally bundled Inter font.
- Training insights stays on one line at desktop and 320px widths. At 320px its rendered height matches one line and page overflow is zero.
- Browser console is empty; the viewport override was reset. Preview saved as `outputs/everymind-inter-titles.jpg` in the chat workspace.
- This change affects font assets, heading styles, font preload, and documentation. Whitespace checks pass; data and application logic were not changed.

## Title case and outcomes spacing — November 7, 2026

- Confirmed title case on all six requested titles. The outcomes heading and cohort control now share a row, leaving a measured 24px gap before the first card on desktop.
- The cohort control still switches between the expected 450 and 423 paired-response bases. Browser console is empty and page overflow is zero.
- Preview saved as `outputs/everymind-title-case-spacing.jpg` in the chat workspace. Whitespace checks pass; application and data logic were not changed.
