# Audit — AI-assist gaps and UI/UX consistency across `/modules/` (14 Aug 2026)

Scope: every screen reachable from the `/modules/` directory (40 sidebar links + 13 "More tools").
Method: two exhaustive code sweeps (not sampled), evidence recorded as file:line.
This file is the durable record; the conversation summary is derived from it.

## Part 1 — AI-suggest / AI-powered gaps

### Modules with NO AI where the core task is judgement-heavy (worst first)

1. **Contracts** — no clause extraction / auto-population from uploaded contract PDFs. Zero LLM references in all of `app/modules/procurement/`. The most classic LLM task in the product, done fully by hand.
2. **Renewals** — no renew/renegotiate/consolidate/drop recommendation, despite the platform holding every input signal (spend, licences, TIME disposition, duplicate overlap).
3. **Spend** — charts with no anomaly narration or savings suggestions.
4. **Licences** — no right-sizing / shelfware detection.
5. **Procurement Compliance** — governance gates exist but nothing checks contract text against them.
6. **ARB Reviews** — no reviewer pre-brief, conflicting-ADR surfacing, or draft disposition. The journey can *draft* an ARB submission (`wizard.js:1014`) but the *reviewing* side gets nothing.
7. **ARB Dashboard / Sessions** — no agenda synthesis or cross-review theme detection.
8. **Applications list** — no row-level AI enrichment; the AI mapper exists but only fires at import (see Part 1b).
9. **Capabilities / Capability Map** — no AI capability discovery or gap narration; the only "AI" on the page is a dropdown option label.
10. **Rationalization** — TIME disposition computed by rules with no written rationale; can't survive challenge.
11. **Traceability Matrix** — computes gaps (`get_gap_analysis`) but never proposes the relationship that would close them.
12. **Health Scorecard** — all inputs on the page, no narrative synthesis.
13. **Portfolio** — no demand triage / initiative scoring.
14. **Value Streams** — no stage decomposition or capability-to-stage suggestions.
15. **ADM Kanban** — "suggestions" are plain DB typeahead (`board_v2.js:537-575`), not inference; no deliverable drafting.
16. **Maturity Frameworks** — no evidence-based level suggestion or improvement drafting.
17. **My Applications (all 4 screens)** — the non-architect audience gets zero assistance; no LLM reference in the module.
18. **Governance Gates** — no gate-criteria drafting (minor).
19. **Dashboard Overview** — no "what changed / what needs you" briefing; only a link to AI Chat (`overview.html:59`).

### Modules where AI is BUILT but not connected (cheapest wins)

- **Stakeholder Map** — a complete 5-method LLM service (`stakeholder_service.py:46-292`: identify, influence, concerns, map-to-requirements, engagement strategy) with **no route and no UI**. Page is a hand-placed D3 grid.
- **ArchiMate Elements** — live endpoint `POST /<layer>/<type>/ai-generate` (`archimate_crud/routes.py:1149-1170`) that **no template or JS calls**.
- **Duplicate Detection** — a full AI dedupe dashboard (`/ai/dashboard`, `ai_duplicate_detection_service.py`) that **navigation never points at**; the listed page uses only the non-AI strategies.
- **Applications** — `comprehensive-auto-map` (LLM APQC/vendor/ArchiMate mapping, `auto_mapping_routes.py:147,368,881`) reachable **only from the import modal checkbox**; existing rows can never be enriched.
- **Capabilities** — `CapabilityDiscoveryAgent` (LLM extraction of capabilities from documents) has **no route**; only `# noqa` re-exports reference it.
- **Chief Architect Synthesis** — AI-branded, deterministic in fact (`chief_architect_service.py:1-10`); users will expect synthesis prose.
- **EA Briefings** — "Generate" button assembles templates; no LLM in `enterprise_briefing_service.py`.
- **Consolidation List** — LLM similarity/consolidation services exist but are wired into the *legacy* routes, not the listed dashboard.
- **Vendors** — "Ask AI" is just a link to chat; `PricingExtractionService` reachable only from an admin screen.

### Modules that already have real AI (for reference)

AI Chat, Architecture Journey (deepest), Solutions, ArchiMate Composer, Roadmaps, Capability Health, Impact Analysis, Investment Analysis, Batch Import, Programmes (import review), plus the admin AI control plane.

## Part 2 — UI/UX inconsistency ranking (worst first)

| Rank | Module | Severity | Dominant defects |
|---|---|---|---|
| 1 | Procurement (all 6 screens) | HIGH | 9 pages, zero standard headers; native `confirm()`; wrong wrapper; hand-rolled empty states; literal `0`s; free-text owner field; no form loading states; "Overview" and "Contracts" land on the same screen |
| 2 | Admin (analytics, health) | HIGH | `/admin/analytics` is a raw unstyled HTML stub ("This is a stub."); `/admin/health` extends a page instead of a layout |
| 3 | My Applications (3 screens) | HIGH | Whole module off-shell; sibling nav differs per page; module hub unreachable from the directory; duplicates the Applications list with a different design |
| 4 | Rationalization | HIGH | Three competing rationalization screens; 36 raw-color violations on one; 4200-line raw table |
| 5 | Architecture Journey | HIGH | Deliberately a foreign design system (onboarding-flow skin, `text-4xl` h1); v2/v3 fork still shipped |
| 6 | Capabilities / Capability Map | HIGH | View switcher exists on 1 of 7 sibling pages (clicking a tab strands the user); hardcoded hex palette; 7 forbidden `onclick=`; native `<dialog>`; 4 header conventions across siblings |
| 7 | ADM Kanban | MED-HIGH | Three different H1 sizes in one module; no page padding; asymmetric cross-links |
| 8 | AI Chat | MED-HIGH | No header/breadcrumbs on any of 6 pages; parallel inline card system shadowing the macro |
| 9 | Solutions family (5 entries) | MEDIUM | Three wrapper conventions; duplicate `risk_heat_map`/`risk_heatmap` templates; three competing programme surfaces |
| 10 | ArchiMate Composer | MEDIUM | Fourth undocumented base layout; 77 inline `style=` attributes |
| 11 | ARB (3 entries) | MEDIUM | Two header systems inside the module; "Reviews" and "Sessions" are the same template with a flag; Python-side raw colors bypassing the token gate |
| 12 | Applications | MEDIUM | Double breadcrumbs on edit; three header conventions; free-text owner fields; literal `0` KPIs |
| 13 | Vendors | MEDIUM | Free-text application field where a picker is mandated; three content widths in one module |
| 14 | ArchiMate Elements | MEDIUM | Consistently off-platform (`text-3xl`, no macros) |
| 15 | Portfolio | MEDIUM | `text-3xl` h1; form loses page rhythm; no submit states |
| 16 | Roadmaps | MEDIUM | Two live view functions + one dead one for the same page; service-injected raw colors bypassing the gate |
| 17 | Investment Analysis | MEDIUM | Three URLs render one page; silent prerequisite template swap |
| 18 | Modules Directory itself | MEDIUM | Advertises "searchable" but has no search input; minority header convention; provisional-taxonomy copy shown to users |
| 19 | Maturity Frameworks | LOW-MED | Error path redirects into a different module; sibling h1 drift |
| 20-24 | Traceability, Batch Import, Health Scorecard, Stakeholder Map, Value Streams | LOW | One-line defects each |
| 25-29 | Impact Analysis, Capability Health, Duplicate Detection, Consolidation List, Dashboard Overview | LOW/NONE | Conforming — reference implementations |

### Cross-cutting (visible between every pair of modules)

- **X1 (HIGH):** three page-header systems ship simultaneously — `page_header` (181 files), `page_shell` (10), and none (113 admin_base templates).
- **X2 (HIGH):** two page wrappers — `p-6 space-y-6` (the documented one) vs `container mx-auto` (64 templates); content width jumps between adjacent screens.
- **X3 (HIGH):** H1 sizes range `text-lg` → `text-4xl`; even `page_header.html:58` deviates from DESIGN.md:117.
- **X5 (HIGH):** the entity-picker rule is implemented in only 2 templates in the whole repo; every other owner/vendor/application field is free text.
- **X4/X6/X7 (MED):** a canonical layout imports a deprecated macro file; server-side Python injects raw Tailwind colors past the token gate; form loading state exists on 1 of 8 sampled forms.

## Recommended attack order

1. **Connect the built-but-orphaned AI** (Stakeholder Map service→route→UI, ArchiMate ai-generate button, AI dedupe dashboard link, auto-map from the Applications list) — days of work, immediate visible AI value.
2. **Procurement wave** — shell conformance + the contract-clause-extraction AI (biggest gap and biggest AI win in one module).
3. **ARB reviewer AI** — pre-brief and disposition drafting; the platform's core governance loop.
4. **Cross-cutting shell ratchet** — one header macro, one wrapper, one H1 scale, entity pickers; add a verify.py gate counting violations so the numbers only go down.
5. Then per-module cleanups in the ranking order above.
