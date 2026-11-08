# backend-fixes validation record

## Scope and branch

Started from current master `0da70d355e7ab12f6e530b98995cd14cc0473edc` in a separate worktree. No other branch's implementation was copied. Original master files and branch ref remain unchanged. The user authorized commits only on `backend-fixes`; no push, merge, rebase, PR or publication was performed.

No optimization/efficiency suggestions were implemented. Original videos, poster, fonts, styles, animations and statistical calculation modules are byte-for-byte unchanged from the base. Runtime dependency ranges are unchanged; there is no lockfile, result cache, frontend metric map or performance refactor.

## Automated checks

On macOS ARM / Python 3.11.18:

- **70 Python tests passed** with the original supplied reference workbook; no workbook tests were skipped in this run.
- **16 frontend data-contract tests passed** with Node.js.
- `git diff --check`, shell syntax checks and JavaScript syntax checks passed.
- Workflow YAML parsed successfully. Publication is `workflow_dispatch` only, requires an explicit boolean confirmation, and is restricted to `refs/heads/master`. It was not executed against GitHub.

New tests cover actual CSV/XLSX ingestion through the complete bundle; known numerator/denominator/interval values; source-byte preservation; newly appended responses updating the full report; private sentinel exclusion; small counts and nested cohorts; unavailable optional questions; required-schema failure preserving prior outputs; deterministic evidence; findings supported only by released metrics; release-metadata tampering; comment-topic ambiguity and unmatched answers; correct private comment locators after blank Excel rows/CSV records; no accidental demo substitution or overwrite; runtime-only site packaging; and loopback-server rejection of audits, repository files and traversal requests.

## Supplied workbook

The actual export produces 1,299 usable IDs. Current agreement among complete pairs is 1,168/1,299 (89.9%) for identifying crises, 1,175/1,299 (90.5%) for describing 988, and 1,199/1,299 (92.3%) for knowing when to use 988. These overall charts remain visible. Both quality cohorts are available where protected comparisons permit. Calling coverage is 293/1,299 (22.6%). Nonblank comment bases are 1,063 valuable-learning answers and 651 improvement answers.

The release contains 386 selected metric entries, including withheld entries, and three evidence-linked recommendation drafts. Broad private Phase 3 diagnostics are not concatenated blindly into the public bundle. Unknown source labels, raw respondent text, IDs, exact training dates, transitions, models and diagnostic tests are not exported. The real report and private audit remain in ignored `reports/`; neither is committed.

## Local browser and launcher checks

Using the current master design and a local-only server:

- Actual report loads as **SURVEY REPORT**, with the correct 1,299 base, overall percentages, intervals, movement and remaining gap.
- The cohort selector changes learning outcomes to 947 unflagged complete pairs. Community tables retain appropriate withheld states. Calling intent is distinguished from coverage and actual calls.
- Topics show fixed labels, denominators and coding diagnostics. Recommendations are labeled drafts for staff review.
- Explicit synthetic-demo loading changes the label and sample base to 450. Selecting the real report returns to the 1,299 survey base.
- Invalid JSON shows an error and preserves the current survey.
- Download report JSON produces a file equal to the selected bundle; the downloaded file passes backend release validation.
- The report-file controls wrap using the existing responsive design. A local review screenshot is saved under ignored `reports/`.

Browser checking caught a newly added demo button losing its event binding when the report's main content was replaced. Binding it with the other main-content controls corrected the error; switching modes and opening the real file then succeeded.

A clean first-launch test initially exposed a managed-Python symlink issue: a copied interpreter could not locate its standard library. The bootstrap now resolves the base interpreter before creating the virtual environment. The actual shell launcher then installed dependencies in a disposable clean copy, reached the mode menu and exited successfully. No survey was sent to a package service.

## Limits and remaining review

Native Windows/Linux double-click behavior and the remote GitHub Pages environment were not executed on this Mac. Workflow parsing and local packaging do not establish that GitHub permissions/settings are already configured. Nothing has been hosted or published.

English keyword topics are a baseline, not semantic/sentiment accuracy estimates. Human comment-sample validation, codebook refinement where needed, final recommendation approval, organizational disclosure review, anonymous hosting arrangements and the final memo/AI appendix/deck/demo remain team responsibilities. No human review or organizer approval has been claimed. Suppression reduces risk but is not a formal proof against cross-table, cross-skill, linked-release or external-information inference.
