# Task 01 — Layer-scoped "Open in composer" from the dashboard overview

## Objective

Make the dashboard overview's per-layer "Open in composer" button open the
ArchiMate composer scoped to the layer tab the user was actually on, showing
that layer's real elements and the **same count the card promised**, instead of
always landing on the same bare unscoped canvas.

## Context

Founder-reported: Technology tab reads "32 elements", clicking "Open in
composer" lands on a blank "Unsaved diagram". Confirmed at
`app/templates/dashboards/overview.html:619` — a static
`href="/archimate/composer"` inside an otherwise fully `activeRole`-bound
Alpine block (lines 595-631). Same defect class as the sidebar link fixed
earlier tonight (PR #33, `8d4d3fee`), different set of links.

Read `docs/buckets/dashboard-composer-layer-links/00-verification-notes.md`
first — it corrects two claims in `brief.md` that will send you the wrong way
if you implement the brief literally:

1. **The brief says the dashboard's six layer keys match the `'layered'`
   viewpoint's `layer_order` exactly. They do not.** `layer_order` has seven
   entries including `physical`; the dashboard has six and folds
   Equipment/Facility/Material into `technology`.
2. **The brief floats a frontend-only fix using the existing `groups` dict.
   Rejected.** `groups` is indeed returned and indeed discarded by
   `selectViewpoint`, but the enterprise-wide query is `.limit(500)` with no
   ordering *before* grouping (`archimate_viewpoint_service.py:367`), so
   client-side filtering of that slice gives an arbitrary, unstable subset for
   any tenant past 500 elements. Filter server-side, before the cap.

The decisive finding: the card's "32" comes from
`app/modules/dashboard/v2/routes/dashboard_views.py:134-169`, which counts
`GROUP BY ArchiMateElement.type` mapped through a local `_LAYER_TYPES` dict.
It never reads the `ArchiMateElement.layer` column. That column
(`app/models/archimate_core.py:60`) is a nullable free-text `String(30)` with
no validator or normalizer anywhere. **Filter by type, using that same map, or
the composer will show a different number than the card promised.**

The `?viewpoint=` half of the plumbing already works end to end
(`composer_page` → `initial_viewpoint` → `__COMPOSER_CONFIG__.initialViewpoint`
→ `composer.js:2546` → `selectViewpoint`). You are adding a parallel `layer`
param alongside it, not building new plumbing.

## Constraints

- **Extends existing components only (ADR 0008). Name them, do not create
  siblings:** `app/services/archimate_viewpoint_service.py`
  (`get_viewpoint_data`), `app/modules/architecture/routes/archimate_routes.py`
  (`api_viewpoint_data`, `composer_page`),
  `app/templates/archimate/composer.html` (`__COMPOSER_CONFIG__`, ~line 2315),
  `app/static/js/archimate/composer_search.js` (`selectViewpoint`),
  `app/static/js/archimate/composer.js` (~line 2546),
  `app/templates/dashboards/overview.html` (line 619). **No new route, no new
  viewpoint id, no new service module.**
- **One system of record for the type→layer map.** `_LAYER_TYPES` currently
  lives inside `dashboard_views.py`. Lift it to a single shared definition
  (module-level in `archimate_viewpoint_service.py` is acceptable) and have the
  dashboard route import it. **Do not copy the dict.** A copy guarantees the
  card and the composer drift apart, which is the exact defect this task fixes.
  There is a third, differently-shaped map (`_ELEMENT_TYPE_LAYER` in
  `archimate_core.py`, for relationship validity) — leave it alone, do not add
  a fourth, and note the reconciliation as a follow-up in the build report.
- **`layer` is untrusted input.** Allowlist against the six keys
  (`motivation, strategy, business, application, technology, implementation`).
  Reject anything else with a 400 from the API route. An unknown value must
  **never** silently fall back to "no filter" — that renders all six layers
  under a link that promised one, which is the same lie in a new place.
- **The param is a strict no-op when absent.** Solution-scoped viewpoints and
  every non-`'layered'` viewpoint must behave byte-identically to today.
- **Do not restructure `selectViewpoint`.** It has five exit paths; four reset
  `viewpointDirty` and the fifth (`.catch`, line 148) adds no cells so cannot
  dirty the canvas. The D1 fix from tonight's earlier composer bucket lives at
  line 139 with an explanatory comment. Your change is confined to the URL
  construction at lines 46-47 plus a third function argument. Adding an early
  `return` anywhere in this function is out of bounds for this task.
- **Tenant isolation:** the filter is an extra `.filter()` on the existing
  `ArchiMateElement.query`, which is `TenantMixin`-scoped by
  `do_orm_execute`. Keep the D5 fail-closed `_current_org_id()` guard
  (`archimate_viewpoint_service.py:339-359`) ahead of it. No raw SQL, no
  hand-written `organization_id` predicate (that double-filters).
- Apply the layer filter **before** `.limit(500)`, not after.
- `Platform.fetch` only — no raw `fetch()`. No `console.*`. No inline `on*=`
  handlers (CSP strips them). Design tokens per `DESIGN.md`.

## Deliverable

1. `get_viewpoint_data(viewpoint_id, solution_id=None, layer=None)` — when
   `layer` is given, narrow the element query by the shared type→layer map on
   both the enterprise-wide and solution-scoped paths, ahead of the row cap.
   `groups`, `elements`, `relationships` and `total` in the response all
   reflect the narrowed set; existing Invariant 4 (no dangling relationships)
   continues to hold against the narrowed `filtered_ids`.
2. Shared `_LAYER_TYPES` / type→layer map with a single definition, imported by
   `dashboard_views.py` rather than duplicated.
3. `GET /archimate/viewpoints-api/<viewpoint_id>/data?layer=` — optional,
   allowlisted, passed through; 400 on an unknown value.
4. `GET /archimate/composer?viewpoint=layered&layer=` — optional, passed to the
   template as `initial_layer`; `composer.html` exposes `initialLayer` on
   `__COMPOSER_CONFIG__`; `composer.js:2546` reads it and passes it as
   `selectViewpoint`'s third argument; `selectViewpoint` appends it to the
   data-fetch URL (URL-encoded, and correctly `?` vs `&` given the existing
   conditional `solution_id` param).
5. `overview.html:619` becomes
   `:href="'/archimate/composer?viewpoint=layered&layer=' + activeRole"`.
6. Tests:
   - all six layer tabs' links carry the right `layer` value (template/DOM
     assertion);
   - a layer-filtered `'layered'` response contains only that layer's elements
     and no relationship with an endpoint outside it;
   - **count agreement**: for a seeded tenant, the filtered response's `total`
     for `technology` equals the dashboard route's
     `layer_breakdown['technology']` — including an equipment/facility/material
     row, to pin the physical-folds-into-technology behaviour;
   - regression: solution-scoped and non-`'layered'` viewpoints are identical
     with the param absent; an unknown `layer` is a 400, not a full render;
   - cross-tenant: org B's elements never appear in org A's layer-filtered
     response;
   - `viewpointDirty` is `false` after a layer-filtered load and no autosave
     POST fires.
7. Playwright smoke coverage in `tests/smoke/` (the `smoke-coverage-on-change`
   gate requires a `tests/smoke/` touch in the same diff as the template/JS
   change): click through each of the six layer tabs' buttons and assert the
   composer lands on that layer's elements, not a blank canvas.
8. Build report with before/after evidence, the count-agreement number, and the
   tenant-isolation and `viewpointDirty` checks explicitly confirmed.

## Acceptance Criteria

- Clicking "Open in composer" from any of the six layer tabs opens directly
  into that layer's real elements.
- The composer's element count equals the number the card showed for that tab
  (for tenants under the 500-row cap; state the cap's effect in the report if
  the test tenant exceeds it).
- Technology includes Equipment/Facility/Material, matching the card.
- No regression to any other viewpoint, solution-scoped or enterprise-wide.
- No cross-tenant leak.
- `viewpointDirty` false after a view-only layer-filtered load; no phantom
  `SavedDiagram` row.
- Exactly one type→layer map is imported by both the dashboard route and the
  viewpoint service.
- `python scripts/verify.py` green (bare, not `--tag static` — a tag subset is
  a `PARTIAL RUN` and cannot see `broken-surfaces` / `dynamic-link-prefixes`,
  both of which this change is in range of).

## Handoff Target

`builder`. Then `refuter` — with the count-agreement assertion and the
`viewpointDirty` exit-path review called out as the two things most likely to
be wrong.
