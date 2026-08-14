# P0 wave — design-review defect fixes

Source: internal product design review (10 Aug 2026). Branch: `fix/design-review-p0-wave`.
Every root cause below was observed in the running app; nothing is speculative.

## Global Constraints

- `TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5439/archie_test` (PostgreSQL enforced; SQLite raises).
- New behaviour needs a test. Write tests against the shared fixtures in `tests/conftest.py`
  (`db_session` rolls back automatically; `app` is session-scoped; `make_org`/`tenant_ctx` for tenancy).
  Do NOT copy the legacy module-scoped `app` fixture pattern. Follow `tests/test_tenant_isolation.py`.
- SQLAlchemy 2.0: raw SQL must be wrapped in `db.text(...)`.
- Null display is `—`, never a fabricated `0`. Never invent data (fabricated-data gate enforces this).
- Verification before claiming done: `python scripts/verify.py --tag static` must stay green, plus the
  test file(s) you added: `pytest <your test file> -q`. Do not run the full suite per task.
- Never raise a number in `verification_baseline.json`. Never run `flask recreate-db`.
- Stage files individually (`git add <file>`), never `git add -A`. Multi-line commit messages via
  `git commit -F- <<'MSG' ... MSG` (Git Bash heredoc). Conventional prefix, e.g. `fix(ea-workflows): ...`.
- Tenancy: models with `TenantMixin` are auto-filtered in request context — do not hand-add
  `organization_id` filters to ORM queries on those models.

## Task 1 — `/ea-workflows/journeys` 500s on a None sort key

**Repro:** authenticated `GET /ea-workflows/journeys` → 500.
**Root cause:** `app/main/routes_ea_workflows.py:770` — `for iter_num in sorted(iterations.keys())`
raises `TypeError: '<' not supported between instances of 'NoneType' and 'int'` because at least one
iteration key is `None` in real data.
**Fix:** make the sort None-safe: `sorted(iterations.keys(), key=lambda k: (k is None, k))` (None sorts
last) — read the surrounding loop first and keep whatever presentation order makes sense for a
None/unnumbered iteration; do not drop the None bucket's data.
**Test:** unit-level test of the route (login via shared fixtures, insert/arrange data so an iteration
key is None if feasible; otherwise test the extracted helper directly with `{None: [...], 1: [...]}`).
Assert the route returns 200.

## Task 2 — shared ORM bug 500s six ADM phase APIs

**Repro (authenticated GETs):**
- `/api/ea-workflows/ba/viewpoint`, `/api/ea/phase-a/viewpoint`, `/api/ea/phase-d/viewpoint`,
  `/api/ea/phase-f/viewpoint`, `/api/ea/phase-g/viewpoint` all raise
  `InvalidRequestError: Can't compare a collection to an object or collection; use contains() to test for membership.`
- `/api/ea/phase-g/compliance-matrix` raises
  `InvalidRequestError: Entity namespace for "arb_review_items" has no property "application_id"`.

**Root cause (to confirm):** a query comparing a relationship *collection* with `==`/`in_` instead of
`.contains()`/`.any()` — likely one shared helper used by every phase viewpoint; plus a raw/textual
column reference to `arb_review_items.application_id` that does not exist (check the model for the real
column name).
**Fix:** correct the comparison(s) with `.contains()`/`.any()`; fix the column reference in the
compliance-matrix query against the actual `arb_review_items` schema.
**Test:** one parametrised test hitting all six endpoints as an authenticated user asserting
`status_code < 500` (JSON endpoints may legitimately 200-with-empty or 400 on missing params — the
assertion is "no server error").

## Task 3 — AI chat fails silently in the UI

**Repro:** send any message in `/ai-chat` with a failing LLM backend. Server: `POST
/ai-chat/message/stream` returns 200 and persists an assistant message
"The AI request couldn't be completed. See the error detail below or check Admin → API Settings."
UI: nothing appears — no typing indicator, no error bubble, 15s+ of dead air.
**Fix (all three):**
1. Typing/loading indicator rendered immediately on send, removed when the reply (or error) lands.
2. Whatever the stream returns — including the persisted error message above — must render as an
   assistant bubble; error-flavoured messages get error styling and a link/pointer to Admin → API Settings.
3. Client-side timeout (~30s): if no stream event arrives, stop the indicator and render an error
   bubble (real error text, no fake content — CLAUDE.md "render the error").
**Where:** `app/modules/ai_chat/` routes/templates/JS (guardrails module is the live one). No
`console.log` in shipped templates; notifications via `Platform.toast` if needed.
**Test:** server-side — assert the stream response for a failing backend actually carries the error
event/message (mock the LLM client to raise). UI behaviour verified manually via a short Playwright
run (chromium is installed; see `tests/smoke/` harness for patterns, but a scratch script is fine —
document what you observed in your report).

## Task 4 — AI-backed endpoints block indefinitely

**Repro:** `GET /api/ea-workflows/sa/application-patterns` hangs a worker indefinitely (stalled a
10-minute crawl twice). `GET /dashboard/api/applications/merging/candidates` runs 10+ minutes
in-request against the 920-app QA portfolio (duplicate analysis appears O(n²)).
**Fix:**
1. Every outbound LLM/HTTP call in the services behind `sa/application-patterns` gets an explicit
   timeout (≤60s) at the client level; on timeout the endpoint returns a JSON error with an
   appropriate 5xx status — never a hung request, never fabricated fallback data.
2. `merging/candidates`: bound the in-request work — cap the candidate comparison set (e.g. limit +
   explicit `truncated: true` in the response) or move the heavy pass behind an existing background
   job mechanism if one is available. The endpoint must respond in seconds on 920 apps, and the
   response must say when results were bounded (no silent truncation).
**Test:** mock a hanging/slow LLM client and assert the endpoint returns the timeout error; for
merging/candidates assert the response is bounded and flags truncation.

## Task 5 — remaining 500 routes from the sweep

**Repro (authenticated GETs, all 500):**
`/api/ea/workflow-adm-lifecycle`, `/api/v1/capabilities/manufacturing`,
`/integration/api/instances`, `/strategic/api/investment-analysis`, `/strategic/investment-matrix`
(the last is a full HTML page, not an API).
**Fix:** run each locally (dev server on :5000 is running, or use the Flask test client with the
`.env` credentials), read the traceback, fix the root cause. If any turns out to be a genuine
product-decision blocker (not a code bug), report it as BLOCKED with the traceback instead of guessing.
**Test:** parametrised test over the five routes asserting `status_code < 500`.
