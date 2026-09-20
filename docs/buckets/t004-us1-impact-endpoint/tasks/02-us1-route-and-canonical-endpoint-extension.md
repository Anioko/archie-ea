# T-004 / Task 02 — US-1 REST route and additive canonical-endpoint extension

## Objective
Expose task 01's query service as `GET /api/v1/intelligence/impact/<element_id>`
(API-1) on the **existing** intelligence blueprint, and extend the canonical
impact endpoint (API-3 / DE-10) additively with `include_derived` and
`max_depth` — without changing a single existing response key, meaning or
value for an unchanged request.

## Context
Two existing components are extended. Neither is replaced, and **no new
blueprint or routes module is created**:

- **`app/modules/intelligence/routes/api.py`** already declares
  `intelligence_api = Blueprint("intelligence_api", __name__,
  url_prefix="/api/v1/intelligence")` (`:22-24`), already registered
  non-fatally by `app/modules/intelligence/__init__.py::register`, and its own
  docstring reserves the US-1 route for T-004. The parent brief asks for a new
  file `routes/intelligence_api.py`; that would put a **second** blueprint on
  the same URL prefix, which is the ADR 0008 rule-3 defect this repo has
  already paid for three times at `/api/users`. Add the route to the existing
  file and the existing blueprint. Reuse `_current_organization_id()`
  (`:27-41`) rather than reading `current_user.organization`.
- **`app/api/v1/impact.py`** is the one canonical impact endpoint
  (`@impact_bp.route("/analyze")`, `:24-96`); `DESIGN.md` forbids a parallel
  scoring path. `scenario` stays required and validated against
  `VALID_SCENARIOS` (`:21`, `:53-57`). The `{id,name,type,level}` projection
  lives in `_normalise_element_result` (`:112-134`) and applies **only to the
  `element_id` branch**; the `app_id` branch returns
  `AIImpactAnalysisService`'s result through `_to_contract_shape`
  (`:137-147`), which does not project at all. That asymmetry is pre-existing
  and stays pre-existing — see acceptance criterion 8.
- **404 identity.** `error_response` (`app/utils/api_response.py:39-61`) stamps
  a fresh `uuid4` `request_id` and a `utcnow()` `timestamp` into `meta` on
  every response, so literal byte-identity is unattainable. The property that
  matters is indistinguishability of everything the caller can attribute to
  the resource: same status, same `error.code`, same `error.message`, same key
  set. Use a single `not_found_response("Element")` call site reached by both
  the cross-tenant and the non-existent case, so there is one code path rather
  than two that happen to agree today.
- Task 01's `IntelligenceQueryService.cross_layer_impact` supplies rows,
  summary and reasons; this task serialises them through `success_response`
  (`app/utils/api_response.py:14-36`) and validates/coerces parameters. No
  business logic in the route.

Read `00-verification-notes.md` first — defects D1, D2 and D3 are all resolved
in this task.

## Constraints
- **Additive only** on `app/api/v1/impact.py`: an unchanged request must
  produce unchanged `risk_level`, `total_score`, `breakdown`,
  `affected_elements`, `summary` and `analysis_id` — same keys, same meanings,
  same values. `derived_elements` and `derivation_state` are new keys only.
- No parallel scoring logic. The extension reads task 01's service for derived
  edges; it does not recompute impact.
- Every new route carries `@login_required`.
- **SEC-02.** Keep the `element_id` branch's `{id,name,type,level}` projection
  exactly as it is. The service layer returns `app_name`, `criticality`, `tco`
  (`impact_analysis_service.py:160-172`) and `estimated_financial_risk`
  (`:60-65`); TCO per application is commercially sensitive and this route
  does not return it. A widened projection here becomes a leak in the
  Release 4 twin.
- Parameter validation, all 400s with a clear message, never a silent default:
  `include_derived` non-boolean -> 400; `max_depth` outside 1-5 -> 400;
  `direction` outside `downstream|upstream|both` -> 400.
- Route-level absence rendering uses the DE-14 vocabulary via
  `validate_reason_code()`; no inline absence strings.
- No new blueprint, no change to `register(app)`'s API wiring.
- Register nothing fatally; guard any template link per DESIGN.md's guarded
  nav-link rule (not expected in this task — see task 03).

## Deliverable
- `GET /api/v1/intelligence/impact/<int:element_id>` added to
  `app/modules/intelligence/routes/api.py`, `@login_required`, accepting
  `include_derived` (default false), `include_stale` (default false),
  `max_depth` (1-5, default 3), `direction` (default `downstream`), `layer`,
  `with_owner` (default true); returning `rows[]` and `summary` per API-1
  through `success_response`.
- Additive extension of `app/api/v1/impact.py`'s `analyze_impact`: optional
  `include_derived` and `max_depth` in the request body;
  `derived_elements: []` and `derivation_state` in the response.
- Extension of `tests/smoke/test_authorisation_matrix.py` covering the new
  route against all eleven canonical `ARCHETYPES`, stating which reach it and
  which do not.
- Tests under `app/modules/intelligence/tests/`, including a characterisation
  test capturing the canonical endpoint's current response keys for both
  branches before the change.
- A build report linking FR-6/FR-14/FR-15 -> DE-9/DE-10/DE-18 -> acceptance
  items, with the mutation-proof test ids.

## Acceptance Criteria
1. `GET /api/v1/intelligence/impact/<id>` returns the full API-1 payload:
   `rows[]` with `relation`, `owner`, `reason`; `summary` with
   `explicit_count`, `derived_count`, `stale_count`, `derivation_state`,
   `latency_ms`.
2. `include_derived=true` returns derived edges alongside explicit in one
   payload; `include_derived=false` returns only `relation.kind ==
   "explicit"`, asserted by test at the HTTP layer as well as the service
   layer.
3. A non-boolean `include_derived`, a `max_depth` outside 1-5, and an invalid
   `direction` each return 400 with a specific message — never a silent
   default.
4. **404 indistinguishability:** requesting another tenant's element and
   requesting a non-existent element produce the same status (404), the same
   `error.code`, the same `error.message` and the same key set; the test
   compares the two response bodies with the `meta` envelope removed
   (`meta.timestamp`/`meta.request_id` are per-response by construction and
   are the only permitted difference).
5. `derivation_state` is `current`, `stale` or `not_computed` — never a zero
   or a blank standing in for any of them. `stale` rows are returned only when
   `include_stale=true` and carry their flag.
6. Additive extension (API-3/DE-10): a test issues the canonical endpoint's
   pre-change request and asserts `risk_level`, `total_score`, `breakdown`,
   `affected_elements`, `summary` and `analysis_id` are unchanged in key,
   meaning and value; `scenario` is still required and still validated against
   `VALID_SCENARIOS`; `derived_elements` and `derivation_state` are present as
   new keys.
7. Projection integrity: the `element_id` branch's `{id,name,type,level}`
   projection is unchanged, asserted by test; no `tco`, `app_name`,
   `criticality` or `estimated_financial_risk` per-element field appears in
   any response from either route.
8. `app_id` branch untouched: a characterisation test asserts the `app_id`
   path's response keys are identical before and after this change. (Its lack
   of projection is a pre-existing SEC-02 gap recorded as a follow-up in
   `00-verification-notes.md`; do **not** "fix" it here — doing so changes
   existing response values and breaks criterion 6.)
9. One blueprint: `grep` shows exactly one blueprint bound to
   `/api/v1/intelligence`, and `scripts/verify.py`'s `canonical-route` and
   `boot-health` gates stay green.
10. Authorisation: `tests/smoke/test_authorisation_matrix.py` covers the new
    route across all eleven archetypes, with explicit should-reach and
    should-not-reach rows — not a bespoke one-off smoke test.
11. Mutation proof: remove the SEC-09 assertion and confirm the cross-tenant
    owner test goes red; collapse the 404 branches to distinct messages and
    confirm criterion 4 goes red; re-enable both; record test ids.
12. `python scripts/verify.py` green (bare command). CI checked with
    `gh run list` before the work is reported done.

## Handoff Target
`builder`, then `refuter`, then `qa-lead`. Depends on task 01 being
`approved`. Task 03 is a decision record, not a build, and does not gate this.
