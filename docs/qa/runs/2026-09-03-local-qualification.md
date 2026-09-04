# Local qualification run — 3 September 2026

Candidate base: `2f7fdc5c121890f3266d3e3ea6e55f6bdac89331`

Worktree: `codex/fortune500-readiness`

Host: Windows 11, Python 3.13, PostgreSQL 12 diagnostic database

Authority: diagnostic only; final acceptance requires the final Git SHA in CI.

## Results retained

| Check | Result | Interpretation |
|---|---:|---|
| Collection | 4,132 tests | Suite inventory established |
| Static verifier | 36 passed, 0 failed, 0 skipped | Green after remediation |
| Focused remaining-failure cohort | 16 passed | Authorization, escaping, timeout, and adversarial emitter checks green |
| Clean-database accessibility blocker check | 1 passed | Eight persona/page axe traversal completed without a new serious/critical regression |
| Smoke database fail-closed contract | 3 passed | Missing or conflicting database URLs now stop qualification before browser launch |
| Adversarial smoke cohort | 11 passed | Nonexistent IDs, hostile pagination, and nine persona route sweeps green on explicit database |
| Main Chromium smoke suite | 144 passed, 3 failed, 4 skipped, 6 xfailed, 21 deselected | Product candidate remains red; F500-006/F500-007 opened and non-passes under audit |
| Non-browser full diagnostic | 3,956 collected; four failures observed before remediation | Original failure evidence retained; full final rerun still required |
| Isolated Chromium remediation retest | 12 passed, 0 failed, 0 skipped | Platform-admin sidebar (1), transformation responsive flow (2), journey home/screenshots (8), and tenant-leak assertion (1) verified against dedicated PostgreSQL on port 55432 |
| Typed ARB remediation slice | 4 browser cases + 1 template contract passed | Architecture Model canonical submission, Return for Evidence and cycle-2 resubmission, historical lock, corrupt-evidence HTTP 503/no-zero state, and decision form/server field contract verified |
| Full typed ARB Chromium retest | 24 passed, 2 xfailed, 0 failed, 0 skipped | Expected failures reduced from six to two; F500-010 remains open and the suite is not release-green |
| Final typed ARB Chromium qualification | 26 passed, 0 failed, 0 skipped, 0 xfailed | All four governed subject types execute canonical create/replay journeys; F500-010 verified locally |
| Typed ARB service/route/template regression | 439 passed | Independent authorization, tenancy, decisions, evidence, ingress, compatibility, read-model, and template coverage green |
| Expanded static verifier | 42 passed, 0 failed, 0 skipped | Six previously orphaned governance/AI checks now execute: evidence 29/29, role coverage 7/7, four AI safety checks 0/0 |
| Governance-checker proof cohort | 6 passed | Seeded bad/good cases and provenance contract confirm the newly registered gates can fail for their intended defects |
| Rebased candidate-wide verifier (`e69ebbcf`) | 49 passed, 1 failed, 0 skipped gates | Static/dependency/boot/schema gates green; test gate red: unit 3,933 passed/4 failed/22 errors/8 skipped, smoke 177 passed/1 skipped |
| Runtime-role root-cause retest | 36 passed, 3 PostgreSQL-version skips | All 26 failures/errors were caused by missing `pgcrypto` in newly-created PG12 scratch databases; fixture now provisions the declared prerequisite before privilege fencing |
| Runtime-role final local retest | 39 passed, 0 skipped | PG12 and PG16 behavior branches now make applicability explicit; complete security-hardening module is locally green |
| Skip-hygiene focused cohort | 26 passed before approval-summary correction; follow-up AI cohort 4 passed | Maintenance writer removed from normal collection; OEF offline assertion named honestly; navigation and PostgreSQL branches assert applicability; Windows PDF render is collected only on production-like Linux; live-provider AI evaluation remains an explicit external blocker |
| Full corrected Chromium smoke suite | 177 passed, 0 failed, 0 skipped, 0 xfailed | Accessibility, adversarial probes, persona journeys, authorization, interaction reality, responsive flows, console/error hygiene, transformation and typed ARB all green |
| Diagnostic WebKit compatibility | 56 passed | Critical cross-browser journeys green on the pre-final candidate |
| Diagnostic Firefox compatibility | 55 passed, 1 failed | Exposed three CSP-blocked inline drag handlers on application import; corrected with external event listeners and a source-level regression test |
| Full instrumented Firefox compatibility | 56 passed, 0 failed, 0 skipped | Exact cross-browser CI command passed locally in 6m39s; the prior CI-only `Object` console failure did not reproduce, so final Linux rerun remains required |
| Linux Chromium exact-SHA browser run | 155 passed, 2 failed | Both failures are the accessibility ratchets reporting four serious `/ai-chat` color-contrast nodes; F500-014 opened and release remains red |
| Browser evidence diagnostics | 4 contract tests passed | Firefox console objects now retain serialized arguments/source locations; axe regressions now retain exact target selectors |
| Deferred Firefox error diagnostics | Failing-before/passing-after runtime contract; 5/5 diagnostic tests passed | The earlier init script was an uninvoked function expression. It is now installed as an IIFE and captures/rethrows timer-callback exceptions with Alpine expression and element context before Firefox flattens them. No production behavior changed. |
| Firefox exception attribution | Local exact-matrix reproduction: 55 passed, 1 failed; diagnostic contracts 7/7 passed | Equipment retained `{isFromCancelledTransition: true}`, Alpine's benign superseded-transition sentinel. The earliest test listener now prevents only that exact signal; a non-sentinel plain-object rejection remains a captured failure. Complete matrix retest pending. |
| Firefox cancellation-sentinel retest | 56 passed, 0 failed, 0 skipped in 392.93s | Complete compatibility command passed after the exact-sentinel filter; arbitrary non-sentinel rejection coverage remains green. Final Linux CI required. |
| Exact-SHA PostgreSQL 16 full suite (`6f017c6a`, run 33810262875) | 3,985 passed, 2 failed, 0 skipped, 0 xfailed; 3,987 collected; 2,398 routes exercised; 27m51s | Both failures were test defects: a stale contradictory Governance Gates assertion and a 150ms wall-clock lease race. Corrected combined root retest passed 13/13. Coverage was 29.07% (83,157/286,097 statements); branch coverage is not configured. |
| AI-chat contrast remediation | Failing-before/passing-after token contract; 10 focused tests passed | Four default Expertise Areas chips moved from the approximately 4.26:1 primary base-on-tint pair to the approximately 6.14:1 info emphasis-on-tint pair required by DESIGN.md; Linux axe retest pending |
| Post-full-CI remediation cohort | 26 passed, 0 failed, 0 skipped | Platform-admin URL construction, Governance Gates read-only authorization, rendered-link assertions, Waitress-backed SSE headers, four CSP browser checks, CI browser provisioning and Firefox diagnostics all pass against the isolated qualification database |
| Post-full-CI static verifier | 42 passed, 0 failed, 0 skipped | Every static, design, tenancy, AI-safety, template, JavaScript, CSS, integrity and CSRF gate passed after the remediation cohort |
| Immutable release/deploy contracts | 10 focused tests passed; both deploy scripts parse | CI build-once digest manifest, source-free production Compose overlay, host identity verification and previous-digest rollback implemented; execution evidence awaits final CI artifact and production rehearsal |
| Isolated scale microbenchmark | 10,000 applications, 50,000 ArchiMate elements, 500 solutions, 1,000 users; 20 samples/query; all three budgets passed | p95: applications 17.4ms, elements 54.9ms, solution count 4.3ms. Synthetic rows verified removed and scratch database dropped. Does not substitute for concurrent HTTP/soak testing. |

## Invalidated run

An initial 178-test browser run produced four accessibility setup errors and
eleven adversarial failures. It is not product evidence: `TEST_DATABASE_URL` was
unset and the application used the long-lived fallback `archie_test` database.
The first isolated failure was inability to authenticate the freshly seeded
procurement user. The harness itself warned the database was untrustworthy.

The equivalent accessibility check passed when both `TEST_DATABASE_URL` and
`DATABASE_URL` explicitly named `archie_f500_run2`. This proves the cluster was
environmental, but also exposes a fail-open harness defect tracked as F500-001.

## Current release position

Not ready. Local static and browser evidence is green and the immutable
artifact path is implemented, but the final Linux/PostgreSQL 16 CI, produced
image digest, performance/soak, recovery/rollback, manual accessibility,
usability research, penetration testing and production deployment evidence are
not yet complete for one immutable release commit.
