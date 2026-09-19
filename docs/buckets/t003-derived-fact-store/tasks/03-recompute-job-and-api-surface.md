# T-003 / Task 03 — Recompute job, on-demand endpoint, provenance expansion (DE-4, FR-1/FR-4/FR-5)

Depends on tasks 01 and 02. Read `00-verification-notes-and-sr1.md` — in particular
its correction #2 about advisory-lock scope, which is binding here.

## Objective
Recompute stale derived facts eventually, per tenant, through the **existing**
tenant-safe scheduler harness; expose exactly two query surfaces — an on-demand
recompute and a provenance expansion — and nothing more.

## Context
- **Extends existing components, creates no harness.** The scheduler is
  `init_scheduler(app)` at `app/_bootstrap/extensions.py:224`, which returns early
  under `app.testing` at `:226-227`. The interval-job registration pattern to copy
  is the typed-ARB waiver job at `:398-405` (`IntervalTrigger`, `id=`, `name=`,
  `replace_existing=True`, `max_instances=1`, wrapped in a try/except that logs when
  registration fails and sets a `*_registered` flag appended to the startup log line
  at `:462-470`). T-002's capability projection at `:413-449` is the most recent
  worked example, including its `app.config[...]` interval with a positive-value
  check; its config default lives at `config.py:148-149`
  (`CAPABILITY_PROJECTION_INTERVAL_MINUTES`, default `"15"`). Add
  `DERIVED_RECOMPUTE_INTERVAL_MINUTES` (default `"10"`) the same way, in the same
  place. Register your job after T-002's block and before `scheduler.start()` at
  `:451`.
- The tenant harness is `app/jobs/tenant_safe_job.py`: `run_for_each_tenant` (`:285`,
  signature `(app, job_name, func, *, organization_ids=None, use_lock=True,
  on_result=None) -> JobRun`), `tenant_scope` (`:167`), `job_lock` (`:199`, its
  `pg_try_advisory_lock` at `:231`), `active_organization_ids` (`:259`), and
  `JobRun` (`:88`) whose `succeeded` (`:105`) / `failed` (`:109`) are properties over
  real results and are deliberately never defaulted to zero. `_reset_session()`
  (`:144`) runs `db.session.remove()` between tenants and **must not be bypassed**.
- **Two jobs, two harness entry points, deliberately.** T-002's capability
  projection uses `job_lock` with no tenant context because its writes span tenants;
  this job uses `run_for_each_tenant` because it writes `TenantMixin` rows one
  tenant at a time. Do not change either to match the other.
- **Lock scope — the design decision, made here, binding.** `job_lock` hashes
  `f"archie_job:{job_name}"`, so it is per job *name*, not per tenant, and
  `run_for_each_tenant`'s own lock covers the whole sweep (`:313-318`). Acceptance
  item 9 requires one concurrent run *per tenant* shared between the scheduled and
  on-demand paths. Implement it as:
  - one shared helper returning the per-tenant lock name
    `f"derived_facts_recompute:org:{organization_id}"`;
  - the per-tenant work function wraps its body in
    `job_lock(<that name>, required=False)` and, when not acquired, returns a result
    marked `skipped_locked` rather than a silent success;
  - the **scheduled** path calls `run_for_each_tenant(app, "derived_facts_recompute",
    func, organization_ids=<stale-carrying ids>, use_lock=True)` — its sweep-level
    lock stops three gunicorn workers firing the same sweep;
  - the **on-demand** path calls `run_for_each_tenant(app,
    "derived_facts_recompute_on_demand", func, organization_ids=[org_id],
    use_lock=False)` — sweep lock off so a user request is not blocked by an
    unrelated tenant's sweep, with the per-tenant inner lock providing the real
    mutual exclusion against the scheduled run.
  This reuses the harness's locking; it does not re-implement it.
- The runner and its upsert are task 01's; this job calls them, and does not
  re-derive, re-enumerate tenants or open its own transaction management.

## Constraints
- The job body **is** `run_for_each_tenant(...)`. It never enumerates tenants
  itself, never manages transactions itself, never calls `Query.get()` across a
  tenant boundary. Tenant scope inside `func` comes from the harness; ORM reads on
  `TenantMixin` models add no `organization_id` predicate (double-filtering), raw
  SQL always does.
- Select only organisations with **at least one stale row**. That selection query
  runs outside tenant scope (like `active_organization_ids` at `:259`), returns
  plain ints not ORM objects, and carries `organization_id` in its own raw-SQL
  grouping — nothing may enter an identity map that a later lookup could serve under
  the wrong tenant.
- Registered with `max_instances=1` and skipped under `app.testing` exactly as the
  surrounding jobs are — inherited from the `:226-227` early return, not
  re-implemented with a second `if app.testing`.
- **The on-demand endpoint calls the harness from inside a request, and the harness
  calls `db.session.remove()`.** Capture `organization_id` as a plain `int` before
  entering; hold no ORM object across the call; do not read a detached instance
  afterwards. Verify by test — do not assume Flask-SQLAlchemy's app-context session
  scoping saves you — that the request's own session and `g.current_org_id` are
  intact after the call and that the response renders.
- `POST /api/v1/intelligence/derivation/recompute` is `@login_required` and
  CSRF-protected (it is a write route; the `csrf-coverage` gate is blocking). Body
  `{scope: "tenant"}`; reject any other scope with a clear 4xx, never a silent
  tenant-wide or estate-wide run.
- Errors surface as errors: no `200` on a failure path (`error-signalling` gate), no
  server failure returned as data (`silent-data` gate). A lock-held outcome is
  reported explicitly as `skipped_locked` with a human-readable message, never as
  success and never as a fabricated zero.
- Reads go through task 02's single read accessor, so `stale = FALSE` applies by
  default here too.
- **No query surface beyond these two routes** (NFR-8). The US-1 impact endpoint is
  T-004 — do not anticipate it. Blueprint registers non-fatally via
  `app/modules/intelligence/__init__.py::register(app)`; any template link is
  guarded per `DESIGN.md` §"Guarded nav links".
- Live defects SR-11, SR-12, SR-13 are out of scope.

## Deliverable
1. `app/modules/intelligence/services/recompute_job.py` — `recompute_derived_facts`
   through `run_for_each_tenant`, the stale-tenant selection, the shared per-tenant
   lock-name helper, and the per-tenant work function (upsert, clear `stale`, delete
   no-longer-produced rows) returning a `DerivationResult`.
2. Registration in `app/_bootstrap/extensions.py` following the `:398-405` /
   `:413-449` pattern, with the `*_registered` flag folded into the startup log line
   at `:462-470`, plus `DERIVED_RECOMPUTE_INTERVAL_MINUTES` in `config.py` beside
   `:148`.
3. `POST /api/v1/intelligence/derivation/recompute` (API-7) on a new API blueprint
   mounted from `register(app)` — returns the `DerivationResult`, reports
   `skipped_locked` when the lock is held.
4. `GET /api/v1/intelligence/derived/{derived_id}` (API-2) — expands one derived row
   to each explicit relationship in `chain`, in order, each resolved to its
   source/target with `derived_from`. Tenant-scoped; 404 for another tenant's id,
   not 403 and not a leak.
5. Tests under `app/modules/intelligence/tests/`, plus a `tests/smoke/` addition if
   any control becomes reachable from a rendered screen (the
   `smoke-coverage-on-change` gate is blocking on template/JS changes).
6. The T-003 build report: FR-3/FR-4/FR-5 → DE-2/DE-3/DE-4 → each acceptance item by
   test id; the mutation-proof record from task 02; the recorded `init-db` +
   `reconcile-schema` run from task 01; and the **SR-1 open item, verbatim per
   `00-verification-notes-and-sr1.md`, under its own heading**.

## Acceptance Criteria
1. **(Brief item 8)** `recompute_derived_facts` runs per tenant through
   `run_for_each_tenant`, selects only organisations with at least one stale row
   (asserted: a tenant with no stale rows is not visited), clears `stale`, deletes
   rows the engine no longer produces, and returns a `JobRun` whose `succeeded` /
   `failed` reflect real results — a test forces one tenant to fail and asserts the
   other tenants still ran, the failure is present in `JobRun.failures`, and neither
   counter was defaulted to zero.
2. **(Brief item 9)** Concurrency: with the per-tenant lock held, a second recompute
   for that tenant reports `skipped_locked` and performs no write — not a silent
   success. A recompute for a *different* tenant proceeds. Assert the scheduled and
   on-demand paths resolve to the **same** lock name for the same tenant.
3. **(Brief item 10)** The endpoint is `@login_required` (anonymous → redirect/401,
   asserted), CSRF-protected (a POST without a token is rejected, asserted), returns
   the `DerivationResult` on success, and returns a clear, non-200 message when the
   lock is held.
4. **(Brief item 3, FR-5/API-2)** `GET /api/v1/intelligence/derived/{derived_id}`
   expands the row to each explicit relationship in `chain`, ordered, each resolved
   to source/target with `derived_from`. A cross-tenant id returns 404.
5. **(Brief item 16)** Job-registration parity: the job is registered on the
   existing scheduler with `max_instances=1`, is skipped under `app.testing` exactly
   as its neighbours are, and re-implements no tenant enumeration, transaction
   management or locking that the harness already provides. A test asserts the job
   id is registered when scheduling is active and that `init_scheduler` still
   returns early under `app.testing`.
6. **(Brief item 12)** The recompute loop sets tenant scope explicitly and does not
   rely on `Query.get()` across a tenant boundary; a two-tenant recompute in one
   process writes each tenant only its own rows.
7. **(Brief item 14)** No query surface beyond these two routes is added by L1 — a
   test or a diff review asserts the module registers exactly these two endpoints.
8. The on-demand endpoint completes inside a request with the request's session and
   `g.current_org_id` intact afterwards, and the response renders — asserted, not
   assumed.
9. `python scripts/verify.py` (bare, never `--tag static`) green, no ratchet raised,
   `csrf-coverage` and `boot-health` green, and `gh run list --limit 5` checked
   before the work is reported done.

## Handoff Target
`builder`, then `refuter` as the **L1 gate** — verifying every parent-brief
acceptance item by test id, including the FR-4 stale-never-current test (item 6) and
re-running its mutation proof (item 13). L1 must be green before T-004 (US-1)
begins. Per this repo's "Done means DEMONSTRATED", the two endpoints are not done on
a passing unit test alone: the recompute must be driven end-to-end and its effect
confirmed to have persisted.
