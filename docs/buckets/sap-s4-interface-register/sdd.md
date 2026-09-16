# SDD: SAP S/4HANA Interface Register

Bucket: `sap-s4-interface-register`
Author role: `solution-architect`
Inputs: `docs/buckets/sap-s4-interface-register/brief.md`,
`docs/buckets/sap-s4-interface-register/srs.md` (handoff
`docs/handoffs/sap-s4-interface-register-business-analyst-to-solution-architect.json`,
`approval_status: approved`)
Parallel track: `integration-architect` owns the interface contract shape and the
ArchiMate element-creation mechanics. Section 9 lists exactly what this SDD
depends on from that track and leaves unresolved.
Companion decision record: [ADR 0011](../../adr/0011-derived-display-bands.md).

---

## 1. Scope of this document

This is the **general solution architecture**: module placement, blueprint
registration, route surface, service seams, screens, tenancy, and the
navigation/template contract. It deliberately does **not** specify the interface
contract fields, the ArchiMate relationship shape between an `ApplicationInterface`
element and its two `ApplicationComponent`s, or the internals of element creation —
those are `integration-architect`'s, and `tech-lead` reconciles.

**Schema position, stated up front: no new tables, no new columns, no new
relationship tables.** Every store this feature writes already exists. Section 8
justifies that claim model by model.

## 2. Which existing components this extends

Per the root `CLAUDE.md` "one system of record per concept" rule and ADR 0008, the
following is the complete list of existing things being extended rather than
duplicated. Nothing on this feature introduces a second authority for a concept
already owned.

| Concept | Existing system of record | What this feature does |
|---|---|---|
| Interface technical profile | `ApplicationInterfaceMetadata` (`app/models/integration_metadata.py`) | Gives it its first **producer**. Today the only reader is a read-only enrichment block at `app/modules/architecture/routes/archimate_routes.py:2627`. |
| The interface itself | `ArchiMateElement` where `type='ApplicationInterface'` | Creates rows of that type. No new "interface" model. |
| System-to-system coupling | `SystemDependency` (`interface_id` FK) | Writes source→interface→target rows. No new junction table. |
| Programme budget | `TechnologyRoadmapInitiative.investment_budget` | Reads it. Does not copy it. |
| As-is / to-be states | `Plateau` (+ `baseline_plateau_id`) | Creates exactly two rows per initiative. |
| Interface change between states | `Gap` with `gap_kind='plateau_transition'` | Writes gaps of that kind — the kind the model comment records as never yet written. |
| Remediation cost/effort | `WorkPackage.estimated_cost` / `.estimated_effort_hours`, linked via the `gap_work_packages` secondary | Reads and sums. **No `interface_cost` field anywhere.** |
| ArchiMate backbone sync | `app/services/archimate_backbone.py` | See §9.1 — the one genuine seam with integration-architect. |
| Null display | existing `dash` Jinja filter (`app/utils/template_utils.py:121`) | Reused for every nullable column. Do not hand-write `or '—'`. |
| Currency display | `window.currencyManager.format()` / `currency` filter (`app/template_helpers.py:33`) | Reused for the £3m rollup. |
| Sidebar / section access | `app/utils/role_access.py` | One link added. §7. |
| Page header + breadcrumb | `macros/page_shell.html::page_shell` | Used on all four screens. §6. |

**Nothing new is created at the model layer.** The one new code artefact that is
not a route, template or service is the derived T-shirt band function — which is a
pure function and a Jinja filter, not a store. That is what ADR 0011 covers.

## 3. Module placement and blueprint registration

### 3.1 Placement decision

New code lands in a **new self-contained module at `app/modules/interface_register/`**,
following `app/modules/tech_radar/` verbatim as the reference implementation.

Rationale, and the three alternatives rejected:

- **`app/integrations/` or `app/api/` (legacy flat layout) — rejected.** Root
  `CLAUDE.md`: "`app/modules/` is canonical for new work." ADR 0004 is actively
  retiring the flat layout; adding to it is moving backwards.
- **Extending `app/modules/integrations/` — rejected.** That package contains only
  a Jira sync service and webhook handler (`app/modules/integrations/jira/`); its
  `__init__.py` is empty and it has no `register(app)`, no routes and no templates.
  It is also one of the seven domains that exist in *both* layouts and is selected
  at boot by a `USE_*_GUARDRAILS` flag (root `CLAUDE.md`, ADR 0004). Landing a new
  persona-facing surface inside a flag-selected duplicate pair is how a route
  becomes conditionally unregistered, which is the `boot-health` failure mode. It
  is also a naming collision: "Integrations" in this product already means
  *outbound tool connectors* (Jira, Salesforce, Power Platform), not *application
  interfaces in the estate*. See §7 on the label.
- **Extending `app/modules/architecture/` — rejected, with a caveat.** The existing
  reader at `archimate_routes.py:2627` lives there. But that file is part of a
  module already carrying the ArchiMate CRUD surface, and the register is a
  programme-scoped workflow, not element CRUD. The caveat: the existing read-only
  enrichment block **must be left in place and must keep agreeing with the register**
  (`store-agreement`); it is a second *reader*, which is fine, not a second writer.

### 3.2 Package layout

```
app/modules/interface_register/
  __init__.py                 # register(app) — idempotent, mirrors tech_radar
  routes/
    __init__.py               # exposes interface_register_bp
    register_routes.py        # US-1, US-2, US-3
    comparison_routes.py      # US-4, US-5
    costing_routes.py         # US-6
  services/
    __init__.py
    interface_register_service.py   # interface CRUD orchestration
    plateau_pair_service.py         # US-4 idempotent provisioning
    interface_gap_service.py        # US-5
    programme_rollup_service.py     # US-6 — THE single rollup query
  templates/interface_register/
    index.html                # register list
    form.html                 # create/edit
    comparison.html           # as-is / to-be
    costing.html              # rollup
```

### 3.3 Registration

One blueprint, `interface_register_bp`, `url_prefix='/interface-register'`,
registered by adding a single tuple to `_register_optional_standalone`'s list in
`app/_bootstrap/blueprints.py` (the same list carrying `tech_radar` at line ~249):

```python
("app.modules.interface_register.routes", "interface_register_bp", "/interface-register")
```

Notes that are load-bearing:

- `init_blueprints` registers **non-fatally** — an import error here degrades to a
  missing endpoint, and any `url_for('interface_register.index')` in a template
  then `BuildError`s and 500s *every page that renders the sidebar*. Because §7
  adds a sidebar link, this endpoint must be added to `REQUIRED_ENDPOINTS` in
  `_validate_critical_endpoints()` so a boot-time warning fires, and the sidebar
  renderer's existing `selectattr('endpoint', 'in', flask.current_app.view_functions)`
  filter (`admin_sidebar.html:150`) already drops the link safely if it is absent.
  No extra `{% if %}` guard is needed *in the sidebar*; one IS needed for any
  cross-module link added elsewhere.
- **One accessor per concept, one route rule per URL.** `/interface-register` is
  not currently claimed by any blueprint. The builder must confirm with
  `verify.py --gate boot-health` and the `canonical-route` check rather than by
  reading files — root `CLAUDE.md` records three rules registered at `/api/users`
  where registration order, not source, decides the winner.

## 4. Route surface

All routes are `@login_required`. Write routes are CSRF-protected by the global
extension (no opt-out; `csrf-coverage` gate).

| Route | Method | Story | Notes |
|---|---|---|---|
| `/interface-register/` | GET | US-1 | Redirects to the initiative picker if `initiative_id` absent; does not guess one. |
| `/interface-register/?initiative_id=<id>` | GET | US-1 | Register list. Side-effect-free. |
| `/interface-register/new?initiative_id=<id>` | GET | US-2 | Create form. |
| `/interface-register/` | POST | US-2 | Create. Redirect-after-POST to the list. |
| `/interface-register/<int:element_id>/edit` | GET | US-3 | Edit form. |
| `/interface-register/<int:element_id>` | POST | US-3 | Update (incl. retire). |
| `/interface-register/comparison?initiative_id=<id>` | GET | US-4 | As-is/to-be columns. **GET creates nothing** (US-4 AC4). |
| `/interface-register/comparison/provision` | POST | US-4 | Idempotent plateau-pair provisioning, explicit user action. |
| `/interface-register/<int:element_id>/gaps` | POST | US-5 | Raise an interface gap. |
| `/interface-register/costing?initiative_id=<id>` | GET | US-6 | Rollup screen. |

Method choice is deliberate: HTML form POSTs, not a JSON API, because the
acceptance criterion is a browser walkthrough clicking real controls and asserting
persistence after reload. Any JSON endpoint added on top is
`integration-architect`'s contract question (§9.2), not a substitute for these.

**Error signalling.** `validate_gap_kind()` raises `ValueError`; the POST handler
re-renders the form with an inline error and a 4xx — it must not catch-and-succeed
(`error-signalling`, `silent-data` gates; US-5 AC3 states this explicitly). No
`fetch()` in these templates parses a response without checking `response.ok`
(`fetch-guards`).

## 5. Services and the rollup seam

### 5.1 `programme_rollup_service.py` — one query, two surfaces

US-6 AC5 (`store-agreement`) is satisfied structurally, not by discipline: there is
exactly **one** function computing the rollup, and every surface calls it.

```
def interface_programme_rollup(initiative_id) -> dict
```

Returns, at minimum: `committed_cost`, `investment_budget`, `headroom`,
`work_packages_missing_cost` (count), `over_budget` (bool), and the per-work-package
rows. Rules baked into this one function so no caller can get them wrong:

- A `WorkPackage` with `estimated_cost IS NULL` is **excluded from the sum and
  counted in `work_packages_missing_cost`** — never coerced to `0`. A `0` that
  means "not computed" is indistinguishable from a measured zero (`fabricated-data`
  gate; US-6 AC2).
- `investment_budget` may itself be NULL. Then `headroom` is `None` and the
  template renders `—`; it does **not** render the committed cost as if it were
  headroom, and `over_budget` is `None`, not `False`.
- `over_budget` is returned as its own flag so the template can render an explicit
  indicator rather than leaving the user to compare two numbers (US-6 AC4).

Any dashboard card referencing S/4HANA programme cost imports this function. A
second implementation of the same sum is a defect even if it agrees today.

### 5.2 `plateau_pair_service.py` — idempotency without a new column

Provisioning must be idempotent (US-4 AC1) and there is no `plateau_kind` column
and none is being added. The pair is identified by
`(architecture_id / initiative linkage, name, sequence_order)` with the to-be
plateau's `baseline_plateau_id` pointing at the as-is one — the `baseline_plateau_id`
link is what makes the pair a pair, and it is the discriminator the comparison
screen queries on. Provisioning is a `SELECT`-then-`INSERT` inside one transaction
on the POST path only; a repeat POST returns the existing pair unchanged.

`WorkPackage` name-uniqueness has a precedent for this (`materialisation_key` +
the `uq_work_package_materialisation` partial index). `Plateau` has no such column
and adding one is out of scope; the `baseline_plateau_id` discriminator is
sufficient because the pair is per-initiative and the screen only ever asks for
"the pair for this initiative".

### 5.3 `interface_register_service.py`

Owns the US-2 three-step write (element → metadata → two `SystemDependency` rows)
as **one transaction**. A partial write here is exactly the "store with no
producer" shape inverted — a metadata row whose element does not exist, or an
element with no metadata. `ApplicationInterfaceMetadata.archimate_element_id` is
`nullable=False, unique=True`, so element creation must precede and flush before
the metadata insert. See §9.1: the element-creation call itself is
integration-architect's.

## 6. Screens

Four screens, all using `macros/page_shell.html::page_shell` (the macro the
`shell-conformance` gate counts; `components/page_header.html` is the older one and
is not used for new work, per DESIGN.md).

Every screen: exactly one `<h1>`, owned by `page_shell`; `breadcrumb` supplied as
`(label, href)` tuples with the last taking `None`; no hand-rolled header row
beside the macro (`breadcrumb-coverage` and `duplicate-breadcrumb` gates).

| Screen | `page_shell` breadcrumb |
|---|---|
| Register list | `[('Home', main.index), ('Interface Register', None)]` |
| Create / edit | `[('Home', …), ('Interface Register', index), ('New interface'/name, None)]` |
| Comparison | `[('Home', …), ('Interface Register', index), ('As-is / To-be', None)]` |
| Costing | `[('Home', …), ('Interface Register', index), ('Costing', None)]` |

Non-default states, specified rather than left to the builder (UI/interaction
architect's before-question):

- **Empty register** — explicit "No interfaces registered for this initiative"
  with the create action inside the empty state, not a zero-row table and not a
  "0" presented as a total (US-1 AC5). Use the existing empty-state macro; root
  `CLAUDE.md` records that **two** `empty_state` macros exist with incompatible
  signatures and importing the wrong one raises `TypeError` and 500s the page —
  the builder must confirm which one the chosen base template's import context
  resolves to, and import it `with context` if it carries script
  (`macro-import-context` gate).
- **Interface with no metadata row** — still listed; every metadata column renders
  `—` via the `dash` filter (US-1 AC3). This is a valid register entry, not an
  error banner.
- **Comparison before provisioning** — a single explicit "Set up As-is/To-be
  comparison" button; the two columns are not rendered empty-but-labelled as
  though they existed.
- **Over budget** — a distinct indicator (badge + text), not a red number.
- **Narrow / overflowing** — the register table has 8+ columns; it must collapse to
  a card list rather than horizontally scrolling a 12,000px page. Name and
  `business_criticality` are the two columns that survive the collapse.
- **Truncation** — interface names are `ArchiMateElement.name String(100)` and
  `sync_archimate_element` truncates at 100 with an ellipsis, storing the full
  value in `custom_properties['source_name']`. Where a name is truncated the
  register must show the full value on hover/title, or the register disagrees with
  the element page.

Entity fields (source/target `ApplicationComponent`) use the documented debounced
live-search picker per DESIGN.md and root `CLAUDE.md`'s entity-field rule — free
text is not acceptable (US-2 AC3). No `onclick=`, no native `alert`/`confirm`
(CSP kills inline handlers here; use `data-confirm`), `Platform.fetch` not raw
`fetch`, no `console.*` (`ui-contract`, `raw-fetch-sites`, `console-reporting`).

Template class changes require `python scripts/build_css.py` — the committed
`tailwind-output.css` is what runs, and `css-build` fails on a stale one.

## 7. Navigation, personas and access control

### 7.1 There is no `integration_architect` enterprise role — decision, not a question

US-7 AC1 asks for the entry to appear for the `solution_architect` **and**
`integration_architect` enterprise roles. `integration_architect` **does not
exist**: `app/utils/role_access.py` imports eleven role constants and
`integration_architect` is not among them, it is absent from
`ENTERPRISE_ROLE_SECTION_MAP` in `app/_bootstrap/context_processors.py`, and it is
not in the eleven canonical `ARCHETYPES` in `tests/smoke/conftest.py`.

**Decision: do not add a twelfth persona for this feature.** Adding one means
touching `role_access.py`, `ENTERPRISE_ROLE_SECTION_MAP`, `ARCHITECT_PERSONAS` in
`app/modules/ai_chat/services/architect_persona_charters.py`, the sidebar, the
authorisation matrix and the visual/a11y baselines — a persona-platform change
with its own blast radius, wholly disproportionate to shipping a register. The
Integration Architect *actor* in the SRS maps onto the existing
`solution_architect` and `enterprise_architect` roles, both of which already hold
the `data_integration` section. If the owner wants a distinct Integration
Architect persona, that is its own bucket.

### 7.2 Section and sidebar link

- **Section: `data_integration`** — already in `NAVIGATION_SECTIONS`
  (`role_access.py:40`) and already granted to `solution_architect`,
  `enterprise_architect`, `business_architect` and `platform_admin`. **No new
  section.**
- **Link: one, in `_MY_WORK_LINKS[ROLE_SOLUTION_ARCHITECT]`**, label
  **"Interface Register"**, icon `cable` (distinct from `git-merge` Programmes,
  `git-branch`, `waypoints`, `milestone` already in use). The label deliberately
  avoids "Integrations", which in this product already names the outbound-connector
  admin surface — content designer's before-question: the two must be
  distinguishable at a glance in a collapsed sidebar, and "Integrations" vs
  "Interface Register" at 12 characters truncates to "Integ…" vs "Interf…", which
  is not distinguishable. If the collapsed rail shows icon only, `cable` vs
  `plug`/`link` must also be checked against the collapsed-sidebar defect root
  `CLAUDE.md` records.
- **Budget.** `SIDEBAR_LINK_BUDGET = 28`; the `sidebar-links` gate is ratcheted at
  27. `solution_architect`'s My-work zone currently holds 6 links and the role is
  well under the ceiling, so this is a 6→7 change that moves neither number.
  **Do not add the same link to `enterprise_architect`** — the in-file comment at
  `role_access.py:468-479` records EA at exactly 25 rendered links with the
  instruction that a new EA link must be paid for by retiring an existing one. EA
  reaches the register via Library/All-modules. If EA discoverability is judged
  insufficient after the walkthrough, that is a separate ratchet decision with its
  own justification, not a silent `+1`.

### 7.3 A pre-existing ADR-0008 violation this feature must not deepen

Section-to-role access is currently held in **two** places that must agree:
`ROLE_SECTION_ACCESS` (`app/utils/role_access.py:51`) and
`ENTERPRISE_ROLE_SECTION_MAP` (`app/_bootstrap/context_processors.py:457`). They
already disagree — `security_architect` and `data_architect` have entries in the
first and none in the second. That is two authorities for one question.

**Instruction to the builder: do not add a third copy, and do not edit only one.**
The in-scope, minimal correction is to make `ENTERPRISE_ROLE_SECTION_MAP` derive
from `ROLE_SECTION_ACCESS` (preserving the legacy alias sets it adds) so there is
one system of record. If `tech-lead` judges that out of scope for this bucket, it
must be recorded as an open finding rather than silently left — root `CLAUDE.md`
is explicit that a note is not a substitute for a fix and that a counting gate
beats prose.

### 7.4 Route guards

Route authorisation uses the **same predicate the sidebar uses** — the
`role_access` section check for `data_integration` — not a bespoke decorator and
not `enterprise_role` compared inline. Root `CLAUDE.md` records three parallel
authorisation vocabularies (`enterprise_role`, `Role`/`Permission`,
`is_platform_admin`) and that nav-versus-guard divergence is the root cause of the
F-01/F-11/F-04 family of defects: a sidebar link that 403s is a dead end.

## 8. Tenancy

`WorkPackage`, `Plateau`, `Gap` and `ImplementationEvent` all carry `TenantMixin`.
`ApplicationInterfaceMetadata`, `SystemDependency` and `TechnologyRoadmapInitiative`
do **not**.

### 8.1 The route layer hand-writes no `organization_id` filter

Confirmed as required by the task. On `TenantMixin` models the filter is injected
by `do_orm_execute` (`app/middleware/tenant_isolation.py`) and `organization_id` is
auto-set on flush. Writing `filter_by(organization_id=...)` on top **double-filters**
and is a defect. So:

- `Plateau`, `Gap`, `WorkPackage` queries in this feature carry **no**
  `organization_id` predicate. Every route runs inside a request context, where
  `g.current_org_id` is set. This satisfies US-1 AC4, US-2 AC4, US-3 AC4, US-5 AC5
  mechanically rather than by inspection.
- No bulk `UPDATE`/`DELETE` is used on this feature's write paths. (ADR 0003 closed
  the bulk-write gap, but none is needed here.)
- No raw SQL. The rollup is an ORM aggregate over `WorkPackage` joined through the
  `gap_work_packages` secondary, so `raw-sql-tenancy` and `tenant-scoping` are
  satisfied without an escape hatch. **No new `tenancy-ok` / `tenant-scoping-ok`
  marker is introduced by this feature.** If the builder finds one is needed, that
  is a design change to escalate to `tech-lead`, not a comment to write.
- `Query.get()` / `Session.get()` is **not** used to load a tenant-scoped row by id
  in these routes — use `.filter_by(id=…).first()`. Root `CLAUDE.md` records that
  `.get()` is scoped only on an identity-map miss. Per-request code is normally
  safe, but the habit is cheap and the failure is silent.

### 8.2 The three non-tenant models

- **`ApplicationInterfaceMetadata`** — reached only through its
  `archimate_element_id` to an `ArchiMateElement`, which carries
  `organization_id` (`sync_archimate_element` sets it explicitly). The register
  query is therefore rooted at `ArchiMateElement` and joins outward to metadata;
  it never queries `ApplicationInterfaceMetadata` as the primary entity. That is
  the whole of the isolation argument and it must be asserted by a cross-org smoke
  case, not assumed.
- **`SystemDependency`** — same argument: rooted at the element, never queried
  standalone.
- **`TechnologyRoadmapInitiative`** — the SRS's Assumption A1. It has no
  `organization_id` and adding one is out of scope (and `reconcile-schema` is
  ADD-nullable-only, so a backfill-requiring column would break existing
  databases). **Solution-architect confirmation, as A1 requested: indirect scoping
  via `architecture_id` → `ArchitectureModel` is accepted for this bucket, with
  two conditions.** (a) The initiative picker and every `initiative_id` route
  parameter resolve the initiative **through** its `architecture_id` within the
  caller's tenant and 404 when it does not resolve — an `initiative_id` in a query
  string is attacker-controlled input, and "this org can see this initiative" must
  be a query, not an assumption. (b) An initiative with `architecture_id IS NULL`
  is **not** addressable from this feature; it resolves to 404, not to "visible to
  everyone". Both are asserted in `tests/smoke/test_authorisation_matrix.py`,
  including an explicit cross-org negative case. This is defensible because the
  exposure is bounded (an initiative name and a budget figure) and the alternative
  is a schema change the brief rules out; it is recorded here as a decision with a
  measurement, not as an assumption.

### 8.3 Outside a request context

No CLI command, importer or scheduler job is added by this feature. If one is added
later (e.g. seeding the 18 Saint-Gobain interfaces), it has **no**
`g.current_org_id` and is therefore unfiltered: it must scope explicitly and call
`db.session.remove()` between tenants.

## 9. Dependencies on the integration-architect track — unresolved here

Stated explicitly so `tech-lead` can see the seam rather than discover it.

### 9.1 Element creation cannot use `sync_archimate_element()` as it stands

This is a concrete finding, not a caveat. `app/services/archimate_backbone.py` is
the single sanctioned `_sync_archimate_element`, and it:

- keys off the **Python model class name** via
  `ELEMENT_TYPES` (`archimate_backbone.py:45-59`), which contains no
  `ApplicationInterface` entry and no `ApplicationInterfaceMetadata` entry, so
  `sync_archimate_element(metadata_row)` returns `None` today — silently;
- creates the element *from an existing domain row* and then sets
  `obj.archimate_element_id`. For an interface the dependency runs the other way:
  `ApplicationInterfaceMetadata.archimate_element_id` is `nullable=False`, so the
  element must exist **before** the metadata row can be inserted at all.

So the brief's "via `_sync_archimate_element()`" cannot be satisfied literally
without either adding `ApplicationInterfaceMetadata` to `ELEMENT_TYPES` and
inverting the helper's ordering contract, or creating the element through the
element-creation path and treating the metadata row as a pure extension.

**This SDD does not decide that — it is squarely integration-architect's ArchiMate
sync mechanics scope, and it is UNRESOLVED at handoff.** What this SDD binds
regardless of which way it goes:

1. There is **one** element-creation call site for interfaces, inside
   `interface_register_service.py`, not one per route.
2. The element carries `organization_id`, `type='ApplicationInterface'`,
   `layer='Application'`, and provenance in `custom_properties` (`source_model`),
   matching what `sync_archimate_element` already writes — so a later unification
   is a refactor, not a data migration.
3. It does not silently return `None`. A failure to place the interface on the
   backbone raises, per that module's own stated contract.

### 9.2 Also integration-architect's, referenced not decided

- The interface contract field set beyond the SRS's listed subset (OpenAPI/AsyncAPI
  spec storage, SLA fields, PII/GDPR fields — all columns that already exist on
  `ApplicationInterfaceMetadata` and are simply not surfaced by US-2).
- The ArchiMate relationship shape between the interface element and its two
  `ApplicationComponent`s, and whether `SystemDependency` rows are the only record
  of it or are mirrored as `ArchiMateRelationship` rows.
- Whether a JSON API is exposed alongside the HTML routes, and under which prefix.
  If one is: it must call the §5.1 rollup function, not reimplement it.

## 10. Verification this design must survive

Not a list of hopes — each maps to a gate or a named test file.

| Gate / test | What this feature must satisfy |
|---|---|
| `boot-health` | blueprint registers; every `url_for` resolves; new endpoint in `REQUIRED_ENDPOINTS` |
| `csrf-coverage` | four write routes, no opt-out |
| `store-agreement` | register total, costing total and any dashboard card all call §5.1 |
| `fabricated-data` | NULL cost excluded and counted, never `0`; NULL band renders `—` |
| `breadcrumb-coverage` / `duplicate-breadcrumb` | four screens, one `page_shell` each |
| `shell-conformance` | `page_shell`, not `page_header` |
| `sidebar-links` / `nav-coverage` / `nav-verified` | one SA link; ratchet unmoved; smoke test loads it |
| `tenant-scoping` / `raw-sql-tenancy` | no hand-written org filter, no raw SQL, no new escape hatch |
| `error-signalling` / `silent-data` | `validate_gap_kind`'s `ValueError` reaches the user as an error |
| `dead-interactions` / `ui-contract` | every control wired; no `onclick=`, no native dialogs |
| `smoke-coverage-on-change` | templates change ⇒ `tests/smoke/` changes in the same diff |
| `test_authorisation_matrix.py` | rows for all four GET routes × eleven archetypes, incl. `procurement` negative and the §8.2 cross-org initiative negative |
| `test_archetype_journeys.py` | the full walkthrough: create interface → see it as an element → raise a gap → attach a costed work package → **reload** → rollup changed |
| `css-build` | `scripts/build_css.py` run if classes changed |

The journey test is the acceptance criterion. Per "Done means DEMONSTRATED", a
green `verify.py` is evidence of no source regression, not evidence the register
works.

## 11. SRS story coverage

| Story | Covered by |
|---|---|
| US-1 view register | §4 GET `/`, §6 list screen + empty/no-metadata states, §8.1 |
| US-2 create | §4 POST `/`, §5.3 single transaction, §6 entity pickers, §9.1 seam |
| US-3 edit/retire | §4 `/…/edit` + POST; `operational_status` + `retirement_date` already exist (§8, no new column) |
| US-4 plateau pair | §5.2 idempotent POST-only provisioning, §6 comparison screen, §4 GET side-effect-free |
| US-5 raise gap | §4 POST `/…/gaps`, §2 `gap_kind='plateau_transition'`, §4 error signalling |
| US-6 rollup | §5.1 single rollup function, §6 over-budget state, ADR 0011 for the band |
| US-7 sidebar | §7 in full (incl. the `integration_architect` decision) |

## 12. Open items for `tech-lead`

1. §9.1 — the element-creation mechanic. Blocking for `builder`.
2. §7.3 — whether the `ROLE_SECTION_ACCESS` / `ENTERPRISE_ROLE_SECTION_MAP`
   de-duplication lands in this bucket or is booked as a finding.
3. §7.2 — EA sidebar discoverability, if the walkthrough shows the persona cannot
   find the register. Costs a ratchet raise or a link retirement.
