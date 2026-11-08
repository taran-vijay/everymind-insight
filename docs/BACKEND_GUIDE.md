# Backend report workflow

This work is based only on master `0da70d3`. It adds functionality and release validation, not the proposed optimization/efficiency changes. No video/font changes, frontend metric indexing, caching, dependency lock, or statistical performance refactors are included.

## Analyst commands

Use Python 3.11. The launchers set up the environment automatically. For explicit setup:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

On Windows use `py -3.11` for the first command and `.venv\Scripts\python.exe` afterward. From the project root:

```sh
.venv/bin/python -m everymind_insight report data/survey.xlsx
.venv/bin/python -m everymind_insight validate-report reports/report.json
.venv/bin/python -m everymind_insight pages --report reports/report.json --out dist/review
.venv/bin/python -m http.server 8000 --bind 127.0.0.1 --directory dist/review
```

Open `http://127.0.0.1:8000/`. The launcher uses a restricted server on a free loopback port instead of serving the repository. The explicit server command above is safe only because `dist/review` contains the allowlisted website package.

`report` accepts `--sheet`, `--config-dir`, `--role-policy`, `--output`, `--audit-output`, and `--synthetic`. Use `--synthetic` for generated surveys. The program cannot infer whether an arbitrary export contains actual participants. Demo mode uses the existing clearly labeled illustrative fixture, and never overwrites a saved survey report.

Required ID and all six skill headers must match unambiguously. No usable IDs is an error. Optional absent questions are unavailable rather than zero. Run the existing private `check` command to diagnose schema failures. `phase3` remains an advanced analyst output; its JSON is not a dashboard report and must not be renamed as one.

## Release surface

Private analysis uses the existing objective, subgroup, survey-version and delivery functions. The complete report deliberately releases a narrower set:

- Skills: paired agreement before/current, gap, gain, movement, ceiling and mean ordinal change, with all-response and unflagged cohorts where safe.
- Communities: all-response county, role, language and training-month counts and paired outcomes. Unapproved labels are not exported. Role counts may overlap. These public comparisons are unadjusted.
- Calling: overall answer coverage and stated-intent mean among valid answers. The coverage denominator is not the same as the mean's denominator.
- Delivery: all-response presenter answer coverage/agreement and recommendation segments/counts where releasable. Detailed score distributions, model outputs and diagnostic tests remain private.
- Comments: fixed codebook labels, answered/unclassified counts, coding coverage and topic shares. No respondent text, IDs, exact dates or verbatim quotations are exported.
- Quality: usable-ID, flagged and invalid-date counts subject to protection.

The release threshold is at least 10, even if an analyst configures a lower Phase 3 threshold. Positive small counts and their binary complements are protected. Related agreement/gain rows and movement cells are withheld together when needed; this does not mean one small omitted transition hides all skill outcomes. Clean-cohort counterparts are protected when subtracting them from overall results would reveal a small flagged group or event count. Small missing-pair partitions and answer-coverage partitions are protected too.

Subgroup outcome row families are protected together with companion rows in additive group tables. Existing count-table suppression is retained. Only all-response subgroup/delivery/calling metrics are released to limit overlapping nested comparisons. Exact-date dimensions, transition matrices, regression diagnostics, associations and shuffle tests are omitted from the public report.

These are release safeguards, not proof of anonymity. Cross-table, cross-skill, repeated-release and external-information inference may still be possible. Data owners must review linked outputs and organizational privacy policy before public release. A valid schema alone never constitutes approval to publish.

## Topic coding and staff review

The bundled `defaults/themes.json` is versioned and hashed into the settings fingerprint. It labels topics in two questions: valuable learning and improvement feedback. Matching is deterministic and may assign several topics to one answer. Coding coverage is the fraction matching any topic, not a measured accuracy score. Empty comments are excluded from theme denominators; unmatched comments remain explicitly counted. The no-change pattern is anchored so an answer such as "nothing about the crisis was explained" is not classified as no change.

Before operational use:

1. Use the PRIVATE audit's `source_record` locators (Excel worksheet rows or logical CSV records, header = 1; multiline CSV records are not physical line numbers) to inspect examples of each topic and unmatched answers in the original workbook.
2. Check negation, ambiguous wording, non-English answers and positive mentions that do not request a change.
3. Independently label a sample and record agreements/disagreements in an approved private review record. The software has not performed or claimed human review.
4. Update the codebook and its version if needed, add representative tests, regenerate the report and compare counts.
5. Have the program lead approve or revise the recommendation drafts before using them for training/funding decisions.

Recommendations reference released metrics and caveats. They include proposed owners, timing and measures. No live LLM call, invented quote, human-review claim or unsupported causal conclusion is generated.

## Reproducibility and validation

Each metric records input/settings hashes, method, population and calculation base. Report metadata records software, Python, analytics-library and codebook versions. Existing dependency ranges are unchanged; archive the actual environment for a reviewed release. No dependency-lock optimization was added.

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests --survey-workbook data/survey.xlsx
node --test tests/dashboard.test.cjs
```

The optional workbook must be the frozen reference export. Its expected all-response paired counts are 1,299; agreement before/current is 938/1,168 for identifying crises, 604/1,175 for describing 988, and 723/1,199 for knowing when to use 988. These tests validate calculations, not causal claims or universal privacy guarantees. Without the private workbook, those checks are explicitly skipped.
