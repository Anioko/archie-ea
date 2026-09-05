# Application roadmap modal visibility repair

Date: 2026-09-05. Worktree: `.worktrees/fortune500-readiness`.

## Cause and change

The application roadmap's handwritten modal combined the native `hidden`
attribute with the Tailwind `flex` utility on its root. The author CSS display
rule overrode hidden display behavior. Before the first open, the supposedly
closed dialog still occupied the viewport and intercepted the Add Work Package
button. A dispatched click bypassed this obstruction; a normal click exposed it.

Replaced that wrapper with the existing `components/modal.html` macro. Its closed
root does not carry `flex`; Platform.modal adds it when opening and removes it
when closing. The macro also supplies the standard backdrop, labelled dialog,
Close control, and scrollable panel. The same modal ID, dynamic title, form,
Alpine methods, and API calls remain in use. No shared modal controller, macro,
stylesheet, existing smoke test, or backend changed.

## Verification

Before repair:

```
python -m pytest tests/test_roadmap_modal_visibility.py -q -k first_add
3 failed, 6 deselected in 34.70s
```

Chromium, Firefox and WebKit each failed on the initial normal Add Work Package
click. All three logs identified `div[hidden]#roadmap-work-package-modal` as the
element intercepting pointer events.

After repair:

```
python -m pytest tests/test_roadmap_modal_visibility.py -q
9 passed in 35.66s
python -m ruff check tests/test_roadmap_modal_visibility.py --select F,E4,E7,E9
All checks passed!
git diff --check -- app/templates/applications/roadmap.html
```

Three cases ran in each actual locally installed engine: Chromium, Firefox and
WebKit. No engine was skipped. Tests verify normal Add/cancel/reopen, initial and
dismissed `display:none`, Escape, Close-button and backdrop dismissal, ordinary
Edit with existing values, and native Tab/Shift-Tab containment. Browser runtime
errors also fail the fixture. There are no forced clicks or synthetic events.

An intermediate harness-only failure came from omitting the production Lucide
asset: the macro's Close icon then had no dimensions. Loading the actual vendored
asset corrected the harness; no workaround was added to production.

## Boundaries

The full roadmap template and its inline Alpine implementation are rendered
through Jinja. Its component macros and shipped seven stylesheets, Lucide,
Platform core/modal, Alpine plugins, CSP evaluator/adapter, and Alpine execute
in the browsers. Only the surrounding authenticated layout is replaced by a
minimal asset-loading shell; the read-only plateau/capability APIs are doubled.

These tests do not exercise login, database persistence, write APIs, full-page
shell interactions, production, or the existing CRUD smoke journey. Full-app CI,
CSS verification and deployment remain coordinator-owned.

Files changed:

- `app/templates/applications/roadmap.html`
- `tests/test_roadmap_modal_visibility.py`
- `docs/qa/roadmap-modal-result.md`
