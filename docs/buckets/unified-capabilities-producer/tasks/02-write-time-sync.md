# Task 02 — Keep the projection current on every write

Handoff target: `builder` → `refuter`
Depends on: Task 01 merged.

## Objective

Stop `unified_capabilities` from drifting back to stale the moment a user creates,
edits or deletes a business capability in the UI, by projecting each
`business_capability` write into the canonical store as part of the same
transaction.

## Context

Task 01 backfills the existing rows. It does nothing for the next row. The only
event listener on `BusinessCapability` today is
`create_capability_archimate_element` (`app/models/business_capabilities.py:572`),
a `before_insert` that mirrors the row into `archimate_elements` with a
connection-level `insert()` during flush — this repo's established pattern for
"this row must exist in a second store", and the component this task extends. A
capability created through the UI therefore reaches `archimate_elements` and
never reaches `unified_capabilities`.

The projection's column mapping, checksum expression and conflict handling live
in `app/commands/project_capabilities.py` (`_SOURCE_CTE`, `_CHECKSUM_SQL`,
`_PROJECT_SQL`, `_PARENT_SQL`). The tech-lead design decision for this bucket is
recorded in `docs/buckets/unified-capabilities-producer/implementation-plan.md`
section 2: **listener plus backfill, not a scheduled job, and the listener must
execute the same SQL the CLI does.**

## Constraints

- **One SQL definition.** The listener MUST reuse `_PROJECT_SQL` (and
  `_PARENT_SQL`) from `app/commands/project_capabilities.py`, parameterised to a
  single source row, rather than re-expressing the column mapping in Python. Two
  mappings would produce two different `source_checksum` values for one row, and
  every subsequent CLI run would report phantom drift and rewrite rows forever.
  Refactor `_SOURCE_CTE` so the source set can be narrowed by id — keep the
  existing `--limit` behaviour working unchanged.
- The listener runs **inside a request**, where
  `_protect_reference_capability_writes` and the `do_orm_execute` scoping in
  `app/models/unified_capability.py` are active. Because it writes on the flush
  `connection` in raw SQL it bypasses the ORM before_flush guard — that is
  correct and necessary, but it means the listener itself must enforce the
  invariant those guards exist for: the projected row's `organization_id` comes
  from `target.organization_id` only, never from `g.current_org_id`, and a
  projected row is never `scope='reference'` and never `organization_id IS NULL`.
- **Failure policy, decided — implement exactly this:**
  - Provenance index absent (un-migrated database): log at ERROR and skip. A
    capability create must not 500 because a migration has not been applied. The
    check is a module-level cached probe, run once per process, not per write.
  - Index present and the projection write fails: **raise**. The capability
    create fails atomically. Do not swallow; a silently half-projected store is
    the defect this bucket closes.
- Deletes: an `after_delete` listener deletes the projected row matching
  `source_table='business_capability' AND source_id = <id>::text` and nothing
  else. Never a broader predicate.
- Updates: project on update too, not just insert — a renamed capability that
  keeps a stale name in the canonical store is the same disagreement in a
  different column. The checksum `WHERE` clause in `_PROJECT_SQL` already makes
  an unchanged update a zero-row write.
- Hierarchy: `parent_capability_id` translation (`_PARENT_SQL`) can only resolve
  once the parent is itself projected. Handle the out-of-order case honestly —
  either run the parent pass for the affected row after insert, or leave it NULL
  and let the next CLI run resolve it, but state which in a comment. Do not
  guess a parent id.
- Do not touch `app/services/archimate_import_service.py`,
  `app/services/archimate_oef_service.py`, or `app/modules/interface_register/`.

## Deliverable

1. `after_insert` / `after_update` / `after_delete` listeners on
   `BusinessCapability` in `app/models/business_capabilities.py`, alongside the
   existing ArchiMate listener, executing the shared projection SQL.
2. The `_SOURCE_CTE` refactor in `app/commands/project_capabilities.py` that
   makes single-row parameterisation possible, with `--limit` behaviour
   unchanged.
3. Tests in `tests/test_capability_projection.py` and
   `tests/test_tenant_isolation.py` (extend, do not duplicate) covering: create →
   projected row exists with correct provenance; update → projection refreshed;
   delete → projection removed and no orphan; a create in org A produces no row
   visible to org B; a create on a database with no provenance index does not
   raise and does not project.
4. A `tests/smoke/` journey extension (the `smoke-coverage-on-change` gate is
   must-be-0 and this touches user-visible behaviour): a persona creates a
   capability in the real UI and the count on a `/api/v1/capabilities/`-backed
   surface increases after reload.

## Acceptance Criteria

- Create a `business_capability` through the UI, then run
  `flask --app manage project-capabilities --dry-run`: the plan reports
  `to_insert = 0` and `to_update = 0`. This is the checksum-agreement proof that
  the listener and the CLI compute the identical row — if they disagree, the
  dry-run will say so.
- Delete that capability; `select count(*) from unified_capabilities where
  source_table='business_capability' and source_id = '<id>'` is 0.
- No cross-tenant leak: org B's session never sees org A's projected row, via a
  test that calls `db.session.expunge_all()` between tenants (per CLAUDE.md's
  `.get()` identity-map note).
- `python scripts/verify.py` green (bare run).
- `pytest tests/test_capability_projection.py tests/test_tenant_isolation.py`
  green, and green when each file is run **alone** (order-dependent passes do not
  count here).

## Handoff target

`refuter` — attack specifically: (a) does the listener's checksum genuinely match
the CLI's, or does the dry-run only appear clean because the test never changed a
column outside the checksum list; (b) what happens when the projection write
raises mid-flush — is the capability create rolled back or half-committed; (c)
can any code path reach the listener with `target.organization_id` NULL.
