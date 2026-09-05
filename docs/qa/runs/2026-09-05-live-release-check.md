# Live release and browser retest — 5 September 2026

## Release identity

Read-only inspection of the running `archie-ea-server-1` container on the application host confirms:

- OCI revision: `02bc01c55f76d9c179b46e64d640fe529ab8d5d9`.
- Image: `ghcr.io/anioko/archie@sha256:64d3b5d1010963de772b7a2216312c178f55ec01daa42ba1b5460b54a12114ff`.
- At the initial inspection the host checkout was also at that revision. After the failed deployment below it remains at c87d0d1f; the running immutable image was restored to 02bc01c5. Host Git HEAD is not runtime release evidence.
- The browser footer displays `c913b7de`. This is **not a Git revision**. `app/_bootstrap/build_info.py` can fall back to a CSS-content fingerprint when neither an explicit build ID nor Git metadata is available. Do not attribute deployment or passing tests to that footer value. CSS fingerprints cannot distinguish backend-only releases.

The latest candidate is `6cd5ea7eadf780e6f9ff1fff7aff005c04526937`, CI run `33927686496`. Its jobs have started; some remain queued. It is not deployed or qualified yet. The deployed revision is an ancestor of the candidate.

## Direct production browser evidence

Using the existing signed-in platform-admin session, opened `/solutions/32`:

1. The page renders the solution blueprint.
2. Clicked the first visible button named exactly **Link**. No dialog appeared; the intended **Link Elements** heading is absent (count zero).
3. The phase checklist visibly reports **Error loading gate: Maximum call stack size exceeded**.

These are continuing failures under F500-029, not new duplicate findings. No business records were changed. Local or CI evidence for a repair does not close either live failure.

Also opened `/dashboard/overview` and clicked **CTO**:

- Screenshot inspection confirms coloured left edges on the Overview health cards, contrary to the owner's requirement (F500-030 remains unclosed on production).
- Overview reports **Solutions 4**, but **Solution Pipeline** says **No solutions yet**. Assigned independent source diagnosis; this may be a model/query mismatch, not evidence that the four solutions are absent.
- CTO tab successfully changes the visible content to Executive Summary, portfolio metrics and ARB pipeline. It displays **Health Score 42.9** in Executive Summary and **48/100** nearby. This confirms the remaining F500-027 metric disagreement, despite the earlier capability-coverage repair. Assigned the remaining calculation mismatch for repair.

Global search has a positive observed outcome in this session: clicked **Open search**, entered **Legacy CRM**, waited for the matching solution result, clicked that result and confirmed navigation to `/solutions/32`, its exact blueprint heading visible and the search dialog closed. This qualifies that lookup/navigation for this signed-in user and record, not cross-tenant search isolation or all search categories.

## Qualification queue

The earlier `63484700` candidate's Chromium job `101197312910` completed successfully. Retrieved its logs: **178 passed, 24 deselected**, followed by **11 passed** for the interaction census. Named passing cases include the radar persistence journey, RoPA generation, five breadcrumb tests and two solution-blueprint control tests. Its backend job is still running. The 24 deselected tests are not represented as passes; this revision predates the explicit adversarial CI step on the latest candidate.

Cancelled superseded CI runs `33927406443` and `33927185089` to reduce competing work. Their changes are included in the latest candidate. Cancellation is not a passing result. Retained the older running whole-product surveys for their diagnostic evidence; they do not qualify the final candidate.

## Next closure requirements

Obtain green final-candidate CI including the newly wired adversarial cases, build and deploy its immutable image, and repeat the exact live solution controls above. Verify intended results and persistence for mutation workflows. Entire-product, all-role and configuration-dependent qualification remains active; no readiness claim or completion estimate is supported by this checkpoint.

## Dashboard repair checkpoint

F500-027/054/055 now have 22 passing focused regressions in an independent main-agent combined run, including actual Chromium-rendered content. Review caught a remaining unknown-phase denominator error; the canonical score now measures only normalized valid phases, preserving genuine measured zero and returning unavailable when none exist. Pipeline normalization also sums duplicate normalized groups. Database endpoint tests and two full-application browser journeys were added; execution awaits the next CI revision. These focused browser cases do not substitute for those full-application tests.

Local static preflight completed **44 passed, 0 failed, 0 skipped**. CSS rebuild/check is unchanged and current. Because the canonical denominator changed while the preflight was running, compilation and correctness lint were rerun on the final dashboard code and passed. Final immutable-revision CI is still required. Reviewer found no remaining blocking issue; noted a minor whitespace-normalization difference between PostgreSQL trim (spaces) and Python strip (broader whitespace).

## Interim deployment and disk incident

CI `33925480259` completed successfully and produced `c87d0d1fa739a3447f19440553bcd4fc3d9b2112`, digest `sha256:68cd84ccd4a54934cec45c286cee5e7a1e52d1cac49197a48eb0842510a024bd`. This is an interim repair wave for already-qualified solution/card changes, **not final whole-product qualification** and does not contain the newer dashboard-data repairs above.

First deployment attempt failed while pulling/extracting the image, before backup/activation. Root volume had 3.1 GB free before pull and 133 MB during failure. The prior running image remained healthy; no rollback was necessary because it was not replaced.

Inspected every container image reference, then removed four specifically identified unused legacy local build images, without force: `483294931b8f` (database ACL), `b0c28597e63a` (database bootstrap), `d7982285037c` (schema deploy), and `e1c8db7985ee` (worker). These were image/build artifacts, not database volumes or records. Current/recoverable release images, all containers and database backups were retained. The deleted local builds would need rebuilding if wanted again. Measured free space afterward: **34 GB**, root usage **57%**; existing server and database remained healthy.

## Rejected deployment and restored production

The retry completed image download and captured `/root/deploy-backups/db-20260904-231802.sql.gz`. Candidate c87d0d1f passed health/public surface checks but its production-log gate counted five error signals. Deployment exited unsuccessfully and rolled back. The old script did not retain the rejected container's logs before recreating it: the five errors' exact cause is unknown, not waived. F500-058 adds private retained logs and fail-closed capture checks.

While c87d0d1f was temporarily serving, direct browser tests opened and closed Link Elements and Codegen dialogs successfully. However, the phase checklist failed on first load with “API base URL not found”; Refresh loaded Phase A with 0/3. More actions was covered by the governance sidebar at 1280px with the real long solution title. Those failures have reproducing Chromium regressions and local repairs, but neither repair is yet deployed. These observations do not qualify the restored old image.

The watchdog restarted the created application before schema deployment finished at 23:21:10Z. This is a confirmed coordination race (F500-059), not proof of the five errors' cause. Paused its timer during supervised rollback, verified the restored 02bc01c5 immutable image and reopened `/solutions/32` successfully, then restored the timer and confirmed it active. No timer is intentionally left paused.

## New qualification failures

CI 33927686496 ran the previously excluded adversarial suite: **12 failed, 1 passed**. Failures include negative ArchiMate element limits producing 500 (F500-060), three configuration-dependent 503 endpoints, and an enterprise-architect relationship request connection error. The 503 contracts and connection error remain under investigation, not blanket-excluded.

CI 33929021425 at fedac94f ran ordinary Chromium journeys: **179 passed, 2 failed, 24 deselected**. Snapshot inspection identifies incorrect test navigation (solution architect starts on Application, not Overview) and an unsuitable exact-regex metric selector. Corrected the tests while retaining score equality, reload, pipeline and navigation outcome assertions. Rerun is pending; this remains a failed candidate and its subsequent adversarial step did not execute.

Pending local batch also includes capacity preflight, retained deployment logs, watchdog lock coordination, cold phase-checklist initialization, constrained-header controls and bounded ArchiMate pagination. Linux lock semantics, full PostgreSQL journeys and deployed outcomes remain required. Whole-product qualification is not complete.

## Independent follow-up verification

CI 33929021425 has now finished: its backend job 101203627892 reports **4,169 passed** in 34m15s. The run remains **failed** because of the two browser failures above. This backend result applies to fedac94f, not the newer uncommitted batch.

Independent local combined rerun of dashboard health, ArchiMate limits and watchdog checks reports **47 passed, 2 skipped**. The skipped tests exercise real Linux locking and must execute in Linux CI; they are not passes. Source inspection confirms the three adversarial 503 endpoints deliberately report missing LLM configuration, disabled page guide and absent framework seed data. That does not make their enabled workflows qualified: explicit configured/unconfigured contract coverage is still needed. Existing logs record only the relationship request's ConnectionError class, not its cause, so it remains unresolved.

A subsequent 31-case local batch showed both cold-load Chromium cases, both responsive-header Chromium cases and six interaction contracts passing, but deployment tests errored and pytest ended with `OSError: [Errno 28] No space left on device`; that batch is not green. Follow-up disk measurement found roughly 1.5 GB free. No cleanup/deletion was performed. Isolated deployment capacity/log tests rerun with pytest cache writes disabled: **21 passed in 29.81s**. This is a separate run, not a reclassification of the failed batch. Local storage headroom needs monitoring. Static verification is still running at this checkpoint; no new commit or deployment is claimed.

## Delegated export repair and independent review

### Latest evidence superseding the interim results below

Local follow-through: **22 export contract/response tests passed** after the timestamp correction; **13 governance Chromium partial tests passed**, including a newly reproduced malformed-search-response case. Search failures now remain visible rather than becoming an empty successful list. Browser download diagnostic now asserts actual HTTP success/attachment if navigation returns a response. Static verification is running; CI backend remains in progress and full-page governance cases remain unexecuted. These local results do not qualify deployment.

Further checkpoint: Chromium main journeys at e8e16687 finished **185 passed, 1 failed, 24 deselected**. CSV download timed out because the actual handler returned 400: retained smoke-server-38789.log identifies `ArchiMateElement` lacking `created_at`. Earlier serialization double supplied that unsupported attribute, masking a second model-contract defect. JSON browser download passed. Census/adversarial stages did not execute after the main-journey failure. Backend job remains running. Candidate rejected for deployment. New focused absent/present timestamp regression is being run before repair.

Governance/availability independent batch completed **24 passed, zero skips** (12 Chromium partial tests + 12 Flask availability contracts). Three coordinator follow-up regressions cover principle type selection, successful-save/failed-refresh recovery and delayed response preserving a newly opened editor. The test page now declares UTF-8, matching production; its earlier missing charset corrupted message text. Focus assertion now waits for actual focus rather than sampling immediately. These tests do not replace the eight pending real-database/full-page governance cases. CSS check and correctness lint passed. Claude follow-up exhausted its budget before task work; no workers remain running.

- e8e16687 includes the corrected canonical `type` implementation and streamed-file cleanup. Combined local export verification completed **21 passed** (17 serialization/import + 4 Flask response/lifecycle), without claiming database or relationship round trips. There is no remaining file-in-use warning in that passing lifecycle run; the older paragraph below records an intermediate result.
- CI 33965073124 is running on that exact branch candidate, not main or production. Nine jobs passed: secrets, boot, static, dependency CVEs, SAST, schema drift, Firefox, WebKit and Level 10 walkthrough. Backend coverage/tests and the main Chromium journey/census/adversarial job remain in progress at this checkpoint. No deployment attempted.
- Claude availability contracts independently passed **12/12, zero skips**, including an exact JSON 401 auth boundary assertion tightened by Codex. Provider and persistence boundaries are disclosed doubles; configured AI and seeded-framework browser outcomes remain unqualified.
- Claude governance repair independently passed **9/9 Chromium partial tests**. No real database or full-page claim. Review follow-up remains active for save/refresh failure, pending-save dismissal, and principle picker type filtering. Eight full-application governance tests have been added by Codex, pending execution.
- All four production governance Add controls were independently reclicked and checked in **separate settled accessibility snapshots**; no editor appeared. No production data written. The new Add Driver failure report was withdrawn: its immediate snapshot was premature, while a later settled check showed the Driver editor; Goal also opened. F500-063 preserves the correction, not an unfixed source defect.

**Later correction:** the canonical mapped element column is `type` in both normal and fast-init models, not `archimate_type`. The original handoff and 13-case double were wrong; their green result does not prove the repair. Model-column assertions and canonical JSON `type` inputs expanded the suite to 17 cases and reproduced **9 failures / 8 passes** against the mistaken implementation. Corrected service to read/construct `type`, retain legacy CSV `element_type`, and reject conflicting supplied aliases. Combined export/response rerun is pending. Added two shared-fixture PostgreSQL tenant-isolation and element round-trip tests, pending CI. No mistaken repair was deployed.

Export cleanup was separately reproduced as two failures on Windows, then corrected by closing the file iterator before unlinking; all four response cases pass including file presence during streaming and removal after close.

Static run completed **44 passed, 0 failed, 0 skipped**, with database unavailable. It began before the latest export changes, so it is not final-candidate qualification. Final changed export files passed correctness lint and diff checks. Full CI remains required.

Claude's newly authenticated review completed with no source-level hard blocker in reviewed UI/pagination/deployment changes; it ran no tests and did not review export/import. Reported list-price usage: $4.89040825, not proof of additional subscription billing. Two review claims need correction: Overview is in `app/templates/dashboards/overview.html` (plural directory), and Jinja `ignore missing` suppresses a missing template, not arbitrary render errors. The requested real-page CI assertions remain necessary regardless. Reviewer artifact: `docs/qa/claude-repair-review.md`.

Claude Code handoff returned a usage-credit 429 without performing work. Owner authorized Aider through the existing OpenRouter credential. One bounded dry-run call returned a patch proposal for **$0.00089** (4.5k input / 917 output tokens). Codex rejected its silent blank-value fallback and missing conflicting-type rejection, and added the omitted tests. No automatic commit, deployment or credit purchase occurred.

F500-061: retained CI logs reveal populated CSV export reading obsolete `element_type` on a canonical model. The handler returns handled JSON **400**, not an error redirect as initially described; a 5xx-only probe missed the failed user outcome. Focused serialization/import tests reproduced **7 failed, 6 passed**, then **13 passed** after canonical mapping and explicit missing/blank/conflicting-type validation. Tests use disclosed query/session doubles, not full database execution.

Actual export-handler response tests additionally reproduced **3 failed, 1 passed**: JSON labelled XML and unsupported formats returning successful downloads. After correcting MIME type and rejecting unsupported formats, **4 passed**. The handler still emits a Windows file-in-use cleanup warning; cleanup lifecycle remains open. Added two full-application authenticated browser download/content tests for CSV and JSON, pending CI. They test direct download navigation, not discovery/click of an export button. Relationship import/preservation, tenant isolation, full model round trips and production browser verification remain outstanding.
