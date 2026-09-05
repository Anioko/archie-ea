# QA coordination board

## Correction requiring verification

F500-061 initial handoff incorrectly described the canonical model type field as archimate_type. Direct inspection of app/models/models.py proves the mapped column and constructor field is **type**, and to_dict exports type. Earlier 13 passing tests used an incorrect field double and do not verify the production repair. Codex is correcting the implementation, adding a model-column assertion plus canonical JSON type input cases, and rerunning. No affected repair has been deployed. Preserve this as a test-quality failure rather than reporting the earlier green result as closure.

Codex coordinates integration, shared ledger updates, independent browser retests and release approval. Claude Code and Aider may implement bounded assignments; a worker's passing tests do not close a defect.

## Ownership and workflow

- Claim a named assignment before editing. Do not change another worker's files.
- Reproduce the failure, implement the repair, add outcome regressions, and report commands/results plus remaining gaps.
- State transitions: assigned -> reproduced -> implementation ready -> independent retest -> deployed retest -> closed. Failed retests reopen the assignment.
- Workers do not edit the shared findings ledger, stage, commit, push, deploy, access production data, or install dependencies. Codex handles integration and records evidence.
- Use isolated test data. No production credentials or confidential user records in prompts or reports.
- Stop after the bounded assignment; do not expand into unrelated refactoring or delegate additional agents.

## Active assignments

### Claude Code: independent repair review dispatched after account switch

Owner reported signing into a credited account. Local auth check confirmed the requested account matches, logged in via claude.ai with Max subscription. Started a separate bounded review without disturbing the owner's existing interactive session. Prompt: docs/qa/claude-review-task.md. Output ownership: docs/qa/claude-repair-review.md only. Source changes, commits, deployment and duplicate full-suite execution are prohibited. The prior 429 below belongs to the previous account/attempt, not this new dispatch. Review result remains pending.

### Claude Code: F500-061 architecture import/export

Dispatch attempted using the existing signed-in account, with no model override, restricted permitted commands and an API budget ceiling. Session 4c71d545-eeef-4bf3-b61b-3ea7766beb28 returned HTTP 429: out of usage credits. Zero model tokens and zero reported cost; no work performed. Assignment is ready but not running. Codex may resume these files until a worker accepts the assignment. Do not assume the handoff succeeded.

Own only:

- app/modules/architecture/services/architecture_import_export_service.py
- tests/test_architecture_export_contract.py
- docs/qa/claude-f500-061-result.md

Evidence: CI 33927686496 server log reports CSV export AttributeError: canonical ArchiMateElement has no element_type. Service imports the canonical class but reads element.element_type and constructs imports with element_type=. Canonical field is archimate_type. JSON export uses to_dict; inspect its real interchange shape before implementing import compatibility. Preserve CSV schema compatibility and tenant scoping. Do not invent data or silently discard relationships while claiming a complete round trip. Report any broader route/content-type/relationship gaps outside your ownership for the coordinator.

A new focused test exists but no successful red reproduction has been claimed: initial attempt hit unrelated ORM mapper configuration; latest test hydrates a mapped row without configuring unrelated relationships. Coordinator relinquishes these two source/test files to Claude for this assignment. Read AGENTS.md and applicable instructions. Use shared DB fixtures for new integration tests; do not target any default or production database. Run bounded regressions available locally, explicitly report skips and failures, and stop with a result file. No full test-suite duplicate run.

### Codex: integration and verification

Own all other currently modified files, the shared findings ledger and release report. Run one coordinated static/full CI qualification rather than duplicating it across workers. Independently test actual browser outcomes, including populated downloads, before closure.

### Aider: F500-061 proposal returned; coordinator review in progress

Owner authorized Aider after the Claude quota failure. Dispatched one bounded request through the existing OpenRouter credential using openrouter/deepseek/deepseek-chat. It has begun returning a patch proposal. Only the import/export service and focused test were supplied, repository map disabled, dry-run enabled, automatic commits/tests/lint/update checks disabled. It does not own production or shared-ledger writes. Prompt: docs/qa/aider-f500-061-task.md. Coordinator will review and apply the proposed patch with independent tests. No credit purchase or auto-top-up authorized; no hard dollar ceiling was supplied by owner. Report actual returned cost when available. Claude is not concurrently working this assignment.

Completed single call: 4.5k input tokens, 917 output tokens, reported cost **$0.00089**. No edits applied by Aider (dry-run). Review accepted the canonical-field mapping direction but rejected a silent blank export fallback and missing conflicting-type rejection. Aider omitted requested import regression implementations and explicitly did not execute tests. Codex added 13 focused CSV/JSON contract cases and is running red/green verification. Full database, browser download and relationship round-trip gaps remain open.
