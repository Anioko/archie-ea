# T-005 (US-5) — build report

Backend implementation of `docs/buckets/t005-us5-yield-report/tasks/01-run-record-and-yield-aggregates.md`
and `.../02-yield-endpoint-p95-read-and-shape-b-trigger.md`, against the corrected design in
`00-verification-notes.md`. Task 03 is a descope record only — no code from it.

## FR-7 → DE-11 → acceptance-item → test-id trace

### Task 01 — `intelligence_derivation_runs` run-record store and aggregates

| Acceptance item | Test |
|---|---|
| 1 (written row matches result) | `test_derivation_run_record.py::test_completed_run_writes_one_run_record_matching_the_result` |
| 2 (D6: zero vs never-ran) | `test_measured_zero_is_distinguishable_from_never_ran` |
| 3 (failed/lock-skipped write no row) | `test_failed_run_writes_no_run_record`, `test_lock_skipped_recompute_writes_no_run_record` |
| 4 (atomicity) | `test_facts_and_run_record_commit_atomically` |
| 5 (tenancy, incl. session-removal loop) | `test_run_record_is_tenant_scoped`, `test_run_record_tenant_loop_with_session_removal_between_tenants` |
| 6 (aggregate counts match direct SQL; null computed_at) | `test_derived_fact_aggregates_matches_direct_count_and_null_computed_at` |
| 7 (bounded statements, no row materialisation) | `test_derived_fact_aggregates_does_not_materialise_rows` |
| 8 (engine_versions from stored rows, not the constant — D9) | `test_engine_versions_reflects_stored_rows_not_the_module_constant` |
| 9 (ratio None not 0) | `test_ratio_is_none_not_zero_when_explicit_count_is_zero` |
| 10 (schema safety) | `test_reconcile_schema_reports_no_drift_after_init_db` + real `flask reconcile-schema --dry-run` run below |
| 11 (verify.py green) | see Verification section |

### Task 02 — `GET /api/v1/intelligence/yield`, p95 bucket-edge read, Shape-B trigger

| Acceptance item | Test |
|---|---|
| 1 (fields present, FR-7) | `test_yield_endpoint.py::test_computed_branch_carries_every_required_field` |
| 2 (not-computed vs measured-zero, D6) | `test_not_computed_branch_carries_state_and_reason_with_null_counts`, `test_measured_zero_differs_from_not_computed_end_to_end` |
| 3 (insufficient samples) | `test_p95_null_with_insufficient_samples_below_100`, `test_p95_sample_count_boundary_99_vs_100` |
| 4 (no fabricated target) | `test_no_fabricated_target_field_anywhere_in_payload` |
| 5 (p95 source: pinned selector, bucket edges, label isolation, self-pollution) | `test_p95_reads_declared_bucket_boundaries_and_moves_across_them`, `test_p95_unaffected_by_different_include_derived_or_depth_label`, `test_repeated_yield_calls_do_not_move_the_pinned_series` |
| 6 (above-top-bucket honesty + still fires Shape-B) | `test_above_highest_bucket_reports_null_with_reason_and_still_fires_shape_b`, `test_shape_b_trigger_fires_on_pinned_series_breach` |
| 7 (scope honesty, D4) | `test_p95_scope_is_process_estate_wide_and_nested` |
| 8 (Shape-B trigger, no work item) | `test_shape_b_trigger_fires_on_pinned_series_breach`, `test_shape_b_trigger_creates_no_work_item_or_queue_entry` |
| 9 (authorisation) | `test_yield_route_rejects_anonymous` (unit) + `tests/smoke/test_authorisation_matrix.py::test_intelligence_yield_route_authorisation` (eleven-archetype row) + `test_intelligence_yield_route_rejects_anonymous_browser_session` |
| 10 (tenancy) | `test_yield_response_is_tenant_scoped` |
| 11 (store agreement, D8) | `test_recompute_and_yield_agree_on_explicit_derived_ratio` |
| 12 (mutation proof) | **`test_yield_endpoint.py::test_mutation_proof_not_computed_zero_seam`** — monkeypatches `query_service._not_computed_counts` to emit `0` instead of `None`; the payload then reports `derived_count == 0` under `state == "not_computed"`, which is exactly the fabrication the real seam prevents and which would flip `test_measured_zero_differs_from_not_computed_end_to_end` red were the seam removed in production code |
| 13 (NFR-8 / Release 1 completeness) | `test_exactly_four_intelligence_routes_registered`, `test_release1_l0_engine_version_matches_runner_constant_on_stored_rows` |
| 14 (verify.py green) | see Verification section |
| 15 (this report) | this file |

## Verification (real output)

### `pytest app/modules/intelligence/tests/ -v` (ran as `-q`)

```
178 passed, 1217 warnings in 232.28s (0:03:52)
```

All pre-existing suites in this directory (T-001/T-003/T-004's tests) still pass. Three pre-existing
tests needed lockstep updates for the new fourth route / nineteenth reason code, matching this
module's own documented convention that these counts are not frozen:

- `test_api_routes.py::test_module_registers_exactly_three_routes` → renamed
  `test_module_registers_exactly_four_routes`, asserts the new `intelligence_api.derivation_yield`
  endpoint.
- `test_module_registration.py`'s blueprint deferred-function count moved from 3 to 4.
- `test_reason_codes.py::test_reason_codes_has_exactly_eighteen_members` → renamed
  `test_reason_codes_has_exactly_nineteen_members`, adds `p95_above_highest_bucket`.
- `test_derivation_runner.py::test_runner_uses_tenant_scope_and_never_hand_writes_organization_id`
  was tightened to a line-scoped scan so the new `DerivationRun(organization_id=organization_id, ...)`
  WRITE-side constructor call (a legitimate model-construction keyword, not a READ filter) does not
  false-fail the "no hand-written tenant predicate on a READ" check the test exists to enforce.

### `flask reconcile-schema --dry-run` (against a database that already ran `init-db` with the new model registered)

```
reconcile-schema: 0 column(s) would add.

2 column(s) FAILED:
  ! typed_arb_constraints:foreign_key_malformed:fk_arb_review_cycle_adr
  ! typed_arb_constraints:foreign_key_malformed:fk_arb_subject_snapshot_adr
```

Zero drift from `intelligence_derivation_runs` — the two failures are pre-existing, on an unrelated
table (`typed_arb_constraints`), and not touched by this bucket.

### `python scripts/verify.py --tag static`

```
48 passed, 0 failed, 1 skipped
```

The one skip (`css-build`) is the pre-existing, documented "no vendored Tailwind CLI on this
machine" skip — unrelated to this bucket, and CI runs it with `--require-db` so it is not silently
skipped there. No template/JS/CSS was touched by this bucket (backend-only, per task 03's descope),
so `smoke-coverage-on-change` correctly reports 0.

**Not run in this session:** the bare `python scripts/verify.py` (full run, including `tests`/
`schema-drift` gates which need the full suite + a clean recreate) and the Playwright
`tests/smoke/` browser tier — both are appropriately the refuter's / QA lead's next pass per this
bucket's handoff target, and per CLAUDE.md the browser tier requires a live server harness beyond
what a backend-only bucket exercises directly. The new
`tests/smoke/test_authorisation_matrix.py::test_intelligence_yield_route_authorisation` row and its
anonymous-rejection sibling are written and `py_compile`-clean but were not driven against a live
server in this session.

## Design decisions carried from `00-verification-notes.md` (implemented, not re-litigated)

- `intelligence_derivation_runs` (D5-D7): one row per tenant per completed `run_and_persist`, written
  atomically with the derived-fact upsert, in the same `tenant_scope` block, before the commit.
  `DerivationRunner.run_and_persist` now takes a required `trigger` keyword (`"scheduled"` from
  `recompute_derived_facts`, `"on_demand"` from `recompute_derived_facts_on_demand`) — never guessed.
- p95 is a bucket-edge read (D3) via `latency_probe.read_p95_bucket_edge`, using
  `Histogram.collect()`'s public API — never `histogram_quantile` (no Prometheus server exists here),
  never interpolated, never averaged. Reports `p95_above_highest_bucket` with `p95_exceeds_seconds:
  5.0` when the 95th percentile falls in the `+Inf` overflow bucket, and still fires the Shape-B
  trigger (the exceeded-bucket fact is itself real evidence of a breach).
- p95 is pinned to `{query="cross_layer_impact", depth="4", include_derived="true"}` (D1) and reported
  as its own nested `{"scope": "process_estate_wide", ...}` block on both response branches (D4) —
  never flattened alongside the per-tenant counts, never per-tenant.
- `derivation_yield` is wrapped in its own `record_query_latency("derivation_yield")` series, kept
  separate from the pinned `cross_layer_impact` selector the p95 read is pinned to (D2) — a dedicated
  test calls the endpoint 200 times and asserts the pinned series' `sample_count` is unchanged.
- `explicit_count`/`derived_count`/`ratio`/`last_recompute_duration_ms` come from the tenant's
  `DerivationRun` row itself — the same values API-7's recompute response already returns (D8); a
  test asserts the two surfaces agree immediately after a recompute.
- `engine_version`/`computed_at`/`stale_count` come from `derived_fact_aggregates` — the store's own
  current state, not the `ENGINE_VERSION` module constant (D9).
- `ShapeBTriggerRecord` (D11, ADR-009) follows `InvalidationRecord`/`QueryLatencyRecord`'s existing
  shape exactly: a frozen dataclass with `as_dict()`, logged at WARNING (a breach, not routine
  telemetry), echoed into the response body. No table, no workflow, no queue entry.

## Release 1 (L0 → L1 → US-1 → US-5) status

The **API surface** is complete: exactly four `/api/v1/intelligence/*` routes are registered
(recompute POST, provenance GET, impact GET — T-004 — and yield GET — this bucket), verified by
`test_exactly_four_intelligence_routes_registered`, and the L0 half (a tenant's reported
`engine_version` equals `derivation_runner.ENGINE_VERSION`, read from the stored rows and not the
constant, for a tenant whose facts were just recomputed) is verified by
`test_release1_l0_engine_version_matches_runner_constant_on_stored_rows`.

**This is not a claim that Release 1 is demonstrated.** Per task 03's descope record, US-5 (and
US-1) have **no user-facing screen** in this codebase — `app/modules/intelligence/` still has no
`templates/` directory and no `routes/ui.py`; the reserved UI-blueprint slot in `register(app)`
remains unused. "Release 1 complete" in this report means its API surface is complete and green,
not that a person has clicked through a rendered "Yield & health" screen — that is T-005b, briefed
jointly with T-004b, per task 03's entry conditions.

## Refuter round-2 fixes

The refuter reviewed this bucket and found it in good shape overall: one real blocker (D-1) and
four minor items. All five addressed:

- **D-1 (BLOCKER)** — `test_derivation_runner.py`'s tenant-scope-scan guard whitelisted its one
  legitimate write-side line (`DerivationRun(organization_id=organization_id, ...)`) by substring
  containment (`allowed_line_substring in line`) rather than exact match, which meant a hand-written
  READ-side predicate containing that same substring alongside other content — e.g.
  `.filter_by(organization_id=organization_id, trigger=trigger)` — would be silently skipped by the
  guard instead of caught. Changed to `line.strip() == allowed_line_substring`. Verified by hand:
  temporarily inserted exactly that fake `.filter_by(...)` READ call into `derivation_runner.py`,
  confirmed the guard test now fails on it (`AssertionError: found a hand-written organization_id
  predicate ('organization_id=') on line 74`), then removed the fake line and confirmed the test
  passes again. `git diff` on `derivation_runner.py` after the revert is clean (no residue).
- **D-2 (minor)** — `query_service.py`'s not-computed branch was missing a `reasons` key (the
  computed branch has always had `"reasons": []`), so a client reading `data["reasons"]` on a fresh
  tenant's first call would `KeyError`. Added `"reasons": []` to the not-computed branch alongside
  the existing singular `"reason"` field (kept, not removed).
- **D-3 (minor)** — `test_repeated_yield_calls_do_not_move_the_pinned_series` only asserted the
  negative half (the pinned `cross_layer_impact` series is unaffected by 200 yield calls), which
  would stay green even if `derivation_yield`'s own probe were mislabelled onto the pinned selector.
  Extended the same test to also assert `derivation_yield`'s own series (labelled `query=
  "derivation_yield", depth="unknown", include_derived="false"` — `record_query_latency
  ("derivation_yield")` never sets `scope.depth`/`scope.include_derived`, so it resolves to
  `latency_probe.py`'s own fallback labels) moves by exactly the number of calls made. Both halves
  now pin that the two label sets are genuinely disjoint.
- **D-4 (minor)** — `_INSUFFICIENT_SAMPLES_REASON` and `_ABOVE_HIGHEST_BUCKET_REASON` in
  `latency_probe.py` were bare string literals bypassing `validate_reason_code(...)`, unlike every
  reason code in `query_service.py`. Both now route through `validate_reason_code(...)` at
  declaration, matching the existing module-level pattern (`NO_OWNERSHIP_REASON = validate_reason_code
  ("no_ownership_recorded")` etc. in `query_service.py`). Both codes were already present in
  `reason_codes.py`'s closed vocabulary, so this is enforcement-only, no vocabulary change.
- **D-5 (minor, judgment)** — addressed rather than deferred: added a `last_run_at` field to the
  computed branch of `derivation_yield`'s response, sourced from the tenant's latest
  `DerivationRun.finished_at` (independent of `derived_fact_aggregates`, which reads the
  now-empty-for-a-zero-yield-tenant `archimate_derived_relationships` table and so honestly nulls
  `computed_at` even when derivation genuinely ran). `computed_at` is unchanged and still specifically
  describes the derived-fact store's own freshness; `last_run_at` is a distinct, additive fact.

### Verification (real output, round 2)

`pytest app/modules/intelligence/tests/ -v` (ran as `-q` for the full-suite confirmation run):

```
178 passed, 1217 warnings in 57.38s
```

`python scripts/verify.py --tag static`:

```
48 passed, 0 failed, 1 skipped
```

Same one pre-existing, documented skip (`css-build` — no vendored Tailwind CLI on this machine;
unrelated to this bucket, no template/JS/CSS touched). `evidence-contract` reads `[29 <= 30]` in
this run (ratchet against the live measurement at run time, not a fixed number — see CLAUDE.md's
own correction note on this gate).

## Release 1 (L0 → L1 → US-1 → US-5) — closing status

The API surface for Release 1 is complete and green: `recompute` POST, `provenance` GET, `impact`
GET (T-004), and `yield` GET (this bucket) — four `/api/v1/intelligence/*` routes, backend-verified
end to end. The UI is explicitly deferred: `app/modules/intelligence/` has no `templates/` directory
and no `routes/ui.py`; the reserved UI-blueprint slot in `register(app)` is unused. That is T-004b/
T-005b, per task 03's descope record — not silently missing, a recorded follow-up.

## Handoff

`refuter`, per task 02's handoff target — round 2 complete, all five items addressed. Not merged,
not deployed by this bucket; a final confirmation pass and the merge/deploy decision are the next
step, per this task's own instruction to hand back rather than self-declare a release closed.
