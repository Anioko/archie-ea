# F500-062 governance editor repair — result

Status: ready for review. Not committed, not deployed, no production access.

## Coordinator review update

Independent follow-up expanded this file's companion Chromium suite from 9 to 12 cases. It reproduced and repaired: unrestricted principle-type search; successful POST followed by failed refresh leaving a duplicate-save risk; and a delayed save response closing a newer editor. Editor revision checks isolate stale asynchronous responses. A persistent notice distinguishes saved-but-stale-list from failed save. The UTF-8 declaration missing from the test page was added, and focus is asserted with a settled-state wait. Combined independent run with availability contracts: **24 passed, zero skips**. Full application/database/authorization/live release gaps below remain open; this is not acceptance or deployment.

The resumed Claude follow-up terminated at its budget threshold before task work. Codex implemented these follow-ups locally. No worker is running.

## Root cause

`_governance_compliance.html` calls `openEntityModal('governance_exception' | 'compliance_mapping' | 'change_request' | 'feasibility_review')`.
`blueprint.js` set `entityType` / `formData` / `activeModal` but no markup on `blueprint.html`
bound `activeModal`, so the four buttons (and the per-row Edit buttons) did nothing.

## Repair (bounded to the four governance controls)

Files touched (only the owned set):

- `app/templates/solutions/partials/_blueprint_governance_editor.html` (new) — one `components/modal.html` macro
  instance (`id="bp-governance-editor"`, `labelledby` to an inner `x-text` heading) with type-specific fields for the four
  types, labelled inputs, `h-9` buttons, semantic tokens only. Principle / mapped element use a live-search picker
  against `/archimate/api/elements/search` writing `principle_id`+`principle_name` / `archimate_element_id`+`element_name`;
  they are not free-text. Legacy rows with a name but no id still display the name.
- `app/templates/solutions/blueprint.html` — includes the partial inside the `blueprintPage()` scope (after the
  governance aside).
- `app/static/js/solutions/blueprint.js` — `openEntityModal` opens `Platform.modal` for the four types only and registers
  a one-time close hook (Escape / backdrop / × reset shared state). `closeModal` closes through `Platform.modal`.
  `submitEntity` now validates the server's required fields client-side, sends the existing
  `POST /solutions/<id>/<resource>` / `PUT .../<item_id>` (`_register_crud` in `solution_sad_routes.py`), treats a
  `{success:false}` envelope as failure, shows the server's `error` inline, keeps the editor and input on failure, and
  refreshes the correct `sad*` list from the `{success, items}` GET on success. Feasibility `feasible` maps
  select string ↔ boolean/null; empty phase/date fields go as `null`, not `''`.
  Behaviour for every other entity type passed to `openEntityModal` / `submitEntity` is unchanged.
- `tests/test_blueprint_governance_editor.py` (new).
- No permission, route, model, CSS, ledger, or delete-flow changes. Delete buttons still call `confirmDeleteEntity`,
  which remains unwired (out of scope by instruction).

## Evidence

Command run (only this file):

```
python -m pytest tests/test_blueprint_governance_editor.py -q -p no:cacheprovider
```

- Run 1: 5 passed, 1 failed — test bug (asserted a key the create defaults never carry). Assertion corrected.
- Run 2: 8 passed, 1 failed — real defect: editing an exception with `principle_name` but no `principle_id` hid the
  name. Partial fixed to show the chip when either is present.
- Run 3: **9 passed in 10.59s**.

## What the tests cover

Chromium via Playwright, real partials rendered with Jinja, real `components/modal.html`, real
`js/bundles/core-admin.js`, `ui/modal.js`, Alpine and `blueprint.js`. Only `/solutions/32/**` is doubled with `page.route`.

- Open on first click, correct heading, required-field label, focus moves into the dialog, Cancel closes, reopen works,
  Escape closes, reopen again — for all four controls.
- Blank required field → inline field-specific error, no network request.
- Create exception → `POST /solutions/32/governance-exceptions` with the typed body; dialog closes; list refreshed
  from the GET (item visible, no page reload).
- Edit existing exception → fields pre-filled with existing values; `PUT /solutions/32/governance-exceptions/7`
  with edited body.
- Failed save (400 `{success:false,error}`) → editor stays open, values retained, server message shown, Save re-enabled,
  nothing added to list.
- Feasibility review → select maps to boolean `false`, empty phase sent as `null`, correct endpoint.

## What the tests do not cover

- Real Flask routes, auth/permissions, CSRF, database persistence, or `to_dict` shapes (network is doubled).
- The full `/solutions/32` page render (only the two partials are mounted), `tailwind-output.css` rebuild of any new
  class combinations, the live element-search endpoint, or the compliance / change / review success paths beyond the
  ones listed (open/cancel/escape and validation are covered for all four; create-success is exercised on exception and
  review, edit-success on exception, failure on change).
- Delete (intentionally not implemented).

## Remaining gaps / follow-up (not this task)

- The other ~24 entity types still call `openEntityModal` with no editor (`integration_flow`, `sla`, `benefit_realization`,
  etc.) — same root cause, separate task.
- `confirmDeleteEntity` for these rows sets `activeModal='delete'` with no confirm dialog.
- Coordinator to run CSS rebuild check, integration and full-app browser smoke against a real DB before merge.
