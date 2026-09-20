# Task Brief: T-004 — US-1 Cross-Layer Impact Endpoint, Owner Attach, Latency Probe

## Objective
Ship the US-1 answer — "if this fails, what stops and who owns it" — as
`GET /api/v1/intelligence/impact/{element_id}` returning explicit and derived
edges with their provenance chain and a tenant-verified owner or an honest
reason, extend the canonical impact endpoint additively with
`include_derived`, and measure query latency at the single NFR-5 point, with
no fabricated value anywhere on the path.

## Context
Source: `docs/buckets/archie-ea-four-intelligences-extension/tasks/T-004-us1-impact-endpoint.md`
in `Anioko/sdlc-orchestrator` (fetched verbatim tonight, reproduced in full
below since that repo isn't checked out here). Depends on T-003 (derived-fact
store), which shipped tonight — PR #34, deployed as `bddfb5cc`.

- Design source: SDD v2 §AA-5 (Intelligence Query Service `cross_layer_impact`,
  owner attachment), §API-1 (the US-1 endpoint), §API-3 (additive extension of
  the canonical impact endpoint), §OA-2 (latency probe / structured record and
  the NFR-5 measurement point), §OA-4 (failure modes), §API-8 (reason-code
  vocabulary), Screens & Surfaces (Ask, Twin map, Provenance drawer).
- The query service (DE-9) is one class, one method per question, each
  returning rows plus a `reasons` list, serialised through `success_response()`
  (`app/utils/api_response.py:14-36`) and wrapped by `record_query_latency`
  (DE-18). This task builds `cross_layer_impact` only; other methods
  (value-streams-at-risk, risk, coverage) are Release 2, out of scope.
- Owner attachment (AA-5): `ApplicationOwnership` is keyed to
  `application_components.id` and `organization_units.id`
  (`app/models/enterprise_intelligence.py:186-199`), not to elements. Join:
  derived/target element → `ApplicationComponent.archimate_element_id`
  (`app/models/application_portfolio.py:309-317`, auto-populated by the
  `before_insert` listener at `:951-983`) → `ApplicationOwnership` →
  `OrganizationUnit`. Per SEC-09 the join additionally asserts the resolved
  component is in the caller's tenant before any unit name renders, because
  `organization_units` and `application_ownership` have no tenant column. If
  any link is absent, or the tenant assertion fails, the row carries
  `"owner": null, "reason": "no_ownership_recorded"` — deliberately
  indistinguishable.
- Canonical impact endpoint (API-3 / DE-10): `app/api/v1/impact.py:24-96` is
  the one impact endpoint; `DESIGN.md` forbids parallel scoring logic.
  Extended, not replaced: request gains optional `include_derived` (default
  false) and `max_depth` (1-5); response gains `derived_elements: []` and
  `derivation_state`. Existing keys keep their meaning/values for an
  unchanged request. `scenario` remains required and validated against
  `VALID_SCENARIOS` (`:21`, `:53-57`); a non-boolean `include_derived` is a
  400. The route's existing `{id,name,type,level}` projection (`:112-134`) is
  unchanged.
- Latency (DE-18 / OA-2 / NFR-5): `record_query_latency` wraps every query-
  service method and emits one structured record per call (`query`,
  `organization_id`, `depth`, `include_derived`, `latency_ms`,
  `explicit_rows`, `derived_rows`, `stale_rows`, `invalidated_rows`,
  `engine_version`) and increments the Prometheus histogram
  `archie_intelligence_query_seconds` labelled by query name and hop depth,
  exported through the existing scrape endpoint. p95 is read from the
  histogram, never computed or averaged in application code. NFR-5
  measurement point: `cross_layer_impact` with `include_derived=true`,
  `max_depth=4`, on the largest tenant by `archimate_relationships` row
  count (re-evaluated at measurement time), p95 over a rolling seven-day
  window, minimum 100 samples (below which report "insufficient samples",
  never a number), threshold 2.0s measured after DA-1 indexes are in place. A
  breach is a logged Shape-B trigger event; it opens the decision, it does
  not start work.
- API-1 shape: path `element_id`; query params `include_derived` (default
  false), `include_stale` (default false), `max_depth` (1-5, default 3),
  `direction` (downstream|upstream|both, default downstream), `layer`,
  `with_owner` (default true). `rows[]` carry `relation {kind:
  explicit|derived, type, depth, rule_id, chain, chain_elements, confidence,
  provenance, computed_at, stale}`, nullable `owner {organization_unit_id,
  name, ownership_type}`, and nullable `reason` from the API-8 enum.
  `summary {explicit_count, derived_count, stale_count, derivation_state:
  current|stale|not_computed, latency_ms}`. A 404 for another tenant's
  element is byte-identical to a 404 for a non-existent element.
- **Prometheus wiring, verified in the source session.** Metrics are
  registered on the module-level `REGISTRY = CollectorRegistry()` in
  `app/services/prometheus_metrics.py:26`, with `Histogram(...)` instances
  declared beside it (e.g. `HTTP_REQUEST_DURATION` at `:39`,
  `AI_REQUEST_DURATION` at `:109`), exported by `get_metrics_response()`
  through the scrape route `@metrics_bp_v2.route("/metrics")` at
  `app/modules/monitoring/v2/routes/metrics_routes.py:27-31`, blueprint
  declared at `:23`. Declare `archie_intelligence_query_seconds` on that same
  `REGISTRY` so it's exported by the existing scrape endpoint without a
  second registry or scrape path.
- **Identity-map trap on this path.** `ArchiMateImpactService`
  (`app/services/archimate_impact_service.py:18`) uses
  `ArchiMateElement.query.get(...)` in its propagation loop at `:36` and
  `:82`. Inside one request that is one tenant and is safe; this task does
  not need to change it. The trap matters only for code that loops tenants —
  do not copy that call shape into anything the recompute job reaches.
- **The `# tenancy-ok:` raw-SQL marker pattern** to follow for any recursive
  walk is at `app/modules/solutions_strategic/v2/services/impact_analysis_service.py:114-116`
  and `:156`.
- **SEC-02.** Field suppression lives in the route, not the service: the
  canonical route projects each affected element to `{id,name,type,level}`
  (`app/api/v1/impact.py:112-134`) while the service returns `app_name`,
  `criticality`, `tco` (`impact_analysis_service.py:160-172`) and
  `estimated_financial_risk` (`:60-65`). TCO per application is commercially
  sensitive and this route does not return it. Keep the projection exactly
  as it is; a widened projection here becomes a leak in the Release 4 twin.

**Verify this context against current code before building** — this brief
was written from the plan doc, not re-derived against the live repo tonight;
that verification is tech-lead's first job.

## Constraints
- **DA-4** (build-time constraint, this task touches the initiative/maturity
  and ownership read path). The owner join and any read of non-`TenantMixin`
  tables (`organization_units`, `application_ownership`) obey DA-4: start
  from the tenant-fenced element and join outward with inner joins only —
  never a left join that re-admits unfenced rows, never a query that starts
  from the unfenced table. Any raw SQL carries an explicit `organization_id`
  predicate on every arm, returns empty when `current_org_id()` is None, and
  carries the `# tenancy-ok:` marker. The intelligence module performs no
  writes to `organization_units`, `application_ownership`,
  `portfolio_initiatives` or `initiative_success_metrics` — a write to any of
  them from this module is a review-blocking defect (DA-4 rule 5).
- `include_derived=false` returns only `relation.kind = "explicit"` rows —
  US-1's second acceptance criterion, tested, not conventional.
- No fabrication (FR-15, NFR-2): a missing owner, missing maturity or absent
  derivation renders the reason code and an em dash, never a `0`, a blank or
  a guess. `derivation_state = "not_computed"` renders "derivation not yet
  computed" with a one-click run action, never a zero.
- The canonical endpoint extension is additive only: unchanged request →
  unchanged response keys, meanings and values. Do not add a parallel
  scoring path.
- Every new REST route carries `@login_required`; persona-gated UI routes
  extend `tests/smoke/test_authorisation_matrix.py` against the eleven
  canonical personas rather than adding a bespoke smoke test.
- p95 is read from the Prometheus histogram, never computed in application
  code and never averaged.
- Register the blueprint non-fatally; guard template links per DESIGN.md
  "Guarded nav links".
- Live defects SR-11, SR-12, SR-13 are out of scope here.
- Full MCP read/write parity is Release 4, NOT in scope. This task owns only
  the tenant-correctness of the US-1 REST route itself and its 404-shape
  identity.

## Deliverable
- `app/modules/intelligence/services/query_service.py` —
  `IntelligenceQueryService.cross_layer_impact` (DE-9), reading the derived
  store + `archimate_relationships` + the ownership chain, returning rows
  plus a `reasons` list, wrapped by `record_query_latency`.
- `app/modules/intelligence/services/latency_probe.py` (DE-18) —
  `record_query_latency` emitting the OA-2 structured record and
  incrementing `archie_intelligence_query_seconds`.
- `app/modules/intelligence/routes/intelligence_api.py` —
  `GET /api/v1/intelligence/impact/{element_id}` (API-1) with the full
  parameter/payload contract above, `@login_required`.
- Additive extension of `app/api/v1/impact.py:24-96` (API-3 / DE-10):
  optional `include_derived` and `max_depth`, `derived_elements` and
  `derivation_state` in the response, unchanged projection and existing
  keys.
- UI surfaces for US-1 (Ask, Twin map, Provenance drawer) calling API-1/API-2
  per Screens & Surfaces, with derived edges distinct on a non-colour
  channel and the hop-depth slider bound to `max_depth`. **Tech-lead: if
  these screens don't exist yet in this codebase, flag that as a scope
  question rather than inventing the UI shape — this may need to be split
  into a backend-only task plus a follow-up UI task.**
- Tests under `app/modules/intelligence/tests/`, an extension of
  `tests/smoke/test_authorisation_matrix.py`, and a build report linking
  FR-6/FR-14/FR-15 → DE-9/DE-10/DE-18 → acceptance items with mutation-proof
  records.

## Acceptance Criteria
The refuter checks each individually:
1. Combined payload (FR-6): `include_derived=true` returns derived edges
   (`depth`, `chain`, `rule_id`) alongside explicit edges in one payload.
2. Explicit-only branch: `include_derived=false` returns only
   `relation.kind = "explicit"` rows, asserted by test.
3. Provenance in the payload (FR-5 via US-1): each derived row carries
   `chain` + `rule_id`.
4. Owner attach (AA-5): where the chain resolves and SEC-09 passes, row
   carries `owner {organization_unit_id, name, ownership_type}`.
5. Owner honesty (FR-15): where any link is absent or SEC-09 fails, row
   carries `"owner": null, "reason": "no_ownership_recorded"` —
   indistinguishable; a test asserts a cross-tenant component pointer does
   not leak a unit name.
6. FR-15 absent-data branch: one fixture with a missing owner, missing
   maturity and no derivation returns three distinct reason codes
   (`no_ownership_recorded`, `no_maturity_recorded`,
   `derivation_not_computed`) and no zeros; rendered screen shows the
   reason text (Playwright/screen assertion).
7. `derivation_state`: `not_computed` renders "derivation not yet computed"
   with a one-click run action, never a zero; `stale`/`current` render
   correctly.
8. Stale honesty on the read path (FR-4 via US-1): stale rows appear only
   with `include_stale=true`, flagged; default read never returns a stale
   row as current.
9. 404-shape identity: a 404 for another tenant's element is byte-identical
   in body and status to a 404 for a non-existent element.
10. Additive extension (API-3, DE-10): unchanged request → unchanged
    `risk_level`, `total_score`, `breakdown`, `affected_elements`,
    `summary`, `analysis_id`; `scenario` still required/validated;
    non-boolean `include_derived` is 400; `{id,name,type,level}` projection
    unchanged; `derived_elements`/`derivation_state` added.
11. DA-4 tenancy: owner join starts from fenced element, inner joins only; a
    test per non-`TenantMixin` table on this path (ownership row, org unit)
    asserts no cross-tenant leak; raw SQL returns empty when
    `current_org_id()` is None and carries `# tenancy-ok:`; no write to
    `organization_units`/`application_ownership` from this module.
12. Latency (NFR-5): `record_query_latency` emits the OA-2 record per call;
    Prometheus histogram incremented/labelled; p95 read from histogram;
    below 100 samples reports "insufficient samples", never a number.
13. Authorisation: new persona-visible routes extend
    `tests/smoke/test_authorisation_matrix.py` across all eleven personas.
14. Mutation proof: disable SEC-09 tenant assertion, confirm the
    cross-tenant owner-leak test goes red; disable the
    `include_derived=false` filter, confirm item 2 goes red; re-enable both;
    record test ids.
15. Metrics plumbing: `archie_intelligence_query_seconds` declared on the
    existing `REGISTRY`, appears in the existing scrape route response, no
    second registry/scrape path/dependency; test asserts metric name+labels
    present after one query.
16. Projection integrity: canonical endpoint's `{id,name,type,level}`
    projection byte-identical before/after, asserted by test.

## Handoff Target
`tech-lead` — verify this brief's file:line citations against current code
(it was transcribed from the plan doc, not re-derived live), flag anything
stale or missing (especially the UI-surfaces deliverable — confirm whether
Ask/Twin map/Provenance drawer screens exist yet), and decompose into
buildable task files. Given the scope (backend service + API extension +
UI + metrics + 16 acceptance criteria), strongly consider splitting into
2-3 task files (e.g. 01-query-service-and-api, 02-canonical-endpoint-
extension-and-metrics, 03-ui-surfaces) the way T-003 was split. Route to
`builder` after task files are written.
