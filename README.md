<div align="center">

# EveryMind Insight

**Turn Understanding 988 training feedback into evidence for the next decision.**

### [Open the application →](https://everymind-insight-judges.onrender.com/)

Upload an Excel or CSV survey, review the data options, and explore the results.

**No installation. No terminal commands. No manual JSON conversion.**

[Get started](#get-started) · [What makes it useful](#what-makes-it-useful) · [Run locally](#run-locally) · [How it works](#how-it-works) · [For contributors](#for-contributors)

</div>

---

## Get started

1. **[Open EveryMind Insight](https://everymind-insight-judges.onrender.com/)** and select **Open report**.
2. Under **Survey or report file**, choose your authorized **Excel (.xlsx)** or **CSV (.csv)** survey export.
3. For Excel, confirm the worksheet name. The default is **Survey Data**.
4. Select **Use this file**. Review the response count and any responses you want to leave out; nothing is excluded by default.
5. Select **Open full report**, or **Open filtered report** when exclusions are selected.

You can also choose **Load synthetic demo** to explore illustrative results without uploading a file. Check the source label before interpreting any numbers. Prepared aggregate **report JSON** files can be opened through the same file picker.

> **For judges:** use the application link above for direct Excel/CSV analysis. The separate [GitHub Pages viewer](https://tvworks22.github.io/everymind-insight/) opens aggregate JSON reports and the synthetic demonstration; it cannot process Excel/CSV surveys on its own.

### Before uploading

| Hosted application | What to expect |
| :--- | :--- |
| File size | Up to **5 MB** per Excel/CSV upload |
| Processing | Survey data is sent to the Render server for analysis |
| Separation | Each browser session has its own uploaded survey and filter history |
| Temporary storage | In-memory sessions expire after **20 minutes of inactivity**, checked on API access; service restarts clear them |
| Finish your review | Use **Clear my uploaded survey** at the bottom of the page |
| Free hosting | The service can take time to wake after inactivity; you may need to upload again |

Upload only data you are authorized to process on this service. For analysis that stays on your computer, use the [local option](#run-locally).

## What makes it useful

EveryMind Insight helps reviewers examine what participants report learning, where gaps remain, and what to investigate before changing training. Each headline is supported by its calculation base and interpretation limits.

| Practical question | Evidence you can inspect |
| :--- | :--- |
| Do participants feel more prepared? | Recalled-before and current agreement for three training objectives, plus individual rating movement |
| Where could reinforcement help? | Remaining gaps by objective and descriptive community comparisons |
| How stable are the findings? | Confidence intervals and sensitivity comparisons with and without quality-flagged responses |
| Whose responses are represented? | County, participant role, language, training-month coverage, and question-specific denominators |
| What did participants discuss? | Aggregate topics in learning and improvement comments, with coding-coverage information |
| What should the team consider next? | Recommendation drafts linked to supporting metrics and limitations |

### Four principles behind the report

- **Evidence traceability.** Metrics retain methods, denominators and input/settings fingerprints. Findings link to the metrics that support them.
- **Visible uncertainty.** Confidence intervals, missingness and quality-flag sensitivity help reviewers distinguish an estimate from a firm conclusion.
- **Privacy-aware release.** Small cells, complements and related results can be withheld. Raw comments and private diagnostics are excluded from the aggregate dashboard report.
- **Survey integrity.** Header checks, response-ID checks, paired-answer requirements and quality flags make problems visible before results are interpreted.

These safeguards reduce disclosure and interpretation risks. They do not certify anonymity, source accuracy, or permission to publish a report.

## Explore the dashboard

| Section | Start here to… |
| :--- | :--- |
| **Overview** | See the headline outcomes, remaining gap, feedback topics and response coverage |
| **Outcomes** | Inspect each objective, complete pairs, rating movement and calculation context |
| **Communities** | Compare released results by county, role, language or training month |
| **Feedback** | Review coded topics and evidence-linked recommendation drafts |
| **Methods** | Inspect quality checks, definitions, provenance and limitations |

**Unavailable**, **withheld** and **zero** mean different things. A withheld value is protected by a release rule; it is not a zero. Recommendation text is a draft for staff review, not an approved decision.

## Run locally

Choose this option when survey analysis should stay on your computer. The local upload server uses the same dashboard and analysis pipeline.

### One-time preparation

1. Download the repository using **Code → Download ZIP**, then extract it into a writable folder.
2. Install **[Python 3.11](https://www.python.org/downloads/)** if needed. On Windows, enable the Python launcher during installation. macOS/Linux users with `uv` can also use the launcher.
3. Open a terminal in the extracted project folder. On macOS, right-click the folder in Finder → **Services → New Terminal at Folder**. On Windows, open the folder and choose **Open in Terminal**.

### Start the upload dashboard

**macOS / Linux**

```sh
sh run.sh
```

**Windows PowerShell**

```powershell
.\run.bat
```

First setup downloads and installs dependencies, which requires internet and can take several minutes. The launcher starts the server on an available local port and opens your browser. Follow the same file-selection steps as the hosted application. No environment activation or port selection is needed.

Keep the terminal open while using the application. Press **Ctrl+C** there to stop it. If the browser does not open, use the address printed after **EveryMind is ready**.

<details>
<summary><strong>Alternative: double-click the guided launcher</strong></summary>

The guided workflow offers a synthetic demonstration or analysis of a private survey export.

| Platform | Launcher |
| :--- | :--- |
| macOS | `Start EveryMind.command` |
| Windows | `Start EveryMind.bat` |
| Linux | `start-everymind.sh` |

If macOS opens the launcher as text, choose **Open With → Terminal**. The guided analysis workflow can save `reports/report.json` and `reports/private-quality.json`; keep the private diagnostics private. The source workbook is read without modifying it. See the [backend guide](docs/BACKEND_GUIDE.md) for saved-output details.

</details>

## How it works

```text
Excel / CSV survey export
          ↓
Header checks → normalization → response-quality checks
          ↓
Paired outcomes + uncertainty + subgroup analysis + topic coding
          ↓
Release protection + report validation
          ↓
Aggregate report → interactive dashboard
```

Python performs the analysis; the browser presents the validated results. FastAPI provides survey upload, filter preview, report generation and aggregate export endpoints. Local mode listens on the computer's loopback interface. Render runs the same application in hosted mode with separate temporary browser sessions.

### Report contract and release rules

Dashboard reports use the **`ReportBundle` schema, version `1.0.0`**. Validation checks metric keys, evidence references, input fingerprints, finite numerical values, calculation-base reconciliation, suppressed fields, and permitted public metrics and dimensions.

The report contains aggregate results. Analyst workflows can generate a separate private audit with source-quality and comment-review diagnostics; that audit is not a dashboard report and must not be published as one.

Hosted analysis allows up to four active upload sessions and processes analysis requests sequentially. It has no persistent database or uploaded-file disk. This is a bounded judging prototype; it is not a production multi-tenant service. See [Render hosting and data handling](docs/RENDER.md).

### Code map

| Area | Main files |
| :--- | :--- |
| Reading and checking exports | `ingestion.py`, `normalization.py`, `quality.py` |
| Outcomes and community analysis | `metrics.py`, `subgroups.py`, `survey_versions.py`, `delivery.py` |
| Comment topics and report assembly | `themes.py`, `reporting.py` |
| Release protection and validation | `release.py`, `schemas.py` |
| Uploads, filters and hosted sessions | `server.py`, `filter_service.py`, `hosted.py` |
| Presentation | `dashboard/` |

Python modules live under `src/everymind_insight/`.

## Status and limitations

EveryMind Insight is a working analytical prototype with hosted survey uploads, a static report viewer and local processing options.

- **Self-reported change is not a causal effect.** Both ratings were collected after training; recall bias, response shift, respondent selection and the lack of a control group limit interpretation.
- **Community comparisons are descriptive and unadjusted.** Participant composition varies, and role groups can overlap.
- **Calling intent is not actual calling behavior.** Blank responses do not distinguish a question that was not asked from one that was skipped.
- **Comment topics need human review.** Deterministic English keyword rules can miss negation, ambiguity and other languages. Topic shares can overlap; they are not sentiment or coding-accuracy scores.
- **Privacy protections have limits.** Suppression does not provide differential privacy or guarantee protection across linked releases and outside information. Review reports before external sharing.

## For contributors

The latest hosting revision passed **116 Python tests**, including tests with the private reference workbook supplied locally. Live checks also covered synthetic Excel/CSV uploads, report validation, visitor isolation and clearing. These results describe the tested revision, not every future change.

From the project folder, create an environment and run the checks:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
node --test tests/dashboard.test.cjs
```

Node.js is required only for the frontend test command. On Windows, use `py -3.11` to create the environment and `.\.venv\Scripts\python.exe` afterward.

To include an authorized reference workbook in local tests:

```sh
.venv/bin/python -m pytest -q tests --survey-workbook /path/to/survey.xlsx
```

Reference-workbook tests are skipped when a workbook is not supplied. Keep workbooks, private audits and credentials out of Git. Preserve the source revision, input/settings fingerprints and environment when preparing a reviewed release.

The hosted service currently deploys from **`render-hosting`**, with automatic deployment disabled. Updating master alone does not update Render; its hosting branch must be updated and a deployment explicitly triggered. GitHub Pages is a separate deployment. See the [hosting guide](docs/RENDER.md).

## AI use

Claude helped develop prompts for Codex, suggest design improvements, and discuss project roles. Codex supported implementation, debugging, testing and documentation.

The application makes no live language-model requests for survey statistics or comment classification. Python functions calculate the numerical results; a deterministic codebook assigns comment topics. See the [AI process record](docs/AI_PROCESS.md) for examples, corrections and validation practices.

## Troubleshooting

| Issue | What to do |
| :--- | :--- |
| The hosted page takes time to open | Allow the free service to wake, then refresh if needed |
| The service is at capacity | Wait for an active session to clear or expire, or run locally |
| A survey will not load | Check the 5 MB hosted limit, worksheet name, supported export headers and response IDs; at least 10 usable responses are required |
| Excel/CSV asks for a local server | Use the Render application link above, or start the local launcher; GitHub Pages handles aggregate JSON only |
| The report is illustrative | Check the synthetic/survey label and choose your authorized survey |
| A result is withheld | Inspect the privacy explanation; do not lower thresholds just to display it |
| Local setup fails | Check Python 3.11, internet access and write permission for the project folder |
| An upload disappears | Temporary sessions expire and service restarts clear them; upload again if authorized |

## Further reading

[Data options and exports](docs/DATA_OPTIONS.md) · [Backend methods](docs/BACKEND_GUIDE.md) · [Render hosting](docs/RENDER.md) · [GitHub Pages](docs/PAGES.md) · [Validation record](docs/VALIDATION.md) · [Submission checklist](docs/SUBMISSION_CHECKLIST.md)

Asset attribution and license information are retained in [`dashboard/assets/`](dashboard/assets/).
