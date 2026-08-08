# /ai-chat Differentiators — Implementation Plan (Plan 3 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the assistant governed, its answers auditable, and its writes visible — the three things a generic chat product structurally cannot do, because they depend on a governed, tenant-scoped model of one enterprise.

**Architecture:** Backend seams first (Tasks 1–3), because everything visible depends on them and each is small. Then the evidence trail, the Assistant control, receipts, and the opening screen. Task 1 is the highest value-to-effort item in all three plans.

**Tech Stack:** Flask · Jinja2 · Alpine.js v3 · Tailwind CSS v3 · PostgreSQL · pytest

**Inputs:**
- Spec: `docs/superpowers/specs/2026-08-07-ai-chat-rebuild-design.md` (v2) §5, §7, §8, §16
- **Parameter map: `docs/known-issues/ai-chat-parameter-effects.md` — read in full before Task 5**
- Plans 1 and 2, both landed

## Global Constraints

- **Read `DESIGN.md`** before editing any template, CSS, or front-end JS file.
- **Never invent data** — `fabricated-data` must stay 0. This plan is where that gate is most at risk: §7 and §16 of the spec both render claims *about* the answer. A confidence number nobody can audit, or a "0" that means "not computed", is the failure mode.
- **`design_tokens` baseline 88** — must not rise. **`raw_sql_tenancy` 98** — must not rise.
- **New columns must be nullable** — `reconcile-schema` only adds nullable columns.
- **`git add <file>`** — never `git add -A`.
- **Multi-tenancy is enforced by ORM events.** Don't hand-write `organization_id` filters on `TenantMixin` models. Anything looping over tenants in one session must `db.session.remove()` between them.
- **Verification:** `python scripts/verify.py --tag static` stays 14/14; the `/ai-chat` a11y baseline entry must shrink, never grow.

---

## Task 1: Reconnect the governed persona charters

The highest-value change in any of the three plans, and among the smallest.

`architect_persona_charters.py` holds the charters, the HARD RULES and the per-persona live-data blocks that `CLAUDE.md` names as the AI's governance layer. They are reached only via `MultiDomainChatService._get_persona_system_prompt` (`:3277`) ← `process_message` — which the live path never calls. `AgentRunner`'s entire use of `persona` is one line (`agent_runner.py:529-531`):

```python
persona_note = f"\nYou are operating as: {persona.replace('_', ' ').title()}.\n"
```

**Selecting "AI Data Architect" versus "CIO" currently changes eight words.** The assistant is not governed by its charter.

**Files:**
- Modify: `app/modules/ai_chat/services/agent_runner.py:491-533`
- Test: `tests/test_ai_chat_persona_charter.py` (create)

**Interfaces:**
- Produces: `_build_system_prompt` returns a prompt containing the persona's charter text when `persona` names a governed persona.

- [ ] **Step 1: Read the charter builder**

Read `app/modules/ai_chat/services/architect_persona_charters.py` in full — `ARCHITECT_PERSONAS`, `build_architect_prompt()`, and its signature. Read `multi_domain_chat_service.py:3277` to see how the existing caller invokes it.

- [ ] **Step 2: Write the failing test**

```python
"""The governed charters must reach the model on the live path.

They were reachable only through MultiDomainChatService.process_message, which
AgentRunner never calls, so persona selection changed eight words of prompt and
the charter's HARD RULES were never in context.
"""
from app.modules.ai_chat.services.agent_runner import AgentRunner


def test_governed_persona_prompt_contains_its_charter(app):
    with app.app_context():
        runner = AgentRunner(user_id=1)
        prompt = runner._build_system_prompt(
            domain="architecture", context=None, persona="enterprise_architect"
        )

    assert "You are operating as: Enterprise Architect." not in prompt or len(prompt) > 2000, (
        "The persona note is still the only persona content in the prompt."
    )
    # A charter is present, not just a title-cased label.
    from app.modules.ai_chat.services.architect_persona_charters import ARCHITECT_PERSONAS
    charter = ARCHITECT_PERSONAS["enterprise_architect"]
    marker = charter["charter"][:60] if isinstance(charter, dict) else str(charter)[:60]
    assert marker.strip() and marker.strip() in prompt, (
        "The enterprise_architect charter is not in the system prompt, so the "
        "assistant is not governed by it."
    )


def test_ungoverned_persona_still_gets_a_note(app):
    """A persona with no charter must not break the prompt."""
    with app.app_context():
        runner = AgentRunner(user_id=1)
        prompt = runner._build_system_prompt(
            domain="general", context=None, persona="product_analyst"
        )
    assert "Product Analyst" in prompt
```

Adjust the marker extraction to the real shape of `ARCHITECT_PERSONAS` once Step 1 tells you what it is. Do not guess the shape.

- [ ] **Step 3: Run it and watch it fail**

Run: `pytest tests/test_ai_chat_persona_charter.py -v`
Expected: FAIL — the charter text is absent.

- [ ] **Step 4: Wire the charter in**

In `_build_system_prompt`, replace the `persona_note` block:

```python
        persona_note = ""
        if persona:
            try:
                from app.modules.ai_chat.services.architect_persona_charters import (
                    ARCHITECT_PERSONAS, build_architect_prompt,
                )
                if persona in ARCHITECT_PERSONAS:
                    # The governed charter: role, hard rules, and the live-data
                    # blocks this persona is expected to reason from. Without it
                    # the persona selector changed eight words of prompt.
                    persona_note = "\n" + build_architect_prompt(persona)
            except Exception as e:
                logger.warning("persona charter unavailable for %s: %s", persona, e)
            if not persona_note:
                persona_note = f"\nYou are operating as: {persona.replace('_', ' ').title()}.\n"
```

The fallback matters: 11 personas are selectable and only 5 are governed, so an ungoverned persona must still get its label.

Check `build_architect_prompt`'s real signature in Step 1 — if it needs a user or org id, pass `self.user_id`.

- [ ] **Step 5: Watch the prompt size**

`_serialise_context` drops whole keys when over budget. A charter is substantial, so confirm you have not pushed the context block out of the prompt. Log the assembled length for one call and compare before/after; if the charter crowds out portfolio context, the charter goes **before** the context block so the drop order stays sane, and you note it in the commit.

- [ ] **Step 6: Verify and commit**

```bash
pytest tests/test_ai_chat_persona_charter.py -v      # PASS
python scripts/verify.py --gate compile --gate undefined-names --gate lint-core
git add app/modules/ai_chat/services/agent_runner.py tests/test_ai_chat_persona_charter.py
git commit -m "feat(ai-chat): the governed charters now reach the model

architect_persona_charters.py — the charters, the HARD RULES and the
per-persona live-data blocks CLAUDE.md names as the AI's governance layer —
was reachable only through MultiDomainChatService._get_persona_system_prompt,
which the live AgentRunner path never calls. Selecting 'AI Data Architect'
versus 'CIO' changed eight words of prompt.

Ungoverned personas keep the plain label: 11 are selectable, 5 are governed."
```

---

## Task 2: Extend `_TOOL_ENTITY` so citations cover the read tools

`_TOOL_ENTITY` (`agent_runner.py:101-107`) maps **5 of the registry's 37 tools**. Every other read tool returns real tenant rows and contributes no citation — so an answer built from `propose_rationalization`, `simulate_impact`, `explain_element`, `diagnose_chain` or `get_solution_summary` looks ungrounded. This is the prerequisite for Task 4.

**Files:**
- Modify: `app/modules/ai_chat/services/agent_runner.py:101-107`, and `_source_url` at `:110-145`
- Test: `tests/test_ai_chat_citations.py` (exists — extend it)

- [ ] **Step 1: Inventory the read tools**

Read `app/modules/ai_chat/tools/registry.py` in full (37 tools). For each, decide: does it return a list of records with `id` and `name`? Those are citable. Write the list down before editing.

`_source_url` already has branches for `vendor` and `solution` that no tool can currently reach (`:127-130`) — the shape was anticipated.

- [ ] **Step 2: Write the failing test**

Extend `tests/test_ai_chat_citations.py` — read it first and match its style — with a test asserting that a turn whose tool results include vendor rows produces `sources` entries of type `vendor`.

- [ ] **Step 3: Extend the map**

Add every citable read tool to `_TOOL_ENTITY`, mapping to the entity type its rows describe. Add `_source_url` branches for any new entity type. Keep `MAX_SOURCES = 25`.

`_collect_sources` already guards correctly — it requires `result.get("success")`, a list of rows, and a real `id` and `name` per row. Do not weaken those guards to increase coverage; a citation that does not correspond to a returned row is fabrication.

- [ ] **Step 4: Verify and commit**

```bash
pytest tests/test_ai_chat_citations.py -v
python scripts/verify.py --tag static
git add app/modules/ai_chat/services/agent_runner.py tests/test_ai_chat_citations.py
git commit -m "fix(ai-chat): citations covered 5 tools out of 37

An answer built from propose_rationalization, simulate_impact, explain_element
or get_solution_summary read real tenant rows and produced no sources at all,
so the UI had no way to tell a grounded answer from an ungrounded one on
exactly the highest-stakes questions."
```

---

## Task 3: Mark which tools mutate

Receipts and next-artifact suggestions both need to know which tools write. The registry does not say.

**Files:**
- Modify: `app/modules/ai_chat/tools/registry.py`
- Test: `tests/test_copilot_tools.py` (exists in `app/modules/ai_chat/tests/`) or a new test beside it

- [ ] **Step 1: Add a `mutates` flag to each tool entry**

`toggle_auto_execute`'s docstring (`chat_core.py:1443-1461`) already recommends exactly this — a `mutates` flag in `tools/registry.py` — for approval tiering. Use one flag for both purposes rather than adding a parallel constant that will drift.

Do NOT use a `name.startswith("create_")` heuristic: it misses `mark_option_recommended`, `submit_for_arb_review`, `link_application_to_capability`, `link_vendor_product`, `update_application_status`, `update_solution_fields`, `update_solution_phase`.

- [ ] **Step 2: Write a test that pins the classification**

Assert every tool has an explicit `mutates` key (so a newly added tool cannot default silently), and spot-assert the tricky ones above are `True` while `find_applications` and `query_capability_gaps` are `False`.

- [ ] **Step 3: Expose it**

Add a helper — `def mutating_tool_names() -> set[str]` — beside the registry, and use it wherever the write/read split is needed.

- [ ] **Step 4: Verify and commit**

```bash
python scripts/verify.py --tag static
git add app/modules/ai_chat/tools/registry.py <test file>
git commit -m "feat(ai-chat): mark which tools mutate, explicitly

An allow-list rather than a startswith() heuristic, which would miss
mark_option_recommended, submit_for_arb_review and every link_*/update_* tool.
One source of truth for receipts, next-artifact mapping and approval tiering —
the last of which toggle_auto_execute's docstring already asked for."
```

---

## Task 4: The evidence trail

Replaces the "grounded / not grounded" binary the spec originally proposed, which would have rendered a **false** "not checked against your portfolio" on any answer built from the 32 uncited tools.

The material is already on the wire: the server emits `tool_start` and `tool_result` per call and returns `actions_taken`; Plan 2 Task 2 surfaced them to `transport.streamMessage` as no-op handlers.

**Files:**
- Modify: `app/static/js/ai_chat/render.js`, `app/static/js/ai_chat/app.js`
- Modify: `app/templates/ai_chat/index.html` (evidence drawer)

- [ ] **Step 1: Collect the trail per turn**

Wire `onToolStart`/`onToolResult` to accumulate `{tool, args, rowCount, shownCount, total}` in turn order. Take counts from the tool result, never from the model's prose.

- [ ] **Step 2: Render three honest states**

| Condition | Rendered |
|---|---|
| tools ran | **Retrieved** — one row per call, in order |
| no tool ran, but domain context was injected | **Context only** — name the snapshot; offer "verify this" |
| neither | **Unretrieved** |

Never a percentage, never a score. Each row reads like:

> Searched applications · status = production · **47 matched, showing 15**

- [ ] **Step 3: Make coverage structural**

When a tool returned N of M, the row says so — always, from the result payload, not from prose the model may omit. `_AGENT_PREFIX` rule 9 already asks the model to report N of M; this makes it a property of the UI instead of a hope.

An architect's real question is not "is this grounded" but *"did it look at everything, or at the first page?"*

- [ ] **Step 4: Accessibility**

The strip is a `<button aria-expanded aria-controls>` whose accessible name is the whole sentence — "Grounded in 6 records from your portfolio, show sources" / "General knowledge, not checked against your portfolio". The **Context only** and **Unretrieved** states must be announced with equal prominence: a visual-only caption is precisely the provenance signal a blind architect cannot afford to miss before an ARB. If the drawer auto-opens, move focus into it and announce it.

- [ ] **Step 5: Verify and commit**

Ask a question that runs tools and one that does not; confirm each renders the correct state and that counts match the network payload. Run the axe audit — the baseline entry must not grow.

```bash
git add app/static/js/ai_chat/render.js app/static/js/ai_chat/app.js app/templates/ai_chat/index.html
git commit -m "feat(ai-chat): an evidence trail, with coverage stated structurally

Replaces a proposed grounded/not-grounded binary that would have rendered a
false 'not checked against your portfolio' on any answer built from the 32
tools that produce no citations — a fabricated claim in the direction the
fabricated-data gate cannot see.

Built from tool_start/tool_result, which the server has always emitted and the
client always discarded. Where a tool returned 15 of 47, the row says so."
```

---

## Task 5: The Assistant control

**Read `docs/known-issues/ai-chat-parameter-effects.md` in full before starting.** It changes this task materially.

**Files:**
- Modify: `app/templates/ai_chat/index.html`, `app/static/js/ai_chat/app.js`
- Modify: `app/modules/ai_chat/services/multi_domain_chat_service.py` (`PERSONA_CONFIGS`)
- Modify: `app/modules/ai_chat/routes/chat_views.py` (drop the unused template pre-fetch)

- [ ] **Step 1: Delete the Template selector — it does nothing**

`chat_core.py:356-362` validates `template_name`, bounds it to 100 chars and HTML-sanitises it, then discards it. `AgentRunner.run()` has no such parameter and no reference to it exists after line 362.

So remove: the `#template-selector` markup, its wiring, `template_name` from the request payload, and the `AIPromptTemplate.query.all()` pre-fetch in `chat_views.py` that populates it on every page load.

Leave the server-side validation in place — it is harmless and other callers may post the field.

This is a deliberate removal of a visible control. Say so in the commit.

- [ ] **Step 2: Build the two-row popover**

One button showing the current assistant. The popover has **two visible rows**, not one plus a hidden "Advanced":

```
AI Data Architect — canonical entities, classification, lineage
Looking at: [Data architecture ▾] · Vendors · Applications · Whole portfolio
```

The second row is labelled **scope**, not "domain" — the noun the user already thinks in. Defaulted from `default_domain`, always visible, changeable in one click.

Do **not** derive domain from persona and hide it: they are orthogonal. `domain` selects which of nine context loaders runs and is the only parameter that reliably changes what the model is shown.

- [ ] **Step 3: Fix the config defects the map found**

- `PERSONA_CONFIGS["data_architect"]["default_domain"]` is `"architecture"` → change to `"data_architecture"`, which has a dedicated loader the persona never reaches today.
- Surface **`compliance`** ("Verify against Architecture Principles") as a scope on every persona. It exists server-side, appears in no UI, and is the ARB's question.
- Surface **`data_architecture`** as a scope.
- Resolve `capability_architect`: `PERSONA_CONFIGS` has 12 entries, the picker offers 11. Expose it or delete it.

- [ ] **Step 4: Accessibility — this is where the task can go backwards**

Four native `<select>` elements today are labelled, keyboard-operable and mobile-native for free. A custom popover is a **net regression** unless it ships with `aria-haspopup`, `aria-expanded`, roving focus, arrow keys, Escape, and focus return to the trigger.

If you cannot build that properly, **keep native selects and just fix their labels**. That is a better outcome than a prettier control AT users cannot operate. Make this call explicitly and record it.

- [ ] **Step 5: Verify and commit**

Axe audit — must not grow. Keyboard-only: open the popover, move with arrows, select, Escape, confirm focus returns. Confirm changing scope changes the loader that runs (watch the network payload).

```bash
git add app/templates/ai_chat/index.html app/static/js/ai_chat/app.js app/modules/ai_chat/services/multi_domain_chat_service.py app/modules/ai_chat/routes/chat_views.py
git commit -m "feat(ai-chat): one assistant control, with scope kept visible

Persona and domain are orthogonal — domain selects which of nine context
loaders runs — so scope stays a visible second row rather than being derived
and hidden.

Removes the Template selector and the per-page-load AIPromptTemplate query
behind it: template_name is validated, sanitised and then discarded, and has
never affected an answer.

Fixes data_architect's default_domain, which pointed at 'architecture' so the
AI Data Architect never loaded the data-architecture context built for it, and
surfaces the compliance and data_architecture scopes, which existed
server-side with no UI at all."
```

---

## Task 6: Receipts and next artifact

**Files:**
- Modify: `app/static/js/ai_chat/render.js`, `app/static/js/ai_chat/app.js`

- [ ] **Step 1: Render write receipts inline**

When a turn ran mutating tools (Task 3's flag, applied to `actions_taken`), render a card stating what was created or changed, linked to the records. Same provenance discipline as Task 4 — from the tool result, never from prose.

- [ ] **Step 2: Attach proposal cards to the answer that caused them**

When `REQUIRE_AI_APPROVAL` is on, render the pending approval **inline**, with Approve/Reject in place — not as a disembodied badge in the header, divorced from the conversation that produced it.

Use the endpoints the live modal already uses: `GET /ai-chat/approvals/pending`, `POST /ai-chat/approvals/<id>/approve`, `POST /ai-chat/approvals/<id>/reject` (`approval_modal.js:49,79,121`) — **not** the `approval_gate.py` 202 payload, which is a different mechanism. Keep the header modal as the roll-up.

Destructive governance actions inside a live region must be announced once on arrival and never re-announced.

- [ ] **Step 3: Offer the next artifact from tools, never from prose**

`create_option`/`mark_option_recommended` ran → *Draft an ADR*. `propose_rationalization` ran → *Start a business case*. `query_capability_gaps` ran → *Create work packages*.

When no tool in the turn maps to a known next step, **offer nothing**. A wrong suggestion is worse than none.

- [ ] **Step 4: Emit enough structure for the artifact object**

Spec §8.1: the artifact — an ADR or ARB submission that opens beside the transcript and carries its evidence permanently — is out of scope here, but this is its seam. Each receipt and next-artifact action must carry: which tools ran, which records, which persona, which resolved model, and when. Getting that shape right now means the artifact needs no re-plumbing later.

- [ ] **Step 5: Verify and commit**

```bash
git add app/static/js/ai_chat/render.js app/static/js/ai_chat/app.js
git commit -m "feat(ai-chat): receipts for writes, and proposals attached to their answer

The assistant could already create drivers, goals, options and ARB
submissions; none of it was visible. A write produced prose claiming it had
happened and no receipt. Approvals appeared as a badge count in the header,
divorced from the conversation that caused them."
```

---

## Task 7: The opening screen

**Files:**
- Modify: `app/templates/ai_chat/index.html`, `app/static/js/ai_chat/panels.js`

- [ ] **Step 1: Replace 21 entry points with this tenant's actual state**

From `GET /ai-chat/recommendations` (`analytics_routes.py:215`) — already called, into a tab nobody opens. What changed, what is at risk, what is waiting on you; each item one click into a grounded conversation. Assistant picker and a few starters below.

- [ ] **Step 2: Design for every failure mode — each is a real state**

- **Empty tenant.** Day one, zero applications: the endpoint returns nothing and the flagship screen would be blank at the moment the product must be most persuasive. The empty state **is** the onboarding path — import a portfolio, or start a solution design, which needs no portfolio at all.
- **5,000 apps.** Three items surfaced from thousands is an editorial claim. Show the denominator and the basis: "3 of 214 open findings, ranked by portfolio impact", with a link to all of them.
- **Disagreement.** Per-item dismiss with a reason, persisted per user. Without it the wrong item sits at the top forever and the panel loses credibility within a week.
- **Latency, staleness, failure.** The most prominent element now depends on a network call: specify the loading state. The endpoint returns **500 with empty arrays**, which is indistinguishable from "nothing to report" — distinguish them, and render the error rather than an empty success. Timestamp the data.
- **Permissions.** Recommendations are portfolio-wide; a CIO and a programme-scoped solution architect should not see the same list. Scope by `enterprise_role`.

- [ ] **Step 3: First run should demonstrate, not describe**

Nothing currently tells a new user the assistant can **write to the repository**, which is the most surprising and valuable fact about it. First run executes one grounded question against their real portfolio with the evidence trail open, so the mechanism is visible before it is trusted.

- [ ] **Step 4: Guard the fabrication risk**

This screen renders numbers. `fetch` does not reject on 404: `if (response.ok)` with no `else` silently leaves a metric at its `0` initialiser, and a `0` meaning "not computed" is indistinguishable from a measured zero. Use `if (!response.ok) throw`, and `null` → `—`.

- [ ] **Step 5: Verify and commit**

Run `python scripts/verify.py --gate fabricated-data` — must be 0. Test with an empty tenant and a populated one.

```bash
git add app/templates/ai_chat/index.html app/static/js/ai_chat/panels.js
git commit -m "feat(ai-chat): open with this tenant's portfolio, not 21 generic buttons

A copilot sitting on a live portfolio should never open by asking the user to
supply the agenda. Uses the recommendations endpoint the page already called,
into a tab nobody opened. Empty, oversized, stale and failed states are all
designed rather than left to the happy path."
```

---

## Self-review

**Spec coverage.** §5 Assistant control ↔ Task 5. §7 evidence ↔ Tasks 2, 4. §8 answer-becomes-work ↔ Tasks 3, 6. §16 opening screen ↔ Task 7. §13 backend changes ↔ Tasks 1, 2, 3 (items 1, 2, 3 and 6 of that list; item 4 was the feedback tenancy fix, landed in Plan 1; item 5 was vision, resolved by removal).

**Type consistency.** Task 3's `mutating_tool_names()` is what Task 6 imports. Task 2's extended `_TOOL_ENTITY` is what Task 4's row counts rely on. Task 4's `onToolStart`/`onToolResult` handler names match the no-op signatures Plan 2 Task 2 defined — no rename across plans.

**Ordering.** 1, 2, 3 are backend and independent of each other; 4 depends on 2; 6 depends on 3; 5 and 7 are client-only. 1 can ship on its own the day it is written and is the single highest value-to-effort item across all three plans.

**Still out of scope, deliberately.** The artifact object (spec §8.1) — a new persisted, permissioned, reviewable entity, not a page change; Task 6 Step 4 builds its seam. Flipping `REQUIRE_AI_APPROVAL` — a governance decision. Vision — removed in Plan 1; reinstating it needs a model-routing decision. The ~8,300 lines of `multi_domain_chat_service.py` workflows reachable only through the legacy blueprint (CAP-014 capability design, AIC-305 ADM, RAG, vendor comparison) — inventory which are intentionally dead before deleting anything.
