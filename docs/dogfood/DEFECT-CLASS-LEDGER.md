# Archie defect-class ledger v1 — what a port or a certification must not carry forward

Author: strategy workforce (`claude-code:cloud-credits-campaign`), 2026-09-17. Audience: internal (refuter,
solution-architect, enterprise-architect, tech-lead, qa-lead). Figures source: `C:\Users\Inter\archiet-strategy\ground-truth\model\repo-measurements.md`.
Evidence base: `C:\Users\Inter\repos\archie-ea` at HEAD `2ba4aa1` — `docs/adr/0001…0010`, `docs/verification.md`,
`docs/ROADMAP_TO_BEST_IN_CLASS.md`, `docs/CAPABILITY_GAP_REGISTER.md`, `docs/known-issues/*`, `docs/qa-remediation-log.md`,
`docs/dogfood/ARCHIET-CUSTOMER-ZERO.md` (PR #16), plus the measurements. Every class cites where Archie itself recorded it.

**How to use this file.** A *class* is a shape of defect, not an instance. For every class: the refuter checks the target
codebase (Iyene if porting, Archie if certifying) for the same shape before any build brief is written; the gate in the
last column becomes a failing test / CI check in the target **before** the feature lands; a class is CLOSED only when
the gate is green in CI and the symptom is absent when clicked (Phase 0 rule: demonstrated, not green).
Status vocabulary: `OPEN` (present in Archie today) · `CLOSED-IN-ARCHIE` (Archie fixed it; the gate must still exist in
any target) · `LATENT` (mechanism exists, nothing exercises it).

## A. Authority and data-shape classes (carry into any port that copies behaviour)

| # | Class | Evidence in Archie | Why it recurs in a port | Must-not-recur gate for the target | Status |
|---|---|---|---|---|---|
| A1 | **Duplicate authority — one concept, several stores/classes** | ADR 0008: capabilities in 6 tables (`business_capability` 461 rows, `capabilities` 0, `unified_capabilities` 0, …); `UnifiedCapability` designed as the canonical store, **no producer**. Measured: 15 model classes defined in ≥2 files — `ArchiMateElement`, `ArchiMateRelationship`, `ArchitectureModel` (`app/models/archimate_core.py` + `app/models/models.py`), `ApplicationComponent` (`application_component_fast.py` + `application_portfolio.py`), `Requirement`, `Principle`, `Outcome`, `TechnologyStack`, `Representation`, `ApprovalStatus`, `BatchJobStatus`, `CheckpointType`, `DuplicateType`, `ApplicationCapabilityMapping`, `MyModel`×6 (`repo-measurements.json` → `duplicate_model_classes`) | A port copies each store as a "feature"; the twins arrive with it | `store-agreement` gate (Archie has it, ADR 0008) at **0**: every concept has exactly one canonical model in the entity registry, and a CI check fails on a second `class <Name>(` under models. Registry = `ENTITY_REGISTRY.yaml` pattern, enforced by pre-commit **and** CI, not pre-commit alone | OPEN |
| A2 | **Vocabulary drift between writer and reader** | DOGFOOD-002: importer writes layer `"Implementation & Migration"` (`app/services/archimate_import_service.py:91-95`), catalog reads `Implementation` → 35 of 168 elements invisible ("133 elements total") | Enums re-typed per module during a port | One shared enum/constant module per vocabulary (layer, element type, relationship type, status); a test that every stored distinct value of `layer`/`type` is one the UI renders | OPEN |
| A3 | **Lossy import/export (round-trip fails)** | DOGFOOD-003 relationships parsed, previewed, never written (`archimate_import_service.py:322+`); DOGFOOD-004 `<properties>` dropped (`:182`, `:460`) — provenance lost; DOGFOOD-001 preview reports 0 errors, execute aborts wholesale on `name` varchar(100) (`app/models/archimate_core.py:58`) | Import code is usually ported first and least tested | Round-trip test: import → export → import gives `exists == N, new == 0, conflict == 0` for elements **and** relationships **and** properties; preview must validate every constraint execute enforces; execute is per-element with savepoints and returns 207, never a raw DB error | OPEN |
| A4 | **Schema managed by three mechanisms, none authoritative** | ADR 0002: `create_all()` + `reconcile-schema` (ADD-only, nullable-only) + 130 unrun Alembic revisions; "every deploy silently mutates production schema"; 47 drifted columns incident; non-nullable columns structurally impossible | A port re-creates the migration story from scratch and repeats the shortcut | Exactly one migration tool; `db upgrade` runs on deploy; a `schema-drift` gate compares mapped models to the live schema and fails CI; no boot-time DDL | OPEN (target state accepted, not executed) |
| A5 | **Tables with no model / models with no table** | known-issues: `conversation_threads` existed only in a migration, no model → `UndefinedTable` on fresh install (fixed 2026-08-10) | Same shortcut is available in any ORM | Gate: every table touched by raw SQL has a mapped model; fresh-install smoke creates and reads every table | CLOSED-IN-ARCHIE |

## B. Reachability and UI-truth classes (the "green but not demonstrated" family)

| # | Class | Evidence in Archie | Why it recurs | Gate | Status |
|---|---|---|---|---|---|
| B1 | **Done meant green + deployed, not clicked** | ROADMAP root cause: ~12 demo-path blockers behind 81 green gates; ARB decision API with no button; mapping endpoint with a dead Save; `unified_capabilities` wired into 8 APIs with nothing writing to it | Agents optimise the stated bar; a port has the same agents | Definition of done = a persona completes the real journey in the rendered UI, clicks, persists, sees after reload; a write feature cannot merge without that browser test; per-persona smoke in CI | OPEN (rule written 1 Sep; enforcement partial) |
| B2 | **Two screens answer one question differently** | ADR 0008: capability map "191" above a table "1-10 of 0"; roadmap "173 gaps" beside gap analysis "0" | Consequence of A1; survives any port that keeps A1 | `store-agreement` measurement: for every headline number, the screen(s) showing it are read and compared in a test | OPEN |
| B3 | **Orphan pages and dead controls** | known-issues: 13 templates with no route (deleted 2026-08-08); ADR 0008: domain cards that "looked pressable and did nothing"; `broken-surfaces` checker 442 → 0 (dead-link, dead-fetch, forbidden-ui, orphan-page, swallowed catches) | New pages are cheap to generate and easy to leave unrouted | `broken-surfaces` gate at 0 in the target; interaction census: every control in the live DOM has a handler and an assertion | CLOSED-IN-ARCHIE (must be recreated in a target) |
| B4 | **Feature has no entry point** | DOGFOOD-005: OEF importer only reachable inside a batch-import job page; catalog empty state offers Composer/Abacus; CAPABILITY_GAP_REGISTER G5 "orphaned/unpromoted capabilities … real engines exist but the agent can't reach them" | Backend-first agents ship endpoints without navigation | Gate: every registered route family is reachable from navigation or an explicit entry point, verified by the interaction census; the gap register's "promote to tools/nav" rule | OPEN |
| B5 | **Swallowed errors** | known-issues: 413 swallowed catch blocks → 0 (2026-08-08) | Default in generated JS/Python | `swallowed` class at 0; failures that matter surface to the user, probes may stay silent — the checker distinguishes | CLOSED-IN-ARCHIE |

## C. Correctness-hygiene classes (code-level; do **not** carry if rewritten, carry **exactly** if code is used as the spec)

| # | Class | Evidence | Gate | Status |
|---|---|---|---|---|
| C1 | **Undefined names / redefinitions / correctness lint at scale** | `verification.md`: 293 F821, 73 F811, 4,508 correctness findings, 6,300 raw colours; CLAUDE.md on another branch claimed these were cleared — "the documentation described what someone hoped it did" | Ratchets in `verification_baseline.json` ("no worse"), `undefined-exports` and `native-dialogs` at 0; **the baseline is measured on the tree, never copied from docs** | OPEN (ratcheted) |
| C2 | **Tests absent where the risk is** | Measured: `codegen` 41,568 lines / 158 routes / **0 test lines**; `transformation_room` 20,932 / 0; `solutions_product` 17,589 / 0; `architecture_assistant` 10,953 / 0; `genome` 3,616 / 0 (`repo-measurements.md`) | Ported code arrives without its (non-existent) tests | Coverage floor per module with routes; no module with routes and zero tests; tests-first in every build brief (T-1xx convention) | OPEN |
| C3 | **Two module layouts live at once** | ADR 0004: `app/<domain>/` legacy and `app/modules/<domain>/` both live; 12 `USE_*_GUARDRAILS` flags defaulted on because a fresh clone with them off produced ~66 `BuildError` 500s; measured top-level outside `modules`: `services` 154k, `models` 76k, `commands` 37k, `application_mgmt` 28k lines | A port copies both layouts or picks one at random per feature | One layout; `canonical-route` gate at 0 (no duplicate accessors decided by registration order); fallback flags removed | OPEN (completion "not scheduled") |
| C4 | **Order-dependent test failures read as product bugs** | known-issues: smoke suite 26 failed + 17 errors are a `browser` fixture-scope resource artifact, not a persona regression (2026-09-08, diagnosed not fixed) | Any target with a shared-browser fixture | Fixture isolation; a flaky-test quarantine with an owner and date; CI treats a diagnosed artifact as a defect with a ticket, not noise | OPEN |
| C5 | **SKIP counted as PASS** | `verification.md`: "a SKIP is never a pass"; CI runs `--require-db` | Tooling absent in a new environment | Same rule in the target's runner: SKIP fails in CI | CLOSED-IN-ARCHIE |

## D. Security and tenancy classes (carry unless explicitly re-verified in the target)

| # | Class | Evidence | Gate | Status |
|---|---|---|---|---|
| D1 | **Tenant scoping by mixin, with a "no context ⇒ no filtering" gap** | ADR 0003: gap 1 remediated 2026-08-07 (`do_orm_execute` filters ORM UPDATE/DELETE, ~43 models gained `TenantMixin`); gap 2 "no context ⇒ no filtering remains by design"; `tests/test_tenant_isolation.py` 6 passed / 2 xfail. **Iyene's own T-122 (gRPC `req.TenantId` + `AllowPermitChecks:false`) and Etione's T-123 are the same class on the target side** | Isolation test per boundary (ORM select/update/delete, raw SQL, gRPC, background jobs) that **fails closed** when no tenant context is present; no `xfail` on an isolation invariant | OPEN on both sides |
| D2 | **Fail-open authorization when a dependency is unconfigured** | Org pattern, not Archie-specific: MarketingIQ `permit_policy.go:32-34` `return c.Next()` when Permit client is nil; Enforcer `permit.go:129-141` returns nil | Gate: missing authz dependency ⇒ deny, with a startup check that refuses to boot "open" in deployed environments | OPEN (org-wide) |
| D3 | **CSP `unsafe-eval` required by the interactivity layer** | ADR 0007: Alpine.js `new Function` on 8,523 expressions; evaluator built, production cutover pending | Any port that keeps Alpine | `inline-handlers` gate at 0; CSP without `unsafe-eval` in the target's production config from day one | OPEN (cutover pending) |

## E. Process classes (the ones that generate all of the above)

| # | Class | Evidence | Gate |
|---|---|---|---|
| E1 | **Documentation states hopes, not measurements** | `verification.md`: CLAUDE.md figures contradicted by the measured baseline; ADR 0009's first draft "asserted the opposite and was wrong" about the scheduler | Every number in a doc or ADR names its measurement command; `model beats doc` — the enterprise model's `source` field is mandatory |
| E2 | **The owner is the QA function by accident** | ADR 0008: "the owner, who is not technical, found each of these by clicking"; ROADMAP's single success measure: "the owner stops finding defects by clicking" | Per-persona browser journeys in CI; a defect found by the owner is logged as a gate that was missing, and the gate is added before the fix |
| E3 | **Copilot writes but cannot read or act on governance** | CAPABILITY_GAP_REGISTER G1–G8: ~73 write tools, no governance read tools, no action tools, no merge, tools not persona-gated | Any AI surface in the target ships read tools for the persona's headline question before write tools; propose → validate → approve → apply, LLM never applies directly (ADR 0010) |
| E4 | **Detected drift, never acted on** | ADR 0009: backbone audit and validity services exist, "nothing invokes them on a cadence"; scheduler exists with 5 jobs, none of them the audit | Every audit/validity service is scheduled and its result is a visible model-age figure; a `LATENT` capability is a defect |

## F. Corrections to `platform-options-v2.md` that fall out of this ledger
- v2 §1 lists `transformation_room`, `solutions_product`, `architecture_assistant` as "0 routes (dead)". The measurements say 38, 28 and 13 routes respectively; the only zero-route module is `integrations` (188 lines). They are **untested**, not dead (class C2). v3 must use the measurements, not memory.
- "Dead" for v3 = class B3/B4 (no route, no entry point) **or** A1 twin **or** C3 legacy-layout duplicate — each measurable — not "outside `app/modules`".

## G. What this means for the options
- **Port Archie into Iyene (Options 1, 3):** classes A1–A4, B1–B4, C3 and D1 all copy unless every gate in this ledger exists in Iyene *before* the port starts — and Iyene has D1 open itself (T-122). The ledger is therefore the pre-condition list for those options, on top of the corrected ~80 engineer-month cost.
- **Archie as platform (Options 2, 2′):** the same ledger *is* the certification programme: A1 (15 twins, `UnifiedCapability` producer) → A4 (Alembic cutover) → C3 (one layout) → B1/B3/B4 (clicked journeys, entry points) → A2/A3 (round-trip) → D3 (CSP cutover) → C2 (tests where routes are). Each item has an existing Archie gate to turn to 0 or a named test to write; nothing here requires an invention.
- Either way the enterprise model records each class as an Assessment with a `source`, and the class is closed only by a clicked demonstration recorded in `docs/dogfood/`.
