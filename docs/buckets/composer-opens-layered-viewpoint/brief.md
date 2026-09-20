# Task Brief: ArchiMate Composer Should Open the Layered Viewpoint, Not a Blank Canvas

## Objective
Fix the "ArchiMate Composer" entry point so it opens directly into the
enterprise-wide Layered viewpoint (every element and relationship across all
ArchiMate layers), instead of a blank "Unsaved diagram" canvas with a
template picker.

## Context
Reported directly by the founder tonight: "The ArchiMate composer doesn't
open the actual architecture overview - layered viewpoint... to enable the
users see the 444 elements, 159 relationships across all Archimate layers.
This is wrong, it should open that viewpoint."

Verified live against production (`https://165-22-125-156.sslip.io`) as
`qa-enterprise-architect@example.com`, the only demo persona with the
composer nav item visible (role-gated to Enterprise):

1. Clicking "ArchiMate Composer" in the sidebar navigates to bare
   `/archimate/composer` and lands on a blank canvas with a "Start from a
   template" picker — not the layered/overview viewpoint.
2. `app/modules/architecture/routes/archimate_routes.py::composer_page`
   (route `/composer`) already accepts a `?viewpoint=<id>` query param that
   opens straight into View mode on that viewpoint — this mechanism is real
   and wired correctly client-side
   (`app/static/js/archimate/composer_search.js::selectViewpoint`, invoked
   from `app/static/js/archimate/composer.js` on page load via
   `window.__COMPOSER_CONFIG__.initialViewpoint`). It was simply never
   passed by the nav link.
2. `app/config/navigation_sections_v2.py`'s "ArchiMate Composer" entry
   (`endpoint="archimate.composer_page"`) had no query param, so
   `url_for('archimate.composer_page')` resolved to the bare URL — no
   query-param plumbing existed in `NavigationItemV2`/`NavigationRegistryV2`
   at all (`app/config/navigation_registry_v2.py::_resolve_url`).
3. **The deeper, real bug**, found by testing `?viewpoint=layered` directly:
   even with the viewpoint correctly selected client-side, the backend
   (`app/services/archimate_viewpoint_service.py::get_viewpoint_data`)
   unconditionally requires a `solution_id` for every viewpoint — "Invariant
   1: Scope required — no solution_id returns scope_required flag". This is
   correct for solution-scoped viewpoints (e.g. "Application Architecture"
   for one solution's model) but wrong for `'basic'` and `'layered'`, both
   of which are explicitly enterprise-wide by their own definitions
   (`'layered'` has `roles: ['Enterprise']` only, and its description reads
   "All elements organised in horizontal layer bands" — the whole point is
   the whole model, not one solution). Without a `solution_id`, the backend
   returned `scope_required: True`, and the frontend rendered "Select a
   solution to view this viewpoint" — while ALSO showing a stale static
   badge reading "No ArchiMate elements linked for this viewpoint. Showing
   enterprise-wide elements." (a second, unrelated self-contradiction —
   `app/templates/archimate/composer.html:662` — this static text is
   apparently always present regardless of what's actually loaded).

## Changes already made (this worktree, uncommitted, needs builder to add
tests and verify, not to redo)
1. `app/config/navigation_registry_v2.py` — added a `query_params:
   Dict[str, str]` field to `NavigationItemV2`, threaded through
   `_resolve_url()` into `_safe_url_for(item.endpoint, **item.query_params)`
   (the underlying `_safe_url_for` already accepted `**kwargs`, just was
   never called with any).
2. `app/config/navigation_sections_v2.py` — the "ArchiMate Composer" nav
   item now sets `query_params={"viewpoint": "layered"}` (and
   `url_fallback` updated to match, for the case `url_for` itself fails).
3. `app/services/archimate_viewpoint_service.py` — added an
   `'enterprise_scope': True` flag to the `'basic'` and `'layered'`
   viewpoint definitions in `STANDARD_VIEWPOINTS`. `get_viewpoint_data()`
   now only enforces "scope required" when the viewpoint does NOT declare
   `enterprise_scope` — for `enterprise_scope` viewpoints with no
   `solution_id`, it queries `ArchiMateElement.query` directly (tenant-
   scoped automatically via `TenantMixin`'s `do_orm_execute` listener, no
   manual `organization_id` predicate), bounded by the same `.limit(500)`
   already used elsewhere in this function, instead of returning
   `scope_required: True`.

## Constraints
- **Verify the existing solution-scoped viewpoints are completely
  unaffected.** Every other viewpoint in `STANDARD_VIEWPOINTS` (stakeholder,
  actor_cooperation, and the rest — do not assume the list, read the whole
  file) must still require `solution_id` and still return `scope_required:
  True` without one — the `enterprise_scope` flag must be opt-in per
  viewpoint, not a global behavior change.
- **Confirm the 500-row cap is acceptable for "444 elements, 159
  relationships"** (comfortably under 500) but flag in the build report
  whether a genuinely larger tenant (500+ elements) would now silently
  truncate the layered viewpoint — if so, that's worth a `total_elements`
  vs `showing_count` disclosure in the response so a truncated view is
  visibly truncated, not silently incomplete (this repo's own
  "never fabricate/never silently truncate" convention — check
  `app/templates/macros/` or similar for the existing pattern used
  elsewhere for "showing N of M").
- **Do not touch the second self-contradiction bug** (the static "No
  ArchiMate elements linked... Showing enterprise-wide elements" badge in
  `composer.html:662` that appears regardless of actual state) unless it's
  trivial — if it's more than a one-line fix, document it as a named
  follow-up rather than scope-creeping this bucket. Check whether this fix
  already makes that specific badge's WORDING accidentally correct now
  (since the enterprise-wide load genuinely does work), even if the
  underlying "always show this badge" logic is still questionable.
- **Tenant isolation is the highest-stakes thing to verify here.** The new
  enterprise-wide query path bypasses the solution-junction lookup entirely
  — confirm with an explicit cross-tenant test that org A's layered
  viewpoint never returns org B's elements, exactly like every other tenant-
  boundary check tonight.
- No new REST route, no new query surface beyond what's described — this is
  a targeted fix to an existing mechanism, not a new feature.

## Deliverable
1. Real tests: a test proving the "ArchiMate Composer" nav link now resolves
   to a URL containing `viewpoint=layered`; a test proving
   `get_viewpoint_data('layered', solution_id=None)` returns real elements/
   relationships for the calling tenant (not `scope_required: True`); a
   cross-tenant test proving org A's call never returns org B's rows; a
   test confirming a genuinely solution-scoped viewpoint (pick one, e.g.
   `'stakeholder'`) still returns `scope_required: True` with no
   `solution_id` — proving the opt-in flag didn't leak into other
   viewpoints.
2. A live browser check (Playwright, since the claude-in-chrome extension is
   unreachable tonight — use a standalone script like the rest of tonight's
   verification work) against a real environment: click the composer link,
   confirm it lands on the layered viewpoint with real elements rendered,
   not a blank canvas or a "select a solution" prompt.
3. Build report with before/after evidence, the tenant-isolation test
   result, and an explicit note on the 500-row truncation question above.

## Acceptance Criteria
- Clicking "ArchiMate Composer" from the sidebar opens directly into the
  Layered viewpoint showing real elements across all layers, not a blank
  canvas.
- No regression to any solution-scoped viewpoint's `scope_required`
  behavior.
- No cross-tenant data leak in the new enterprise-wide query path.
- `python scripts/verify.py --tag static` clean.

## Handoff Target
`refuter` — this bucket's code changes are already made and need
independent verification plus test coverage, not a full tech-lead re-scope.
Given the tenant-isolation stakes, treat this with the same rigor as every
other production-touching bucket tonight. If the refuter finds it needs
tests written first, route to `builder` for that, then back to `refuter`.
