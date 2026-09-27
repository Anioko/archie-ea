# AI model selector note repair

## Scope and cause

`app/static/js/ai_chat/app.js` used the same `models.length < 2` branch
to reveal the template's “No AI models are configured” note for both zero
and one configured model. A hidden selector is appropriate when there is
no choice; a claim of zero models is not appropriate when there is one.

The bounded repair explicitly supplies separate zero/one notes. Zero says
“No AI models are configured.” One says “One AI model is configured —
responses use the platform default.” Neither asserts provider health.
Two or more models still expose the real choices. A list-loading failure
retains its separate error message. The note-only repair left selection/sending
unchanged; the subsequent F075 submit repair is documented below.
No template/classes/shared CSS or provider configuration changed.

## Behavioral verification

`tests/test_ai_model_selector_display.py` renders the complete production
`ai_chat/index.html` with a small replacement authenticated layout. It loads
the shipped core, modal, CSP evaluator/adapter, Alpine, Lucide, Markdown and
sanitizer assets, and every chat module from the template. Normal Settings
clicks, textarea input, Enter and select-option interactions exercise real
initialization, transport, composer payloads and streamed rendering. No copied
production function or runtime function replacement remains in the harness.

The initial one-model regression failed in Chromium, Firefox and WebKit:
**3 failed, 9 deselected in 34.74s**, each observing the false no-model note.
The zero-model regression also failed against the old default-response claim.

After the repair, the explicitly limited command
`python -m pytest tests/test_ai_model_selector_display.py -q -k 'model_count_note or failed_loading or chromium' --tb=short`
reported **17 passed, 10 deselected in 41.49s**: 12 all-engine display checks
and five Chromium composer checks. The ten deselections are NOT passes.
Default collection includes **27 tests** (0.66s). Targeted Ruff correctness
lint and `git diff --check` passed. This is limited evidence, not closure of
the unresolved Firefox transport regression or acceptance of the full harness.

The final harness serves deterministic HTTP fixtures through a real ephemeral
127.0.0.1 server. An initial Playwright-fulfilled SSE fixture produced a Firefox
native fetch NetworkError. Replacing it with real HTTP did NOT fix this failure;
neither did eliminating local request interception or using HTTP/1.1. The failure
must not be attributed solely to response interception. Test-server CSP confines
connections/assets to self (plus data assets); unexpected paths/requests fail the
harness. Contexts, server sockets and serving threads close on teardown.

Default collection retains all three engines for both display and composer.
The F075 follow-up adds ordinary Send-click cases alongside the existing 27
cases: 30 total. No opt-in, skip or xfail hides a failing engine. Root independent
review and real application/database qualification remain separate requirements.

Display scenarios cover zero, one, two models and failed loading in all engines.
Composer scenarios assert automatic `model: null` in each state and explicit
selection of a supplied second model. Every composer case rejects unexpected
navigation and extra/fallback requests rather than accepting a response-shaped
DOM fragment after the form has navigated away.

## F075 — Firefox native form navigation, diagnosed and repaired

Firefox's native fetch rejects `/ai-chat/message/stream` with
`TypeError: NetworkError when attempting to fetch resource.` The local server
records zero stream POSTs. The application's actual fallback then requests
`/ai-chat/message`; the strict fixture does not supply a successful fallback,
so the assertion fails and the unexpected path is reported. This is separate
from the now-correct note display. One reproduced failure took 18.42s.
The final retained node
`tests/test_ai_model_selector_display.py::test_default_composer_preserves_automatic_model[1-False-firefox]`
reported **1 failed, 1 teardown error in 23.36s**: no visible assistant response
and unexpected `/ai-chat/message`. Teardown closed the contexts/server/thread;
the teardown error is the deliberate unexpected-path assertion, not a leak.

The initial cause was unresolved; a subsequent bounded native-browser probe
established the production defect without replacing fetch or transport:

- Plain fetch, Headers-based fetch, fresh AbortSignal fetch, and the unchanged
  `ArchieChat.transport.streamMessage` each succeeded against the same Firefox
  loopback fixture. All four requests reached the server. The constructed
  request was same-origin, mode `cors`, signal `aborted: false`.
- Ordinary Send click produced one stream POST and a visible fixture reply,
  with no navigation. Ordinary Enter produced zero stream POSTs, the fallback
  request, then native navigation from `/` to `/?`.
- A passive submit listener observed `cancelable: false`, `defaultPrevented:
  false`, `isTrusted: false`, `bubbles: false`. Firefox also warned at the
  production Enter handler that untrusted submit events can submit forms.
  `new Event('submit')` cannot be canceled by the shared listener's
  `preventDefault()`, allowing Firefox's legacy default form action to navigate
  away and interrupt inference transport.
- Fresh red with a navigation assertion: the retained one-model Firefox case
  failed plus reported the unexpected `/?` navigation (**1 failed, 1 teardown
  assertion error in 28.90s**).

After explicit coordinator authorization, the three intentional chat-form
dispatch sites were changed to `chatForm.requestSubmit()`: Enter,
`askAIAboutEntity`, and the document panel's `ask-question` bridge. This uses the
normal cancelable submit event and validation while retaining the common
application submit listener. Other CustomEvents were not changed. No runtime
fetch replacement, header/prompt logger, or response interception remains in
the harness. The record-store persistence boundary is NOT simulated as proof:
these checks qualify actual frontend requests/rendering with deterministic HTTP
fixtures; real saved conversation persistence remains the enabled CI journey.

Follow-up verification:
`python -m pytest tests/test_ai_model_selector_display.py -q --tb=short`
reported **30 passed in 70.10s**: all model-display states, automatic and explicit
model payloads, ordinary Enter and ordinary Send, visible streamed fixture
answers, exactly one intended stream request, and no unexpected navigation in
Chromium, Firefox and WebKit. No case was skipped or deselected. Targeted Ruff
correctness lint and `git diff --check` passed. This supersedes the earlier
limited/failed harness results, not the separate pending real-DB qualification.

## Boundaries

Models, persona/domain seed data, session/approval/context/recommendation and
thread responses, and SSE reply text are disclosed test fixtures. They do not
prove a model exists outside the fixture or can answer a real user. No database,
provider API, credentials, billing, package installation, production access,
deployment or persistence qualification occurs here. The opt-in AI protocol
suite is untouched; full application/database qualification remains separate.
