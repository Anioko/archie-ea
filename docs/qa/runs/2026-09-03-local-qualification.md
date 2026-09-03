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

Not ready. Static and focused regression evidence is green, but the complete
browser suite, full database verifier, Linux/PostgreSQL 16 CI, security jobs,
browser matrix, performance/soak, recovery/rollback, manual accessibility,
usability research, penetration testing, and production deployment evidence are
not yet complete for one immutable release commit.
