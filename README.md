<div align="center">

## Judges: run Excel/CSV upload locally

**Public website:** [Open EveryMind Insight](https://tvworks22.github.io/everymind-insight/). The hosted viewer opens aggregate reports. For direct Excel/CSV analysis and source-row filters, use the command below.

### One-time preparation

1. Download this repository using **Code → Download ZIP**, then extract it.
2. Install **Python 3.11** from [python.org](https://www.python.org/downloads/) if it is not installed. Windows users should enable the Python launcher. Existing `uv` installations are also supported on macOS/Linux.
3. Open a terminal **in the extracted project folder**. On macOS, right-click the folder in Finder → Services → **New Terminal at Folder**. On Windows, open the folder, right-click empty space → **Open in Terminal**.

### Type one command

**macOS / Linux:**

```sh
sh run.sh
```

**Windows PowerShell:**

```powershell
.\run.bat
```

The command installs the required tools on first use, starts the local survey server on an available port, and opens your browser automatically. First setup needs internet and can take several minutes. No activation commands, port selection, or Linux knowledge are needed.

In the page, select your **XLSX or CSV** survey and follow the data-options controls to view results. No manual JSON conversion is required. Keep the terminal open while judging; press **Ctrl+C** there when finished. If the browser does not open, copy the address printed after **EveryMind is ready** into your browser.

Analysis runs on this computer. The command does not publish a website or upload survey data to GitHub. Installed tools are downloaded during setup. If setup fails, check Python 3.11, internet access and write permission for the extracted folder. An incomplete `.venv` can be removed and the same command rerun; do not delete the survey file.

---


### [Open EveryMind Insight →](https://tvworks22.github.io/everymind-insight/)

**Explore training outcomes, participant feedback, and opportunities for improvement.**

No installation is required to view the dashboard.

</div>

1. Open the application and scroll past the introduction.
2. Check whether you are viewing a **survey report** or the **synthetic demonstration**.
3. Explore the results using the report sections, filters, and evidence panels.

> **Local data options:** The local `serve` command accepts Excel/CSV uploads in memory and offers checkbox filters before opening a report. The hosted static application accepts prepared report JSON. See the [local data-options guide](docs/DATA_OPTIONS.md).

---

# EveryMind Insight

### From training feedback to practical decisions.

EveryMind Insight helps teams understand what participants report learning from Understanding 988 training, where knowledge gaps remain, and which aspects of future training deserve closer attention.

The application combines survey analysis with an interactive dashboard. Results are accompanied by calculation bases, uncertainty intervals, quality checks, and interpretation limits so reviewers can examine the evidence behind the headline numbers.

**[Open the application](https://tvworks22.github.io/everymind-insight/)** · **[Explore the dashboard](#explore-the-dashboard)** · **[Understand the results](#understand-the-results)** · **[Technical details](#technical-architecture)**

---

## What can you learn?

| Question | What the application provides |
| :--- | :--- |
| Do participants feel more prepared? | Recalled-before and current agreement for three training objectives |
| Where might reinforcement help? | Remaining gaps and the direction of individual rating changes |
| How stable are the results? | Confidence intervals and comparisons with and without quality-flagged responses |
| Do outcomes differ across groups? | Released comparisons by county, participant role, language, and training month |
| What did participants discuss? | Aggregate topics from valuable-learning and improvement comments |
| What should the team consider next? | Recommendation drafts connected to supporting evidence and limitations |

The application supports descriptive evaluation. It does not establish that training caused a change or that participants subsequently called 988.

## Run the application locally

The public website is the easiest way to explore the dashboard. Local setup is available for analysts and contributors working with survey exports.

### Requirements

- **Python 3.11**
- An extracted project folder in a writable location.
- Internet access for first-time package installation.
- A supported survey export.

### Beginner setup

1. Download and extract the repository.
2. Open the launcher for your operating system.
3. Choose the synthetic demonstration or your private survey export.
4. Follow the prompts and keep the launcher window open while browsing.

| Platform | Launcher |
| :--- | :--- |
| macOS | `Start EveryMind.command` |
| Windows | `Start EveryMind.bat` |
| Linux | `start-everymind.sh` |

If macOS opens the launcher as text, use **Open With → Terminal**.

For an Excel workbook, the default worksheet name is `Survey Data`. Enter a different name when prompted if needed.

The source workbook is read in place and left unchanged.

### Local outputs

| File | Purpose |
| :--- | :--- |
| `reports/report.json` | Aggregate dashboard report |
| `reports/private-quality.json` | Private schema, quality, and comment-review diagnostics |

Both are ignored by Git by default. Keep the private audit private.

Successful runs replace the local outputs. After a failed run, check timestamps before using existing files.

---

## Technical architecture

```text
Supported survey export
          │
          ▼
Header checks and normalization
          │
          ▼
Quality checks and analytics
          │
          ▼
Topic coding and evidence-linked drafts
          │
          ▼
Release policy and report validation
          │
     ┌────┴───────────┐
     ▼                ▼
Aggregate report   Private diagnostics
     │
     ▼
Interactive dashboard
```

The implementation separates Python analysis from browser presentation. A loopback-only FastAPI server supports in-memory workbook upload, filter previews, privacy-checked report recomputation, and aggregate exports. Static hosting displays prepared aggregate JSON reports.

### Main components

| Component | Responsibility |
| :--- | :--- |
| `ingestion.py` | Read exports and audit question headers |
| `normalization.py` | Normalize scores, categories, dates, and response values |
| `quality.py` | Identify usable IDs and quality flags |
| `metrics.py` | Calculate paired skill results and uncertainty |
| `subgroups.py` | Analyze participant groups |
| `survey_versions.py` | Examine calling coverage and survey-version/date patterns |
| `delivery.py` | Analyze presenter ratings and recommendation measures |
| `themes.py` | Apply the comment-topic codebook |
| `release.py` | Restrict the public surface and protect sensitive results |
| `reporting.py` | Assemble the complete report |
| `dashboard/` | Display validated results |

### Validation contract

The existing dashboard report contract is `ReportBundle`, schema version `1.0.0`.

Validation checks include:

- Duplicate metric keys.
- References to absent metrics.
- Inconsistent input fingerprints.
- Nonfinite numerical values.
- Calculation-base reconciliation.
- Numeric fields incorrectly retained in suppressed entries.
- Public-release metric and dimension rules.

Structural validation does not certify source truth or constitute approval to publish.

---

## Tests and reproducibility

The backend-fixes implementation recorded:

| Check | Result |
| :--- | :--- |
| Python tests with the supplied reference workbook | **70 passed** |
| Frontend data-contract tests | **16 passed** |
| Browser validation | Real/synthetic switching, cohort controls, invalid files, and downloads |
| Clean macOS setup | Launcher reached the mode menu successfully |

These results describe that tested implementation. New features require additional testing.

For contributors:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
node --test tests/dashboard.test.cjs
```

To include the original private reference workbook:

```sh
.venv/bin/python -m pytest -q tests \
  --survey-workbook data/survey.xlsx
```

On Windows, use `py -3.11` for environment creation and `.\.venv\Scripts\python.exe` afterward.

Reference-workbook tests are skipped when that file is not supplied.

Metrics record input/settings fingerprints and analytical methods. Report metadata records software, Python, library, and codebook versions. Preserve the source revision and environment for any reviewed release.

---

## AI use

Claude supported planning, prompt development, design suggestions, and discussions about team responsibilities.

Codex supported implementation, debugging, testing, and documentation.

The current application does not make live language-model requests to calculate survey statistics or classify comments. Numerical results come from Python analysis functions; comment topics come from the deterministic codebook.

See the [AI process record](docs/AI_PROCESS.md) for representative requests, limitations, corrections, and validation practices.

---

## Troubleshooting

| Issue | What to check |
| :--- | :--- |
| The displayed results are illustrative | Check the synthetic/survey source label |
| A file is rejected | Confirm that its format is supported by the deployed version |
| Python setup fails | Confirm Python 3.11, internet access, and folder permissions |
| The launcher opens as text | Use **Open With → Terminal** on macOS |
| The file picker is unavailable | Paste the full file path when prompted |
| Required questions are missing | Check worksheet name and approved question wording |
| A value is unavailable | Inspect data coverage and methods; do not assume zero |
| A value is withheld | A privacy rule applies; do not lower thresholds merely to display it |
| Results appear outdated | Check the source label and generation timestamp |

---

## Status and limitations

EveryMind Insight is a working analytical prototype with a public dashboard and tested survey-processing functionality.

Results remain subject to retrospective reporting, respondent selection, question coverage, ordinal-scale assumptions, and differences in participant composition. Public community comparisons are descriptive and unadjusted.

### Further documentation

- [Local data options, filtering and exports](docs/DATA_OPTIONS.md)
- [Backend methods and analyst workflow](docs/BACKEND_GUIDE.md)
- [GitHub Pages and judge workflow](docs/PAGES.md)
- [Validation record](docs/VALIDATION.md)
- [AI-assisted development record](docs/AI_PROCESS.md)
- [Submission checklist](docs/SUBMISSION_CHECKLIST.md)

Asset attribution and license information are retained in [`dashboard/assets/`](dashboard/assets/).


## Hosted Excel/CSV analysis on Render

A separate hosted mode supports temporary, isolated browser upload sessions. It preserves local-only mode and the GitHub Pages viewer. See [Render setup and data-handling limits](docs/RENDER.md). Render hosting uses the free plan; an idle service may take time to restart.
