# Start here

<div align="center">

### [Open EveryMind Insight →](https://tvworks22.github.io/everymind-insight/)

**Explore training outcomes, participant feedback, and opportunities for improvement.**

No installation is required to view the dashboard.

</div>

1. Open the application and scroll past the introduction.
2. Check whether you are viewing a **survey report** or the **synthetic demonstration**.
3. Explore the results using the report sections, filters, and evidence panels.

> **Development update:** Direct Excel workbook upload is being added. Until that feature is released, the hosted application’s **Open report** control accepts a prepared report JSON.

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

---

## Explore the dashboard

### Overview

Start with the overall picture:

- Agreement before and after training.
- Changes in individual ratings.
- The largest released remaining learning gap.
- Selected feedback topics.
- Participation by training month.

Switch between **Agreement** and **Rating movement** to examine different aspects of the results. Use the interval control to display uncertainty where available.

### Learning Outcomes

Examine the three learning objectives:

1. Identifying mental health challenges and crises.
2. Describing 988 and how it works.
3. Knowing when to use 988.

Each objective includes its calculation base, current agreement, agreement change, remaining gap, and rating movement.

The cohort selector compares results for all usable responses with results excluding quality-flagged responses.

### Community Reach

Explore available results by county, participant role, language, or training month.

These comparisons help identify questions for further investigation. They should be read alongside sample sizes and differences in participant composition.

Participant roles can overlap, so role counts should not be added together as unique people.

### Participant Feedback

Review topics mentioned in open-ended responses and recommendation drafts linked to released evidence.

Topic counts describe mentions—not necessarily positive sentiment, dissatisfaction, or a shared request for a particular change.

Recommendations include proposed actions, responsible roles, and measures for subsequent review. They require staff judgment before implementation.

### Data & Methods

Use this section to understand:

- Response-quality checks.
- Metric definitions and calculation bases.
- Data provenance.
- Privacy-related withholding.
- Analytical limitations.

---

## Understand the results

### Agreement

Agreement means selecting **Agree** or **Strongly agree** on the five-point skill scale.

Each skill uses respondents with valid values for both recalled-before and current ratings. The complete-pair denominator may differ between skills.

### Percentage-point change

An increase from 60% agreement to 80% agreement is **20 percentage points**.

It is not the same as a 20% relative increase.

### Rating movement

| Movement | Meaning |
| :--- | :--- |
| **Higher** | Current rating exceeds recalled-before rating |
| **Unchanged** | Both ratings are equal |
| **Lower** | Current rating is below recalled-before rating |

A participant can move upward without crossing the Agree threshold. Movement and agreement therefore measure different aspects of change.

### Remaining gap

The remaining gap is the share of complete-pair respondents whose current rating remains below Agree.

It identifies a topic worth reviewing, but does not explain the cause of that gap.

### Uncertainty

Agreement metrics use 95% Wilson intervals. Mean ordinal change uses a seeded paired bootstrap.

Intervals communicate statistical uncertainty. They do not remove recall bias, selection bias, or limitations in the survey design.

### Quality cohorts

| Cohort | Included responses |
| :--- | :--- |
| **All responses** | Usable, nonduplicate IDs, including flagged responses |
| **Exclude flagged responses** | Usable IDs without response-quality flags |

Flags are review signals—not proof that responses are false.

Comparing cohorts helps assess whether the overall story depends heavily on flagged responses.

### Calling coverage and intent

Calling-question coverage measures the share of eligible responses with a valid answer.

Mean stated willingness uses only valid answers to that question.

A blank response may mean the question was not asked, was skipped, or contained an invalid answer. It must not automatically be interpreted as unwillingness to call.

Neither measure establishes actual calling behavior.

### Zero, unavailable, and withheld

| Display | Interpretation |
| :--- | :--- |
| **0** | A calculated zero |
| **Unavailable** | Required data or a calculation is unavailable |
| **Withheld** | A privacy rule prevents release |

A withheld result never means zero.

---

## Why this approach is different

### Evidence remains connected to the display

Metrics carry definitions, populations, methods, calculation bases, and source/settings fingerprints.

Recommendation drafts reference supporting metrics and caveats. Reviewers can inspect the evidence rather than relying solely on a written summary.

### Survey integrity is part of the workflow

The analysis checks question headers against an approved registry and detects missing, ambiguous, duplicate, renamed, or reordered questions.

Missing and duplicate response IDs are excluded from respondent headline counts. Quality checks identify responses requiring further review.

### Privacy is considered before release

The reporting layer separates aggregate results from private diagnostics.

It protects small counts, complements, and related comparisons, while excluding raw comments, respondent IDs, exact training dates, and private review locators from the computed dashboard report.

### Future updates use the same analytical framework

New supported survey exports can be processed using the same definitions, checks, and reporting structure.

This supports recurring review rather than limiting the application to a single presentation.

---

## Feedback analysis and human review

Open-ended responses are categorized using a versioned English keyword codebook.

The codebook covers topics in:

- What participants found valuable.
- Suggestions and other topics mentioned in improvement feedback.

A response can match several topics. Topic percentages therefore should not be summed as mutually exclusive categories.

The report also identifies unmatched answers and coding coverage. Coding coverage measures whether an answer matched a topic; it is not an accuracy score.

### Important limitation

“More examples” and “no more examples” mention the same topic but express different preferences.

Keyword coding cannot reliably resolve every instance of negation, ambiguity, or non-English wording. Staff should inspect a private sample, record disagreements, and refine the codebook where necessary.

The application does not claim that this human review has already occurred.

---

## Privacy and responsible use

The computed dashboard report excludes:

- Respondent IDs and raw comments.
- Verbatim quotations.
- Exact training dates.
- Unapproved source labels.
- Private comment-review locators.
- Detailed transition matrices and private diagnostic outputs.

The public-release threshold is at least **10**. Related results may also be withheld when subtraction or comparison could expose a small count.

These safeguards reduce risk; they are not differential privacy or a guarantee against every possible disclosure through linked reports and external information.

Review aggregate outputs with the data owner before sharing them publicly.

---

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

The current implementation separates Python analysis from browser presentation. The direct-workbook upload feature is under development; its final processing architecture should be documented when released.

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

Direct Excel upload is being added and should be treated as an upcoming capability until it is available in the deployed application.

Results remain subject to retrospective reporting, respondent selection, question coverage, ordinal-scale assumptions, and differences in participant composition. Public community comparisons are descriptive and unadjusted.

Human review remains necessary for comment coding, final recommendations, and disclosure decisions.

### Further documentation

- [Backend methods and analyst workflow](docs/BACKEND_GUIDE.md)
- [GitHub Pages and judge workflow](docs/PAGES.md)
- [Validation record](docs/VALIDATION.md)
- [AI-assisted development record](docs/AI_PROCESS.md)
- [Submission checklist](docs/SUBMISSION_CHECKLIST.md)

Asset attribution and license information are retained in [`dashboard/assets/`](dashboard/assets/).
