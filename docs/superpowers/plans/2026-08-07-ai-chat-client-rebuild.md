# /ai-chat Client Rebuild — Implementation Plan (Plan 2 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace a 3,591-line template carrying ~2,500 lines of inline JavaScript with a slim template plus five focused modules — preserving every working behaviour, and fixing the transcript mechanics and accessibility defects that the current structure makes impossible to fix safely.

**Architecture:** Behaviour is ported **verbatim first, restyled second**. Task 1 builds the browser coverage that makes every later task verifiable — without it, this rebuild is unfalsifiable. Tasks 2–7 extract modules one seam at a time, each independently revertable. Tasks 8–11 then fix mechanics and a11y in code that is finally small enough to reason about.

**Tech Stack:** Flask · Jinja2 · Alpine.js v3 · Tailwind CSS v3 (standalone CLI) · Playwright · axe-core

**Inputs:**
- Spec: `docs/superpowers/specs/2026-08-07-ai-chat-rebuild-design.md` (v2)
- Parameter map: `docs/known-issues/ai-chat-parameter-effects.md` — **read this first**
- Plan 1 (landed): branch `fix/ai-chat-foundation`

## Global Constraints

- **Read `DESIGN.md` before editing any template, CSS, or front-end JS file.**
- **The contract in spec §12 is binding.** 35 endpoints, 7 deep-link params, 5 CustomEvents, the `data-modal-open` convention, 11 `window.*` globals. Walk it item by item before claiming done.
- **Never use raw Tailwind colours.** `design_tokens` baseline is **88** (`verification_baseline.json`) — it must not rise.
- **Never invent data.** `fabricated-data` must stay 0. `null` → `—`.
- **No `onclick=` attributes.** Alpine `@click` or `data-action` delegation.
- **`git add <file>` — never `git add -A`.** Another session may be working in this tree.
- **Editing template classes requires `python scripts/build_css.py`.**
- **Verification:** `python scripts/verify.py --tag static` must stay 14/14.
- **Do not port dead code.** Spec §12.5 lists it. Porting a corpse faithfully is still porting a corpse.

---

## Task 1: A browser journey that proves the chat works

Everything below rewrites code with no runtime coverage. This task is the instrument. It must land first and must be red-then-green: write it against the **current** page, watch it pass, and it becomes the regression net for the rebuild.

**Files:**
- Create: `tests/smoke/test_ai_chat_journey.py`
- Modify: `tests/smoke/test_authorisation_matrix.py`

**Interfaces:**
- Consumes: the `browser`, `live_server`, `seeded` fixtures from `tests/smoke/conftest.py`; `seeded["emails"]["enterprise_architect"]`.
- Produces: the journey every later task runs before committing.

- [ ] **Step 1: Read the existing harness**

Read `tests/smoke/conftest.py` and `tests/smoke/test_archetype_journeys.py` in full. Match their fixture use, login helper, and timeout constants exactly — do not invent a second style.

- [ ] **Step 2: Write the journey**

Create `tests/smoke/test_ai_chat_journey.py`. Cover the paths the rebuild can silently break. Mock nothing about the UI; the LLM may be unavailable in CI, so assert on **transport and DOM**, not on answer content.

```python
"""Browser journey for /ai-chat.

The page had no browser coverage at all, which is why a dead stop button, a
composer handoff writing a key nobody reads, and a modal that needed two
clicks to close all shipped unnoticed. Assertions here are about transport and
DOM, never about what the model says — the provider may be unavailable in CI.
"""
import pytest

from tests.smoke.conftest import PAGE_TIMEOUT  # match the module's own import style


@pytest.mark.smoke
def test_ai_chat_core_journey(browser, live_server, seeded):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.set_default_timeout(PAGE_TIMEOUT)
    page = ctx.new_page()
    try:
        _login(page, live_server, seeded["emails"]["enterprise_architect"])
        page.goto(live_server + "/ai-chat", wait_until="domcontentloaded")

        # The composer exists and Enter is bound (it was not, for a long time).
        assert page.locator("#user-input").is_visible()
        assert page.locator("#chat-form").count() == 1

        # All four sidebar panels toggle, and exactly one is visible at a time.
        for tab in ("context", "query", "alerts", "history"):
            page.click(f"#tab-{tab}")
            page.wait_for_timeout(200)
            visible = [
                t for t in ("context", "query", "alerts", "history")
                if page.locator(f"#panel-{t}").is_visible()
            ]
            assert visible == [tab], f"expected only panel-{tab}, saw {visible}"

        # No uncaught console errors on load or interaction.
        assert not _console_errors(page), _console_errors(page)
    finally:
        ctx.close()
```

Write `_login` and `_console_errors` as module-level helpers. `_login` mirrors `test_accessibility_audit.py:56-68`. `_console_errors` attaches `page.on("console", ...)` **before** `goto` and collects `msg.type == "error"`.

- [ ] **Step 3: Run it against the current page**

Run: `pytest tests/smoke/test_ai_chat_journey.py -v`
Expected: **PASS** on the tab assertions (Plan 1 fixed the `history` omission) and on the composer assertions.

If the console-error assertion fails, **read the errors before adjusting the test** — Plan 1 removed the vision wiring, and a dangling reference would show up exactly here. That is the test doing its job.

- [ ] **Step 4: Add the authorisation row**

In `tests/smoke/test_authorisation_matrix.py`, follow the file's existing row format to assert `/ai-chat` is reachable by `enterprise_architect` and rejected unauthenticated.

- [ ] **Step 5: Commit**

```bash
git add tests/smoke/test_ai_chat_journey.py tests/smoke/test_authorisation_matrix.py
git commit -m "test(ai-chat): browser journey covering composer, tabs and console health

The page had no browser coverage, which is how a dead stop button, a composer
handoff writing a key nobody reads and a two-click modal all shipped. This is
the instrument the client rebuild is verified against."
```

---

## Task 2: Extract `transport.js`

The first seam, and the safest: network calls have a clear boundary and no DOM dependencies.

**Files:**
- Create: `app/static/js/ai_chat/transport.js`
- Modify: `app/templates/ai_chat/index.html`

**Interfaces:**
- Produces, on `window.ArchieChat.transport`:
  - `sendMessage(payload) -> Promise<Response>` — POST `/ai-chat/message`
  - `streamMessage(payload, handlers) -> Promise<boolean>` — POST `/ai-chat/message/stream`; `handlers` is `{onToken(text), onToolStart(evt), onToolResult(evt), onDone(meta), onThreadId(id), onRedirect(url)}`; resolves `false` when the caller should fall back
  - `abort()` — aborts the in-flight stream
  - `loadModels() -> Promise<Array>` — GET `/ai-chat/models`
  - `listThreads() / loadThread(id) / deleteThread(id)`
  - `submitFeedback(rating, meta) -> Promise<void>` — POST `/ai-chat/feedback`

- [ ] **Step 1: Copy the SSE parser verbatim**

Move `streamAiReply`'s body into `streamMessage`, preserving **exactly**:
- `data:` line framing and the `[DONE]` sentinel
- `{type:'token'}`, `{type:'done'}`, `{thread_id}` handling
- returning `false` on empty output so the caller falls back to `/ai-chat/message`

Add `onToolStart` / `onToolResult` handler calls for the `tool_start` / `tool_result` events the server already emits and the current client discards. **Wire them to no-ops for now** — Plan 3 consumes them. Emitting them here means Plan 3 needs no transport change.

- [ ] **Step 2: Add the AbortController the page never had**

```javascript
let _controller = null;

async function streamMessage(payload, handlers) {
    _controller = new AbortController();
    const resp = await fetch('/ai-chat/message/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _csrf() },
        body: payload,
        signal: _controller.signal,
    });
    // …parser, unchanged…
}

function abort() {
    if (_controller) { _controller.abort(); _controller = null; }
}
```

`#stop-btn` has a working implementation in the dead `ai_chat.js:109,203-211` — read it before writing this, and salvage rather than reinvent.

- [ ] **Step 3: Load the module and delete the inline originals**

Add `<script src="{{ url_for('static', filename='js/ai_chat/transport.js') }}"></script>` **before** the existing inline blocks, and delete the functions it replaces. Keep the call sites unchanged for now — they call `ArchieChat.transport.*`.

- [ ] **Step 4: Verify**

Run: `python scripts/verify.py --tag static` → 14/14
Run: `pytest tests/smoke/test_ai_chat_journey.py -v` → PASS, no console errors

Then manually: send a message, confirm it streams; kill the network mid-stream and confirm the fallback to `/ai-chat/message` still fires (spec §12.4 — losing that means one bad proxy yields no answers at all).

- [ ] **Step 5: Commit**

```bash
git add app/static/js/ai_chat/transport.js app/templates/ai_chat/index.html
git commit -m "refactor(ai-chat): extract transport, and give the stop button an AbortController

The SSE parser, the non-streaming fallback and the thread endpoints move out
of the template unchanged. streamMessage now surfaces the tool_start and
tool_result events the server has always emitted and the client always
discarded — wired to no-ops until the evidence trail consumes them.

#stop-btn is finally reachable: the working AbortController implementation
already existed in ai_chat.js, the 169 KB file no template loads."
```

---

## Task 3: Extract `render.js`

**Files:**
- Create: `app/static/js/ai_chat/render.js`
- Modify: `app/templates/ai_chat/index.html`

**Interfaces:**
- Produces, on `window.ArchieChat.render`:
  - `escapeForHtml(v) -> string`
  - `renderMarkdown(text) -> string` — `marked` → DOMPurify, falling back to escaped plain text
  - `appendMessage(role, text, meta) -> HTMLElement`
  - `appendError(message, onRetry) -> HTMLElement`
  - `appendSystemMessage(text, type)`
  - `renderSources(sources) -> string`

- [ ] **Step 1: Port the sanitiser unchanged**

`renderMarkdownSafely` must keep its exact behaviour: `DOMPurify.sanitize(marked.parse(...))`, falling back to escaped text when either library is missing. The comment above it records a stored-XSS fix — **carry the comment across**; it is the reason the function exists.

- [ ] **Step 2: Stop destroying and rebuilding the finished bubble**

Current code does `wrap.remove()` then `appendMessage(...)`, causing a visible flash and scroll jump at the end of every answer. Instead, hand `appendMessage` the element that was streaming and let it finalise in place:

```javascript
function finaliseStreamedMessage(el, text, meta) {
    const body = el.querySelector('.message-content');
    body.innerHTML = renderMarkdown(text);
    el.querySelector('.stream-caret')?.remove();
    el.removeAttribute('aria-busy');
    el.insertAdjacentHTML('beforeend', renderSources(meta.sources));
    return el;
}
```

Keep the caret **outside** the prose container — inside it, the caret inherits paragraph spacing now that the typography plugin is live.

- [ ] **Step 3: Replace the fake error messages**

`appendMessage('ai', '**⚠️ Error:** …')` dresses a failure as an answer. Replace with a distinct card:

```javascript
function appendError(message, onRetry) {
    const div = document.createElement('div');
    div.className = 'mx-auto max-w-3xl rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive-emphasis';
    div.setAttribute('role', 'alert');
    div.innerHTML =
        '<div class="flex items-start gap-2">' +
        '<i data-lucide="alert-circle" class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true"></i>' +
        '<div class="flex-1"><p>' + escapeForHtml(message) + '</p></div>' +
        '<button type="button" class="js-retry inline-flex items-center rounded-md border border-input bg-background px-3 py-1 text-xs font-medium hover:bg-accent">Retry</button>' +
        '</div>';
    div.querySelector('.js-retry').addEventListener('click', onRetry);
    return div;
}
```

`text-destructive-emphasis`, not `text-destructive` — the base token is 3.30:1 on its own tint (`DESIGN.md:80`).

- [ ] **Step 4: Verify and commit**

Run `--tag static` (14/14) and the journey. Manually: force an error (stop the LLM provider) and confirm a red card with a working Retry, not a fake AI turn.

```bash
git add app/static/js/ai_chat/render.js app/templates/ai_chat/index.html
git commit -m "refactor(ai-chat): extract rendering; stop the end-of-answer flash and fake errors

The streamed bubble was removed and rebuilt on completion, so every answer
flashed and jumped. It is now finalised in place. Errors render as an error
card with Retry instead of an AI turn saying '**⚠️ Error:**', which dressed a
failure as an answer."
```

---

## Task 4: Extract `commands.js` — all 11, verbatim

The least-covered code in the file and the most likely silent drop. Port behaviour **exactly**; restyle nothing.

**Files:**
- Create: `app/static/js/ai_chat/commands.js`
- Modify: `app/templates/ai_chat/index.html`

**Interfaces:**
- Produces `window.ArchieChat.commands.handle(message) -> Promise<boolean>` — returns `true` when handled.

- [ ] **Step 1: Move the map and every handler**

All 11: `/generate-archimate`, `/map-apqc`, `/save-insights`, `/bulk-process`, `/gap-analysis`, `/discover-vendors`, `/create-diagram`, `/analyze`, `/viewpoints`, `/arb-ready`, `/help`.

Carry across the follow-up `data-action` buttons each renders: `apply-apqc`, `gap-analysis-tab`, `discover-vendors`, `architect-viewpoints`, `arb-ready`.

- [ ] **Step 2: Do not port the dead command path**

`handleCommand` → `generateArchimatePreview` → `mapApqcPreview` → `renderActionCard` → `window.applyAction` (~190 lines) is unreachable: the submit handler calls `handleChatCommand`, not `handleCommand`. Delete it, and with it the four endpoints that then have no caller: `/ai-chat/generate-archimate`, `/ai-chat/map-apqc`, `/ai-chat/apply-archimate`, `/ai-chat/apply-apqc`.

Confirm with `grep -n "handleCommand\b"` — one hit (its own definition) means dead.

- [ ] **Step 3: Keep the two interceptors that run before the pipeline**

Both live in the submit path, not the command map, and both are easy to lose:
- **NL ArchiMate interception** — `ARCHIMATE_NL_PATTERNS` (4 regexes) + `detectArchimateFreeformIntent` + `handleArchimateFreeform`, which fire *before* the chat request.
- **Advisory-query re-routing** — `isAdvisoryQuery()` pulls "recommend/assess/why/risks/consolidat/duplicat/rationali" out of the NL-query path into the chat. A comment in the source says it exists to fix exactly this regression; carry the comment.

- [ ] **Step 4: Verify each command still reaches its endpoint**

For each of the 11, type it and confirm the expected network call in devtools. This is a checklist, not a spot check — the whole point of the task.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/ai_chat/commands.js app/templates/ai_chat/index.html
git commit -m "refactor(ai-chat): extract all 11 slash commands, behaviour unchanged

Also deletes the ~190-line dead command path (handleCommand ->
generateArchimatePreview -> renderActionCard -> window.applyAction), which the
submit handler never called, and the four endpoints left with no caller."
```

---

## Task 5: Extract `panels.js`

**Files:**
- Create: `app/static/js/ai_chat/panels.js`
- Modify: `app/templates/ai_chat/index.html`

**Interfaces:**
- Produces `window.ArchieChat.panels`: `switchTab(name)`, `loadDomainContext(domain)`, `executeNLQuery()`, `runQuickQuery(q)`, `loadRecommendations(refresh)`, `refreshRecommendations()`.

- [ ] **Step 1: Move the panel code**

Context panel, NL query (with the advisory re-routing hook from Task 4), quick queries, recommendations, alerts, portfolio health gauge (`#health-score`, `#health-bar`, three colour bands) and `#alert-badge`.

- [ ] **Step 2: Preserve the two context shapes**

`/ai-chat/context/<domain>` returns `data.elements` for `architecture` and `data.applications` for `technology`, and an empty state otherwise. Each row is a `data-action="select-context"` target that sets `#selected-element-id` and `contextElement` — the only click-path to element context.

- [ ] **Step 3: Keep the genome panel working**

`genomePanel()` is an Alpine component registered inline and reached via `window._genomePanelInstance`, called after every answer when `?mode=genome`. Move it to `panels.js` and keep the global.

- [ ] **Step 4: Verify and commit**

Journey plus: all four tabs, an NL query, a quick query, an advisory query re-routing to chat, `?mode=genome`.

```bash
git add app/static/js/ai_chat/panels.js app/templates/ai_chat/index.html
git commit -m "refactor(ai-chat): extract context, NL query, recommendations and genome panels"
```

---

## Task 6: Extract `app.js` and slim the template

**Files:**
- Create: `app/static/js/ai_chat/app.js`
- Modify: `app/templates/ai_chat/index.html`

- [ ] **Step 1: Move what remains**

Submit handler, `handleEnter`, domain/persona/model selector wiring, the 14-branch `data-action` delegation, entity modal, sidebar toggle, document-panel toggle, session history rail, export.

- [ ] **Step 2: Preserve the integration seams — spec §12.3**

These are invisible from the template and break silently:
- **5 window CustomEvents** — `add-document-analysis`, `show-notification`, `ask-question`, `link-to-entity`, `create-entity`, dispatched by `document_upload.js`. The only connection between the upload panel and the transcript.
- **`data-modal-open` / `data-modal-close` + `hidden` attribute**, served by `ui/modal.js:562-573`. The approvals modal opens through this, **not** Alpine. Do not convert it to `x-show`.
- **11 `window.*` globals**, including `loadSessionList`, which is called across a script boundary — lose it and a new chat will not appear in the rail until refresh.

- [ ] **Step 3: Remove the duplicate welcome grid**

The grid is server-rendered, then **overwritten** by `messagesContainer.innerHTML` on `DOMContentLoaded` with a second copy carrying different prompt strings, and the card wiring is registered twice. Keep the server-rendered one; delete the JS copy and the duplicate registration.

- [ ] **Step 4: Delete the dead 169 KB fork**

```bash
git rm app/static/js/ai_chat.js app/static/js/ai_chat/slash_commands.js
```

Confirm first that no template loads either (`grep -rn "ai_chat\.js\|slash_commands\.js" app/templates/`). Salvage `#stop-btn`'s AbortController (Task 2) and `exportConversation` before deleting — both live only here.

- [ ] **Step 5: Verify and commit**

Full journey, all four tabs, document upload → analysis posts into the chat, approvals modal opens, `?panel=docs`, all six deep links from spec §12.2.

```bash
git add app/static/js/ai_chat/app.js app/templates/ai_chat/index.html
git rm app/static/js/ai_chat.js app/static/js/ai_chat/slash_commands.js
git commit -m "refactor(ai-chat): slim the template to markup; delete the 169 KB dead fork

index.html goes from 3,591 lines to markup only. app/static/js/ai_chat.js was
a drifted duplicate no template has ever loaded; its stop-button
AbortController and exportConversation were salvaged first.

Also removes the second welcome grid, which overwrote the server-rendered one
on DOMContentLoaded with different prompt strings and duplicate wiring."
```

---

## Task 7: Restore `exportConversation` and the rate-limit badge

Both are listed as working features and neither has ever run — they were defined only in the file Task 6 deleted.

**Files:**
- Modify: `app/static/js/ai_chat/app.js`, `transport.js`

- [ ] **Step 1: Implement export**

Serialise `chatHistory` to Markdown and trigger a download via a Blob URL. Read the dead `ai_chat.js:2519` implementation first and port it rather than inventing a format.

- [ ] **Step 2: Populate the rate-limit badge honestly**

`#rate-limit-badge` is hidden until populated. Populate it only from a real response header or body field. **If the server does not return remaining quota, leave the badge hidden and delete it** — a fabricated count is exactly what the `fabricated-data` gate exists to stop. Check `rate_limit(30, "1h")` in `chat_core.py` for what is actually exposed.

- [ ] **Step 3: Verify and commit**

Export produces a file with the conversation in it. The badge either shows a real number or does not exist.

```bash
git add app/static/js/ai_chat/app.js app/static/js/ai_chat/transport.js
git commit -m "fix(ai-chat): export conversation actually works now

Both export and the rate-limit badge were defined only in the dead ai_chat.js,
so the Export button threw an Alpine expression error on every click while
being listed as a working feature."
```

---

## Task 8: Streaming accessibility

Highest-severity a11y defect: the transcript is one live region whose entire subtree is rewritten per token, so screen readers queue an announcement of the whole accumulated answer on every token.

**Files:**
- Modify: `app/templates/ai_chat/index.html`, `app/static/js/ai_chat/render.js`

- [ ] **Step 1: Replace the live region with a log plus a status region**

On `#messages-container`: remove `aria-live` and `aria-relevant`; add `role="log" aria-label="Conversation transcript"`.

Add a visually-hidden status region:

```html
<div id="chat-status" role="status" aria-live="polite" aria-atomic="true" class="sr-only"></div>
```

- [ ] **Step 2: Announce state, never content**

```javascript
function announce(text) {
    const el = document.getElementById('chat-status');
    if (el) el.textContent = text;
}
```

Call with `'Generating response…'` on send, `'Response stopped'` on abort, and on completion a summary — `'Response complete'` plus the source count when there is one. Never the answer text.

- [ ] **Step 3: Mark the streaming bubble busy and focusable**

`aria-busy="true"` while streaming, removed on completion; `tabindex="-1"` so focus can move there. The base layout already provides `Alpine.store('announcer')` (`admin_base.html:404-411`) — prefer it over a second mechanism if it fits.

- [ ] **Step 4: Verify and commit**

Run the axe audit; the `/ai-chat` baseline entry must shrink, never grow. Test with a screen reader if available; otherwise confirm the status region's text changes and the transcript is no longer a live region.

```bash
git add app/templates/ai_chat/index.html app/static/js/ai_chat/render.js tests/smoke/a11y_baseline.json
git commit -m "a11y(ai-chat): stop re-announcing the whole answer on every streamed token

The transcript was one aria-live region whose subtree was replaced per token,
so a 400-token answer queued 400 announcements of the whole accumulated text.
role=log for the transcript; a small status region carries state, not content."
```

---

## Task 9: Real tab semantics, focus management and reduced motion

**Files:**
- Modify: `app/templates/ai_chat/index.html`, `app/static/js/ai_chat/panels.js`, `app/static/css/shadcn_tokens.css`

- [ ] **Step 1: Give the tab set ARIA and keyboard behaviour**

Wrap in `role="tablist" aria-label="Chat context panels"`; each button gets `role="tab"`, `aria-selected`, `aria-controls`, and roving `tabindex` (0 on selected, -1 on the rest). Each panel gets `role="tabpanel"`, `aria-labelledby`, `tabindex="0"`. Add Left/Right/Home/End handling in `switchTab`, and set `aria-selected` there — today selection is conveyed by colour alone.

(The `aria-label` overrides were removed in Plan 1; the visible text is the name.)

- [ ] **Step 2: Route the remaining modals through `Platform.modal`**

Of five surfaces only the approvals modal is correct. Route the create-solution modal and the entity modal through `data-modal-open`/`Platform.modal.open`, which supplies focus trap, restore, Escape and LIFO. The document panel and mobile sidebar are non-modal disclosures above `lg`: give each an accessible name, a close button as first focusable child, Escape while open, and `previouslyFocused.focus()` on close.

- [ ] **Step 3: Add the missing names**

`#domain-selector`, `#model-selector`, `#template-selector` have no label — three `select-name` criticals. Also the "Docs" and "Match" buttons, whose only label is a `<span class="hidden lg:inline">`, so they are nameless below 1024px (axe runs at 1440×900 and will not catch it).

- [ ] **Step 4: Honour reduced motion**

There are zero `prefers-reduced-motion` rules in the project. Add to `shadcn_tokens.css` so the whole product benefits:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Make the streaming caret static under reduced motion rather than blinking for the whole response.

- [ ] **Step 5: Verify and commit**

Axe audit — the `/ai-chat` entry must shrink. Keyboard-only pass: reach every control, operate the tabs with arrows, open and close each modal with Escape, confirm focus returns.

```bash
git add app/templates/ai_chat/index.html app/static/js/ai_chat/panels.js app/static/css/shadcn_tokens.css tests/smoke/a11y_baseline.json
git commit -m "a11y(ai-chat): real tablist semantics, focus management, control names, reduced motion"
```

---

## Task 10: Scroll anchoring and the composer

**Files:**
- Modify: `app/static/js/ai_chat/render.js`, `app/static/js/ai_chat/app.js`, `app/templates/ai_chat/index.html`

- [ ] **Step 1: Anchor only when already at the bottom**

Replace the 8 unconditional `scrollTop = scrollHeight` calls:

```javascript
const NEAR_BOTTOM_PX = 100;

function isNearBottom(el) {
    return el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
}

function maybeScroll(el) {
    if (isNearBottom(el)) el.scrollTop = el.scrollHeight;
    else showJumpPill();
}
```

The pill must be a real `<button>` with an accessible name ("Jump to latest response"), and dismiss itself on click and when the user reaches the bottom.

- [ ] **Step 2: Autosize the composer**

`rows="3"` with `resize-none` and no `input` listener. Grow 1→12 rows on input, reset on send, and never steal focus.

- [ ] **Step 3: Add the keyboard shortcuts**

⌘K new chat; Esc stop (announce it via the status region, not only visually); ↑ edit last message **only when the composer is empty**, or it fights caret movement. Add a discoverable shortcut list.

- [ ] **Step 4: Verify and commit**

Scroll up mid-stream and confirm you are not dragged down and the pill appears. Type a long message and confirm growth. Exercise each shortcut.

```bash
git add app/static/js/ai_chat/render.js app/static/js/ai_chat/app.js app/templates/ai_chat/index.html
git commit -m "fix(ai-chat): stop yanking the reader to the bottom; grow the composer

scrollTop was set unconditionally in 8 places, once per streamed token, so
scrolling back to re-read dragged you down ~30x/second."
```

---

## Task 11: Fix the deep-link contract the parameter map exposed

`docs/known-issues/ai-chat-parameter-effects.md` §2: six places deep-link in with `?element_id=&context_type=`, but only the architecture and technology loaders read the filter. The vendor, capability and general loaders take it and ignore it — so "Ask AI about this vendor" hands the model the first 50 vendors with no indication which was asked about.

**Files:**
- Modify: `app/modules/ai_chat/services/multi_domain_chat_service.py`
- Test: `tests/test_ai_chat_context.py`

- [ ] **Step 1: Write the failing test**

Extend `tests/test_ai_chat_context.py` (it exists — read it and match its style) with a test asserting that `get_domain_context("vendor_intelligence", {"element_id": <id>, "context_type": "vendor"})` returns context naming that vendor.

- [ ] **Step 2: Run it and watch it fail**

Run: `pytest tests/test_ai_chat_context.py -v`
Expected: FAIL — the loader ignores the filter.

- [ ] **Step 3: Honour the filter in the three loaders**

In `_load_vendor_context`, `_load_capability_context` and `_load_general_context`, when `context_filter` carries an `element_id` matching the loader's `context_type`, load that record first and mark it as the focus. Follow how `_load_architecture_context` already does it — do not invent a second convention.

- [ ] **Step 4: Verify and commit**

```bash
git add app/modules/ai_chat/services/multi_domain_chat_service.py tests/test_ai_chat_context.py
git commit -m "fix(ai-chat): three context loaders ignored the element the user asked about

Six places deep-link into the chat with ?element_id, but only the architecture
and technology loaders read it. Ask AI about a vendor and the model received
the first 50 vendors with no indication which one was meant — from a link that
looked like it worked."
```

---

## Self-review

**Spec coverage.** §11 code structure ↔ Tasks 2–6. §12 contract ↔ Tasks 4, 5, 6 (each names the seams it must preserve). §9 accessibility ↔ Tasks 8, 9, 10. §10 control and failure ↔ Tasks 2, 3, 10. D2/D3/D4/D5/D7 ↔ Tasks 3, 10. D10/D15/D23/D24 ↔ Tasks 6, 7. Parameter map §2 ↔ Task 11.

**Type consistency.** `ArchieChat.transport.streamMessage(payload, handlers)` in Task 2 is the signature Task 3 and Task 6 call. `handlers.onToolStart` / `onToolResult` are defined in Task 2 as no-ops and consumed in Plan 3 — no rename between.

**Deferred to Plan 3:** the Assistant control (§5), evidence trail (§7), receipts (§8), opening screen (§16), and the backend seams they need — charter reconnection, `_TOOL_ENTITY` extension, the `mutates` flag.

**Not in either plan, and deliberately so.** The parameter map found that `template_name` has **no effect whatsoever** — validated, sanitised, then discarded. The Template selector and the per-page-load `AIPromptTemplate` query behind it are decoration. Removing them belongs with the Assistant control in Plan 3, not here, because it is a product decision about a visible control rather than a refactor.

**Ordering risk.** Task 1 must land first. If it cannot run in the executing environment for lack of PostgreSQL, the rebuild becomes unfalsifiable — stop and get a database rather than proceeding on static gates alone. This plan rewrites ~2,500 lines of JavaScript that no static gate inspects.
