# Page Guide saved-history availability investigation

Read-only source investigation; no implementation, provider calls, database
access or existing note/harness edits. Proposed design awaits coordinator approval.

## Finding

`app/modules/ai_chat/routes/page_guide_routes.py:23` applies the same
`_feature_guard()` to history GET, history-clear POST and message POST.
`PageGuideService.is_enabled()` (service line 91) combines the guide flag with
`FeatureFlagService.is_ai_enabled('chat')`. When chat has no explicit config
override, that method falls back to provider/model configuration detection.
Consequently removing provider configuration blocks existing-history reads and
deletion with 503, although both service operations only query/delete saved rows.

`get_history()` and `clear_history()` filter by current authenticated user ID
and the generated guide session ID (page plus scope). Generation alone calls
`LLMService.generate_from_prompt()`. Saved history does not need inference,
live-context generation or embeddings computation.

## Exact configuration distinction

- `AI_PAGE_GUIDE_ENABLED`: `config.py:359` parses the environment using
  `_env_bool(..., False)`. False/missing means the administrator has not enabled
  this optional feature. Preserve denial of read, clear and generation.
- `AI_CHAT_ENABLED`: `FeatureFlagService` reads **Flask app config**, not
  `os.environ`. There is no corresponding environment mapping in `config.py`.
  Explicit false disables chat. None/missing currently means automatic detection
  of provider/model configuration, not an administrator disable.
- Explicit true currently overrides configuration detection entirely. Therefore
  the existing `require_ai_for_route('chat')` is not sufficient by itself to
  guarantee that generation has a provider when `AI_CHAT_ENABLED=True`.
- No generic database FeatureFlag row is consulted by these guards. Do not
  silently substitute that separate feature-flag system.

## Recommended bounded split (not implemented)

1. Make `PageGuideService.is_enabled()` describe policy: guide flag is enabled
   and chat config is not an explicit falsy non-None override. None/missing chat
   config allows saved-record access. Preserve existing typed config semantics;
   do not interpret an arbitrary string such as `"false"` as a new config API.
2. Split route guard policy from provider readiness. History read/clear require
   policy only. Message generation requires policy **and** an independent
   configured-provider/model check, including when chat config is explicitly
   true. Preserve truthful structured 503 errors for generation; do not return
   a fake successful answer or change global FeatureFlagService semantics.
3. Keep authentication, schema/page-registry validation, audit decoration and
   per-user/session filters unchanged. `ChatMessageEmbedding` has no tenant
   mixin/organization column; isolation here relies on authenticated user ID,
   not an implied organization predicate. Verify cross-user/org denial with real
   records before claiming tenant coverage. Scope IDs must not be broadened.

Changing policy semantics of `is_enabled()` also keeps the guide drawer visible
during provider absence: both admin/composer layouts gate its inclusion on the
context processor's `enabled` value, and page_guide.js exits when it is false.
A route-only fix leaving `is_enabled()` unchanged would permit API access but
leave saved history unreachable through the normal UI. Existing generation
errors remain visible if sending is attempted without a provider; a dedicated
read-only composer/status treatment is an optional separate UI follow-up, not
a reason to withhold saved records.

## Approval/verification constraints

The current no-database contract test
`test_page_guide_history_503_when_flag_on_but_llm_unconfigured` in
`tests/test_availability_response_contracts.py` explicitly pins today's coupling.
It must be replaced with the new saved-record contract, not weakened by broadly
allowing 503s. Its enabled service double also mirrors `is_enabled()`.

Required matrix: guide disabled and chat explicitly disabled deny every route;
guide enabled/chat None or true/provider absent allow history read/clear but
deny generation; configured provider permits generation without bypassing
policy. Verify malformed/unknown scope, unauthenticated request, another user
and organization, correct read/delete counts, and no LLM lookup/generation from
history paths. Database persistence/tenant tests cannot run locally here and
remain required in CI. Existing enabled protocol journeys are separate evidence.
