# Task 01 — Run the producer that already exists

Handoff target: `builder` → `refuter`

## Objective

Make the already-written capability projection actually execute, on every
database this product boots against, so `unified_capabilities` stops answering 0
against `business_capability`'s 461 rows. No new projection logic is written in
this task.

## Context

`app/commands/project_capabilities.py` already implements the ADR 0008
projection correctly (idempotent on `(source_table, source_id)`, full provenance,
`scope='tenant'`, per-tenant `organization_id`, five pre-flight blockers, three
post-write verifications, dry-run/apply, JSON audit report). It is registered as
a CLI command at `app/_bootstrap/cli.py:313` and tested by
`tests/test_capability_projection.py`. Its pre-cutover guard is already cleared —
`app/commands/cutover_capability_tenancy.py:31` sets
`CLASSIFIES_PROVENANCE_ONLY_TENANT = True`.

It has simply never been invoked. `scripts/database/deploy-schema.sh` — the
one-shot schema-owner container that every deploy runs — executes `init-db`,
`reconcile-schema` and nine named backfills, and does not include it.
`scripts/migrate_unified_capability_provenance.sql`, which creates the
`uq_unified_capabilities_provenance` unique index the projection's `ON CONFLICT`
arbiter requires, is likewise never applied; `reconcile-schema` emits only
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` and can never create an index, so
without this step `run_projection` raises `ProjectionBlocked` and writes nothing.

The component you extend is `scripts/database/deploy-schema.sh` (per ADR 0008 —
name the existing component, do not invent a new bootstrap path).

## Constraints

- **Do not modify the projection SQL.** If a blocker fires, resolve the data, or
  report it; do not weaken `_PROJECT_SQL`, `_plan`'s blockers or `_verify`.
- The migration must be applied by a step that is idempotent and safe to re-run
  on a database where it has already run (the SQL file already is —
  `CREATE UNIQUE INDEX IF NOT EXISTS`, wrapped in `BEGIN/COMMIT`). Applying it
  needs a mechanism: either a new thin `flask` CLI command that executes the
  file, or a `psql -f` step in `deploy-schema.sh` running as the schema owner.
  Prefer the `flask` command — the runtime containers never receive
  `DATABASE_ADMIN_URL`, and the existing chain is entirely `flask --app manage`
  invocations, so a `psql` step would be a second convention for one job.
- The `project-capabilities` step in the chain uses `--apply` and **must not** be
  `|| echo WARN`-suppressed the way the tenancy backfills are. A failed
  projection means the canonical store is wrong; the boot should surface it.
  Exception: it may be suppressed **only** for the `ProjectionBlocked` case where
  the provenance index is absent, which cannot happen if the migration step ran
  immediately before it. Justify whichever you choose in a comment in the file,
  matching the style of the existing comment block in `docker-compose.yml:55-76`.
- Ordering: migration → `project-capabilities --apply`, and both **after**
  `reconcile-schema` (the provenance columns must exist) and **after**
  `backfill-*` tenancy commands (an ownerless source row is blocker 1 and would
  abort the projection).
- No schema change beyond the one index in the existing SQL file. No new
  non-nullable column.
- Do not touch `app/services/archimate_import_service.py`,
  `app/services/archimate_oef_service.py`, or `app/modules/interface_register/`.

## Deliverable

1. A mechanism that applies `scripts/migrate_unified_capability_provenance.sql`
   idempotently, wired into `scripts/database/deploy-schema.sh`.
2. `flask --app manage project-capabilities --apply --report <path>` wired into
   the same chain, after it.
3. A recorded before/after measurement on a real seeded database (the local test
   Postgres is acceptable for the measurement; production is Task 03's
   demonstration): `select count(*) from business_capability` and
   `select count(*) from unified_capabilities where source_table =
   'business_capability'`, captured before and after, plus the command's own JSON
   report.
4. A test in `tests/test_capability_projection.py` (extend it; do not create a
   parallel file) asserting the deploy chain's ordering contract that matters —
   that `run_projection` refuses without the provenance index, and succeeds after
   the migration file has been applied.

## Acceptance Criteria

- On a database seeded with `business_capability` rows, a fresh run of
  `sh scripts/database/deploy-schema.sh` leaves
  `count(unified_capabilities where source_table='business_capability')` equal to
  `count(business_capability)`, with zero rows failing `_verify`'s three
  assertions.
- Running the chain a **second** time writes zero rows
  (`writes.inserted_or_updated == 0` in the report) — the idempotency claim is
  measured, not assumed.
- Every projected row has non-NULL `source_table`, `source_id`,
  `source_checksum`, `source_org_id`, `scope='tenant'` and
  `organization_id = source_org_id`. Zero projected rows have
  `organization_id IS NULL` (that value means *shared reference data* and a
  projected tenant row must never claim it).
- `python scripts/verify.py` is green (bare, not `--tag static`).
- No change to what `business_capability`-reading screens report.

## Handoff target

`refuter` — read-only on code; asked specifically to attack (a) whether the
second run really writes zero rows or merely reports zero, (b) whether an
ownerless or cyclic source row in a real tenant would abort a production boot,
and (c) whether the WARN-suppression decision is justified in the file.
