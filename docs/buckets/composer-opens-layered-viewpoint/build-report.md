# Build report — composer-opens-layered-viewpoint

## Summary

The brief described three changes as "already made, uncommitted": edits to
`app/config/navigation_registry_v2.py`, `app/config/navigation_sections_v2.py`,
and `app/services/archimate_viewpoint_service.py`. Re-verifying them against
the actual rendered application surfaced a critical gap the brief's summary
missed: **`navigation_registry_v2.py`/`navigation_sections_v2.py` is dead
code.** Nothing in `app/_bootstrap/` or any Jinja template imports
`NavigationRegistryV2`, `get_navigation_sections`, or
`navigation_sections_v2` (`grep -rln 'get_navigation_sections\|NavigationRegistryV2'
app/templates/` returns nothing). The sidebar the founder actually clicked is
rendered by `app/utils/role_access.py::get_sidebar_zones()` /
`_link()` and `app/templates/components/admin_sidebar.html`'s
`{{ url_for(link.endpoint) }}` — a completely separate mechanism with no
`query_params` support at all. Had the bucket shipped only the "already made"
diff, the sidebar link would still have opened the blank canvas; the fix
would have been invisible in the browser while looking complete in source.

This build:
1. Kept the three "already made" changes (they're harmless and the backend
   `enterprise_scope` change in `archimate_viewpoint_service.py` is correct
   and load-bearing).
2. Added the same `query_params` mechanism to the REAL sidebar
   (`app/utils/role_access.py::_link()` gained an optional `query_params`
   dict; `app/templates/components/admin_sidebar.html` and
   `app/templates/dashboards/overview.html` — the only two templates that
   render `url_for(link.endpoint)` off `get_sidebar_zones()` — now call
   `url_for(link.endpoint, **(link.query_params or {}))`), and set
   `query_params={"viewpoint": "layered"}` on the "ArchiMate Composer" link.
3. Fixed two more pre-existing defects in the dead `navigation_registry_v2.py`
   module, only because they blocked even *importing* the file the brief's
   own diff touched (see "Pre-existing defects found" below).
4. Wrote the tests the brief's Deliverable section asked for, plus one that
   directly asserts against the real sidebar HTML rather than the dead
   registry.
5. Verified in a real headless browser against a local dev server running
   this worktree's code (not production — production doesn't have this fix
   deployed, and this bucket is explicitly not being deployed this session).

## Files touched

- `app/config/navigation_registry_v2.py` — kept the brief's `query_params`
  plumbing; also fixed two unrelated pre-existing bugs that blocked the
  module from importing at all in this environment (see below).
- `app/config/navigation_sections_v2.py` — kept the brief's
  `query_params={"viewpoint": "layered"}` on the composer item, unchanged.
- `app/services/archimate_viewpoint_service.py` — kept the brief's
  `enterprise_scope` opt-in flag and backend branch, unchanged; re-verified
  by direct reading and by the new tenant-isolation tests below.
- `app/utils/role_access.py` — **new work this session**: `_link()` gained
  `query_params`; the composer `_link` call now sets
  `query_params={"viewpoint": "layered"}`. This is the change that actually
  fixes the founder-reported bug in the live application.
- `app/templates/components/admin_sidebar.html`,
  `app/templates/dashboards/overview.html` — **new work this session**: both
  places that render `url_for(link.endpoint)` off `get_sidebar_zones()` now
  pass through `link.query_params`.
- `tests/test_composer_layered_viewpoint.py` — new, six tests (below).
- `tests/smoke/test_composer_opens_layered_viewpoint.py` — new Playwright
  smoke test (below), added to satisfy the `smoke-coverage-on-change` gate
  and to have a persistent, CI-run browser check beyond this session's manual
  verification.

## Pre-existing defects found and fixed (not part of the brief's scope, but
blocking)

While re-verifying the brief's "already made" diff, `app/config/
navigation_registry_v2.py`/`navigation_sections_v2.py` turned out not to even
*import* successfully in this environment, on code paths entirely untouched
by the brief's diff:

1. `NavigationSectionV2` used pydantic v1's `regex=` kwarg (`key`, `icon`
   fields), which pydantic 2.11+ removed outright
   (`PydanticUserError: 'regex' is removed. use 'pattern' instead`). Fixed:
   `regex=` → `pattern=` (two lines).
2. `NavigationItemV2.endpoint_and_fallback_not_both_invalid()` did not
   special-case `disabled` items the way the sibling `icon` validator does,
   so the "Framework Extensions" disabled placeholder header
   (`endpoint=None, url_fallback="#", disabled=True`) failed validation at
   **module import time**, taking the whole module down. Fixed the validator
   to skip disabled items, and reordered the `disabled` field ahead of
   `endpoint` in the class body (pydantic v1-style validators only see
   fields validated so far, in declaration order, not kwarg order — the
   validator needs `disabled` present in `values` regardless of how the
   caller ordered its kwargs).
3. A third bug was found but **not fixed**, left as a known-issue instead:
   `NavigationRegistryV2._is_visible()` reads `config.disabled`, but
   `NavigationSectionV2` (unlike `NavigationItemV2`) declares no `disabled`
   field, so `get_navigation_sections()` raises `AttributeError` on any real
   call. Not fixed because the module is confirmed dead code (see Summary) —
   fixing every bug in code nothing renders is scope creep this bucket did
   not ask for. The two bugs above were fixed only because they blocked
   importing the file the brief's own diff modified.

Recommendation for a follow-up bucket: either wire `navigation_registry_v2.py`
into the real sidebar (retiring `role_access.py`'s hand-rolled `_link()`
system per ADR 0008's "one system of record" rule — right now there are
literally two independent sidebar-construction mechanisms, one of them fully
dead and buggy), or delete the dead module outright. Recording this rather
than fixing it now because it is a genuine architectural decision (which
system survives) outside this bucket's scope, not a one-line fix.

## Tests written

`tests/test_composer_layered_viewpoint.py` (6 tests, all passing):

1. `test_composer_sidebar_link_carries_viewpoint_query_param` — logs in as a
   real user, hits `/dashboard/overview`, and asserts the rendered HTML's
   anchor has `href="/archimate/composer?viewpoint=layered"`. This is the
   test that actually matters: it exercises the real, live sidebar mechanism
   the founder clicked, not the dead registry.
2. `test_composer_nav_link_resolves_to_layered_viewpoint` — exercises
   `NavigationRegistryV2._resolve_url()` directly (the brief's originally
   requested test), kept for completeness even though this code path is
   currently unreached by the app.
3. `test_layered_viewpoint_returns_elements_without_solution_id` —
   `get_viewpoint_data('layered', solution_id=None)` returns real elements
   for the calling tenant, not `scope_required: True`.
4. `test_basic_viewpoint_also_enterprise_scoped` — same for `'basic'`, the
   other viewpoint the brief's diff flagged `enterprise_scope`.
5. `test_layered_viewpoint_cross_tenant_isolation` — **the highest-priority
   test.** Creates 5 elements in org B and 1 in org A, calls
   `get_viewpoint_data('layered', solution_id=None)` as org A, asserts org
   B's element ids never appear in the result — and the symmetric check the
   other way. Follows the exact pattern of
   `tests/test_archimate_relationship_health_tenancy.py`
   (`make_org`/`tenant_ctx`/`db_session`, elements written outside any
   `tenant_ctx` with `organization_id` set explicitly).
6. `test_solution_scoped_viewpoint_still_requires_solution_id` — confirms
   `'stakeholder'` (verified by reading `STANDARD_VIEWPOINTS`: only
   `'basic'` and `'layered'` carry `enterprise_scope`) still returns
   `scope_required: True` with no `solution_id` — the opt-in flag did not
   leak into other viewpoints.

```
tests/test_composer_layered_viewpoint.py::test_composer_sidebar_link_carries_viewpoint_query_param PASSED
tests/test_composer_layered_viewpoint.py::test_composer_nav_link_resolves_to_layered_viewpoint PASSED
tests/test_composer_layered_viewpoint.py::test_layered_viewpoint_returns_elements_without_solution_id PASSED
tests/test_composer_layered_viewpoint.py::test_basic_viewpoint_also_enterprise_scoped PASSED
tests/test_composer_layered_viewpoint.py::test_layered_viewpoint_cross_tenant_isolation PASSED
tests/test_composer_layered_viewpoint.py::test_solution_scoped_viewpoint_still_requires_solution_id PASSED
6 passed
```

Regression check — no existing nav/sidebar/viewpoint test broke:
```
tests/test_composer_layered_viewpoint.py tests/test_sidebar_render.py
tests/test_sidebar_budgets.py tests/test_sidebar_role_filtering.py
tests/test_nav_permission_driven.py tests/test_navigation_route_coverage.py
tests/test_archimate_layer_nav.py tests/test_viewpoint_diagram_search_scope.py
110 passed, 0 failed
```

`tests/smoke/test_composer_opens_layered_viewpoint.py` — Playwright, seeds 3
real `ArchiMateElement` rows for the `enterprise_architect` persona's org,
clicks the real sidebar link, confirms the URL carries `viewpoint=layered`,
and asserts the seeded element names are visible in the rendered composer
(not the blank-canvas or scope_required text). Run locally:
```
tests/smoke/test_composer_opens_layered_viewpoint.py::test_composer_sidebar_link_opens_layered_viewpoint_with_elements PASSED
1 passed in 101.52s
```

## Tenant isolation — the highest-stakes question

Confirmed by direct reading (unchanged from the brief's own diff) and now
proven by test 5 above: the enterprise-wide path in `get_viewpoint_data`
queries `ArchiMateElement.query` with **no manual `organization_id`
predicate**, relying entirely on `TenantMixin`'s `do_orm_execute` listener
(`app/middleware/tenant_isolation.py`) to inject the
`WHERE organization_id = g.current_org_id` filter. This is the correct
pattern per `CLAUDE.md`'s tenancy section — a manual predicate here would be
redundant, not defensive, since this executes inside a request context with
`g.current_org_id` already set. `test_layered_viewpoint_cross_tenant_isolation`
proves org A's call never returns org B's rows, symmetrically in both
directions.

## The 500-row truncation question

**Decision: leave as a documented follow-up, do not implement a disclosure
mechanism in this bucket.**

Reasoning: the founder's reported dataset (444 elements, 159 relationships)
is comfortably under the `.limit(500)` cap already used elsewhere in this
function, so today's fix does not truncate anything for the reported tenant.
A genuinely larger tenant (500+ ArchiMate elements) *would* silently
truncate — `get_viewpoint_data` returns no `total_elements`/`showing_count`
distinction, and the frontend has no way to know it received a partial set.
This repo has an established pattern for exactly this disclosure (`ARC-003`,
`app/templates/architecture/elements.html:384-389`: `'Showing ' + start + '–'
+ end + ' of ' + totalCount + ' elements'`, backed by a `total_elements` key
in the JSON payload at `app/templates/architecture/elements.html:720`).

Not implementing it now because: (a) it is a distinct concern from the
reported bug — the reported bug is "opens a blank canvas", not "silently
truncates a large tenant" — and conflating the two risks under-testing both
in one already tenant-isolation-sensitive change; (b) it would touch the
`get_viewpoint_data` response shape, which the composer's Alpine.js consumer
(`composer_search.js`) would also need updating to actually surface, growing
this bucket's blast radius beyond what the brief scoped; (c) no tenant in
this dataset is currently near the cap. Recommended follow-up: add
`total_elements` (an unbounded `.count()` alongside the existing
`.limit(500)` query) and `showing_count` to `get_viewpoint_data`'s enterprise-
wide branch, and reuse the ARC-003 "Showing N of M" pattern in
`composer.html`'s status bar when `total_elements > showing_count`.

## The composer.html:662 badge

**Not touched, and confirmed the fix does not need to touch it.** Read
`app/static/js/archimate/composer_search.js:59-71`: `scopeFallback` (the flag
gating the "No ArchiMate elements linked for this viewpoint. Showing
enterprise-wide elements." banner) is set `true` only in two places — when
`data.scope_required` is true (the early-return branch), or when
`self.solutionId && data.scope === 'enterprise'` (a solution *was* selected
but the API fell back to enterprise scope; `get_viewpoint_data` does not
currently return a `scope` key at all, so this second branch can never fire
today regardless of this fix). The composer nav link opens with no
`solution_id`, so `self.solutionId` is falsy. Before this fix: `scope_required`
was `true` for `'layered'` with no `solution_id`, so `scopeFallback` became
`true` and the contradictory banner showed *alongside* the "Select a solution"
message. After this fix: `scope_required` is no longer `true` for `'layered'`
with no `solution_id`, so neither branch fires and `scopeFallback` stays
`false` — the banner does not render at all in this flow. The brief's
predicted "accidental correctness" doesn't quite apply: the fix doesn't make
the badge's wording correct, it makes the badge not appear at all for this
flow, which resolves the specific contradiction reported. The underlying
question of whether `scopeFallback`'s own two trigger conditions are well-
named/well-designed (conflating "no scope required at all" with "solution
selected but backend fell back to enterprise scope") is left untouched per
the brief's constraint — no fix was needed here beyond what this bucket
already shipped, since the observed symptom is gone.

## Browser verification

Local dev server (this worktree's code) on `127.0.0.1:5052`, `flask_app`
Postgres database, seeded a demo org/user (`composer-demo@example.com`) with
5 `ArchiMateElement` rows across 4 layers via a one-off seed script (not
committed — scratch tooling only). Logged in with Playwright (headless
Chromium), navigated to `/dashboard/overview`, confirmed the sidebar's
`ArchiMate Composer` anchor's `href` is
`/archimate/composer?viewpoint=layered`, clicked it, and screenshotted the
result:

`docs/buckets/composer-opens-layered-viewpoint/browser-check-composer-layered.png`

The screenshot shows the composer landed directly on the **Layered**
viewpoint (toolbar reads "Layered"), status bar reads **"Layered — 5
elements, 0 relationships"** (all 5 seeded elements, matching the org's true
count), elements are grouped into layer bands visible in the minimap
(Motivation/purple, Business/yellow, Application/cyan, Technology/green) —
not a blank "Unsaved diagram" canvas, not a "Select a solution to view this
viewpoint" prompt. No console errors were captured during the run.

Production was **not** used for this verification, deliberately: production
does not have this session's fix deployed (the brief's "already-made" diff
alone, still on `origin/main`, does not fix the live sidebar — see Summary),
and verifying against unfixed production would have proven nothing about
this fix. Per this bucket's explicit instruction, no deploy happened this
session.

## Verification run

```
python scripts/verify.py --tag static
48 passed, 0 failed, 1 skipped (css-build — no vendored Tailwind CLI locally, CI covers it)
[exited with code 0]
```

## Round 2 — refuter defects fixed (D1–D7)

An independent refuter reviewed the round-1 diff and confirmed the core fix
correct, but found 7 real defects, several blocking. All 7 are fixed in this
round.

### D1 (BLOCKER) — viewing the layered viewpoint wrote a new SavedDiagram row

`selectViewpoint` (`app/static/js/archimate/composer_search.js`) rendered
every loaded element/relationship via `self.graph.addCell(...)`, and
`composer.js`'s `graph.on('add', ...)` listener set `viewpointDirty = true`
for each one, but `selectViewpoint` never reset it back to `false` after a
successful load — unlike `composer.js:2541`'s `loadSavedViewpoint()` path,
which does. Result: opening the composer via the sidebar link marked the
canvas dirty purely from viewing it, and the 30s `_autoSave()` timer would
then call `_autoCreateSavedDiagram()`, writing a new DB row for a user who
only looked.

**Fix:** `self.viewpointDirty = false` added to all three exit paths of
`selectViewpoint` — the `scope_required` early return, the
`elements.length === 0` early return, and the main success path — mirroring
`composer.js:2541`'s reset.

**Evidence — browser walkthrough against this worktree's code, real
Postgres, real login:**

```
HREF: /archimate/composer?viewpoint=layered
HAS 'Unsaved': False
Unsaved changes -> False
Layered -> True
elements, -> True
relationships -> True
AFTER 32s, HAS 'Unsaved': False
EXIT:0
```

Screenshot taken immediately after load, confirming the status bar reads
**"Ready"** — not "Unsaved changes":
`docs/buckets/composer-opens-layered-viewpoint/round2-d1-no-unsaved.png`

Database check, before and after the full walkthrough including the 30s+
autosave window:

```
org 2
count 0
```

Zero `SavedDiagram` rows exist for the demo org after opening the composer,
watching it render, and waiting past the autosave timer — confirms no
write happened from view-only access.

### D2 (BLOCKER) — undo/redo permanently broken for empty-tenant landings

`UndoStack.pause()` was called at the top of `selectViewpoint`, but the
`elements.length === 0` early-return branch returned without calling
`UndoStack.resume()` — unlike the `scope_required` branch just above it,
which already did. `UndoStack.pause`/`resume` is a plain boolean flag, not
refcounted, so this permanently disabled undo/redo for the rest of the
session on any brand-new/empty tenant's first composer visit.

**Fix:** added `UndoStack.resume()` (and `UndoStack.clear()` for
consistency with the other two branches) to the `elements.length === 0`
early return in `composer_search.js`.

**Test:** covered indirectly — `test_layered_viewpoint_with_no_org_context_returns_scope_required`
and the existing scope_required test exercise the backend side; the JS fix
itself mirrors the already-correct `scope_required` branch pattern exactly,
so no new JS test harness was introduced for this bucket (this repo has no
JS unit test runner — `js-syntax`/`js-build` gates cover parse-level
regressions only).

### D3 (MAJOR) — /modules directory page still had the original bug

`app/modules/modules_directory/routes.py`'s `_resolve()` re-used the same
`SIDEBAR_ZONES` link data as the real sidebar, but built
`url_for(link["endpoint"])` with no `query_params`, so the ArchiMate
Composer link on the "All modules" directory page still opened the bare
blank-canvas URL — a second live door onto the founder's original bug.

**Fix:** `url_for(link["endpoint"], **(link.get("query_params") or {}))`.

**Test:** `test_modules_directory_composer_link_carries_viewpoint_query_param`
in `tests/test_modules_directory.py` — logs in, hits `/modules`, and asserts
the rendered composer link's href carries `?viewpoint=layered`. Passing
(see Verification below).

### D4 (MAJOR) — backend exception fabricated an empty-but-200 result

`archimate_viewpoint_service.py`'s `except Exception: serialised = []`
returned a 200 with `elements: []`, `total: 0`, no error flag — on ANY
failure, indistinguishable from a genuinely empty model. Also
`relationships_out` was not reset in that handler, so a mid-loop failure
could return `elements: []` alongside a non-empty `relationships` list,
violating the function's own Invariant 4.

**Fix:** the except handler now logs the real exception, resets both
`serialised` and `relationships_out`, and returns an explicit
`error: True, error_reason: "..."` response distinct from the legitimate
`scope_required`/empty-model cases. `composer_search.js`'s `selectViewpoint`
now checks `data.error` before the empty-elements branch and renders a
visible error state (`_toast('error', ...)` + status bar text), rather than
silently showing "No elements for this viewpoint."

**Test:** `test_layered_viewpoint_backend_failure_returns_explicit_error_not_fabricated_empty`
— monkeypatches `ArchiMateElement.query` to raise, asserts `result["error"]
is True` and both `elements`/`relationships` are empty. Passing.

### D5 (MEDIUM) — enterprise-wide path unsafe-by-default with no org context

The enterprise-wide query (`ArchiMateElement.query.limit(500).all()` when
`solution_id` is `None` and `enterprise_scope=True`) relied entirely on the
`do_orm_execute` tenant-isolation listener, which is a documented NO-OP (not
a deny) when `g.current_org_id` is unset. The round-1 fix flipped this path
from safe-by-default (no org → `scope_required`, zero rows) to
unsafe-by-default (no org → every org's rows), as a structural property, even
though today's only caller (`@login_required`, `organization_id` NOT NULL)
never actually hits it that way.

**Fix:** added an explicit guard — if `current_org_id()` (from
`app.middleware.tenant_context`) is falsy, the enterprise-wide branch now
returns `scope_required: True` (fail closed) instead of running the
unscoped query.

**Test:** `test_layered_viewpoint_with_no_org_context_returns_scope_required`
— seeds an element in org A, calls `get_viewpoint_data("layered", None)`
inside a bare `app.test_request_context("/")` with `g.current_org_id`
deliberately left unset, asserts `scope_required: True` and zero rows (not
org A's data leaking out through an unscoped query). Passing.

### D6 (MINOR) — regression guard too narrow

`test_solution_scoped_viewpoint_still_requires_solution_id` only asserted
`'stakeholder'` individually lacks `enterprise_scope`. Tightened to assert
the complete set: `{k for k,v in STANDARD_VIEWPOINTS.items() if
v.get('enterprise_scope')} == {'basic', 'layered'}`, so a future viewpoint
accidentally gaining the flag is caught.

### D7 (MINOR) — smoke test locator ambiguity + residue

`tests/smoke/test_composer_opens_layered_viewpoint.py` used
`a[href*="/archimate/composer"]` — with D3 now also fixed (a second render
site carrying a matching href), an unqualified partial-href locator could
ambiguously match either page's link by DOM order. Fixed:
`nav#sidebar-nav a[href*="/archimate/composer"]`, scoped to the real
sidebar nav specifically.

The same test also seeded 3 `ArchiMateElement` rows via a second
`create_app("testing")` instance with no teardown, leaving residue in the
shared smoke database. Fixed: the seeded IDs are captured and explicitly
deleted after the browser context closes.

## Verification run (round 2) — actual command output, not summarized

```
$ python scripts/verify.py --tag static
...
48 passed, 0 failed, 1 skipped
[exited with code 0]
```
(1 skip is `css-build`, no vendored Tailwind CLI locally — unchanged from
round 1, CI covers it.)

```
$ pytest tests/test_composer_layered_viewpoint.py -v
tests/test_composer_layered_viewpoint.py::test_composer_sidebar_link_carries_viewpoint_query_param PASSED
tests/test_composer_layered_viewpoint.py::test_composer_nav_link_resolves_to_layered_viewpoint PASSED
tests/test_composer_layered_viewpoint.py::test_layered_viewpoint_returns_elements_without_solution_id PASSED
tests/test_composer_layered_viewpoint.py::test_layered_viewpoint_backend_failure_returns_explicit_error_not_fabricated_empty PASSED
tests/test_composer_layered_viewpoint.py::test_basic_viewpoint_also_enterprise_scoped PASSED
tests/test_composer_layered_viewpoint.py::test_layered_viewpoint_cross_tenant_isolation PASSED
tests/test_composer_layered_viewpoint.py::test_solution_scoped_viewpoint_still_requires_solution_id PASSED
tests/test_composer_layered_viewpoint.py::test_layered_viewpoint_with_no_org_context_returns_scope_required PASSED
8 passed, 21 warnings in 40.42s
```

```
$ pytest tests/test_modules_directory.py -v
... (D3's new test among them)
15 passed, 889 warnings in 86.48s
```

```
$ pytest tests/smoke/test_composer_opens_layered_viewpoint.py -v
tests/smoke/test_composer_opens_layered_viewpoint.py::test_composer_sidebar_link_opens_layered_viewpoint_with_elements PASSED
1 passed, 117 warnings in 115.85s
EXIT:0
```

All four runs executed in this session against this worktree's actual code
(real Postgres at 127.0.0.1:5432/flask_test, real headless Chromium via
Playwright) — not summarized or assumed.

## Files touched, round 2

- `app/static/js/archimate/composer_search.js` — D1, D2, D4 fixes (dirty-flag
  reset on all three `selectViewpoint` exit paths; `UndoStack.resume()` on
  the empty-elements branch; explicit `data.error` handling).
- `app/modules/modules_directory/routes.py` — D3 fix (`query_params` threaded
  through `_resolve()`).
- `app/services/archimate_viewpoint_service.py` — D4 fix (explicit error
  flag + `relationships_out` reset on exception) and D5 fix (fail-closed
  guard on missing `current_org_id()` in the enterprise-wide branch).
- `tests/test_composer_layered_viewpoint.py` — 2 new tests (D4, D5), D6's
  tightened assertion.
- `tests/test_modules_directory.py` — 1 new test (D3).
- `tests/smoke/test_composer_opens_layered_viewpoint.py` — D7 fixes (specific
  locator, seeded-row teardown).

## Explicitly not done

- **No merge, no deploy.** Per the brief's Handoff Target, this goes to
  `refuter` next given the tenant-isolation stakes.
- **500-row disclosure** — documented as a follow-up above, not implemented.
- **composer.html:662 badge's own internal logic** — not touched; confirmed
  it no longer surfaces the contradiction in this flow.
- **`navigation_registry_v2.py`/`navigation_sections_v2.py` dead-code
  retirement or wiring** — flagged as a follow-up architectural decision
  (ADR 0008 "one system of record"), not fixed in this bucket.
