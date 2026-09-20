# Task 01 — Fix all composer diagram-opening link mismatches (D1, D2, D3 + D4)

## Objective

Make every "open this in the ArchiMate Composer" link in the codebase actually
open the intended content. Three defects were named in the brief (D1, D2, D3);
investigation found a **fourth** instance of the same class (D4, below) plus a
fifth in the AI-chat solution-diagram path. Fix all of them in one change, and
prove each by driving the rendered UI, not by reading source.

## Context

Two entirely separate composer entry mechanisms exist and are routinely confused:

| Parameter | Value space | Handled by | Reads |
|---|---|---|---|
| `?viewpoint=<key>` | named keys only — `layered`, `basic`, `technology`, … (`STANDARD_VIEWPOINTS` in `app/services/archimate_viewpoint_service.py`) | server-side `get_viewpoint_data` | generated live from `ArchiMateElement` |
| `?viewpoint_id=<int>` | numeric `SavedDiagram.id` | client-side `loadSavedViewpoint`, `app/static/js/archimate/composer.js:2535-2543` | `GET /archimate/api/saved-viewpoints/<id>` → `SavedDiagram` |

Passing a numeric id as `?viewpoint=` does **not** error. `get_viewpoint_data`
falls through to `STANDARD_VIEWPOINTS['basic']`, so the user silently lands on
the wrong canvas. That is the single root cause behind D2, D3, D4 and the
`chat_workflows.py:817` case.

### D3 architectural decision — resolved: option (b)

`ViewpointView` (`app/models/archimate_viewpoint.py:213`) is **write-only dead
weight**. An exhaustive grep for `ViewpointView` across the repo returns exactly
four production hits, all inside `architect_viewpoints()` in
`app/modules/ai_chat/routes/chat_workflows.py` (the import at :1014, the
construction at :1078, and two log strings), plus the re-export line in
`app/models/__init__.py:185`. **Nothing reads `viewpoint_views` rows anywhere —
no route, no service, no template, no test.** Rows are created, committed, an id
is handed back in a URL that cannot open them, and they are never touched again.

Against that, `SavedDiagram` (`app/models/archimate_core.py:402`) is the
composer's actual system of record: it carries `TenantMixin` (ViewpointView does
**not** — it has only `owner_id`, so it is a tenant-isolation hole as well as a
dead store), optimistic-locking `version`, `viewpoint_type`, `solution_id`,
per-element layout via `SavedDiagramElement`, and it is what all fifteen
`/archimate/api/saved-viewpoints/*` endpoints, the composer tab list, autosave,
snapshots, export and review-submission all operate on.

Extending the saved-viewpoint API to also serve `ViewpointView` rows (option a)
would create a second authority for "a saved thing you can open in the composer"
and require a type disambiguator on every one of those fifteen endpoints — the
exact second-accessor mistake ADR 0008 exists to prevent, in exchange for
preserving a store with no readers.

**Therefore: option (b).** `architect_viewpoints()` creates `SavedDiagram` rows
(one per stakeholder viewpoint) instead of `ViewpointView` rows, and returns
`?viewpoint_id=<SavedDiagram.id>`. The existing loader then works unmodified, the
result is tenant-scoped, and it appears in the composer's own saved-viewpoint
list like every other diagram. `ViewpointView` is left in place, untouched and
now with zero writers (ADR 0008: retire, never accumulate — do not drop the
table; see Constraints for the marker to leave behind).

A ready-made helper already does exactly the required work: `create_diagram()` in
`app/services/archimate_composer_service.py` builds a `SavedDiagram`, lays the
elements out by layer, writes `SavedDiagramElement` rows and commits. Reuse it —
do not write a second layout routine.

## Constraints

- **Extend existing components; add none.** `create_diagram()` in
  `app/services/archimate_composer_service.py` is the diagram-creation component;
  `loadSavedViewpoint` in `composer.js` is the opening component; the
  `/archimate/api/saved-viewpoints/*` family in
  `app/modules/architecture/routes/archimate_routes.py` is the accessor. Nothing
  new belongs here.
- **Never fabricate a link.** The current code emits
  `"composer_url": "/archimate/composer?viewpoint=0"` on the failure paths — a
  link to nothing, indistinguishable to the user from a working one. Replace with
  `"composer_url": None`, and guard the renderer at
  `app/static/js/ai_chat/commands.js:405` so no anchor is emitted when
  `composer_url` is null (show the viewpoint name and element count, no link).
  This is the `fabricated-data` rule, not a style preference.
- Tenant isolation: `SavedDiagram` carries `TenantMixin`, so `organization_id` is
  set automatically inside a request context. `architect_viewpoints()` runs under
  `@login_required` in a request, so this is satisfied by using the model — do
  **not** hand-set `organization_id`.
- Do not regress tonight's three deployed composer fixes (sidebar link,
  dashboard per-layer tab buttons, `viewpointDirty`/autosave behaviour). The
  per-layer tab link at `app/templates/dashboards/overview.html:620` is
  **correct as-is** (`viewpoint=layered&layer=…` — `layered` is a real
  `STANDARD_VIEWPOINTS` key); leave it alone.
- Leave a short comment where `ViewpointView` is defined recording that it now
  has no writers and what superseded it, so the next reader does not re-adopt it.
- Read-only-on-code roles do not apply to you; route authoring through Aider per
  CLAUDE.md, `Edit`/`Write` as the fixup path.

## Deliverable

**D1 — dashboard "Architecture Overview — Layered Viewpoint" card.**
`app/templates/dashboards/overview.html`, line **253** (the brief says 252; that
is the closing `</div>` — the `<a href>` is on 253). Change
`href="/archimate/composer"` to `href="/archimate/composer?viewpoint=layered"`.

**D2 — canvas sub-diagram drill-down.**
`app/static/js/archimate/composer.js:5256`, in `linkSubDiagram`. Change
`'/archimate/composer?viewpoint=' + existingId` to
`'/archimate/composer?viewpoint_id=' + existingId`. `existingId` is
`cell.get('linkedSubDiagramId')`, a `SavedDiagram.id`. Rebuild the JS bundles
(`js-build` gate).

**D3 — AI chat `architect_viewpoints()`**, `app/modules/ai_chat/routes/chat_workflows.py`:
1. Drop the `ViewpointView` import and the `ArchiMateViewpoint` stakeholder-match
   lookup block (:1047-1075) — with option (b) there is no `viewpoint_id` FK to
   satisfy, so the whole "skip when no matching ArchiMateViewpoint" branch and
   its `?viewpoint=0` placeholder disappear.
2. For each of the four `VIEWPOINT_DEFINITIONS`, call
   `create_diagram(filtered_ids, name=f"{solution.name} — {vp_def['name']}", created_by=current_user.id, solution_id=solution_id)`
   from `app.services.archimate_composer_service`. It returns a relative URL
   string or `None`.
3. That helper currently returns `?viewpoint=<id>` — fix it too (see D4) so the
   returned URL is already correct; do not string-patch the URL at the call site.
4. Set `SavedDiagram.viewpoint_type` to `vp_def["type"]` so the four viewpoints
   are distinguishable in the composer's saved list. `create_diagram()` does not
   accept that argument today — add an optional `viewpoint_type: Optional[str] = None`
   parameter to it (keyword, defaulted, backward compatible with its four other
   callers in `slack_architect_service.py`, `teams_meeting_service.py` and
   `structured_deliverable_service.py`).
5. Response shape: replace `"viewpoint_view_id"` with `"saved_diagram_id"`, and
   emit `"composer_url": None` when `create_diagram` returns `None` (no elements
   matched that viewpoint's layers). Update the docstring at :949-970 to match —
   including the `?viewpoint=42` example at :966 and the "create a ViewpointView
   record" sentence at :953.
6. `app/static/js/ai_chat/commands.js:405` — guard the anchor on
   `vp.composer_url` being truthy, per Constraints.

**D4 (found during this investigation — same bug class, not in the brief).**
Three further sites pass a real `SavedDiagram.id` as `?viewpoint=`:
- `app/services/archimate_composer_service.py:96` — `url = f"/archimate/composer?viewpoint={diagram.id}"`. This one is the worst of the set: its return value feeds the Slack architect service, the Teams meeting service and the structured-deliverable service, so **every** AI-generated diagram link delivered to Slack/Teams today opens the wrong canvas. Change to `viewpoint_id=`. Also fix the docstring example at :23.
- `app/modules/architecture/routes/archimate_routes.py:6746` — `"composer_url": f"/archimate/composer?viewpoint={diagram.id}"` (the create-diagram-from-elements route; `diagram` is a `SavedDiagram`, see the docstring at :6655). Change to `viewpoint_id=`. Note :750 in the same file already uses `viewpoint_id=` correctly — that is the pattern to match.
- `app/modules/ai_chat/routes/chat_workflows.py:817` — `redirect_url = f"/archimate/composer?viewpoint={diag.id}&solution_id={solution_id}"`, where `diag` is the `SavedDiagram` created at :788. Change to `viewpoint_id=`.

Leave `?elements=<ids>` URLs (`archimate_routes.py:6504`, `:6633`) and
`navigation_sections_v2.py:333` (`viewpoint=layered`) alone — both are correct.

**Tests.**
- Template test asserting the Architecture Overview card's anchor carries
  `viewpoint=layered` (D1).
- A `tests/smoke/` Playwright journey: dashboard → click "Open Composer" on that
  card → assert real elements render on the canvas (not an empty basic view).
- JS-level or smoke assertion that `linkSubDiagram` produces a `viewpoint_id=`
  URL (D2).
- A test for `architect_viewpoints()` asserting it creates `SavedDiagram` rows
  (not `ViewpointView`), that each returned `composer_url` uses `viewpoint_id=`,
  that `GET /archimate/api/saved-viewpoints/<that id>` returns the diagram with
  its elements, and that a viewpoint matching zero elements returns
  `composer_url: None` rather than a placeholder link.
- An end-to-end proof for D3: generate viewpoints for a solution, follow the
  returned URL in the browser, assert real elements are on the canvas.
- A tenant-isolation test: a second org cannot load a diagram created by
  `architect_viewpoints()` under the first org.
- A test asserting `create_diagram()` returns a `viewpoint_id=` URL (D4), which
  transitively covers the Slack/Teams/deliverable callers.

**Re-grep.** After fixing, re-run an exhaustive search across templates, JS and
Python for `viewpoint=` and confirm every remaining occurrence resolves to a
literal `STANDARD_VIEWPOINTS` key. Paste the raw output and a line-by-line
verdict into the build report — this bug class has now been found independently
six times, so the grep is the deliverable, not a formality.

## Acceptance Criteria

- D1, D2, D3 and all three D4 sites fixed.
- `architect_viewpoints()` writes `SavedDiagram`; no code path in the repo
  constructs a `ViewpointView`; the model retains its comment explaining why.
- No `composer_url` in the repo is ever a link to a non-existent diagram —
  failure paths return `None` and the UI renders no anchor.
- The exhaustive re-grep shows zero remaining `?viewpoint=<non-key>` usages, with
  the output in the report.
- A browser walkthrough demonstrates D1 and D3 opening real content; the result
  is described in the report as a clicked journey, not a status line.
- `python scripts/verify.py` (bare, not `--tag static`) green, including
  `js-build`, `fabricated-data`, `tenant-scoping` and `smoke-coverage-on-change`.
- None of tonight's three prior composer fixes regress.

## Handoff Target

`refuter`. This is the fourth round tonight in which a "complete" fix was
followed by another instance of the same defect; this task itself added three
sites the brief did not know about. Review on the assumption a seventh exists —
in particular check non-composer surfaces that link to diagrams (exports, email
and Slack/Teams notification payloads, PDF/report generators) for the same
parameter confusion, since those were not covered by the greps above.
