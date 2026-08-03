# ADR 0002 — Schema management: reconcile now, Alembic baseline next

- **Status:** Accepted (target state); migration to it **not yet executed**
- **Date:** 2026-07-30
- **Supersedes discussion in:** `docs/known-issues/schema-drift-on-existing-databases.md`

## Context

Three mechanisms currently define Archie's schema, and the one that looks
authoritative is not:

1. **`create_all()`** via `flask --app manage init-db` — creates missing *tables*.
   It has no concept of `ALTER TABLE ... ADD COLUMN`, so a model that gains a column
   never reaches an existing database.
2. **`flask reconcile-schema`** (`app/commands/reconcile_schema.py`) — diffs mapped
   models against live tables and issues `ADD COLUMN IF NOT EXISTS`. ADD-only, all
   nullable, never drops or retypes. Idempotent. Runs on container boot.
3. **`migrations/`** — Flask-Migrate/Alembic, 130+ revisions, multiple merge heads.
   **Deploys never run `flask db upgrade`.** It is effectively historical.

Additionally, `manage.py init_db` carries ~250 lines of hand-written idempotent
`ALTER TABLE` statements for pre-Alembic columns, marked legacy in its own comments.

### Why this is a problem beyond untidiness

- Every deploy **silently mutates production schema** (`init-db && reconcile-schema
  && gunicorn`). There is no plan, no review, and no record of what changed.
- The design **structurally forbids non-nullable columns**, because
  `reconcile-schema` can only add nullable ones. Nobody chose that constraint; it is
  an emergent property. A developer adding `nullable=False` gets a clean local
  install and a broken upgrade.
- Backfills have nowhere to live. `reconcile-schema` adds a column; it cannot
  populate it.
- The documented incident is the second-order effect: 47 drifted columns across ~20
  tables, one `UndefinedColumn` aborting the transaction and cascading into
  `InFailedSqlTransaction` for every later query, 500-ing whole pages.

## Decision

**Target state:** Alembic is the single source of truth; `flask db upgrade` runs on
deploy; `reconcile-schema --dry-run` is demoted to a **CI drift detector that must
report zero**, rather than a runtime mutator.

**Now (this change):** the detector half only.

- `scripts/verify.py --gate schema-drift` runs `reconcile-schema --dry-run` and fails
  when drift is present. CI runs it with `--require-db`, so it cannot pass by being
  skipped.
- `reconcile-schema` stays in the boot sequence. Removing it before Alembic is
  trustworthy would leave existing deployments with no self-heal.

**Deliberately not done here:** squashing the 130+ revisions and changing the deploy
command. Both are irreversible-in-practice and need a maintenance window plus a
verified backup. Doing them unannounced from a code change would be reckless. The
plan is below so the next person does not have to re-derive it.

## Migration plan (requires a maintenance window)

1. **Freeze.** Announce that no new Alembic revisions land during the squash.
2. **Resolve heads.** `flask db heads` — expect several. Merge to one, or discard
   the pre-baseline history entirely in step 3.
3. **Generate the baseline.** Against a database built by
   `init-db && reconcile-schema` from current models:
   ```
   flask --app manage db revision --autogenerate -m "baseline: schema as of <date>"
   ```
   Review the emitted revision by hand. Autogenerate does not see everything —
   server defaults, index differences, and the `extend_existing` duplicate-mapped
   tables all need checking.
4. **Archive old revisions.** Move `migrations/versions/*` to
   `migrations/versions/_archive_pre_baseline/` (kept for forensics, excluded from
   the chain). The baseline becomes the single root.
5. **Stamp existing databases.** On every deployed environment:
   `flask --app manage db stamp <baseline_rev>` — records the revision without
   re-running DDL. **Verify against a restored production backup first.**
6. **Switch the deploy command** in `docker-compose.yml` from
   `init-db && reconcile-schema && gunicorn` to
   `db upgrade && gunicorn`, keeping `reconcile-schema --dry-run` as a boot-time
   *assertion* that logs loudly on drift rather than repairing it.
7. **Lift the nullable-only constraint.** Document that `nullable=False` columns are
   now permitted provided the revision includes a backfill.

### Exit criteria

- `flask db upgrade` on a copy of production is a no-op.
- `reconcile-schema --dry-run` reports zero drift on every environment.
- CI's schema-drift gate has been green for one full release cycle.

## Consequences

- Until step 6, the drift gate catches *model-vs-database* divergence in CI but
  production still self-mutates at boot. That is a genuine reduction in risk, not a
  fix.
- New columns must stay nullable (or carry a server default) until step 7. This is
  now written down rather than being folklore.
- `manage.py init_db`'s hand-written `ALTER TABLE` block should be deleted at step 6;
  the baseline supersedes it. Do not add to it before then.

## Alternatives considered

- **Delete `migrations/` entirely, commit to `reconcile-schema`.** Honest about
  current practice and simpler, but permanently forfeits non-nullable columns,
  backfills, data migrations, and any reviewable record of schema change. Rejected.
- **Keep both indefinitely.** The status quo. Rejected: two sources of truth means
  neither is trusted, and the reconcile path silently constrains modelling.
