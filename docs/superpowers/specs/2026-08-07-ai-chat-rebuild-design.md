# /ai-chat rebuild — design (v2)

**Date:** 2026-08-07
**Status:** revised after four independent reviews; supersedes v1 (commit `adf6a5a`)
**Surface:** `GET /ai-chat` (`unified_ai_chat.index`, `app/modules/ai_chat/routes/chat_views.py:135`)

> **What changed from v1.** v1 audited the template exhaustively and the backend not at all.
> Three of its four differentiating sections rested on server behaviour that turned out to be
> false, and its verification plan was wrong in both directions. The Assistant control,
> grounding, the preserved-behaviour contract, verification and sequencing are all rewritten;
> §3 (parameter-effect map) and §9 (accessibility) are new. The typography finding, the module
> split and the defect table survive and are extended — 13 new defects, 8 of them in the
> backend.
>
> **Every claim a reviewer overturned is recorded in §18, including errors in this document's
> own first draft.** That table is the most useful page here for anyone who has to trust the
> rest of it.

---

## 1. Why

### 1.1 Every AI answer renders unstyled

The answer bubble is `class="prose"` (`app/templates/ai_chat/index.html:1684`). But
`@tailwindcss/typography` is not enabled — `tailwind.config.js:87` is `plugins: []` — and
`prose` appears **zero** times in the built `app/static/css/tailwind-output.css`.

Tailwind Preflight, which *is* in the build, resets:

```css
menu,ol,ul{list-style:none;margin:0;padding:0}
h1,h2,h3,h4,h5,h6{font-size:inherit;font-weight:inherit}
```

A well-structured answer — `## Findings`, numbered options, a comparison table — renders as
one undifferentiated grey slab. The markdown pipeline (`marked` → DOMPurify) is correct and
then dumps into a stylesheet that strips it.

Independently confirmed by two reviewers. This is the largest single quality defect and the
cheapest fix.

### 1.2 Defects in the client

| # | Defect | Evidence |
|---|---|---|
| D1 | Stop button dead — generation cannot be interrupted | `#stop-btn` (`index.html:781`) is **wired**, in `ai_chat.js:109,203,206-211`, with a real `AbortController` at `:128,1931,2047`. It is dead only because that file is loaded by nothing. **D1 and D10 are the same defect** — v1 said "referenced nowhere", which was wrong; the working implementation exists and can be salvaged rather than rewritten |
| D2 | No message actions | `.msg-action-bar` CSS at `index.html:102` never rendered |
| D3 | Scroll yanks the reader down | 8 unconditional `scrollTop = scrollHeight`, one per streamed token (`:2538`) |
| D4 | Every answer flashes on completion | `streamAiReply` does `wrap.remove()` then `appendMessage(...)` (`:2548-2551`) |
| D5 | Composer never grows | `rows="3"`, `resize-none`, no `input` listener |
| D6 | Welcome-grid tiles fail non-text contrast | `text-emerald-600` on `bg-emerald-50` = 3.58, `text-cyan-600`/`bg-cyan-50` = 3.54, `text-orange-600`/`bg-orange-50` = 3.35 — below WCAG 1.4.11's 3:1. **Fix the lines that actually render: `:3407,3415,3423,3431`.** The `:675-702` copy v1 cited is destroyed before paint (D23) |
| D7 | Errors masquerade as answers | `appendMessage('ai', '**⚠️ Error:** …')` (`:2462`), no retry |
| D8 | 21 competing entry points | 5 architect cards + 6 domain cards + 4 chips + 6 quick queries, plus 4 header selectors |
| D9 | A11y — see §9, which supersedes this row | tabs, live region, focus, contrast |
| D10 | 169 KB of dead JS | `app/static/js/ai_chat.js` (3,246 lines) loaded by no template. `slash_commands.js` likewise. `#command-hints` populated by nothing |
| D11 | Feedback loop open | `POST /ai-chat/feedback` exists (`chat_core.py:626`); nothing has ever written to the table |
| D12 | **Two** quick-query buttons send slash commands to the wrong endpoint | `[data-quick-query]` clicks route through the delegated handler (`:2769-2773`) → `runQuickQuery()` (`:2755`) → `executeNLQuery()` → `POST /ai-chat/nl-query`. They never reach `handleChatCommand`, which is called only from the chat-form submit (`:2360`). So "Create capability" (`:476`, `/create-capability`) **and** "Map APQC framework" (`:477`, `/map-apqc` — a *registered* command, so it looks correct) both post a literal slash string to the NL-query endpoint. **Implementing `/create-capability` as a command would not fix either button**; repoint both at plain language, or make `runQuickQuery` detect a leading `/` and dispatch to `handleChatCommand` |

### 1.3 Defects found by review — the client is worse than v1 said

| # | Defect | Evidence |
|---|---|---|
| **D13** | **Attached diagrams are silently discarded.** User attaches an architecture diagram, sees a thumbnail, and gets a confident answer generated as if no image existed | `chat_core.py:474-477` puts `image_data` into `context_data`; the turn runs through `AgentRunner`, which has **zero** occurrences of `image_data`/`vision`. The base64 never reaches a model |
| **D14** | **"Open in Composer" opens an empty canvas** | chat writes `sessionStorage['archimate_prefill']` (`:1709`); `archimate/composer.js:2407,2495` reads `composer_prefill`. Nothing reads the key the chat writes |
| **D15** | **Export conversation and the rate-limit badge are dead** | Both defined only in the orphaned `ai_chat.js` (`:2519`, `:246`). The Export button throws an Alpine expression error on every click |
| **D16** | **The entity modal needs two clicks to close** | Static `#entity-action-modal` (`:825`) and a dynamically built one (`:2877`) share an id. Close paths call `getElementById(...).remove()`, which returns the *first* — the invisible decoy — leaving the real overlay covering the viewport with no Escape and no focus trap. Also `duplicate-id-aria` (critical) |
| **D17** | **The mobile sidebar backdrop never appears** | Authored with the `hidden` **attribute** (`:573`); `toggleSidebar()` toggles the `hidden` **class** (`:2590`,`:2595`). Body scroll still locks (`:2596`) — the page freezes behind an undimmed, still-tabbable overlay |
| **D18** | **Both warning banners are invisible in dark mode** | `--warning-foreground: 0 0% 0%` — pure black — in *both* themes (`shadcn_tokens.css:28`, `:68`). On `bg-warning/10` in dark mode that composites to **1.19:1** (`:117`, `:143`). The two elements whose job is to warn that the AI is degraded cannot be read |
| **D19** | `marked.min.js` is the only vendor script on the page without `integrity=` | `index.html:5`, while `_head.html` gates DOMPurify with SRI. Subject matter of the `sri` gate |
| **D20** | 4 queries × 50 rows on every page load, discarded | `chat_views.py:180-218` builds `context_data`; the template references it **0** times |
| **D21** | Selecting a tab never hides the Chats panel | `switchSidebarTab` panel list `:2608` is `['context','query','alerts']` — omits `'history'` |
| **D22** | Replayed history always renders as domain `general` | `:3565` reads `window.currentDomain`, never assigned (`currentDomain` is a block-scoped `let` at `:1084`) |
| **D23** | The welcome grid exists twice, with different copy and prompts | Server-rendered `:581-718`, then overwritten by `messagesContainer.innerHTML` at `:3343-3447`; card wiring registered twice (`:2980-3008`, `:3450-3460`) |
| **D24** | ~190 lines of dead command code | `handleCommand` → `generateArchimatePreview` → `mapApqcPreview` → `renderActionCard` → `window.applyAction` (`:1350,1387,1410,1433,1522`). Consequence: `/ai-chat/generate-archimate`, `/map-apqc`, `/apply-archimate`, `/apply-apqc` have **no live call site** |
| **D25** | The "type in chat: *Create a solution for …*" hint has no implementation | `:485`; `openCreateSolutionModalWithMessage` (`:3026`) is only ever called with `''` |

### 1.4 Defects in the backend — what v1 never checked

These are the reason v1's differentiators do not work. They are not optional context.

| # | Defect | Evidence |
|---|---|---|
| **B1** | **The governed persona charters never reach the model.** `architect_persona_charters.py` — the charters, the HARD RULES, the per-persona live-data blocks that `CLAUDE.md` names as the AI's governance layer — is reached only via `MultiDomainChatService._get_persona_system_prompt` (`:3277`) ← `process_message`. The live path is `AgentRunner.run()`, whose entire use of persona is `agent_runner.py:531`: `persona_note = f"\nYou are operating as: {persona.replace('_',' ').title()}.\n"` | Eight words. Reconnecting this is ~2 lines and will improve answer quality more than everything in §5 |
| **B2** | **Citations cover 5 tools out of 37.** `_TOOL_ENTITY` (`agent_runner.py:101-107`) maps `find_applications`, `find_applications_by_capability`, `query_capability_gaps`, `search_capabilities_by_problem`, `search_archimate_elements`. `propose_rationalization`, `simulate_impact`, `explain_element`, `diagnose_chain`, `get_solution_summary`, `verify_codegen` and 33 others read real tenant rows and contribute nothing | Any grounding signal built on `sources` alone reports **false negatives on the highest-stakes answers** |
| **B3** | **No vision handling on the live path** | See D13 |
| **B4** | **`AIChatFeedback` is outside tenant isolation.** No `TenantMixin`, no `organization_id` on the model (`app/models/ai_chat_feedback.py`), while `message_text` stores the AI's answer — i.e. portfolio content. The admin dashboard query filters on `created_at` only (`chat_admin_routes.py:265-269`), no org predicate | Cross-tenant read. This work makes the table non-empty for the first time. **Blocker — see §17** |
| **B5** | The server **already** emits `tool_start` / `tool_result` per tool call (`agent_runner.py:455,458`) and already returns `actions_taken` — tool name, arguments, result, message (`:461-466`) — through both paths (`chat_core.py:527` and the `{"type":"done", **result}` spread at `:816`). **The client discards all of it.** Nothing in `index.html` listens | The material for §7 and §8 is already on the wire. **This is client-only work, not a backend change** |
| **B6** | Two domains exist server-side and in no UI: **`compliance`** ("Verify against Architecture Principles") and **`data_architecture`** (with a dedicated `_load_data_architecture_context`) | `compliance` is arguably the most valuable domain for an ARB audience |
| **B7** | `PERSONA_CONFIGS` has 12 personas; the picker shows 11 | `capability_architect` is orphaned |
| **B8** | `PERSONA_CONFIGS["data_architect"]["default_domain"]` is `"architecture"`, not `"data_architecture"` | So the AI Data Architect never loads the data-architecture context |

### 1.5 There is no test coverage on this surface

`/ai-chat` has **zero** smoke and Playwright coverage. It is absent from
`tests/smoke/test_accessibility_audit.py` `AUDIT` (7 paths), from
`test_archetype_journeys.py`, from `test_authorisation_matrix.py`, and has no entry in
`a11y_baseline.json`. Nothing in CI would catch any defect above, or any regression this
rebuild introduces. §13 is therefore load-bearing, not a formality.

### 1.6 The thesis

Fixing D1–D25 reaches parity with a competent generic chat UI. Parity is its ceiling —
chat chrome cannot differentiate, because ChatGPT's is better and free.

v1 said the differentiator is "a governed, tenant-scoped model of this specific
enterprise." That is half right, and review sharpened it:

> **The enterprise already has the model — it is the rest of Archie. The differentiator is
> that the assistant's output re-enters the governed record as a first-class, attributable,
> reviewable artifact. Chat is the input method. The artifact is the product.**

An architect's output is an ADR, an ARB submission, a business case — documents read days
later by people who were not in the conversation. Everything v1 built lived in a transcript
and died when the tab closed.

---

## 2. Principles

1. **The answer is the product; the artifact is the point.** Craft goes into rendering,
   provenance, and what survives the tab closing.
2. **Never assert what we have not verified.** Applies to the UI's own claims about
   provenance as much as to the model's claims. A false "not grounded" is as much a
   fabrication as a false confidence score.
3. **Rank, don't amputate.** Where v1 removed a control because it was confusing, prefer a
   label. (Exception: §8, stated openly there.)
4. **Native semantics unless we can afford to rebuild them properly.** A custom popover
   replacing a labelled `<select>` is a regression until it has full menu semantics.
5. **Every control must have an observable effect.** A picker for a parameter that does
   nothing is worse than four selectors, because it looks like it works.

---

## 3. Prerequisite: the parameter-effect map

**Do this before any UI work.** Produce a table of *request parameter → observable effect on
the answer* on the live `AgentRunner` path, covering at minimum `persona`, `domain`,
`template_name`, `element_id`, `context_type`, `model`, `image_data`, `thread_id`.

Every control the rebuild keeps must have a row. B1, B2 and B3 were all discovered by
asking this question, and none of them was visible from the template. Publish the table in
this document before §5 begins.

---

## 4. Layout

```
┌──────────┬──────────────────────────────────┬───────────┐
│ Chats    │  ◆ AI Enterprise Architect   ⌄   │ Evidence  │
│          ├──────────────────────────────────┤  Context  │
│ + New    │                                  │  Query    │
│ ──────── │      transcript                  │  Alerts   │
│ Today    │                                  │           │
│  · …     │                                  │ collapsed │
│ Earlier  ├──────────────────────────────────┤ by        │
│  · …     │  [ composer          ]    ⚙  ▶   │ default   │
└──────────┴──────────────────────────────────┴───────────┘
```

- **Left — Conversations.** Persistent rail, promoted out of today's buried 4th tab.
- **Centre — Transcript.** **Per-block measure, not a global `max-w-3xl`**: prose at `3xl`,
  but tables, ArchiMate listings and rationalization matrices may break the column. A fixed
  narrow measure is right for prose and wrong for this product's actual payloads.
- **Right — Evidence.** Collapsed by default; holds Context / Query / Alerts.

**DOM order must be transcript → composer → left rail → right drawer**, whatever the visual
order. Today the sidebar precedes the transcript (`:395` before `:576`), so a keyboard user
traverses ~20 sidebar controls before reaching the message they came to read. Landmarks:
`<nav aria-label="Conversations">`, `<div role="log" aria-label="Conversation transcript">`,
`<aside aria-label="Evidence">`.

Use `dvh`, not `vh` (`:149` breaks under mobile browser toolbars).

**Below `lg`**, the rail and drawer overlay the transcript and therefore *become* modal:
trap focus there and only there. Icon-width collapse requires `aria-label`s that survive the
visible label being hidden.

---

## 5. The Assistant control

v1 proposed collapsing four selectors into one and **deriving domain from persona**. Review
established that domain and persona are orthogonal: `persona` selects voice; `domain`
selects **which portfolio context is loaded** (`get_domain_context` dispatches to nine
loaders). Server-side derivation happens only when `domain == "general"`. Under v1's rule,
"Data Architect looking at vendor data" becomes unreachable, and — because of B8 — the AI
Data Architect would never load the data-architecture context at all.

**Revised.** One button, popover with **two visible rows**:

> **AI Data Architect** — canonical entities, classification, lineage
> Looking at: **[Data architecture ▾]** · Vendors · Applications · Whole portfolio

The second row is labelled **scope**, not "domain" — the noun the user already thinks in.
Defaulted from `default_domain`, always visible, changeable in one click. Model and template
sit in a subordinate footer strip.

Alongside:

- **Fix B8** — `data_architect` defaults to `data_architecture`.
- **Surface `compliance` as a scope on every persona** (B6). "Check this against our
  principles" is a question every one of these roles asks, and it is the ARB's question.
- **Resolve `capability_architect`** (B7) — expose it or delete it.
- **Reconnect the charters (B1)** — the highest-value item in this document.

**Accessibility constraint (Principle 4).** Four native `<select>`s today are labelled,
keyboard-operable and mobile-native for free. The replacement ships only with
`aria-haspopup`, `aria-expanded`, roving focus, arrow keys, Escape, and focus return to the
trigger. If that cannot be built properly, keep native selects and fix their labels instead
— that is a better outcome than a prettier control that AT users cannot operate.

---

## 6. Answer rendering

Enable the typography plugin and remap the prose variables to design tokens.

> **Verified three times, including against the real config and content globs.** The
> standalone CLI at `scripts/bin/tailwindcss.exe` resolves `require('@tailwindcss/typography')`
> with no npm install and no network. A baseline build is **byte-identical** to the committed
> `tailwind-output.css` (152,867 B — so `css-build` is green today); with the plugin it is
> **172,313 B (+12.7%)**, emitting 150 `.prose` selectors including `list-style-type: disc`
> and `h2{font-size:1.5em}`. Air-gap posture unaffected. It **will** fail
> `build_css.py --check` until the rebuild is committed, which §14 already mandates.

**The remap is 36 variables, not a handful** — 18, each with an `invert` twin. Because every
source token is already `.dark`-aware, **both halves take identical values** and dark mode
resolves per theme. Two traps:

- **`--tw-prose-links` must map to `--info`, not `--primary`.** `--primary` is near-white in
  dark mode (`210 40% 98%`), which would make links indistinguishable from body text.
  `DESIGN.md:93-96` warns about exactly this.
- **`--tw-prose-kbd-shadows` takes an R G B triplet**, not HSL — the plugin injects it into
  `rgb(var(--…) / …)`.

Also: `pre-bg` → `--muted` and `pre-code` → `--foreground` must be set together, or code
blocks render white-on-white in light mode. `prose` sets `max-width: 65ch`, which fights the
wrapper — use `prose max-w-none` inside the measure wrapper. Keep the streaming caret
**outside** the prose container so it does not inherit paragraph spacing.

> **Correction to v1:** the `design_tokens` gate scans templates only and never reads
> `tailwind.config.js`, so stock `prose` would *not* trip it. Do the remap because
> `DESIGN.md` requires it, not because CI would catch it.

Plus: code blocks with language label and copy button; tables in `overflow-x-auto`; **one
persistent streaming bubble**, never destroyed and rebuilt (D4).

---

## 7. Evidence — replacing v1's grounding binary

v1 proposed a binary: `sources.length > 0` → "Grounded in N records", else "General
knowledge — not checked against your portfolio."

**That is unshippable.** Because of B2, an answer that ran `propose_rationalization` or
`simulate_impact` against real tenant rows produces zero sources and would render *"not
checked against your portfolio"* — a false provenance claim, in the UI, on the highest-stakes
answers. It is the `fabricated-data` violation v1 was written to avoid, pointing in the
direction the gate cannot see. Two further faults: the *default* path injects
`get_domain_context` data with no tool call and would always read as ungrounded; and "N
records" is rows *returned*, capped at `MAX_SOURCES = 25`, so on a large tenant it is a
truncation constant presented as a count.

**Build an evidence trail instead**, from the `tool_start` / `tool_result` events the server
already emits and the client already discards (B5). Under each answer, one row per tool call
in execution order: the tool in plain language, the arguments it ran with, and the shape of
what came back.

> Searched applications · status = production · **47 matched, showing 15**
> Validated SAP clean core · Solution: Order-to-Cash · score 62

Rows expand to the records, each linked. Three honest states fall out, none a score:

| State | Meaning |
|---|---|
| **Retrieved** | Tools ran; here is what they returned |
| **Context only** | No tool ran; the answer used the portfolio snapshot in the prompt — name which, and offer "verify this" (re-ask forcing a tool call) |
| **Unretrieved** | Neither. Say so |

**Coverage honesty is the point.** When a tool returned 15 of 47, the row says so — always,
structurally, not as prose the model may omit. An architect's real question is never "is this
grounded" but *"did it look at everything, or at the first page?"* `_AGENT_PREFIX` rule 9
already instructs the model to report N of M; the tool results carry it.

**Prerequisite:** extend `_TOOL_ENTITY` to the remaining read tools. This is backend work,
so §14 sequences it accordingly.

**Decision retained from v1: do not wire `AIConfidenceCalculator` or
`AIHallucinationDetector`.** Both were read in full and the reasoning was endorsed by review.
**The calculator.** No method scores a chat response at all — the four public methods score
ArchiMate generation, vendor matching, entity matching and APQC matching. A number for a chat
answer would have to be invented. Each score also carries a hardcoded 20%: `historical_score
= 0.7` in `calculate_archimate_confidence` (`:73`) and `boundary_match = 1.0` in
`calculate_apqc_match_confidence` (`:219`).

> **Correction to v1**, which said "two hardcoded constants carry 40% of the weight." They
> are in *different methods* — 20% each of its own score, never 40% of one. The conclusion
> holds; the arithmetic did not.

**The detector.** `HALLUCINATION_INDICATORS[1]` is exactly `all|none|every|only|always|never`
— the language of true statements about a finite portfolio. The real formula is
`min(len(issues) * 0.15 + confidence_penalty, 1.0)` (`:98`), where `confidence_penalty` adds a
further **0.1 per absolute-statement match** (`:68`). With `critical` starting at 0.6 (`:145`),
**three** occurrences of "all"/"none"/"every" (3 × 0.25 = 0.75) pin an answer to *critical —
mandatory human review*. v1 said "~7 flags" and thereby **understated** the problem.

Conversely, v1 overstated one point: `_has_citation` has a fourth pattern v1 missed —
`according to|as per|based on|source:|reference:` (`:132`). An answer saying "Based on your
portfolio, 12 applications…" within ±100 characters of the number is *not* flagged. So "every
numeric claim in every answer" is too strong; many are exempted by a phrase the model happens
to use.

Both corrections leave the decision intact: a detector that reports *critical* on three
correct words is unusable, and the exemption is accidental rather than principled. Leave both
services in place with a one-line note recording why, so this is not rediscovered.

---

## 8. The answer becomes work

The registry exposes 37 tools including writes: `create_solution`, `create_driver`,
`create_goal`, `create_constraint`, `create_requirement`, `create_risk`, `create_option`,
`mark_option_recommended`, `propose_rationalization`, `submit_for_arb_review`,
`create_archimate_element`, `update_solution_fields`. Entirely invisible today.

- **Action receipts, inline.** When a turn ran write tools, a card states what was created or
  changed, linked to the records. Same discipline as §7.
- **Proposal cards, inline.** Rendered attached to the answer that caused them, with
  Approve/Reject in place. **Note:** the live modal uses
  `GET /ai-chat/approvals/pending` and `POST /ai-chat/approvals/<id>/{approve,reject}`
  (`approval_modal.js:49,79,121`) — *not* the `approval_gate.py` 202 payload v1 pointed at.
  Reconcile the two mechanisms before building. Destructive governance actions inside a live
  region must be announced once on arrival and never re-announced.
- **Next artifact, driven by which tools ran** — never by parsing prose.
  `create_option`/`mark_option_recommended` → *Draft an ADR*; `propose_rationalization` →
  *Start a business case*; `query_capability_gaps` → *Create work packages*. No mapping, no
  chip. A wrong suggestion is worse than none.

**Defining "write tool."** The registry does not mark writes. Add a **`mutates` flag to each
tool entry in `tools/registry.py`** — not a `startswith("create_")` heuristic, which would
miss `mark_option_recommended`, `submit_for_arb_review`, `link_*`, `update_*`.

> Use the flag rather than v1's separate allow-list constant: `toggle_auto_execute`'s
> docstring (`chat_core.py:1443-1461`) already recommends exactly this — splitting reads from
> writes via a `mutates` flag — for the approval tiering. One source of truth serves both,
> where a parallel constant would drift from it.

> `REQUIRE_AI_APPROVAL` defaults to `False` (`approval_gate.py:53`), so AI writes currently
> execute immediately and the Approvals badge is permanently empty. Flipping it is a
> governance decision outside this work. Receipts matter more while it is off, not less.

### 8.1 North star, and the boundary of this spec

The artifact — an ADR or ARB submission that opens beside the transcript, is edited by
conversation, carries its evidence trail frozen per section, and gives an ARB reviewer a
read-only lane with "ask about this section" — is the correct end state and the thing
ChatGPT structurally cannot do.

**It is out of scope for this rebuild.** It is a new object with its own persistence,
permissions and review surface, not a page redesign. This spec ends at the *seam*: receipts
and next-artifact actions must emit enough structure (which tools, which records, which
persona, which model, when) that the artifact can be built on top without re-plumbing.
Recorded here so the seam is designed for it rather than retrofitted.

---

## 9. Accessibility requirements

Not a §13 line item. Acceptance criteria for the sections above.

**Transcript and streaming.** Remove `aria-live` from `#messages-container` (`:578`) — with
a full `innerHTML` rewrite per token (`:2538`) it queues an announcement of the entire
accumulated answer on every token, leaving AT users an unusable backlog. Use
`role="log" aria-label="Conversation transcript"` for the append-only transcript, plus a
visually-hidden `role="status" aria-live="polite" aria-atomic="true"` carrying **state, not
content**: "Generating response…", "Response stopped", "Response complete — 4 paragraphs,
6 records". `aria-busy` on the streaming bubble; `tabindex="-1"` on it so focus can be moved
there on completion. The base layout already provides `Alpine.store('announcer')`
(`admin_base.html:404-411`) and this page never uses it.

**Tabs (`:401-419`).** Not tabs today: no `role="tablist"`/`tab`/`tabpanel`, no
`aria-selected`, no `aria-controls`, no roving `tabindex`, no arrow keys. Selection is
conveyed by colour alone. Three carry `aria-label="Action"` and one `aria-label="Conversations"`
over visible text "Chats" — both **override the visible label**, failing WCAG 2.5.3 Label in
Name (A). **Delete all four `aria-label`s**; add real tablist semantics and arrow/Home/End
handling. Fix D21 while there.

**Names.** `#domain-selector` (`:171`), `#model-selector` (`:227`), `#template-selector`
(`:238`) have no label — three guaranteed `select-name` criticals. `.element-checkbox`
(`:1454`, `:1475`) has `id` but no label. The "Docs" (`:250`) and "Match" (`:254`) buttons
name themselves with `<span class="hidden lg:inline">`, so below 1024px they have no
accessible name — and axe runs at 1440×900, so CI will never see it.

**Focus.** Of five surfaces, only the approvals modal is correct. Create-solution has no
Escape (it listens for no `modal-escape` event); the entity modal has no trap, no restore, no
Escape and no `role="dialog"` (plus D16); the mobile sidebar and document panel have none of
the above. Route them through `Platform.modal`. Background `inert` is a no-op for all of them
— `modal.js` inerts `document.body.children`, but `admin_base.html` nests everything under
one app-shell child, so nothing is ever inerted.

**Contrast.** Fix D18 by adding `--warning-emphasis` (none exists; only `destructive` and
`info` have emphasis variants). Move the five `text-destructive`-on-tint sites (`:299`,
`:319`, `:367`, `:1164`, `:1734`) to `text-destructive-emphasis` per `DESIGN.md:80-91`. Add
`--primary-emphasis`: `text-primary` on `bg-primary/10` is **4.50 — passing by 0.00** across
~20 sites and will fail on any nudge to `--primary`.

**Motion.** Zero occurrences of `prefers-reduced-motion` in the file or in
`shadcn_tokens.css`, against a blinking caret for the whole response, 6 `animate-bounce`, 4
`animate-spin`, `fadeIn` with translate, and Alpine scale transitions. Add the global
reduced-motion block to `shadcn_tokens.css` so the whole product benefits, and make the caret
static under reduced motion.

**Message actions.** `opacity-0 group-hover:opacity-100 group-focus-within:opacity-100
focus:opacity-100` — never `hidden`/`invisible`/`display:none`, which removes them from the
tab order and defeats the stated goal. The codebase already gets this wrong at `:3540`, where
the delete-conversation button is focusable but fully transparent when focused (WCAG 2.4.7).
Labels must identify the message ("Copy response 3"). Thumbs need `aria-pressed`. Copy needs
a `role="status"` confirmation.

**Evidence strip (§7).** A `<button aria-expanded aria-controls>` whose accessible name is
the whole sentence. The **Context only / Unretrieved** states must be announced with equal
prominence — a visual-only caption is exactly the provenance signal a blind architect cannot
afford to miss before an ARB. If the drawer auto-opens, move focus and announce it.

**Right drawer.** Not a modal above `lg`: no focus trap, no `role="dialog"`. Persistent
toggle with `aria-expanded`/`aria-controls`; `hidden` (or `inert`) when collapsed — never
merely `width:0`, which leaves invisible focusable children; focus to the panel heading on
open; Escape collapses and returns focus.

**Skip links.** The base layout's skip target is `#main-content`, which here is the whole
three-pane app. Add page-local "Skip to conversation", "Skip to composer", and — the highest
-value affordance on a streaming page — **"Skip to latest response"**.

**Keyboard.** ⌘K new chat, Esc stop (with an audible confirmation, not just a visual state
change), ↑ edit last message **guarded to fire only when the composer is empty**, or it
fights caret movement in a multiline field. Provide a discoverable shortcut list. The Stop
button must occupy the same DOM position as Send so focus is not lost when they swap.

---

## 10. Control and failure

- **Stop** — real `AbortController` (D1)
- **Scroll** — anchor only within ~100 px of the bottom; otherwise a real `<button>` pill
  with an accessible name, announced via the status region (D3)
- **Errors** — destructive-tinted card with the real message and **Retry**, never a fake AI
  turn (D7)
- **Message actions** — Copy · Regenerate · 👍 👎 · *Open in Composer*. Thumbs POST to the
  unused endpoint — **gated on B4 being fixed first** (§17)
- **Model provenance** — stamp the *resolved* model on each answer.
  `_resolve_requested_model` (`agent_runner.py:345`) silently falls back when a requested
  model is not configured, logging a warning the user never sees. Which model wrote a
  paragraph is provenance, not a preference

---

## 11. Code structure

```
app/templates/ai_chat/index.html   ~450 lines, markup only        (was 3,591)
app/static/css/ai_chat.css         chat chrome not expressible as utilities
app/static/js/ai_chat/             ← ALREADY EXISTS, 8 files, ~120 KB
    document_upload.js  (live)     ┐
    approval_modal.js   (live)     │ keep — §12.1 depends on them
    business_output.js  (live)     │
    analytics_charts.js (live)     │
    page_guide.js       (live)     ┘ loaded globally by admin_base.html
    slash_commands.js   (dead)     ┐
    ai_personas_table.js(dead)     │ confirm and delete
    inline_chat.js      (dead)     ┘
    transport.js   NEW  send · stream · abort · threads · models
    render.js      NEW  markdown · sanitise · evidence trail · receipts · actions
    commands.js    NEW  the 11 /slash handlers + action cards
    panels.js      NEW  context · NL query · recommendations · genome
    app.js         NEW  Alpine components + wiring
```

This is not a greenfield directory — v1's diagram implied it was. The five live files stay;
`document_upload.js` and `approval_modal.js` own 9 of the 35 endpoints in §12.1 and the five
CustomEvents in §12.3.

Delete `app/static/js/ai_chat.js` (D10) and `#command-hints`. Replace the `onclick=`
attributes at `:250` and `:551` (DESIGN.md forbids). Add SRI to `marked.min.js` (D19). Delete
`context_data` from `chat_views.py` (D20).

---

## 12. Preserved behaviour — the contract

> v1's contract named 24 of 35 endpoints and asserted two dead ones were live. It is replaced
> wholesale. **Walk this list item by item before claiming done.**

### 12.1 Endpoints — 35

**Template (26):** `/ai-chat/message` · `/ai-chat/message/stream` · `/ai-chat/models` ·
`/ai-chat/nl-query` · `/ai-chat/threads` · `/ai-chat/threads/<id>` (GET + DELETE) ·
`/ai-chat/feedback` · `/ai-chat/context/<domain>` · `/ai-chat/recommendations` ·
`/ai-chat/api/health/llm` · `/ai-chat/chat/{generate-archimate, generate-archimate-description,
map-apqc, save-insights, bulk-process, gap-analysis, discover-vendors, create-solution-diagram}` ·
`/ai-chat/architect/{analyze, viewpoints, arb-ready}` · `/api/codegen/genome/extract` ·
`/solutions/create-with-draft` · and four with **no live call site** (D24):
`/ai-chat/generate-archimate`, `/ai-chat/map-apqc`, `/ai-chat/apply-archimate`,
`/ai-chat/apply-apqc` — delete rather than port, but decide explicitly.

**`document_upload.js` (6):** `POST /ai-chat/upload-document` · `POST /ai-chat/create-elements` ·
`GET /ai-chat/documents` · `GET /ai-chat/documents/<id>` ·
`POST /ai-chat/documents/<id>/re-analyze` · `POST /ai-chat/documents/<id>/feedback`.

**`approval_modal.js` (3):** `GET /ai-chat/approvals/pending` ·
`POST /ai-chat/approvals/<id>/approve` · `POST /ai-chat/approvals/<id>/reject`.

**Cross-module reads from `document_upload.js` (3)** — outside the `/ai-chat` prefix, so easy
to miss when porting: `/capability-map/api/applications` ·
`/dashboard/api/applications/table-data` · `/dashboard/api/vendors/organizations`.

All 35 were verified to exist against a booted `app.url_map` (3,107 rules).

### 12.2 Deep links — 7 params, 6 external call sites

`element_id`, `context_type`, `domain`, `context`, `id`, `mode`, `panel` (read at
`:928`, `:2561`, `:3466-3507`). Linked from `applications/detail.html:537`,
`vendors/vendor_detail.html:63`, `solutions/detail.html:515`, `archimate/composer.html:546`,
`applications/dashboard.html:531,670`, `application_mgmt/application_detail.js:19`.

**Drop these and every "Ask AI about this application / vendor / solution" button in Archie
lands on a blank chat.** Two params are linked-to but never read — `?action=generate_archimate`
and `?workspace=` — resolve rather than port.

### 12.3 Integration seams

- **5 window CustomEvents** — the entire seam between the document panel and the transcript:
  `add-document-analysis`, `show-notification`, `ask-question`, `link-to-entity`,
  `create-entity` (`:3248,3264,3270,3282,3288` ← `document_upload.js:604,680,612,804,815`).
- **`data-modal-open` / `data-modal-close` + `hidden` attribute**, served by the delegated
  handler in `ui/modal.js:562-573`. The approvals modal opens through this, **not** Alpine.
  Switching to `x-show` silently breaks it.
- **11 `window.*` globals**: `__threadId`, `loadSessionList`, `loadSession`,
  `deleteConversation`, `startNewConversation`, `_genomePanelInstance`, `applyAction`,
  `domainConfig`, `promptTemplates`, `personaConfig`, `csrfToken`. `loadSessionList` is called
  across a `<script>` boundary (`:2434`, `:2533`) — preserve that seam or a new chat will not
  appear in the rail until refresh.

### 12.4 Behaviours

11 slash commands (`/generate-archimate`, `/map-apqc`, `/save-insights`, `/bulk-process`,
`/gap-analysis`, `/discover-vendors`, `/create-diagram`, `/analyze`, `/viewpoints`,
`/arb-ready`, `/help`) and their action cards · the 14-branch delegated `data-action`
vocabulary (`:2767-2871`) · **NL ArchiMate interception** (4 regexes, `:2272-2283`,
intercepting *before* the chat pipeline) · **advisory-query re-routing** (`isAdvisoryQuery`
`:2656-2664`, which pulls "recommend/assess/why/risks/consolidat" out of `nl-query` into the
chat — a comment at `:2651` says it exists to fix exactly this regression) · portfolio health
gauge + alert badge (`:516-524`, `:3117-3143`) · genome panel · document upload ·
approvals modal · NL query + quick queries · entity action modal · session history CRUD ·
LLM health banner (60 s poll) · create-solution-from-brief · `chat_bootstrap_error` degraded
banner and the `_fallback_domain_config`/`_fallback_persona_config` path, which must stay in
sync with the hardcoded `<option>` values at `:173-179` and `:203-218`.

**SSE wire contract:** `data:` framing, `[DONE]` sentinel, `{type:'token',text}`,
`{type:'done',response,domain,sources,error}`, `{thread_id}` — plus the **automatic fallback
to `/ai-chat/message` when streaming fails** (`:2418-2419`). Lose that and one bad proxy means
no answers at all. The `{action:'redirect'}` branch (`:2535`) has no server emitter; delete it.

**Payload is 10 fields**, not 4: `message, domain, template_name, element_id, context_type,
persona, model, thread_id, image_data, image_media_type`. `element_id`/`context_type` are how
§12.2's deep-link context reaches the model.

### 12.5 Do not port — already dead

D10 · D14 · D15 · D24 · D25 · the static `#entity-action-modal` block (`:825-860`, 6 dead ids)
· `applyArchimateElements` (`:1817`) · the `redirect` stream branch · `window.currentDomain`
(D22) · `data.metadata?.processing_time` (`:2475` — the server returns
`processing_metadata`, so this is always `undefined`; **do not "fix" by inventing a number**)
· `#recommendations-list` (static wrapper; JS writes `#recs-content`) · the 7 `onclick=`
attributes in generated markdown, which DOMPurify strips before insertion — the `<a href>` is
what works · `context_data` (D20).

**Where a "preserved" feature is already broken (D14, D15), preserving it means fixing it.**
Porting faithfully would reimplement a corpse.

---

## 13. Backend changes

The list is shorter than v1 *and* shorter than this document's own first draft: the evidence
trail and receipts need **no** backend change, because `tool_start`/`tool_result` and
`actions_taken` already reach the client and are thrown away (B5).

1. **Reconnect the persona charters** (B1) — ~2 lines, highest value in the document.
2. **Extend `_TOOL_ENTITY`** to the remaining read tools (B2) — the only prerequisite for §7.
   `_source_url` already has unreachable branches for `vendor` and `solution`
   (`agent_runner.py:127-130`), so the shape is anticipated.
3. **Add the `mutates` flag** to `tools/registry.py` (§8).
4. **Fix `AIChatFeedback` tenancy** (B4) — see §17.
5. **Either implement vision on the `AgentRunner` path or remove the attach UI** (D13/B3).
   Shipping a control that silently discards its input is the worst option and is the status
   quo.
6. **Fix `PERSONA_CONFIGS["data_architect"].default_domain`** (B8).

Everything else in §7 and §8 is client work against data already on the wire.

---

## 14. Verification

> v1's §13 was wrong in both directions. Both corrections below were measured, not reasoned.

**Add the page to CI first.** `/ai-chat` is in no smoke test (§1.5). **Before** the rebuild:
add `("enterprise_architect", "/ai-chat")` to `AUDIT` in `test_accessibility_audit.py`,
regenerate with `SMOKE_A11Y_UPDATE_BASELINE=1`, and add rows to `test_archetype_journeys.py`
and `test_authorisation_matrix.py`. Adding them afterwards bakes whatever is left into the
accepted set. Shrinking the new a11y entry is then an explicit deliverable.

**`design_tokens` — the real mechanism.** The gate counts only
`gray|grey|slate|zinc|neutral|stone|blue|red` (`check_design_tokens.py:36`). **`emerald`,
`purple`, `orange`, `cyan` are not counted**, so v1's plan to remove those four tiles moves
the number by zero. This file contributes **2** (`from-slate-500`, `to-slate-600` at `:1158`);
5 more are suppressed by `token-migration-ok` (`:1152` ×2, `:1164` ×2, `:3235`). Stripping
markers without converting takes the file 2 → 7 and the repo 90 → 95.
**Target: file 2 → 0**, by converting `:1158` to `from-muted-foreground`, converting the 5
suppressed blue/red gradients to `from-primary`/`from-destructive`, then deleting the markers.
Repo 90 → 83. The `emerald`/`purple`/`orange`/`cyan` removals still happen — for `DESIGN.md`
and D6, not for the gate.

> **`CLAUDE.md` is stale.** It states 164 raw-colour uses; `verification_baseline.json` says
> **90**. Correct `CLAUDE.md` as part of this work.

**Everything else:** `python scripts/verify.py` green · `fabricated-data` stays 0 (§7 and §8
are where it could regress) · `air_gap` stays 0 · `sri` — fix D19 · `template_syntax`,
`boot_health`, `tests` pass · `python scripts/build_css.py` rebuild committed (mandatory —
template classes change).

**New tests:** route test for `/ai-chat` anchors; tests for the feedback POST path (after
B4); a tenancy test that feedback cannot be read cross-org; a test that the SSE fallback to
the non-streaming endpoint still fires.

---

## 15. Sequencing

Backend seams move earlier than v1, because §7 depends on them.

1. **CI coverage first** (§14) — nothing below is verifiable without it.
2. **Parameter-effect map** (§3).
3. **Typography** (§6) — smallest diff, largest visible effect, independently revertable.
4. **Backend seams** (§13.1–3, 13.7) — charters, `_TOOL_ENTITY`, tool events. Small, and
   everything differentiating depends on them.
5. **Port behaviour verbatim** — the 11 slash commands, genome, approvals, doc upload, NL
   query (with advisory re-routing), entity modal, deep links, CustomEvents, history. No
   restyling. This is where a silent drop would happen.
6. **Transcript mechanics + a11y** (§9, §10).
7. **Evidence trail** (§7).
8. **Layout and Assistant control** (§4, §5).
9. **Receipts and next artifact** (§8, §13.4).
10. **Opening screen** (§16).

Steps 1–6 restore correctness and are the intended stopping point if this runs long.

---

## 16. The opening screen

Replace the 21 entry points with what is happening in this tenant, from
`GET /ai-chat/recommendations` — already called, into a tab nobody opens. Each item one click
into a grounded conversation; assistant picker and a few starters below.

> This is the one place Principle 3 is overridden. Stated openly rather than hidden behind
> the principle.

**Failure modes, all of which must be designed for:**

- **Empty tenant.** Day one, zero apps: the endpoint returns nothing and the flagship screen
  is blank at the moment the product must be most persuasive. The empty state **is** the
  onboarding path — import a portfolio, or start a solution design, which needs no portfolio.
- **5,000 apps.** Three items surfaced from thousands is an editorial claim. Show the
  denominator and the basis: "3 of 214 open findings, ranked by portfolio impact", with a link
  to all of them.
- **Disagreement.** Per-item dismiss with a reason, persisted per user, feeding the ranking.
  Without it the wrong item sits at the top forever and the panel loses credibility in a week.
- **Latency, staleness, failure.** The most prominent element now depends on a network call.
  Specify the loading state; the endpoint returns 500 with empty arrays, which is
  indistinguishable from "nothing to report" — distinguish them. Timestamp the data.
- **Permissions.** Recommendations are portfolio-wide; a CIO and a programme-scoped solution
  architect should not see the same list. Scope by `enterprise_role`.
- **Onboarding.** First run should *demonstrate*: one grounded question executed against the
  user's real portfolio with the evidence trail open — so the mechanism is visible before it
  is trusted. Nothing currently tells a new user the assistant can write to the repository,
  which is the most surprising and valuable fact about it.

---

## 17. Blockers and open decisions

**B4 — `AIChatFeedback` tenancy is a blocker, not a footnote.** v1 deferred it. The model has
no `TenantMixin` and no `organization_id`, so it sits outside ORM tenant isolation while
storing AI answers — portfolio content — and the admin dashboard aggregates across
organisations. This rebuild makes the table non-empty for the first time. **Either the column
and the mixin land before the thumbs are wired, or the thumbs are not wired.** Landing a
known cross-tenant read three commits after `fix(ai-chat): cross-tenant leak…` is not
defensible.

**D13 — vision.** Implement on the `AgentRunner` path or remove the UI. Not both, not neither.

**Deferred deliberately:** the artifact object (§8.1) · flipping `REQUIRE_AI_APPROVAL` ·
`multi_domain_chat_service.py`'s ~8,300 lines of workflows reachable only through the legacy
blueprint (CAP-014 capability design, AIC-305 ADM, vision, RAG, vendor comparison) — record
which are intentionally dead before deleting anything · out-chatting ChatGPT at chatting.

---

## 18. What v1 got wrong

Kept as a record of how the errors happened, so the pattern is visible.

| v1 claim | Reality | Root cause |
|---|---|---|
| Grounding is a client-only change | Needs `_TOOL_ENTITY` extended and tool events surfaced | Assumed `sources` covered the tools |
| Binary grounding is honest | False negatives on the highest-stakes answers (B2) | Verified how `sources` is *built*, never its *coverage* |
| Domain is redundant with persona | Orthogonal; derivation breaks real combinations | Read the client's selectors, not the server's dispatch |
| "Backend stays still" | Seven backend changes (§13) | Same |
| §11 was the contract | 24 of 35 endpoints; 2 dead ones asserted live; deep links, CustomEvents and modal convention all absent | `fetch()` grep without tracing callers |
| Export / rate-limit badge / composer handoff preserved | All three already broken | Assumed a rendered control works |
| `design_tokens` will fall | Would rise; the removed colours are not counted | Never read the gate's source |
| The axe baseline must not regress | The page is not in the audit | Never read the audit list |
| One backend seam | See above | — |
| D1: `#stop-btn` "referenced nowhere" | It is fully wired, with an `AbortController`, in the dead `ai_chat.js`. Same defect as D10 | Grepped the template, not the tree |
| D12: the string is "typed at the LLM" | It goes to `POST /ai-chat/nl-query`; and a *second* button has the same bug | Guessed the code path instead of tracing the handler |
| D6 cited `:675-702` | Those lines never paint (D23); the live ones are `:3407-3431` | Read the server-rendered markup, not what runs |
| "Two constants carry 40% of the weight" | Different methods — 20% each of its own score | Conflated two functions while summarising |
| Detector: "~7 flags → critical" | `confidence_penalty` adds 0.1 per match; **three** words suffice | Read the formula's first term only |
| Detector: "every numeric claim flagged" | A fourth citation pattern exempts "based on…" | Missed a branch |
| 44 tools in the registry | **37** | `grep -c '"name":'` also matched nested parameter schemas |

The pattern: **v1 verified the client exhaustively and the server not at all.** §3 exists to
stop that recurring.

The second pattern, visible in the lower half of this table: **counting with a grep instead of
tracing a path.** Every one of those errors came from matching a string rather than following
what calls what. Where this document states a mechanism, it now cites the call site, not the
match.

> This table includes errors in *this document's own first draft*, not only v1's. The fourth
> review landed after §13 was written and removed a backend change it had invented.
