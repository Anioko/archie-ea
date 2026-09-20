# T-005 / Task 02 — `GET /api/v1/intelligence/yield`, the p95 bucket read, and the Shape-B trigger

## Objective
Answer US-5 — "how much does derivation add" — as a single authenticated,
tenant-scoped endpoint that states the measured figures and sets no target,
keeps "not yet computed" distinguishable from a measured zero, reads p95 off
the T-004 histogram without inventing a percentile, and records a dated
Shape-B trigger event when the NFR-5 measurement point breaches 2.0s.

## Context
Read `00-verification-notes.md` first — D1, D2, D3, D4, D8, D11 and D12 are
binding and several of them correct the parent brief.

Components this **extends** (ADR 0008 — nothing new is created):
- `app/modules/intelligence/services/query_service.py` — `IntelligenceQueryService`
  gains a second static method `derivation_yield` alongside `cross_layer_impact`.
- `app/modules/intelligence/routes/api.py` — the **existing** `intelligence_api`
  blueprint (`url_prefix="/api/v1/intelligence"`), already registered once and
  non-fatally. Verified as the single blueprint on that prefix; do not create a
  second one (this was T-004's D1 defect).
- `app/modules/intelligence/services/latency_probe.py` — `record_query_latency`
  wraps the new query; the p95 **read** helper is added here too, next to the
  histogram it reads.
- `app/modules/intelligence/services/observability.py` — gains the Shape-B
  record, following `InvalidationRecord`'s shape exactly.
- `app/modules/intelligence/services/reason_codes.py` — gains one member.
- `tests/smoke/test_authorisation_matrix.py` — gains a row.
- Task 01's `derived_fact_aggregates` / `latest_derivation_run`.

## Constraints
- **p95 selector is pinned** to `{query="cross_layer_impact", depth="4",
  include_derived="true"}` on `archie_intelligence_query_seconds` (labels are
  `["query", "depth", "include_derived"]` — three, verified; the brief's guess
  of two is wrong). Never widen the selector, never aggregate across label
  values, and never fall back to a looser selector because the pinned one is
  empty (D12: empty is the correct, common answer — report `null` with
  `insufficient_samples_for_p95` and `sample_count: 0`).
- **The yield query must not measure itself** (D2). Wrapping `derivation_yield`
  in `record_query_latency("derivation_yield")` creates a new series; the p95
  read is pinned to `cross_layer_impact` and must be unaffected by calling the
  yield endpoint repeatedly.
- **p95 is a bucket-edge read** (D3): walk the histogram's cumulative `_bucket`
  counters for the pinned series and report the `le` of the first bucket whose
  cumulative count reaches 95% of the total. No interpolation, no averaging, no
  raw-sample retention, no arithmetic beyond the comparison. The reported value
  is always one of the declared boundaries. If the crossing bucket is `+Inf`,
  report `latency_seconds: null`, `"reason": "p95_above_highest_bucket"` and
  `"p95_exceeds_seconds": 5.0` — never `5.0` as if measured.
- **p95 is process-local and estate-wide, not per tenant** (D4). The histogram
  has no `organization_id` label and production runs three gunicorn workers.
  The p95 block is nested and self-describing with a `scope` field; it is never
  flattened into the per-tenant counts. **Do not add an `organization_id` label
  to the histogram** — unbounded cardinality on the hottest new metric, and it
  would mutate a metric shipped and deployed tonight.
- **No fabricated target anywhere.** No `target`, `threshold_target`,
  `goal` or benchmark-derived field for the ratio. The 2.0s value used for the
  Shape-B comparison is NFR-5's stated measurement threshold and appears only as
  the trigger's `threshold_seconds`, never as a yield target.
- Counts are `null`, never `0`, on the not-computed branch, and the response
  carries **both** `"state": "not_computed"` and
  `"reason": "derivation_not_computed"` (both already in the DE-14 vocabulary —
  no addition needed for these two).
- Exactly one new reason-code member: `p95_above_highest_bucket`, added in
  `reason_codes.py` and nowhere else, per that module's own rule.
- `@login_required`. Tenant scope comes from `_current_organization_id()` — the
  existing helper in `api.py` — and no tenant context is a 400 with
  `no_tenant_context`, matching the two existing routes. No route-level business
  logic; the route serialises the service through `success_response`.
- View function name `derivation_yield` (`cross_layer_impact` is taken in that
  file). Errors use `error_response` with a real status code — never a 200
  carrying an error (the `error-signalling` and `silent-data` gates).
- No new store, container or dependency in this task. No template, no UI
  blueprint, no front-end JS (see task 03).
- Release 1 exposes no query surface beyond US-1 and US-5 — add no L2 / US-2 /
  risk / coverage endpoint here (NFR-8).
- Live defects SR-11, SR-12, SR-13 are out of scope.

## Deliverable
1. `IntelligenceQueryService.derivation_yield()` — per-tenant, wrapped in
   `record_query_latency("derivation_yield")`, composing task 01's accessors
   plus the explicit-relationship count, returning the payload below.
2. A p95 read helper in `latency_probe.py` (e.g. `read_p95_bucket_edge(...)`)
   implementing the pinned-selector bucket-edge read.
3. `ShapeBTriggerRecord` in `observability.py` — frozen dataclass with
   `as_dict()`, fields at least `measured_p95_seconds`, `threshold_seconds`,
   `sample_count`, `query`, `depth`, `include_derived`, `recorded_at` — logged
   at WARNING and echoed into the response.
4. `GET /api/v1/intelligence/yield` on `intelligence_api`.
5. Tests in `app/modules/intelligence/tests/test_yield_endpoint.py` (shared
   fixtures from `tests/conftest.py`), a row in
   `tests/smoke/test_authorisation_matrix.py`, and a build report.

### Response shape (binding)

Computed branch:

    {"organization_id": ..., "state": "computed",
     "explicit_count": 1234, "derived_count": 4567, "ratio": 3.70,
     "computed_at": "...", "engine_version": ["1.0.0"],
     "stale_count": 12, "last_recompute_duration_ms": 8321,
     "p95": {"latency_seconds": 0.5, "sample_count": 412,
             "scope": "process_estate_wide", "query": "cross_layer_impact",
             "depth": 4, "include_derived": true, "reason": null},
     "shape_b_trigger": null, "reasons": []}

Not-computed branch (no `DerivationRun` row for this tenant):

    {"organization_id": ..., "state": "not_computed",
     "reason": "derivation_not_computed",
     "explicit_count": null, "derived_count": null, "ratio": null,
     "computed_at": null, "engine_version": null, "stale_count": null,
     "last_recompute_duration_ms": null,
     "p95": { ... as above, independent of derivation state ... },
     "shape_b_trigger": null}

The p95 block is reported on **both** branches — it measures query latency, not
derivation, and suppressing it on the not-computed branch would hide a real
breach.

## Acceptance Criteria
1. **Fields present (FR-7):** the computed branch carries `explicit_count`,
   `derived_count`, `ratio`, `computed_at`, `engine_version`, `stale_count`,
   `last_recompute_duration_ms`, and `p95` with `latency_seconds` and
   `sample_count`, for the calling tenant. Test asserts each key exists.
2. **Not-computed branch (F-13):** a tenant with no `DerivationRun` row gets
   BOTH `"state": "not_computed"` AND `"reason": "derivation_not_computed"`,
   with every count `null`. A separate test drives the D6 case end to end — a
   tenant that ran and derived zero returns `"state": "computed"` with
   `derived_count == 0` — and asserts the two responses differ. A test that only
   checks `null`-ness does not satisfy this criterion.
3. **Insufficient samples:** with fewer than 100 observations on the pinned
   series, `p95.latency_seconds` is `null` and
   `p95.reason == "insufficient_samples_for_p95"`, never a number. Test covers
   `sample_count == 0` and `sample_count == 99`; a test at 100 asserts a number
   appears.
4. **No fabricated target:** test asserts no key matching `target`/`goal`/
   `slo_target` appears anywhere in the payload, and that the ratio is reported
   as measured. The literal `2.0` appears only inside a `shape_b_trigger`.
5. **p95 source:** test observes known values directly onto
   `INTELLIGENCE_QUERY_DURATION` with the pinned labels and asserts the reported
   value is one of the histogram's declared bucket boundaries, and that it
   changes when the observations move across a boundary. A test asserts a value
   observed with a *different* `include_derived` or `depth` label does **not**
   move the reported p95 (D1). A further test calls the yield endpoint 200 times
   and asserts `p95.sample_count` for the pinned series is unchanged (D2).
6. **Above-top-bucket honesty:** observations above 5.0s produce
   `latency_seconds: null`, `reason: "p95_above_highest_bucket"`,
   `p95_exceeds_seconds: 5.0` — and still fire the Shape-B trigger.
7. **Scope honesty (D4):** test asserts `p95.scope == "process_estate_wide"`
   and that `p95` is a nested object, not flattened alongside the per-tenant
   counts.
8. **Shape-B trigger (ADR-009):** a simulated breach at the NFR-5 measurement
   point (observations pushing the pinned series' p95 above 2.0s) produces a
   `shape_b_trigger` object carrying a real `recorded_at`, the measured value,
   `threshold_seconds: 2.0` and the sample count, and emits one WARNING log
   record. Test asserts no build/work item, task, queue entry or state change is
   created by it — it opens a decision, it does not start work.
9. **Authorisation:** `@login_required` (an anonymous request does not get a
   200), and `tests/smoke/test_authorisation_matrix.py` is extended with a row
   for this route stating which of the eleven canonical archetypes should and
   should not reach it. A bespoke smoke test outside the matrix does not satisfy
   this.
10. **Tenancy (NFR-4):** with two orgs holding different counts, each tenant's
    response carries only its own figures; no field from the other tenant is
    reachable. Includes the `state` field — tenant A having run must not make
    tenant B report `computed`.
11. **Store agreement (D8):** immediately after
    `POST /api/v1/intelligence/derivation/recompute` for a tenant, that
    response's `explicit_count`, `derived_count` and `ratio` equal the yield
    endpoint's for the same tenant. Test asserts equality across the two
    surfaces, not against literals.
12. **Mutation proof (item 10 of the parent brief):** force the not-computed
    branch to emit `0` instead of `null`, confirm criterion 2's
    distinguishability test goes **red**, re-enable, record the test id in the
    build report. Implement the branch behind an isolated seam (the pattern
    `_apply_default_staleness_filter` and `_include_derived_gate` already
    establish in this module) so the test monkeypatches the seam rather than
    editing source under test.
13. **NFR-8 / Release 1 completeness:** a test enumerates `app.url_map` for
    `/api/v1/intelligence/*` and asserts exactly four rules — the T-003
    recompute POST, the T-003 provenance GET, T-004's impact GET, this yield
    GET. A second test asserts the L0 half (D9/section C of the verification
    notes): for a tenant whose facts were just recomputed, the reported
    `engine_version` equals `derivation_runner.ENGINE_VERSION`, read from the
    stored rows and not from the constant.
14. `python scripts/verify.py` (bare, not a `--tag` subset) is green, including
    `error-signalling`, `silent-data`, `fabricated-data`, `csrf-coverage`,
    `boot-health` and `store-agreement`.
15. Build report links FR-7 → DE-11 → each acceptance item above, records the
    mutation-proof test id, and states plainly that Release 1's **API** surface
    (L0 → L1 → US-1 → US-5) is complete while US-5 has **no user-facing screen**
    and is therefore not claimed as demonstrated (see task 03).

## Handoff Target
`builder`, then `refuter`. Do not begin before task 01 is `approved`.
