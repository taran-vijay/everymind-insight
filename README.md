# everymind-insight

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

The overview switches between **Agreement** and **Rating movement**, with optional confidence intervals. Objective links scroll to the selected outcome; cohort and community filters are preserved in the URL and support Back and reload. Bars and rings fill on entering the viewport and replay after leaving it. **Animate charts** remembers a local preference and defaults to the system motion setting. The decorative forest video automatically plays while visible and pauses offscreen.

Learning Outcomes includes an **Exclude flagged responses** cohort selector. Community comparisons appear only when the bundle contains the selected subgroup metrics; the sample does not include those comparisons. Feedback displays report-supplied findings, actions, and coded themes. Findings with unavailable or suppressed supporting metrics are withheld. **Print view** prints the continuous report without the video.

The frontend uses native HTML, CSS, and JavaScript, with locally bundled Inter and Chivo Mono fonts. It requires no frontend build step or external font service. Font and footage licenses are recorded in `dashboard/assets/`. Opening `dashboard/index.html` directly also works: select a report with **Open report**.

For a quick preview from the repository root, without installing Python dependencies:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Then open [the dashboard](http://127.0.0.1:8000/dashboard/). It falls back to the synthetic fixture when no generated `dashboard/report.json` exists.

Run the frontend data-contract checks with Node.js 18 or later:

```sh
node --test tests/dashboard.test.cjs
```
