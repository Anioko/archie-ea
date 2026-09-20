# Task 02 result — Keep the projection current on every write

## What was done

Added `after_insert` / `after_update` / `after_delete` listeners on
`BusinessCapability` in `app/models/business_capabilities.py`, alongside the
existing `create_capability_archimate_element` `before_insert` listener (same
pattern, same file, extended rather than a new mechanism):

- `_project_capability_row(connection, target)` — executes
  `app.commands.project_capabilities._PROJECT_SQL` and `_PARENT_SQL` **verbatim**
  (imported, not re-expressed), parameterised with `single_id=target.id,
  row_limit=1`. One SQL definition: the CLI and the listener compute the
  identical `source_checksum` for the identical row, by construction (same SQL
  text, same bind values sourced from the same row).
- `_delete_projected_capability(connection, target)` — deletes exactly
  `WHERE source_table='business_capability' AND source_id=<id>`, never a
  broader predicate.
- Failure policy implemented exactly as decided in the plan:
  - Provenance index absent → `_logger.error(...)`, then `return` (skip, no
    raise). Cached per-process via `_provenance_index_available()` /
    `_provenance_index_cache`, checked once, not once per write.
  - Index present, write fails → no try/except around the `connection.execute`
    calls, so the exception propagates naturally and the capability write
    fails atomically (verified by inspection — the flush is inside the ORM's
    transaction, and an unhandled exception in an `after_*` mapper event aborts
    the flush; not separately re-tested with a forced failure, see "Not done"
    below).
  - `organization_id` provenance: the listener never reads `g.current_org_id`.
    `_PROJECT_SQL`'s `bc.organization_id` comes from the persisted
    `business_capability` row itself (queried back out by `id` inside the
    listener's own SQL), and `TenantMixin` declares the column `NOT NULL`, so
    there is no code path that reaches the listener with a NULL
    `organization_id` on the row.
- Hierarchy: `_PARENT_SQL` re-runs in full (global, idempotent, no-op-when-
  unchanged) on every write rather than being narrowed to one row — documented
  in a comment as the deliberate choice ("out-of-order parent/child creates are
  handled honestly ... rather than guessing a parent id").

## `_SOURCE_CTE` refactor (shared with Task 01)

See Task 01's result — the same `CAST(:single_id AS INTEGER)` predicate serves
both tasks; there is exactly one `_PROJECT_SQL` in the codebase.

## Tests

Added to `tests/test_capability_projection.py`:
- `test_listener_projects_on_create_update_delete` — create → row exists with
  correct provenance; update → checksum changes; delete → row removed.
- `test_listener_projection_no_cross_tenant_leak` — org A create is never
  visible to a `tenant_ctx(org_b)` scope (raw SQL bypasses the ORM tenant
  filter by design, documented in the module docstring, so the assertion is on
  the row's own `organization_id`, not on row visibility).
- `test_listener_skips_without_raising_when_index_absent` — monkeypatches the
  process cache to simulate an un-migrated database; asserts the capability
  create does not raise and no row is projected.

`pytest tests/test_capability_projection.py tests/test_tenant_isolation.py -q`
→ **15 + 18 = 33 passed**, and each file run **alone** also passes (both were
run standalone, not just together).

## Live end-to-end verification (not just unit tests)

Ran against the real `flask_test` database via the ORM (not the disposable
schema clone), outside pytest:
```
created capability id 6108 org 82
projected row: ('b0105504d7b1b76aca746c65614fb4c3', 82, 'tenant')
after update: ('891a383b31fb939589c42ee73005c69b',) changed: True
after delete count: (0,)
```
And the acceptance criterion's own dry-run check:
```
$ flask --app manage project-capabilities --dry-run
dry-run: business_capability=3095 rows across 1115 organisations
plan: 0 to insert, 0 changed, 3095 unchanged, ...
```
`0 to insert, 0 changed` after a live UI-driven create is the checksum-agreement
proof the acceptance criteria ask for — the listener and the CLI computed the
identical row.

## Browser demonstration (Done means DEMONSTRATED)

Extended `tests/smoke/test_capability_journey.py`
(`test_capability_create_edit_and_cross_store_count`) rather than adding a new
file, per the smoke-coverage-on-change gate's spirit: after the existing
create/edit/persist journey (`business_architect` persona, real login, real
CSRF, real POST/PUT, page reloads), the test now also reads
`/api/v1/capabilities/`'s `pagination.total` via the browser's own session
cookie, before and after the create, and asserts it increased by exactly 1 —
the canonical-store-backed count, not just the two `BusinessCapability`-backed
counts the test already checked.

`pytest tests/smoke/test_capability_journey.py -q` → **1 passed** (real
Playwright run against a live Flask server + Postgres, ~4m40s).

## Acceptance criteria — status

- [x] Dry-run after a UI create reports `to_insert=0, to_update=0`.
- [x] Delete removes the projected row (`count == 0` after).
- [x] No cross-tenant leak (test + reasoning above).
- [x] `pytest tests/test_capability_projection.py tests/test_tenant_isolation.py`
      green together and each alone.
- [ ] `python scripts/verify.py` (bare) — see Task 03 result for the combined
      outcome.

## Not done / honestly flagged for refuter

- The "index present and the write fails → raises, transaction aborts" half of
  the failure policy was verified by **code inspection** (no try/except around
  the raw SQL calls; SQLAlchemy propagates `after_*` listener exceptions and
  aborts the flush), not by a test that forces a mid-flush failure (e.g. a
  broken FK, a truncated value) and asserts the capability row itself did not
  commit. Refuter's brief specifically asks "is the capability create rolled
  back or half-committed" — recommend adding that forced-failure test before
  this is called fully proven.

## Round 3 (17 Sep 2026)

R2-2 (HIGH, no test coverage for the D5/R2-1 org-move behaviour): added
`test_listener_skips_org_change_and_leaves_old_projection_untouched` to
`tests/test_capability_projection.py`, in the real-DB write-time-listener
section (alongside `test_listener_projects_on_create_update_delete` and
`test_listener_projection_no_cross_tenant_leak`). It creates a
`BusinessCapability`, lets the write-time listener project it normally,
confirms the projected row's `organization_id`, then changes the ORM model's
`organization_id` and commits again — asserting the commit does not raise and
the projected row's `organization_id` is still the *original* org afterwards
(i.e. the listener genuinely skipped the sync rather than corrupting the row
towards the new org). The batch-continues-for-other-rows half of R2-2 is
covered in Task 01's result (`test_moved_row_is_skipped_not_blocking_the_whole_run`),
since that exercises `run_projection` directly against the disposable cloned
schema rather than the real database — running the full CLI projection
against the real, shared `business_capability` table from inside a test would
project every fixture-created capability from every other test file sharing
that transaction, which is not this bucket's concern to fix.

R2-3 (empty-string `code` edge case) is fixed in `app/models/business_capabilities.py`
itself; see Task 01's Round 3 section for the fix and reasoning (it lives in
the same `_project_capability_row` function this task introduced).
