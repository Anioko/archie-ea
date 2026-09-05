# QA coordination board

## Current checkpoint — 5 September, candidate 18d52beb

Ready for next candidate checkpoint: independent roadmap three-engine run **9 passed**, CSS check green/unchanged. Local static process 77784 completed **44 passed / 0 failed / 0 skipped**; it ran concurrently with edits, so immutable full CI still required. Candidate now also includes composition add/edit (27 local composition/governance cases), strengthened census and real-click journeys.

F500-068 isolated runtime results: CI33967988526 at aa2cebe0 measured Gunicorn22 and23 each **73/80 success, 7 connection failures**; Gunicorn26.2.0 **80/80 success, 9 worker PIDs, zero failures**. Candidate dependency floor is now26.2.0 and regular CI adds the real recycling gate. Production unchanged. Backend CI must install all three browser engines because the new non-smoke roadmap regression actually executes all three.

18d52beb main Chromium is terminal **193 passed / 1 failed / 24 deselected**: same roadmap hidden-overlay interception as Firefox/WebKit. Census/adversarial did not execute after that failure. Backend still under observation; no cancellation/restart inferred from polling.

Latest evidence: 64825fe5 main Chromium completed **194 passed**, and old census **11 passed**. Retained JUnit explicitly includes both populated CSV/JSON downloads and all eight governance open/cancel/save/reload cases without failure. Adversarial **12 failed / 1 passed / 0 skipped**: the same three 503 endpoints plus enterprise-architect ConnectionError now on /strategic/api/compliance-analysis (not the prior relationships route). Cause of the connection failure remains unproven; no retry or waiver applied. Backend still under observation.

Connection-failure lead, not yet proof: retained smoke-server-32813.log lines 11085–11089 show worker 10585 recycling at max_requests nr=10048 immediately after /strategic/compliance-tracking at 12:52:48; the next /strategic/api/compliance-analysis request is the reported failure, while later personas receive 200. Worker replacement boots seven seconds later. Investigate request/keepalive draining during recycling before treating the endpoint itself as faulty. Do not disable recycling or add blind retries to obtain green.

18d52beb Firefox and WebKit each **63 passed / 1 failed**. Ordinary Add Work Package click is intercepted by the hidden roadmap-work-package-modal carrying flex layout. Assigned roadmap-specific template repair, focused real-browser tests and report to worker; no shared modal/CSS ownership. This is newly exposed failure evidence, not permission to revert to synthetic clicks.

Composition independent coordinator run: **27 passed** (14 composition + 13 governance) in Chromium, with disclosed network boundaries. CSS check completed green, unchanged 1ac67799 fingerprint. Real full-app composition cases remain unexecuted pending CI. No deployment or defect closure.

Follow-up harness defect F500-066: real Chromium controlled HTTP navigation reproduced three false-green census outcomes (403/404/500 required pages silently skipped). Coordinator changed the actual measurement loop and gate to retain unmeasured paths and fail incomplete coverage, including baseline generation. Four focused cases now pass, including a genuine HTTP 200 positive control. Auth and network responses are disclosed test boundaries; no full-product browser claim. Forced form submission and missing business-outcome assertions remain separate census limitations, explicitly stated in its docstring. Full CI will need to run against the resulting new checkpoint.

Composition full-app tests added at tests/smoke/test_blueprint_composition_controls.py: ordinary-click open/cancel/Escape and real application picker → POST → reload → edit → PUT → reload/persisted API assertions, exact-row cleanup. Two cases collect and lint passes; execution pending test database/CI. Worker still owns the editor implementation and focused tests.

Full CI 33967077472 is running for exact candidate 18d52bebf02d27a72fdbc3e8c4c523d09c0d348b. Previous candidate 64825fe5 run 33966263332 has nine completed successful jobs; its Chromium job has reached adversarial probes and backend coverage is still running. Neither candidate is deployed or release-approved.

Probe diagnostics worker returned; coordinator inspected the diff and independently ran tests/test_probe_error_diagnostics.py: 15 passed. This only improves bounded failure explanations; 503/connection failures still fail and baselines/timeouts are unchanged. No claim that the underlying failures are repaired.

Live settled Chrome check of /solutions/32: + Component under Solution Composition leaves the page unchanged, with focus on the trigger and no editor. Source calls openEntityModal('composition'), which has no editor branch. No production data written. Composition editor worker exclusively owns blueprint.js, blueprint.html insertion, a new composition editor partial, focused Chromium tests and its result report. Coordinator owns ledger, CI, independent review and full-app tests. Other generic editor types remain unqualified.

## Correction requiring verification

Update: e8e16687 contains the corrected canonical `type` implementation. Independent local runs passed 17 serialization/import contract cases and 4 actual export-response lifecycle cases. Real PostgreSQL import/export and browser download cases are in CI 33965073124, not yet qualified. The false-positive test episode below is retained as history, not the current implementation state.

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

Newest branch checkpoint: **18d52bebf02d27a72fdbc3e8c4c523d09c0d348b**, committed/pushed to QA branch only. Includes F500-064, its nine passing focused/rendered-browser tests, the pending real-DB route case, and stronger procurement/application/roadmap/login clicks. No CI dispatched for this commit yet. Existing run 33966263332 continues to test immutable **64825fe5**, not the new branch tip. Its main journeys passed; census is still running. Main/production unchanged.

CI 33966263332 at 64825fe5: the **Run archetype journeys** step is now explicitly SUCCESS. The broader interaction census is running; adversarial and backend completion still required. Do not equate this step with whole-product qualification. The procurement fix and stronger click tests are being checkpointed separately; their full database/browser run remains pending.

Prior candidate e8e16687 / CI 33965073124 is now terminal FAILED. Backend: **4281 passed, 1 failed** in 34m18s, with the sole failure in the real PostgreSQL CSV export/import test: missing ArchiMateElement.created_at. This independently confirms the same CSV defect seen in the browser and corrected in 64825fe5; it is not an additional unrelated repair. Route-verification enforcement after pytest did not run because pytest failed. New candidate 64825fe5 / 33966263332 remains running; do not transfer old-candidate passes into its qualification.

Procurement verification follow-through: CSS rebuild comparison passed unchanged. Added tests/test_procurement_compliance_database.py using real Flask routes, real users/organizations and shared rollback/login fixtures; no route/query doubles. It remains unexecuted locally because no test PostgreSQL is configured and is not in 64825fe5. Do not count it as a pass. Candidate 64825fe5 now has nine successful CI jobs including Firefox/WebKit; main Chromium journeys and backend suite are still running. No release promotion.

F500-064 fixed locally after live reproduction: empty licence portfolio no longer fabricates 0% utilization. Four failing boundary/template cases reproduced before repair; nine tests now pass, including two actual Chromium rendered-template checks. Positive entitlement/zero consumption still reports 0%; unavailable denominator reports an em dash and no fabricated progress bar. Not committed, in CI, or deployed. Candidate 64825fe5 currently has seven successful CI jobs; backend and three browser jobs remain pending/running. Stronger click tests and this procurement repair belong to the next candidate, not that run.

Interaction-evidence audit expanded: application-manager Save changes and roadmap add/create/edit/save/delete now use ordinary actionable browser clicks, as does the shared archetype login helper. Previous form.submit(), dispatch_event and force=True paths could bypass reachability or validation. Assertions on persisted results remain intact. These two modified test files are **not yet executed or included in candidate 64825fe5**. Existing green runs therefore do not prove these stronger button contracts. Other standalone login helpers still use synthetic events and require follow-up; no whole-suite click coverage claim.

Local static run 70851 completed **44 passed, 0 failed, 0 skipped**; database unavailable, so this is static qualification only. Live Chrome survey: module directory displayed 103 entries (not asserted to be unique modules); Licences navigation, New Licence form opening, and Cancel back to the empty register verified without saving production data. Procurement smoke previously bypassed visible buttons via native form.submit(); coordinator changed contract/licence journeys to click Create contract and Record licence. This stronger test is unexecuted and not in 64825fe5; no claim of saved procurement outcomes from the live navigation check.

Candidate checkpoint: committed and pushed **64825fe57b782622fd02ce32e81d4cca7d4c9f5b** to codex/fortune500-readiness only. Full CI dispatched as **33966263332** (https://github.com/Anioko/archie-ea/actions/runs/33966263332). Includes eight real full-application governance cases and the repaired CSV download. This is a test candidate, not release approval. Main and production unchanged. Earlier e8e16687 run 33965073124 retains its failed CSV evidence; its backend job was still running at dispatch and was not cancelled. Local static session 70851 remains under observation; no green result claimed.

Latest local results: export serialization/import/response rerun **22 passed, zero skips**. Governance partial Chromium suite **13 passed** after adding malformed-picker-response coverage (red reproduced before fix). The real browser download test now reports an HTTP error/page response directly rather than masking it as a download timeout. Static verification is still executing (session 70851); CI backend at e8e16687 remains in progress while Chromium main is failed. No active repair workers, no checkpoint commit/deployment yet, and no claim that database/full-page tests passed.

Current integration blocker: e8e16687 Chromium main completed 185 passed / 1 failed / 24 deselected. The CSV download failed with actual server AttributeError for absent created_at (400 response); JSON download passed. Census/adversarial steps did not execute. Root added absent/present timestamp regression (one failed, one passed before repair), corrected serialization to leave the unknown date empty without inventing a timestamp, and launched the 22-case export regression rerun. Governance + availability batch is now independently 24 passed, zero skips. No deployment or complete qualification claimed.

Follow-up status correction: resumed Claude session terminated with budget_exhausted after context loading, before completing work. Reported list-price usage $2.64164975 despite a $2 threshold; this flag is not a hard billing cap. Do not resume that large context again. No Claude worker is currently running. Codex took ownership back, reproduced missing principle type filtering, unsafe saved/refresh recovery, and a delayed save closing a newer editor with real Chromium tests and doubled network boundaries. Local repairs are under final focused rerun. CSS check passed without requiring a rebuild change; full-app database tests remain pending.

Latest checkpoint: both initial Claude workers returned. Availability contracts independently passed 12/12 twice (including the tightened exact JSON 401 assertion); no configured-provider or database claim. Governance partial tests independently passed 9/9 in Chromium. That repair is **not yet accepted**: a bounded follow-up owns the same implementation/test files to test successful-save/failed-refresh duplication risk, dismissal while saving, and typed principle search. Follow-up instructions: docs/qa/claude-governance-followup-task.md; $2 reported API budget ceiling. Initial governance worker reported $4.55720575 list-price usage, not additional subscription billing. Codex added eight full-application governance cases (four open/cancel/Escape/focus and four actual save/reload/persisted-list reads); these are not yet run against the test database.

Browser evidence correction: F500-063 Add Driver failure was withdrawn after a settled-state observation showed the editor. Add Goal also opens. No repair was warranted by that premature snapshot. All four governance Add controls were then independently reclicked with separate settled snapshots and still showed no editor; F500-062 remains valid. No records were written on the production solution.

CI 33965073124 at e8e16687 currently has nine successful jobs, with backend coverage/tests and the Chromium journey/census/adversarial job still running. It predates this governance repair; neither that candidate nor this repair is deployed. Production remains the restored 02bc01c5 image.

### Claude Code: availability contracts and governance editor (separate workers)

- Availability worker returned tests/test_availability_response_contracts.py and docs/qa/claude-availability-result.md: 12 passed, no skips, actual Flask handlers with explicitly disclosed provider/database doubles. Codex is independently rerunning and tightened the unauthenticated assertion to exactly JSON 401 (a redirect must not silently pass). No probe/baseline relaxation. Reported model usage cost $2.01354025 on a list-price basis; not a claim of additional subscription charges. Configured integration/browser checks remain open.
- Governance worker owns blueprint.js, blueprint.html, new _blueprint_governance_editor.html, tests/test_blueprint_governance_editor.py and docs/qa/claude-governance-result.md. Task: docs/qa/claude-governance-task.md; four governance editors only; $5 API ceiling. No deployment or full-suite duplication.
- Codex owns tests/smoke/test_blueprint_governance_controls.py and full-application/database/live outcome verification. Do not edit worker-owned files while their assignments run. An API ceiling limits a CLI run's reported model budget, not a claim about subscription billing.

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
