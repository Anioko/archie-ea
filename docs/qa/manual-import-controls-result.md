# Manual-import browser controls

## Reproduction and narrow repair

The actual manual-entry modal, DOMPurify, core fetch/modal helpers, Alpine CSP
evaluator, and application import script were exercised using ordinary clicks.
DOMPurify's DOM-clobber protection removes `name="name"` from generated inputs.
The importer collected fields by input name, so a visibly populated application
name was ignored. A normal-click Chromium regression failed before repair with
no POST. The preceding read-only reproduction showed the same result in all
three engines. The repair uses `data-field="name"`; sanitization stays enabled.

After that first repair, the desktop matrix exposed three further defects in
Chromium, Firefox and WebKit: confirmation changed the global event so the wrong
button was disabled; Remove did nothing; and a logical failure without an error
message was treated as success. Chromium also aborted a navigation because the
manual handler reloaded both through the auto-map helper and directly afterward.
That run ended with 10 failures and 2 passes. Normal create/merge already passed
in Firefox and WebKit: a Firefox-specific undefined-global-event exception was
not reproduced and is not claimed.

The handler now captures the explicit event's original control before awaiting,
guards repeated submission, and restores the button in `finally`, including
validation/cancellation returns. Remove has a native listener scoped to its
sanitized row. Explicit failure gets error feedback. The handler awaits the
existing auto-map helper, which owns the final reload; the redundant reload was
removed. No shared event dispatcher, sanitizer, backend, generated bundle, CSS
class, or template changed.

A further ordinary-click regression returning HTTP 200 with `{}` failed because
the handler refreshed as if import succeeded. The response guard now requires
the actual unified endpoint's contract: `success: true` and nonnegative integer
`created`, `updated`, `skipped`, and `failed` counters. Explicit error responses
retain their messages; empty/null/malformed success responses receive error
feedback without navigation. A positive `failed` count is allowed and remains
represented by the existing summary, not silently converted to all-success.

## Test boundary

`tests/test_manual_import_controls.py` renders the real modal and its includes
inside a synthetic surrounding page, with real repository scripts/styles. A
native loopback HTTP server holds and answers synthetic requests. Only non-origin
requests are intercepted and denied. No runtime APIs are replaced, attributes
are not restored by tests, and no forced clicks are used.

The fixture observes exact request JSON and CSRF headers, pending control state,
retry/error feedback, page errors, unexpected requests, and success navigation.
Create and merge responses are synthetic: this suite proves browser request and
control behavior, not database persistence or authorization. The independent
full-app smoke/database suites cover those separate boundaries.

DESIGN.md and the debugging/TDD instructions were read before edits. Scoped
Python correctness lint, JavaScript syntax, and whitespace checks passed. Final
browser verification is recorded below.

## Verification results

With `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`:

- Original normal-click regression: 1 failed before the safe field mapping.
- Mapping-only desktop matrix: 10 failed, 2 passed, exposing the separate
  confirmation, Remove, logical-response and redundant-navigation defects.
- Repaired initial matrix: **48 passed, zero skipped**, 1 configuration warning,
  141.22 seconds. Chromium, Firefox and WebKit at desktop 1440×1000 and mobile
  390×844; create/merge payloads, HTTP/logical errors, retries, double-click,
  missing names, partial valid batches, and row removal.
- Additional empty-object HTTP 200 regression: 1 failed before response guard.
- Expanded Chromium desktop matrix: **12 passed, 60 deselected, zero skipped**,
  1 configuration warning, 23.18 seconds. The final expanded 72-case matrix is
  frozen for the parent agent's independent all-browser rerun; this worker has
  not claimed that expanded full run passed.

The expanded matrix additionally checks null/empty responses, console errors
after browser-context closure (not just JavaScript page errors), and checked
auto-mapping success/HTTP failure with exact option payloads. Only expected
injected HTTP 400 resource errors at the exact fixture endpoint are permitted;
ordinary flows must have no console errors. While the mapping response is held,
the import dialog stays visible, the original control remains disabled, and only
one import plus one mapping request is sent even after a double-click.

The existing shared auto-map helper reloads after either mapping success or
HTTP failure, after emitting its corresponding toast; that behavior is unchanged.
The mapping tests assert sequencing and requests, not that transient feedback
remains readable after navigation. No live mapping or AI service is exercised.
The warning is pytest's unused `base_url` option with plugin autoload disabled.

No database, external service, credentials, configuration saves, commits or
deployments were used by this task.

Parent independent verification: final 72-case matrix passed with no skips in
216.16 seconds. This confirms the controlled browser scope above, not database
persistence or deployed behavior.
