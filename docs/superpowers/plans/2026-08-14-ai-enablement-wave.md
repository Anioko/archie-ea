# AI Enablement Wave — every archetype gets task-embedded AI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the AI-assist gaps found in the 14 Aug archetype audit: task-embedded AI for Application Manager, Procurement (renewals/compliance/spend/licenses), ARB (queue triage + session drafts), CTO (executive briefing + investment suggestions), Business Architect (value-stream / BMC / business-case drafting), Portfolio Manager (wire the orphaned ai-gap-detection API into the rationalization dashboard), plus five missing AI persona charters and the two persona-key mismatches.

**Architecture:** Every feature copies the canonical advisory-AI trio shipped in `ab523e5` (ARB pre-brief): a service module that assembles strictly-real context → prompts the LLM for a fixed-key JSON object → validates it hard (custom `...Error`, never a fabricated fallback); a `POST` route gated by `FeatureFlagService.require_ai_for_route(FeatureFlagService.FEATURE_SUGGESTIONS, ...)` returning 503 (no LLM) / 502 (unparseable) / 404 (tenant-filtered `get_or_404`); an advisory UI card that drafts into view (apply-into-form where a form exists, per the `736b2e2` contract-extraction pattern) and never writes silently. Charters extend `architect_persona_charters.py` exactly in its existing shape (charter string + fault-tolerant `_safe()` live-context builder).

**Tech Stack:** Flask/Jinja2, Alpine.js, `LLMService.generate_from_prompt`, pytest with shared fixtures from `tests/conftest.py`.

**Spec:** The gap analysis in this session's conversation (14 Aug 2026); reference implementations are the spec: `app/modules/architecture/services/arb_review_ai_service.py`, `app/modules/architecture/routes/arb_review_ai_routes.py`, `tests/test_arb_review_ai.py`, `app/modules/procurement/contract_extraction_service.py` + `app/modules/procurement/templates/procurement/contract_form.html` (apply-per-field UI), `app/modules/ai_chat/services/architect_persona_charters.py`.

## Global Constraints

- Never invent data: no fallback values in `catch`/`except`; LLM parse failure → 502 with error JSON; missing value → `None` → `—`.
- Every new route: `@login_required` + `FeatureFlagService.require_ai_for_route(FeatureFlagService.FEATURE_SUGGESTIONS, endpoint_name="...")` guard first, ORM `get_or_404` for tenant filtering (never raw SQL).
- SQLAlchemy 2.0: raw SQL only via `db.text(...)` (avoid raw SQL entirely in this wave).
- Templates: DESIGN.md tokens only (`bg-card`, `text-muted-foreground`, `text-primary`, tint text uses `-emphasis`); buttons have `type="button"`; icon `sparkles` via `data-lucide`; no `console.log`; toasts via `Platform.toast`; `x-show` needs `x-cloak`. New Tailwind classes require `python scripts/build_css.py` rebuild before commit if any class is new.
- fetch in JS: `if (!resp.ok) throw` — never leave metrics at initialisers on 404.
- Tests use `tests/conftest.py` shared fixtures (`db_session`, `make_org`) and the `_clear_auth_caches()` + `logged_in_org` pattern copied from `tests/test_arb_review_ai.py`. Every task's tests cover: happy path (mocked `LLMService.generate_from_prompt`), LLM failure → 502, unparseable → 502, AI-disabled → 503, and advisory-only (no DB write).
- Git: work happens on branch `feat/ai-enablement-wave` in worktree `.worktrees/ai-wave`. `git add <file>` individually, never `-A`. Commit messages via `git commit -F-` heredoc.
- Every commit's message ends with the Claude Co-Authored-By trailer.

## Canonical pattern (copy this trio; per-task sections give only the deltas)

Service module shape (real code — adapt names/keys per task):

```python
"""<one-para purpose — advisory only, nothing persisted>"""
from __future__ import annotations
import json, logging
from typing import Any, Dict
from app.modules.ai_chat.services.llm_service_impl import LLMService

logger = logging.getLogger(__name__)

class <Feature>AIError(Exception):
    """LLM response unusable. Never caught to fabricate a fallback."""

def _build_context(<real_orm_objects>) -> Dict[str, Any]:
    # ONLY real fields read from the ORM objects / cheap org-scoped queries.
    ...

def _build_prompt(context: Dict[str, Any]) -> str:
    return (
        "<persona framing>. Below is the real, verified context — do not invent facts.\n\n"
        f"Context (JSON):\n{json.dumps(context, indent=2, default=str)}\n\n"
        "Respond ONLY with a single JSON object with exactly these keys:\n"
        "<key spec from the task section>\n"
        "Respond with raw JSON only, no markdown fences, no extra prose."
    )

def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(ln for ln in raw.splitlines() if not ln.startswith("```"))
    return raw.strip()

def _parse(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        raise <Feature>AIError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise <Feature>AIError("LLM response was not a JSON object")
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise <Feature>AIError(f"LLM response missing required keys: {sorted(missing)}")
    # per-key type checks: strings are strings, lists are lists, enums in the allowed set
    return {<coerced copy>}

def generate_<feature>(<args>) -> Dict[str, Any]:
    raw = LLMService.generate_from_prompt(_build_prompt(_build_context(<args>)), use_cache=False)
    return _parse(raw)
```

Route shape:

```python
@<bp>.route("<path>", methods=["POST"])
@login_required
def <endpoint>(...):
    guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_SUGGESTIONS, endpoint_name="<bp>.<endpoint>")
    if guard:
        return guard
    obj = <Model>.query.get_or_404(obj_id)   # TenantMixin filters cross-org to 404
    try:
        result = generate_<feature>(obj)
    except <Feature>AIError as e:
        logger.warning("<feature> unparseable for %s: %s", obj_id, e)
        return jsonify({"error": f"AI <feature> failed: {e}"}), 502
    except Exception as e:
        logger.exception("<feature> failed for %s", obj_id)
        return jsonify({"error": f"AI <feature> failed: {e}"}), 502
    return jsonify({"<feature>": result})
```

Test file shape: copy `tests/test_arb_review_ai.py` verbatim structure — `client` fixture, `logged_in_org` fixture (role per task), `_clear_auth_caches()`, `_VALID_LLM_JSON` for the task's key set, then the five standard tests. Monkeypatch `FeatureFlagService.is_ai_enabled` and the service module's `LLMService.generate_from_prompt`.

UI card shape (advisory panel; adapt heading/fields):

```html
<div class="bg-card border border-border rounded-lg p-4 space-y-3"
     x-data="{ loading: false, brief: null, error: null,
       async run() {
         this.loading = true; this.error = null;
         try {
           const resp = await fetch('<endpoint-url>', { method: 'POST' });
           const json = await resp.json();
           if (!resp.ok) throw new Error(json.error || ('HTTP ' + resp.status));
           this.brief = json.<feature>;
         } catch (e) { this.error = e.message; }
         finally { this.loading = false; }
       } }">
  <div class="flex items-center justify-between">
    <h3 class="text-lg font-semibold text-foreground flex items-center gap-2">
      <i data-lucide="sparkles" class="h-4 w-4 text-primary"></i> <Card title></h3>
    <button type="button" @click="run()" :disabled="loading"
      class="inline-flex items-center justify-center rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-4 py-2 disabled:opacity-50 disabled:pointer-events-none">
      <span x-show="loading" x-cloak class="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full inline-block mr-2"></span>
      Generate</button>
  </div>
  <p class="text-sm text-muted-foreground" x-show="!brief && !error && !loading">Advisory only — nothing is saved.</p>
  <p class="text-sm text-destructive-emphasis" x-show="error" x-cloak x-text="error"></p>
  <template x-if="brief"> <!-- per-task fields rendered with x-text; lists via <template x-for> --> </template>
</div>
```

---

### Task 1: Persona charters — five new + two key-mismatch fixes

**Files:**
- Modify: `app/modules/ai_chat/services/architect_persona_charters.py`
- Test: `tests/test_persona_charters_wave.py` (new)

**Interfaces:**
- Produces: `ARCHITECT_PERSONAS` extended with `"arb_member", "portfolio_manager", "cto", "procurement", "application_manager"`; new module-level dict `PERSONA_ALIASES = {"solution_architect": "solutions_architect", "cio": "cto"}`; `build_architect_prompt(persona)` and `get_live_context(persona)` resolve aliases first (`persona = PERSONA_ALIASES.get(persona, persona)`).

- [ ] **Step 1: Write failing tests** — `tests/test_persona_charters_wave.py`: for each of the 5 new personas assert `build_architect_prompt(p)` returns a string containing "HARD RULES" and "Live Platform Data"; assert `build_architect_prompt("solution_architect")` is not None (alias resolves); assert `build_architect_prompt("cio")` is not None; assert every `enterprise_role` in `VALID_ENTERPRISE_ROLES` except `platform_admin` resolves to a charter (platform_admin documented as intentionally charter-less — assert it returns None). Tests need `app` fixture only (context builders are `_safe`-wrapped so run without data).
- [ ] **Step 2: Run, verify fail** (`pytest tests/test_persona_charters_wave.py -q`).
- [ ] **Step 3: Implement.** Five charters in the existing voice (mission / scope of duty / how-you-answer / `{_EVIDENCE_RULES}`):
  - `arb_member` — governance reviewer: challenge submissions against active principles, ADR precedent, governance gates; propose conditions not rewrites; disposition vocabulary approved/approved_with_conditions/rejected/deferred; never claims to decide.
  - `portfolio_manager` — TIME rationalization steward: disposition mix, duplicate groups, cost/ownership coverage, vendor concentration; next action on /applications/rationalization.
  - `cto` — executive: verdict-first, portfolio health score, ARB pipeline flow, investment posture, risk hotspots; ≤5 sentences unless asked.
  - `procurement` — commercial steward: contracts, renewals within 90 days, licence position (entitled vs deployed), spend by category, vendor risk; never invents contract terms.
  - `application_manager` — application steward: owned apps' health/lifecycle, incidents-to-lifecycle coherence, upgrade/retire timing; scoped to the user's ApplicationOwner rows.
  Five `_safe()`-wrapped context builders with cheap org-scoped aggregates: arb_member (ARBReviewItem counts by status, active principle count), portfolio_manager (reuse `_ea_context`'s rationalization+portfolio sections pattern + duplicate-group count), cto (solution counts by governance_status, ARB queue depth, app total), procurement (Contract/License/spend aggregates from procurement models — read `app/modules/procurement/models.py` for real column names), application_manager (ApplicationOwner-scoped app count by health_status — note: builder runs per-request; scope by `flask_login.current_user` if available inside `_safe`, else return org-wide counts labelled as such).
  Add `PERSONA_ALIASES` and resolve in both public functions.
- [ ] **Step 4: Run tests to pass.**
- [ ] **Step 5: Commit** (`git add` the two files; `feat(ai): persona charters for the five uncovered archetypes + alias joins`).

### Task 2: Wire ai-gap-detection into the rationalization dashboard

**Files:**
- Modify: template rendered by endpoint `unified_applications.rationalization_dashboard` (resolve via `grep -rn "rationalization_dashboard" app/modules/applications/` → follow `render_template` — expected `app/templates/applications/rationalization.html`)
- Test: `tests/test_ai_wiring_ui.py` (append)

**Interfaces:**
- Consumes: existing `GET /api/ai-gap-detection/summary`, `/critical-gaps`, `/rationalization`, `/vendor-lifecycle` (`app/modules/ai_chat/routes/ai_gap_detection_routes.py` — read it first for exact response envelopes; unwrap `json.data ?? json`).

- [ ] **Step 1: Read the four endpoints' response shapes** in `ai_gap_detection_routes.py` and the target template's existing Alpine component.
- [ ] **Step 2: Write failing UI-wiring test** (append to `tests/test_ai_wiring_ui.py`, following its existing assertions style): rationalization page HTML contains `data-testid="ai-gap-panel"` and references `/api/ai-gap-detection/summary`.
- [ ] **Step 3: Implement** an "AI Gap Analysis" card (canonical UI card, `data-testid="ai-gap-panel"`) with four tabs/sections (summary, critical gaps, rationalization opportunities, vendor lifecycle risks), each lazy-loading its GET endpoint on first open, rendering lists with `—` for nulls, `if (!resp.ok) throw`.
- [ ] **Step 4: Run test + `python scripts/verify.py --gate template-syntax`.**
- [ ] **Step 5: Commit** (`feat(portfolio): the orphaned gap-detection API gets its dashboard`).

### Task 3: Application Manager — AI health assessment

**Files:**
- Create: `app/modules/my_applications/services/health_ai_service.py`, `app/modules/my_applications/routes/health_ai_routes.py` (register following how `crud_routes.py` attaches to the module's blueprint — read `app/modules/my_applications/routes/__init__.py` first)
- Modify: `app/modules/my_applications/templates/my_applications/health_overview.html`
- Test: `tests/test_my_applications_health_ai.py`

**Interfaces:**
- Produces: `POST /my-applications/api/app/<int:app_id>/ai-health-assessment` → `{"assessment": {"summary": str, "suggested_health_status": one of the model's real health_status values (read them from the model/templates first), "suggested_lifecycle_status": one of the real lifecycle values, "signals": [str], "recommended_actions": [str], "rationale": str}}`. Route guard: `@requires_application_owner` equivalent — copy the decorator usage from `app/modules/my_applications/routes.py` AND verify the app belongs to the current user's `ApplicationOwner` rows (404 otherwise).
- Context builder reads only real fields: name, description, lifecycle_status, health_status, business_criticality, annual_cost/TCO fields if present, vendor + vendor lifecycle if linked, open rationalization score if present.

- [ ] Steps 1–5: canonical trio + five standard tests (role `application_manager`, plus a sixth test: an app NOT owned by the user → 404) + advisory card on `health_overview.html` per app row or detail panel with "Apply suggestion" buttons that only fill the existing edit-form fields via link to `/my-applications/app/<id>/edit?suggest_health=...` — read the edit form template and prefill via query params parsed in its route (nullable, ignored when absent). Commit `feat(my-apps): AI health assessment for application owners`.

### Task 4: Procurement AI — renewals briefing, compliance remediation, licence position, spend recommendations

**Files:**
- Create: `app/modules/procurement/procurement_ai_service.py` (four generate functions sharing one parse helper), `app/modules/procurement/ai_routes.py` (attach to the existing procurement blueprint the same way `crud_routes.py` does — read `app/modules/procurement/routes.py` for the bp object and `@requires_procurement`)
- Modify: `app/modules/procurement/templates/procurement/renewals_dashboard.html`, `compliance_dashboard.html`, `licenses_list.html`, `spend_analytics.html`
- Test: `tests/test_procurement_ai.py`

**Interfaces (all POST, all `@requires_procurement` + AI guard):**
- `/procurement/api/contracts/<int:contract_id>/ai-renewal-brief` → `{"brief": {"summary": str, "stance": "renew"|"renegotiate"|"consolidate"|"exit", "leverage_points": [str], "risks": [str], "questions_for_vendor": [str], "rationale": str}}` — context: the contract's real fields + its licences (entitled vs deployed) + vendor name + days-to-expiry (computed from the contract's own date columns; read `app/modules/procurement/models.py` for names).
- `/procurement/api/compliance/violations/<int:license_id>/ai-remediation` → `{"remediation": {"summary": str, "options": [{"option": str, "tradeoff": str}], "recommended_option": str, "rationale": str}}` — context: the licence row's entitled/deployed/contract fields.
- `/procurement/api/licenses/ai-position` → `{"position": {"summary": str, "anomalies": [str], "recommended_actions": [str]}}` — context: org-wide licence aggregate (count, over-deployed list, unused-entitlement list — real query).
- `/procurement/api/spend/ai-recommendations` → `{"recommendations": [{"title": str, "detail": str, "category": str}], "summary": str}` — context: spend-by-category aggregates as computed by the existing spend_analytics route (extract/reuse its query, do not duplicate logic — factor into a helper if needed).
- [ ] Steps: canonical trio ×4 (one service file, one routes file), five standard tests per endpoint can share fixtures — minimum: happy+502+503 per endpoint and 404 for the two id-scoped ones (role `procurement`; build Contract/License rows with the model's real required columns — copy setup from `tests/smoke` procurement write journey or existing procurement tests). Advisory cards on the four templates (canonical card; renewals card renders per-contract "AI brief" button in the row/expanded view; compliance card per violation row). Commit `feat(procurement): AI across renewals, compliance, licences and spend`.

### Task 5: ARB — queue triage + session agenda/minutes drafts

**Files:**
- Create: `app/modules/architecture/services/arb_queue_ai_service.py`, `app/modules/architecture/routes/arb_queue_ai_routes.py` (side-effect import from `arb_routes.py`, same as `arb_review_ai_routes.py`)
- Modify: `app/templates/arb/dashboard.html` (queue triage card), `app/templates/arb/session_detail.html` (agenda + minutes draft cards)
- Test: `tests/test_arb_queue_ai.py`

**Interfaces:**
- `POST /arb/api/queue/ai-triage` → `{"triage": {"summary": str, "items": [{"review_number": str, "title": str, "complexity": "routine"|"standard"|"contentious", "reason": str}], "suggested_order": [str]}}` — context: up to 20 pending/submitted `ARBReviewItem` rows (real fields only: number, title, type, priority, scores, age). Items whose `review_number` is not in the context are dropped at parse time (no invented reviews).
- `POST /arb/api/sessions/<int:session_id>/ai-agenda` → `{"agenda": {"summary": str, "items": [{"review_number": str, "suggested_minutes": int, "focus": str}], "sequencing_rationale": str}}` — context: the session row + its linked review items (read the session model in `app/models/architecture_review_board.py` first for the relationship name).
- `POST /arb/api/sessions/<int:session_id>/ai-minutes-draft` → `{"minutes": {"summary": str, "decisions": [{"review_number": str, "disposition": str, "conditions": [str]}], "actions": [str]}}` — context: the session's reviews **with recorded dispositions only**; if none recorded, service raises its error → route returns 409 `{"error": "No recorded decisions to draft minutes from"}` (not 502 — add a distinct test).
- [ ] Steps: canonical trio, tests (role `enterprise_architect` — passes governance), advisory cards. Minutes card renders a copyable draft (`<textarea readonly>` populated from the JSON) — never auto-saves. Commit `feat(arb): queue triage and session drafts — the board gets a clerk`.

### Task 6: CTO — executive briefing + investment-priority suggestions

**Files:**
- Create: `app/modules/dashboard/v2/services/executive_briefing_service.py`, route appended to the module that owns `dashboard.health_scorecard` (resolve: `grep -rn "health_scorecard" app/modules/dashboard/`)
- Modify: health-scorecard template (from that route's `render_template`), investment-priorities template (endpoint `architecture.investment_priorities` — resolve the same way)
- Test: `tests/test_executive_briefing_ai.py`

**Interfaces:**
- `POST /dashboard/api/ai-executive-briefing` → `{"briefing": {"headline": str, "what_changed": [str], "risks": [str], "recommended_focus": [str], "rationale": str}}` — context: the same aggregates the scorecard route already computes (factor its metric assembly into a reusable helper rather than re-querying differently; read the route first).
- `POST /architecture/api/investment-priorities/ai-suggest` → `{"suggestions": [{"item": str, "priority": "now"|"next"|"later", "rationale": str}], "summary": str}` — context: the investment-priorities page's own data assembly.
- [ ] Steps: canonical trio ×2, five standard tests each (role `cto`), advisory cards on both pages. Commit `feat(cto): the scorecard explains itself`.

### Task 7: Business Architect — value-stream grid suggest, BMC block draft, business-case draft

**Files:**
- Create: `app/modules/<owning module>/services/business_arch_ai_service.py` — resolve owners: `grep -rn "value_stream.index\|business_model.index\|business_case.index"` for blueprints; place one service per owning module if they differ, sharing nothing beyond the canonical pattern
- Modify: the three index templates (value-streams grid, business-model canvas, business-case document)
- Test: `tests/test_business_arch_ai.py`

**Interfaces:**
- `POST /value-streams/api/<int:stream_id>/ai-suggest-mappings` → `{"suggestions": [{"stage": str, "capability": str, "rationale": str}], "summary": str}` — context: the stream's real stages + org capability catalog names (capped 50). Parse drops any suggestion whose stage or capability is not in the context. UI: suggestions render next to the grid with per-row "Apply" calling the grid's **existing** click-to-set endpoint (read the template's current cell-set fetch call and reuse it) — apply is the existing write path, AI never writes.
- `POST /business-model/api/<int:canvas_id>/ai-draft-block` body `{"block": <one of the 9 real block keys — read the canvas model/template for their names>}` → `{"draft": {"block": str, "content": str, "based_on": [str]}}` — context: the canvas's other filled blocks + app/capability aggregates. UI: draft into the block's existing inline editor, user saves via existing save.
- `POST /business-case/api/<int:case_id>/ai-draft-section` body `{"section": <real section key from the business-case model>}` → same shape as BMC. Same draft-into-editor rule.
- [ ] Steps: canonical trio ×3, tests (role `business_architect`; include invalid-block-key → 400 test), UI wiring. Commit `feat(biz-arch): drafting assist for streams, canvas and cases`.

### Task 8: Verification, merge, deploy, live confirmation

- [ ] Full test additions pass: `pytest tests/test_persona_charters_wave.py tests/test_my_applications_health_ai.py tests/test_procurement_ai.py tests/test_arb_queue_ai.py tests/test_executive_briefing_ai.py tests/test_business_arch_ai.py tests/test_ai_wiring_ui.py -q` (TEST_DATABASE_URL on :5439).
- [ ] `python scripts/build_css.py` if any template class is new, then `python scripts/verify.py --tag static` — all static gates green, no ratchet regressions (design-tokens stays ≤ baseline; new templates use tokens only).
- [ ] `python scripts/verify.py` full (DB gates included) in the worktree.
- [ ] Merge `feat/ai-enablement-wave` → `main` (check `git status` in the main checkout first — another agent may have staged work; never `--amend`, never sweep their files). Re-run `verify.py --tag static` on merged main. Push origin.
- [ ] Deploy per prod-deploy memory: check the droplet's actual branch first, `git checkout`/pull on the droplet, `docker compose restart`, poll the public sslip.io URL with a 15-minute bound (boot chain takes 8–12 min), confirm HTTP 200 + a spot-check page.
- [ ] Report: what shipped, test counts, gate summary, live confirmation.
