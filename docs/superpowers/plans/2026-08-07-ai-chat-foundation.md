# /ai-chat Foundation & Standalone Fixes — Implementation Plan (Plan 1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put `/ai-chat` under CI coverage, make AI answers legible, and fix eleven verified defects — none of which depend on the client rebuild that follows in Plan 2.

**Architecture:** Every task here is independently shippable and independently revertable. Task 1 must land first because nothing below is verifiable without it. Task 2 is an investigation whose output gates Plan 2. Tasks 3–14 are ordered by value, not dependency, apart from Task 4 which depends on Task 3's config change.

**Tech Stack:** Flask · Jinja2 · Tailwind CSS v3 (standalone CLI, no Node) · Alpine.js · PostgreSQL · pytest · Playwright + axe-core

**Source spec:** `docs/superpowers/specs/2026-08-07-ai-chat-rebuild-design.md` (v2, commit `eb35608`)

## Global Constraints

- **Read `DESIGN.md` before editing any template, CSS, or front-end JS file.** It is the binding UI contract.
- **Never use raw Tailwind colours.** Semantic tokens only. Gate: `design_tokens`, baseline **90** in `verification_baseline.json`. (`CLAUDE.md` says 164 — it is stale; Task 14 fixes the doc.)
- **Never invent data.** No fabricated fallback in a `catch`; no literal metric that looks computed; `None` → `—`. Gate: `fabricated-data`, must stay 0.
- **No CDN assets.** Gate: `air_gap`, must stay 0.
- **`git add <file>` — never `git add -A`.** CI runs gitleaks over full history.
- **SQLAlchemy 2.0:** raw strings in `db.session.execute("…")` raise. Always `db.text(...)`.
- **New columns must be nullable or carry a server default.** `reconcile-schema` only adds nullable columns; a non-nullable one breaks every existing database.
- **Editing template classes requires a CSS rebuild:** `python scripts/build_css.py`. `--check` fails when the committed CSS is stale.
- **Verification command:** `python scripts/verify.py` (add `--gate <name>` for one gate, `--tag static` for the fast set).
- **Every `<button>` needs `type="button"` or `type="submit"`.** No `onclick=` attributes.

---

## Task 1: Put `/ai-chat` under CI coverage

Nothing else in this plan is verifiable until this lands. `/ai-chat` appears in **no** smoke test, no journey, no authorisation row, and has no a11y baseline entry — so no regression on this page can currently fail CI. Adding it *after* the fixes would bake the current violations into the accepted set.

**Files:**
- Modify: `tests/smoke/test_accessibility_audit.py:41-49` (the `AUDIT` list)
- Modify: `tests/smoke/a11y_baseline.json` (regenerated, not hand-edited)
- Modify: `tests/smoke/test_authorisation_matrix.py`

**Interfaces:**
- Consumes: the `seeded` fixture from `tests/smoke/conftest.py`, which creates one user per archetype; `enterprise_architect` is a valid archetype (`conftest.py:273-278`).
- Produces: a baseline entry keyed `"/ai-chat"` that later tasks must shrink and must never grow.

- [ ] **Step 1: Add the page to the a11y audit**

In `tests/smoke/test_accessibility_audit.py`, add to `AUDIT`:

```python
AUDIT = [
    ("procurement", "/procurement/contracts"),
    ("procurement", "/procurement/contracts/new"),
    ("procurement", "/procurement/compliance"),
    ("application_manager", "/my-applications/"),
    ("portfolio_manager", "/applications/"),
    ("business_architect", "/capability-map/"),
    ("cto", "/dashboard/overview"),
    ("enterprise_architect", "/ai-chat"),
]
```

- [ ] **Step 2: Run the audit and watch it fail**

Run: `pytest tests/smoke/test_accessibility_audit.py -v`
Expected: FAIL on `/ai-chat` with `critical`/`serious` violations not present in the baseline — at minimum `select-name` (three unlabelled selects at `index.html:171,227,238`).

This failure is the point: it proves the gate now sees the page.

- [ ] **Step 3: Record the current state as the baseline**

Run: `SMOKE_A11Y_UPDATE_BASELINE=1 pytest tests/smoke/test_accessibility_audit.py -v`

Then **read the diff** in `tests/smoke/a11y_baseline.json`. Every accepted rule under `"/ai-chat"` is a known defect this plan or Plan 2 must remove. If the diff contains a rule you cannot explain, stop and investigate — do not accept it.

- [ ] **Step 4: Add an authorisation row**

In `tests/smoke/test_authorisation_matrix.py`, follow the file's existing row format to assert `/ai-chat` is reachable by `enterprise_architect` and rejected for an unauthenticated request. Match the surrounding style exactly rather than inventing one.

- [ ] **Step 5: Verify green**

Run: `pytest tests/smoke/test_accessibility_audit.py tests/smoke/test_authorisation_matrix.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/smoke/test_accessibility_audit.py tests/smoke/a11y_baseline.json tests/smoke/test_authorisation_matrix.py
git commit -m "test(ai-chat): put the page under a11y and authorisation coverage

/ai-chat was in no smoke test, no journey and no a11y baseline, so no
regression on it could fail CI. The recorded baseline is a list of known
defects to remove, not an accepted state."
```

---

## Task 2: Parameter-effect map

Spec §3. The v1 design failed because it verified the client exhaustively and the server not at all. This task exists so Plan 2 cannot repeat that. Its deliverable is a committed document, not code.

**Files:**
- Create: `docs/known-issues/ai-chat-parameter-effects.md`

**Interfaces:**
- Produces: the table Plan 2's Assistant-control task depends on. **Plan 2 must not start before this is committed.**

- [ ] **Step 1: Trace each request parameter to its observable effect**

The live path is `POST /ai-chat/message` and `/message/stream` → `AgentRunner.run()`. Trace each of these from `chat_core.py` through to what reaches the model, and record what you find:

`message`, `domain`, `template_name`, `element_id`, `context_type`, `persona`, `model`, `thread_id`.

Known starting points, all verified — confirm each still holds and record the line:
- `persona` → `agent_runner.py:531`, one line: `persona_note = f"\nYou are operating as: {persona.replace('_',' ').title()}.\n"`. The governed charters in `architect_persona_charters.py` are reached only via `MultiDomainChatService._get_persona_system_prompt` (`:3277`), which is **not** on this path.
- `domain` → `get_domain_context(domain)`, which dispatches to nine loaders.
- `model` → `_resolve_requested_model` (`agent_runner.py:345`) silently falls back when a model is not configured, logging a warning the user never sees.

- [ ] **Step 2: Write the table**

One row per parameter: *parameter · where it is read · what it changes in the prompt or context · observable in the answer? (yes/no/partial) · file:line*.

State plainly which parameters currently have **no** observable effect. That list is the justification for Plan 2's control decisions.

- [ ] **Step 3: Commit**

```bash
git add docs/known-issues/ai-chat-parameter-effects.md
git commit -m "docs(ai-chat): map each request parameter to its observable effect

Written before the client rebuild because the previous design specified a
picker for a parameter that changes eight words of a prompt. Every control
the rebuild keeps must have a row here."
```

---

## Task 3: Make AI answers legible (the typography fix)

The single largest quality defect. The answer bubble is `class="prose"` while `@tailwindcss/typography` is disabled, so `prose` resolves to nothing — and Preflight, which *is* in the build, strips list markers and heading sizes. Every structured answer renders as one grey slab.

**Files:**
- Modify: `tailwind.config.js:87` (`plugins`) and `theme.extend` (add `typography`)
- Regenerate: `app/static/css/tailwind-output.css`, `app/static/manifest.json`

**Interfaces:**
- Produces: working `prose` classes. Task 4 depends on the `theme.extend` block existing.

- [ ] **Step 1: Confirm the current state fails**

Run: `grep -c "prose" app/static/css/tailwind-output.css`
Expected: `0`.

Run: `grep -o "menu,ol,ul{[^}]*}" app/static/css/tailwind-output.css`
Expected: `menu,ol,ul{list-style:none;margin:0;padding:0}` — the reset that makes this a defect.

- [ ] **Step 2: Enable the plugin and remap every variable to design tokens**

The standalone CLI bundles `@tailwindcss/typography`; no npm install is needed. In `tailwind.config.js`, add a `typography` key inside `theme.extend` (alongside `borderRadius`), and replace `plugins: []`.

All 18 variables get an `invert` twin — **36 entries**. Because every source token is already `.dark`-aware, both halves take *identical* values and dark mode resolves per theme.

```js
      typography: {
        DEFAULT: {
          css: {
            '--tw-prose-body': 'hsl(var(--foreground))',
            '--tw-prose-headings': 'hsl(var(--foreground))',
            '--tw-prose-lead': 'hsl(var(--muted-foreground))',
            '--tw-prose-links': 'hsl(var(--info))',
            '--tw-prose-bold': 'hsl(var(--foreground))',
            '--tw-prose-counters': 'hsl(var(--muted-foreground))',
            '--tw-prose-bullets': 'hsl(var(--muted-foreground))',
            '--tw-prose-hr': 'hsl(var(--border))',
            '--tw-prose-quotes': 'hsl(var(--muted-foreground))',
            '--tw-prose-quote-borders': 'hsl(var(--border))',
            '--tw-prose-captions': 'hsl(var(--muted-foreground))',
            '--tw-prose-code': 'hsl(var(--foreground))',
            '--tw-prose-pre-code': 'hsl(var(--foreground))',
            '--tw-prose-pre-bg': 'hsl(var(--muted))',
            '--tw-prose-th-borders': 'hsl(var(--border))',
            '--tw-prose-td-borders': 'hsl(var(--border))',
            '--tw-prose-kbd': 'hsl(var(--foreground))',
            '--tw-prose-kbd-shadows': '15 23 42',
            '--tw-prose-invert-body': 'hsl(var(--foreground))',
            '--tw-prose-invert-headings': 'hsl(var(--foreground))',
            '--tw-prose-invert-lead': 'hsl(var(--muted-foreground))',
            '--tw-prose-invert-links': 'hsl(var(--info))',
            '--tw-prose-invert-bold': 'hsl(var(--foreground))',
            '--tw-prose-invert-counters': 'hsl(var(--muted-foreground))',
            '--tw-prose-invert-bullets': 'hsl(var(--muted-foreground))',
            '--tw-prose-invert-hr': 'hsl(var(--border))',
            '--tw-prose-invert-quotes': 'hsl(var(--muted-foreground))',
            '--tw-prose-invert-quote-borders': 'hsl(var(--border))',
            '--tw-prose-invert-captions': 'hsl(var(--muted-foreground))',
            '--tw-prose-invert-code': 'hsl(var(--foreground))',
            '--tw-prose-invert-pre-code': 'hsl(var(--foreground))',
            '--tw-prose-invert-pre-bg': 'hsl(var(--muted))',
            '--tw-prose-invert-th-borders': 'hsl(var(--border))',
            '--tw-prose-invert-td-borders': 'hsl(var(--border))',
            '--tw-prose-invert-kbd': 'hsl(var(--foreground))',
            '--tw-prose-invert-kbd-shadows': '226 232 240',
          },
        },
      },
```

and:

```js
  plugins: [require('@tailwindcss/typography')],
```

**Three traps, each already cost someone a bug:**
1. `--tw-prose-links` maps to `--info`, **not** `--primary`. `--primary` is near-white in dark mode (`210 40% 98%`), which would make links indistinguishable from body text. `DESIGN.md:93-96` warns about exactly this.
2. `--tw-prose-kbd-shadows` takes an **R G B triplet**, not HSL — the plugin injects it into `rgb(var(--…) / …)`. Hence the bare numbers.
3. `pre-bg` and `pre-code` must be set **together**, or code blocks render white-on-white in light mode.

- [ ] **Step 3: Rebuild the CSS and confirm the plugin took effect**

Run: `python scripts/build_css.py`
Expected: output grows from ~152,867 B to ~172,313 B (+12.7%).

Run: `grep -c "prose" app/static/css/tailwind-output.css`
Expected: a number in the hundreds, not 0.

Run: `grep -o "list-style-type:disc" app/static/css/tailwind-output.css | head -1`
Expected: `list-style-type:disc` — proof that list markers are restored inside `prose`.

- [ ] **Step 4: Verify the gates**

Run: `python scripts/verify.py --gate css-build`
Expected: PASS (committed CSS matches a fresh build).

Run: `python scripts/verify.py --gate design-tokens`
Expected: no worse than baseline 90. The gate scans `app/templates/**/*.html` only and never reads `tailwind.config.js`, so this change cannot move it.

Run: `python scripts/verify.py --gate air-gap`
Expected: 0. The plugin is bundled in the local CLI; nothing is fetched.

- [ ] **Step 5: Commit**

```bash
git add tailwind.config.js app/static/css/tailwind-output.css app/static/manifest.json
git commit -m "fix(ai-chat): AI answers were rendering with no typography at all

The answer bubble carries class=\"prose\", but the typography plugin was
never enabled, so \`prose\` matched nothing in the built CSS — while
Preflight, which is in the build, resets list-style to none and heading
font-size to inherit. Structured markdown arrived correctly and was
flattened into one grey slab.

Every prose variable is mapped to a design token rather than the plugin's
stock greys, so dark mode resolves per theme with no second ruleset.
Links map to --info, not --primary: --primary is near-white in dark mode
and would render links indistinguishable from body text."
```

---

## Task 4: Fix the two warning banners that are invisible in dark mode

`--warning-foreground` is `0 0% 0%` — pure black — in **both** themes. On `bg-warning/10`, which composites to near-black in dark mode, that is **1.19:1**. The degraded-mode banner and the LLM-health banner — the two elements whose only job is to tell you the AI is broken — cannot be read by a dark-theme user.

There is no `--warning-emphasis`; only `destructive` and `info` have emphasis variants.

**Files:**
- Modify: `app/static/css/shadcn_tokens.css` (both `:root` and `.dark` blocks)
- Modify: `tailwind.config.js` (the `warning` colour entry)
- Modify: `app/templates/ai_chat/index.html:117`, `:143`
- Regenerate: `app/static/css/tailwind-output.css`

- [ ] **Step 1: Add the token in both themes**

In `app/static/css/shadcn_tokens.css`, in the `:root` block next to `--warning-foreground` (around line 27):

```css
    --warning-emphasis: 32 95% 30%;
```

and in the `.dark` block (around line 67):

```css
    --warning-emphasis: 45 93% 65%;
```

Light is darkened for contrast against a pale tint; dark is lightened for contrast against a dark tint. This mirrors how `--destructive-emphasis` and `--info-emphasis` already work.

- [ ] **Step 2: Expose it to Tailwind**

In `tailwind.config.js`, extend the existing `warning` entry:

```js
        warning: {
          DEFAULT: "hsl(var(--warning) / <alpha-value>)",
          foreground: "hsl(var(--warning-foreground) / <alpha-value>)",
          emphasis: "hsl(var(--warning-emphasis) / <alpha-value>)",
        },
```

- [ ] **Step 3: Use it on both banners**

In `app/templates/ai_chat/index.html`, change `text-warning-foreground` to `text-warning-emphasis` on line 117 and line 143. Leave every other class on those elements alone.

- [ ] **Step 4: Rebuild and verify contrast**

Run: `python scripts/build_css.py`

Verify the ratios with this throwaway script (delete it afterwards — do not commit it):

```python
def rel_lum(r, g, b):
    def c(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)

def ratio(fg, bg):
    l1, l2 = sorted([rel_lum(*fg), rel_lum(*bg)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)

# dark theme: --warning-emphasis 45 93% 65% over bg-warning/10 on --background
print(round(ratio((250, 214, 90), (23, 27, 38)), 2))
```

Expected: comfortably above 4.5. If it is not, adjust the lightness in Step 1 and repeat — do not lower the target.

- [ ] **Step 5: Check both themes by eye**

Load `/ai-chat` with the AI provider unreachable so the health banner shows, in light and dark. Confirm the text is readable in both. A contrast number that passes on paper but reads badly is still a failure.

- [ ] **Step 6: Commit**

```bash
git add app/static/css/shadcn_tokens.css tailwind.config.js app/templates/ai_chat/index.html app/static/css/tailwind-output.css app/static/manifest.json
git commit -m "fix(a11y): the two AI warning banners were invisible in dark mode

--warning-foreground is pure black in both themes. On bg-warning/10 in
dark mode that composites to 1.19:1 — so the degraded-mode banner and the
LLM-health banner, whose whole purpose is to say the assistant is not
working, could not be read by a dark-theme user.

Adds --warning-emphasis, following the existing destructive/info pattern."
```

---

## Task 5: Fix the feedback write path — it lies about succeeding

**This is the blocker gating the thumbs in Plan 3.** The endpoint is worse than untenanted:

```python
# chat_core.py:673-678
        db.session.commit()
    except Exception:
        current_app.logger.info("ai_chat_feedback table not ready; feedback not persisted")
    return jsonify({"success": True, "rating": rating})
```

`organization_id` is declared **nowhere** — not on the model, not in `manage.py`, and not reachable by `reconcile-schema`, which diffs *models* against tables and the model has no such column. So the org-scoped INSERT at `:647` raises `UndefinedColumn`, the bare `except` swallows it, and the endpoint returns `success: True` for a write that did not happen. There is no `rollback()`, so the aborted transaction cascades `InFailedSqlTransaction` into every later query on that request.

Separately, the model has no `TenantMixin`, so it sits outside ORM tenant isolation while `message_text` stores AI answers — portfolio content — and the admin aggregation (`chat_admin_routes.py:260-265`) filters on `created_at` only.

**Files:**
- Modify: `app/models/ai_chat_feedback.py`
- Modify: `app/modules/ai_chat/routes/chat_core.py:639-678`
- Modify: `app/modules/ai_chat/routes/chat_admin_routes.py:260-269`
- Test: `tests/test_ai_chat_feedback_tenancy.py`

**Interfaces:**
- Produces: `POST /ai-chat/feedback` returning `{"success": true}` **only** when a row was written, and `{"error": ...}` with a non-2xx status otherwise. Plan 3's thumbs depend on this contract.

- [ ] **Step 1: Write the failing tenancy test**

Create `tests/test_ai_chat_feedback_tenancy.py`. Use the shared fixtures in `tests/conftest.py` (`db_session`, `make_org`, `tenant_ctx`) — follow `tests/test_tenant_isolation.py`, the reference adopter. Do **not** copy the hand-rolled module-scoped pattern in older test files.

```python
"""Feedback rows must not be readable across organisations.

message_text stores the assistant's answer, which is portfolio content.
"""
from app.extensions import db
from app.models.ai_chat_feedback import AIChatFeedback


def test_feedback_is_scoped_to_its_organisation(db_session, make_org, tenant_ctx):
    org_a = make_org("Org A")
    org_b = make_org("Org B")

    with tenant_ctx(org_a):
        db.session.add(AIChatFeedback(
            user_id=1, rating="up", domain="architecture",
            persona="enterprise_architect",
            message_text="Org A portfolio detail that org B must never see",
        ))
        db.session.commit()

    # Session caching would otherwise return org A's row from the identity map
    # without emitting SQL, so no tenant filter would run (CLAUDE.md).
    db.session.remove()

    with tenant_ctx(org_b):
        assert AIChatFeedback.query.all() == []

    db.session.remove()

    with tenant_ctx(org_a):
        assert len(AIChatFeedback.query.all()) == 1
```

- [ ] **Step 2: Run it and watch it fail**

Run: `pytest tests/test_ai_chat_feedback_tenancy.py -v`
Expected: FAIL — the model has no `organization_id`, so either the insert errors or org B sees org A's row.

- [ ] **Step 3: Put the model inside tenant isolation**

Rewrite `app/models/ai_chat_feedback.py`:

```python
"""AI chat message feedback model."""
import datetime

from app.extensions import db
from app.models.mixins.core import TenantMixin


class AIChatFeedback(TenantMixin, db.Model):
    __tablename__ = "ai_chat_feedback"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.String(10), nullable=False)   # 'up' or 'down'
    domain = db.Column(db.String(50))
    persona = db.Column(db.String(50))
    message_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
```

`TenantMixin` supplies `organization_id` as a declared attribute and the ORM event listeners then filter SELECTs and auto-set the column on insert.

**Note the nullability tension and check it explicitly:** `TenantMixin.organization_id` is `nullable=False` (`app/models/mixins/core.py:69`), but `reconcile-schema` only ever emits nullable `ADD COLUMN`. On an existing database the column arrives nullable while the ORM declares NOT NULL. Run the drift gate in Step 6 and record what it reports; if it flags the mismatch, resolve it there rather than papering over it.

- [ ] **Step 4: Replace the raw SQL and the silent failure**

In `chat_core.py`, replace the whole `try` block at `:639-678` with an ORM insert that reports its own failure:

```python
    try:
        from app.models.ai_chat_feedback import AIChatFeedback

        # organization_id is set by the tenant before_flush; do not pass it.
        db.session.add(AIChatFeedback(
            user_id=current_user.id,
            rating=rating,
            domain=domain,
            persona=persona,
            message_text=message_text,
        ))
        db.session.commit()
    except Exception:
        # Returning success for a write that did not happen told the user their
        # feedback was recorded when it was discarded, and left the transaction
        # aborted so every later query on the request failed too.
        db.session.rollback()
        current_app.logger.exception("ai_chat_feedback insert failed")
        return jsonify({"error": "Feedback could not be saved"}), 500

    return jsonify({"success": True, "rating": rating})
```

Remove the now-unused `from sqlalchemy import text` import if nothing else in the function uses it.

- [ ] **Step 5: Scope the admin aggregation**

In `chat_admin_routes.py`, add the organisation predicate to the query at `:260-265`. `AIChatFeedback` now carries `TenantMixin`, so an ORM query inside a request context is filtered automatically — **verify that is actually true here** rather than assuming it, because this dashboard may run for a platform admin whose org context differs from the rows being counted. If the intent is genuinely cross-org platform analytics, that is a product decision: leave the query unfiltered but add an explicit comment saying so, and confirm the route is admin-only.

- [ ] **Step 6: Run the tests and the drift gate**

Run: `pytest tests/test_ai_chat_feedback_tenancy.py -v`
Expected: PASS.

Run: `python scripts/verify.py --gate schema-drift`
Expected: PASS. If it reports the nullability mismatch from Step 3, fix it now.

Run: `python scripts/verify.py --gate raw-sql-tenancy`
Expected: no worse than baseline 98 — this task removes two raw INSERTs, so it should improve.

- [ ] **Step 7: Commit**

```bash
git add app/models/ai_chat_feedback.py app/modules/ai_chat/routes/chat_core.py app/modules/ai_chat/routes/chat_admin_routes.py tests/test_ai_chat_feedback_tenancy.py
git commit -m "fix(ai-chat): feedback returned success for a write that never happened

organization_id was declared on no model, in no migration, and was
unreachable by reconcile-schema, so the org-scoped INSERT raised
UndefinedColumn every time. A bare except swallowed it, logged at INFO and
returned success: true — and without a rollback the aborted transaction
cascaded into every later query on the request.

The model now carries TenantMixin, so it sits inside tenant isolation
rather than outside it: message_text holds the assistant's answer, which
is portfolio content, and the admin dashboard aggregated it across
organisations."
```

---

## Task 6: Remove the vision UI

**Decided by the product owner on 2026-08-07** (spec §17). `AgentRunner` has no vision handling — zero occurrences of `image_data`/`vision` — so an attached diagram is silently discarded and the user gets a confident answer generated as if no image existed. Implementing vision is real backend scope with a model-routing decision attached and does not belong here. The control goes.

**Files:**
- Modify: `app/templates/ai_chat/index.html` — remove `:756-764`, `:766`, `:787-794`, the FileReader wiring at `:3307-3340`, and the payload fields at `:2412-2413`
- Modify: `app/modules/ai_chat/routes/chat_core.py:474-477` (comment only)

- [ ] **Step 1: Remove the UI**

Delete from `app/templates/ai_chat/index.html`:
- `#image-preview-bar` with `#image-preview-thumb`, `#image-preview-name`, `#image-remove-btn` (`:756-764`)
- `#image-upload-input` (`:766`)
- `#image-attach-btn` (`:787-794`)
- the FileReader/attach wiring (`:3307-3340`) and the `attachedImage` variable it maintains
- `image_data` and `image_media_type` from the `_payload` object (`:2412-2413`), and the `imageForRequest` handling at `:2394-2399`

Grep for `attachedImage` and `image` afterwards to confirm nothing dangles.

- [ ] **Step 2: Leave a marker on the server**

In `chat_core.py`, above `:474`, add:

```python
        # The chat client no longer sends these: AgentRunner has no vision
        # handling, so the base64 was accepted, stored in context_data and
        # discarded, and the user received a confident answer generated as if
        # no diagram had been attached. Kept as the reattachment point if
        # vision is implemented; harmless while nothing sends it.
```

- [ ] **Step 3: Rebuild CSS and verify**

Run: `python scripts/build_css.py`
Run: `python scripts/verify.py --tag static`
Expected: PASS. `template-syntax` must be 0.

- [ ] **Step 4: Load the page and confirm nothing broke**

Load `/ai-chat`, send a message, confirm it still works and the attach button is gone. Check the browser console for errors from removed references.

- [ ] **Step 5: Commit**

```bash
git add app/templates/ai_chat/index.html app/modules/ai_chat/routes/chat_core.py app/static/css/tailwind-output.css app/static/manifest.json
git commit -m "fix(ai-chat): remove the diagram-attach UI, which discarded what it accepted

DELIBERATE CAPABILITY REMOVAL — do not restore from the template alone.

The button, thumbnail and payload fields existed; AgentRunner has no vision
handling, so the base64 went into context_data and was dropped. The user saw
a thumbnail and received a confident answer generated as if no image had been
attached — the most dangerous defect on the page, because the failure was
invisible.

Implementing vision is separate backend scope with a model-routing decision
attached. Until then, not offering the control is the honest option."
```

---

## Task 7: Fix "Open in Composer", which opens an empty canvas

The chat writes `sessionStorage['archimate_prefill']` (`index.html:1709`); the composer reads `composer_prefill` (`archimate/composer.js:2407,2495`). Nothing reads the key the chat writes, so the button has never worked.

**Files:**
- Modify: `app/templates/ai_chat/index.html:1709`

- [ ] **Step 1: Confirm the mismatch**

Run: `grep -rn "archimate_prefill\|composer_prefill" app/static/js/ app/templates/`
Expected: `archimate_prefill` written only at `index.html:1709` with no reader; `composer_prefill` read at `composer.js:2407,2495` and written only by the dead `ai_chat.js`.

- [ ] **Step 2: Read what the composer expects**

Read `app/static/js/archimate/composer.js:2400-2420` and `:2490-2500` and confirm the **shape** it parses, not just the key. If the shape differs from the `prefillData` object built at `index.html:1703-1708`, match the composer's shape — it is the consumer and it works.

- [ ] **Step 3: Write the key the composer reads**

At `index.html:1709`, change the key to `composer_prefill`, adjusting the payload shape to whatever Step 2 established.

- [ ] **Step 4: Verify end to end**

Ask the chat to generate ArchiMate elements, click "Open in Composer", and confirm the canvas opens **populated**. This cannot be verified by grep — the shape must actually parse.

- [ ] **Step 5: Commit**

```bash
git add app/templates/ai_chat/index.html
git commit -m "fix(ai-chat): Open in Composer handed off under a key nobody reads

The chat wrote sessionStorage['archimate_prefill']; the composer reads
'composer_prefill'. The button opened an empty canvas, silently, for as long
as it has existed."
```

---

## Task 8: Fix the entity modal, which takes two clicks to close

A static `#entity-action-modal` (`:825`) and a dynamically built one (`:2877`) share an id. Every close path calls `getElementById('entity-action-modal').remove()`, which returns the **first in document order** — the invisible static decoy. The first click removes the decoy and leaves the real overlay covering the viewport, with no Escape and no focus trap. It is also a `duplicate-id-aria` critical violation whenever both are in the DOM.

**Files:**
- Modify: `app/templates/ai_chat/index.html` — delete `:825-860`

- [ ] **Step 1: Confirm the static block is genuinely unused**

Run: `grep -n "entity-action-view\|entity-action-ask\|entity-action-context\|entity-action-title\|entity-action-subtitle" app/templates/ai_chat/index.html`

Expected: the ids appear in the static block (`:825-860`) and are rebuilt inside `showEntityInChat` (`:2873+`). Confirm no JS binds to the static instances at page load — if any does, that binding must move before deletion.

- [ ] **Step 2: Delete the static block**

Remove `index.html:825-860` — the whole `<div id="entity-action-modal">` including its six child ids.

- [ ] **Step 3: Verify the modal now closes on the first click**

Load `/ai-chat`, trigger an entity modal (click an entity reference in an answer), and confirm **one** click on Close dismisses it and returns the page to normal. Repeat for "View Details", "Ask AI" and "Add to Context".

- [ ] **Step 4: Confirm the a11y baseline improved**

Run: `pytest tests/smoke/test_accessibility_audit.py -v`
Expected: PASS, and `duplicate-id-aria` should no longer appear for `/ai-chat` if it was recorded in Task 1. If the baseline still lists it, regenerate and commit the shrunk baseline.

- [ ] **Step 5: Commit**

```bash
git add app/templates/ai_chat/index.html tests/smoke/a11y_baseline.json
git commit -m "fix(ai-chat): the entity modal needed two clicks to close

A static #entity-action-modal and a dynamically built one shared an id, so
every close path's getElementById().remove() hit the invisible static decoy
first, leaving the real overlay covering the viewport with no Escape and no
focus trap. Also a duplicate-id-aria critical violation."
```

---

## Task 9: Fix the mobile sidebar backdrop, which never appears

`index.html:573` authors the backdrop with the native `hidden` **attribute**; `toggleSidebar()` toggles the `hidden` **class** (`:2590`, `:2595`), which the element never had and which cannot clear the attribute. Meanwhile `:2596` does lock body scroll. On mobile the page freezes behind an undimmed, still-tabbable overlay.

**Files:**
- Modify: `app/templates/ai_chat/index.html:573`, `:2582-2601`

- [ ] **Step 1: Reproduce**

Load `/ai-chat` at a viewport below 1024px, open the sidebar, and confirm: no dimming, content behind still reachable by Tab, page scroll locked.

- [ ] **Step 2: Make the attribute and the toggle agree**

At `:573`, remove the `hidden` attribute and add the `hidden` class instead, so the JS toggle addresses the same thing it sets:

```html
<div id="sidebar-backdrop" @click="toggleSidebar()" class="hidden modal-root lg:hidden fixed inset-0 bg-black/50 overflow-y-auto z-30"></div>
```

Also remove the bare `role="dialog"`: an element with that role and no accessible name is an `aria-dialog-name` **serious** axe violation the moment it becomes visible. The backdrop is decorative — the sidebar it reveals is the thing with meaning.

- [ ] **Step 3: Verify both states**

Below 1024px: open the sidebar → backdrop dims the page, clicking it closes the sidebar, scroll stays locked while open and is released on close. Above 1024px: the backdrop never appears (`lg:hidden`).

- [ ] **Step 4: Run the a11y audit**

Run: `pytest tests/smoke/test_accessibility_audit.py -v`
Expected: PASS with no new violations. The audit runs at 1440×900, so it will not exercise the mobile path — Step 3's manual check is the real verification here, and that gap is worth noting in Plan 2.

- [ ] **Step 5: Commit**

```bash
git add app/templates/ai_chat/index.html
git commit -m "fix(ai-chat): the mobile sidebar backdrop never appeared

Authored with the hidden attribute; toggled as the hidden class. The two
never met, so on mobile the page scroll-locked behind an undimmed, fully
tabbable overlay. Also drops a bare role=dialog that had no accessible name."
```

---

## Task 10: Fix the two quick-query buttons that post slash commands to the wrong endpoint

`[data-quick-query]` clicks route through the delegated handler (`:2769-2773`) → `runQuickQuery()` (`:2755`) → `executeNLQuery()` → `POST /ai-chat/nl-query`. They never reach `handleChatCommand`, which is called only from the chat-form submit (`:2360`).

So **"Create capability"** (`:476`, `/create-capability` — not a registered command) and **"Map APQC framework"** (`:477`, `/map-apqc` — a registered command, so it looks correct) both post a literal slash string to the natural-language query endpoint.

**Files:**
- Modify: `app/templates/ai_chat/index.html:2755-2760` (`runQuickQuery`)
- Modify: `app/templates/ai_chat/index.html:476`

- [ ] **Step 1: Confirm the routing**

Read `index.html:2769-2773` and `:2755-2761`. Confirm `runQuickQuery` writes into `#nl-query-input` and calls `executeNLQuery()` with no branch for a leading `/`.

- [ ] **Step 2: Route slash strings to the command handler**

In `runQuickQuery`, dispatch on the leading `/` so a command reaches the code that implements commands:

```javascript
    function runQuickQuery(query) {
        // A quick-query button carrying a slash command used to be posted to
        // /ai-chat/nl-query as literal text, because every [data-quick-query]
        // click funnels through here rather than the chat submit handler.
        if (query.startsWith('/')) {
            userInput.value = query;
            chatForm.requestSubmit();
            return;
        }
        switchSidebarTab('query');
        document.getElementById('nl-query-input').value = query;
        setTimeout(() => executeNLQuery(), 150);
    }
```

Keep the existing body below the new branch — reproduce it exactly as it stands rather than rewriting it.

- [ ] **Step 3: Fix the button that names a command that does not exist**

`/create-capability` is absent from the handler map (`:1758-1769`), so routing it correctly still fails. Change `:476` to plain language, which the assistant handles today:

```html
<button type="button" class="quick-query-btn inline-flex items-center gap-1 rounded-md border border-input bg-background px-3 py-1 text-xs hover:bg-accent" data-quick-query="Create a new business capability" aria-label="Quick query: Create capability">Create capability</button>
```

- [ ] **Step 4: Verify both buttons**

Click **"Map APQC framework"** → the `/map-apqc` command runs and renders its action card (not a flat entity list).
Click **"Create capability"** → a normal grounded chat answer, no literal slash string echoed.

- [ ] **Step 5: Commit**

```bash
git add app/templates/ai_chat/index.html
git commit -m "fix(ai-chat): two quick-query buttons posted slash commands as literal text

Every [data-quick-query] click funnels through runQuickQuery into
/ai-chat/nl-query, never into handleChatCommand. 'Map APQC framework' sent
/map-apqc — a real command — to the NL-query endpoint as a string, so it
looked correct and silently did the wrong thing. 'Create capability' named a
command that does not exist at all."
```

---

## Task 11: Fix the sidebar tab that never hides

`switchSidebarTab` iterates `['context','query','alerts']` (`:2608`) and omits `'history'`, so selecting another tab never hides the Chats panel.

**Files:**
- Modify: `app/templates/ai_chat/index.html:2608`

- [ ] **Step 1: Reproduce**

Load `/ai-chat`, click **Chats**, then click **Context**. The conversation list stays visible underneath.

- [ ] **Step 2: Include the fourth panel**

At `:2608`:

```javascript
        const panels = ['context', 'query', 'alerts', 'history'];
```

Read the surrounding function first: the `[id^="tab-"]` styling reset at `:2620-2637` may also need `history` included for the tab's active state to clear. Fix both if so.

- [ ] **Step 3: Verify all four**

Click through Context → Query → Alerts → Chats → Context. Exactly one panel visible at every step, and the active tab styling follows.

- [ ] **Step 4: Commit**

```bash
git add app/templates/ai_chat/index.html
git commit -m "fix(ai-chat): selecting a tab never hid the Chats panel

switchSidebarTab's panel list omitted 'history', so the conversation list
stayed visible under whichever tab was chosen next."
```

---

## Task 12: Add SRI to `marked.min.js`

`index.html:5` is the only vendor script on the page loaded without `integrity=`, while `_head.html` gates DOMPurify with SRI. It is also the only template that loads it.

**Files:**
- Modify: `app/templates/ai_chat/index.html:5`
- Possibly modify: `VENDOR_MANIFEST.txt`

- [ ] **Step 1: Compute the hash**

```bash
python -c "import base64,hashlib;print('sha384-'+base64.b64encode(hashlib.sha384(open('app/static/vendor/marked.min.js','rb').read()).digest()).decode())"
```

- [ ] **Step 2: Match the existing pattern**

Read how `_head.html` declares DOMPurify's `integrity` and `crossorigin` and copy that form exactly, substituting the hash from Step 1. Do not invent a different attribute set.

- [ ] **Step 3: Check the vendor manifest**

Run: `grep -n "marked" VENDOR_MANIFEST.txt`
If `marked.min.js` is absent, add it following the file's existing format — `vendor-integrity` compares vendored assets against this manifest.

- [ ] **Step 4: Verify**

Run: `python scripts/verify.py --gate sri --gate vendor-integrity`
Expected: PASS, `sri` at 0.

Load `/ai-chat` and confirm markdown still renders — a wrong hash makes the browser refuse the script silently, and the symptom is unrendered markdown, not a visible error.

- [ ] **Step 5: Commit**

```bash
git add app/templates/ai_chat/index.html VENDOR_MANIFEST.txt
git commit -m "fix(ai-chat): marked.min.js was the one vendor script with no SRI

Every other vendored asset on this page is integrity-gated, including
DOMPurify in _head.html. marked parses model output into HTML, so it is a
poor place to make the exception."
```

---

## Task 13: Delete `context_data` — four queries per page load, referenced zero times

`chat_views.py:180-218` runs four queries of up to `AI_CHAT_CONTEXT_LIMIT` (default 50) rows each on **every** page load and passes them to a template that references `context_data` **zero** times.

**Files:**
- Modify: `app/modules/ai_chat/routes/chat_views.py:177-220`

- [ ] **Step 1: Confirm it is unused**

Run: `grep -c "context_data" app/templates/ai_chat/index.html`
Expected: `0`.

Run: `grep -rn "context_data" app/templates/`
Expected: no hits in any template that `index.html` includes or imports. Check `ai_chat/document_upload.html` specifically, since it is imported as a macro at `:820`.

- [ ] **Step 2: Remove the queries and the template argument**

In `chat_views.py`, delete the `context_limit` line, the `context_data` dict, all four `try/except` query blocks (`:187-211`), and the `context_data=context_data` argument to `render_template`. Remove any imports left unused — `ApplicationComponent`, `BusinessCapability`, `VendorOrganization`, `UnifiedCapability` — but only if nothing else in the module uses them.

- [ ] **Step 3: Verify the page still renders**

Run: `python scripts/verify.py --gate boot-health --gate template-syntax --gate undefined-names`
Expected: PASS. `undefined-names` (ruff F821) catches an import removed while still referenced.

Load `/ai-chat` and confirm it renders normally.

- [ ] **Step 4: Commit**

```bash
git add app/modules/ai_chat/routes/chat_views.py
git commit -m "perf(ai-chat): drop four per-page-load queries whose results were never used

chat_views built context_data from four queries of up to 50 rows each and
passed it to a template that references it zero times."
```

---

## Task 14: Take the file's `design_tokens` contribution to zero, and correct `CLAUDE.md`

The v1 spec claimed removing `bg-emerald-50`/`purple-50`/`orange-50`/`cyan-50` would lower the ratchet. It would not: the gate counts only `gray|grey|slate|zinc|neutral|stone|blue|red` (`check_design_tokens.py:36`). This file's real contribution is **2**, and five more are suppressed by `token-migration-ok` markers.

**Files:**
- Modify: `app/templates/ai_chat/index.html:1152`, `:1158`, `:1164`, `:3235`
- Modify: `verification_baseline.json`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Measure the starting point**

Run: `python scripts/check_design_tokens.py app/templates/ai_chat/index.html`
Expected: **2** violations, both `slate` on line 1158.

- [ ] **Step 2: Convert the two counted violations**

At `:1158`, replace `from-slate-500 to-slate-600` with `from-muted-foreground to-muted-foreground`. Read the surrounding `getColorClass` function first — this is a gradient map keyed by domain colour, so the replacement must keep the same shape for every branch.

- [ ] **Step 3: Convert the five suppressed ones and delete their markers**

- `:1152` — `from-blue-500 to-blue-600` → `from-info to-info`
- `:1164` — `from-red-500 to-red-600` → `from-destructive to-destructive`
- `:3235` — `text-red-800` → `text-destructive-emphasis` (per `DESIGN.md:80-91`, since it sits on `bg-destructive/10`)

Then delete the `token-migration-ok` comments on those lines. **Do not delete a marker without converting the colour first** — the marker is the only thing keeping those five out of the count.

While here: `:3237` uses `text-yellow-800` on `bg-amber-500/10`, which fails in dark mode (2.60). Convert it to `text-warning-emphasis`, the token Task 4 introduces.

- [ ] **Step 4: Re-measure and re-baseline**

Run: `python scripts/check_design_tokens.py app/templates/ai_chat/index.html`
Expected: **0**.

Run: `python scripts/verify.py --gate design-tokens`
Expected: repo total 90 → **83**.

Run: `python scripts/verify.py --update-baseline`
Confirm `verification_baseline.json` records the *lower* number. A ratchet that rises is a regression that must be justified in review.

- [ ] **Step 5: Correct the stale figure in `CLAUDE.md`**

`CLAUDE.md` states **164** raw-colour uses; the baseline says 90 (83 after this task). Update the number and the sentence around it so the next person sizing this work is not reading a figure that is 82% too high.

- [ ] **Step 6: Rebuild CSS and verify**

Run: `python scripts/build_css.py`
Run: `python scripts/verify.py`
Expected: fully green; `design_tokens` at 83.

- [ ] **Step 7: Commit**

```bash
git add app/templates/ai_chat/index.html verification_baseline.json CLAUDE.md app/static/css/tailwind-output.css app/static/manifest.json
git commit -m "style(ai-chat): take the file's raw-colour count to zero, and fix a stale doc

The gate counts gray/slate/zinc/neutral/stone/blue/red only, so the
emerald/purple/orange/cyan tiles an earlier draft proposed removing were
never counted. The real contribution was two slate gradients plus five more
hidden behind token-migration-ok markers. Converted and the markers deleted;
repo baseline 90 -> 83.

CLAUDE.md said 164, which is stale by 82%."
```

---

## Self-review

**Spec coverage.** Task 1 ↔ §14 (CI first). Task 2 ↔ §3. Task 3 ↔ §6 and §1.1. Task 4 ↔ §9 contrast and D18. Task 5 ↔ §17 blocker B4. Task 6 ↔ §17 blocker D13. Tasks 7–11 ↔ D14, D16, D17, D12, D21. Task 12 ↔ D19. Task 13 ↔ D20. Task 14 ↔ §14 design_tokens.

**Deliberately deferred to Plan 2** (client rebuild): D1/D10 dead JS, D2 message actions, D3 scroll, D4 streaming flash, D5 composer, D7 error cards, D8 entry points, D22 `window.currentDomain`, D23 duplicate welcome grid, D24/D25 dead command code, and the whole of §9 beyond contrast — tabs, live region, focus management, reduced motion, skip links. Each needs the module extraction to land first.

**Deliberately deferred to Plan 3** (differentiators): §5 Assistant control, §7 evidence trail, §8 receipts, §16 opening screen, and the two backend seams they need (`_TOOL_ENTITY` extension, charter reconnection, `mutates` flag).

**Ordering note.** Task 4 depends on Task 3 (the `theme.extend` block). Task 14 depends on Task 4 (`--warning-emphasis`). Everything else is independent and may be reordered or dropped without breaking its neighbours.

**Known gap, stated rather than hidden.** Tasks 7, 8, 9 and 11 are verified by manual browser checks, not automated tests. The page has no Playwright journey, and writing one per bug fix would cost more than the fixes. Plan 2 adds a journey covering send / stream / stop / history / modal-close, which is where these become regression-proof. Until then they can silently break again.
