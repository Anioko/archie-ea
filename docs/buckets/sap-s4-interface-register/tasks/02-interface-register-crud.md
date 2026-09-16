# Task 02 — Interface Register module: list, create, edit/retire (US-1, US-2, US-3)

## Objective

Give `ApplicationInterfaceMetadata` its first producer: a working Interface
Register that lists, creates and edits interfaces as real ArchiMate elements,
scoped to a `TechnologyRoadmapInitiative`.

## Context

Extends:
- **`app/services/archimate_backbone.py::create_backbone_element`** (Task 01) —
  the only element-creation call in this feature.
- **`app/models/integration_metadata.py::ApplicationInterfaceMetadata`** and
  **`SystemDependency`** — existing stores, neither `TenantMixin`, gaining
  their first write path.
- **`app/models/archimate_core.py::ArchiMateRelationship`** — the backbone
  relationship table, the same one `archimate_routes.py:2605` already reads
  with lowercase `type` strings.
- **`app/_bootstrap/blueprints.py`** — `_register_optional_standalone`'s list
  (`tech_radar` at ~line 249 is the reference tuple).
- The existing read-only enrichment block at
  `app/modules/architecture/routes/archimate_routes.py:2627` stays untouched
  and must keep agreeing with the register (it is a second *reader*, fine).

New module `app/modules/interface_register/`, laid out per SDD §3.2, following
`app/modules/tech_radar/` verbatim.

## Constraints

- **Tenancy.** Every read roots at `ArchiMateElement` and joins outward:
  `db.session.query(ArchiMateElement).outerjoin(ApplicationInterfaceMetadata, ApplicationInterfaceMetadata.archimate_element_id == ArchiMateElement.id)`.
  Never `ApplicationInterfaceMetadata.query` as primary entity. No
  hand-written `organization_id=` predicate on any `TenantMixin` model. Use
  `.filter_by(id=...).first()`, never `.get()`. No raw SQL. No new
  `tenancy-ok` / `tenant-scoping-ok` marker — if you think you need one, stop
  and escalate to `tech-lead`.
- **Initiative resolution.** `initiative_id` is attacker-controlled. Resolve
  `TechnologyRoadmapInitiative` **through** its `architecture_id` →
  `ArchitectureModel` within the caller's tenant; an initiative that does not
  resolve, or whose `architecture_id IS NULL`, is a 404 — not "visible to
  everyone" (SDD §8.2).
- **One transaction** for the whole create (integration-spec §1.3). One
  `db.session.commit()` at the end, never four.
- Do not write `ApplicationInterface` (`app/models/application_layer.py`) rows.
- No new columns, no new tables, no `ArchiMateElement.custom_properties`
  shortcut for `protocol`/`interface_type` (integration-spec §1.1).
- `page_shell` macro (`app/templates/macros/page_shell.html`), not
  `components/page_header.html`. Exactly one `<h1>`, one breadcrumb trail.
- Null display via the existing `dash` filter
  (`app/utils/template_utils.py:121`) — never hand-written `or '—'`, never `0`.
- No `onclick=`, no `alert()`/`confirm()` (CSP strips inline handlers here —
  use `data-confirm`), `Platform.fetch` not raw `fetch`, no `console.*`.
- Entity fields for source/target `ApplicationComponent` use the documented
  debounced live-search picker (DESIGN.md), never free text.
- Read `DESIGN.md` before touching any template or CSS. If you add or change a
  Tailwind class, run `python scripts/build_css.py`.

## Deliverable

### Module skeleton

```
app/modules/interface_register/
  __init__.py                       # register(app) — idempotent, mirrors tech_radar
  routes/__init__.py                # exposes interface_register_bp
  routes/register_routes.py
  services/__init__.py
  services/interface_register_service.py
  templates/interface_register/index.html
  templates/interface_register/form.html
```

Registration: add
`("app.modules.interface_register.routes", "interface_register_bp", "/interface-register")`
to `_register_optional_standalone` in `app/_bootstrap/blueprints.py`, and add
`interface_register.index` to `REQUIRED_ENDPOINTS` in
`_validate_critical_endpoints()` (`app/__init__.py`). Confirm `/interface-register`
is unclaimed with `python scripts/verify.py --gate boot-health`, not by reading
files.

### Routes (`register_routes.py`), all `@login_required`

| Endpoint | Rule | Method | Story |
|---|---|---|---|
| `interface_register.index` | `/` | GET | US-1 — list; redirects to the initiative picker when `initiative_id` is absent, never guesses one |
| `interface_register.new` | `/new` | GET | US-2 — create form |
| `interface_register.create` | `/` | POST | US-2 |
| `interface_register.edit` | `/<int:element_id>/edit` | GET | US-3 |
| `interface_register.update` | `/<int:element_id>` | POST | US-3, incl. retire |

Route authorisation uses the **same predicate the sidebar uses** — the
`role_access` `data_integration` section check
(`app/utils/role_access.py`) — not a bespoke decorator and not an inline
`enterprise_role ==` comparison. A sidebar link that 403s is the F-01/F-11
defect family.

Write routes are CSRF-protected by the global extension; no opt-out.

### Service (`interface_register_service.py`)

```python
def list_interfaces(initiative_id) -> list          # element-rooted join, US-1
def create_interface(initiative_id, form_data)      # US-2, one transaction
def update_interface(element_id, form_data)         # US-3
```

`create_interface` sequence, one transaction, `commit()` once:

1. `create_backbone_element(element_type="ApplicationInterface", layer="Application", name=..., description=..., organization_id=g.current_org_id, provenance={"source_model": "InterfaceRegister", "initiative_id": initiative_id})` → flush → `element.id`.
2. `ApplicationInterfaceMetadata(archimate_element_id=element.id, **tech_fields)` — `interface_type`, `protocol`, `data_format`, `message_pattern`, `is_synchronous`, `authentication_method`, `business_criticality`, `transaction_volume_daily`, `operational_status`.
3. Two `SystemDependency` rows per integration-spec §1.3 steps 3–4, both with `interface_id=element.id`.
4. `ArchiMateRelationship` rows per integration-spec §4.1: `type="composition"` provider→interface; `type="serving"` interface→consumer; `type="realization"` interface→service **only if** a matching `ApplicationService` element already exists (never fabricate one).
5. `db.session.commit()`.

Validate before flush against explicit allow-lists: `business_criticality`, and
required fields `name` / `interface_type` / `protocol`. A picked
`ApplicationComponent` with no `archimate_element_id` is rejected with
"this application has no ArchiMate element yet" — never a `NULL`-sided
`SystemDependency` or `ArchiMateRelationship` row.

`update_interface` creates the metadata row on first edit if absent (US-3 AC1),
sets `retirement_date` (defaulting to today, editable) when
`operational_status='retired'`, and **deletes the stale
`ArchiMateRelationship` rows** matched on the `(source_id, target_id, type)`
triple before inserting the new pair when source/target change
(integration-spec §4.2) — no accumulation.

### Screens

- `index.html` — register list. Breadcrumb `[('Home', main.index), ('Interface Register', None)]`.
  Columns: name, `interface_type`, `protocol`, `message_pattern`, sync/async
  label, `business_criticality`, `transaction_volume_daily`,
  `operational_status`. An element with **no** metadata row still lists, every
  metadata cell `—` (US-1 AC3). Empty state: explicit "No interfaces registered
  for this initiative" with the create action inside it — use the empty-state
  macro the chosen base template's import context actually resolves to (two
  incompatible `empty_state` macros exist; the wrong one raises `TypeError` and
  500s the page), imported `with context` if it carries script. At narrow
  width the table collapses to a card list; name and `business_criticality`
  survive the collapse. Truncated names (>100 chars) show the full value via
  `title`, sourced from `custom_properties["source_name"]`.
- `form.html` — create and edit. Inline field errors, 4xx on rejection, never a
  500 and never a silently dropped field.

### Tests

- `tests/test_interface_register_service.py` (new, against the shared fixtures
  in `tests/conftest.py` — `db_session`, `make_org`, `tenant_ctx`; follow
  `tests/test_tenant_isolation.py`, do **not** copy the hand-rolled module-scoped
  pattern in `tests/test_business_case.py`): full create writes exactly one
  element + one metadata + two dependencies + two relationships; a bad component
  reference rolls the whole thing back leaving **zero** orphan elements; a
  cross-org read returns zero rows; edit replaces rather than accumulates
  relationships.
- `tests/smoke/test_archetype_journeys.py` — extend with a solution-architect
  create: fill the real form, submit, **reload**, assert the row persisted.
  (`smoke-coverage-on-change` requires a `tests/smoke/` touch in this diff.)

## Acceptance Criteria

- `python scripts/verify.py` bare and green, `boot-health` and `csrf-coverage`
  included.
- A Playwright run as the solution-architect archetype creates an interface,
  reloads, sees it in the list **and** on the element detail page at
  `archimate_routes.py:2627` with the same values — `store-agreement`.
- Every control on both screens does something (`dead-interactions`).
- `grep` shows no `organization_id` predicate on `ArchiMateElement`,
  `Plateau`, `Gap` or `WorkPackage` queries in the new module.

## Handoff target

`builder` → Task 03.
