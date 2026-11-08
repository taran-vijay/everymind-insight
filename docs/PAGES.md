# GitHub Pages and the judge workflow

GitHub Pages serves this static dashboard. It does not run the Python pipeline or process uploaded Excel files. The existing native design, media and animations are preserved.

## Local review, before publication

Generate `reports/report.json`, then use `pages --report reports/report.json --out dist/review`. This produces only the runtime HTML/CSS/JS, original assets/licenses, the selected aggregate as `report.json`, a separate labeled `report.synthetic.json`, and `.nojekyll`. Nonempty output folders are rejected rather than cleared. Raw surveys, audits, source files and Git metadata are not copied. All relative links work under a repository URL prefix.

Nothing in this branch has been published. The real survey-derived report is generated locally under ignored `reports/`, not committed or automatically included in deployment. Review it before any public use. Synthetic data is the deployment default.

## After explicit approval to integrate and publish

1. Check the brief's anonymous-judging rule with the organizer. Personal account/repository URLs, linked commit history, site text and document metadata can identify team members. Use an approved anonymous arrangement. Do not remove required asset-license attribution.
2. Review the aggregate disclosure policy and the linked/repeated reports with the data owner. Never place the raw workbook, private audit or comment-review locators in the public site.
3. If publishing a real report is approved, place only that validated aggregate at `public/report.reviewed.json` in the approved source checkout. Do not unignore the general `reports/` folder or force-add private files. That path is intentionally absent from this branch until a release is reviewed.
4. After an approved integration into `master`, configure Settings → Pages → Source → GitHub Actions. Configure the `github-pages` environment's deployment protections if desired.
5. Manually run **Publish reviewed GitHub Pages package** from `master`, choose `synthetic` or `approved`, and explicitly enable its publication confirmation input. The workflow has no push trigger, refuses non-master refs, and does not deploy without this input. It uses GitHub's configure/upload/deploy Pages actions. The check workflow runs tests but never publishes.
6. Test the deployed URL in a signed-out browser and from a phone. Confirm the report source label, downloads, fonts/media, navigation, cohorts, unavailable states and an invalid JSON selection. No GitHub login should be required for judges.

Official references: [custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) and [creating a Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site).

## What judges do

1. Open the approved website link and scroll to the report.
2. Read the survey/synthetic label and generation date.
3. Select **Download report JSON** to save the report currently displayed.
4. Select **Open report** and choose that JSON. The browser validates and displays it locally. This does not upload data to GitHub or run Python.
5. Inspect agreement, movement, intervals, community tables, calling coverage/intent, themes, recommendation evidence and methods.
6. Optionally select **Load synthetic demo** to explore the separately labeled example. A failed or missing survey report never silently substitutes it.

A JSON validation failure retains the current report and displays an error. Deployment preparation validates the backend release policy too; browser contract validation is not a guarantee that an arbitrary third-party report is safe to publish.
