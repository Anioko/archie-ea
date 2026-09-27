# F500-083 — Jira connection-test control

## Current defect and repair

The current `admin/connectors/jira.html` reproduced the historical audit's
`Unexpected token '.'` failure in Chromium at desktop and mobile widths. The
template terminated its promise chain after `.catch(...)`, then began a new
statement with `.finally(...)`. Parsing failed before the click listener could
register; `testJiraConnection` was undefined, and clicking Test Connection sent
no request even though the real Platform core bundle loaded successfully.

The repair removes the premature semicolon and attaches `.finally(...)` to the
promise chain. It preserves the existing endpoint, payload, messages, styles,
disabled state, and final button restoration. No CSS classes changed.

`DESIGN.md` was read fully before editing. The debugging/TDD workflow preserved
the current browser reproduction and a failing automated test before repair.

## Verification

`tests/test_jira_connector_controls.py` renders the actual current Jira template
and page-header macro with real vendored Lucide/DOMPurify, `core-admin.js`, and
the committed application stylesheets. Its minimal base-layout wrapper replaces
the surrounding navigation/authentication context. A loopback HTTP fixture
supplies empty connector configuration and a deliberately synthetic connection
test endpoint; it does not call the real connector service.

The initial 18-case matrix passed: Chromium, Firefox and WebKit, desktop
1440×1000 and mobile 390×844, successful responses, HTTP 400 errors, and explicit
connection-rejected responses. The expanded matrix exercises both ordinary
single-click and double-click gestures in all those cases.

Final expanded run: **36 passed, 1 warning in 86.63 seconds**, using
`python -m pytest tests/test_jira_connector_controls.py -q --tb=short` with
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. No tests skipped.

The first expanded run exposed a fixture scheduling error in Firefox's six
single-click cases: waiting on the loopback server's threading event blocked the
Playwright callback needed to forward that same local request. The harness now
intercepts only non-origin requests for denial, leaving loopback requests native.
This correction changed no application code and preserved all pending-state,
payload, response, and exactly-once assertions.

Each case verifies:

- no JavaScript page errors;
- the exact POST destination and JSON payload, using fixture-only URL, email
  and token values;
- the real Platform fetch wrapper's CSRF header;
- one request despite a double-click, with a disabled button and visible pending
  feedback while the fixture holds the response;
- visible success/error feedback, followed by an enabled button with its original
  label, demonstrating that `finally` executes;
- no requests outside the loopback fixture and no configuration-save POST.

The pre-fix focused test failed specifically with `Unexpected token '.'`.
Scoped correctness lint and whitespace checks passed. The only test-run warning
is the unused pytest `base_url` option when plugin autoload is disabled.

## Boundaries

These tests establish the current control behavior with actual page scripts and
ordinary browser input. They do not establish real Jira connectivity, production
credentials, configuration storage, full Flask authorization/CSRF enforcement,
or deployment. No runtime APIs were replaced and no forced clicks were used.
No actual Jira requests, real credentials, configuration saves, commits, or
deployments were performed.
