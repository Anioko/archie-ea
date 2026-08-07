# /ai-chat rebuild — design

**Date:** 2026-08-07
**Status:** approved, not yet implemented
**Surface:** `GET /ai-chat` (`unified_ai_chat.index`, `app/modules/ai_chat/routes/chat_views.py:135`)

---

## 1. Why

The page works and is not best-in-class. The reasons are specific and verified, not
impressionistic.

### 1.1 Every AI answer renders unstyled

The answer bubble is `class="prose"` (`app/templates/ai_chat/index.html:1684`). But
`@tailwindcss/typography` is not enabled — `tailwind.config.js:87` is `plugins: []` — and
`prose` appears **zero** times in the built `app/static/css/tailwind-output.css`.

Tailwind Preflight, which *is* in the build, resets:

```css
menu,ol,ul{list-style:none;margin:0;padding:0}
h1,h2,h3,h4,h5,h6{font-size:inherit;font-weight:inherit}
```

So a well-structured answer — `## Findings`, numbered options, a comparison table —
renders as one undifferentiated grey slab: no bullets, no numbers, headings the same
size as body text, no paragraph rhythm, no table borders, no code styling. The markdown
pipeline (`marked` → DOMPurify) is correct and then dumps into a stylesheet that strips it.

This is the largest single quality defect on the page and the cheapest to fix.

### 1.2 Verified defects

| # | Defect | Evidence |
|---|---|---|
| D1 | Stop button is dead — generation cannot be interrupted | `#stop-btn` declared `index.html:781`, referenced nowhere; no `AbortController` in the file |
| D2 | No message actions | `.msg-action-bar` CSS at `index.html:102` is never rendered. No copy, regenerate, or feedback |
| D3 | Scroll yanks the reader down | 8 unconditional `scrollTop = scrollHeight`, one per streamed token (`index.html:2538`) |
| D4 | Every answer flashes on completion | `streamAiReply` does `wrap.remove()` then `appendMessage(...)` (`index.html:2548-2551`) — the finished bubble is destroyed and rebuilt |
| D5 | Composer never grows | `rows="3"`, `resize-none`, no `input` listener |
| D6 | Dark mode broken on welcome grid | `bg-emerald-50`, `bg-purple-50`, `bg-orange-50`, `bg-cyan-50` (`index.html:675-702`) have no dark variants |
| D7 | Errors masquerade as answers | `appendMessage('ai', '**⚠️ Error:** …')` (`index.html:2462`), no retry |
| D8 | 21 competing entry points | 5 architect cards + 6 domain cards + 4 chips + 6 quick queries, plus 4 header selectors |
| D9 | A11y | All four sidebar tabs share `aria-label="Action"` (`index.html:403-416`); `aria-live` wraps the whole transcript, so screen readers re-read the full answer on every token |
| D10 | 169 KB of dead JS | `app/static/js/ai_chat.js` (3,246 lines) is loaded by no template — a drifted fork of the inline JS. `slash_commands.js` likewise. `#command-hints` is populated by nothing |
| D11 | Feedback loop is open | `POST /ai-chat/feedback` exists (`chat_core.py:626`), `AIChatFeedback` exists, an admin analytics dashboard reads it — nothing has ever written to it |
| D12 | A quick-query button promises a command that does not exist | The "Create capability" button (`index.html:476`) sends `/create-capability`, which is absent from the `handleChatCommand` map (`index.html:1758-1769`). It falls through and is typed at the LLM as literal text |

### 1.3 The deeper problem

Fixing D1–D11 reaches parity with a competent generic chat UI. Parity is its ceiling,
because chat chrome cannot be a differentiator — ChatGPT's is better and free.

The page is a *feature inventory rendered as UI*: every capability the team shipped got a
button in the header or a card on the welcome screen, which is why there are four
selectors and 21 entry points. Nobody decided what the page is **for**.

It is for one thing: **turning a question about the portfolio into a defensible,
traceable, actionable answer.** The differentiator is the thing ChatGPT structurally
cannot have — a governed, tenant-scoped model of this specific enterprise. Today that
advantage appears as a caption at the bottom of a bubble.

---

## 2. Principles

1. **The answer is the product.** Craft goes into rendering, provenance, and actions. Chrome recedes.
2. **One control for "who am I talking to."** Not four.
3. **Evidence sits beside the answer**, not behind a tab.
4. **Never show a number we cannot audit.** (`CLAUDE.md`, `fabricated-data` gate.)
5. **Nothing is removed — things are ranked.** Every power feature stays reachable.

---

## 3. Layout

```
┌──────────┬──────────────────────────────────┬───────────┐
│ Chats    │  ◆ AI Enterprise Architect   ⌄   │ Evidence  │
│          ├──────────────────────────────────┤  Context  │
│ + New    │                                  │  Query    │
│ ──────── │      transcript, max-w-3xl       │  Alerts   │
│ Today    │                                  │           │
│  · …     │                                  │ collapsed │
│ Earlier  ├──────────────────────────────────┤ by        │
│  · …     │  [ composer          ]    ⚙  ▶   │ default   │
└──────────┴──────────────────────────────────┴───────────┘
```

- **Left — Conversations.** Persistent rail, promoted out of today's buried 4th tab.
  New chat, grouped by date, rename/delete. Collapses to icon width below `lg`.
- **Centre — Transcript.** `max-w-3xl` for readable measure. Composer autosizes 1→12 rows.
- **Right — Evidence.** Collapsed by default. Holds today's Context / Query / Alerts tabs.
  **Auto-opens and scrolls to an answer's sources when its grounding strip is clicked** —
  the interaction that makes provenance feel designed rather than bolted on.

Use `dvh`, not `vh`, for the page height — `h-[calc(100vh-4rem)]` (`index.html:149`) breaks
under mobile browser toolbars.

---

## 4. The Assistant control — replaces four selectors

Today the header carries **Domain** (7), **Persona** (11), **Model** (N) and **Template** (N).
Domain and persona are largely redundant; a user cannot know what
"Domain: Architecture + Persona: Data Architect" means.

One button showing the current assistant. Click → popover:

- 5 governed **AI Architects** promoted, 6 specialists below, each with a one-line
  "what I'm good at"
- Footer strip: **Model** `Auto ▾` · **Template** `None ▾` — present, subordinate
- **Advanced** disclosure exposes the raw domain override

Domain becomes *derived* from persona (the server already maps this in
`MultiDomainChatService.PERSONA_CONFIGS`). The wire payload is unchanged — the client
still sends `domain`, `persona`, `model`, `template_name`; it just stops making the user
assemble them.

---

## 5. Answer rendering

Enable the typography plugin **and remap every `--tw-prose-*` variable to the design
tokens** in `tailwind.config.js`. Dark mode then works by construction instead of via a
second `prose-invert` ruleset, and it satisfies DESIGN.md's no-raw-colours rule, which
stock `prose` would violate.

> **Verified:** the standalone Tailwind CLI at `scripts/bin/tailwindcss.exe` bundles
> `@tailwindcss/typography`. A probe build with `plugins: [require('@tailwindcss/typography')]`
> emitted 148 prose rules with no npm install. The air-gap posture is unaffected.

Also:

- Code blocks: language label + copy button, horizontal scroll
- Tables wrapped in `overflow-x-auto`
- **Streaming uses one persistent bubble**, never destroyed and rebuilt (fixes D4)

---

## 6. Grounding — the honest trust signal

**Decision: do not wire `AIConfidenceCalculator` or `AIHallucinationDetector`.**
Both were read in full. Both are unfinished sketches, and rendering either would
fabricate.

`AIConfidenceCalculator` — two hardcoded constants carry 40% of the weight:

```python
historical_score = 0.7  # Could be enhanced with actual historical tracking   # 20% weight
boundary_match   = 1.0  # Assuming regex word boundary was used               # 20% weight
```

`_calculate_data_quality` is `populated_fields / total_fields` — it measures how full a
dict is, not confidence in an answer. Decisively: **no function scores a chat response.**
It scores ArchiMate generation, vendor matching, entity matching and APQC matching. A
percentage on a chat answer would have to be invented.

`AIHallucinationDetector` — would fire on correct answers:

- flags `all`, `none`, `every`, `only`, `always`, `never` — the exact language of true
  statements about a finite portfolio ("none of the vendors have expiring contracts")
- `_has_citation` looks for `[1]`, `(Author, 2024)` or a URL; this model emits none of
  those, because sources arrive as a **separate server-side array**. So every numeric
  claim in every answer is flagged `unsourced_statistic`
- `risk_score = min(len(issues) * 0.15, 1.0)` → ~7 flags pins it to `critical`

A trust signal that cries wolf on good answers is worse than none: users learn to ignore
it, which destroys the true positives too.

**What we build instead.** `AgentRunner._collect_sources`
(`app/modules/ai_chat/services/agent_runner.py:146`) records only rows that read-tools
actually returned, with a real `id` and `name`, deduplicated and capped. That is genuine
provenance. `context_used = bool(sources)` already exists at `chat_core.py:538`.

Every AI answer states one of two things, plainly, at the top:

| Condition | Rendered |
|---|---|
| `sources.length > 0` | **"Grounded in N records from your portfolio"** — expandable to the exact rows, each linked |
| `sources.length == 0` | **"General knowledge — not checked against your portfolio"** |

Auditable end-to-end, needs no new backend, and it is the distinction an architect needs
before an ARB. Leave both services in place with a one-line note recording *why* they are
unwired, so this is not rediscovered.

---

## 7. The answer becomes work

The tool registry (`app/modules/ai_chat/tools/registry.py`) exposes 40+ tools including
writes: `create_solution`, `create_driver`, `create_goal`, `create_constraint`,
`create_requirement`, `create_risk`, `create_option`, `mark_option_recommended`,
`propose_rationalization`, `submit_for_arb_review`, `create_archimate_element`,
`update_solution_fields`. The capability is built and entirely invisible.

Three additions, all **inline in the transcript**:

- **Action receipts.** When a turn ran write tools, render a card: what was created or
  changed, linked to the new records. The same provenance discipline as §6, applied to writes.
- **Proposal cards.** When `REQUIRE_AI_APPROVAL` is on, the 202 `pending_approval` payload
  (`approval_gate.py:39`) renders **attached to the answer that caused it**, with
  Approve/Reject in place — not as a disembodied badge in the header. The header modal
  stays as the roll-up.
- **Next artifact.** Offered from **which tools ran in the turn**, never from parsing the
  prose — the same rule as receipts. `create_option` / `mark_option_recommended` ran →
  *Draft an ADR*; `propose_rationalization` ran → *Start a business case*;
  `query_capability_gaps` ran → *Create work packages*. When no tool in the turn maps to a
  known next step, offer nothing. A wrong suggestion is worse than none.

**Defining "write tool."** The registry (`tools/registry.py`) does not mark writes. Derive
the set explicitly in `tools/registry.py` as a named constant — an allow-list, not a
`name.startswith("create_")` heuristic, which would miss `mark_option_recommended`,
`submit_for_arb_review`, `link_*` and `update_*`. The constant is the single source of
truth for both receipts and next-artifact mapping, and it belongs beside the registry so
it cannot drift from it.

> **Note, not a change:** `REQUIRE_AI_APPROVAL` defaults to `False`
> (`approval_gate.py:53`), so AI writes currently execute immediately and the Approvals
> badge is permanently empty. Flipping it is a governance decision outside this work.
> Receipts are valuable either way — arguably more so while the gate is off.

---

## 8. The opening screen is your portfolio

Replace the 21 generic entry points with what is actually happening in this tenant, from
`GET /ai-chat/recommendations` (`analytics_routes.py:215`) — an endpoint the page already
calls, into a tab nobody opens. What changed, what is at risk, what is waiting on you;
each item one click into a grounded conversation. Assistant picker and a small set of
starters sit below, for arriving with your own agenda.

A copilot sitting on a live portfolio should never open by asking the user for the agenda.

If the endpoint returns nothing, render a genuine empty state — never a fabricated
placeholder metric (`fabricated-data` gate).

---

## 9. Control and failure

- **Stop** — real `AbortController`; the button replaces Send during generation (D1)
- **Scroll** — anchor only when already within ~100 px of the bottom; otherwise show a
  "↓ New response" pill (D3)
- **Errors** — a destructive-tinted card with the real message and **Retry**, never a
  fake AI turn (D7)
- **Message actions** — Copy · Regenerate · 👍 👎 · *Open in Composer* when ArchiMate
  elements are present. In the DOM always for keyboard and screen readers, revealed on
  hover (D2). Thumbs POST to the endpoint that has sat unused (D11)
- **Keyboard** — Enter send / Shift+Enter newline (existing), ⌘K new chat, Esc stop,
  ↑ edit last message

---

## 10. Code structure

```
app/templates/ai_chat/index.html   ~450 lines, markup only        (was 3,591)
app/static/css/ai_chat.css         chat chrome not expressible as utilities
app/static/js/ai_chat/
    transport.js   send · stream · abort · threads · models
    render.js      markdown · sanitise · grounding · receipts · code copy · actions
    commands.js    the 10 /slash handlers + action cards
    panels.js      context · NL query · recommendations · genome
    app.js         Alpine components + wiring
```

Delete `app/static/js/ai_chat.js` (dead, 169 KB) and the dead `#command-hints` element (D10).
Both are git-tracked and recoverable.

Replaces the `onclick=` attributes at `index.html:250` and `:551`, which DESIGN.md forbids.

---

## 11. Preserved behaviour — contract

The rebuild re-points new client code at the **same endpoints**. Backend changes are
limited to §12. All of the following must still work:

**Endpoints:** `/ai-chat/message`, `/ai-chat/message/stream`, `/ai-chat/models`,
`/ai-chat/nl-query`, `/ai-chat/threads`, `/ai-chat/threads/<id>`, `/ai-chat/feedback`,
`/ai-chat/context/<domain>`, `/ai-chat/recommendations`, `/ai-chat/api/health/llm`,
`/ai-chat/chat/generate-archimate`, `/ai-chat/chat/generate-archimate-description`,
`/ai-chat/chat/map-apqc`, `/ai-chat/chat/save-insights`, `/ai-chat/chat/bulk-process`,
`/ai-chat/chat/gap-analysis`, `/ai-chat/chat/discover-vendors`,
`/ai-chat/chat/create-solution-diagram`, `/ai-chat/architect/analyze`,
`/ai-chat/architect/viewpoints`, `/ai-chat/architect/arb-ready`,
`/ai-chat/generate-archimate`, `/ai-chat/map-apqc` (the non-`/chat/` variants are both
live call sites in the current template — confirm which is canonical while porting rather
than assuming),
`/api/codegen/genome/extract`, `/solutions/create-with-draft`.

**Slash commands — all 11**, with their action cards (`index.html:1758-1769`):
`/generate-archimate`, `/map-apqc`, `/save-insights`, `/bulk-process`, `/gap-analysis`,
`/discover-vendors`, `/create-diagram`, `/analyze`, `/viewpoints`, `/arb-ready`, `/help`.
Resolve D12 while porting: either implement `/create-capability` or repoint that button at
a plain-language query. Do not carry the broken affordance forward.

**Features:** genome panel (`?mode=genome`) ·
CRUD approvals modal · document upload panel (`?panel=docs`) · NL query + quick queries ·
entity action modal · ArchiMate composer handoff via `sessionStorage` · session history
CRUD · LLM health banner · rate-limit badge · export conversation · export context log ·
create-solution-from-brief · `chat_bootstrap_error` degraded-mode banner.

---

## 12. Backend changes (the only ones)

The response payload must carry which **write** tools ran in a turn, so §7 receipts are
truthful rather than parsed out of prose. Additive, alongside the existing `sources`
collection in `AgentRunner` (`agent_runner.py:401-484`) — same shape, same discipline:
record only what a tool actually returned.

No other backend change. Grounding (§6) needs none.

---

## 13. Verification

Per `CLAUDE.md`, work is not complete without a green run.

- `python scripts/verify.py` green
- **`design_tokens` ratchet must go down**, never up — this removes `bg-emerald-50`,
  `bg-purple-50`, `bg-orange-50`, `bg-cyan-50` and the `token-migration-ok` markers around
  them. Re-baseline with `--update-baseline` after
- `air_gap` stays at 0 — the typography plugin is bundled in the local CLI; no CDN asset added
- `fabricated-data` stays at 0 — §6 and §8 are the two places this could regress
- `python scripts/build_css.py` rebuild committed (template classes change, so this is mandatory)
- `template_syntax`, `boot_health`, `tests` pass
- a11y: name the four sidebar tabs (D9); scope `aria-live` to a small status region rather
  than the transcript. The CI `smoke` job's axe-core audit is ratcheted against
  `tests/smoke/a11y_baseline.json` — it must not regress
- New tests: a route test asserting `/ai-chat` renders with the key anchors present, and a
  test for the feedback POST path now that the UI exercises it

---

## 14. Sequencing

Ordered so the riskiest, least-covered code moves first, while the change that most
improves perceived quality lands earliest.

1. **Typography** (§5) — plugin + token remap + CSS rebuild. Smallest diff, largest
   visible effect. Independently shippable and independently revertable.
2. **Port behaviour** — the 11 slash commands, genome, approvals, doc upload, NL query,
   entity modal, history, into the new module layout. Behaviour verbatim, no restyling.
   This is where a silent feature drop would happen, so it happens while the UI is still
   recognisable and diffable.
3. **Transcript mechanics** (§9) — streaming bubble, abort, scroll anchoring, error cards,
   message actions, composer autosize.
4. **Grounding** (§6) — client-only.
5. **Layout and Assistant control** (§3, §4) — the visible IA change, once everything
   underneath is known-good.
6. **Receipts and next artifact** (§7, §12) — the one backend seam.
7. **Opening screen** (§8).

Steps 1–3 restore correctness; 4–7 are the differentiators. Stopping after 3 would still
leave the page far better than it is today, which is the intended fallback if the rebuild
runs long.

## 15. Risks

| Risk | Mitigation |
|---|---|
| Rebuild silently drops a working feature | §11 is the contract; walk it item by item before claiming done |
| Regression in the 10 `/slash` commands (least-covered code) | Port them first, verbatim in behaviour, before any restyling |
| `design_tokens` ratchet regresses | Check the gate before and after; it should fall |
| Stale committed CSS | `build_css.py --check` is part of the run |
| Scope creep into `chat_core.py` | §12 is the entire allowed backend surface |

---

## 16. Deliberately not doing

- Wiring the two trust services (§6)
- Flipping `REQUIRE_AI_APPROVAL` (§7)
- Fixing `AIChatFeedback`'s missing `organization_id` on the ORM model, though the insert
  at `chat_core.py:647` writes the column. Pre-existing model/schema drift; this work makes
  the table non-empty for the first time, so it stops being theoretical. Flagged, not fixed
- Out-chatting ChatGPT at chatting. This is best-in-class *for an EA copilot grounded in a
  governed model of the enterprise*
