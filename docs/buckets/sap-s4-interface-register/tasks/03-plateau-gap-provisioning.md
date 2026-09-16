# Task 03 — As-Is/To-Be plateau pair, interface gaps, and wiring `validate_gap_kind` (US-4, US-5)

## Objective

Provision the two-plateau comparison for an initiative, let an architect raise
an interface `Gap` between them, and make `validate_gap_kind()` — today a
validator with zero callers — actually enforce its invariant.

## Context

Extends:
- **`app/models/implementation_migration.py`** — `Plateau`, `Gap`,
  `validate_gap_kind` (line 550), `GAP_KIND_PLATEAU_TRANSITION` (line 547). All
  `TenantMixin`. The comment at lines 526–545 records that the product has
  never written a `plateau_transition` gap; this task writes the first ones.
- **`app/modules/interface_register/`** (Task 02) — new routes and services
  land inside it.

Confirmed by grep across the whole tree: `validate_gap_kind` appears only in
its own definition and in this bucket's markdown. It is not a `@validates`
decorator and no `before_insert`/`before_flush` listener registers it. The
SRS's claim that it is "already enforced in code today" is wrong; the
integration-spec §3.1 correction is right. See `implementation-plan.md` §3 for
why both the listener and the explicit call are being taken, not just one.

## Constraints

- **GET is side-effect-free.** The comparison screen never provisions on GET;
  provisioning is an explicit POST (US-4 AC4). The gap POST likewise never
  auto-provisions the pair — it rejects with "set up the As-Is/To-Be comparison
  first" (integration-spec §3.3).
- No new column. There is no `plateau_kind` and none is being added;
  idempotency comes from `(initiative linkage, name, sequence_order)` with the
  to-be plateau's `baseline_plateau_id` pointing at the as-is one, which is what
  makes the pair a pair (SDD §5.2).
- Tenancy rules from Task 02 apply unchanged: no hand-written
  `organization_id`, no `.get()`, no raw SQL, element-rooted joins.
- `gap_type` must be validated against the explicit allow-list before insert —
  the column has no DB constraint, so a typo would create a fourth
  `gap_type` the UI never shows.

## Deliverable

1. **`app/models/implementation_migration.py`** — register `validate_gap_kind`
   as a SQLAlchemy listener directly below the function:
   ```python
   @event.listens_for(Gap, "before_insert")
   @event.listens_for(Gap, "before_update")
   def _enforce_gap_kind(mapper, connection, target):
       validate_gap_kind(target)
   ```
   Zero behaviour change for existing data: the function returns at line 564
   unless `gap_kind == 'plateau_transition'`, and nothing in the tree writes
   that value today. Add a comment saying so, and why the listener exists (a
   validator with no producer is the same defect as a store with no producer).
2. **`app/modules/interface_register/services/plateau_pair_service.py`**
   ```python
   def get_plateau_pair(initiative_id) -> tuple | None   # read-only, no writes
   def provision_plateau_pair(initiative_id) -> tuple     # idempotent, POST-only
   ```
   `provision_plateau_pair` does SELECT-then-INSERT in one transaction and
   returns the existing pair unchanged on a repeat call. Creates
   `Plateau(name='Current Integration Landscape', sequence_order=1)` and
   `Plateau(name='S/4HANA-Integrated Landscape', sequence_order=2, baseline_plateau_id=<as-is id>)`.
   Both plateaus also get a backbone element via the existing
   `sync_archimate_element` (`Plateau` is already in `ELEMENT_TYPES`) — do not
   hand-roll one.
3. **`app/modules/interface_register/services/interface_gap_service.py`**
   ```python
   def raise_interface_gap(element_id, initiative_id, gap_type, **fields) -> Gap
   ```
   - `gap_kind = GAP_KIND_PLATEAU_TRANSITION` (import the constant, never the
     literal), `originating_plateau_id` = as-is, `target_plateau_id` = to-be.
   - `gap_type` ∈ `{'protocol_change', 'new_interface', 'retirement'}`,
     validated against a module-level allow-list; anything else is a 400.
   - `archimate_element_id = element.id` — the single FK column, **not** the
     `gap_archimate_elements` many-to-many junction (integration-spec §3.2).
   - Calls `validate_gap_kind(gap)` explicitly after constructing the object and
     before `db.session.add()`, so the `ValueError` message reaches the user as
     an inline form error and a 4xx. Do **not** catch-and-succeed, do **not**
     default the plateau ids on failure, do **not** rewrite the message into a
     generic "something went wrong" (`error-signalling`, `silent-data` gates).
4. **`app/modules/interface_register/routes/comparison_routes.py`**
   | Endpoint | Rule | Method | Story |
   |---|---|---|---|
   | `interface_register.comparison` | `/comparison` | GET | US-4 — as-is/to-be columns, side-effect-free |
   | `interface_register.provision_comparison` | `/comparison/provision` | POST | US-4 |
   | `interface_register.raise_gap` | `/<int:element_id>/gaps` | POST | US-5 |
   Same `data_integration` section guard as Task 02. CSRF on both POSTs.
5. **`app/modules/interface_register/templates/interface_register/comparison.html`**
   `page_shell`, breadcrumb `[('Home', …), ('Interface Register', index), ('As-is / To-be', None)]`.
   Two clearly labelled As-Is / To-Be columns — never both totals under one
   unlabelled number. Before provisioning: a single explicit "Set up As-is/To-be
   comparison" button, not two empty-but-labelled columns pretending to exist.
   Gap form uses a `gap_type` dropdown of exactly the three values.
6. **Tests**
   - `tests/test_gap_kind_enforcement.py` (new): a `plateau_transition` `Gap`
     missing either plateau id raises `ValueError` on flush via the listener;
     an existing-shape `capability_shortfall` gap inserts unaffected; a valid
     interface gap inserts.
   - `tests/test_interface_plateau_pair.py` (new): `provision_plateau_pair`
     called twice creates exactly two `Plateau` rows, and the second call
     returns the same ids.
   - `tests/smoke/test_archetype_journeys.py` — extend: provision the pair,
     raise a gap, reload, assert the gap shows against both the interface and
     the To-Be plateau's list.

## Acceptance Criteria

- `python scripts/verify.py` bare and green. `pytest tests/ -q` passes — in
  particular the existing gap/roadmap tests, which the new listener must not
  break. Run the gap-related test files **alone** as well as in the full suite
  (a full-run pass is evidence about one ordering only).
- Submitting the gap form with a plateau id missing shows the
  `validate_gap_kind` message inline with a 4xx — demonstrated in a browser,
  not asserted from source.
- A repeat POST to `/comparison/provision` adds no rows.
- `grep -rn "plateau_transition" app/` shows the constant imported, not the
  string literal, in the new code.

## Handoff target

`builder` → Task 04.
