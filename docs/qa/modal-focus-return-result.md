# Modal focus return repair — 2026-09-05

## Cause and scope

Exact-candidate Firefox and WebKit evidence for `2dbeb823f614503b9fe5acb02ebf2e3c4b401b11`, CI `33969670461`, showed the data entity lifecycle failing its Cancel focus-return assertion. The opener is the actual `#btn-delete-entity` button, still present after cancellation. Cleanup DELETE requests are not evidence of the later user-confirmation path completing. See `current-compatibility-failures.md` for the retained report paths and counts.

The shared controller attempted to focus the opener while its app shell was still inert, then discarded the saved reference. A nested parent modal also remained inert when its child closed. Separately, pointer activation does not reliably make buttons activeElement in every browser; current focus is not sufficient to infer an invoking button.

## Changes

- `app/static/js/ui/modal.js`: restore the surviving top modal/page's interactivity before returning focus; avoid focusing detached, hidden, or inert origins; preserve the active registered modal when the fallback visibility observer releases an older dialog.
- Add explicit `returnFocus` support to `open(id, payload, options)`, `prompt(id, payload, options)`, and `confirm(message, options)`. Without it, retain programmatic `document.activeElement` fallback. No global click capture, retained click event, WeakRef tracking, or listener wrapping ships.
- Existing owned `data-modal-open` handler supplies its closest trigger (including nested-icon clicks); `data-confirm` and `confirmSubmit` supply the submitter. `confirmSubmit` also resolves direct click controls and respects an explicit options.returnFocus override.
- `app/templates/data_architecture/entity_form.html`: actual Delete handler passes its button explicitly. No form submission, CSRF, endpoint, or destructive-action behavior changed.
- `tests/test_modal_focus_return.py`: real shipped modal/core/sanitizer/CSS assets in Chromium, Firefox, and WebKit, with an explicitly disclosed synthetic nested app shell and real pointer/keyboard interaction. The primary synthetic caller explicitly supplies the invoker, matching the changed data entity callsite.

## Verification

Systematic debugging and test-driven-development skills guided cause isolation and red-before-green browser checks. Valid original-controller reproduction: 17 failed, 1 passed (18 cases); recorded native focus attempt targeted the connected opener while inert. After ordering repair, remaining WebKit pointer failures exposed missing invoker information. Explicit-option regression failed in all three engines before support was added. Three owned handler variants each failed their Chromium focus assertion before propagation was implemented.

An experimental generic weak click-origin fallback was rejected: a Promise microtask without a focus change still appeared to be in click dispatch and restored the wrong origin (three engine failures). It was removed entirely. Async/programmatic cases now deliberately verify current-focus fallback; legacy pointer callers without an explicit invoker are not claimed fixed.

The final expanded suite passed **63 cases, zero skips**, in 114.64 seconds (21 cases each in Chromium, Firefox, and WebKit): `python -m pytest tests/test_modal_focus_return.py -q`. Coverage includes pointer and keyboard Cancel/Escape; explicit invokers despite preserved unrelated input focus; nested and underlying-modal closes; removed triggers; observer/new-modal ordering; unrelated-click and both microtask focus variants; and pointer/keyboard declarative open, declarative submit confirmation, confirmSubmit, and explicit override priority. The first explicit-only 48-case run also passed (107.49 seconds). An added keyboard fixture initially attempted reverse traversal from the first input, which left the document; this setup was corrected to normal forward Tab traversal before the final run, without changing product assertions.

Existing suites passed **46 cases, zero skips**, in 135.48 seconds: `python -m pytest tests/test_blueprint_governance_editor.py tests/test_blueprint_composition_editor.py tests/test_blueprint_delete_confirmation.py tests/test_roadmap_modal_visibility.py -q` (13 governance, 14 composition, 10 blueprint delete, 9 roadmap).

`ruff check tests/test_modal_focus_return.py`, `node --check app/static/js/ui/modal.js`, affected-file `git diff --check`, and `python scripts/build_js.py --check` passed. The modal controller is loaded separately, not included in the generated core bundles; no bundle rebuild was needed. No CSS classes changed.

## Boundaries

No app login, database, backend deletion, production access, dependency installation, full test suite, commit, or deployment was performed for this repair. Browser fixture routing serves only local HTML and existing shipped assets; it does not intercept a real application API. Tests assert Cancel sends no POST for the owned form handlers, not successful backend deletion. Full-app data entity journey remains unchanged and requires candidate CI verification with its isolated PostgreSQL fixture. Other direct modal callers still need explicit-invoker migration where pointer focus is not reliable; the root agent owns that inventory and integration.
