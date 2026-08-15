# AI-governance wave: closing four deferred items

Worktree: `C:\Users\A4821420\Downloads\archie-oss\.worktrees\gov-close`
Branch: `feat/ai-gov-close`
Commit: `160fdab867ca0fceaa1c85cedc25a2ce03cfcf28`

## ITEM 1 — `generate_blueprint_narrative` silent no-op

**Finding: a real implementation existed, but only as inline logic inside a Flask
route, not as an importable function under the name/path the tool was importing.**

The tool executor
(`app/modules/ai_chat/tools/executor.py::_tool_generate_blueprint_narrative`) imported
`generate_section_narrative` from
`app.modules.solutions_strategic.v2.routes.solution_blueprint_routes` — a module/name
that has never existed. The real narrative-generation logic (LLM prompt assembly +
call + persist to `solution.section_narratives[section_id]`) was inline in the view
function `api_generate_section_narrative` in
`app/modules/solutions_strategic/v2/routes/solution_design_routes.py`, gated by
`@login_required` and using flask_login's `current_user` / `jsonify` directly — not
callable from a non-request context as-is.

**Fix**: extracted the logic into a standalone
`generate_section_narrative(solution_id, section_id, user_id)` (same file), raising a
new `NarrativeGenerationError(message, error_code)` on any handled failure
(`INVALID_SECTION`, `NOT_FOUND`, `FORBIDDEN`, `NO_LLM`, `LLM_ERROR`) instead of
building a `jsonify` response. `_check_solution_access` was widened to accept an
explicit `user` argument (default `current_user`, so all ~40 existing route call
sites are unaffected) so the access check works without an HTTP request. The route
`api_generate_section_narrative` now delegates to the shared function and maps
`NarrativeGenerationError.error_code` to an HTTP status.

The executor now imports `generate_section_narrative` and `NarrativeGenerationError`
from the correct module, calls the former with `self.user_id`, and replaces the bare
`except Exception` with: `ImportError` → honest `"error_code": "UNAVAILABLE"`;
`NarrativeGenerationError` → honest `{"success": False, "error", "error_code"}`
(logged as a warning, since it's an expected/handled case); any other exception →
logged via `logger.exception` and a generic `"INTERNAL_ERROR"` — no branch reports
fabricated success.

**Wiring evidence**: `app/modules/ai_chat/tests/test_copilot_tools.py::TestGenerateBlueprintNarrativeTool`
(new, 3 tests) mocks `generate_section_narrative` at its real import location and
asserts it is called with `(solution_id, section_id, user_id)`, that a
`NarrativeGenerationError` surfaces as an honest structured error (not silent
success), and that an import failure returns `"error_code": "UNAVAILABLE"` rather than
being swallowed.

## ITEM 2 — value-stream capability derivation partial-failure edge

`app/modules/capabilities/services/value_stream_ai_service.py::_org_scoped_capability_names`
previously only raised `CapabilityCatalogUnavailableError` when *both* underlying
queries failed. Changed the rule to: raise when *any* query failed **and** the
combined name set is empty (can't distinguish empty-because-broken from
genuinely-empty); if a query fails but the other query returns real names, proceed
with the partial-but-real set and log a `logger.warning` naming which source failed.

Split the two queries into `_vs_mapped_capability_names(limit)` and
`_app_mapped_capability_names(limit)` so each failure mode is independently
mockable in tests.

New tests in `tests/test_business_arch_ai.py`:
- `test_ai_suggest_mappings_one_source_failed_other_has_names_is_200` — the
  application-mapping query raises, the value-stream-mapping query returns a real
  name; asserts `200` with the real suggestion (not an error, not the "map one
  manually first" 200).
- `test_ai_suggest_mappings_one_source_failed_other_empty_is_honest_error` — the
  value-stream-mapping query raises, the application-mapping query is genuinely empty
  for this org; asserts a `500`/`502` honest error, not the "map one manually first"
  200 (which would misdiagnose a broken query as an empty catalog).

The pre-existing `test_ai_suggest_mappings_catalog_query_failure_is_honest_error`
(both-fail case) still passes unchanged.

## ITEM 3 — `REQUIRE_AI_APPROVAL` default flipped to `true`

`config.py:239` (`Config.REQUIRE_AI_APPROVAL`) now defaults `"true"` when the env var
is unset, with an expanded comment explaining the scope of the flag and the
slash-command exemption (see Item 4).

**Pre-flip audit**: grepped the whole `tests/` tree and `app/modules/ai_chat/routes/workflow_routes.py`
for `workflow_routes`, `/ai-chat/data/`, `data/create-capability`, `apply-archimate`,
`apply-apqc`, `generate-archimate`, `bulk-process`, `entities/suggest`, and
`REQUIRE_AI_APPROVAL` — **zero existing tests exercise any of the seven
`@require_ai_approval`-decorated endpoints in `workflow_routes.py`**, so nothing in
the pre-existing suite assumed the gate was off. `approval_gate.py` was read in full:
when the config flag is true, `require_ai_approval` short-circuits before the
decorated view body runs and returns `202 {"status": "pending_approval", "message",
"action", "payload", "ai_originated": true}`; when false, it tags the action
(`tag_ai_action`) and runs the view normally.

**Test-by-test decisions**: no existing test needed updating (none touched these
routes). Added new tests instead, in `tests/test_ai_write_approval.py` under
`TestRequireAIApprovalDefaultsOn`:
- `test_config_default_is_true_when_env_unset` — reloads `config` with the env var
  unset and asserts `Config.REQUIRE_AI_APPROVAL is True`.
- `test_create_capability_returns_202_pending_approval_by_default` — hits
  `POST /ai-chat/data/create-capability` with the flag on; asserts `202`,
  `status == "pending_approval"`, `ai_originated is True`, and that nothing was
  written.
- `test_create_capability_writes_directly_when_flag_off` — same endpoint with the
  flag explicitly set `False`, proving the pre-Aug-2026 direct-write behaviour is
  still reachable as an operator opt-out, not deleted.

**The command_parser check at (old) line 1038**: read `_handle_link_capability` in
full. It had its own separate `current_app.config.get("REQUIRE_AI_APPROVAL", False)`
check that returned a `"...has been submitted for review"` message and a
`"pending_approval": True` flag — but **never actually created any approval record**;
it was a fabricated-success response with no backing queue entry. Flipping the
default would have made every `/link-capability` invocation hit this dead branch and
silently stop writing anything, while claiming a review had been requested that
never happens. Per the task's guidance, this is exactly the case where Item 4's
user-typed-command rationale applies: **removed the check** (rather than wiring it up
to a real queue that doesn't exist) and replaced it with the governance-note comment
described in Item 4. `_handle_generate_from_capabilities` never had a
`REQUIRE_AI_APPROVAL` check at all — it already wrote directly, consistent with the
same rationale, and got the same explanatory comment for symmetry.

## ITEM 4 — slash-command exemption rationale, documented

Added governance-note comments at both write sites in
`app/modules/ai_chat/services/command_parser_service.py`:
- `_handle_link_capability` (~line 1036, where the old fake approval-check used to
  be, immediately before `SolutionCapabilityMapping(...)` is constructed).
- `_handle_generate_from_capabilities` (~line 849, immediately before the
  ArchiMate-element generation loop that writes `ArchiMateElement` /
  `SolutionArchiMateElement` rows).

Both comments state the same reconciled rationale: these commands are parsed
verbatim from the user's own typed chat message — deterministic, not LLM-initiated —
so a prompt-injected document cannot type a slash command, and they execute directly
regardless of `REQUIRE_AI_APPROVAL`, which remains the opt-in belt-and-braces gate for
the LLM-agent-initiated paths (the `/ai-chat/data/*` endpoints and the mutating-tool
queue). `config.py`'s `REQUIRE_AI_APPROVAL` comment cross-references this decision.
New test `TestSlashCommandsExemptFromApprovalGate::test_link_capability_writes_directly_with_approval_flag_on`
in `tests/test_ai_write_approval.py` pins it: with the flag explicitly `True`,
`_handle_link_capability` still writes the `SolutionCapabilityMapping` row directly
and the response contains no `pending_approval`/"requires approval" text.

## Test output

```
tests/test_business_arch_ai.py tests/test_ai_write_approval.py \
  app/modules/ai_chat/tests/test_copilot_tools.py
  => 68 passed

python scripts/verify.py --gate compile --gate boot-health --gate template-syntax
  => 3 passed, 0 failed, 0 skipped

python scripts/verify.py --tag static
  => 23 passed, 0 failed, 1 skipped (css-build — no vendored Tailwind CLI locally,
     expected/pre-existing per CLAUDE.md)
```

One static-gate regression was caught and fixed during this wave: the new
`User.query.get(user_id)` in the extracted `generate_section_narrative` tripped
`tenant-scoping` (User is a tenant-owned-but-unmixed model). Annotated
`tenant-scoping-ok` inline with a comment explaining that cross-org access is closed
by the immediately-following `_check_solution_access(solution, user=user)` call, not
by an org filter on this lookup — re-ran the gate to confirm `[0 <= 0]`.

## Commit

`160fdab867ca0fceaa1c85cedc25a2ce03cfcf28` — `feat(ai-gov): approval-by-default for
the data API, and no more silent no-ops`. 8 files changed (all real source/tests;
the worktree's stale `.pyc` files under `app/templates/macros/__pycache__/` were
deliberately left unstaged — not part of this change).

## Not done / left as-is (in scope for review, not fixed here — superseded, see below)

- Did not modify `app/modules/ai_chat/routes/workflow_routes.py` itself — its seven
  `@require_ai_approval` decorators already do the right thing once the config
  default flips; no code change was needed there, only the default and tests.
- Did not attempt to build a real approval-queue entry for `/link-capability` (the
  fake one that was removed) — out of scope for this wave; the exemption rationale
  means it doesn't need one, per Item 4.

---

# Fix round 2 — the data-API gate now queues real approvals

**Review verdict on the first pass: 1 Critical in Item 3, other three items approved
as-is.** The critical: `require_ai_approval` (`app/modules/ai_chat/approval_gate.py`)
returned `202 {"status": "pending_approval"}` without ever persisting an approval
record — no `approval_id`, nothing in `GET /ai-chat/approvals/pending`, and the write
was silently dropped forever. With the default flipped to `true`, the seven
`/ai-chat/data/*`-family endpoints became black holes the moment anything called
them. This section documents the fix.

## What changed

`app/modules/ai_chat/approval_gate.py` — replaced the bare `@require_ai_approval`
decorator with `queue_ai_write(operation_type, entity_type, payload, summary,
entity_id=None)`, called **inline from inside the view body** rather than wrapping
the whole function. When `REQUIRE_AI_APPROVAL` is true it calls
`AIChatApprovalService.create_pending_approval(...)` and returns a `202` carrying the
**real** `approval_id`; when false, it tags the action via `tag_ai_action` (as the old
decorator did) and returns `None`, telling the caller to proceed with the write
itself.

**Why inline, not a decorator with parameters**: several of the gated routes
validate/sanitize `request.get_json()` (HTML-escaping via `sanitize_html`, enum
checks, length limits) *before* calling the service. A decorator wrapping the whole
view only ever sees the raw, unvalidated body — queuing that would mean an approved
write later runs unsanitized input through the same path the direct route
deliberately protects (a real, if narrow, stored-XSS-shaped gap in the create-capability
`name`/`description` fields). Calling `queue_ai_write()` after validation, with the
already-validated `data` dict as the payload, means the queued approval is
byte-for-byte identical to what the route would have written directly — this was
caught while doing the "verify end-to-end" step the review asked for, not called out
in the original ask, so flagging it here explicitly.

## Route-by-route: wired vs. exempted

Read `ai_chat_approval_service.py::approve_and_execute` in full. Its dispatch only
executes a fixed vocabulary: `operation_type` ∈ {create, update, link, delete,
tool_use} × `entity_type` ∈ {capability, application, vendor, capability_mapping,
work_package} (create), {capability, application, vendor} (update/delete),
{application_capability_mapping} (link). Compared each of the seven
`@require_ai_approval`-decorated routes' actual write against that vocabulary:

| Route | Verdict | Wiring |
|---|---|---|
| `POST /data/create-capability` | **Wired** | `queue_ai_write("create", "capability", data, ...)`. Route already called `AIDataInteractionService.create_capability(data)` directly — exact match, no divergence once queued post-validation. |
| `PUT /data/update-capability/<id>` | **Wired** | `queue_ai_write("update", "capability", data, entity_id=capability_id, ...)`. Route already called `update_capability(capability_id, data)` — exact match. |
| `PUT /data/update-application/<app_id>` | **Wired — and a pre-existing bug fixed** | `queue_ai_write("update", "application", data, entity_id=app_id, ...)`. **Divergence found**: the route was calling `service.update_application_metadata(app_id, data)`, a method that **does not exist** on `AIDataInteractionService` (only `update_application` does) — every direct call to this route, gate on or off, has always raised `AttributeError` and 500'd. The queued/approved path calls the *correct* `update_application`, which is what surfaced the bug while comparing the two paths. Fixed the route to call `update_application` too, so both paths now agree (and the direct path actually works for the first time). Left a comment at the call site explaining why. |
| `POST /data/add-compliance-requirement` | **Exempted** | No `entity_type="compliance_requirement"` anywhere in the dispatch. Removed the decorator, added a comment, executes immediately (still behind `@login_required` + `@audit_log`, and now tags via `tag_ai_action` explicitly since that no longer comes free from a decorator). |
| `POST /data/create-requirement` | **Exempted** | No `entity_type="requirement"` under `create`. Same treatment as above. |
| `POST /apply-archimate` | **Exempted** | Calls `ArchitectWorkflowService.apply_archimate_elements` with a variable-length element list — no shape in the create/update/delete/link vocabulary fits an arbitrary list of ArchiMate elements. Already called `tag_ai_action` manually on success, so no metric regression. |
| `POST /apply-apqc` | **Exempted** | Same reasoning as `apply-archimate` — `ArchitectWorkflowService.apply_apqc_mappings` has no matching entry. Already tagged via `tag_ai_action` on success. |

**3 of 7 wired for real approval, 4 exempted with an explicit code comment** at each
write site (`app/modules/ai_chat/routes/workflow_routes.py`), per the review's option
(3): "honest immediate execution beats a fake queue."

## Tests

Extended `tests/test_ai_write_approval.py::TestRequireAIApprovalDefaultsOn`:
- `test_create_capability_queues_a_real_pending_approval` — `202` with an integer
  `approval_id`; the `AIChatCRUDApproval` row actually exists (`operation_type`,
  `entity_type`, `operation_payload` all correct); the same id appears in
  `GET /ai-chat/approvals/pending`; nothing was written to `BusinessCapability` yet.
- `test_approving_create_capability_performs_the_real_write` — approve →
  the capability row is actually created.
- `test_rejecting_create_capability_creates_nothing` — reject → nothing created,
  approval row moves to `REJECTED`.
- `test_update_capability_queues_with_the_capability_id_as_entity_id` — second gated
  endpoint: the URL's `capability_id` reaches `approval.entity_id`; approving it
  actually renames the capability via `AIDataInteractionService.update_capability`.
- `test_create_capability_writes_directly_when_flag_off` — unchanged from round 1,
  still passes (confirms the opt-out path).
- `test_add_compliance_requirement_is_exempt_and_never_queues` — with the gate on,
  this exempted route never returns `pending_approval`/`approval_id` — it always
  executes.

## Verification

```
TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5439/flask_test \
  python -m pytest tests/test_ai_write_approval.py tests/test_business_arch_ai.py \
    app/modules/ai_chat/tests/test_copilot_tools.py -q
  => 72 passed

python scripts/verify.py --gate compile --gate boot-health
  => 2 passed, 0 failed, 0 skipped

python scripts/verify.py --tag static
  => 23 passed, 0 failed, 1 skipped (css-build, expected, same as round 1)
```

## Fix commit

`fix(ai-gov): the data-API gate queues real approvals, not promises` — see
`git log` in this worktree for the hash (recorded at the end of this session).
