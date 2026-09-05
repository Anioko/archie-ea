# Explicit enabled-AI protocol qualification

2026-09-05. Test-only implementation in `.worktrees/fortune500-readiness`.

## Delivered

- `tests/smoke/ai_protocol_stub.py`: stdlib ThreadingHTTPServer bound directly to
  127.0.0.1 on an ephemeral port. Accepts only `/v1/chat/completions`, the explicit
  dummy token, `ci-protocol-stub-v1`, and two known scenario markers. Chat requires
  streaming; page guide requires nonstreaming. Unknown scenarios/models/modes,
  authentication and routes fail explicitly. JSON includes usage; SSE emits
  multiple content chunks, a finish chunk and `[DONE]`. The thread-safe ledger
  records scenario, method, path, model, stream flag and HTTP status, not prompts
  or credentials. Shutdown closes the socket and joins the listener thread.
- `tests/smoke/conftest.py`: optional session fixture activates only for
  `SMOKE_AI_PROTOCOL_STUB=1`. It passes the loopback URL and invalid dummy key only
  to the app child, keeping pytest's existing provider-key isolation intact.
  Alternate provider primary/numbered/secondary keys remain empty and dotenv
  stays disabled. Loopback is added to NO_PROXY. Page guide is explicitly enabled;
  AI write approval remains required. Ordinary runs get no provider env changes.
  The enabled seeder rejects a database with existing enabled provider records,
  commits one APISettings row for the isolated smoke org, and registers cleanup
  by exact row/org/provider/label with before/after counts. The app subprocess
  cleanup is registered before boot checks so it closes before its provider
  fixture even if startup fails.
- `tests/smoke/test_ai_protocol_journeys.py`: two `ai_protocol` journeys using
  normal login, composer Enter, and actual AI Guide buttons. No browser API
  interception, forced/synthetic clicks, hidden element removal or production
  handler doubles. They assert actual streamed/nonstreamed application responses,
  the provider request ledger, visible replies, and persisted history after
  reload. Cleanup deletes the exact created conversation or guide scope through
  authenticated application endpoints. Browser console/runtime/HTTP errors fail.
  Missing explicit opt-in is a failure, not a skip.
- `tests/test_ai_protocol_stub.py`: nine local tests use the actual OpenAI SDK
  and real loopback HTTP. One starts a separate Python client with the returned
  child environment and checks its resolved base URL before any network call.

## Verification performed

The initial focused test failed because the explicit protocol helper was missing.
After implementation:

```
python -m pytest tests/test_ai_protocol_stub.py -q
9 passed in 16.76s

python -m pytest tests/smoke/test_ai_protocol_journeys.py --collect-only -q
2 tests collected in 0.19s

python -m ruff check tests/smoke/ai_protocol_stub.py tests/smoke/test_ai_protocol_journeys.py tests/test_ai_protocol_stub.py tests/smoke/conftest.py --select F,E4,E7,E9
All checks passed!

git diff --check -- tests/smoke/conftest.py
```

Helper coverage includes JSON/usage, real SSE parsing/termination, unknown
scenario, wrong model/mode, dummy-auth enforcement, unknown route, sanitized child
environment, actual SDK environment resolution in a subprocess, concurrency,
ledger copies and closed listener sockets. OpenAI SDK used locally: 1.109.1.
No external inference requests or provider billing were involved.

## Pending and limits

The **two actual browser/backend journeys have only been collected and linted**.
They have not run locally because this assignment has no local PostgreSQL.
Tenant provider visibility, full UI behavior, server persistence and exact-row
cleanup require the coordinator's real candidate-database CI invocation.
Marker registration, default-suite exclusion and explicit enabled CI invocation
are coordinator-owned. Existing no-provider tests and response allowances were
not edited; the enabled journeys do not inherit their console-503 exclusions.

The child uses an invalid bootstrap token before the seeded org exists, then the
tenant APISettings record resolves the explicit fixture model. Unexpected
background inference with a different model/scenario is rejected, not supplied
with a fabricated healthy response. Optional embedding/context initialization
can still try to load external/local model assets; this fixture does not make
those dependencies available or hide their errors. That outbound dependency risk
must be checked in the real enabled CI run. The initial scenarios return text
only and make no tool-call, architecture-advice, external model-quality or
production-availability claim. Usage figures belong to a deterministic fixture,
not measured paid-provider consumption.

Source inspection found a separate potential UI defect, not yet browser-verified:
`loadAvailableModels()` in
`app/static/js/ai_chat/app.js` hides its picker when fewer than two models exist,
and displays the same no-model note even when one model is configured. The
journey therefore verifies the real `/ai-chat/models` response and sends through
the ordinary default composer. It does not fabricate a second model or force a
hidden control. This unverified production UI finding was reported to the
coordinator and is outside the test-only edit scope.
