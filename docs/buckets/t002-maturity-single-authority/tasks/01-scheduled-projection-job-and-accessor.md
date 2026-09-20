# Task 01 — Scheduled projection job, preconditions, staleness signal, and the single accessor

## Objective
Put the **existing** producer (`app/commands/project_capabilities.py`) on the existing APScheduler as a
recurring interval job, evidence both of its preconditions on this database, emit a projection-staleness
signal, and add the one accessor every later reader migration will use — so
`unified_capabilities.current_maturity_level` / `target_maturity_level` becomes a continuously-fresh
authority rather than a deploy-time snapshot.

## Context
Read `docs/buckets/t002-maturity-single-authority/brief.md` in full first, then
`tasks/00-verification-notes.md` — the brief's path:line citations have drifted and 00 holds the
corrected ones. Cite 00's numbers, not the brief's.

Already merged by PR #23, **do not re-do or modify**:
- `scripts/database/deploy-schema.sh:48-53` — one-shot `project-capabilities --apply` on deploy.
- `app/models/business_capabilities.py:601-790` — write-time ORM sync listeners
  (`after_insert` `:778`, `after_update` `:783`, `after_delete` `:788`).
Neither covers the raw-SQL writers at `app/modules/capabilities/routes/maturity_routes.py:177-199`,
`:269-273`, `:313-318`, which never fire an ORM event. That gap is exactly what this job closes.

The component you extend, per ADR 0008, is **`app/_bootstrap/extensions.py`'s `init_scheduler`**
(`:224`), following the interval pattern already there at `:398-405` (`typed_arb_waiver_expiry`), plus
a new module under the existing `app/jobs/` package alongside `tenant_safe_job.py`. Do not create a new
scheduler, a new package, or a second producer.

Why not `run_for_each_tenant`: `_protect_reference_capability_writes`
(`app/models/unified_capability.py:502-517`) raises `PermissionError` for a `UnifiedCapability` whose
`organization_id` differs from `g.current_org_id`, and returns early only when there is no request
context / `g.current_org_id` is None. `run_for_each_tenant` (`app/jobs/tenant_safe_job.py:285`) sets
`g.current_org_id` per tenant and would therefore refuse on the first foreign row. Use `job_lock`
(`app/jobs/tenant_safe_job.py:198-251`) instead — a standalone context manager that takes a
session-level advisory lock on a dedicated connection and sets no tenant context. Note its
`required=True` default raises `JobLockUnavailable` (`:135`), which is how a skip gets recorded rather
than silently swallowed. `run_projection` takes its own *transaction-level* locks
(`ADVISORY_LOCK_ID`, `CUTOVER_ADVISORY_LOCK_ID`, `project_capabilities.py:581-591`) — different keys,
no conflict, but the job must not assume acquisition and must surface `ProjectionBlocked` as a logged
failure, never as success.

The accessor exists so step 2-5 readers repoint at **one** place rather than copying a column name into
a fifth file. Put it on the authority model itself (`app/models/unified_capability.py`) — that is the
existing component that owns these columns; do not invent `app/services/capability_maturity_*.py`.

## Constraints
- **Do not modify `app/commands/project_capabilities.py` at all** — not its SQL, not its signatures.
  The job imports and calls `execute_projection_with_audit` (`:660-689`), whose
  `report_path: str | Path | None` already accepts `None`. If you find a genuine defect in that file,
  **stop and report** — it is co-designed with `app/commands/cutover_capability_tenancy.py` and both
  hold interlocking advisory locks.
- Do not create a maturity table, column or cache. Do not add a REST route, template or query surface.
  This is L0; L0 exposes nothing.
- The job must set no tenant context and must not run inside a request context. Assert this in a test.
- Not registered under `app.testing` — `init_scheduler` already returns at `:226-227`; do not weaken it.
- Interval default 15 minutes, configurable **downward** via an app-config key following the
  `ARB_CONDITION_EXPIRY_INTERVAL_MINUTES` precedent (`extensions.py:392-397`), including its
  non-positive rejection and its `app.logger.error` on registration failure.
- Forbidden territory, untouched: connector configuration, review-queue, ServiceNow
  configuration-loader code (SR-11/12/13).
- New column policy per CLAUDE.md: none here. If the staleness signal needs persistence, it does not —
  emit it, do not store it.

## Deliverable
1. **Precondition evidence, taken before writing code**, pasted verbatim into the build report:
   - `python scripts/verify.py --gate store-agreement` → record the exact count line.
   - `flask --app manage project-capabilities --dry-run` → record whether it raises `ProjectionBlocked`
     and, if so, which of the five reasons. If it names the missing
     `uq_unified_capabilities_provenance` index, install it via the existing
     `app/commands/apply_unified_capability_provenance_migration.py` /
     `scripts/migrate_unified_capability_provenance.sql` and re-run until clean.
     If it names the `CLASSIFIES_PROVENANCE_ONLY_TENANT` condition
     (`project_capabilities.py:620-627`), run `flask cutover-capability-tenancy --apply` first, or
     order the projection after the cutover — whichever this database's state requires. Evidence the
     resolution with a clean `--dry-run` whose report shows the plan non-empty.
2. `app/jobs/capability_projection_job.py` — a small module exposing a callable that, inside
   `job_lock("capability_projection")`, calls
   `execute_projection_with_audit(db.engine, report_path=None, apply=True)` and logs the returned
   payload on the same structured-record path `tenant_safe_job.py` uses (`JobRun.as_dict()`-shaped).
   A contended lock records a **skipped run**; `ProjectionBlocked` and any other exception are logged
   as a failed run, never as success.
3. Registration in `app/_bootstrap/extensions.py`'s `init_scheduler`, `max_instances=1`,
   `replace_existing=True`, `IntervalTrigger(minutes=<config>)`, wrapped in `with app.app_context():`,
   matching `:398-405`.
4. **Staleness signal**, emitted on the same structured path: (a) the count of `unified_capabilities`
   rows whose stored `source_checksum` disagrees with the freshly-computed source checksum, and (b) the
   timestamp of the last successful projection run. Derive (a) from the measurement the projection
   already computes — reuse `_counts` / `_plan` output in the returned payload; do not write a second
   checksum query if the payload already answers it.
5. **The accessor**, on `UnifiedCapability` in `app/models/unified_capability.py`: one entry point that
   returns both current and target maturity for a capability **from the same row**, resolved by
   provenance (`source_table='business_capability'`, `source_id`) — plus a batch form so a list view
   does not N+1. A capability with no maturity returns the T-001 `no_maturity_recorded` reason code
   (`app/modules/intelligence/services/reason_codes.py`), **never `0`**. No caller may bypass it by
   reading the columns directly outside this module and the projection.
6. Tests at `app/modules/intelligence/tests/test_capability_projection_job.py`, written against the
   shared fixtures in `tests/conftest.py` (`db_session`, `app`, `make_org`, `tenant_ctx`) — follow
   `tests/test_tenant_isolation.py`, not the hand-rolled module-scoped pattern.

## Acceptance Criteria
1. `flask --app manage project-capabilities --dry-run` completes without raising `ProjectionBlocked`,
   and its report shows the provenance index present and the plan non-empty. Both command outputs in
   the report.
2. After one job run, every `business_capability` row has a matching `unified_capabilities` row with
   `source_table='business_capability'`, non-null `source_id` and non-null `source_checksum`; a test
   asserts the counts agree and that no projected row has a null checksum.
3. Idempotence: a second run immediately after the first writes zero rows, asserted **both** by row
   count and by the returned payload's `writes.inserted_or_updated == 0`.
4. A maturity change made through the **raw-SQL** path — the statement shape at
   `app/modules/capabilities/routes/maturity_routes.py:177-199` — is reflected in
   `unified_capabilities` after the next job run. A test reproduces that statement shape directly;
   it must not go through the ORM, or it proves the wrong thing.
5. A test asserts `g.current_org_id` is unset for the whole run, and that one pass covers capabilities
   belonging to more than one organisation (use `make_org` twice).
6. Two concurrent invocations → exactly one run and exactly one recorded skip. Never two runs; never a
   silent no-op reported as success. Assert on the emitted record, not on log text.
7. The job is not registered under `app.testing`; a test asserts the job id is absent from the
   scheduler in a testing app.
8. Staleness is observable: a test dirties a source row via raw SQL and asserts the
   checksum-disagreement count rises, then falls to 0 after a run, and that the last-successful-run
   timestamp advances.
9. The accessor returns `no_maturity_recorded` — not `0`, not `None` rendered as `0` — for a capability
   with null maturity. A test asserts this explicitly.
10. **Mutation proof**: disable the scheduler registration, confirm the AC-4 test goes red, name that
    test id in the report, re-enable.
11. `python scripts/verify.py` (bare, not `--tag static`) is green. `pytest -q` green.
12. Diff review confirms zero changes to `app/commands/project_capabilities.py`, no new table/column/
    cache, no new route/template.

## Handoff Target
`refuter`. The refuter must specifically attack AC-4 (raw-SQL path — verify the test really bypasses
the ORM listeners PR #23 added, otherwise it passes for the wrong reason), AC-6 (lock contention — a
test that never actually contends passes vacuously), and AC-9 (a `0` reaching a caller). Then task 02.
