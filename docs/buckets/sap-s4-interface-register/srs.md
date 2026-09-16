# SRS: SAP S/4HANA Interface Register

Bucket: `sap-s4-interface-register`
Source brief: `docs/buckets/sap-s4-interface-register/brief.md`
Grounded against: `app/models/integration_metadata.py` (`ApplicationInterfaceMetadata`,
`SystemDependency`), `app/models/implementation_migration.py`
(`TechnologyRoadmapInitiative`, `Plateau`, `Gap`, `WorkPackage`, `Deliverable`),
and ArchiMate 3.2's Application layer (`ApplicationInterface`) and
Implementation & Migration layer (`Plateau`, `Gap`, `WorkPackage`) metamodel.

## 0. Grounding notes (read before the stories)

- **Corrected 15 Sep 2026** — this bullet previously said no separate
  `ApplicationInterface` ORM class exists in this codebase. That was wrong: one
  does, at `app/models/application_layer.py:42` (`TenantMixin`, backed by the
  `application_interfaces` table, with a `before_insert` listener that mirrors
  a row into `ArchiMateElement`). This feature deliberately does **not** write
  to that class or rely on its listener — see
  `implementation-plan.md` §1.2 — because the listener uses a raw core
  `connection.execute(insert(...))` that skips `scope`, `custom_properties` and
  the ORM tenant hooks the register needs. The conclusion below is unchanged:
  "interface" in this feature means the ArchiMate `ApplicationInterface`
  element type, created element-first via `create_backbone_element()` /
  `sync_archimate_element()` in `app/services/archimate_backbone.py`, with
  `ApplicationInterfaceMetadata.archimate_element_id` (unique, FK to
  `archimate_elements.id`) as its 1:1 metadata extension. Every user story
  below that says "create an interface" means: create an `ArchiMateElement`
  of type `ApplicationInterface` via `create_backbone_element()`, then attach
  one `ApplicationInterfaceMetadata` row to it.
- The "named initiative" the brief refers to for scoping and budget is
  `TechnologyRoadmapInitiative` (`app/models/implementation_migration.py:32`),
  the only model in this codebase carrying `investment_budget`. It is
  **not** `TenantMixin`-scoped itself (no `organization_id` column) — see
  Assumption A1.
- `Plateau`, `Gap`, `WorkPackage` are all `TenantMixin`. The two comparison
  plateaus ("Current Integration Landscape" / "S/4HANA-Integrated
  Landscape") are ordinary `Plateau` rows distinguished by `sequence_order`
  and linked via `baseline_plateau_id` (to-be → as-is).
- Per the brief's constraint and `Gap.gap_kind`'s own docstring
  (`implementation_migration.py:526-547`), every interface gap created by
  this feature MUST be `gap_kind='plateau_transition'` with both
  `originating_plateau_id` and `target_plateau_id` set — `validate_gap_kind()`
  already rejects a `plateau_transition` missing either, so this is enforced
  in code today, not just by convention.
- T-shirt size band is **derived, never stored**: a display-time function of
  `WorkPackage.estimated_effort_hours`. See Assumption A4 for the banding
  thresholds.

## 1. User Stories

### US-1 — View the Interface Register

As a **Solution Architect**, I want to see a list of all
`ApplicationInterface` elements (+ their `ApplicationInterfaceMetadata`)
scoped to the current `TechnologyRoadmapInitiative`, so I can assess the
S/4HANA integration landscape at a glance.

**Acceptance Criteria**
1. A new route (e.g. `GET /integration/interface-register?initiative_id=<id>`)
   lists every `ArchiMateElement` of `type='ApplicationInterface'` that is
   linked (directly, or via its metadata row's originating `Gap`/`WorkPackage`
   — see US-4) to the selected initiative, joined to its
   `ApplicationInterfaceMetadata` row.
2. Each row shows at minimum: interface name, `interface_type`, `protocol`,
   `message_pattern`, `is_synchronous`/async label, `business_criticality`,
   `transaction_volume_daily`, `operational_status`.
3. An interface with no `ApplicationInterfaceMetadata` row yet still appears
   (metadata columns render as em dash `—`, never `0` or blank, per root
   CLAUDE.md's null-display convention) — a plain ArchiMate element with no
   metadata is a valid, if incomplete, register entry, not an error state.
4. The list is `organization_id`-scoped (via `TenantMixin` on the underlying
   join path); a user from a different org sees zero rows, never another
   org's interfaces.
5. Empty state (no interfaces yet for the initiative) renders an explicit
   "No interfaces registered" message with a create action, not a blank
   table or a fabricated zero-row count presented as a real total.
6. `tests/smoke/test_authorisation_matrix.py` gains a row for this route
   stating which of the eleven canonical archetypes reach it and which do
   not (see US-7).

### US-2 — Create an Interface Register entry

As a **Solution Architect**, I want to register a new SAP S/4HANA
integration interface, so that its technical profile is captured as a real
ArchiMate element from the moment it is proposed.

**Acceptance Criteria**
1. A create form captures: name, description, `interface_type`, `protocol`,
   `data_format`, `message_pattern`, `is_synchronous`, `authentication_method`,
   `business_criticality`, `transaction_volume_daily`, and the two systems it
   connects (source/target `ApplicationComponent`, recorded via
   `SystemDependency.interface_id` linking back to the new element — reusing
   `SystemDependency`, not a new junction table).
2. Submitting the form: (a) creates an `ArchiMateElement` of
   `type='ApplicationInterface'`, `layer='Application'` via
   `app.services.archimate_backbone.create_backbone_element()` — called
   directly, not via `sync_archimate_element()`, because
   `ApplicationInterfaceMetadata` has none of `sync_archimate_element`'s
   `NAME_FIELDS` columns (Task 01 result, D1), (b) creates
   one `ApplicationInterfaceMetadata` row with `archimate_element_id` set to
   it, (c) creates the two `SystemDependency` rows (source→interface,
   interface→target) with `interface_id` set.
3. No plain-textarea substitute exists anywhere in this flow — every field
   that names a system uses the documented live-search entity picker
   (`DESIGN.md`), not free text, per root CLAUDE.md's entity-field rule.
4. The write path applies `TenantMixin`'s implicit `organization_id`
   scoping/assignment; no hand-written `organization_id=` filter is added on
   top of it.
5. The new interface appears in the Interface Register list (US-1) and, on
   the existing read-only element detail page
   (`app/modules/architecture/routes/archimate_routes.py:2627`), without a
   page reload discrepancy — same total, same fields, per `store-agreement`.
6. Validation: required fields (name, `interface_type`, `protocol`) block
   submission with an inline error, not a 500 or a silently-dropped field.
7. CSRF-protected write route (`csrf-coverage` gate).

### US-3 — Edit / retire an Interface Register entry

As a **Solution Architect**, I want to edit an interface's metadata or mark
it retired, so the register reflects the current true state of the
integration landscape as the programme progresses.

**Acceptance Criteria**
1. Edit form pre-populates from the existing `ApplicationInterfaceMetadata`
   row (creating one on first edit if none exists yet, per US-1 AC3).
2. Setting `operational_status='retired'` also sets `retirement_date` (defaults
   to today, editable) and requires no new column — both already exist.
3. Edits persist and are visible after a full page reload (not just in the
   submitting browser tab's in-memory state).
4. Edit route is CSRF-protected and `organization_id`-scoped identically to
   create (US-2 AC4).

### US-4 — Establish the As-Is / To-Be plateau pair for the interface landscape

As an **Integration Architect**, I want a fixed pair of plateaus representing
the current and S/4HANA-integrated interface landscape, so every interface
gap has a consistent two-state comparison to be raised against.

**Acceptance Criteria**
1. For a given `TechnologyRoadmapInitiative`, the system provisions (once,
   idempotently — not duplicated on repeat visits) exactly two `Plateau`
   rows: `name='Current Integration Landscape'` (`sequence_order=1`) and
   `name='S/4HANA-Integrated Landscape'` (`sequence_order=2`,
   `baseline_plateau_id` = the first plateau's id).
2. Both plateaus are `TenantMixin`-scoped to the initiative's organisation.
3. A screen shows both plateaus side by side, or as clearly labelled
   As-Is / To-Be columns — never both totals under one unlabelled number
   (this is exactly the ambiguity `store-agreement` and the `gap_kind` split
   exist to prevent).
4. If the pair does not yet exist for an initiative, the screen offers an
   explicit "Set up As-Is/To-Be comparison" action rather than silently
   creating it on GET (GET must stay side-effect-free).

### US-5 — Raise an interface gap between As-Is and To-Be

As an **Integration Architect**, I want to record how each interface changes
between current and S/4HANA-integrated state — protocol change, new
interface, or retirement — so the programme has a traceable gap register
driving the work packages that close it.

**Acceptance Criteria**
1. From an interface in the register (US-1), the user can raise a `Gap` with
   `gap_kind='plateau_transition'`, `originating_plateau_id` = the As-Is
   plateau, `target_plateau_id` = the To-Be plateau (both from US-4), and
   `archimate_element_id`/`source_capability_*` or a comparable link back to
   the interface element being changed.
2. `gap_type` is set to one of three interface-specific values surfaced in
   the UI as a dropdown: `protocol_change`, `new_interface`, `retirement`
   (stored in the existing `gap_type` `String(30)` column — no schema
   change; see Assumption A2 for why these three literals and not a new
   enum table).
3. Submitting a gap with `gap_kind='plateau_transition'` and either plateau
   id missing is rejected client-side and server-side (the server side is
   already enforced by `validate_gap_kind()` — the UI must not attempt to
   swallow or re-interpret that `ValueError` as a success).
4. The gap appears against both the interface (via its element link) and
   the To-Be plateau's gap list, consistently, wherever either is displayed.
5. `TenantMixin` scoping applies identically to US-2 AC4.

### US-6 — WorkPackage costing rollup against the initiative budget

As a **Solution Architect** (and, for the £3m figure specifically, the
**Integration Architect** and **CTO/delivery lead** per root CLAUDE.md), I
want every `WorkPackage` attached to an interface `Gap` to roll up its
`estimated_cost` and `estimated_effort_hours` against the initiative's
`investment_budget`, with a derived T-shirt size shown per work package, so
the programme can see spend committed against the £3m at any time.

**Acceptance Criteria**
1. The register screen (or a dedicated costing tab) sums `estimated_cost`
   across every `WorkPackage` linked (via the `gap_work_packages` junction,
   i.e. `WorkPackage.gaps`) to a `Gap` that is itself linked to the
   initiative's To-Be plateau (US-4/US-5), and displays: total committed
   cost, `investment_budget` (£3m), and remaining headroom
   (`investment_budget - total committed cost`).
2. A `WorkPackage` with `estimated_cost IS NULL` is excluded from the sum,
   not treated as `0` — the running total is real only when every
   contributing row has a real figure (per the fabricated-data / null-display
   rule); the UI additionally shows a count of work packages still missing a
   cost estimate so the total's completeness is visible, not hidden.
3. Each `WorkPackage` row shows a derived T-shirt size band (S/M/L/XL)
   computed at display time from `estimated_effort_hours` per the bands in
   Assumption A4. A work package with `estimated_effort_hours IS NULL` shows
   `—` for size, never a default band.
4. If `total committed cost > investment_budget`, the screen shows a clear
   over-budget indicator (not just a number that happens to be bigger) —
   this is the concrete "does the failure reach the user as a
   [legible] state" check from the Integration Architect role in root
   CLAUDE.md.
5. `store-agreement`: this same total, computed identically, is what any
   dashboard card referencing "SAP S/4HANA programme cost" or similar shows
   — one query, reused, not two independent implementations of the same sum.
6. Creating/editing a `WorkPackage`'s `estimated_cost` or linking/unlinking
   it to a `Gap`, then reloading the rollup screen, changes the displayed
   total — proven by the browser walkthrough in the brief's Acceptance
   Criteria, not asserted from source.

### US-7 — Sidebar entry reachable by the relevant personas

As a **Solution Architect** or **Integration Architect**, I want the
Interface Register reachable from my sidebar, so I can find it without being
told the URL.

**Acceptance Criteria**
1. A new sidebar entry (label distinguishable from neighbouring entries per
   the Information/Content Architect roles — not a generic "Integrations"
   label that collides with the existing integrations admin section) appears
   for the `solution_architect` and `integration_architect` enterprise
   roles in `app/utils/role_access.py` / `components/admin_sidebar.html`.
2. `nav-coverage` and `sidebar-links` gates stay green (the new entry does
   not push any persona's sidebar over its link budget without an explicit,
   justified ratchet update).
3. `tests/smoke/test_authorisation_matrix.py` gains rows confirming
   `solution_architect` and `integration_architect` archetypes reach the
   route, and confirming at least one archetype that should **not** see the
   entry (e.g. `procurement`) does not.
4. `nav-verified` gate: the new sidebar route is exercised by a smoke test
   that actually loads it, not just declared.
5. A breadcrumb is present on every new page under this feature
   (`breadcrumb-coverage` gate), and does not duplicate an existing
   breadcrumb trail (`duplicate-breadcrumb` gate).

## 2. Assumptions made to resolve brief ambiguity (per CLAUDE.md "own the decision")

- **A1 — Initiative scoping is not itself tenant-mixed.**
  `TechnologyRoadmapInitiative` has no `organization_id` column. Rather than
  add one (a non-nullable-column risk, and out of this feature's declared
  scope of "no new bespoke schema"), initiative-level access is scoped
  through its linked `architecture_id` / `solution_id`, which are themselves
  reachable only within the user's tenant via the existing
  `ArchitectureModel`/`Solution` tenant scoping. The Solution/Integration
  Architect should confirm this indirect scoping is sufficient before
  build; flagged here as a design decision, not left as an open question,
  because the alternative (a schema change) is explicitly out of scope per
  the brief's constraints.
- **A2 — `gap_type` values for interface gaps are plain strings, not a new
  enum table.** `protocol_change`, `new_interface`, `retirement` are three
  literal values stored in the existing `gap_type` `String(30)` column,
  matching how `gap_type` already stores `coverage`/`quality`/`retirement`/
  `modernization`/`custom` for capability-shortfall gaps. No new lookup
  table — consistent with the brief's "no new top-level tables" constraint.
- **A3 — "Interface" in the brief means the ArchiMate `ApplicationInterface`
  element type**, with `ApplicationInterfaceMetadata` as its 1:1 extension,
  not a new domain object. **Corrected 15 Sep 2026** — an `ApplicationInterface`
  ORM class *does* exist (`app/models/application_layer.py:42`); this feature
  deliberately does not write it or rely on its `before_insert` listener, per
  `implementation-plan.md` §1.2, because the element-first
  `create_backbone_element()` path in `app/services/archimate_backbone.py` is
  the canonical creation path for this feature's motivation/interface
  elements. Confirmed by the brief's own file references and by
  `implementation-plan.md`'s arbitration of the two candidate paths.
- **A4 — T-shirt band thresholds** (not specified in the brief). Set as:
  S ≤ 40h, M 41–160h, L 161–400h, XL > 400h — chosen to roughly correspond to
  a person-week, person-month, and person-quarter of effort, appropriate for
  an 18-application/£3m programme. This is a display-only mapping (a pure
  function, not a stored value), so it can be re-tuned later without a
  migration. Documented here rather than left as an open question because
  it is a reversible, code-level constant.
- **A5 — Interface Register "list" scope** is per-initiative, not global,
  because the brief frames this as one S/4HANA programme; a global
  cross-initiative interface view is out of scope for this bucket.

## 3. Open Questions

None. All ambiguities identified while writing this SRS are resolved under
"Assumptions" above, per the instruction to make the call rather than defer
it.
