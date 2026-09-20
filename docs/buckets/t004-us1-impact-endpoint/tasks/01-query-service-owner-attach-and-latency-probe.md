# T-004 / Task 01 — Query service, owner attach, latency probe

## Objective
Build `IntelligenceQueryService.cross_layer_impact` (DE-9) — the US-1 answer
"if this fails, what stops and who owns it" — returning explicit and derived
edges with their provenance chain and a tenant-verified owner or an honest
reason code, wrapped by a new `record_query_latency` (DE-18) that emits the
OA-2 structured record and increments a Prometheus histogram. Service layer
only: no routes in this task.

## Context
Extends the existing `app/modules/intelligence/` module shipped by T-003 — do
not create a new module. Specifically:

- **Extends `app/modules/intelligence/services/derived_facts.py`**, which is
  the single declared accessor over `archimate_derived_relationships`
  (ADR 0008; its own docstring forbids a second read path at L1). It currently
  exposes `list_derived_facts(organization_id, *, include_stale=False,
  source_element_id=None, target_element_id=None)` and cannot express
  `max_depth`, `direction=both` (it ANDs the two element filters) or `layer`
  (no layer column on the model). Add those three as optional keyword
  parameters, additively, with existing defaults and existing callers
  unchanged. Keep the `stale = FALSE` default inside
  `_apply_default_staleness_filter` — that seam is monkeypatched by T-003's
  mutation-proof test and must stay monkeypatchable.
- **Reads `DerivedRelationship`** (`app/modules/intelligence/models/
  derived_relationship.py`): rows carry `depth`, `rule_id`, `chain`
  (`archimate_relationships.id` values), `chain_element_ids` (node path),
  `confidence`, `provenance`, `engine_version`, `computed_at`, `stale`.
  `max_depth` is a predicate on `depth`; the partial indexes `ix_dr_src` /
  `ix_dr_tgt` are what keep this within NFR-5, so filter in SQL, never in
  Python after an unfiltered fetch.
- **Explicit edges** come from `ArchiMateRelationship` /`ArchiMateElement`,
  both `TenantMixin` (`app/models/archimate_core.py:53`, `:110`), so the ORM
  tenant listener fences them with no hand-written predicate. Prefer reusing
  the existing recursive walk in
  `app/modules/solutions_strategic/v2/services/impact_analysis_service.py`
  (`_get_dependencies`, `:100-172`) over writing a new one. If a new raw
  recursive walk is genuinely required, follow its `current_org_id()`
  fail-closed guard (`:114-116`) and its `# tenancy-ok:` marker (`:156`)
  exactly.
- **Owner attach (AA-5, SEC-09).** `ApplicationOwnership`
  (`app/models/enterprise_intelligence.py:180-215`) keys
  `application_components.id` to `organization_units.id`. Join path: target
  element id -> `ApplicationComponent.archimate_element_id`
  (`app/models/application_portfolio.py:309-319`, populated by the
  `before_insert` listener at `:951-983`) -> `ApplicationOwnership` ->
  `OrganizationUnit`. `OrganizationUnit` (`:129`) and `ApplicationOwnership`
  (`:180`) have **no `organization_id` column and no `TenantMixin`** — they
  are entirely unfenced. `ApplicationComponent` **is** `TenantMixin`
  (`app/models/application_portfolio.py:80`), so resolve the component through
  the ORM (auto-fenced) and assert `component.organization_id ==
  current_org_id()` before reading any `OrganizationUnit.name`.
- **Reason codes** come from
  `app/modules/intelligence/services/reason_codes.py` via
  `validate_reason_code()`. Never write an absence string inline.
- **Prometheus.** Declare the histogram on the existing module-level
  `REGISTRY` in `app/services/prometheus_metrics.py:26`, following
  `HTTP_REQUEST_DURATION` (`:39`) and `AI_REQUEST_DURATION` (`:109`). It is
  then exported automatically by the existing scrape route
  `app/modules/monitoring/v2/routes/metrics_routes.py:27-31` (blueprint at
  `:23`). No second registry, no second scrape path, no new dependency.
- **Do not call or modify `ArchiMateImpactService`**
  (`app/services/archimate_impact_service.py:18`). Its
  `ArchiMateElement.query.get()` propagation (`:36`, `:82`) is safe inside a
  request but is an identity-map trap for anything that loops tenants; do not
  copy that call shape.

Read `00-verification-notes.md` in this directory first — it records four
defects in the parent brief, including the derived-store accessor gap (D4)
that this task resolves.

## Constraints
- **DA-4.** Start from the tenant-fenced element and join outward with inner
  joins only. Never a left join that re-admits unfenced rows; never a query
  that starts from `organization_units` or `application_ownership`. Any raw
  SQL carries an explicit `organization_id` predicate on every arm, returns
  empty when `current_org_id()` is None, and carries `# tenancy-ok: <reason>`.
- **No writes.** This module writes nothing to `organization_units`,
  `application_ownership`, `portfolio_initiatives` or
  `initiative_success_metrics`. A write to any of them is a review-blocking
  defect (DA-4 rule 5).
- `include_derived=False` returns only rows with `relation.kind ==
  "explicit"`. This is a tested branch, not a convention.
- **No fabrication (FR-15, NFR-2).** A missing owner, missing maturity or
  absent derivation yields the reason code and `None` — never `0`, never a
  blank, never a guess. `owner: null` + `reason: "no_ownership_recorded"` must
  be byte-identical whether the cause is a NULL `archimate_element_id`, a
  missing ownership row, a missing unit, or a failed SEC-09 assertion.
- p95 is **never** computed or averaged in application code. The histogram is
  the only source; below 100 samples the answer is the
  `insufficient_samples_for_p95` reason code, never a number.
- The `derived_facts.py` change is additive: no existing parameter, default or
  return shape changes.
- Add the depth/direction/layer filters to the **existing** accessor. A second
  query over `archimate_derived_relationships` anywhere is a defect.

## Deliverable
- `app/modules/intelligence/services/query_service.py` — `IntelligenceQueryService`
  with one public method, `cross_layer_impact(element_id, *, include_derived,
  include_stale, max_depth, direction, layer, with_owner)`, returning
  `{rows, summary, reasons}` where each row carries
  `relation {kind, type, depth, rule_id, chain, chain_elements, confidence,
  provenance, computed_at, stale}`, nullable `owner {organization_unit_id,
  name, ownership_type}` and nullable `reason`; and `summary
  {explicit_count, derived_count, stale_count, derivation_state, latency_ms}`
  where `derivation_state` is one of `current|stale|not_computed`. Other DE-9
  methods (value-streams-at-risk, risk, coverage) are Release 2 and are **not**
  added.
- `app/modules/intelligence/services/latency_probe.py` —
  `record_query_latency`, a decorator/context manager emitting the OA-2 record
  (`query`, `organization_id`, `depth`, `include_derived`, `latency_ms`,
  `explicit_rows`, `derived_rows`, `stale_rows`, `invalidated_rows`,
  `engine_version`) as a frozen dataclass with `as_dict()` logged at INFO,
  following the shape of `services/observability.py`'s `InvalidationRecord`,
  and incrementing `archie_intelligence_query_seconds` labelled by query name
  and hop depth.
- `archie_intelligence_query_seconds` declared in
  `app/services/prometheus_metrics.py` on the existing `REGISTRY`.
- Additive extension of `app/modules/intelligence/services/derived_facts.py`
  for `max_depth`, `direction`, `layer`.
- Tests under `app/modules/intelligence/tests/`.

## Acceptance Criteria
1. `include_derived=True` returns derived edges carrying `depth`, `chain` and
   `rule_id` alongside explicit edges in one result.
2. `include_derived=False` returns only `relation.kind == "explicit"` rows,
   asserted by test.
3. Every derived row carries both `chain` and `rule_id` (FR-5 via US-1).
4. Where the element -> component -> ownership -> unit chain resolves and the
   SEC-09 tenant assertion passes, the row carries `owner
   {organization_unit_id, name, ownership_type}`.
5. Where any link is absent **or** the SEC-09 assertion fails, the row carries
   `"owner": null, "reason": "no_ownership_recorded"`, and a test asserts the
   two payloads are indistinguishable. A dedicated test plants a component in
   another tenant, points a fenced element's chain at it, and asserts no unit
   name leaks.
6. A fixture with a missing owner, missing maturity and no derivation returns
   three distinct reason codes (`no_ownership_recorded`,
   `no_maturity_recorded`, `derivation_not_computed`) and no zeros anywhere in
   the payload. (Rendered-screen half is T-004b — see task 03.)
7. `derivation_state` returns `not_computed` when the tenant has no derived
   rows, `stale` when the newest matching rows are stale, `current` otherwise
   — never a zero standing in for any of the three.
8. Stale rows appear only with `include_stale=True` and carry `stale: true`
   plus `reason: "derivation_stale"`; the default read never returns a stale
   row presented as current.
9. DA-4: a test per unfenced table on this path (`application_ownership`,
   `organization_units`) asserts no cross-tenant leak; any raw SQL returns
   empty when `current_org_id()` is None and carries `# tenancy-ok:`; a test
   asserts this module issues no write to either table.
10. `record_query_latency` emits one OA-2 record per call with all ten fields
    populated from real values (no literals), and increments
    `archie_intelligence_query_seconds` with the query-name and hop-depth
    labels; a test asserts the metric name and labels are present in the
    existing scrape response after one query.
11. Below 100 samples, any p95 accessor returns the
    `insufficient_samples_for_p95` reason code and no number.
12. Mutation proof: disable the SEC-09 tenant assertion and confirm the
    cross-tenant owner-leak test goes red; disable the `include_derived=False`
    filter and confirm criterion 2 goes red; re-enable both; record the test
    ids in the build report.
13. `python scripts/verify.py` green (bare command, not a `--tag` subset).

## Handoff Target
`builder`, then `refuter`. Task 02 depends on this task's service being
complete; do not start 02 until 01's handoff is `approved`.
