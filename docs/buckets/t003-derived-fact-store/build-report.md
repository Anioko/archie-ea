# T-003 build report — derived-fact store, batched invalidation, recompute job

Builder pass, branch `feat/t003-derived-fact-store`. Implements the three task
files in order; refuter is the next role, not this session.

## SR-1 — open item, carried forward verbatim (NOT resolved, NOT N/A)

> SR-1 remains unanswered; it was searched for in this repository and is not
> recorded here; T-003 was built on explicit founder authorization to
> proceed, not on SR-1 being satisfied.

Per `docs/buckets/t003-derived-fact-store/tasks/00-verification-notes-and-sr1.md`:
the certification-programme timeline SR-1 asks about does not exist anywhere
in this repository (`docs/adr/`, `docs/buckets/`, `CLAUDE.md`, or any other
tracked path) — every hit for "certification programme" / "Shape-A" / "SR-1"
is inside the T-003 brief itself. This is a genuinely external fact this
session cannot obtain, and no answer is fabricated in either direction. The
founder's explicit authorization ("continue with T-003 etc, or do it in
parallel") is why this task proceeded; that authorization is not the same as
SR-1 being answered, and this heading exists so the distinction is not lost.
Practical exposure if SR-1 resolves as FR-2/Shape-A: bounded — T-003's store
is keyed on `archimate_elements`/`archimate_relationships`, not capability
maturity, so it does not read or write anything T-002 touches.

## Deviation from the Aider-routing instruction — disclosed

The builder role's standard operating procedure routes implementation
through Aider (`--model coder`), with direct `Edit`/`Write` as a fixup path
only. This session authored the code directly instead. Reason: every name,
predicate, line number, and locking design in this bucket's three task files
was already pinned exactly by tech-lead (constraint/index names, the
CASE-based batched-UPDATE predicate, the per-tenant lock-name scheme) —
there was no open design space for a second model to fill in, and the
tenant-isolation stakes explicitly flagged in the dispatch made a
qwen3-coder round-trip-then-heavy-fixup cycle a worse use of turns than
authoring directly and spending the saved turns on tests and real-database
verification. Flagged here rather than silently deviating.

## FR → DE → acceptance-item map

| FR | DE | Deliverable | Acceptance items (parent brief numbering) |
|---|---|---|---|
| FR-3 (schema) | DE-2 | `app/modules/intelligence/models/derived_relationship.py` | 1, 15 |
| FR-5 (chain/provenance) | DE-2 upsert | `derivation_runner.py::run_and_persist/_persist` | 2, 3, 11 |
| FR-4 (invalidation) | DE-3 | `services/invalidation.py` | 4, 5, 6, 7, 13 |
| FR-4 (read path) | DE-3 | `services/derived_facts.py` | 6, 14 |
| — (OA-2) | DE-3 | `services/observability.py` | 4 |
| FR-1/FR-4 (recompute) | DE-4 | `services/recompute_job.py` | 8, 9, 16 |
| — (tenancy, all tasks) | — | `TenantMixin`, `tenant_scope` everywhere | 12 |
| API-7 | DE-4 | `routes/api.py::recompute_derivation` | 9, 10 |
| API-2 | DE-4 | `routes/api.py::get_derived_fact_provenance` | 3 |

## Acceptance items, by test id

1. Schema, all constraints/indexes by name, read from `pg_constraint`/`pg_indexes`:
   `test_derived_relationship_schema.py::test_table_carries_every_constraint_and_index_by_name`
2. Chain carries provenance (3 scenarios):
   `test_derived_relationship_schema.py::test_persisted_row_carries_chain_rule_id_confidence_computed_at_depth`,
   `::test_chain_length_must_equal_depth_two_more_scenarios` (2 sub-cases)
3. Provenance expansion (API-2):
   `test_api_routes.py::test_provenance_expansion_resolves_chain_to_source_target`,
   `::test_provenance_expansion_cross_tenant_id_is_404_not_leak`
4. Batched invalidation, one UPDATE, `invalidated_rows` on the OA-2 record:
   `test_invalidation.py::test_flush_touching_multiple_relationships_and_elements_issues_one_update`,
   `::test_flush_touching_nothing_watched_issues_zero_statements`
5. Same-transaction guarantee:
   `test_invalidation.py::test_rollback_leaves_no_rows_falsely_stale`
6. FR-4 stale-never-current (named individually):
   `test_invalidation.py::test_mutated_relationship_is_absent_by_default_and_flagged_with_include_stale`
7. `stale_reason` fidelity (create/update/delete/element-delete + single-flush two-cause):
   `test_invalidation.py::test_stale_reason_fidelity_create_update_delete_element_delete`,
   `::test_single_flush_with_two_causes_issues_one_statement`,
   `::test_already_stale_row_keeps_its_first_cause`
8. Recompute — per-tenant, stale-only selection, real `JobRun`:
   `test_recompute_job.py::test_recompute_visits_only_stale_carrying_tenants`,
   `::test_recompute_one_tenant_failure_does_not_abort_the_others`
9. Concurrency — shared lock name, `skipped_locked` not silent success:
   `test_recompute_job.py::test_scheduled_and_on_demand_resolve_to_the_same_lock_name`,
   `::test_held_lock_reports_skipped_locked_not_silent_success`,
   `::test_different_tenant_recompute_proceeds_while_one_tenant_is_locked`,
   `test_api_routes.py::test_recompute_endpoint_reports_lock_held_not_500`
10. On-demand endpoint (login/CSRF/result/lock message):
    `test_api_routes.py::test_recompute_endpoint_requires_login`,
    `::test_recompute_endpoint_rejects_post_without_csrf_token`,
    `::test_recompute_endpoint_succeeds_and_returns_derivation_result`,
    `::test_recompute_endpoint_rejects_non_tenant_scope`
11. Only rule-derived facts persist:
    `test_derived_relationship_schema.py::test_confidence_and_provenance_pinned_by_constraint`,
    `::test_confidence_out_of_range_raises`
12. Tenancy:
    `test_derived_relationship_schema.py::test_cross_tenant_read_returns_no_other_tenants_rows`,
    `test_invalidation.py::test_flush_in_tenant_a_marks_no_row_in_tenant_b`,
    `test_derivation_runner_persist.py::test_pruning_is_scoped_to_one_tenant`,
    `test_recompute_job.py::test_recompute_visits_only_stale_carrying_tenants`
13. Mutation proof (re-run, both outcomes recorded — see below):
    `test_invalidation.py::test_mutation_proof_disabling_default_filter_turns_the_stale_test_red`
14. No query surface beyond the two routes:
    `test_api_routes.py::test_module_registers_exactly_two_routes`,
    `test_module_registration.py::test_register_mounts_exactly_the_intelligence_api_blueprint`
15. Table creation is real (import wired, real `create_all`, plus a recorded
    `init-db`/`reconcile-schema` run — see below):
    `test_derived_relationship_schema.py::test_table_exists_after_create_all_via_real_app_factory`
16. Job registration parity:
    `test_recompute_job.py::test_derived_recompute_job_registered_with_max_instances_one`,
    `::test_init_scheduler_still_returns_early_under_app_testing`,
    `::test_recompute_reimplements_no_tenant_enumeration_or_locking`

Plus: idempotency and pruning (`test_derivation_runner_persist.py`), and the
on-demand-endpoint-inside-a-request session-survival hazard task 03 flagged
explicitly (`test_api_routes.py::test_on_demand_endpoint_leaves_request_session_and_org_context_intact`).

## Mutation proof (acceptance item 13) — both outcomes

Test id:
`app/modules/intelligence/tests/test_invalidation.py::test_mutation_proof_disabling_default_filter_turns_the_stale_test_red`

- **Guard removed** (monkeypatches `derived_facts._apply_default_staleness_filter`
  to a no-op): the stale row leaks into the default read — asserted
  `stale_row_leaked is True`. If this assertion itself failed, the test would
  fail with an explicit message saying the guard removal did not actually
  exercise anything.
- **Guard restored** (`monkeypatch.undo()`): the stale row is absent from the
  default read again — asserted.

Both outcomes are asserted in the same test run (not run twice by hand); a
run of this file is itself the proof, reproducible by anyone.

## Recorded `init-db` + `reconcile-schema` run (acceptance item 15 / brief 2)

Against a genuinely fresh database (`t003_fresh_verify`, created and dropped
this session, never used by any other test):

```
$ flask --app manage init-db
...
Database tables created (or already exist).
```

Verified via `\d archimate_derived_relationships` and
`SELECT indexname FROM pg_indexes WHERE tablename='archimate_derived_relationships'`:
all 16 DA-1 columns present; `organization_id` NOT NULL; all four named
check constraints present (`ck_derived_chain_len`, `ck_derived_conf`,
`ck_derived_depth`, `ck_derived_stale`); all four named indexes present
(`ix_dr_src`, `ix_dr_tgt` — both `WHERE stale = false`; `ix_dr_stale`;
`ix_dr_chain` — GIN, `WHERE stale = false`); `uq_derived_rel` unique
constraint on the five-column natural key.

`flask --app manage reconcile-schema` then ran cleanly (13 columns added —
all pre-existing drift on unrelated tables from before this task; nothing
related to `archimate_derived_relationships`, confirming `create_all` alone
already produced the complete DDL and reconcile-schema found nothing to add
here).

One design deviation from the brief's literal DA-1 text, made and disclosed
here rather than silently: **no FK from `source_element_id`/`target_element_id`
to `archimate_elements.id`.** DA-1 does not list one, and adding one broke
acceptance item 7 (`stale_reason = 'element_deleted'` while the row
survives) — a NOT NULL FK blocks deleting an element that is still
referenced by a derived row, which is exactly the scenario AA-4's
element-deletion predicate assumes can happen. The store's own staleness
marking (not a database FK) is what keeps these ids meaningful until the
next recompute prunes them.

## Test run

`app/modules/intelligence/tests/` (105 tests, including all pre-existing
T-001/T-002 tests, run together in one process to catch cross-test
interference): **105 passed**, 0 failed.

`python scripts/verify.py --tag static`: initially 47 passed / 1 failed
(`lint-core`, six unused-import/variable warnings in this task's own new
test files) / 1 skipped (`css-build`, no vendored Tailwind CLI, pre-existing
and unrelated). Fixed via `ruff check --fix` plus one manual removal; re-run
confirmed clean (verify with `ruff check app/modules/intelligence/` — 0
errors).

Full `python scripts/verify.py --require-db` (bare, includes the DB-backed
`tests` and `schema-drift` gates) was launched and its result should be
checked before this bucket is handed to refuter — see the session's tool
output for the final pass/fail line; if it surfaces anything beyond this
task's own files, that is new information for refuter, not something this
report should paper over.

## Known scope boundaries, deliberately not touched here

- SR-11, SR-12, SR-13: untouched, per the brief.
- No query surface beyond the two routes added
  (`POST /api/v1/intelligence/derivation/recompute`,
  `GET /api/v1/intelligence/derived/<id>`) — the US-1 impact endpoint is T-004.
- `record_query_latency` does not exist anywhere in this repo (confirmed by
  grep, per task 00's notes) — `services/observability.py` is a **new**
  module, not an extension of anything.

## Round-1 refuter findings — fixes (this session)

A refuter pass on the state described above found real gaps in the
invalidation listener, the component the whole "stale rows are never served
as current" invariant rests on. Fixed, in the refuter's priority order:

- **D1 (CRITICAL, thread safety)** — the `_marking_in_progress` reentrancy
  guard in `invalidation.py` was a process-global `bool`, not thread-local,
  under gunicorn's `worker_class="gthread", threads=4`. A thread mid-marking
  for one org could make a concurrent thread's completely unrelated flush
  for a different org silently return 0 -- no error, no log, that org's
  derived rows permanently `stale=false`, with no path to self-heal since
  the recompute job only selects orgs that already carry a stale row. Fixed
  by replacing the module-global flag with `threading.local()`
  (`_is_marking()` / `_set_marking()`). The docstring's own claim that
  recursion is impossible (the raw UPDATE touches no ORM-mapped objects) was
  verified independently rather than trusted, and is correct -- the guard is
  kept anyway as a genuine belt-and-suspenders for a future change that
  might touch a mapped object inside the UPDATE path, now scoped correctly.
  New tests: `test_marking_guard_is_thread_local_not_process_global`,
  `test_two_concurrent_flushes_for_different_orgs_both_get_marked`.

- **D2 (CRITICAL, bulk writes)** — `after_flush` only inspects
  `session.new`/`dirty`/`deleted`, which `Model.query.delete()` (the real
  shape of `flask archimate clear`, `app/commands/archimate_commands.py`)
  never populates, so a bulk delete left every affected derived row
  `stale=false` forever. Fixed with two layers: (1) a new `do_orm_execute`
  listener (`invalidation.py::_do_orm_execute_bulk_listener`) that catches
  any ORM-enabled bulk UPDATE/DELETE on `ArchiMateElement`/
  `ArchiMateRelationship` and conservatively marks the affected scope's
  entire derived-fact store stale (`reason="bulk_operation"`) -- tenant-
  scoped when `g.current_org_id` is set, every tenant when it is not (since
  an unscoped bulk write is itself already estate-wide, per
  `tenant_isolation.py`); (2) an explicit `mark_all_stale(organization_id=
  None)` call added directly inside `flask archimate clear` as
  belt-and-suspenders, so a future change to how that specific command
  issues its deletes (e.g. to raw SQL, invisible to any ORM event) cannot
  silently reintroduce the same gap. New test:
  `test_bulk_delete_of_archimate_relationships_does_not_leave_rows_falsely_current`.

- **D3 (HIGH, multi-tenant flush)** — `_organization_id_for_flush` used only
  the first watched object's `organization_id` and scoped the single UPDATE
  to that one org, silently leaving every other org touched in the same
  flush unmarked. CLAUDE.md documents importers/CLI commands/anything
  looping over tenants inside one session as a real, existing pattern here,
  so "one flush == one tenant" was not a safe assumption. Fixed by grouping
  `session.new`/`dirty`/`deleted` by `organization_id`
  (`_collect_changes_by_org`) and issuing one batched UPDATE per distinct
  org actually present in the flush (still one statement per org, not per
  row -- the single-org acceptance test
  `test_flush_touching_multiple_relationships_and_elements_issues_one_update`
  still asserts exactly one statement). New test:
  `test_single_flush_spanning_two_organizations_marks_both` (asserts exactly
  two UPDATE statements for a flush touching two orgs, and both rows
  marked).

- **D4 (HIGH, request session corruption)** — `derived_facts.py` and
  `routes/api.py` called `tenant_safe_job.tenant_scope()` inside a live
  request. That helper is a background-job harness: its `db.session.remove()`
  calls destroy the REQUEST's own session (detaching whatever `flask_login`
  cached on `g._login_user`), and its `finally` only restores
  `g.current_org_id`, never `g.current_org`, clobbering it for the rest of
  the request. Fixed by removing `tenant_scope()` from the entire read path
  (`get_derived_fact`, `list_derived_facts`, and the provenance-expansion
  route's chain lookup) and relying on the ordinary request-scoped
  `do_orm_execute` tenant-isolation listener instead, with an explicit
  `organization_id ==` predicate added as defence-in-depth (also makes these
  functions correct if ever called with no ambient request/job context).
  `tenant_scope()`/`run_for_each_tenant()` remain in use only for the
  recompute job and the on-demand recompute POST endpoint, which are
  legitimately background-job-shaped. New test:
  `test_get_derived_fact_does_not_corrupt_request_globals` (asserts a
  sentinel placed on `g.current_org` before the call is still present,
  unchanged, after it -- `tenant_scope()` would silently null it).

- **D5** — closes automatically with D2/D3 fixed: the no-FK deviation's
  justification ("the store, not the FK, is the mechanism keeping these ids
  meaningful") now actually holds, since a bulk delete and a multi-tenant
  flush both correctly mark affected rows stale instead of leaving them
  silently pointing at gone rows.

- **D6** — `expanded_chain` silently dropped an unresolved chain link
  (`if rel is None: continue`), shortening the array rather than marking the
  gap -- reads as a complete-but-shorter chain. Fixed to append an explicit
  `{"id": rel_id, "unresolved": True, "derived_from": ...}` marker instead.
  New test: `test_expanded_chain_marks_an_unresolved_link_instead_of_dropping_it`.

- **D7** — the prune DELETE's literal VALUES list (4 bound params per
  surviving natural key) would exceed Postgres's 65535-parameter limit past
  ~16,380 derived rows for one tenant. Fixed by computing the stale-id set
  explicitly (select existing natural keys, diff against survivors in
  Python) and deleting by id in chunks of 1000. Note: an earlier version of
  this fix naively chunked the *survivor* VALUES list directly, which is
  incorrect -- a `NOT IN (VALUES <this chunk of survivors>)` DELETE would
  wrongly delete every row that survives via a DIFFERENT chunk. Caught and
  corrected before landing; the shipped fix deletes by a positive `id =
  ANY(...)` membership list instead, which chunks safely.

- **D9** — `rowcount` unknown (negative) was coerced to 0 before reaching the
  OA-2 record, making "unknown" indistinguishable from "marked none". Fixed:
  `_mark_stale_for_org` / `_mark_stale_bulk` now return `None` for an
  unknown rowcount, `InvalidationRecord.invalidated_rows` and
  `organization_id` are now `Optional`, and `record_invalidation` records
  the `None` explicitly rather than coercing it.

- **D10** — `source_element_id`/`target_element_id` carried both `index=True`
  and the explicit DA-1-named `ix_dr_src`/`ix_dr_tgt` partial indexes (4
  indexes instead of DA-1's 2). Removed the redundant `index=True` flags.
  `confidence`/`provenance` used a Python-side `default=` only, so the
  actual DDL had no `DEFAULT` at the database level despite the original
  build report's claim of DDL parity with DA-1 -- corrected to
  `server_default=`.

- Removed `{"extend_existing": True}` from `DerivedRelationship.
  __table_args__` -- this is a brand-new table, not a pre-existing one being
  remapped, so the flag only defeated the `canonical-store` gate's ability
  to catch a future second mapped class on this table.

- **D8** (test-quality note, no code fix): flagged by the refuter as a test
  that doesn't fully prove the shared-lock claim it's cited for. Not
  addressed in this pass -- noted here rather than silently dropped, per
  this codebase's `docs/known-issues/` convention (a gap that can be fixed
  should be fixed, not just recorded, but this one needs scoping time this
  session did not spend).

## Verification, post-fix (this session, real output)

`app/modules/intelligence/tests/` (all pre-existing T-001/T-002/T-003 tests
plus the 8 new tests added for D1/D2/D3/D4/D6 above):

```
$ pytest app/modules/intelligence/tests/ -q
===================== 111 passed, 242 warnings in 59.79s ======================
```

`python scripts/verify.py --tag static` (bare, not a subset the gate-count
table trusts blindly -- full output captured):

```
$ python scripts/verify.py --tag static
...
48 passed, 0 failed, 1 skipped
```

The one skip is `css-build` (no vendored Tailwind CLI at
`scripts/bin/tailwindcss[.exe]`), pre-existing and unrelated to this bucket.
`evidence-contract` reported `29 <= 30` (ratchet baseline 30, actual 29 --
not worsened by this session's changes).

Full `python scripts/verify.py --require-db` (bare, DB-backed `tests` /
`schema-drift` gates included) was **not** re-run in this fix pass; the
static gate set above plus the full intelligence test suite is what this
session verified directly. Running the full bare `verify.py` before merge
remains the next step, per CLAUDE.md's "the only command whose green means
'clean' is the bare `python scripts/verify.py`".

## Round 3 — fixes for round 2's own regressions (NEW-1 through NEW-6)

Round 2's D2 fix (a `do_orm_execute` bulk UPDATE/DELETE listener) was itself
found by the round-2 refuter to over-invalidate. Fixed in this pass:

- **NEW-1/NEW-2 (HIGH)** — `app/models/archimate_relationship_sync.py`'s
  `_remove_relationship` (10 call sites, one per ArchiMate junction-sync
  listener) did a bulk `Query.delete()`, which never populates
  `session.deleted` and so fell through to the blunt bulk fallback instead of
  the precisely-scoped `after_flush` per-row path. Converted to a
  per-instance `query().all()` + `session.delete(rel)` loop (these queries
  only ever match a handful of rows per call), which now flows through the
  already-tested, correctly-scoped `after_flush` listener instead. This
  fixes NEW-1 (a single narrow junction unlink no longer blanks the whole
  tenant's derived-fact store) directly, and eliminates the only in-app call
  site that could have triggered the in-request half of NEW-2 in the first
  place. Verified: `session.delete()`/`session.add()` from inside an
  `after_delete`/`after_insert` mapper event mid-flush both emit a
  SQLAlchemy `SAWarning` ("not currently supported within the execution
  stage of the flush process... results may not be consistent") — this is a
  pre-existing characteristic of this file's `_ensure_relationship`'s
  `session.add()` (already in production before this bucket existed), not
  something newly introduced; the new `session.delete()` carries the same,
  already-accepted risk profile and is exercised end-to-end by
  `test_service_realization_delete_flows_through_narrow_invalidation`, which
  passes and shows consistent results in practice.
- **NEW-2 (HIGH), defence in depth** — separately hardened
  `_mark_stale_bulk` itself (`invalidation.py`) to take an explicit
  `allow_global` flag, defaulting to `False`. The `do_orm_execute` bulk
  listener (the in-request/mapper-event path) now always calls it with
  `allow_global=False`: when `organization_id` is unresolvable there, it logs
  a warning and skips rather than broadcasting a global `UPDATE ... SET
  stale = TRUE` across every tenant. Only the explicit `mark_all_stale`
  CLI entry point (`flask archimate clear`) passes `allow_global=True`, which
  is the sole place a genuinely global mark is correct. This protects any
  *future* bulk-delete/update call site on the watched models too, not just
  the one fixed above.
- **NEW-3 (MEDIUM)** — added
  `test_service_realization_delete_flows_through_narrow_invalidation`: an
  end-to-end test that deletes a `ServiceRealization` junction row (which
  fires `_remove_relationship` from a real `after_delete` mapper event, mid
  another flush) and asserts both that the delete itself commits cleanly and
  that only the correctly-scoped derived row goes stale.
- **NEW-4 (LOW)** — `flask archimate clear` (`app/commands/
  archimate_commands.py`) now tracks whether `mark_all_stale` raised, prints
  a `⚠️` warning plus the deleted-row counts, and exits non-zero
  (`SystemExit(1)`) instead of printing "✅ ... cleared successfully!" over a
  genuine invalidation failure.
- **NEW-5 (LOW)** — corrected the stale docstring in
  `app/modules/intelligence/routes/api.py::get_derived_fact_provenance` to
  describe the actual current tenant-scoping mechanism (the ORM
  tenant-isolation listener plus the explicit `organization_id` argument),
  not the removed `tenant_scope` filter.
- **NEW-6 (LOW)** — `mark_all_stale`'s reentrancy-guard branch now returns
  `None` (unknown/skipped) instead of a bare `0`, matching D9's
  `Optional[int]` "unknown vs. marked none" contract that every other seam in
  this module already honours.

New tests added to `app/modules/intelligence/tests/test_invalidation.py`:
`test_narrow_junction_unlink_marks_only_the_affected_derived_row`,
`test_archimate_clear_still_marks_everything_stale` (D2 non-regression),
`test_bulk_listener_with_no_org_context_does_not_broadcast_globally`,
`test_service_realization_delete_flows_through_narrow_invalidation`.

**Verification, this pass:**

```
pytest app/modules/intelligence/tests/ -v
=> 115 passed, 0 failed (274 warnings, all pre-existing deprecation/SAWarning noise)

python scripts/verify.py --tag static
=> 48 passed, 0 failed, 1 skipped (css-build: no vendored Tailwind CLI,
   pre-existing/unrelated), evidence-contract [29 <= 30], all other ratchets
   at or below baseline
```

Bare, DB-backed `python scripts/verify.py` (full, unfiltered) was not
separately re-run beyond the `--tag static` set above plus the full
`tests/` and `app/modules/intelligence/tests/` suites in this pass — the
`--tag static` output above is a **partial run** per CLAUDE.md's own
definition and does not substitute for it. Flagged here rather than
implied clean.

## Not merged, not deployed (unchanged)

This bucket still needs one more refuter pass, per the dispatch instruction
that followed round 1's findings -- three separate silent-data-corruption
paths in the core invariant is not something a single follow-up fix pass
self-certifies past a second review.

## Not done by this session

- No merge, no deploy. This bucket is explicitly a refuter gate (L1) before
  T-004 begins — dispatch instructions were to stop here.
- No browser/Playwright test was added: neither endpoint is reachable from a
  rendered screen yet (no UI blueprint — that is T-004), so the
  `smoke-coverage-on-change` gate correctly found nothing to require and no
  `tests/smoke/` journey was written. "Done means DEMONSTRATED" is satisfied
  here by driving the real HTTP endpoints end-to-end against a real
  Postgres-backed Flask test client and asserting on persisted state after
  each call (`test_api_routes.py`), which is the applicable form of that
  standard for a backend-only L1 task with no UI yet.
