# Chat context lifecycle and response contract

Date: 2026-09-05. Candidate source repair; shared bundle rebuild and final CI qualification belong to the parent.

## F082: proven cancellation misclassification

The chat initializer calls persona synchronization and then loads domain context. Persona synchronization also loads its default domain when it changes, so an architecture persona starts two background requests. `panels.js` previously owned no cancellation lifecycle. `Platform.fetch` discarded caller `signal` options and classified every native fetch rejection as a network outage.

Read-only reproduction used the real rendered chat template, shipped JavaScript and native browser fetch against delayed loopback HTTP responses. WebKit reload with two pending architecture responses reproduced the exact CI text `Network error /ai-chat/context/architecture TypeError: Load failed`; Playwright identified both requests as `Load request cancelled`, with no HTTP error response. Settled controls were clean. Firefox produced `NS_BINDING_ABORTED` request failures but did not reproduce its CI console text locally, even when replacement HTML was delayed two seconds. Close-only probes produced no captured browser error. These results demonstrate the lifecycle defect, not that every CI error has the same cause.

The candidate forwards an explicit AbortSignal through Platform.fetch. A rejection is left intact and avoids outage notification only when that signal is actually aborted and the native failure is AbortError or that signal's exact cancellation reason. Ordinary failures still report through the existing network/HTTP paths. Explicit null cancellation preserves the browser-native rejection (null in Chromium/Firefox, AbortError in WebKit), rather than replacing it with an incidental TypeError. Loading start/stop and CSRF behavior are retained.

The context panel owns one pending request: it shares concurrent same-domain requests, cancels superseded requests, cancels on beforeunload/pagehide, reloads on persisted pageshow, and checks request/target identity before rendering. The startup calls in app.js remain intact; deduplication at the owner prevents the duplicate request without removing necessary initialization. Cancellation is handled only for that owner's operation; no global AbortError/TypeError suppression, silent option, runtime fetch replacement, retry, or smoke assertion weakening was introduced.

## F084: context response contract

The backend returns `{success: true, context: ...}`. Architecture data is `context.architecture_elements`; technology data is `context.technology_stacks` with `total_stacks`. The former renderer expected top-level `elements`/`applications`, making real populated responses look empty.

The candidate unwraps that envelope, renders architecture elements and truthful read-only technology stack cards, and distinguishes empty lists from malformed collections and backend error objects. The technology loader supports focused application context, not focused technology-stack selection: stack cards therefore have no fake application label or dead selection action. Existing direct element/application response compatibility remains separate. Recorded names and descriptions are escaped before insertion so enabling real data rendering cannot turn their contents into markup.

## Files and validation

Owned source changes:

- `app/static/js/core/03-fetch.js`
- `app/static/js/ai_chat/panels.js`
- `tests/test_ai_context_lifecycle.py`

No generated bundle, app.js, production data, external AI provider, deployment or commit was changed by this worker. The test serves the core bundle rendered in memory by the repository's existing `scripts/build_js.py.render`, preserving the real source/load order without overwriting shared generated files. Parent must run `python scripts/build_js.py` and verify the resulting shipped bundles.

Red evidence:

- Original renderer: populated architecture was displayed as empty; a delayed old architecture response overwrote the newest technology panel. Four focused cases failed before implementation.
- Original fetch wrapper: explicit abort left the pending operation unsettled (3-second assertion failed).
- First candidate: the parent identified that technology's initial test control used the legacy application shape. Changing it to the actual technology_stacks envelope reproduced the remaining empty-state defect; this was repaired before claiming canonical technology coverage.
- First candidate's null cancellation reason became TypeError; a focused native-fetch test reproduced it before the null-safe comparison was applied.

Verification commands:

- `node --check app/static/js/core/03-fetch.js`: passed.
- `node --check app/static/js/ai_chat/panels.js`: passed.
- `python -m ruff check tests/test_ai_context_lifecycle.py --select F,E4,E7,E9`: passed.
- `git diff --check -- app/static/js/core/03-fetch.js app/static/js/ai_chat/panels.js`: passed.
- `python scripts/check_raw_fetch.py`: passed, zero sites.
- `python scripts/check_design_tokens.py --count`: passed, zero violations.
- First candidate browser suite: 27 passed; this predates the canonical technology/strict post-close expansion and is not its qualification result.
- Expanded canonical suite before the final cross-engine expectation correction: 44 passed, 1 failed in 144.70s. The sole failure required null rather than WebKit's native AbortError for abort(null); it was a test expectation error, not a fabricated success or hidden network failure. The corrected test accepts only those two native rejection outcomes, and the parent owns its fresh independent 45-case run.
- `python -m pytest tests/test_ai_model_selector_display.py -q --override-ini addopts='' -k default_composer --maxfail=2`: 12 passed, 18 deselected in 50.89s. Its existing loopback server emitted connection-reset traces during teardown; pytest exited zero. These controls began before the parent's shared bundle rebuild and are not a post-build qualification claim.

The parent reports that all three shared core bundles were subsequently rebuilt and `--check` passed. No production source edits followed that rebuild; only the native WebKit cancellation test expectation and this report changed.

Remaining limitations: local Windows Firefox did not reproduce the exact Linux CI console representation; the guide's opaque Object error remains unclassified. This candidate does not close either proof gap or claim enabled-AI CI is green. Shared generated bundle build, complete repository gates and final CI remain the parent's responsibility.

Parent independent final verification: 45 browser cases passed with no skips in
123.27 seconds. All three core bundles were rebuilt and their freshness check
passed. The full-app CI and deployed limitations above still apply.
