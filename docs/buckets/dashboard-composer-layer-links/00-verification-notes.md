# Verification Notes — dashboard-composer-layer-links

Tech-lead pass over the brief's recommended fix shape. Read against the
worktree `archie-oss-dashboard-composer-layer-links`
(branch `fix/dashboard-composer-layer-links`). Two of the brief's claims are
wrong and one of its open questions resolves against the "easy" answer.

---

## 1. The bug — CONFIRMED, exactly as reported

`app/templates/dashboards/overview.html:619`:

```html
<a href="/archimate/composer" class="inline-flex ...">
    Open in composer <i data-lucide="pen-tool" class="h-3.5 w-3.5"></i>
</a>
```

Static `href`, inside the `x-data` block at lines 595-631 that defines
`_layers` with exactly the six keys `motivation, strategy, business,
application, technology, implementation`. The heading (610), blurb (611) and
count (614) are all `activeRole`-bound; only this link is not. The sibling
`/architecture/dashboard` link (622) is equally unscoped but is out of this
bucket's scope (it is a "browse everything" affordance, not a per-layer one).

`composer_page` (`app/modules/architecture/routes/archimate_routes.py:1143-1174`)
already reads `viewpoint` from the query string and passes it as
`initial_viewpoint`; `composer.html:2319` exposes it as
`__COMPOSER_CONFIG__.initialViewpoint`; `composer.js:2546-2550` calls
`selectViewpoint(initialVp, initialVp)`. So the `?viewpoint=layered` half of
the link already works end to end today — only the `layer` half is missing.

## 2. Frontend-only fix — VIABLE-LOOKING BUT WRONG. Backend filtering is required.

The brief's open question (a) resolves as follows:

- `get_viewpoint_data` DOES return a `groups` dict
  (`archimate_viewpoint_service.py:496-513`), keyed by lowercased layer,
  built over `layer_order`.
- `selectViewpoint`'s success path
  (`app/static/js/archimate/composer_search.js:89-146`) reads **only**
  `data.elements` and `data.relationships`. `groups` is received and
  discarded entirely. Layout comes from `applyLayerBanding(self.graph)`
  (line 124) using each node's own `layer`, not from `groups`.
- Relationship pruning would be free client-side: line 118 already does
  `if (!srcCell || !tgtCell) return;`, so links whose endpoints are not on
  canvas are already silently skipped. The brief's worry about dangling
  relationships is not a reason to prefer the backend.

So a two-line client-side filter would *appear* to work. It is still the
wrong fix, for one decisive reason:

**The enterprise-wide query is capped at 500 rows before any grouping.**
`archimate_viewpoint_service.py:367` — `elements = query.limit(500).all()`,
with no `ORDER BY`. For any tenant past 500 ArchiMate elements, the flat
payload is an arbitrary database-order slice, and filtering that slice
client-side yields an arbitrary, unstable subset of the requested layer.
A backend `layer` filter applies *before* the cap, so the 500 budget is spent
on the layer actually being shown. This is a correctness difference, not an
efficiency one — it is the same "the control lies about what it does" class
as the bug being fixed.

Secondary: sending six layers' rows to hide five is wasteful, but that is not
what decides it.

**Decision: backend filter, threaded through the existing optional-param
path the brief describes. No new route.**

## 3. Layer-key mapping — the brief's claim is FALSE, and this is the load-bearing finding

The brief asserts the dashboard's six `activeRole` values "match the
`'layered'` viewpoint's `layer_order` list exactly, so no key-mapping table is
needed." They do not.

- `layer_order` (`archimate_viewpoint_service.py:52-53`) is **seven** entries:
  `['strategy', 'motivation', 'business', 'application', 'technology',
  'physical', 'implementation']`.
- The dashboard's `_layers` is **six** — no `physical`. Its own comment
  (`overview.html:131-133`, route side) states ArchiMate 3.2 folds Physical
  (Equipment/Facility/Material) into Technology.

So `layer=technology` filtered against `layer_order` semantics would drop
Equipment/Facility/Material, while the dashboard card counts them **inside**
technology. Six of six keys are string-equal; the seventh's absence is the
whole problem.

**How `.layer` is actually stored** — `app/models/archimate_core.py:60`:

```python
layer = db.Column(db.String(30), index=True)
```

Nullable, free text, 30 chars, **no validator, no normalizer, no enum, no
default** anywhere on the model. The service lowercases it only at
serialization time (`archimate_viewpoint_service.py:410`,
`'layer': (e.layer or '').lower()`), and `composer_search.js:108` falls back
to `guessLayer(el.type)` when it is blank — proof the frontend already treats
this column as unreliable. Grouping (line 500) is a raw `el['layer'] == layer`
string compare, so every NULL and every off-spelling silently lands in no
group at all.

**Therefore: do not filter on `ArchiMateElement.layer`.** Filter on
`ArchiMateElement.type`, using the same type→layer map the dashboard card
uses.

## 4. The "32 elements" count — this is where the fix would have silently lied

`layer_breakdown` is computed in
`app/modules/dashboard/v2/routes/dashboard_views.py:134-169`. It is a
`GROUP BY ArchiMateElement.type` count, mapped through a hardcoded
`_LAYER_TYPES` dict (lines 134-153) via `_type_to_layer`, keyed on
`(elem_type or "").lower()`. It **never reads the `layer` column**.

The card's "32" for Technology is therefore "count of rows whose *type* is one
of the 17 technology type names, including equipment/facility/material."
A `.layer`-based composer filter would answer a different question and show a
different number — exactly the count-disagreement defect class ADR 0008 and
the `store-agreement` gate exist for.

Type restriction stacking is not a risk here: `'layered'` declares
`'element_types': []` and `'allowed_relationships': []`
(`archimate_viewpoint_service.py:54, 58`), i.e. wildcard, so the layer filter
is the only narrowing applied. Tenant scoping is identical on both sides
(both go through `ArchiMateElement.query` / `db.session.query(ArchiMateElement)`
under the `TenantMixin` `do_orm_execute` listener).

The one genuine residual: the 500 cap can still truncate a layer with >500
elements. Below that, filtered composer count must equal card count exactly.

**Consequence for the build: `_LAYER_TYPES` must become ONE shared definition,
not a second copy.** Per ADR 0008 ("one accessor per concept"), lift it out of
`dashboard_views.py` into the viewpoint service (or a small shared module) and
have the dashboard route import it. Copy-pasting the dict into the service is
the failure mode this repo's own ADR names, and it would drift the first time
ArchiMate gains a type.

Note there is a *third* type→layer map already in the tree —
`_ELEMENT_TYPE_LAYER` in `archimate_core.py` (used at line 350 for
relationship validity). Reconciling all three is out of scope for this bucket
and is recorded as a follow-up; this bucket must not add a fourth.

## 5. viewpointDirty / autosave (D1) regression risk — contained, if the function is not restructured

`selectViewpoint` (`composer_search.js:34-157`) has five exit paths:

| Line | Exit | resets `viewpointDirty` |
|---|---|---|
| 63 | `scope_required` | yes |
| 80 | `data.error` | yes |
| 102 | zero elements | yes |
| 139 | success (the D1 fix, commented in place) | yes |
| 148 | `.catch` | no — but it adds no cells, so nothing marks dirty |

The planned change touches only lines 46-47 (URL construction) and the
function signature. It adds **no new exit path** and no new `graph.addCell`
call site, so the D1 invariant holds by construction.

The binding constraint for the builder: **do not refactor or re-order
`selectViewpoint`'s exit paths.** Append the layer param to `url` and add a
third argument; nothing else in this function.

Also note `composer.js:2541` performs the same reset after
`loadSavedViewpoint` on the `viewpoint_id` URL branch. That branch `return`s
before line 2546, so the `initialLayer` wiring cannot interfere with it.

## 6. Tenant isolation — preserved, and strictly narrowing

The enterprise-wide path already fails closed on a missing org
(`archimate_viewpoint_service.py:339-359`: explicit `_current_org_id()` check
with a `scope_required` return, added as D5 tonight), then relies on
`TenantMixin` for the predicate. The layer filter is an additional
`.filter(ArchiMateElement.type.in_(...))` on that same query object — it can
only ever return a subset of what is already returned. No raw SQL, no new
query path, no new route. `raw-sql-tenancy` and `tenant-scoping` gates are
unaffected.

The `layer` value arrives from a query string and so is untrusted: it must be
allowlisted against the six known keys and rejected with a 400 on anything
else, never interpolated. An unknown value must **not** silently degrade to
"no filter" — that would render all six layers under a link that promised one.

## 7. Scope call

One task file. The change is ~6 small edits across 5 files plus one dict move,
all additive and no-op when the param is absent. Splitting it would put the
backend filter and the link that exercises it in different reviews, which is
how a half-wired control ships.
