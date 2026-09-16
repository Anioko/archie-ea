# Task 04 — WorkPackage costing rollup, derived T-shirt band, over-budget state (US-6)

## Objective

One query that sums committed `WorkPackage` cost against the initiative's
`investment_budget`, reused by every surface that answers that question, with a
display-time size band and an honest account of what is missing from the total.

## Context

Extends:
- **`app/models/implementation_migration.py`** — `WorkPackage.estimated_cost`,
  `.estimated_effort_hours`, linked to `Gap` via the `gap_work_packages`
  secondary (`WorkPackage.gaps`); `TechnologyRoadmapInitiative.investment_budget`
  (line ~42) is the only `investment_budget` in the codebase.
- **`app/modules/interface_register/`** (Tasks 02–03).
- **`docs/adr/0011-derived-display-bands.md`** — the band is derived, never
  stored. Thresholds: S ≤ 40h, M 41–160h, L 161–400h, XL > 400h.
- Currency display: the existing `currency` filter
  (`app/template_helpers.py:33`) / `window.currencyManager.format()`.

## Constraints

- **Exactly one implementation of the sum.** `store-agreement` is satisfied
  structurally, not by discipline. Any dashboard card referencing S/4HANA
  programme cost imports this function; a second implementation is a defect
  even if it agrees today.
- **A `WorkPackage` with `estimated_cost IS NULL` is excluded from the sum and
  counted separately — never coerced to `0`.** A `0` meaning "not computed" is
  indistinguishable from a measured zero (`fabricated-data` gate).
- `investment_budget` may itself be NULL: then `headroom` is `None` (renders
  `—`) and `over_budget` is `None`, not `False`. Do not render committed cost
  as if it were headroom.
- The band is a **pure function**, not a column, not a cached value. NULL
  effort renders `—`, never a default band.
- ORM aggregate only — no raw SQL, so `raw-sql-tenancy` and `tenant-scoping`
  pass without an escape hatch. No hand-written `organization_id`.

## Deliverable

1. **`app/modules/interface_register/services/programme_rollup_service.py`**
   ```python
   def interface_programme_rollup(initiative_id) -> dict
   ```
   Returns at minimum:
   `committed_cost`, `investment_budget`, `headroom`,
   `work_packages_missing_cost` (int), `over_budget` (bool | None),
   `total_effort_hours`, and `work_packages` (the per-row list, each carrying
   its derived band).
   Query shape: `WorkPackage` joined through `gap_work_packages` to `Gap`,
   filtered to gaps whose `target_plateau_id` is the initiative's To-Be plateau
   (Task 03). All three models are `TenantMixin`, so no org predicate.
   Every rule above is baked into this function so no caller can get it wrong.
2. **`app/modules/interface_register/services/size_bands.py`**
   ```python
   def effort_band(estimated_effort_hours) -> str | None
   ```
   Pure; returns `None` for `None` or a negative value. Registered as a Jinja
   filter (`effort_band`) by the module's `register(app)`.
3. **`app/modules/interface_register/routes/costing_routes.py`** —
   `interface_register.costing` at `/costing`, GET, `@login_required`, same
   `data_integration` section guard. Side-effect-free.
4. **`app/modules/interface_register/templates/interface_register/costing.html`**
   `page_shell`, breadcrumb `[('Home', …), ('Interface Register', index), ('Costing', None)]`.
   Shows: total committed cost, `investment_budget`, headroom, and — visibly,
   not in a tooltip — the count of work packages still missing a cost estimate,
   so the total's completeness is legible. Over budget renders a **distinct
   indicator (badge plus text)**, not merely a red number; a user must not have
   to compare two figures to learn they are over. Per-row band via the
   `effort_band` filter; `—` via the `dash` filter for NULLs.
5. **Wire the existing surface, do not add a second one.** If any dashboard
   card already claims to show S/4HANA programme cost, repoint it at
   `interface_programme_rollup`. If none exists, add none — do not invent a card
   to prove the point.
6. **Tests**
   - `tests/test_interface_programme_rollup.py` (new, shared fixtures): a NULL
     `estimated_cost` work package is excluded and counted; a NULL
     `investment_budget` yields `headroom is None` and `over_budget is None`;
     `over_budget` is `True` when committed exceeds budget; a cross-org work
     package never contributes.
   - `tests/test_effort_bands.py` (new): boundary values 40/41/160/161/400/401,
     `None`, and a negative.
   - `tests/smoke/test_archetype_journeys.py` — extend: attach a costed work
     package to an interface gap, **reload** the costing screen, assert the
     displayed total changed. This is the US-6 AC6 acceptance criterion and it
     must be a clicked journey, not a source assertion.

## Acceptance Criteria

- `python scripts/verify.py` bare and green, `store-agreement` and
  `fabricated-data` included.
- `grep -rn "estimated_cost" app/modules/interface_register/` shows the sum
  computed in exactly one place.
- A browser run shows the over-budget indicator when the total is pushed past
  the budget, and `—` (not `0`) for a work package with no effort estimate.

## Handoff target

`builder` → Task 05.
