# Pages that existed and could not be reached — resolved

**Found:** 2026-08-08, by `scripts/check_broken_surfaces.py --kind orphan-page`
**Decided:** 2026-08-08 — all thirteen deleted. This is the decision record.

Thirteen templates extended a layout — which is what made them **pages** rather
than partials or macro files — and no `render_template()` call named them, and
no other template included them. They had no URL. Someone built each of these
and nobody could open any of them.

## The decision

**All thirteen were deleted.** Not one turned out to be a feature waiting for a
route: every single one was either superseded by a live equivalent or had no
back end at all. Resolving each against the running app's `url_map` — rather
than by grep — is what made that call safe, and it twice contradicted what a
grep had suggested.

| Template | Why it had no URL | Live equivalent |
|---|---|---|
| `adm_kanban/index.html` | superseded v1 board | `adm_kanban/board_v2.html`, served at `/adm-kanban/` |
| `admin/admin_overview.html` | superseded | `admin/index.html` |
| `archimate/viewpoints.html` | `/archimate/viewpoints` **redirects** to the unified composer — viewpoints became a mode within it | composer |
| `archimate_crud/list.html` | superseded by the dashboard/detail pair | `archimate_crud/dashboard.html` |
| `archimate_crud/create.html` | ditto | `archimate_crud/detail.html` |
| `archimate_crud/edit.html` | ditto | `archimate_crud/detail.html` |
| `archimate_crud/health_scorecard.html` | ditto | `archimate_crud/dashboard.html` |
| `capability_framework/dashboard.html` | its route redirects to `main.framework_management.dashboard` | framework management |
| `capability_maturity/frameworks/cobit_dashboard.html` | no route, no API — never wired | none |
| `capability_maturity/frameworks/level4_dashboard.html` | no route, no API — never wired | none |
| `duplicate-detection/dashboard.html` | stale copy under a **hyphenated** directory; the live one is the underscore path | `duplicate_detection/dashboard.html` |
| `errors/custom_error.html` | unused | `errors/{403,404,500,generic_error}.html` |
| `testing/artifact_viewer.html` | its only script was deleted as dead code earlier the same day | none |

## Two corrections to the original version of this document

The first draft asserted things that turned out to be false. Both were caught
by resolving against the real route table instead of grepping:

1. It said the ADM Kanban board's back end was **absent** — that `board_v2.js`
   called `/api/adm-kanban/v2/{phases,deliverables}`, which "do not exist". They
   do. `adm_kanban_v2_routes.py` registers **22** routes including `/cards`,
   `/config`, `/metrics`, `/phases/<phase>/deliverables` and four
   `/suggestions/*` endpoints. The API is complete and it serves the *live*
   board, `board_v2.html`. Only the superseded `index.html` was orphaned.

2. It implied wiring up a route was a live option for some of these. It was not
   for any of them: every page was already replaced or had nothing behind it.

## The two that had a data layer but no front door

`cobit_dashboard.html` and `level4_dashboard.html` are the only ones deleted
with no live equivalent. The COBIT **models do exist** — `cobit_domains`,
`cobit_processes` and the `cobit_capability_mapping` association in
`app/models/capabilities.py`. What was missing was any API serving them and any
route rendering the dashboards.

Wiring them up would mean building a feature, not fixing a defect, so the
templates were deleted rather than left to rot in every grep, audit and token
count. Git holds them if the work is ever resumed — and whoever resumes it
should know the data layer is already there.

## Why deletion rather than "leave it and document it"

A template nobody can open still costs something every day: it appears in every
grep, every design-token count, every audit, and it invites the reasonable-but
-wrong assumption that the feature exists. Deleting is reversible; the
confusion it causes is not free. Where a page had genuinely unfinished work
behind it, that fact is recorded above so the decision can be revisited with
the evidence rather than re-derived from scratch.

## Related finding: blueprint name collisions

`/admin/security` is unreachable for a different and more interesting reason.
The route **is** defined, in `app/modules/admin/security_routes.py` — but that
blueprint is never registered. `app/_bootstrap/blueprints.py` registers a
*different* blueprint that happens to share the name `security_bp`, from
`app/routes/security_api.py`.

Eleven blueprint **names** are declared more than once across the codebase.
Seven are the documented dual-layout design (`CLAUDE.md`: `account`, `admin`,
`ai_chat`, `auth`, `dashboard`, `integrations`, `monitoring`, selected by the
`USE_*_GUARDRAILS` flags). The remainder — `capability_map`, `dashboard_pages`
(declared **three** times), `deprecation`, `health`, `sidebar_mgmt` — are worth
checking individually: where two blueprints share a name, only one can win, and
the loser's routes vanish silently. Flask raises nothing, `boot-health` sees a
registered blueprint, and the page simply 404s.

This is **not** resolved and is not covered by the deletions above.
