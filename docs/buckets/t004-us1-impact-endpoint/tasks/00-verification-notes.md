# T-004 — Tech-lead verification notes

Every file:line citation in `brief.md` was re-derived against this worktree
(`feature/t004-us1-impact-endpoint`, based on main including T-002 and T-003).
This file records what held, what did not, and the design decisions taken
before any code is written. The brief is **not** rubber-stamped: four defects
are recorded below, two of which would have produced a review-blocking result
if built as written.

## 1. Citation verification

| Brief citation | Result |
|---|---|
| `app/utils/api_response.py:14-36` — `success_response` | **Exact.** `def success_response` at 14, `return jsonify(...)` at 36. |
| `app/models/enterprise_intelligence.py:186-199` — `ApplicationOwnership` | **Off by a few lines, substantively correct.** The class is declared at **180**; 186 is `__tablename__`, 190-195 are the two FKs, and the class runs to 215. Use 180-215 when quoting it. |
| `app/models/application_portfolio.py:309-317` — `archimate_element_id` | **Off by two lines.** The column spans **309-319** (`nullable=True, index=True` at 317-318, close paren 319). Column and FK target as described. |
| `app/models/application_portfolio.py:951-983` — `before_insert` listener | **Exact.** `create_app_component_archimate_element` at 951-983. |
| `app/api/v1/impact.py:24-96` — canonical endpoint | **Exact.** `@impact_bp.route("/analyze")` at 24, handler ends 96. |
| `app/api/v1/impact.py:21`, `:53-57` — `VALID_SCENARIOS` / validation | **Exact.** |
| `app/api/v1/impact.py:112-134` — `{id,name,type,level}` projection | **Correct but incomplete — see defect D2.** |
| `app/services/prometheus_metrics.py:26` — `REGISTRY` | **Exact.** `REGISTRY = CollectorRegistry()` at 26. |
| `app/services/prometheus_metrics.py:39`, `:109` — histogram examples | **Exact.** `HTTP_REQUEST_DURATION` at 39, `AI_REQUEST_DURATION` at 109, both `registry=REGISTRY`. |
| `app/modules/monitoring/v2/routes/metrics_routes.py:23`, `:27-31` | **Exact.** `metrics_bp_v2` at 23, `@route("/metrics")` 27-31 calling `get_metrics_response()`. |
| `app/services/archimate_impact_service.py:18`, `:36`, `:82` | **Exact.** Class at 18, `ArchiMateElement.query.get` at 36 and 82. |
| `app/modules/solutions_strategic/v2/services/impact_analysis_service.py:114-116` | **Exact.** `org_id = current_org_id()` / `if org_id is None: return []`. |
| `...impact_analysis_service.py:156` — `# tenancy-ok:` marker | **Exact.** |
| `...impact_analysis_service.py:60-65` — `estimated_financial_risk` | **Exact.** |
| `...impact_analysis_service.py:160-172` — `app_name`/`criticality`/`tco` | **Exact.** |

Additionally verified, not cited by the brief but load-bearing:

- `ArchiMateElement` and `ArchiMateRelationship` both carry `TenantMixin`
  (`app/models/archimate_core.py:53`, `:110`) — so the element lookup that
  seeds the walk is fenced by `do_orm_execute` with no hand-written predicate.
- `ApplicationComponent` carries `TenantMixin`
  (`app/models/application_portfolio.py:80`).
- `OrganizationUnit` (`app/models/enterprise_intelligence.py:129`) and
  `ApplicationOwnership` (`:180`) carry **no `organization_id` column at all**
  and do **not** inherit `TenantMixin`. The brief's SEC-09 premise is correct
  and stronger than stated: these tables are entirely unfenced, so the tenant
  assertion is the *only* thing standing between the join and a cross-tenant
  unit name.

## 2. T-003's actual shape vs. what this brief assumes

T-003 (`app/modules/intelligence/`) shipped:

- `models/derived_relationship.py` — `DerivedRelationship`, `TenantMixin`,
  table `archimate_derived_relationships`, carrying `source_element_id`,
  `target_element_id`, `derived_type`, `rule_id`, `chain` (relationship ids),
  `chain_element_ids` (node path), `depth`, `confidence`, `provenance`,
  `engine_version`, `computed_at`, `stale`, `stale_since`, `stale_reason`.
- `services/derived_facts.py` — `list_derived_facts(...)` and
  `get_derived_fact(...)`, declared in its own docstring as **the ONE accessor
  over the derived-fact store (ADR-004/ADR-0008)**, with the `stale = FALSE`
  default applied in a single isolated seam `_apply_default_staleness_filter`.
- `services/reason_codes.py` — the closed 16-member DE-14 vocabulary with
  `validate_reason_code()`. Every code T-004's acceptance criteria name
  (`no_ownership_recorded`, `no_maturity_recorded`,
  `derivation_not_computed`, `derivation_stale`,
  `insufficient_samples_for_p95`) is present.
- `services/observability.py` — `record_invalidation` / `InvalidationRecord`.
  Its docstring explicitly records that `record_query_latency` **does not
  exist anywhere in the repo** and is T-004's to create.
- `routes/api.py` — blueprint **`intelligence_api`, already registered with
  `url_prefix="/api/v1/intelligence"`**, carrying two routes, and stating in
  its module docstring that "the US-1 impact endpoint is T-004 and is NOT
  added here".
- `__init__.py::register(app)` — non-fatal registration of the invalidation
  listener and the API blueprint, with a comment reserving a UI blueprint slot
  for T-004.

Confirmed grep: no `record_query_latency`, no `cross_layer_impact`, no
`IntelligenceQueryService`, no `archie_intelligence_query_seconds` anywhere
under `app/`. T-004 builds all four from scratch; nothing is being duplicated.

The dependency is satisfied. Four corrections to the brief's assumed read
path follow.

## 3. Defects found in the brief

### D1 (blocking as written) — the deliverable creates a second blueprint on an existing URL prefix

The brief's Deliverable says build
`app/modules/intelligence/routes/intelligence_api.py`. A blueprint **named**
`intelligence_api`, with `url_prefix="/api/v1/intelligence"`, already exists
in `app/modules/intelligence/routes/api.py` and is already registered by
`register(app)`. Adding a second module with a second blueprint on the same
prefix is precisely the ADR 0008 rule-3 defect ("Two routes on one URL ... is
a defect even while it appears to work") and is the failure mode CLAUDE.md
cites three times at `/api/users`.

**Decision:** the US-1 route is added to the existing
`app/modules/intelligence/routes/api.py`, on the existing `intelligence_api`
blueprint. No new routes module. `register(app)` is unchanged for the API.
Task 02 owns this.

### D2 (blocking as written) — the "unchanged projection" claim is only half true

The brief states the canonical route "projects each affected element to
`{id,name,type,level}` (`:112-134`)". That projection lives in
`_normalise_element_result` and applies **only to the `element_id` path**.
The `app_id` path (`:70-74`) returns `AIImpactAnalysisService`'s result
straight through `_to_contract_shape` (`:137-147`), whose
`affected_elements` line is a pass-through with **no projection at all**.
So acceptance item 16's "projection byte-identical before/after" is a claim
about one of the two branches.

**Decision:** acceptance item 16 is restated in task 02 as: the `element_id`
branch's projection is unchanged and asserted by test, **and** the `app_id`
branch is asserted to be untouched by this task (characterisation test
capturing its current keys before the change). Widening `_to_contract_shape`
to project is *not* in scope — it would change existing response values and
violate the additive-only constraint. It is recorded as an open follow-up
(SEC-02 hole on the `app_id` branch) rather than silently fixed here.

### D3 (blocking as written) — acceptance item 9's "byte-identical 404" is impossible

`error_response` (`app/utils/api_response.py:39-61`) puts a fresh
`uuid.uuid4()` `request_id` and a `datetime.utcnow()` `timestamp` in `meta`
on **every** response. No two error responses from this codebase are ever
byte-identical. Written as-is, acceptance item 9 is either untestable or will
push the builder to bypass the standard envelope to satisfy it — which would
itself be a defect.

**Decision:** acceptance item 9 is restated as *indistinguishability*, which
is the actual security property: same HTTP status (404), same
`error.code` (`NOT_FOUND`), same `error.message`, same key set, differing only
in the `meta` envelope's `timestamp`/`request_id`. The test compares the
response with `meta` removed. `not_found_response("Element")` from the shared
util is the single call site for both branches, so there is one code path, not
two that happen to agree.

### D4 (design gap) — `list_derived_facts` cannot express three of API-1's parameters

The brief assumes the derived store is read for `max_depth`, `direction` and
`layer`. `list_derived_facts` today supports only `organization_id`,
`include_stale`, `source_element_id`, `target_element_id`, and it **ANDs**
the two element filters — so it cannot express:

- `max_depth` — no depth predicate (rows carry `depth`, the accessor ignores it);
- `direction=both` — needs `source = X OR target = X`, the accessor gives AND;
- `layer` — `DerivedRelationship` has no layer column; layer is a property of
  `ArchiMateElement` and requires a join.

**Decision:** extend the existing accessor in
`app/modules/intelligence/services/derived_facts.py` with `max_depth`,
`direction` and a `layer` join — do **not** write a second query over
`archimate_derived_relationships` in the query service. That store has exactly
one declared accessor and it stays that way (ADR 0008 rule 3; the accessor's
own docstring says "no other read path over the store may exist at L1
(NFR-8)"). Filtering in Python after an unfiltered fetch is also rejected: it
defeats the `ix_dr_src`/`ix_dr_tgt` partial indexes and puts NFR-5's 2.0s p95
at risk on the largest tenant. Task 01 owns this extension, and it is additive
— existing defaults and existing callers unchanged.

## 4. Open question resolved — the UI surfaces do not exist

Searched: no `app/modules/intelligence/templates/` directory at all; no
template, route or JS anywhere under `app/` matching Ask, Twin map, or a
derivation Provenance drawer. The only adjacent thing that exists is
`app/templates/components/provenance.html` — a set of *badge//pill* macros
(`measured` / `missing` / `ai` / `unavailable`) for marking where a single
value came from. That is a useful primitive for FR-15 reason rendering, but it
is not a provenance drawer and it knows nothing about derivation chains.

So all three named screens are greenfield. This is a materially larger scope
than "UI surfaces calling API-1/API-2": a hop-depth slider, a graph rendering
with derived edges distinguished on a non-colour channel, and a chain-expansion
drawer are each a design decision this task has no design source for in this
repo (the Screens & Surfaces section lives in a spec that is not checked out
here).

**Recommendation, taken as a decision: descope the UI from T-004.** T-004 ships
the backend contract, the metrics, and the reason codes — a complete, testable,
demonstrable-by-API-and-test deliverable. The UI becomes T-004b with
`conversational-ux-designer` / UI-architect involvement before a builder brief
exists, rather than a builder inventing three screens from a sentence.

Consequences of the descope, carried explicitly rather than dropped:

- Acceptance item 6's Playwright "rendered screen shows the reason text" and
  item 7's "one-click run action" move to T-004b. Their **API halves** stay in
  T-004: the three distinct reason codes and `derivation_state` values must be
  present and correct in the payload, asserted by API test.
- Acceptance item 13 (authorisation matrix across eleven personas) stays in
  T-004 but is scoped to the new REST route, not to persona-visible pages.
- `register(app)`'s reserved UI-blueprint slot stays reserved and unused.
- Task 03 in this bucket is the descope record, not a build task.

"Done means DEMONSTRATED" is not weakened by this: T-004 is not claimed as a
shipped user-facing feature. It is claimed as the endpoint T-004b demonstrates
through. That distinction is written into task 03 so nobody later reads a green
T-004 as "US-1 is done".

## 5. Other decisions taken here

- **Owner join goes through the ORM, not raw SQL.** `ApplicationComponent`
  carries `TenantMixin`, so resolving `archimate_element_id -> component` via
  the ORM is fenced automatically by `do_orm_execute`; the SEC-09 assertion is
  then a belt-and-braces `organization_id == current_org_id()` check on the
  resolved component before any `OrganizationUnit.name` is read. This is
  simpler and harder to get wrong than a raw-SQL join, and needs no
  `# tenancy-ok:` marker. The marker pattern at
  `impact_analysis_service.py:114-116`/`:156` applies only if a recursive raw
  walk turns out to be necessary for the explicit-edge side — task 01 should
  prefer reusing the existing walk over writing a new one.
- **The `before_insert` listener is not a guarantee.** It fires only on insert
  and only when `archimate_element_id is None`, so components created before it
  existed, or by raw SQL/import paths, can still have a NULL link. A NULL link
  is an ordinary `no_ownership_recorded` path, not an error — this is why the
  reason code is indistinguishable from the SEC-09-failure path, which is what
  acceptance item 5 wants anyway.
- **Do not touch `ArchiMateImpactService`.** The brief is right that its
  `.query.get()` usage is safe inside a request. Task 01 must not call it from
  anything the recompute job reaches.
- **`archimate_elements.application_component_id`** exists and is used by
  `impact_analysis_service._get_dependencies` — a *second*, opposite-direction
  link between elements and components alongside
  `ApplicationComponent.archimate_element_id`. Task 01 uses
  `ApplicationComponent.archimate_element_id` (the brief's choice, and the one
  the `before_insert` listener maintains) and must not introduce a third path
  or silently fall back between the two. The duplication itself is pre-existing
  and out of scope; it is recorded here so it is not discovered mid-build and
  "fixed" by adding a fallback.
