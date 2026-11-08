# AI-assisted implementation record

This is a factual working record for the team to adapt into the required one-page AI appendix. It does not claim human review, organizer approval or independent manual coding that has not happened.

## Tools and purpose

OpenAI Codex assisted with reviewing the current master source, mapping the case brief to missing functionality, implementing the complete report pipeline and local workflow, drafting controlled evidence-linked recommendation templates, writing tests and preparing a manual-only Pages workflow. The application itself makes no live AI/LLM requests and does not upload comments to an AI service. Comment classification is deterministic keyword coding.

## Representative requests

- "Use current master as the reference. Identify missing steps between the survey workbook and the dashboard-ready report."
- "Create backend-fixes from master. Implement the report workflow and validation. Do not push, merge or publish. Do not implement optimization or efficiency changes."
- "Test actual CSV/XLSX ingestion, privacy guards, missing questions, source preservation, report references and the supplied reference-workbook counts."

## Refinement and limitations

Keyword topics are mentions, not sentiment or a reliable request classifier. For example, both "more examples" and "no more examples please" mention examples; treating both as requests for more practice would be an error. The implementation therefore exposes topic labels and coding coverage, keeps source-row locators private, labels recommendations as drafts, and explicitly asks staff to check negation, non-English and unmatched answers. Tests also ensure "nothing about the crisis was explained" is not mistaken for a no-change answer.

An initially drafted privacy test wrongly expected private comment/ID text to appear in the quality audit. The test was corrected to place its sentinel in an unfamiliar county label, where private normalization diagnostics legitimately retain it. Comments and IDs are not intentionally copied into either public outputs or the comment-review locator list.

Browser validation also caught a new demo button losing its click binding after the main report was replaced. The binding was moved into the existing main-control setup and the synthetic-to-survey switching test was repeated successfully. A clean first-launch check caught a managed-Python path issue; resolving the interpreter before creating the environment corrected it.

## Validation evidence

Existing frozen-reference tests compare calculations against the provided original workbook and known counts. New tests check the complete generated report against the same paired counts, topic denominators, absence of sentinel private labels in aggregate JSON, suppressed numeric fields, nested-cohort protection, missing-question semantics, source preservation and static-site allowlisting. The frontend separately checks schema references, suppressed states and metadata. Exact results and browser/platform limitations are recorded in `VALIDATION.md` after execution.

## Human work still required

Record actual human review of a privately selected comment sample, any codebook changes and disagreements, final recommendation revisions, data-owner disclosure approval, and anonymous submission checks. Include only true review actions and results in the submitted appendix. AI assistance and passing tests are not substitutes for those approvals.
