# everymind-insight


## Start here: complete local survey workflow

### Data options before opening a report

Install/update the local environment once with `python -m pip install -e '.[test]'`.
From the repository folder on Windows, run:

```powershell
.\.venv\Scripts\python.exe -m everymind_insight serve --input 'C:\Users\arije\Downloads\BuildFest_EveryMind_Survey_Data_FULL.xlsx' --port 8001
```

Open `http://127.0.0.1:8001/`. The server binds only to this computer. Omit
`--input` to choose an XLSX or UTF-8 CSV in the page. Upload bytes, normalized
responses, specifications and caches stay in memory. Nothing is
written to localStorage. Stop the
server to discard its source and cache. Uploaded surveys are never saved.

Choose **Open report** to review **Data Options**. All options start unchecked.
The panel offers four checkboxes: completion under 30 seconds, completion over
two hours, a four-point before/after drop, and missing or invalid training dates.
Check the exclusions and use the single report button. It opens the full report
when nothing is checked and the filtered report when exclusions are selected.
The removed total counts each response once. Uncheck an option to remove it.
File selection is tucked under **Choose Your Data** in the same panel; choose
**Use this file** after selecting a replacement source.

Advanced FilterSpec rules remain available through the CLI/API, outside this
checkbox-only interface. Option and category exclusions are unioned; **Any/All**
combines numeric rules only. Exact duplicates match every original field except
ID, including timestamps, and keep the first record. Missing training dates count as missing/invalid.
“Below” and “above” are strict; “between” includes its endpoints. Missing values
match only “is missing,” and never silently act as zero.

The supported numeric fields are `duration_seconds`, `recommend_score`,
`calling_score`, the six `{skill}_before`/`{skill}_after` objective fields,
`presenter_engaged`, `presenter_knew_subject`, `presenter_organized`,
`identify_crises_change`, `describe_988_change`, `know_when_to_use_988_change`,
and ISO `training_date`. The skill IDs are `identify_crises`, `describe_988`,
and `know_when_to_use_988`. Changes are current minus recalled-before ratings.

For example, save this as `filters.json` to remove durations below 30 or above
3,600 seconds:

```json
{
  "schema_version": "1.0.0",
  "numeric_rules": [
    {"field": "duration_seconds", "operator": "below", "value": 30},
    {"field": "duration_seconds", "operator": "above", "value": 3600}
  ],
  "rule_logic": "any"
}
```

To remove declines in knowing when to use 988, use
`{"field":"know_when_to_use_988_change","operator":"below","value":0}`.
Supported CLI/API option IDs are `exact_duplicates`, `speeders`, `long_duration`,
`straightliners`, `large_drops`, `invalid_training_date`, `invalid_timestamps`.
The CLI/API thresholds are `speed_seconds` (default 30) and `long_seconds`
(default 7,200). Optional `categorical_exclusions` contains lists named `county`,
`role`, `language`, and `training_month`, using released labels from `/api/fields`.

Reproduce an analysis and export aggregates:

```powershell
.\.venv\Scripts\python.exe -m everymind_insight report 'C:\Users\arije\Downloads\BuildFest_EveryMind_Survey_Data_FULL.xlsx' --filters filters.json --output reports\filtered.json --csv-output reports\filtered.csv --parquet-output reports\filtered.parquet
```

JSON includes versioned `filter_provenance`. Every CSV/Parquet metric row includes
the specification, counts and filtered-view notice. These are aggregate exports,
not cleaned respondent files. Filtered charts and printing carry the same notice.
Aggregate JSON reports and synthetic fixtures have no source rows; the panel
explains why their options are disabled rather than simulating exclusions.

The API serves `GET /api/fields`, `POST /api/preview`, `POST /api/report`, and
`POST /api/export/{json|csv|parquet}`. `POST /api/source?filename=survey.xlsx`
accepts an application/octet-stream body in memory (50 MB maximum). Preview and
report requests accept FilterSpec JSON. The field response includes an input
hash; send it as `X-Input-Hash` so a source change cannot mix old selections with
a new survey. Browser requests are same-origin only, and the server never serves
the repository, private audits or raw uploads.

Small bins are merged before histogram ranges/counts are returned. A histogram is
withheld when its total would reveal 1–9 missing answers. Small category
counts and complements are withheld. A selection keeping fewer than 10 is
rejected. A selection removing 1–9 is also withheld: returning its exact included
count would reveal that complement through subtraction. Preview displays “fewer
than 10,” without the exact kept/removed numbers. Previously opened views that
differ by fewer than 10 responses cannot be compared. Filtered metrics also
receive the existing release guards and protection against small full-sample
differences. This reduces disclosure risk; it is not differential privacy or a
guarantee against external information and arbitrary linked releases.

Reports cache in memory by input hash and canonical specification hash (up to 16
reports). Numerical results and cached JSON are deterministic for the same loaded
source/specification; a new server session records a new generation timestamp.
The fast report path skips private models and associations that never appear in
the public report, while retaining the same released metrics and suppression.
Reference-data tests compare its full metric ledger with the existing pipeline.

**This branch connects the supplied survey export to a validated dashboard report.** The current forest design, videos, fonts and animations are preserved. GitHub Pages deployment is prepared but remains manual and disabled on this branch.

1. Extract/download the project into a writable folder. Install **Python 3.11** if needed.
2. On macOS, double-click **Start EveryMind.command**. On Windows, open **Start EveryMind.bat**. On Linux, run **start-everymind.sh**. macOS/Linux can also use an existing `uv` installation to obtain Python 3.11.
3. Choose **1** for the clearly labeled synthetic demo, or **2** to select an XLSX/UTF-8 CSV survey export. For XLSX, press Enter for the `Survey Data` worksheet or enter the actual name.
4. The browser opens the current dashboard. Keep the launcher window open; press **Ctrl+C** there to stop.

First launch installs the analytics/test dependencies and needs internet. The workbook is read locally and is not uploaded. If the file picker is unavailable, paste its full path. A failed survey never silently substitutes the demo. If macOS opens the launcher as text, use Open With → Terminal, or run `sh "Start EveryMind.command"` from this folder. If setup was interrupted, remove only `.venv` and reopen the launcher. Native Windows/Linux launcher execution still requires platform-specific verification.

### Your outputs

| File | Purpose |
| --- | --- |
| `reports/report.json` | Complete aggregate report: skill results, both quality cohorts, released community/month tables, calling coverage/intent, topic counts and evidence-linked recommendation drafts. Review before sharing. |
| `reports/private-quality.json` | **PRIVATE** schema/quality diagnostics and source-row locators for reviewing comment coding. Never add this file or the workbook to a public site. |

Both outputs are ignored by Git. Successful runs replace the local outputs; save historical copies separately if needed. A failed run may leave earlier files in place: check the generation timestamp.

**On static GitHub Pages, Open report reads aggregate JSON in the browser.** XLSX/CSV analysis and data options require the local `serve` command above. Download report JSON downloads the report currently displayed. Load synthetic demo is explicit and visibly labeled. Missing/unavailable and privacy-withheld results are not zero.

### Important interpretation limits

- Recalled-before/current ratings describe self-reported change, not a causal training effect.
- Flags identify responses for review; both skill cohorts support sensitivity checks.
- Calling intent describes stated willingness among valid answers, not actual calls. Blank answers may mean not asked, skipped or invalid.
- Comment topics use a deterministic English keyword codebook, not sentiment analysis. Topics overlap; non-English, unmatched and negated examples require private manual review.
- Recommendations are controlled drafts grounded in released evidence, with suggested owners, next steps and measures. No human approval is implied.
- Privacy release checks protect small counts, complements and related comparisons. They do not provide differential privacy or guarantee safety across linked reports and external information.

[Backend guide and tests](docs/BACKEND_GUIDE.md) · [GitHub Pages and judge instructions](docs/PAGES.md) · [AI process record](docs/AI_PROCESS.md) · [Submission checklist](docs/SUBMISSION_CHECKLIST.md)

---

Local analytics for EveryMind's 988 awareness training survey. Phase 1 reads an export, checks for changes to the survey questions, normalizes responses, and saves a private quality report.

## Run the Phase 1 check on Windows

Open PowerShell in the repository folder. Install Python 3.11 if `py -3.11 -V` cannot find it, then set up the project once.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
```

Set `$workbook` to the location of your private export, then run the check. The path below is an example in the ignored `data` folder.

```powershell
$workbook = '.\data\survey.xlsx'
.\.venv\Scripts\python.exe -m everymind_insight check $workbook --output reports\quality.json
```

```text
Loaded 1,299 responses and 20 columns.
Usable response IDs 1,299. Flagged rows 352.
Presenter sensitivity check. Objective headline counts unchanged.
Private quality report saved to reports\quality.json.
```

A separate timing line shows how long each stage took. The same command accepts a UTF-8 CSV export. For a workbook, the default worksheet is `Survey Data`. Use `--sheet` when the worksheet has a different name. The command reads the export in place and writes a separate report file.

## Read the quality report

- `ingestion` records the file hash, schema fingerprint, and questions that were added, renamed, reordered, missing, duplicated, or sent for review. A missing or ambiguous question has blank canonical values so other questions can still be checked.
- `normalization.columns` shows answered, missing, invalid, and changed counts, along with unfamiliar category labels. An unfamiliar county remains a separate value. Similar approved names appear as review suggestions.
- `flags` gives the count for each response-quality flag. `flag_combinations` gives mutually exclusive counts, including overlaps. `objective_flag_sensitivity` shows how objective counts change when flagged responses are excluded. Rows with missing or duplicate IDs are counted in the audit and excluded from respondent headline counts.
- `presenter_sensitivity` shows valid response and agreement counts when `Satisfied` is scored as 4 and when those answers are treated as missing. It compares objective headline counts for both treatments.

The quality report can contain exact unfamiliar category labels and is for private review. `reports/` is excluded from Git. Keep workbooks, raw responses, and private audits out of version control.

By default, each multi-role respondent contributes once to each distinct role they selected. Add `--role-policy multiple` to assign respondents with multiple selections to one `Multiple roles` group. Use `--config-dir` to override a bundled YAML file by placing a file with the same name in the selected folder. The defaults live in `src/everymind_insight/defaults/`.

## Verify the implementation

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_phase1.py
.\.venv\Scripts\python.exe -m pytest -v tests/test_phase1.py -k refresh
$workbook = '.\data\survey.xlsx'
.\.venv\Scripts\python.exe -m pytest -q tests/test_phase1.py "--survey-workbook=$workbook"
```

The refresh command lists all five scenarios and a combined test. The workbook command also verifies the reference counts and expects 17 passing tests.

## Verify Phase 2 objective metrics

Reinstall the project with `pip install -e '.[test]'` in the virtual environment if it was set up before Phase 2. Then run the reference-workbook checks and the full suite.

```powershell
$workbook = '.\data\survey.xlsx'
.\.venv\Scripts\python.exe -m pytest -vv -s tests/test_ground_truth.py "--survey-workbook=$workbook"
.\.venv\Scripts\python.exe -m pytest -q "--survey-workbook=$workbook"
```

The first command prints and checks agreement, movement, remaining gap and ceiling counts for each skill, plus four cells in the Know when to use 988 transition matrix. All three skills use 1,299 complete pairs in the reference workbook. The full suite also checks the metric properties and the frontend sample.

`analyze_objectives` in `src/everymind_insight/metrics.py` builds the typed ledger from the normalized and flagged frame. It includes both quality cohorts, transition counts, Wilson intervals, a seeded paired bootstrap for mean ordinal change, paired tests, ceiling and normalized gain measures, and gap and gain ranks. Percentages are represented as proportions between 0 and 1. A `percentage_point` entry already uses percentage-point units.

The frontend can load `fixtures/report.sample.json` as a complete `1.0.0` example. Its metric values are synthetic. Ledger rows are keyed by `metric_id` and `dimensions`. The report sections reference those keys, including a suppressed entry that demonstrates the null numeric fields. The contract is the `ReportBundle` model in `src/everymind_insight/schemas.py`.

## Run Phase 3 subgroup, coverage, and delivery analyses

```powershell
$workbook = '.\data\survey.xlsx'
.\.venv\Scripts\python.exe -m everymind_insight phase3 $workbook --output reports\phase3.json
.\.venv\Scripts\python.exe -m pytest -v tests/test_subgroups.py tests/test_survey_versions.py `
  tests/test_delivery.py tests/test_suppression.py "--survey-workbook=$workbook"
```

The analysis command saves an aggregate ledger to `reports\phase3.json` and prints the metric and suppression counts. Filter `dimensions.cohort` to `all_responses` or `excluding_flagged`. In the reference workbook, November 2025 and February, July, and August 2026 are suppressed in the training-month tables.

- `subgroup_*` covers county, role, language, and training month. County results include unadjusted shares, directly standardized shares, and a county-plus-role logistic model with standard errors clustered by training date. Direct standardization uses mutually exclusive role strata even when the descriptive role tables count people in every role they chose.
- `calling_*` and `date_item_coverage` show observed coverage, a date-based exposure proxy, stated calling intent among valid answers, and the shuffle test. A mixed date contains both valid answers and blanks or invalid answers. The county and role coverage comparisons are descriptive. `calling_group_inseparable` flags dominance by one date or a lack of shared dates.
- `presenter_*` and `recommend_*` cover valid-answer counts, distributions, recommendation segments and heaping, and associations with paired skill changes.

`phase3.yaml` sets the minimum table size, the minimum number of training-date clusters for modeling, the dominance threshold, and the resampling settings. Suppression is applied within each table. A suppressed entry has null value, counts, sample size and interval.

## Open the draft dashboard

Run these commands from the repository folder after installing the project. They copy the synthetic sample beside the page and serve the dashboard folder locally.

```powershell
.\.venv\Scripts\python.exe -m everymind_insight dashboard --report fixtures/report.sample.json --out dashboard
.\.venv\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1 --directory dashboard
```

Open [the local dashboard](http://127.0.0.1:8000/). When an aggregate report bundle is ready, pass its path to `--report` and refresh the page. The generated `report.json` is ignored by Git. The page reads the report bundle schema used by the sample fixture.

The dashboard opens with a full-screen forest video, followed by one scrolling report with five sections: Overview, Learning Outcomes, Community Reach, Participant Feedback, and Data & Methods. Navigation links jump to each section. Use **Open report** to read a different aggregate report JSON locally in the browser. The synthetic-data banner stays visible for sample reports. Invalid files leave the current report in place.

The overview switches between **Agreement** and **Rating movement**, with available confidence intervals always shown. Objective links scroll to the selected outcome; cohort and community filters are preserved in the URL and support Back and reload. Bars and rings automatically fill on entering the viewport and replay after leaving it. File selection and data options appear only when **Open report** is clicked. The decorative forest video automatically plays while visible and pauses offscreen.

Learning Outcomes includes an **Exclude flagged responses** cohort selector. Community comparisons appear only when the bundle contains the selected subgroup metrics; the sample does not include those comparisons. Feedback displays report-supplied findings, actions, and coded themes. Findings with unavailable or suppressed supporting metrics are withheld. **Print view** prints the continuous report without the video.

The frontend uses native HTML, CSS, and JavaScript, with locally bundled Inter and Chivo Mono fonts. It requires no frontend build step or external font service. Font and footage licenses are recorded in `dashboard/assets/`. Opening `dashboard/index.html` directly also works: select a report with **Open report**.

For a quick preview from the repository root, without installing Python dependencies:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Then open [the dashboard](http://127.0.0.1:8000/dashboard/). If no generated `dashboard/report.json` exists, select **Load synthetic demo** explicitly. Missing real reports are never silently replaced by sample data.

Run the frontend data-contract checks with Node.js 18 or later:

```sh
node --test tests/dashboard.test.cjs
```
