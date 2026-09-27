# AI red-team pass — 4 September 2026

Candidate base: `0a17761dcfe2e81ad3c80260f0a424f888944c8e`

Worktree: `security/ai-red-team`

Scope: dynamic, behavioural testing of the AI chat tool-execution and
untrusted-content boundaries — deliberately not a re-run of the static
`ai-*` gates already registered (`ai-evidence-rules`, `ai-tool-guard`,
`ai-untrusted-content`, `ai-approval-honoured`), which check that code is
*shaped* correctly. This pass tries to defeat the boundaries those gates
check for, with adversarial inputs, the way a static AST scan cannot.

## Method

Attacked the enforcement code directly rather than through a live LLM
conversation: the security boundary in this codebase is explicitly the code
(`ToolExecutor.execute`'s docstring: "This — not the prompt, not the LLM's
own judgement — is the access control"), so testing it deterministically,
without spending LLM API calls or depending on a particular model's
cooperativeness, is the correct target — and is what a competent attacker
who has read the source would also do.

## Finding 1 — fence_untrusted() delimiter-injection escape (fixed)

**Attack**: craft retrieved content (a RAG document, or any field that
reaches a pgvector search result) containing a literal `=== END <label>
===` line, followed by forged instruction text, followed by a fake
`=== BEGIN <label> ===`. `fence_untrusted()` embedded this byte-for-byte
unchanged, so the untrusted block could manufacture what looks like the end
of itself followed by fresh "trusted" text and a second untrusted section —
classic delimiter/fence-escape prompt injection, the same class of bug as
an un-escaped `</script>` breaking out of a fenced HTML context.

**Proof** (before fix):
```
malicious body containing "=== END ORGANISATION DOCUMENTS ===" mid-text
-> fence_untrusted() output contained TWO occurrences of that exact string,
   the forged one appearing before the real one
```

**Fix**: `app/modules/ai_chat/services/architect_persona_charters.py` —
`fence_untrusted()` now runs untrusted `body` through
`_neutralize_fence_lookalikes()` first, which spaces apart any run of 3+
`=` characters (`"==="` -> `"= = ="`) so untrusted content can still
describe or quote fence syntax (nothing is deleted or hidden — the preamble's
promise, "report that you saw it," still holds) but can never produce the
exact byte sequence the real fence uses.

**Verification**:
- `pytest tests/test_ai_red_team_fence_escape.py` — 5 passed. Reproduces the
  original attack (asserts exactly one real BEGIN/END pair survives, the
  forged pair does not appear intact in the body region), confirms the
  payload text itself is still visible (not silently dropped), confirms
  ordinary content with `=`/`==` below the 3-run threshold is untouched, and
  confirms the no-fabrication preamble still ships.
- `python scripts/verify.py --tag static` — see this run's log for the
  pass/fail count; no new findings introduced by the fix itself.

Not yet logged as a numbered `F500-###` finding pending this session's
report-back — the fix is committed and tested on branch
`security/ai-red-team`, `verified_local` by the same standard this ledger
already uses elsewhere, final CI/independent retest still required.

## Checked, clean — no vulnerability found

**Attack attempted**: cross-tenant IDOR via `ToolExecutor`'s `user_id` /
`organization_id` scoping — could a mutating tool call's own arguments
override which user/org it acts as, bypassing the server-trusted session?

**Result**: no. Traced every `ToolExecutor(...)` / `AgentRunner(...)` /
`AIChatApprovalService(...)` instantiation back to its call site
(`app/modules/ai_chat/routes/*.py`) — every one is constructed with
`current_user.id` (Flask-Login's trusted session identity), never a
client-supplied value from the request body or tool arguments. `_get_organization_id()`
resolves through `g.current_org_id` or a DB lookup keyed on that same
server-trusted `user_id`, with no path from tool-call arguments into either.

This is a genuine negative result, not an unexamined gap — worth recording
so a future pass does not re-derive it, and so "checked, found clean" is
distinguishable from "not checked."

## Not yet attempted this pass (recommended next)

- Live conversational red-team via the actual chat endpoint (requires LLM
  API calls; not run here to keep this pass deterministic and free, but is
  the complementary half — a smart-enough model might resist a forged fence
  even before the code fix, or a differently-shaped attack might defeat the
  charter's instruction-following despite structurally sound fencing).
- Tool-argument fuzzing for resource exhaustion / unbounded query patterns.
- Approval-queue tampering (racing `AIChatApprovalService.approve_and_execute`
  against a concurrent state change).
- The four registered `ai-*` static gates' own Proven-against cases were not
  re-verified in this pass — they are Codex's work, already independently
  wired in per the 3 Sep governance-gates finding.
