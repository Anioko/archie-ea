# Blueprint deletion confirmation

Date: 2026-09-05. Scope: generic blueprint deletion UI and rendered-browser
regressions. Full-application authorization/persistence evidence is root-owned.

## Reproduced defect and change

The actual Delete button in the rendered `_solution_composition.html` row called
`confirmDeleteEntity`, which only assigned `activeModal = 'delete'`. No dialog
markup or Platform.modal open call existed. The first Chromium test clicked that
real row button with a synthetic Payments component and failed waiting for a
visible confirmation: the dialog did not exist (1 failed, 7 deselected, 9.45s).

The blueprint now includes `_blueprint_delete_confirmation.html` inside its
Alpine scope. It uses the existing `components/modal.html` macro and
`Platform.modal`, as required by DESIGN.md. It shows the target's display name,
an irreversible-action explanation, Cancel and Delete controls, and inline
errors. The standard modal provides a named dialog, focus trapping/restoration,
Escape, close button and backdrop behavior. No native alert/confirm, shared
modal changes, or new styling utilities were introduced.

Delete state is separate from the shared composition/governance editor state.
The confirmation captures its own type, copied target, revision and request
status. Each DELETE uses that captured type/id. Pending and completed identities
prevent duplicate requests, including dismissing and reopening a pending
deletion. A dismissed request may finish without closing or clearing a newer
editor. Rejected HTTP responses and `success:false` remain errors, retain the
target, and permit a deliberate retry.

After a confirmed successful DELETE, the known-deleted row is removed locally
before refreshing its list. If that refresh fails or returns malformed data,
the confirmation closes, the deleted identity cannot be submitted again, and
the page states that deletion succeeded but the list needs reloading. Existing
save/editor handling remains unchanged; deletion supplies an action label to
the shared refresh helper so its error says “Deleted” rather than “Saved”.

## Verification

- The first complete Chromium regression run passed 35 tests: eight new deletion
  cases plus all 27 existing composition/governance editor cases (40.91s).
- After adding governance-resource identity and malformed-successful-refresh
  coverage, all ten deletion tests passed (15.75s).
- Final combined run: `python -m pytest tests/test_blueprint_delete_confirmation.py
  tests/test_blueprint_composition_editor.py tests/test_blueprint_governance_editor.py -q`:
  **37 passed** (56.53s), including all 27 existing editor tests. No skips.
- Repository-config Ruff check for the new test file: passed.
- Scoped whitespace diff check: passed.
- `python scripts/build_css.py --check`: passed; committed stylesheet is current.
  The build emitted an outdated Browserslist metadata advisory. No package was
  installed; no CSS/manifest changes remained afterward.

The ten deletion cases exercise the real Jinja partials, actual row buttons,
shipped Platform core/modal code, Alpine, and blueprint JavaScript in Chromium.
HTTP responses alone are doubled. Covered outcomes include Cancel/Escape with
zero writes and restored focus, exact composition/governance DELETE paths,
HTTP rejection and HTTP 200 with `success:false`, refresh rejection/malformed
JSON, disabled repeated submission, dismissal/reopening during a pending request,
and late success/failure preserving an unrelated editor's unsaved input. Browser
runtime exceptions fail the test fixture.

No application login, database, authorization decision, production deletion or
backend persistence was exercised in this bounded harness. Root owns the
full-application composition deletion smoke test, broader verification and
deployment. This result makes no claim that those checks have run or passed.
