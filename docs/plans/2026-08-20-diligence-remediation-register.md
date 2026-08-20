# Diligence Remediation Register — 20 Aug 2026

Source: Technical Due Diligence audit of commit `5bc3ce7` (deployed tip), 20 Aug 2026.
Scope exclusion set by the owner: **all billing / monetisation items are OUT OF SCOPE**
(MON-01, MON-02, plan enforcement, seat limits, Stripe, usage metering for spend).

Baseline verified in-repo 20 Aug 2026:
- `HEAD`/`main` = `ab523e5`, 176 commits behind deployed `5bc3ce7`; `origin/main` 108 behind. No divergence.
- `fix/green-gates` and `fix/qa-register-100` exist but sit AT `5bc3ce7` with 0 commits ahead — unstarted.
- All work branches from `5bc3ce7`, not from `main`.

Status legend: TODO / DOING / DONE / DROPPED (with reason).

---

## Wave 0 — Restore the invariant (blocks everything else)

| ID | Task | Audit ref | Status |
|---|---|---|---|
| W0-1 | Fast-forward local `main` and `origin/main` to `5bc3ce7` so every clone reflects what runs | §09 | **DONE (local)** — local `main` ff'd ab523e5→5bc3ce7, verified true ancestor, 0 ahead. `origin/main` push pending W0-7. |
| W0-2 | Fix `verify.py` UnicodeEncodeError on the cp1252 Windows console (reconfigure stdout to UTF-8 at entry) | CQ-06 | **DONE** `b08da8a` — reproduced (`'✓'` → UnicodeEncodeError, `—` → mojibake); `_force_utf8_console()` at `main()` entry; re-verified under forced cp1252. |
| W0-3 | Reproduce the 3 red gates at `5bc3ce7` and record the exact output as evidence | CQ-01 | **DONE** — evidence below. Note it is **4 red, not 3**: `css-build` also fails. |
| W0-4 | Fix `tenant-scoping`: `application_fact_sheet.py:101` unscoped query | CQ-01 | **DONE** `b08da8a` — gate 1→0. |
| W0-5 | Fix `silent-data`: `application_fact_sheet.py:99,154` broad `except` returning `[]` — must surface the error, not render "no capabilities" on a screen branded the single source of truth | CQ-01/CQ-02 | **DONE** `b08da8a` — gate 2→0. |
| W0-6 | Close QA finding ARCH-064 (capability-map 482KB, architecture dashboard 170KB) — lazy-load the macro's modals instead of rendering all of them | CQ-01/PF-02/UX-02 | **DONE** `b2bd44e` — /capability-map/ 436,618→368,193 bytes (−15.7%). QA register 160/160. |
| W0-7 | Full `verify.py --tag static` green (every gate, never a subset), then deploy and confirm the live site serves | standing rule | **GREEN — 30 passed, 0 failed, 0 skipped.** Deploy in progress. |

**Exit criterion: the deployed commit passes its own gates.** Nothing else starts first — a ratchet that ships red once becomes advisory.

---

### W0-3 evidence — `python scripts/verify.py --tag static` at `5bc3ce7`, 20 Aug 2026

`26 passed, 4 failed, 0 skipped`. The register said three red gates; there are **four**.

```
FAIL  tenant-scoping   23.5s  [1 > 0]
      app/services/application_fact_sheet.py:101  [ApplicationCapabilityMapping]
      db.session.query(...) with no organization_id filter nearby

FAIL  silent-data       7.7s  [2 > 0]

FAIL  qa-register       0.3s  [1 > 0]
      S3 ARCH-064 Large server-rendered HTML payloads without pagination
      (1 of 160 findings blocking; 147 fixed and evidenced)

FAIL  css-build        49.8s
      the committed tailwind-output.css is stale - a rebuild changes it
```

**`css-build` was not in the register and is a genuine Wave 0 blocker** — the
committed CSS does not match a rebuild, so a fresh clone renders against stale
classes. It is folded into W0-7 rather than given its own ID, because the
rebuild has to run *after* the W0-6 template edits or it goes stale again.

---

## Wave 1 — Delete the latent attack surface

| ID | Task | Audit ref | Status |
|---|---|---|---|
| W1-1 | Enumerate all 25 defined-but-unregistered blueprints with exact file paths | FC-01 | **DONE** — see findings below. Audit's 25 = definition *sites*; **23 distinct blueprints**. |
| W1-2 | Register `gdpr_bp` after a security review of its routes — GDPR export/erasure is written, secured, has a model and a table, and is unreachable | FC-01 | TODO |
| W1-3 | Add an authz test proving the GDPR export + erasure endpoints resolve and enforce self-or-admin | FC-01 | TODO |
| W1-4 | **Delete** the remaining 20 (not 24 — see W1-1 findings; 3 are registered via non-symbolic paths and 1 is live under another parent). Priority: `signup_routes.py` (unauthenticated `invite_member` taking `org_id` from the URL and `inviter_id` from the body — org-boundary privilege escalation in six lines) and `analytics_routes.py` (unauthenticated admin dashboard, event endpoint accepting an arbitrary `user_id`) | SEC-02 | TODO |
| W1-5 | Land a `verify.py` gate: **blueprints defined == blueprints registered**, ratcheted at 0, so the class cannot return | audit ethic | TODO |

W1-4 removes the code referencing `/billing/setup` and `plan="starter"` (not a valid `SubscriptionPlan` member). That deletion is in scope; building a replacement billing flow is not.

---

### W1-1 findings — verified 20 Aug 2026

Method: AST scan of every `.py` under `app/` — **205 `Blueprint(...)` definition sites**
against **277 `register_blueprint(...)` call sites** — then manual resolution of the
three registration paths a symbol diff cannot see. Both `USE_*_GUARDRAILS` tiers and
every `register(app)` entrypoint were walked.

**Verified: 25 unregistered definition sites, collapsing to 23 distinct blueprints.**
123 unreachable routes, **14 of them carrying no auth decorator of any kind**.

**Four corrections to the audit — deleting on the audit's list as written would
have removed working code:**

| Blueprint | Why it must NOT be deleted |
|---|---|
| `application_api_bp` (`app/api/application_routes.py:43`) | Registered via `_safe_register(lambda: ...)` — invisible to a symbol diff |
| `admin_security_bp` (`app/modules/admin/security_routes.py:31`) | Registered via the `_register_optional_standalone` spec list |
| `main` (`app/main/views.py:26`) | Registered through the aliased re-export `from app.main import main as main_blueprint` |
| `lucidchart_import_bp` (`.../lucidchart_import_routes.py:20`) | Its 4 routes ARE live — `archimate_routes.py:34` calls `register_lucidchart_import_routes(archimate_bp)`. Delete the unused blueprint *object* only; deleting the module removes working OAuth import. |

**Confirmed as real, and both genuinely unauthenticated — but LATENT, not live**
(they are unregistered, so unreachable in production; this is why W1-4 is a deletion
task and not an incident):

- `signup_routes.py::invite_member` — `POST /api/orgs/<int:org_id>/invite`, no
  `@login_required`, no `current_user`, no membership check. `org_id` comes from the
  path and `inviter_id` from the body, both attacker-chosen: an anonymous caller could
  mint a member in **any** tenant. Its sibling `/register` is equally open and also
  broken (passes `plan="starter"`, not a valid `SubscriptionPlan`; redirects to the
  non-existent `/billing/setup`). Template exists, so it would render if wired.
- `analytics_routes.py` — `GET /admin/analytics` renders the admin dashboard with no
  auth; `POST /api/analytics/event` takes `user_id` wholesale from the body, so anyone
  could forge analytics attributed to any user. Service and template both exist.

**`gdpr_bp` — the audit is right, this is a compliance gap, not dead code.** All three
routes are already guarded (`@login_required` + `_forbid_unless_self_or_platform_admin`
on export/status; `@platform_admin_required` on erasure, which deliberately refuses
self-service). `app/models/gdpr_request.py` (`gdpr_requests`) and
`app/services/gdpr_service.py` both exist. Written, secured, and unreachable. → W1-2.

**Also worth wiring rather than deleting:** `phase_e` and `phase_h`
(`/api/ea/phase-e`, `/api/ea/phase-h`) — TOGAF phases A, B, F and G are all
registered; E and H are the only holes. And `user_role` (`admin.user_info` already
links to it).

**Two stale referrers must be fixed alongside their deletions**, or they leave dangling
links: `blueprints.py:451` claims `options_analysis_bp` is "covered by
v2/unified_vendor_api" (those routes do not exist under v2), and
`sidebar_discovery_service.py:182` advertises `/tech-debt`, which 404s.

**W1-5 gate design:** match on the *resolved* set, not bare symbol names, or the gate
reports three false positives on day one. Ratchet at 0 only after `gdpr_bp` is wired and
the deletions land; interim baseline 23.

**If `backtesting_bp` (#6) is wired up rather than deleted**, its three undecorated
routes must be decorated first — `/backtesting/summary` is a POST that batch-processes
solutions.

---

## Wave 2 — Scalability, before there is data to be slow

| ID | Task | Audit ref | Status |
|---|---|---|---|
| W2-1 | Move portfolio imports, document analysis and LLM generation onto the RQ worker. Inline execution on 3 gunicorn workers means three concurrent imports take the site down. | PF-01 | TODO |
| W2-2 | Take the RQ worker out of the compose `profile` so it runs by default; verify on the 2-vCPU box (serial containers only) | PF-01 | TODO |
| W2-3 | Paginate the three heaviest pages | PF-02/UX-02 | TODO |
| W2-4 | Fix the N+1 at `application_fact_sheet.py:129-140` — one `session.get()` per relationship edge; batch the name/type lookup | PF-02 | TODO |
| W2-5 | Convert `lazy="dynamic"` to `selectin` where the relationship is always fully iterated; keep `dynamic` only where the Query is genuinely filtered further | PF-02 | TODO |
| W2-6 | Enable the Redis cache on a **separate DB number** from the queue with `allkeys-lru`. Current `noeviction` refuses writes rather than evicting — switching cache on without changing it produces write errors under load. | PF-03 | TODO |
| W2-7 | Make the rate-limiter's Redis fallback loud — a health-degraded signal, not one log line. 3 workers on `memory://` means 3x the configured limit. | PF-05 | TODO |
| W2-8 | Dropping the 2,135 never-scanned indexes — **deferred to post-launch**. `idx_scan=0` on an empty database proves nothing about a loaded one. | PF-04 | DROPPED (deferred, with reason) |

---

## Wave 3 — Correctness and schema safety

| ID | Task | Audit ref | Status |
|---|---|---|---|
| W3-1 | Execute ADR-0002: Alembic baseline at current schema, `db upgrade` on deploy, `reconcile-schema` demoted to a drift detector. Before any customer holds data that cannot be rebuilt, not after. | CQ-03 | TODO |
| W3-2 | Remove the soft-fail from the 9-command boot chain: a tenancy backfill that silently did not run must fail the boot, not print WARN and serve | CQ-04 | TODO |
| W3-3 | Invert tenancy to fail **closed** — an explicit `unscoped_context()` for CLI/seeder paths; the ORM listener raises rather than no-ops inside a request context lacking an org | SEC-03 | TODO |
| W3-4 | Audit the 119 auth-decorator-free routes; confirm each is login, health, or a signature-verified webhook, and gate the rest | SEC-03 | TODO |
| W3-8 | `application_fact_sheet.py::_dependencies` has a broad `except` returning `{"upstream": [], "downstream": [], "linked": True}`. The `silent-data` gate does not flag the dict shape, so it passed W0-5 untouched — but it is the same defect: an import failure renders as "no dependencies". Needs the template's `linked` handling reviewed alongside. Surfaced 20 Aug during W0-5. | CQ-02 | TODO |
| W3-5 | Attack the 104 `except: pass` handlers — widen the silent-data ratchet to count bare-pass handlers and drive the number down | CQ-02 | TODO |
| W3-6 | Indirect prompt-injection defences on the RAG layer — uploaded documents and portfolio text reach prompts unfiltered; this surfaces at the first enterprise security review | SEC-05 | TODO |
| W3-7 | Backup and restore, tested end to end. Not found in the repo. | §08 | TODO |

---

## Wave 4 — Product surface: stop building, start validating

| ID | Task | Audit ref | Status |
|---|---|---|---|
| W4-1 | Self-serve signup and org creation that actually works — today an org can only be made by an admin running `create_admin.py`. Billing-free path only. | UX-03 | TODO |
| W4-2 | One-click demo tenant / seeded dataset. Highest-leverage UX fix available: 683 empty tables means empty is the default first experience. | UX-04 | TODO |
| W4-3 | Guided first-run for a new empty tenant | UX-04 | TODO |
| W4-4 | Drive the 158 shell-conformance violations down — three competing page-header systems and two page widths make adjacent modules look like different products | UX-01 | TODO |
| W4-5 | Instrument which features the 23 real users actually touch. The audit's closing recommendation: point the ratchet discipline at the product surface, not only the code surface. | §09 | TODO |

---

## Wave 5 — Strategic consolidation (largest, last)

| ID | Task | Audit ref | Status |
|---|---|---|---|
| W5-1 | Quarantine the unvalidated half: take the 63 populated tables and the workflows around them as the product; move `codegen` (41,065 lines), `solutions_product` (17,549) and the empty subsystems behind an experimental flag or into a separate repository | §09 | TODO |
| W5-2 | Finish or abandon the v1→v2 migration — 205 files, 99,285 lines, services imported 324 times from outside v2, but only 2 of 110 blueprint registrations point at v2 routes | FC-02 | TODO |
| W5-3 | Retire the 7 duplicated domains per ADR-0004 (`account`, `admin`, `ai_chat`, `auth`, `dashboard`, `integrations`, `monitoring`) | FC-02 | TODO |
| W5-4 | Split the four largest modules: `solution_design_routes.py` (12,145 lines), `codegen/routes/_helpers.py` (8,799), `deterministic_code_generator.py` (8,626), `multi_domain_chat_service.py` (8,591) | CQ-05 | TODO |
| W5-5 | Architecture drift detection — compare the modelled estate against reality pulled from cloud APIs and CMDBs. The genuine differentiator; connector scaffolding already exists. | §07 | TODO |

---

## Housekeeping

| ID | Task | Audit ref | Status |
|---|---|---|---|
| H-1 | Correct `CLAUDE.md`: it states `design_tokens` 88 and `raw_sql_tenancy` 98; both are 0 in `verification_baseline.json` | FC-04 | TODO |
| H-2 | Refresh `FEATURE_FLAGS.md` — last verified 14 Jul, five weeks stale | FC-04 | TODO |
| H-3 | Correct the 15 Aug handoff document: it says "Prod has NO LLM keys"; production has a DeepSeek key loaded | FC-04 | TODO |

---

## Explicitly out of scope (owner instruction, 20 Aug 2026)

- MON-01 plan enforcement, feature gates, seat limits
- MON-02 usage-metering pipeline for AI spend
- Stripe checkout, portal, and webhook work
- `/billing/setup` — the dead route is **deleted** under W1-4, not built
