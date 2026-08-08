# /ai-chat — what each request parameter actually does

**Date:** 2026-08-07
**Why this exists:** the first `/ai-chat` redesign specified a control for a
parameter that changes eight words of a prompt, because it audited the template
and trusted the backend. Every control the rebuild keeps must have a row here.

**Live path:** `POST /ai-chat/message` and `/message/stream`
(`app/modules/ai_chat/routes/chat_core.py`) → `AgentRunner.run()`
(`app/modules/ai_chat/services/agent_runner.py:283`).

`USE_AI_CHAT_GUARDRAILS` defaults on, so `app/modules/ai_chat/` serves the page.
`MultiDomainChatService.process_message` — and everything reachable only from it —
is **not** on this path.

---

## The map

| Parameter | Read at | What it changes | Observable in the answer? |
|---|---|---|---|
| `message` | `chat_core.py` → `run(user_message=…)` | The user turn | **Yes** |
| `domain` | `agent_runner.py:522` → `get_domain_context(domain, …)` | Selects 1 of 9 context loaders, whose output is serialised into the system prompt | **Yes** |
| `persona` | `agent_runner.py:529-531` | Appends one sentence: `You are operating as: {Title Case}.` | **Barely** — see §1 |
| `template_name` | `chat_core.py:356-362` | Validated, length-checked, HTML-sanitised — **then discarded**. `AgentRunner.run()` has no such parameter | **No — none at all** |
| `element_id` + `context_type` | `chat_core.py:446-452` → `context_filter` | Honoured by **one** loader before 2026-08-07 (`_load_technology_context`); three more fixed since | **Domain-dependent** — see §2 |
| `model` | `agent_runner.py:345` `_resolve_requested_model` | Selects the LLM; silently falls back when the requested model is not configured, logging a warning the user never sees | **Yes**, but unreported |
| `thread_id` | `chat_core.py` → `_load_history(...)` → `run(history=…)` | Prior turns, so follow-ups resolve | **Yes** |
| `solution_id` | `agent_runner.py:495-503` | `ACTIVE SOLUTION CONTEXT` block; write tools default to this solution | **Yes** |
| `workspace_id` | `chat_core.py:465` → `context_data` | Passed through; no loader reads it | **No** |
| `workflow_instance_id` | `chat_core.py:457` → `context_data` | Passed through; no loader reads it | **No** |
| `document_context` | `chat_core.py:468-470` | Merged into `context_data` | Loader-dependent |
| `image_data` / `image_media_type` | `chat_core.py:480-483` | **Nothing** — no vision handling on this path. Client no longer sends them; UI removed 2026-08-07 | **No** |

---

## 1. `persona` — the governance layer is disconnected

`AgentRunner`'s entire use of the parameter (`agent_runner.py:529-531`):

```python
persona_note = ""
if persona:
    persona_note = f"\nYou are operating as: {persona.replace('_', ' ').title()}.\n"
```

The governed charters — `architect_persona_charters.py`, `ARCHITECT_PERSONAS`, the
HARD RULES, the per-persona live-data blocks that `CLAUDE.md` names as the AI's
governance layer — are reached only through
`MultiDomainChatService._get_persona_system_prompt` (`:3277`) ← `process_message`,
which the live path never calls.

**So the assistant is not governed by its charter today.** Selecting "AI Data
Architect" vs "CIO" changes eight words. Reconnecting this is a small change and
is the highest-value item in the rebuild.

One exception exists and proves the pattern: `get_domain_context` special-cases
`persona == 'solutions_architect'` to load `sa_context`
(`multi_domain_chat_service.py:573-577`). That is the only persona with any
effect on retrieved context.

## 2. `element_id` — the deep-link contract is domain-dependent

Six places in Archie deep-link into the chat with `?element_id=…&context_type=…`
(applications, vendors, solutions, composer, dashboard ×2). Those become
`context_filter`.

> **Correction, 2026-08-07.** The first version of this section counted
> `context_filter` references per loader and inferred "uses it" from a count above
> one. That conflated two unrelated things. `_load_architecture_context` has seven
> references, but **none of them is the singular `element_id`** — they are `layer`
> (a filter) and `element_ids` (plural, for graph expansion). Verified: `grep -c
> "element_id\b"` over that function body returns **0**.
>
> A reference count answers "does this function read the filter at all", not "does
> it honour the deep link". Only the second question mattered.

**State before 2026-08-07 — one loader of five honoured the deep link:**

| Loader | Honours `element_id`? | Note |
|---|---|---|
| `_load_technology_context` | **Yes** | AIC-016; `context_type == "application"` |
| `_load_architecture_context` | **No** | Reads `layer` and `element_ids` (plural) for other purposes |
| `_load_vendor_context` | **No** | Ran `VendorOrganization.query.limit(50).all()` and never looked |
| `_load_capability_context` | **No** | |
| `_load_general_context` | **No** | The fallback, so it received every deep link sent with no `domain` |

**Consequence:** "Ask AI about this vendor" from `vendor_detail.html:63` sent the
vendor's id, and the assistant was handed the first 50 vendors with no indication
which one was meant. The link appeared to work. The same held for capabilities,
for solutions, and — because `_load_architecture_context` never read it either —
for the architecture domain that most personas default to.

**Fixed** in the three ignoring loaders (commit `809663c`), following
`_load_technology_context` as the precedent. Each now attaches a `context_focus`
block naming the resolved record, and reports `resolved: false` with an
instruction to say so when the id cannot be read — rather than silently
substituting fifty other records, which is the failure this fix exists to close.
`_load_architecture_context` is **still unfixed**: it is the default domain for
most personas and does not honour the deep link.

## 3. `template_name` — the Template selector does nothing

`chat_core.py:356-362` validates it, bounds it to 100 characters and runs it
through `sanitize_html`. Nothing then reads it: `AgentRunner.run()` has no
`template_name` parameter, and no `template_name` reference exists after line 362.

The header's Template dropdown, and the `prompt_templates` list `chat_views.py`
pre-fetches from `AIPromptTemplate` on every page load to populate it, have no
effect on any answer.

## 4. Two domains exist server-side with no UI

`get_domain_context` dispatches on `data_architecture` (with a dedicated
`_load_data_architecture_context`) and the service defines a `compliance` domain
("Verify against Architecture Principles", used at `:1051` for ARB compliance
checks). Neither appears in the domain selector's seven options.

`compliance` is arguably the single most valuable domain for an ARB audience.

## 5. `PERSONA_CONFIGS` defaults are wrong for at least one persona

`PERSONA_CONFIGS["data_architect"]["default_domain"]` is `"architecture"`, not
`"data_architecture"` — so the AI Data Architect never loads the data-architecture
context that exists for it. `PERSONA_CONFIGS` also has 12 entries while the picker
offers 11; `capability_architect` is orphaned.

---

## What this means for the rebuild

1. **Do not build a picker for `template_name`.** Either wire it to the prompt or
   remove the control, the selector and the per-page-load `AIPromptTemplate`
   query behind it.
2. **Do not derive `domain` from `persona` and hide it.** `domain` is the only
   parameter that reliably changes what the model is shown.
3. **Reconnect the charters before polishing the persona control.** A beautiful
   picker over an eight-word effect is worse than four ugly selectors, because it
   looks like it works.
4. **Fix `element_id` for the vendor/capability/general loaders, or stop
   advertising it** — six entry points across the product currently promise
   context that three of the loaders discard.
5. **Surface `compliance` and `data_architecture`**, and fix the
   `data_architect` default.
