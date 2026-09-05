# Enabled-AI browser qualification: investigation

2026-09-05. Read-only investigation of `.worktrees/fortune500-readiness`.
No provider requests, credentials, production access, configuration changes,
package installation, database changes, or test execution were performed.

## Recommendation

Use an explicitly selected, isolated CI qualification run with a local
OpenAI-compatible HTTP protocol stub. Both current chat transports and the page
guide can reach that stub through the existing OpenAI SDK `OPENAI_BASE_URL`
configuration. No production provider-routing change is necessary for this path.

This qualifies the enabled UI, application backend, provider HTTP serialization,
stream parsing, and persistence. It does **not** qualify an external provider's
availability, model reasoning, architecture advice, latency, billing, tool-choice
quality, or production credentials. Response text and artifacts must identify
the run as deterministic protocol qualification.

## Evidence and current configuration

| Evidence | Implication |
|---|---|
| `tests/smoke/conftest.py:110` starts a separate `manage:app` subprocess, using gunicorn with 2 workers/8 threads on CI and Flask on Windows. It copies the process environment before startup. | Patching LLMService in the pytest process does not patch the live browser server. A real localhost listener is reachable by every worker. |
| `tests/smoke/conftest.py:80` requires an explicit TEST_DATABASE_URL and rejects a different DATABASE_URL. `seeded` depends on live_server and commits a separate smoke organization and users after server startup. | Keep the candidate database isolated. Provider rows inserted in an uncommitted shared db_session fixture would be invisible to the subprocess. |
| `tests/conftest.py:29` blanks primary, numbered and secondary credentials for nine provider families, plus LLM_API_KEY and AZURE_OPENAI_API_KEY; it sets PYTHON_DOTENV_DISABLED=1. | Preserve this isolation. A CI environment API key supplied before pytest collection is deliberately erased. Introduce only an obviously invalid, non-secret stub token after isolation, preferably only in the child environment. |
| `config.py:359` parses AI_PAGE_GUIDE_ENABLED with `_env_bool`, default false. | Set AI_PAGE_GUIDE_ENABLED=true in the child environment before its config module imports. |
| `app/services/feature_flag_service.py:31` reads AI_CHAT_ENABLED from Flask config, then falls back to the real provider resolver. No AI_CHAT_ENABLED environment mapping was found in config.py. | Merely exporting AI_CHAT_ENABLED=true does not enable chat here. Prefer actual configured-provider resolution over a route-gate override. |
| `PageGuideService.is_enabled`, `app/modules/ai_chat/services/page_guide_service.py:91`, requires both the page-guide flag and chat availability. | Setting either alone is insufficient. Its answer path calls generate_from_prompt with use_cache=False, then persists both messages. |
| `LLMService._get_configured_provider`, `app/modules/ai_chat/services/llm_service_impl.py:180`, resolves preferences, tested DB records, enabled DB records, and environment bootstrap configuration. OpenAI has first provider priority. | One explicitly configured OpenAI fixture avoids model/provider ambiguity. Inspect the candidate fixture database for unexpected usable settings; do not assume env isolation also isolates existing DB credentials. |
| `LLMService._get_all_api_keys`, same file at 1512, loads enabled DB credentials, suppressing environment key fallback if a DB record exists; it otherwise includes primary/numbered/secondary env keys. | Do not combine a blank or disabled DB OpenAI record with an env-only stub setup. Keep all alternate provider keys empty and do not seed alternate providers. |
| `_call_openai`, same file at 1956, constructs OpenAI(api_key=...). AgentRunner at 829/859 constructs OpenAI(api_key=..., base_url=None, timeout=90) for provider=openai. | Both synchronous guide generation and agent streaming/nonstreaming use the SDK default URL resolution. |
| Locally inspected installed OpenAI SDK 1.109.1 constructor: when base_url is None it reads OPENAI_BASE_URL, then defaults to the external URL. requirements.txt:89 permits openai>=1.0.0,<2.0.0. | OPENAI_BASE_URL=http://127.0.0.1:<bound-port>/v1 is the existing seam. Reconfirm it with the dependency version installed by CI through a transport contract test. No external lookup was needed. |

`app/services/llm_service.py` re-exports the same canonical LLMService used by
AgentRunner/PageGuideService. The old comment in `tests/test_ai_chat_stream_error.py`
claiming those imports reference different classes is stale; that test still
demonstrates an in-process gate/method-mocking pattern, not live-server transport.

## Minimal fixture design

Introduce a test-only session fixture behind an explicit option, for example
`--ai-protocol-stub` (proposed, not currently implemented). It binds a stdlib
ThreadingHTTPServer directly to `127.0.0.1:0`, starts its thread, returns the exact
bound URL and a thread-safe request ledger, and shuts down after the app server.
Let live_server depend on it and merge only the returned child-environment
settings. Do not patch production request handlers or intercept browser API calls.

The enabled invocation needs:

| Setting | Proposed value/purpose |
|---|---|
| TEST_DATABASE_URL and DATABASE_URL | The same disposable candidate PostgreSQL database, as current smoke harness requires. |
| FLASK_CONFIG | testing, already the smoke default. |
| SECRET_KEY | Existing deterministic test-only value for real browser sessions and CSRF. |
| OPENAI_BASE_URL | Exact fixture URL with `/v1`; reject non-loopback fixture configuration. |
| OPENAI_API_KEY | A non-secret invalid external token such as `ci-protocol-only`, injected only into the app child. This makes bootstrap feature state consistent before `seeded` exists. |
| AI_PAGE_GUIDE_ENABLED | true in the child environment before boot. |
| PYTHON_DOTENV_DISABLED and all alternate provider key values | Preserve current disabled/empty isolation, including numbered and secondary key variants. |
| REQUIRE_AI_APPROVAL | Keep true; initial protocol replies contain no tool calls. |
| SMOKE_BROWSER / SMOKE_REQUIRE_BROWSER | Select each intended engine explicitly and require its binary, as current smoke infrastructure supports. |

For a clearly labelled selectable model, extend only the enabled test's seeding
with one committed `APISettings` row in `seeded['ids']['org']`:

```
provider='openai'
key_label='ci-protocol-stub'
api_key='ci-protocol-only'
enabled=True
default_model='ci-protocol-stub-v1'
organization_id=<isolated smoke org>
test_status=None
last_tested_at=None
```

These fields are defined at `app/models/models.py:1087`. No new DB column is
needed. `custom_endpoint_url` is not the OpenAI URL setting; leave it unused.
`max_tokens` and `temperature` have model defaults and are not required for
selection. Do not set test_status='success' as fabricated evidence of an external
provider test. The model picker accepts configured model strings through
`chat_core.py:107` and displays the deliberately named fixture model.

APISettings keys use `_EncryptedString`; `ARCHIE_KEY_SECRET`, when present, must
be identical in the seeder and server. A fresh test-only key or absent setting is
sufficient for this invalid test token. Never copy a production encryption key.
Cleanup must use the recorded row/org/user IDs, or discard the dedicated database.

The env-only variant is smaller and already supported by model-list fallback,
but displays a real default model ID from model_defaults.py despite hitting a
stub. The explicit DB fixture is preferable for clarity and tenant-scoping tests.

## HTTP protocol required

One route is sufficient for the initial scope: `POST /v1/chat/completions`.
The stub must check the dummy Authorization header, the expected fixture model,
and nonempty messages; reject unknown paths/models/scenarios instead of returning
generic success. Match a unique test marker in the supplied user message/prompt,
not the global call number: gunicorn workers, retries and other initialization
requests can arrive concurrently.

For nonstreaming requests, return a complete chat-completion object: id,
object='chat.completion', created, model, choices with index=0,
message={role:'assistant', content:<marked fixture text>}, finish_reason='stop',
and usage with prompt_tokens, completion_tokens, total_tokens. LLMService reads
usage.prompt_tokens and usage.completion_tokens directly, so omitting them is
not a faithful protocol fixture. Its cost calculations may create estimated
test usage; no external billing takes place, and those estimates are not measured
provider costs.

For stream=true, use HTTP 200 `text/event-stream`, write and flush several
`data: {...}\n\n` OpenAI chat.completion.chunk frames with choices[0].delta.content,
then a finish_reason='stop' chunk and `data: [DONE]\n\n`. Keep choices nonempty:
AgentRunner currently indexes chunk.choices[0]. An empty usage-only final chunk
is a separate edge-case test, not part of the happy-path fixture. Initially omit
tool_calls so the real agent reaches its ordinary final-text branch. Tool-call
qualification later needs its own explicit scripted tool exchange and approvals;
a text-only reply cannot prove tool execution.

The stub ledger should record scenario, path, method, model, stream flag and
request/result counts. Assert that each browser action reached this listener and
that the expected transport was used. Avoid full prompt dumps in routine CI
artifacts. A configured health response alone is insufficient: `/ai-chat/api/health/llm`
only inspects configuration (`legacy_compat.py:156`), not live inference.

## Browser/backend journeys and data contracts

1. Sign in normally as a seeded architect. `/ai-chat/models` must contain the
   explicit fixture model and `/ai-chat/api/health/llm` must reflect that real
   configuration. Send through the visible composer. The default UI calls
   `POST /ai-chat/message/stream`; verify actual provider stream frames become
   visible assistant text and that the application SSE emits a done event with
   a thread_id. The application stream remains real: it translates tokens and
   persists turns (`chat_core.py:836`).
2. Verify nonstreaming `POST /ai-chat/message` with the same real provider
   listener. ChatMessageSchema requires message and accepts domain='general',
   model, persona, solution_id and optional thread_id handled by the route.
   Do not fabricate an unknown request property or intercept the route. Reload
   the browser/history and confirm the recorded user/assistant exchange remains.
3. Open an actual seeded application detail page and click `#page-guide-trigger`.
   The context processor must produce enabled context and the real drawer must
   show it. The registry maps this page to page_key='applications.detail' and
   scope_key='applications.detail:<application id>' (`page_guide_registry.py:474`).
   Submit through `#page-guide-form`; it sends page_key, scope_key, page_title,
   message to `/ai-chat/guide/message`. Verify visible fixture text, then
   `/ai-chat/guide/history` and a reload. Clear using the actual drawer control
   and `/ai-chat/guide/history/clear` and verify that scoped history is empty.
4. Add a second user/scope only when asserting isolation: the guide history
   filters user_id and constructs a scope-based session key; no alternate user
   should see another's seeded conversation. Run negative provider scenarios
   explicitly and assert visible failure and state recovery, with a distinct
   expected failure contract. Never classify arbitrary 503 responses as healthy.

Guide payload length limits and required context fields are defined in
`app/schemas/api_schemas.py:272`. Existing tables needed include APISettings,
users/organizations, chat_message_embeddings, conversation_threads and
conversation_messages. The guide stores text without computing embedding vectors
(`page_guide_service.py:165`); vector data is not required for this scenario.
Chat's conversation-history service optionally initializes ChromaDB and a local
SentenceTransformer when installed (`conversation_history.py:78`). Offline
assets/network isolation therefore still need to be verified in the enabled
candidate run; a protocol stub does not prove all unrelated startup/context
dependencies avoid outbound traffic. DB, prompt-context and persistence failures
must remain failures, not be replaced by healthy stub responses.

## Existing reusable tests and constraints

No LLM HTTP protocol stub was found in tests/ or scripts/: searches for
OPENAI_BASE_URL, chat/completions, ThreadingHTTPServer and HTTPServer found only
unrelated local HTTP fixtures such as
`tests/test_production_readiness_control_outcomes.py:13` and CSP asset servers.
That stdlib server lifecycle is reusable, but its HTML/status fixture is not an
AI response implementation. Existing AI tests patch methods in-process or
intercept individual browser responses; neither proves the subprocess-to-provider
HTTP path.

Run enabled qualification as a **separate explicit pytest/CI invocation**.
`tests/smoke/test_ai_chat_journey.py` intentionally asserts the no-provider banner
and currently has a broad console-503 exclusion; turning on a provider for that
entire suite would change its premise. The enabled run must use strict
URL/status-specific assertions and must not inherit that exclusion. Retain
unconfigured-state coverage as its own scenario. Proposed fixtures/flags and
journeys above have not been implemented or executed by this investigation.

The smallest implementation surface is a test-only protocol server/helper, an
explicit opt-in child-env/seed fixture seam, dedicated enabled journeys, and one
isolated CI invocation. Production files need not change merely to make those
paths testable. Additional defects exposed by actual execution must be diagnosed
and repaired separately, not accommodated by broader fake responses or allowances.
