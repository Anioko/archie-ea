# T-005 / Task 01 — Derivation run record and yield aggregates

## Objective
Make "did derivation run for this tenant, when, and how long did it take"
answerable after the request that produced it ends, and provide the per-tenant
aggregate reads the yield report needs — without loading the derived-fact rows
into memory to count them.

## Context
Read `00-verification-notes.md` first; defects D5, D6, D7, D8 and D9 are the
reason this task exists and its decisions are binding, not suggestions.

Short version: `DerivationRunner.run()` measures `duration_ms` onto a frozen
`DerivationResult`, `run_and_persist()` returns it, and nothing persists it.
`JobRun`/`TenantResult` in `app/jobs/tenant_safe_job.py` are in-memory only —
there is no job-run table anywhere. Separately, `_persist()` DELETEs all of a
tenant's rows when the engine produces nothing, so "ran and derived zero" and
"never ran" are byte-identical in the store.

Components this **extends** (ADR 0008 — none of these is new):
- `app/modules/intelligence/services/derivation_runner.py` — `DerivationRunner`,
  the single producer. It gains the run-record write; it keeps everything else.
- `app/modules/intelligence/services/derived_facts.py` — the ONE accessor over
  `archimate_derived_relationships`. It gains SQL aggregate functions alongside
  `list_derived_facts`/`get_derived_fact`; it does not gain a second read path.
- `app/modules/intelligence/models/` — gains one sibling model file next to
  `derived_relationship.py`.

## Constraints
- **New table `intelligence_derivation_runs`, one row per tenant per completed
  `run_and_persist`.** `TenantMixin`. Carry the
  `# migration-exempt — new table created via db.create_all() (migration freeze)`
  marker exactly as `derived_relationship.py` does. Every non-key column
  nullable or server-defaulted, per CLAUDE.md "Schema management" —
  `reconcile-schema` only ever adds nullable columns.
  Minimum columns: `organization_id`, `started_at`, `finished_at`,
  `duration_ms`, `explicit_count`, `derived_count`, `ratio` (nullable — `None`,
  never `0`, when `explicit_count` is zero), `engine_version`, `trigger`
  (`"scheduled"` / `"on_demand"`, whatever the caller passes — never guessed).
  Do **not** add `extend_existing`; this is a new table and `extend_existing`
  would blind the `canonical-store` gate.
- **The producer ships in this task.** A row is written on every successful
  `run_and_persist`, inside the same `tenant_scope` block that persists the
  facts, before the commit — so the run record and the facts it describes land
  atomically and no reader can observe one without the other. A store with no
  producer is worse than no store; do not create the table and defer the write.
- A failed or lock-skipped run writes **no** row. Absence means "no completed
  run", which is the exact fact the not-computed branch reads. Never write a
  placeholder row.
- `derivation_yield` aggregates must be **SQL aggregates** (`COUNT`, `MAX`,
  `COUNT(DISTINCT ...)`), not `len(list_derived_facts(...))`. A tenant with
  100k derived rows must not materialise them to produce a count.
- Any raw SQL carries an explicit `organization_id` predicate (the ORM listeners
  do not reach raw SQL). ORM aggregates over `DerivedRelationship` must **not**
  hand-write the predicate when called inside a request — that double-filters;
  follow the existing pattern and reasoning in `derived_facts.py`'s module
  docstring, and keep the explicit-`organization_id`-argument style the two
  existing functions use so the module stays correct outside a request context.
- Do **not** use `tenant_scope()` on any request-path read (round-1 refuter
  finding D4, documented in `derived_facts.py`).
- `explicit_count` and `ratio` keep exactly the definitions `DerivationRunner`
  already uses — `explicit_count` is the count of the tenant's
  `ArchiMateRelationship` rows, `ratio = derived_count / explicit_count` and
  `None` when explicit is zero. Two surfaces, one answer (D8).
- No new dependency, no new container, no second read path over the derived
  store.

## Deliverable
1. `app/modules/intelligence/models/derivation_run.py` — the
   `DerivationRun` model described above, exported from
   `app/modules/intelligence/models/__init__.py` the same way its sibling is.
2. `DerivationRunner.run_and_persist` extended to write one `DerivationRun` row
   per completed run, from the real measured values on `DerivationResult` —
   never a literal. `run()` is unchanged (computing without writing stays
   possible, per its own docstring).
3. In `derived_facts.py`, additive aggregate accessors — suggested shape, name
   them as you see fit but keep them in this module:
   - `derived_fact_aggregates(organization_id) -> dict` returning
     `derived_count` (non-stale), `stale_count`, `computed_at` (max over the
     tenant's rows, `None` when there are none), and `engine_versions` (the
     distinct set present — D9: the store's values, never the module constant).
   - `latest_derivation_run(organization_id) -> DerivationRun | None`.
4. Tests in `app/modules/intelligence/tests/` (new file, e.g.
   `test_derivation_run_record.py`), written against the **shared fixtures** in
   `tests/conftest.py` (`db_session`, `make_org`, `tenant_ctx`) — not a
   hand-rolled module-scoped `app` fixture.

## Acceptance Criteria
1. A completed `run_and_persist` for a tenant writes exactly one
   `DerivationRun` row carrying the same `explicit_count`, `derived_count`,
   `ratio`, `duration_ms` and `engine_version` the returned `DerivationResult`
   carries. Test asserts field-by-field equality with the returned object, so a
   hard-coded value cannot pass.
2. **The D6 case:** a tenant whose model yields zero derived relationships runs
   `run_and_persist`, ends with zero rows in `archimate_derived_relationships`,
   **and** has a `DerivationRun` row with `derived_count = 0`. A tenant that
   never ran has zero rows in both. Test asserts the two tenants are
   distinguishable by `latest_derivation_run(...) is None`.
3. A run that raises, and a run skipped by the per-tenant lock
   (`_recompute_one_tenant` returning `{"skipped_locked": True}`), write no
   `DerivationRun` row. Test asserts the row count is unchanged.
4. Atomicity: the run record and the facts commit together. Test forces a
   failure between the fact persist and the commit and asserts neither the facts
   nor the run record are visible afterwards.
5. Tenancy (NFR-4): a `DerivationRun` written under tenant A is invisible to a
   read under tenant B. Test uses two orgs and asserts
   `latest_derivation_run(B)` does not return A's row. Includes a loop-over-
   tenants-in-one-session case with `db.session.remove()` between tenants, per
   CLAUDE.md's identity-map caveat.
6. `derived_fact_aggregates` returns counts equal to a direct
   `SELECT COUNT(*)` against the table for the same tenant, and returns
   `computed_at = None` (not a date, not an epoch) for a tenant with no rows.
7. `derived_fact_aggregates` issues a bounded number of statements and
   materialises no `DerivedRelationship` instances. Test asserts via a statement
   count or by asserting the return type contains no row dicts — a `len(...)`
   over `list_derived_facts` must not pass this.
8. `engine_versions` reflects what is **on the rows**. Test writes rows carrying
   an engine version different from `derivation_runner.ENGINE_VERSION` and
   asserts the accessor reports the row value, not the constant (D9).
9. `ratio` is `None`, never `0`, when `explicit_count` is zero — on both the
   `DerivationRun` row and the aggregate return.
10. Schema safety: `flask reconcile-schema --dry-run` reports no drift after
    `init-db` creates the new table, and the model's columns are nullable or
    server-defaulted such that adding this table to an existing database needs
    no backfill. Record the command output in the build report.
11. `python scripts/verify.py` (bare, not `--tag static`) is green, including
    `canonical-store` and `schema-drift`.

## Handoff Target
`builder`. On completion, hand to task 02 — which depends on every accessor in
this task and must not begin before the payload shapes here are settled.
