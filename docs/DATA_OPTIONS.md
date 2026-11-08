# Data options before opening a report


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

