# Solution composition add/edit repair

Date: 2026-09-05. Scoped worktree: `.worktrees/fortune500-readiness`.

The `+ Component` control called `openEntityModal('composition')`, but only governance
types had editor markup and a Platform modal open path. The initial Chromium test
failed after a normal button click: `#bp-composition-editor` did not exist.

## Changes

- Added the standard Platform modal inside the blueprint Alpine scope, with visible
  labels, native controls, focus containment, Escape/cancel, inline errors, and save
  state. Both add and edit buttons now reach the editor.
- Application selection uses `/applications/api/list?search=…&limit=10&per_page=10`.
  ArchiMate selection uses `/archimate/api/elements/search?q=…&limit=10`.
  DESIGN.md's decision-search URL is obsolete; the current architecture forms
  explicitly document its replacement and the route exists in archimate_routes.py.
  Searches are debounced 300ms, require two characters, distinguish loading/empty/
  invalid-response/error states, and discard stale responses.
- Save requires a selected positive integer identity and name, posts to
  `/solutions/32/composition` (using the current solution ID), and puts edits to
  `/solutions/32/composition/<id>`. Existing additional model fields and unfamiliar
  classifications are retained on edit. Replacement choices are Application and
  ArchiMate element; the backend has no declared enum for component_type.
- Extended existing revision protection to composition saves: late success/failure
  cannot close a newer editor or overwrite its input. Successful writes followed
  by failed or malformed refreshes close the editor and report stale list data,
  avoiding a duplicate create from retrying Save. Failed writes preserve input.

## Verification

Executed:

```
python -m pytest tests/test_blueprint_composition_editor.py tests/test_blueprint_governance_editor.py -q
27 passed in 41.96s
python -m ruff check tests/test_blueprint_composition_editor.py --select F,E4,E7,E9
All checks passed!
git diff --check
```

There are 14 composition cases and 13 existing governance cases. These exercise
real Jinja-rendered composition/governance partials, the real modal macro, shipped
Platform core/modal scripts, Alpine, and blueprint.js in Chromium. Composition
tests also fail on browser runtime errors. All clicks use normal actionability
checks; picker activation includes a native Tab/Enter journey.

Coverage includes open/cancel/Escape/reopen, missing identity validation, both
pickers, exact create payload, edit payload and legacy values, save errors at HTTP
400 and HTTP 200 success:false, failed/malformed refresh, late success/failure
while a governance editor is open, malformed search, and out-of-order searches.

Additional failing tests exposed and then verified corrections for JSON escaping
inside an Alpine attribute and malformed refresh responses treated as empty lists.
A test-only route capture race was corrected by fulfilling the newer search in
its route handler before releasing the older request.

## Boundaries and remaining work

Only HTTP JSON responses are doubled. No local PostgreSQL, Flask login, real
persistence, tenant authorization, complete blueprint layout, or production state
was exercised by this agent. Full-app smoke tests, full verification, CSS rebuild,
CI and deployment are coordinator-owned; this report does not claim those passed.

The existing composition Delete control and all other generic entity types are
outside this add/edit repair. No backend authorization or schema changes were made.
The shared notice is rendered by the governance editor partial, already included
next to the composition editor in the blueprint.

Files owned by this repair:

- `app/static/js/solutions/blueprint.js`
- `app/templates/solutions/blueprint.html` (one include)
- `app/templates/solutions/partials/_blueprint_composition_editor.html`
- `tests/test_blueprint_composition_editor.py`
- `docs/qa/composition-editor-result.md`
