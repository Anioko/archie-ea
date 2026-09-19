# T-004 — US-1 Cross-Layer Impact Endpoint: Build Report

**Revision 3 (second refuter fix pass).** Round 2 fixed B1/B3/M4-M7 but its
B2 fix (SEC-09 traceability) was itself found broken on inspection: round 2
independently moved owner resolution onto a new batched function
(`_resolve_owners_batch`, for the M7 N+1 fix) while its SEC-09 test still
targeted the old per-row `_resolve_owner`/`_find_component_for_element`
pair — which the refuter confirmed had **zero production callers** left.
Round 2 also introduced five new defects (NEW-1 through NEW-5) while fixing
the earlier ones. All of these are fixed in this revision; see below.

**Revision 2 (first refuter fix pass).** Found three blocker-class defects
(B1-B3) and four major-class defects (M4-M7), listed and fixed then, plus
two of the four "if time permits" medium items. In particular, the
revision-1 SEC-09 traceability claim (naming
`test_mutation_proof_sec09_and_include_derived_filter` as proof) was **false**
and was corrected then — see "SEC-09 traceability correction" below (now
itself corrected a second time, for revision 3).

Scope: tasks 01 and 02 only. Task 03 (`03-ui-surfaces-descope-record.md`) is
a decision record, not a build task, and is not implemented here.

## Revision 3 fixes (this pass)

- **B2, third attempt — resolved via Option (b) (delete the dead code).**
  Traced every caller of `_resolve_owner`/`_find_component_for_element` with
  `grep -rn` across the whole worktree (excluding tests): **zero production
  callers** confirmed. Deleted both functions entirely from
  `query_service.py`. `_resolve_owners_batch` (the M7 batching fix) is now
  the SOLE owner-resolution implementation, and is `cross_layer_impact`'s
  only caller. The two SEC-09 tests
  (`test_sec09_tenant_check_blocks_real_cross_tenant_resolution`,
  `test_mutation_proof_sec09_real_path`, in
  `app/modules/intelligence/tests/test_query_service.py`) now call
  `_resolve_owners_batch([target.id], org_a.id)` directly instead of the
  deleted `_resolve_owner`, keeping the same genuine session-drift
  construction (`g.current_org_id` set to org B, an explicit divergent
  `org_id=org_a.id` passed in) against the real, unmodified,
  production-reachable function.

  **Honest status, stated plainly per the refuter's instruction:** this
  scenario is real production code (not a dead seam — deleting
  `_sec09_tenant_check`'s guard from `_resolve_owners_batch` would NOT be
  caught by the existing cross-tenant leak test, because
  `ApplicationComponent`'s automatic `TenantMixin` ORM filtering already
  drops the foreign component before the guard matters, in a plain
  per-request call). What the two tests above prove is narrower and
  accurate: the guard behaves correctly on the one call shape that COULD
  make it load-bearing (an explicit, caller-supplied `org_id` diverging from
  `g.current_org_id` within one session) — a shape this repo's own
  CLAUDE.md tenant-isolation section names as a real exposure class for
  CLI/scheduler/importer code, but one neither of `_resolve_owners_batch`'s
  two current real callers (`cross_layer_impact`'s two HTTP entry points)
  actually produces today, since both read `org_id` from the same
  `g.current_org_id` the ORM filter reads. SEC-09 remains genuine
  defense-in-depth with a real, reachable-by-direct-call proof — not a
  guarantee that today's HTTP call graph can currently diverge into. This is
  the honest final answer: no further mutation-proof rewrite is warranted
  unless a genuine divergent-org_id caller is added to this codebase.

- **NEW-1 (fabricated `derivation_state` for a nonexistent/cross-tenant
  element_id) — fixed.** `app/api/v1/impact.py::analyze_impact` now queries
  `ArchiMateElement` (TenantMixin-fenced, so a foreign-tenant row is already
  invisible) for the `element_id` branch BEFORE calling
  `ImpactAnalysisService.analyze_change_impact`, and returns a real 404 when
  it does not resolve, instead of proceeding to fabricate a
  `derivation_state: "not_computed"` 200 for something that was never
  analysed. Tests:
  `test_canonical_endpoint_nonexistent_element_id_is_404_not_fabricated`,
  `test_canonical_endpoint_cross_tenant_element_id_is_404_not_fabricated`
  (`app/modules/intelligence/tests/test_impact_route.py`).
- **NEW-2 (literal `"not_computed"` fallback fabricates state) — fixed.**
  `_derived_elements_for_element` now does `summary["derivation_state"]`
  (a `KeyError` on a genuinely missing key, surfacing as a 500 via the
  caller's `except Exception` block) instead of
  `summary.get("derivation_state", "not_computed")`. `cross_layer_impact`
  sets this key on every branch, so the only way this key is ever missing is
  a real bug, which must now look like a bug.
- **NEW-3 (dead duplicate owner-resolution implementation) — fixed as part
  of the B2 fix above.** `_resolve_owner`/`_find_component_for_element` are
  deleted; `_resolve_owners_batch` is the one remaining implementation, and
  its own docstring now explains the duplicate-component-pointer dedup
  logic inline (the B3 fix) instead of that logic living only in the now-
  deleted function.
- **NEW-4 (the `no_tenant_context`/`element_not_found` reason codes were
  structurally unreachable in the 200 `reasons` list) — fixed via the
  "wire into the error body" branch of the refuter's option (b).** Both
  conditions are intercepted by an early 400/404 return in
  `app/modules/intelligence/routes/api.py::cross_layer_impact` before
  `IntelligenceQueryService.cross_layer_impact` is ever called, so they can
  never appear in that route's 200 `reasons` list — confirmed by re-reading
  the route's own control flow. Rather than leave the two reason codes
  reachable only from a direct unit-test call into the service, they are now
  attached as `details: {"reason": ...}` on the exact 400 (`NO_TENANT_CONTEXT`)
  and 404 (`NOT_FOUND`, "Element not found") responses that ARE their real
  home — the same call site for both the cross-tenant and nonexistent-element
  404 cases, so D3 indistinguishability is unaffected (both get the identical
  `details` value). Test:
  `test_404_indistinguishability_cross_tenant_vs_nonexistent` now also
  asserts `body["error"]["details"] == {"reason": "element_not_found"}`.
  `no_tenant_context`'s wiring is added for the same reason but has no new
  test forcing that branch (`login_required` plus the
  `current_user.organization_id` fallback in `_current_organization_id`
  make it effectively unreachable through a real logged-in request too;
  adding a forced test would mean monkeypatching the same seam the B2
  correction explicitly moved away from). `reason_codes.py`'s stale
  "the sixteen members" comment is corrected to describe the current
  eighteen.
- **NEW-5 (rows carried no element identity) — fixed.** `query_service.py`
  no longer does `row.pop("element_id", None)`; only the internal
  `_endpoints` join key is stripped. Every row in the API-1 payload now
  names the element it is about. Tests: `test_route_returns_full_api1_payload`
  (tightened to assert `element_id` is present and non-null) and
  `test_row_shape` assertions elsewhere are unaffected since none asserted
  an exact (non-subset) key set that excluded it.
- **MINOR-1 — comment fixed, behaviour kept as-is (judgment call, stated
  here).** The claim that an unchanged request produces byte-identical
  output was inaccurate and is corrected in the comment. The behaviour
  itself (adding `derived_elements`/`derivation_state` unconditionally on
  the `element_id` branch, regardless of `include_derived`) is intentional,
  not a defect: `derivation_state` is a real, always-computed measurement
  (B1/M9), and gating it behind `include_derived` would mean either
  fabricating it or reporting a stale value on every `include_derived=False`
  request — reintroducing exactly the defect class B1 exists to prevent.
  No behaviour change made.

## Refuter findings fixed in this revision

- **B1 (fabricated `not_computed` on lookup failure).** `app/api/v1/impact.py`'s
  `_derived_elements_for_element` no longer catches exceptions and converts
  them into `derivation_state: "not_computed"` (a real, meaningful state per
  acceptance item 7). A crashed lookup now propagates to the route's own
  `except Exception` handler, which returns a proper 500. Test:
  `test_derived_elements_lookup_failure_does_not_fabricate_not_computed`
  (`app/modules/intelligence/tests/test_impact_route.py`), which monkeypatches
  `IntelligenceQueryService.cross_layer_impact` to raise and asserts the
  response is a 500, never a 200 carrying `"not_computed"`.
- **B2 (false SEC-09 traceability claim).** See the dedicated section below.
- **B3 (`MultipleResultsFound` 500 on duplicate component pointer).**
  `_find_component_for_element` (`query_service.py`) now uses
  `.scalars().first()` ordered by `id`, matching the pattern already used
  correctly for the ownership lookup ten lines below, instead of
  `scalar_one_or_none()`. Test:
  `test_duplicate_component_pointer_resolves_deterministically_not_500`
  (two `ApplicationComponent` rows sharing one `archimate_element_id`,
  confirming the route returns rows instead of raising).
- **M4 (latency histogram cannot isolate NFR-5's measurement point).**
  `INTELLIGENCE_QUERY_DURATION` (`app/services/prometheus_metrics.py`) and
  `record_query_latency` (`latency_probe.py`) now carry an `include_derived`
  label alongside `query`/`depth`, so
  `{query="cross_layer_impact", depth="4", include_derived="true"}` — the
  literal NFR-5 measurement point — is queryable in isolation from cheap
  explicit-only samples recorded under the same query/depth. Tests:
  `test_latency_record_and_histogram_populated` (updated for the new label)
  and the new `test_latency_histogram_labels_include_derived_true_separately`.
- **M5 (`include_derived`/`max_depth` silently dropped on the `app_id`
  branch).** `app/api/v1/impact.py` now returns 400 when either parameter is
  supplied alongside `app_id` (matching this task's additive-only scope for
  the `element_id` branch), instead of validating them and then silently
  ignoring them. Test: `test_app_id_branch_rejects_include_derived_and_max_depth`.
- **M6 (invented absence strings bypassing the closed vocabulary; dropped
  `reasons` list).** `no_tenant_context` and `element_not_found` are now real
  members of `reason_codes.py`'s `REASON_CODES` (18 total, up from 16),
  routed through `validate_reason_code` in `query_service.py` exactly like
  the pre-existing codes. `test_reason_codes.py` is updated in lockstep
  (`test_reason_codes_has_exactly_eighteen_members`). Separately, the
  `reasons` list the service returns was being discarded by the route
  (`app/modules/intelligence/routes/api.py::cross_layer_impact`) — it is now
  included in the response body.
- **M7 (N+1 owner resolution on the NFR-5 measurement path).** A new
  `_resolve_owners_batch` (`query_service.py`) collects every distinct
  element id needing an owner lookup across the WHOLE result set, then issues
  one `IN`-query per table (component, ownership, unit) instead of 3 queries
  per row. `cross_layer_impact`'s per-row loop now looks up results from this
  batch instead of calling `_resolve_owner` once per row. `_resolve_owner`
  itself is left in place (still directly exercised by the SEC-09 tests
  below) but is no longer on the hot path.
- **Minor: `test_impact_route.py`'s subset assertion tightened to `==`**
  (exact key set) per acceptance item 16's "byte-identical" language.
- **Minor: `tests/smoke/test_authorisation_matrix.py`'s anonymous-session
  assertion tightened.** Corrected against a LIVE run (see "Live Playwright
  run" below): this route answers 401 directly (it is a JSON API route, not
  an HTML page), not a redirect to `/account/login` as the original loose
  assertion implied. The test now asserts `response.status == 401`, matching
  the precise-status pattern already used at `:647-657`.

Not fixed in this revision, carried forward explicitly:

- **M8 (reason-code precedence drops a simultaneous absence).** A stale row
  with no resolvable owner reports `derivation_stale` and silently drops
  `no_ownership_recorded`, because `row["reason"]` is a single scalar field.
  Acceptance item 5 expects both facts to be visible. Widening `reason` to a
  list is a response-shape change beyond this fix pass's scope (it would
  touch the API contract's `reason` field type, tested at multiple call
  sites) — recorded here as a known limitation rather than silently left
  undisclosed, per the refuter's instruction. `test_stale_rows_only_appear_with_include_stale_true`
  (`query_service.py`) still pins the current, single-reason behaviour.
- **M9 (BFS always runs regardless of `include_derived`) — deliberately not
  applied.** `query_service.py`'s own comment documents that the underlying
  fetch (`list_derived_facts(..., include_stale=True, ...)`) runs
  unconditionally so `derivation_state` is always a REAL measurement, never
  fabricated when `include_derived=False` — this is precisely the
  "never invent data" behaviour B1 exists to protect. Skipping the call when
  `include_derived=False`, as M9 suggests, would make `derivation_state`
  either stale or fabricated on every `include_derived=False` request,
  contradicting FR-15/acceptance item 7. Not applied; flagged here rather
  than silently dropped.

## SEC-09 traceability correction (B2)

**Revision 1's claim was false.** It named
`test_mutation_proof_sec09_and_include_derived_filter` as proof that SEC-09
(`_sec09_tenant_check`, `query_service.py`) is load-bearing. That test
monkeypatches `_find_component_for_element` to force a same-tenant-looking
pass-through — a scenario the real code path never produces, because
`ApplicationComponent` carries `TenantMixin`, and `cross_layer_impact`'s
`org_id` (from `current_org_id()`, which reads `g.current_org_id`) is the
SAME source the ORM tenant filter reads. Under any single request they
always agree, so a foreign-tenant component is filtered out by the ORM
BEFORE `_sec09_tenant_check` is ever reached — the monkeypatched seam
manufactures a scenario that cannot occur through unmodified code, making the
"proof" circular. (It also broke outright once M7's batching landed, because
`_resolve_owners_batch` does its own component query rather than calling
`_find_component_for_element` — direct evidence the old test was pinned to
an implementation detail, not a real behaviour.)

**The real gap SEC-09 exists for**, per the tech-lead's verification notes
and this repo's own CLAUDE.md tenant-isolation section ("the exposure is
anything that loops over tenants inside a single session: CLI commands, the
scheduler, importers, and tests"): a caller holding an explicit target
`org_id` while `g.current_org_id` has drifted to a different tenant within
the same session. `OrganizationUnit`/`ApplicationOwnership` carry no
`organization_id` column at all, so once that drift happens, SEC-09 is the
ONLY thing standing between the join and another tenant's unit name.

**Corrected AGAIN in revision 3.** Revision 2's own fix named
`_resolve_owner` as "the real, unmodified function" reached by the two tests
below — but revision 2 had ALSO (separately, for the M7 N+1 fix) already
moved `cross_layer_impact` onto a new `_resolve_owners_batch` function,
leaving `_resolve_owner`/`_find_component_for_element` with zero production
callers. The refuter's grep confirmed this. Revision 3 deletes both dead
functions and repoints the same two tests at `_resolve_owners_batch`
directly — same scenario construction, now against the actual production
function:

- `test_sec09_tenant_check_blocks_real_cross_tenant_resolution` — sets
  `g.current_org_id` to org B (so org B's real, unmodified component and
  ownership chain are genuinely, ORM-returnably visible — nothing mocked)
  and calls the real, unmodified `_resolve_owners_batch([target.id],
  org_a.id)`, reproducing the session-drift scenario. Asserts the owner is
  `None` and the foreign unit's name never appears.
- `test_mutation_proof_sec09_real_path` — the companion mutation proof: with
  the same real, reachable scenario, monkeypatching ONLY
  `_sec09_tenant_check` (the real function itself, not an upstream seam) to
  always return `True` makes org B's unit name leak through
  `_resolve_owners_batch`. This is the correct SEC-09 traceability evidence.

**What this does and does not prove, stated plainly:** `_resolve_owners_batch`
is genuinely `cross_layer_impact`'s only production caller for owner
resolution, and `cross_layer_impact` is called by exactly two real HTTP
routes, both of which read `org_id` from the same `g.current_org_id` the
ORM's tenant filter also reads — so neither can hand `_resolve_owners_batch`
a diverging `org_id` today. Deleting `_sec09_tenant_check`'s guard would
therefore NOT be caught by a test that only drives those two HTTP routes,
because the ORM's automatic filtering already removes the foreign
component first. The two tests above instead call `_resolve_owners_batch`
directly with a deliberately diverging `org_id`, proving the guard is
correct for the call shape it exists to protect against (an explicit,
caller-supplied `org_id` diverging from `g.current_org_id` in one session —
this repo's own CLAUDE.md names this as the real exposure class for
CLI/scheduler/importer code that loops tenants). It does not claim, and
should not be read as claiming, that today's two HTTP callers can currently
produce that divergence — they cannot. This is defense-in-depth with a real,
direct-call proof, not a guarantee currently exercised by a live request.

`test_mutation_proof_sec09_and_include_derived_filter` is retained for its
`_include_derived_gate` mutation proof only (still valid and unaffected by
either fix); its docstring is updated to point at the two tests above for
SEC-09 and to disclose why its own SEC-09 portion was removed.

**No user-facing UI surface exists for US-1 yet.** This build ships the
backend contract, the latency probe, and the reason-code honesty rules —
demonstrable by direct API calls and by the tests below. It does not mean a
person can complete the "if this fails, what stops and who owns it" journey
in the rendered application; there is no Ask/Twin-map/Provenance-drawer
screen calling this endpoint. That UI is T-004b, scoped separately per
`docs/buckets/t004-us1-impact-endpoint/tasks/03-ui-surfaces-descope-record.md`.
A green result here is evidence the backend contract is correct, not
evidence of a shippable end-user feature.

## Traceability: FR -> DE -> acceptance item -> test

| Requirement | Design element | Acceptance item(s) | Test id(s) |
|---|---|---|---|
| FR-6 (combined payload) | DE-9 `cross_layer_impact` | Task01 #1 | `test_include_derived_true_returns_explicit_and_derived_in_one_payload` |
| FR-6 (explicit-only) | DE-9 | Task01 #2, Task02 #2 | `test_include_derived_false_returns_only_explicit_rows`, `test_route_include_derived_true_and_false_at_http_layer` |
| FR-5 (provenance) | DE-9 | Task01 #3 | `test_derived_row_carries_chain_and_rule_id` |
| FR-15/AA-5 (owner attach) | DE-9 owner join | Task01 #4 | `test_owner_attaches_when_chain_resolves_and_tenant_matches` |
| FR-15 (owner honesty / SEC-09) | DE-9 owner join | Task01 #5, #9 | `test_owner_absent_is_indistinguishable_and_cross_tenant_does_not_leak`, `test_cross_tenant_component_pointer_does_not_leak_unit_name` |
| FR-15 (derivation_state honesty) | DE-9 summary | Task01 #7 | `test_derivation_state_not_computed_when_tenant_has_no_derived_rows`, `test_derivation_state_current_when_fresh_derived_rows_exist` |
| FR-4 (stale honesty) | DE-9 + DE-3 `list_derived_facts` | Task01 #8 | `test_stale_rows_only_appear_with_include_stale_true` |
| DA-4 (tenancy) | DE-9 owner join, `_resolve_owners_batch` | Task01 #9 | `test_no_write_to_ownership_or_unit_tables`, `test_cross_tenant_component_pointer_does_not_leak_unit_name` |
| DE-18/OA-2 (latency probe) | `latency_probe.py`, `INTELLIGENCE_QUERY_DURATION` | Task01 #10 | `test_latency_record_and_histogram_populated` |
| Task01 mutation proof (`_include_derived_gate`) | `_include_derived_gate` seam | Task01 #12 | `test_mutation_proof_sec09_and_include_derived_filter` |
| Task01 mutation proof (SEC-09, corrected) | `_sec09_tenant_check` | Task01 #12 | `test_sec09_tenant_check_blocks_real_cross_tenant_resolution`, `test_mutation_proof_sec09_real_path` |
| API-1 (full payload at HTTP layer) | `GET /api/v1/intelligence/impact/<id>` | Task02 #1 | `test_route_returns_full_api1_payload` |
| API-1 (parameter validation) | route param parsing | Task02 #3 | `test_route_parameter_validation_returns_400` |
| API-1 (404 indistinguishability, D3) | `not_found_response` single call site | Task02 #4 | `test_404_indistinguishability_cross_tenant_vs_nonexistent` |
| API-1 (derivation_state at HTTP layer) | route | Task02 #5 | `test_derivation_state_values_and_stale_gating` |
| API-3/DE-10 (additive extension, D2) | `app/api/v1/impact.py::analyze_impact` | Task02 #6 | `test_canonical_endpoint_additive_extension_unchanged_request` |
| SEC-02 (projection integrity) | `_normalise_element_result`/`_derived_elements_for_element` | Task02 #7 | `test_projection_integrity_no_commercially_sensitive_fields` |
| D2 (app_id branch untouched) | `_to_contract_shape` (unchanged) | Task02 #8 | `test_app_id_branch_characterisation_untouched` |
| D1 (one blueprint) | `app/modules/intelligence/routes/api.py` | Task02 #9 | `test_single_blueprint_bound_to_intelligence_prefix`, `test_module_registers_exactly_three_routes`, `test_register_mounts_exactly_the_intelligence_api_blueprint` |
| Persona authorisation | `tests/smoke/test_authorisation_matrix.py` | Task02 #10 | `test_intelligence_impact_route_authorisation`, `test_intelligence_impact_route_rejects_anonymous_browser_session` |

## Design decisions carried from `00-verification-notes.md` (not re-litigated)

- D1: the US-1 route is added to the existing `intelligence_api` blueprint in
  `app/modules/intelligence/routes/api.py` — no new blueprint/module.
- D2: `app/api/v1/impact.py`'s additive `derived_elements`/`derivation_state`
  keys are added **only** on the `element_id` branch. The `app_id` branch is
  untouched; `test_app_id_branch_characterisation_untouched` pins its current
  keys as a characterisation test, not a fix.
- D3: 404 identity is tested as indistinguishability (status, `error.code`,
  `error.message`, key set) with `meta` removed before comparison, not literal
  byte-identity.
- D4: `list_derived_facts` (`app/modules/intelligence/services/derived_facts.py`)
  is extended additively with `max_depth`, `direction`, `layer` — no second
  read path over `archimate_derived_relationships` was written; the query
  service (`query_service.py`) calls this one accessor only.

## Mutation-proof test ids (task 01 acceptance item 12, task 02 item 11) — CORRECTED

See "SEC-09 traceability correction (B2)" above for the full explanation.
Summary of what proves what now:

1. **`_include_derived_gate`** (`test_mutation_proof_sec09_and_include_derived_filter`):
   monkeypatched to always return `True`. With a real derived row present,
   criterion 2's assertion (`all(r["relation"]["kind"] == "explicit" ...)`)
   is confirmed to go red.
2. **`_sec09_tenant_check`** (`test_sec09_tenant_check_blocks_real_cross_tenant_resolution`
   + `test_mutation_proof_sec09_real_path`): a REAL session-drift scenario
   (`g.current_org_id` set to org B, `_resolve_owners_batch` called with an
   explicit `org_id=org_a.id`) reaches the real, unmodified
   `_sec09_tenant_check` through production control flow. With the check
   intact, no owner resolves; with it monkeypatched to always return `True`,
   org B's real unit name leaks. This replaces the revision-1 claim, which
   monkeypatched `_find_component_for_element` instead (a seam the real code
   path never exercised this way), and the revision-2 claim, which called
   `_resolve_owner` — a function that, by revision 2's own separate M7
   change, already had zero production callers by the time revision 2
   shipped (see the B2 correction above; both dead functions are now
   deleted).

The 404-branch mutation named in task 02 item 11 ("collapse the 404 branches
to distinct messages") is not separately exercised as a live mutation: both
the cross-tenant and non-existent-element paths in the route
(`app/modules/intelligence/routes/api.py::cross_layer_impact`) already call
the **same** `not_found_response("Element")` call site — there are not two
branches to collapse, by construction (D3's resolution: one code path, not
two that happen to agree). `test_404_indistinguishability_cross_tenant_vs_nonexistent`
is the test that would fail if a second, differently-worded 404 were
introduced on either path.

## Known gaps / follow-ups (not fixed here, recorded rather than silently dropped)

- **`no_maturity_recorded` / maturity data.** Task 01's acceptance item 6
  (carried over from the original brief) names a fixture with "missing
  maturity" alongside missing ownership and no derivation. No maturity
  read path, table, or accessor is named anywhere in task 01's context or
  deliverable — `cross_layer_impact` implements owner attach and derivation
  provenance only, per its Objective ("DE-9 method only impact... other
  methods are Release 2"). Emitting `no_maturity_recorded` here would mean
  inventing a maturity data source with no design basis, which is exactly
  what CLAUDE.md's "never invent data" rule forbids. This task implements
  and tests the two reason codes that ARE in scope
  (`no_ownership_recorded`, `derivation_stale`); `no_maturity_recorded` is
  left as an open scope question for whichever future task defines the
  maturity data model.
- The `app_id` branch's own SEC-02 gap (no `{id,name,type,level}` projection
  at all) is pre-existing and explicitly out of scope per D2 — recorded, not
  fixed, matching the tech-lead's decision.
- `derivation_not_computed` as a per-row reason code (as opposed to the
  `derivation_state: "not_computed"` summary value, which IS implemented and
  tested) is not emitted by any row in this task's payload shape; nothing in
  task 01/02's row contract calls for it.

## Verification run (revision 3 — this fix pass, real pasted output)

All commands below were actually executed in this session against a live
PostgreSQL instance (`TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/flask_test`).
No number in this section is asserted without having been run in this
session.

```
$ python -m pytest app/modules/intelligence/tests/ -q
================ 146 passed, 458 warnings in 79.24s (0:01:19) =================

$ python scripts/verify.py --tag static
...
48 passed, 0 failed, 1 skipped
1 gate(s) skipped and therefore NOT verified:
    css-build: no vendored Tailwind CLI at scripts/bin/tailwindcss[.exe] --
    an npm-resolved Tailwind is not byte-reproducible against the committed
    build (caniuse-lite floats), so this cannot be verified here. CI runs
    with --require-db so this is not silently skipped there.
```

(Revision 2's prior run — 144 passed — is superseded by the above; the
count grew to 146 with revision 3's two new NEW-1 tests offsetting the two
dead-function tests removed with `_resolve_owner`/`_find_component_for_element`.)

Note: `--tag static` is a partial run (CLAUDE.md: only the bare
`python scripts/verify.py` is "clean"). The full run needs
`--require-db`-class gates (`schema-drift`, `tests`, `nav-verified`), which
were not run as a single combined invocation in this session; the `tests`
gate's equivalent coverage was run directly via the pytest command above.

## Live Playwright run (this fix pass)

`tests/smoke/test_authorisation_matrix.py`'s Playwright rows for the
intelligence impact route WERE executed live in this session, against a real
running Flask server plus PostgreSQL (this repo's smoke-test harness, not a
syntax check):

```
$ python -m pytest tests/smoke/test_authorisation_matrix.py -k "intelligence_impact" -v
...
========= 12 passed, 71 deselected, 118 warnings in 121.96s (0:02:01) =========
```

This run is what surfaced the minor-item fix above: the original
`test_intelligence_impact_route_rejects_anonymous_browser_session` assertion
(`response.status >= 400 or "/account/login" in page.url`) was loose enough
to pass either way, and the live run showed the actual behaviour is a direct
401 JSON response (this is an API route, not an HTML page, so
`login_required` does not redirect it) — not a redirect to the login page as
the looser assertion implied. The test now asserts the precise status.

## Handoff

Per both task briefs: `builder` (this report) -> `refuter`, then task 02 also
requires `qa-lead`. Not merged, not deployed — a refuter pass on this diff is
still outstanding, matching every other bucket tonight.
