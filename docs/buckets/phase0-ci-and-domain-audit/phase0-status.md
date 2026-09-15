# Phase 0 status: CI fixes + domain-retirement audit

Branch: `fix/phase0-ci-and-audit` (own worktree, isolated from `main` and
from the other in-flight buckets). All items below are committed and
independently verified against a live local Postgres — not asserted from
the plan alone.

## Domain-retirement audit — COMPLETE

See `domain-retirement-audit.md`. Result: the 7 "overlapping domains" split
into 3 categories (clean flag-flip, shared-utility migration, dead code),
not one uniform kind of work. `integrations` (Category C, dead code) was
retired immediately — commit `964a37bc`.

## `Tests` CI job — 4 of 4 identified root causes fixed and verified

| Root cause | Fix | Commit | Verified |
|---|---|---|---|
| `ErrorEvent` missing `INTENTIONALLY_GLOBAL` entry | Registered with the model's own documented reasoning | `29ee0a15` | `test_tenant_isolation_matrix.py` 4/4 passed |
| Jinja `flask.current_app` undefined in a bare-Environment test | Stubbed `flask.current_app.view_functions`, same category as the existing `url_for` stub | `b9bfb2b0` | `test_procurement_utilization_honesty.py` 9/9 passed |
| `SIDEBAR_LINK_BUDGET` stale since the "Errors" link landed (10 Sep) with no budget bump | Raised 28→30, matching actual measured count | `8bc7fe26` | `test_sidebar_budgets.py` + `test_sidebar_render.py` 32/32 passed |
| `create_programme` AI tool missing from the hand-pinned mutating-tools set | Verified its write path first (`ProgrammeSetupService.create_business_first_programme`, gated by `can_create_programme`), then added it | `e08554b3` | `test_tool_mutates_flag.py` 87/87 passed |

**One correction made along the way, recorded not hidden:** the as-is/to-be
analysis bucket (separate branch `archie-ea-as-is`) had characterized the
`ErrorEvent` finding as "a live tenant-isolation gate regression... a
potential cross-tenant data-leak risk class." That was wrong — made from
the test failure message without reading the model. Corrected in both
`to-be-plan.md` and `refuter-report.md` on that branch (commit `a8485323`)
rather than silently fixed.

## `Browser journeys` CI job — NOT fixed, and I want to be direct about why

This CI job runs Playwright browser tests. This machine has no working
Playwright browser install (Node.js/npm gap, established earlier in this
engagement) — confirmed directly: `tests/test_ai_context_lifecycle.py`'s
`[firefox]` parametrized cases fail with `BrowserType.launch: Executable
doesn't exist at .../firefox-1490/firefox/firefox.exe`, a pure environment
gap, not a code defect. I cannot responsibly diagnose or fix the 5 failing
`Browser journeys` steps from this machine — doing so would mean guessing
at failures I can't reproduce.

**What I did instead:** ran a partial, targeted survey (not the full suite —
running the entire non-smoke suite serially against a single local Postgres
was projected to take multiple hours, an unreasonable use of this session)
and found only environment-caused errors (missing Firefox binary) beyond the
4 fixes above. No further **code** regression was found in what I could
check.

**What this means practically:** the 4 `Tests`-job fixes should be pushed
and CI re-run to get a real signal on both jobs — I cannot claim `Browser
journeys` is fixed, only that its likely root causes (Playwright/browser
environment) are outside what a local fix from this machine can address.
If CI's `Browser journeys` failures turn out to be genuine app-code
defects rather than a CI-runner-specific browser issue, that needs
diagnosing from a machine (or CI itself) that can actually run the
browsers.

## What's still open

- Push `fix/phase0-ci-and-audit` and re-run CI to confirm the `Tests` job is
  actually green now (not claimed here — this used local pytest against a
  portable Postgres, not CI's own environment).
- `Browser journeys` job needs investigation from an environment with
  working Playwright browsers.
- The domain-retirement audit's Category A/B items (account, dashboard,
  admin, ai_chat clean flips; auth, monitoring import-migrations) are not
  started — this bucket covered the audit and the dead-code deletion only.
