# Live release and browser retest — 5 September 2026

## Release identity

Read-only inspection of the running `archie-ea-server-1` container on the application host confirms:

- OCI revision: `02bc01c55f76d9c179b46e64d640fe529ab8d5d9`.
- Image: `ghcr.io/anioko/archie@sha256:64d3b5d1010963de772b7a2216312c178f55ec01daa42ba1b5460b54a12114ff`.
- The host checkout is also at that revision.
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

Inspected every container image reference, then removed four specifically identified unused legacy local build images, without force: `483294931b8f` (database ACL), `b0c28597e63a` (database bootstrap), `d7982285037c` (schema deploy), and `e1c8db7985ee` (worker). These were image/build artifacts, not database volumes or records. Current/recoverable release images, all containers and database backups were retained. The deleted local builds would need rebuilding if wanted again. Measured free space afterward: **34 GB**, root usage **57%**; existing server and database remained healthy. Retry is in progress; do not infer deployment success from this preflight remediation.
