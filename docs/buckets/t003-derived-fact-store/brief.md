# Task Brief: T-003 — Derived-Fact Store, Batched Invalidation, Recompute Job

## Objective
Same as the verbatim brief below — persist the derivation engine's output,
keep it correctly invalidated, and recompute it on a schedule.

## IMPORTANT — an open gate condition from the wider plan, read before starting
`implementation-plan-v1.md` (the tech-lead plan covering this whole
programme, in the separate `sdlc-orchestrator` repo, not this one) states
T-003 does not start until the **L0 certification gate** records three
things: (1) T-001's 17 green derivation cases — done, verified independently
tonight; (2) T-002's `store-agreement` ratchet moving 1→0 for capability
maturity — done, merged, deployed tonight (PR #32); (3) **"SR-1 answered in
writing: the certification programme's duplicate-authority collapse is
confirmed scheduled on the same timeline as L0, or FR-2 is re-priced as
Shape-A scope"** — a cross-team scheduling confirmation from a separate
certification programme this coordinator has no visibility into and cannot
obtain.

The founder has explicitly authorized proceeding with T-003 now
("continue with T-003 etc, or do it in parallel") — this is not a request to
block on SR-1. But per this repo's own "own the decision" standing
instruction, a genuinely unknown external fact should be surfaced, not
silently assumed either way. **Tech-lead: investigate whether SR-1's
condition is knowable from anything in this codebase or its docs (e.g. does
`docs/adr/` or any bucket reference a "certification programme" timeline?),
and state clearly in your task file(s) whether you found it, and if not,
proceed anyway per the explicit founder authorization but flag this
explicitly in the build report as an open item for the founder's own
awareness — not a blocker, but not silently dropped either.**

---

# T-003 — L1 · Derived-fact store, batched invalidation, recompute job (FR-3, FR-4, FR-5)
(verbatim from the sdlc-orchestrator pipeline's tasks/T-003-derived-fact-store.md)

## Objective
Persist the runner's output in the dedicated `archimate_derived_relationships` table (DE-2), mark rows stale in one batched statement inside the same transaction as any model write (DE-3), and recompute eventually through the existing tenant-safe scheduler (DE-4) — such that a query never returns a stale row as current without the flag, and every derived fact carries the ordered explicit-relationship chain and rule id that answer "why does this row exist".

## Context
- Design source: SDD v2 §DA-1 (table DDL and indexes), §AA-4 (invalidation write path and recompute), §API-1/§API-2 (chain in the payload, provenance expansion), §API-7 (the on-demand recompute endpoint), §OA-2 (structured record incl. `invalidated_rows`); ADR-001 (dedicated table, not the inference table), ADR-002-v2 (native integer-array chain, batched invalidation), ADR-003 (scheduled per-tenant job plus on-demand endpoint), ADR-004 (immediate staleness, eventual recomputation).
- Depends on: T-001 (the `DerivationRunner` and the ADR-002-v2 extended engine signature) and the L0 certification gate. This task is L1; it does not start until L0 (T-001, T-002) is certified and merged. **Both are now merged and deployed to production (T-001 tonight earlier, T-002 as PR #32) — verify this yourself against the current checked-out code before relying on it, per the drift already found in T-002's own task briefs.**
- Table shape (DA-1): `archimate_derived_relationships` with `organization_id NOT NULL` (tenant column, `TenantMixin`), `source_element_id`, `target_element_id`, `derived_type`, `rule_id`, `chain INTEGER[]`, `chain_element_ids INTEGER[]`, `depth`, `confidence NUMERIC(3,2) DEFAULT 1.00`, `provenance DEFAULT 'derivation'`, `engine_version`, `computed_at`, `stale`, `stale_since`, `stale_reason`. Natural key `uq_derived_rel (organization_id, source_element_id, target_element_id, derived_type, rule_id)`. Check constraints: `depth BETWEEN 1 AND 5`; `confidence > 0 AND confidence <= 1`; the stale/stale_since paired-nullability check; `array_length(chain,1) = depth`. Indexes `ix_dr_src`, `ix_dr_tgt` (partial `WHERE stale = FALSE`), `ix_dr_stale`, and `ix_dr_chain` GIN on `chain` partial `WHERE stale = FALSE`.
- `chain` is the ordered list of `archimate_relationships.id` values — FR-5's answer; `chain_element_ids` is the node path, retained for the node-highlighting screen. `confidence` is 1.00 for every rule-derived row by check constraint; anything uncertain belongs in the inference tables, not here (ADR-001). `engine_version` makes a rule-table change selectively recomputable.
- The table is created by `flask init-db` (`create_all`) and may carry NOT NULL columns; the model module carries the `# migration-exempt — new table created via db.create_all()` marker. Naming is deliberately not `derivation_audit` — a table of that name exists in Alembic history for a different concept.
- Invalidation write path (AA-4 / ADR-002-v2): an `after_flush` listener registered by `app/modules/intelligence/__init__.py::register(app)` inspects `session.new`, `session.dirty`, `session.deleted` for `ArchiMateElement` and `ArchiMateRelationship`, collects affected ids, and issues ONE batched `UPDATE` per flush using array predicates (`chain && :changed_relationship_ids::integer[] OR source_element_id = ANY(:changed_element_ids) OR target_element_id = ANY(:changed_element_ids)`), scoped by `organization_id`, filtered `stale = FALSE`. `stale_reason` records the cause (`relationship_created|updated|deleted`, `element_deleted`). Running in the user's own flush means marking and the model change commit or roll back together — no window where the model changed and the store still claims current.
- Read path (ADR-004): every query applies `stale = FALSE` by default; `include_stale=true` returns stale rows each carrying `"stale": true` and `"reason": "derivation_stale"`; no code path returns a stale row without the flag.
- Recompute (DE-4, ADR-003): `recompute_derived_facts` on the existing APScheduler through `run_for_each_tenant`, default 10-minute interval, `max_instances=1`, selecting organisations with at least one stale row; the harness closes the four tenant hazards (`tenant_safe_job.py:25-45`, advisory lock at `:199-246`). On-demand at `POST /api/v1/intelligence/derivation/recompute`, one concurrent run per tenant via the same advisory lock.
- The runner's upsert (from T-001, exercised here now the table exists): upsert on the natural key, stamp `computed_at`, clear `stale`, delete rows the engine no longer produces.

- **Model registration, verified this session.** `db.create_all()` only creates tables whose models have been imported. New-table models are imported inside the aggregate import function in `app/models/__init__.py` — the pattern to copy is `from .architecture_inference_relationship import ArchitectureInferenceRelationship  # noqa: F401` at `:360` and `from .acm_property_template import AcmPropertyTemplate  # noqa: F401` at `:366`. The `# migration-exempt` marker convention is `app/models/acm_property_template.py:2`. Add the import for the new model there, or `flask init-db` will not create the table and every read will fail on a missing relation rather than on an empty one. **Re-verify these line numbers — T-002's own briefs found several had drifted since originally written.**
- **Scheduler wiring, verified this session.** `init_scheduler(app)` at `app/_bootstrap/extensions.py:224-233` builds the `BackgroundScheduler` and returns early under `app.testing` (`:226-227`); the interval-job registration pattern with `max_instances=1` is at `:398-405`. The harness entry points are `run_for_each_tenant` (`app/jobs/tenant_safe_job.py:285`), `tenant_scope` (`:167`), `job_lock` with its `pg_try_advisory_lock` (`:199-246`) and `JobRun`, whose `succeeded`/`failed` are properties over real results and are deliberately never defaulted to zero (`:88-116`). `db.session.remove()` between tenants is the harness's own precaution against identity-map carry-over and must not be bypassed. **Note: T-002 already added a second scheduled job (capability_projection_job.py) to this same extensions.py file tonight — re-read the current state of this file, the line numbers above will have shifted.**
- **Depth range the engine actually emits.** `compute_derived` seeds its queue at `depth = 1` with a two-node path and expands only while `depth < MAX_DEPTH`, so the smallest `depth` it can emit is 2 and the largest is 5. `ck_derived_depth CHECK (depth BETWEEN 1 AND 5)` is correct as specified and is deliberately wider than the engine's current range; do not narrow it, and do not write a test asserting a `depth` of 1 exists.
- **Two maturity- and capability-adjacent jobs now run on the same scheduler.** T-002 registers the capability projection with `job_lock` and no tenant context, because its writes span tenants; this task's recompute job uses `run_for_each_tenant`, because it writes `TenantMixin` rows one tenant at a time. The two use different harness entry points for different and stated reasons, and neither should be changed to match the other.

## Constraints
- The `after_flush` marking runs inside the user's flush and is one batched statement per flush, never one per id (DR-2, SEC-16). Do not move marking to an asynchronous queue — staleness must commit or roll back with the write (ADR-004; the SR-2 escalation to an in-request bounded queue applies only if measurement shows the penalty exceeds 100 ms p95, and is not this task's default).
- Every read over the store applies `stale = FALSE` by default; there must be no service, route, template or export path that returns a stale row without `"stale": true` and `"reason": "derivation_stale"` (ADR-004 read invariant).
- Derived facts are rule-derived facts only, `confidence = 1.00`, `provenance = 'derivation'`; never write an agent proposal or an inference row into this table (ADR-001). Agent-proposed relationships belong in the inference tables and are out of scope here.
- The recompute job body is `run_for_each_tenant(...)`; it never opens its own transaction management, never enumerates tenants itself, and never calls `Query.get()` across a tenant boundary. It sets tenant scope explicitly (raw-SQL and multi-tenant loop context is not ORM-fenced).
- Table created via `create_all`; carry the `# migration-exempt` marker; do not add an Alembic migration. No new store, container or dependency (NFR-6); `array_ops` GIN is Postgres core — no extension.
- The on-demand recompute endpoint is `@login_required` and CSRF-protected (it is a write route). Register the blueprint non-fatally and guard any template link per `DESIGN.md` §"Guarded nav links".
- Live defects SR-11, SR-12, SR-13 are out of scope here.

## Deliverable
- `app/modules/intelligence/models/derived_relationship.py` (DE-2) — the `archimate_derived_relationships` model with `TenantMixin`, the DA-1 DDL, all four check constraints and all four indexes, and the `# migration-exempt` marker.
- `app/modules/intelligence/services/invalidation.py` (DE-3) — the `after_flush` listener issuing the single batched `UPDATE` per flush, wired in `register(app)`.
- `app/modules/intelligence/services/recompute_job.py` (DE-4) — `recompute_derived_facts` on the existing APScheduler through `run_for_each_tenant`, selecting stale-carrying tenants; registered on the existing scheduler, skipped under `app.testing`.
- The runner's upsert-on-natural-key persistence completed against the now-existing table (stamp `computed_at`, clear `stale`, delete no-longer-produced rows), returning `DerivationResult`.
- `POST /api/v1/intelligence/derivation/recompute` (API-7) — body `{scope: "tenant"}`, runs/enqueues the tenant recompute, returns the `DerivationResult`, one concurrent run per tenant via the advisory lock, `@login_required`, CSRF-protected.
- `record_query_latency` / OA-2 structured record emitting `invalidated_rows` (the count the batched statement marked) alongside the existing fields.
- Tests under `app/modules/intelligence/tests/`, and a build report linking FR-3/FR-4/FR-5 → DE-2/DE-3/DE-4 → the acceptance items below, with the mutation-proof record.

## Acceptance Criteria
The refuter checks each individually:
1. Schema (FR-3): the table carries every DA-1 column, the `organization_id NOT NULL` tenant column, the natural-key unique constraint, all four check constraints (`ck_derived_depth`, `ck_derived_conf`, `ck_derived_stale`, `ck_derived_chain_len`) and all four indexes with the partial `WHERE stale = FALSE` predicate on `ix_dr_src`, `ix_dr_tgt` and `ix_dr_chain`. Named per constraint/index.
2. Chain carries provenance (FR-5): three test scenarios (per the sprint plan's L1 acceptance) assert a persisted derived fact carries `chain` (ordered `archimate_relationships.id` values), `rule_id`, `confidence`, `computed_at`, `depth`, and that `array_length(chain,1) = depth` holds.
3. Provenance expansion (FR-5 / API-2): `GET /api/v1/intelligence/derived/{derived_id}` expands a derived row to each explicit relationship in `chain` resolved to source/target with `derived_from`.
4. Batched invalidation (FR-4, DR-2/SEC-16): a test asserts a flush touching N relationships and M elements issues exactly ONE `UPDATE` against the store, scoped by `organization_id` and filtered `stale = FALSE`, and records the marked count as `invalidated_rows` on the OA-2 record.
5. Same-transaction guarantee (FR-4): a write and its staleness marking commit or roll back together — a test asserts that a rolled-back model write leaves no rows falsely stale.
6. **FR-4 stale-never-current (OA-6 item 3, named individually):** mutate a relationship, re-query in the same request, and assert the affected derived row is absent (default read) or, with `include_stale=true`, present and flagged `"stale": true` with `"reason": "derivation_stale"`; assert no default-read path returns a stale row without the flag.
7. `stale_reason` fidelity: a create, an update, a delete of a relationship and an element deletion each stamp the corresponding `stale_reason` value.
8. Recompute (FR-1/FR-4): `recompute_derived_facts` runs per tenant through `run_for_each_tenant`, selects only organisations with at least one stale row, clears `stale`, deletes rows the engine no longer produces, and its outcome is a `JobRun` whose `succeeded`/`failed` are never defaulted to zero on error.
9. Concurrency: on-demand recompute and the scheduled run cannot overlap for the same tenant (shared advisory lock); a second concurrent tenant recompute reports `skipped_locked`, not a silent success.
10. On-demand endpoint (API-7): `POST /api/v1/intelligence/derivation/recompute` is `@login_required`, CSRF-protected, returns the `DerivationResult`, and rejects with a clear message when the lock is held.
11. Only rule-derived facts persist (ADR-001): a test asserts no inference/agent-proposal row can be written into the store and that `confidence = 1.00` and `provenance = 'derivation'` hold by constraint.
12. Tenancy (NFR-4): the store model carries `TenantMixin`; a cross-tenant read returns no other tenant's derived rows; the recompute loop sets scope explicitly and does not rely on `Query.get()` across a tenant boundary.
13. Mutation proof (OA-6 structural rule): disable the read-path `stale = FALSE` default and confirm the FR-4 stale-never-current test (item 6) goes red; re-enable; record the test id.
14. No query surface beyond the recompute endpoint and the provenance-expansion route is added by L1 (the US-1 impact endpoint is T-004); NFR-8 respected.
15. Table creation is real, not assumed: the new model is imported in `app/models/__init__.py` alongside the `architecture_inference_relationship` and `acm_property_template` imports, and a test (or a recorded `flask init-db && flask reconcile-schema` run against a fresh database) confirms the table and all four indexes exist afterwards. A model that is never imported produces a missing-relation error at first read rather than an empty result, so this is checked rather than inferred.
16. Job registration parity: the recompute job is registered on the existing scheduler with `max_instances=1`, is skipped under `app.testing` exactly as the surrounding jobs are, and does not re-implement tenant enumeration, transaction management or locking that `run_for_each_tenant` already provides.

## Handoff Target
Next role: builder implements this brief; refuter then verifies every acceptance item by test id, including the FR-4 stale-never-current test and its mutation proof, as the L1 gate. Gate conditions the refuter checks: full DA-1 schema with all constraints and partial indexes; batched single-statement invalidation with `invalidated_rows` recorded; same-transaction staleness that survives rollback; stale never served as current; recompute through the tenant-safe harness with a real `JobRun`. L1 must be green before T-004 (US-1) begins.
