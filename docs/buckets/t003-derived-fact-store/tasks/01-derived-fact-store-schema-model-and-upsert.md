# T-003 / Task 01 — Derived-fact store: schema, model, registration, upsert (DE-2, FR-3, FR-5)

Read `00-verification-notes-and-sr1.md` first. Its corrected line numbers are the
ones to use; the parent brief's are not.

## Objective
Create the `archimate_derived_relationships` table exactly per SDD v2 §DA-1 — all
DA-1 columns, the natural-key unique constraint, four named check constraints and
four named indexes — as a `TenantMixin` model that `flask init-db` genuinely
creates, and complete T-001's `DerivationRunner` with an upsert-on-natural-key
persistence path so that a derived fact carries, on the row, the ordered
explicit-relationship chain and the `rule_id` that answer "why does this row exist".

## Context
- **Extends an existing component, does not create one (ADR 0008).** The consumer
  of this store is the existing `DerivationRunner` at
  `app/modules/intelligence/services/derivation_runner.py:50` — verified present,
  computing correctly and deliberately persisting nothing. You are completing that
  class, not writing a second runner. The engine behind it is the existing
  `ArchiMateDerivationService.compute_derived`
  (`app/services/archimate_derivation_service.py:95`), whose ADR-002-v2 extended
  rows already carry `relationship_chain` (`:175`) and `rule_id` (`:176`). Do not
  change the engine.
- **This store is the system of record for rule-derived ArchiMate relationships and
  for nothing else.** The adjacent `architecture_inference_relationship` table
  remains the authority for uncertain/agent-proposed edges (ADR-001). Two stores,
  two concepts, deliberately — this is not a duplicate authority.
- Model registration is real and checkable: `db.create_all()` only creates tables
  whose model modules were imported. The aggregate import function in
  `app/models/__init__.py` is the place; copy the pattern at **`:365`**
  (`from .architecture_inference_relationship import ArchitectureInferenceRelationship  # noqa: F401`)
  and **`:371`** (`from .acm_property_template import AcmPropertyTemplate  # noqa: F401`).
- Migration-exempt marker text, verbatim, as line 2 of the new model module,
  directly under the docstring and above every import:
  `# migration-exempt — new table created via db.create_all() (migration freeze)`
- Depth: `compute_derived` seeds at depth 1 with a two-node path and expands only
  while `depth < MAX_DEPTH` (`:153`, `MAX_DEPTH = 5` at `:51`), so it emits 2..5.
  `ck_derived_depth CHECK (depth BETWEEN 1 AND 5)` is correct as written and
  deliberately wider than the engine's range. Do not narrow it; do not write a test
  asserting a depth of 1 exists.
- `chain` is `INTEGER[]` of `archimate_relationships.id` in order (FR-5).
  `chain_element_ids` is the node path, kept for T-004's node-highlighting screen.
- Tenancy is implicit: `TenantMixin` models are filtered by `do_orm_execute`, so ORM
  reads here must **not** hand-write an `organization_id` predicate (that
  double-filters). Raw SQL must (the listeners cannot reach it).

## Constraints
- Every check constraint and index is **named**, exactly: `uq_derived_rel`,
  `ck_derived_depth`, `ck_derived_conf`, `ck_derived_stale`,
  `ck_derived_chain_len`, `ix_dr_src`, `ix_dr_tgt`, `ix_dr_stale`, `ix_dr_chain`.
  `ix_dr_src`, `ix_dr_tgt` and `ix_dr_chain` carry the partial predicate
  `WHERE stale = FALSE`; `ix_dr_chain` is GIN with `array_ops` on `chain`.
  `array_ops` is Postgres core — add no extension, no dependency, no new store
  (NFR-6).
- `confidence NUMERIC(3,2) DEFAULT 1.00` with `ck_derived_conf CHECK (confidence > 0
  AND confidence <= 1)`; `provenance` defaults `'derivation'`. Only rule-derived
  facts are ever written here (ADR-001) — the upsert writes `confidence = 1.00` and
  `provenance = 'derivation'` and accepts no caller override.
- `ck_derived_stale` is the paired-nullability check: `stale_since` is NULL exactly
  when `stale = FALSE`, non-NULL exactly when `stale = TRUE`.
- `ck_derived_chain_len CHECK (array_length(chain, 1) = depth)`.
- Table via `create_all` only. **No Alembic migration.** The module carries the
  migration-exempt marker. NOT NULL columns are permitted here *because the table is
  new* — that exemption does not extend to any other table.
- `DerivationRunner.run()` keeps its current signature and return type. The upsert is
  additive: computing must remain possible without writing (T-001's tests must still
  pass unchanged). Add persistence as an explicit call path, not as a silent side
  effect of `run()` — the recompute job in task 03 is its caller.
- Never invent data: a `DerivationResult` count that was not computed is `None`, not
  `0`. Follow the existing `ratio` field's precedent at `derivation_runner.py:98`.
- Staging: `git add <file>` per file, never `git add -A`.

## Deliverable
1. `app/modules/intelligence/models/derived_relationship.py` — the model, with the
   package `__init__.py` if `app/modules/intelligence/models/` does not yet exist.
   Columns per DA-1: `id`, `organization_id` (NOT NULL, via `TenantMixin`),
   `source_element_id`, `target_element_id`, `derived_type`, `rule_id`, `chain`
   (`ARRAY(Integer)`), `chain_element_ids` (`ARRAY(Integer)`), `depth`,
   `confidence`, `provenance`, `engine_version`, `computed_at`, `stale`,
   `stale_since`, `stale_reason`. All four constraints and four indexes in
   `__table_args__`, each named as above. Line 2 migration-exempt marker.
2. The import line added to the aggregate import function in
   `app/models/__init__.py`, adjacent to `:365`/`:371`, in the same
   `# noqa: F401` form.
3. `DerivationRunner` persistence: upsert on the natural key
   `(organization_id, source_element_id, target_element_id, derived_type, rule_id)`
   — stamp `computed_at`, set `stale = FALSE` / `stale_since = NULL` /
   `stale_reason = NULL`, write `chain`, `chain_element_ids`, `depth`,
   `engine_version` from `ENGINE_VERSION`, and **delete rows for that tenant the
   engine no longer produces**. Use a Postgres `INSERT ... ON CONFLICT ON CONSTRAINT
   uq_derived_rel DO UPDATE` so the write is one statement per batch, not one per
   row. `organization_id` appears explicitly in that raw-SQL predicate.
4. Tests in `app/modules/intelligence/tests/` — written against the shared fixtures
   in `tests/conftest.py` (`db_session`, `make_org`, `tenant_ctx`), following
   `tests/test_tenant_isolation.py`. Do not copy the hand-rolled module-scoped `app`
   fixture pattern.

## Acceptance Criteria
1. **(Brief item 1, FR-3)** A test inspects the live database after creation and
   asserts: every DA-1 column present; `organization_id` NOT NULL; `uq_derived_rel`
   present on the five-column natural key; `ck_derived_depth`, `ck_derived_conf`,
   `ck_derived_stale`, `ck_derived_chain_len` all present **by name**; `ix_dr_src`,
   `ix_dr_tgt`, `ix_dr_stale`, `ix_dr_chain` all present by name, with the partial
   `WHERE stale = FALSE` predicate asserted on `ix_dr_src`, `ix_dr_tgt` and
   `ix_dr_chain`, and `ix_dr_chain` confirmed GIN. Read `pg_indexes.indexdef` /
   `pg_constraint.conname` — do not assert against the model's Python metadata,
   which would pass even if the DDL never reached the database.
2. **(Brief item 15)** A test confirms the table exists after `db.create_all()` via
   the real app factory — i.e. that the `app/models/__init__.py` import is
   effective. Additionally record in the build report a real
   `flask --app manage init-db && flask --app manage reconcile-schema` run against a
   fresh database, with the table and all four indexes verified present afterwards.
   A model that is never imported fails at first read with a missing-relation error,
   not an empty result; this is checked, not inferred.
3. **(Brief item 2, FR-5)** Three scenarios assert a persisted derived fact carries
   `chain` (ordered `archimate_relationships.id` values, matching the engine's
   `relationship_chain`), `rule_id`, `confidence`, `computed_at`, `depth`, and that
   `array_length(chain, 1) = depth` holds in the database.
4. **(Brief item 11, ADR-001)** A test asserts `confidence = 1.00` and
   `provenance = 'derivation'` hold by constraint/default — an attempt to insert
   `confidence = 0` or `confidence = 1.5` raises — and that the upsert path exposes
   no way to write an inference or agent-proposal row into this table.
5. **(Brief item 12, NFR-4)** The model carries `TenantMixin`; a test in tenant B's
   scope returns none of tenant A's derived rows. The upsert's raw SQL carries
   `organization_id` explicitly.
6. Re-running `DerivationRunner` persistence twice over an unchanged model is
   idempotent: same row count, `computed_at` refreshed, no duplicate-key error.
   Rows the engine stopped producing are deleted, and deletion is scoped to that one
   tenant.
7. `python scripts/verify.py` (bare, not `--tag static`) is green, and no ratchet in
   `verification_baseline.json` is raised. T-001's existing tests
   (`test_derivation_runner.py`, `test_derivation_engine.py`) pass unchanged.

## Handoff Target
`builder`. On completion, hand to task 02 (invalidation listener and the OA-2
record), which depends on this table and on the upsert's stale-clearing semantics.
The refuter verifies items 1, 2, 3, 11, 12 and 15 of the parent brief against this
task by test id at the L1 gate.
