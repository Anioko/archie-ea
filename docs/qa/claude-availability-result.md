# F500-053 availability-contract result

Owned files: `tests/test_availability_response_contracts.py`, this report. No application code, probes, baselines, CI, or ledger were touched.

## Test run

```
python -m pytest tests/test_availability_response_contracts.py -q -p no:cacheprovider
12 passed, 0 failed, 0 skipped
```

## What the tests execute

The real `unified_ai_chat` and `application_mgmt` blueprints are registered on a bare `Flask` app, so the actual handler code runs through the Flask request cycle. Nothing else is booted: no application factory, no PostgreSQL, no Redis, no LLM provider.

Boundary doubles, all named inside the tests:

| Boundary | Double | Why |
|---|---|---|
| `LLMService._get_configured_provider` | raises `ValueError` (unconfigured) or returns a fixed provider/model pair (configured) | The real `FeatureFlagService` logic runs on top of it. No external LLM call is made or claimed. |
| `PageGuideService` | in-memory class that keeps the real `is_enabled` but stubs `get_history` | Avoids a database query in the enabled path. |
| `current_user` in `page_guide_routes` | plain object with `id` | `LOGIN_DISABLED` yields an anonymous user without an id. |
| `ElementTemplate.get_frameworks` | returns `[]`, a list, or raises `OperationalError` | Simulates empty seed, seeded, and backend failure. |

Not covered: real login and session handling (one test only checks the guard fires when `LOGIN_DISABLED` is off), tenant scoping, any real database row, and browser behaviour.

## Contracts pinned

| Endpoint | Condition | Status | Body signature |
|---|---|---|---|
| `GET /ai-chat/api/health/llm` | provider resolver raises | 503 | `status: unhealthy`, `error: LLM provider not configured`, all four `features` false, `hint` present |
| same | resolver returns provider | 200 | `status: healthy`, provider and model echoed |
| same | `AI_CHAT_ENABLED=True` but resolver raises | 503 | `features.chat` true, verdict still unhealthy |
| same | auth on, no session | 401 | `{"error": "Unauthorized access"}` from the blueprint handler |
| `GET /ai-chat/guide/history` | `AI_PAGE_GUIDE_ENABLED` unset, LLM configured | 503 | `error: service_unavailable`, `message: The page guide is not enabled.` |
| same | flag on, LLM unconfigured | 503 | identical body to flag-off |
| same | enabled, no query params | 400 | `errors` keyed by `page_key`, `scope_key` |
| same | enabled, unknown `page_key` | 400 | `error.code: VALIDATION_ERROR`, detail `Unsupported page guide context` |
| same | enabled, valid context | 200 | `success`, `messages`, `guide_mode: specialized` |
| `GET /dashboard/api/templates/frameworks` | no seed rows | 503 | `error: No frameworks available...`, `frameworks: []` |
| same | seeded | 200 | bare JSON array |
| same | `OperationalError`, XHR header | 500 | `success: false`, `error: Database error occurred...`, no `frameworks` key |

## Findings

1. **Page guide 503 does not distinguish flag-off from LLM-missing.** `PageGuideService.is_enabled` already ANDs the flag with the chat feature, so `_feature_guard` returns "The page guide is not enabled." in both cases and its `require_ai_for_route` branch is unreachable from these routes. Operators reading the probe cannot tell which to fix. Not changed here; reported for Codex.
2. **Two validation envelopes on one route.** Schema failures return `{"success": false, "errors": {...}}`; registry failures return `{"success": false, "error": {"code": "VALIDATION_ERROR", "details": [...]}}`. Both are 400 and both stay visible once enabled, so the probe must accept either shape.
3. **Frameworks backend failure is not a 503.** The handler has no try/except; the blueprint's `DatabaseError` handler returns JSON 500 for XHR callers and a redirect for non-XHR callers. A probe without the `X-Requested-With` header would see a 302, not a 500.
4. **LLM health is auth-gated.** The 503 body is only reachable after login, so an unauthenticated probe sees 401 and never observes the availability state.

## Next integration plan (Codex-owned)

Classify a probe hit as **expected unavailable** only when all of the following hold. Anything else is a genuine failure.

| Endpoint | Expected-unavailable signature | Genuine failure |
|---|---|---|
| `/ai-chat/api/health/llm` | 503 and `status == "unhealthy"` and `error == "LLM provider not configured"` | 500, 502, 504, timeout, 503 with a different body, or 401 when the probe is supposed to be logged in |
| `/ai-chat/guide/history` | 503 and `error == "service_unavailable"` and `message == "The page guide is not enabled."` | any 5xx with another body; 400 when the probe sent a valid registered `page_key` and `scope_key` |
| `/dashboard/api/templates/frameworks` | 503 and `frameworks == []` and the seed step was intentionally skipped in that environment | 503 after seeding ran; 500 JSON with `Database error occurred`; 302 redirect on an API call |

No blanket 503 allowlist and no baseline increase. Match on body, not status.

Real configured browser tests still needed, none of which this task performs:

- Log in as a real user with a configured provider and confirm `/ai-chat/api/health/llm` returns 200 with the actual provider name. This is the only way to verify the provider path.
- With `AI_PAGE_GUIDE_ENABLED=true` and a configured provider, open a registered page (for example the dashboard overview), open the guide, and confirm history loads with a real user id and rows persist and clear.
- Against a database where the framework seed has run, confirm `/dashboard/api/templates/frameworks` returns the seeded array and that the template picker renders it.
- Confirm the unauthenticated 401 on the health endpoint is what the front end expects, since the blueprint returns JSON rather than a login redirect.
