# Task Brief: Dashboard Per-Layer "Open in Composer" Buttons Don't Open the Right Layer

## Objective
Fix the "Open in composer" button on the dashboard overview's Architect tab
(Motivation/Strategy/Business/Application/Technology/Implementation & Migration
layer sub-tabs) so it opens the composer scoped to the ACTIVE layer, showing
that layer's real elements — instead of always landing on the same bare,
unscoped composer URL regardless of which layer tab was open.

## Context
Founder-reported tonight (screenshot: Technology layer tab showing "32
elements", clicking "Open in composer" from that tab). Verified in source:
`app/templates/dashboards/overview.html:619` — inside the Alpine
`x-data="{_layers: {...}}"` block (lines 595-631) that drives the six
ArchiMate-layer sub-tabs (`activeRole`: motivation, strategy, business,
application, technology, implementation) — the button is a **static,
hardcoded link**:

```html
<a href="/archimate/composer" ...>Open in composer</a>
```

This ignores `activeRole` entirely. Every layer tab's button points at the
exact same bare URL, landing on a blank "Unsaved diagram" canvas every time
— this is the same defect CLASS fixed earlier tonight for the sidebar's
"ArchiMate Composer" link (`docs/buckets/composer-opens-layered-viewpoint/`,
merged as PR #33, `8d4d3fee`), but it is a SEPARATE, additional set of links
that fix did not touch.

There is a second layer to this, beyond just fixing the href: even a
correctly-parameterized link needs the backend to support filtering to ONE
layer's elements. Today:
- `app/services/archimate_viewpoint_service.py`'s `'layered'` viewpoint
  (fixed tonight to be enterprise-wide, no `solution_id` required) shows
  ALL layers grouped together, not one layer alone.
- The individual per-layer viewpoints that exist (`'technology'`,
  `'motivation'`, `'strategy'`, `'business_process'`,
  `'application_cooperation'`, `'migration'`, etc.) each still require a
  `solution_id` and are not a clean 1:1 match to the dashboard's six layer
  keys — some layers (business, application, implementation) have no
  single matching viewpoint id that means "all elements in this layer,
  enterprise-wide."

**Recommended fix shape** (tech-lead should confirm/correct, not just
implement blindly): extend the ALREADY-ENTERPRISE-WIDE `'layered'`
viewpoint mechanism with an optional `layer` filter, rather than inventing
six new per-layer enterprise-wide viewpoints. Concretely:
- `get_viewpoint_data(viewpoint_id, solution_id=None, layer=None)` in
  `archimate_viewpoint_service.py` — when `layer` is given, filter the
  returned `elements`/`relationships` (and the `groups` dict) down to just
  that one layer, after the existing type/relationship filtering. This
  should work for both the enterprise-wide code path (no `solution_id`)
  and the solution-scoped path, since the dashboard use case is
  enterprise-wide but the parameter should be generally correct.
- `GET /archimate/viewpoints-api/<viewpoint_id>/data` (route:
  `api_viewpoint_data` in `app/modules/architecture/routes/archimate_routes.py`)
  — accept an optional `layer` query param, pass through.
- `GET /archimate/composer` (route: `composer_page`, same file) — accept an
  optional `layer` query param alongside the existing `viewpoint` param,
  pass through to the template as `initial_layer`.
- `app/templates/archimate/composer.html`'s `window.__COMPOSER_CONFIG__`
  — add `initialLayer: {{ initial_layer|tojson }}` alongside the existing
  `initialViewpoint`.
- `app/static/js/archimate/composer_search.js`'s `selectViewpoint` — accept
  an optional layer argument, append `&layer=` to the viewpoint-data fetch
  URL when present.
- `app/static/js/archimate/composer.js`'s page-load wiring (~line 2546,
  where `initialVp` is read from `window.__COMPOSER_CONFIG__` and
  `selectViewpoint` is called) — also read `initialLayer` and pass it
  through.
- `app/templates/dashboards/overview.html:619` — replace the static href
  with an Alpine-bound dynamic one:
  `:href="'/archimate/composer?viewpoint=layered&layer=' + activeRole"`.
  The dashboard's `activeRole` values (`motivation, strategy, business,
  application, technology, implementation`) match the `'layered'`
  viewpoint's `layer_order` list exactly
  (`['strategy', 'motivation', 'business', 'application', 'technology',
  'physical', 'implementation']`), so no key-mapping table is needed —
  verify this claim, don't just trust it.

**Verify all of the above against current code before building** — this
brief was written from a source read tonight, not independently re-derived
by a tech-lead. In particular, verify: (a) whether `'layered'`'s existing
`'groups'` dict (already grouped by layer) could be used directly by the
frontend instead of needing new backend filtering — i.e., could this be a
FRONTEND-only fix (just render `groups[layer]` instead of all groups) if
the composer's rendering code already receives the full grouped payload?
Check `composer_search.js`'s `selectViewpoint` success path to see whether
it currently discards `groups` in favor of a flat `elements` array, and
which approach is less invasive. (b) whether the elements count shown on
the dashboard card ("32 elements" for Technology) is computed the same way
the fix's filtered composer view would compute it — if they use different
counting logic, the fix could show a different count than the card
promised, which is its own version of the same "control lies about what it
does" defect this bug report is about.

## Constraints
- **Do not regress tonight's already-shipped composer fix.** The
  `'layered'`/`'basic'` `enterprise_scope` opt-in, the cross-tenant
  isolation, and the `viewpointDirty`/autosave fix (D1 from tonight's
  earlier bucket — loading a viewpoint for VIEWING must never mark the
  diagram dirty or trigger a phantom autosave) all apply equally to this
  layer-filtered case. Any new code path through `selectViewpoint` must
  reset `viewpointDirty`/`UndoStack` correctly on every exit path, matching
  the pattern already fixed tonight.
- No new REST route beyond the described additive param on the existing
  ones. This is a targeted fix to an existing mechanism.
- Tenant isolation: the layer filter must not bypass or weaken the
  existing tenant-scoping on the enterprise-wide query path.
- Every other viewpoint's behavior (solution-scoped, individual
  non-'layered' viewpoints) must be completely unaffected by adding the
  optional `layer` param — it should be a no-op when absent.

## Deliverable
1. The layer-filter mechanism (backend and/or frontend, per the
   tech-lead's determination of which is the less invasive correct fix),
   wired end-to-end from the dashboard button through to a correctly
   layer-scoped composer view.
2. The dashboard button's href genuinely reflects the active layer tab.
3. Real tests: a test proving each of the six dashboard layer tabs' "Open
   in composer" link carries the correct layer param; a test proving the
   layer-filtered viewpoint response contains ONLY that layer's elements/
   relationships; a regression test confirming solution-scoped and other
   non-'layered' viewpoints are unaffected by the new optional param; a
   test confirming `viewpointDirty`/autosave behavior is correct on this
   new code path (no phantom save from loading a layer-filtered view).
4. A live browser check (Playwright, matching tonight's established
   pattern) against a real environment: click each layer tab's "Open in
   composer" button, confirm it lands on that layer's real elements, not a
   blank canvas or the wrong layer's elements.
5. Build report with before/after evidence and the tenant-isolation/
   viewpointDirty regression checks explicitly confirmed.

## Acceptance Criteria
- Clicking "Open in composer" from any of the six layer tabs opens
  directly into that layer's real elements, matching the count shown on
  the dashboard card for that tab.
- No regression to any other viewpoint's behavior (solution-scoped or
  enterprise-wide, layer-filtered or not).
- No cross-tenant data leak.
- No phantom autosave / no `viewpointDirty` left `true` after loading a
  layer-filtered view for viewing only.
- `python scripts/verify.py --tag static` clean.

## Handoff Target
`tech-lead` — verify the recommended fix shape above against current code
(especially whether a frontend-only fix using the existing `groups` dict is
viable and less invasive than backend filtering), correct anything wrong,
and decompose into a task file for `builder`. Given this is a small,
contained fix (not a new feature), a single task file is likely sufficient
unless the tech-lead finds real complexity. Route to `builder`, then
`refuter` — treat with the same rigor as every other composer-touching
bucket tonight, since this shares code paths (viewpointDirty, autosave,
tenant isolation) with defects found and fixed there.
