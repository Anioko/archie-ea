# Pages that exist and cannot be reached

**Found:** 2026-08-08, by `scripts/check_broken_surfaces.py --kind orphan-page`

Thirteen templates extend a layout — which is what makes them **pages** rather
than partials or macro files — and no `render_template()` call names them, and no
other template includes them. They have no URL. Someone built each of these and
nobody can open any of them.

This is not inference from a grep. It was checked against dynamic dispatch: the
entire codebase contains exactly **one** `render_template()` with a variable
template name (`app/services/solution_narrative_service.py`, for narrative
documents), so no page here is reachable by indirection the check cannot see.

## The list

| Template | Notes |
|---|---|
| `admin/admin_overview.html` | An admin overview. Uses `text-info-emphasis`, so it was styled to the design system — this was finished work. |
| `archimate_crud/list.html` | ArchiMate CRUD — list |
| `archimate_crud/create.html` | ArchiMate CRUD — create |
| `archimate_crud/edit.html` | ArchiMate CRUD — edit |
| `archimate_crud/health_scorecard.html` | ArchiMate health scorecard |
| `adm_kanban/index.html` | The ADM Kanban board. Its `board_v2.js` also called `/api/adm-kanban/v2/{phases,deliverables}`, which do not exist — so the page is unreachable *and* its back end is absent. Consistent with a feature that was never finished. |
| `archimate/viewpoints.html` | ArchiMate viewpoints |
| `capability_framework/dashboard.html` | Capability framework dashboard |
| `capability_maturity/frameworks/cobit_dashboard.html` | COBIT maturity dashboard |
| `capability_maturity/frameworks/level4_dashboard.html` | Level-4 maturity dashboard |
| `application_mgmt/custom_field_form.html` | Custom field form |
| `duplicate-detection/dashboard.html` | Duplicate detection dashboard |
| `errors/custom_error.html` | Error page — may be intended for a handler that never registered it |

## Why this is not being fixed here

Three of these outcomes are possible per page, and choosing between them is a
product decision rather than a defect fix:

1. **Wire it up** — the feature is wanted and a route was never added.
2. **Delete it** — the feature was abandoned; the template is dead weight that
   still shows up in every grep, every design-token count and every audit.
3. **Leave it deliberately** — it is a work-in-progress someone intends to
   finish, in which case that intent should be written down here.

Guessing would either destroy work or ship a half-built feature. What has been
done instead: `check_broken_surfaces.py` counts them, and the `broken-surfaces`
ratchet in `scripts/verify.py` means the number cannot **grow** while the
decision is outstanding.

## Related finding: blueprint name collisions

`/admin/security` is unreachable for a different and more interesting reason.
The route **is** defined, in `app/modules/admin/security_routes.py` — but that
blueprint is never registered. `app/_bootstrap/blueprints.py` registers a
*different* blueprint that happens to share the name `security_bp`, from
`app/routes/security_api.py`.

Eleven blueprint **names** are declared more than once across the codebase.
Seven of those are the documented dual-layout design (`CLAUDE.md`: `account`,
`admin`, `ai_chat`, `auth`, `dashboard`, `integrations`, `monitoring`, selected
by the `USE_*_GUARDRAILS` flags). The remainder — `capability_map`,
`dashboard_pages` (declared **three** times), `deprecation`, `health`,
`sidebar_mgmt` — are worth checking individually: where two blueprints share a
name, only one can win, and the loser's routes vanish silently. Flask raises
nothing, `boot-health` sees a registered blueprint, and the page simply 404s.
