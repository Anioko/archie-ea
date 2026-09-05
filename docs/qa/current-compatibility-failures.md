# Exact-candidate compatibility failures

Read-only diagnosis of CI run **33969670461**, candidate **2dbeb823f614503b9fe5acb02ebf2e3c4b401b11**. Unlike the older whole-product survey, these results apply to this exact candidate. They do not qualify later working-tree repairs.

| Job | Retained artifact | JUnit result |
|---|---|---|
| Firefox, **101315836389** | `smoke-firefox-2dbeb823f614503b9fe5acb02ebf2e3c4b401b11`, artifact 9970670790 | **80 tests: 79 passed, 1 failed, 0 errors, 0 skips**, 355.505 seconds |
| WebKit, **101315836268** | `smoke-webkit-2dbeb823f614503b9fe5acb02ebf2e3c4b401b11`, artifact 9970680744 | **80 tests: 79 passed, 1 failed, 0 errors, 0 skips**, 388.874 seconds |

Only these two artifacts were downloaded, to `.qa-artifacts-33969670461/firefox/` and `webkit/`. Each contains its JUnit XML under `home/runner/work/archie-ea/archie-ea/tests/smoke/_artifacts/` and a server log under `tmp/` (`smoke-server-46789.log`, `smoke-server-53337.log`). Job metadata reports both jobs completed/failure, with both the critical-journey step and no-skip acceptance step failed. The JUnit evidence has **no skipped tests**; the acceptance failure must not be described as a skip defect. Overall-run logs were unavailable while the run remained active, so this diagnosis uses the completed job metadata and uploaded artifacts.

## Exact failing outcome

Both fail only:

`tests.smoke.test_data_entity_lifecycle.test_data_architect_entity_create_filter_edit_cancel_delete`

At `tests/smoke/test_data_entity_lifecycle.py:112`, after clicking **Cancel** and confirming that the dialog is hidden, `expect(trigger).to_be_focused()` fails after five seconds. The locator resolves repeatedly to the real `#btn-delete-entity` button named **Delete Entity**, but its focus state is inactive.

The test reached and passed create, matching/excluding filters, edit, saved-value API readback, reload, reopening the edit form, visible named confirmation and Cancel/hide assertions. It did **not** reach the subsequent Cancel/no-request assertion, reopening/Confirm action, exactly-once user deletion, final deletion readback, or final page-error assertion. Do not report the full lifecycle as passing.

Both logs show successful create/edit POST redirects and successful read requests. After the assertion failure, the test's `finally` block independently finds the owned row, loads its edit page, sends the exact cleanup POST and reads an empty collection. The later `/architecture/data-entities/1/delete` HTTP 302 is **cleanup**, not evidence of a successful user Confirm. The row was still present in the cleanup lookup after Cancel, consistent with cancellation preserving it, but the explicit normal-flow no-deletion assertion was not executed.

## Product versus harness diagnosis

**Classify as a product accessibility/focus-return failure, with a source-supported modal ordering defect; not a demonstrated flaky test or wrong opener.**

The opener is unambiguous: the edit form's `#btn-delete-entity` receives the normal user click and synchronously calls `Platform.modal.confirm(...)` in `app/templates/data_architecture/entity_form.html:139–146`. Cancel does not navigate, remove that button, or replace the form, so returning to that control is the appropriate continuation. The test does not use synthetic click forcing or request interception.

Current source (unchanged from the candidate in the inspected files) explains a concrete failure mechanism:

1. `app/static/js/ui/modal.js:_trapFocus`, around lines 106–113, captures `document.activeElement` into `entry.prevFocus`.
2. `create()` appends the dynamic confirmation as a direct child of `<body>`. `open()` then makes the other body children inert through `_setBackgroundInert`. The entity form/opener sits inside the real admin shell, outside the dynamic modal.
3. `close()`, around lines 325–336, calls `_releaseFocus` **before** restoring background interactivity.
4. `_releaseFocus`, around lines 140–149, invokes `entry.prevFocus.focus()` while the opener's ancestor can still be inert, then clears `prevFocus`. Only afterwards does `close()` remove the background inert state. There is no subsequent retry of the correct focus return.

This order conflicts with the modal's own stated focus-restoration contract and is a strong explanation for the executed symptom. The artifacts do not retain `document.activeElement` at open/close, a DOM trace, or the inert ancestry at the exact instant. Therefore the evidence cannot prove this was the sole mechanism in either engine. Pointer-click focus differences are a secondary possibility: the API captures the active element, not an explicit invoking element. That is not grounds to remove the expected return-to-invoker behavior.

## Minimal repair and verification recommendation

Reproduce the current modal with both ordinary pointer activation and keyboard activation of the real opener. Record focus identity/inert ancestry without user data. Then make modal close establish the correct remaining-modal/background interactivity **before** returning focus; preserve stacked-modal isolation and avoid focusing a removed or unrelated element. If pointer activation does not establish the correct saved target, support/record the explicit invoking control rather than relying only on incidental activeElement state. The fallback visibility-observer release path has the same focus-before-uninert ordering and deserves a scoped regression assessment, not an untested blanket rewrite.

Keep the existing focus assertion, timeouts, deletion cancellation and persistence checks intact. Add a focused dynamic-confirm regression for Cancel and Escape with a nested app-shell opener, then rerun the exact full-application lifecycle in Firefox and WebKit. Do not count cleanup as a successful user action, manually focus the button in the smoke test after Cancel, force clicks, or accept body focus to manufacture green.

No source or tests were changed by this diagnosis, no tests were executed, and no local database or production service was used. Root owns repair authorization, candidate retests, ledger and CI status.
