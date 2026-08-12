# Archie shell overhaul — design spec

Approved 2026-08-12. Origin: internal product design review (2026-08-10, artifact
`archie-design-review`) + user's production screenshots of AI Chat and Dashboard at ~1024px
(2026-08-12), which confirmed the review's Red/Amber ratings and exposed sub-1280px layout
collapse the review missed. Goal: a shell and screen system credible to Fortune-500 users and
Saint-Gobain's evaluation — calmer than a Big-4 deliverable, honest as a system of record.

## Principles (binding on every wave)

1. Trust the data: `—` for not-computed, never fabricated zeros; provenance visible; AI-suggested
   content marked until confirmed. (Enforced: `fabricated-data` gate.)
2. One job per screen; title + context + actions in a single row; chrome never precedes content.
3. Persona-first navigation; the TOGAF/ArchiMate ontology stays reachable (Ctrl-K, Library,
   All-modules directory) but stops being the primary structure.
4. Empty states teach — icon, one sentence, one primary CTA — never walls of red zeros.
5. Nothing clips or overflows at 1024px; verified at 1024 / 1280 / 1440.
6. Design quality is gated, not aspired to: screenshot matrix per wave, sidebar link-count
   ratchet, design-tokens ratchet stays 0, a11y contrast baseline burns down on rebuilt screens.

## Assumptions (user-approved)

- A: Enterprise Architect, Solution Architect, CTO are the flagship personas — polished first.
- B: ArchiMate composer and Architecture Journey canvases are OUT of scope (separate projects).
- C: Waves deploy to production as they finish (no held big-bang reveal).

## 1. Navigation architecture

**Sidebar** (today: 102 links, 10 sections, identical for all roles) becomes five fixed zones,
**≤25 visible links per persona**:

| Zone | Content | Who |
|---|---|---|
| Home | persona dashboard, Health Scorecard | all |
| My work | persona's primary surface, 3–6 items (SA: Architecture Journey, Solutions, AI Chat, ADM Kanban · EA: Portfolio, Capability Map, Elements, Roadmaps · CTO: Health, Rationalization, Investment · Business Architect: Capability Map, Value Streams · Portfolio Mgr: Rationalization, Vendors, Applications · Procurement: Vendors, Contracts, Renewals, Spend · App Mgr: Applications, Rationalization, Vendors) | per role |
| Library | Applications, Capabilities, Vendors, ArchiMate Elements | all |
| Governance | ARB dashboard, Reviews, Sessions | roles on the board (EA, ARB member, CTO, admin) |
| Admin | Command Center + admin pages | platform_admin |

- Single source of truth: `app/utils/role_access.py` (role → zone → links). The sidebar template
  (`app/templates/components/admin_sidebar.html`) renders from that structure only — no
  hand-maintained parallel lists. `_bootstrap/context_processors.py` exposes it.
- The long tail: Ctrl-K global search (kept as-is) + one new "All modules" directory page
  (flat, grouped, searchable — every current route reachable).
- Every cross-module link keeps the `view_functions` guard (CLAUDE.md blueprint rule).
- **New verify.py ratchet `sidebar-links`**: renders the sidebar per role in a request context,
  counts visible links, fails if any role exceeds its budget (25).

**Global header**: remove the LLM model selector (relocate to AI surfaces' Settings, driven by
the configured-provider registry — review finding "header contradicts actual AI config"). Keep:
search, notifications, org switcher, profile. One confirmation surface for login (kill the
duplicate banner+toast).

## 2. Screen system (shared components before screens)

New macros in `app/templates/macros/` (Jinja + tokens from DESIGN.md, no new colour families):

- `page_shell(title, subtitle, breadcrumb, actions, tabs)` — one row: h1 + context left,
  actions right; tabs beneath when present. No screen renders its own ad-hoc header again.
  Exactly one breadcrumb mount (kills the double-breadcrumb defect).
- `empty_state(icon, headline, body, cta_label, cta_href)` — the only sanctioned empty state.
- `stat_card(label, value, hint, variant)` — variants `hero` / `standard` / `compact`;
  value `None` renders `—`.
- `section_card(title, actions)` — standard content container.

Screens rebuilt on the system (order): Dashboard, AI Chat (wave 1) · Applications list,
Application detail, Capability Map, Solutions (wave 2) · ARB, EA Workflows (wave 3).

## 3. Dashboard — two explicit modes

Mode selection server-side from real counts (no client flicker):

- **Guided mode** (org has < 5 applications AND no capability mappings): replace health score,
  coverage bars, funnel, and viewpoint thumbnail with a setup journey card — "Import
  applications · Map capabilities · Invite your team" with real progress per step, each step
  linking to its surface. No red, no zeros presented as scores.
- **Data mode**: `page_shell` with persona tabs first · health score + coverage (kept — it is
  best-in-class when there is data) · only visualizations whose datasets are non-empty; a chart
  with all-zero rows collapses to one sentence ("Nothing past Vision yet — 70 solutions are in
  phase A"). The Layered Viewpoint preview renders as a clean generated image (no editor
  handles) or is omitted; "Open Composer" link remains.
- Welcome banner: one dismissible line, dismissal persisted server-side (per user, once ever).
  Workspace admin tiles: removed (duplicate the sidebar Admin zone).

## 4. AI Chat

- One header row: `[assistant ∨] [scope ∨]` merged segmented control · overflow menu (⋯) holding
  Docs / Match / Export / Approvals · Settings. Delete the "General Assistant / Multi-Domain AI
  Assistant" title block (the selector already says it).
- Conversation rail (Context/Query/Alerts/Chats) becomes a drawer: toggleable, auto-collapsed
  below 1280px, state remembered per user.
- Suggestion cards: CSS grid `minmax(240px, 1fr)`, max 2 rows then "More suggestions" —
  no clipped text at any width ≥1024.
- Composer: one chip row (≤4, overflow into the row scroll), send + upload right, disclaimer as
  one small line. The insight cards ("895 applications without business owner") stay — they are
  a strength — but respect the grid.
- Behavioural invariants preserved: keepalive/timeout contract, error bubbles (P0 wave).

## 5. Verification (per wave, before deploy)

- Screenshot matrix: rebuilt screens × {1024, 1280, 1440}, reviewed (by me) against this spec.
- `python scripts/verify.py --tag static` green; design-tokens ratchet stays 0; new
  `sidebar-links` ratchet green; a11y contrast entries for rebuilt pages removed from
  `tests/smoke/a11y_baseline.json` (target 0 for rebuilt screens).
- Full local suite (`--ignore=tests/smoke`) green; smoke tests updated in wave 3.
- Deploy per wave: merge → droplet checkout + `docker compose restart server` → authenticated
  session-harness sweep + production screenshots.

## 6. Waves

1. **Shell + Dashboard + AI Chat**: macros, role_access restructure, sidebar rewrite, header
   cleanup, sidebar-links gate, dashboard two modes, chat redesign.
2. **Library screens**: Applications list, Application detail, Capability Map, Solutions on the
   system; All-modules directory page.
3. **Governance + workflows + realignment**: ARB, EA Workflows, smoke-journey updates, a11y
   burn-down for rebuilt screens, remove dead nav entries from templates.

Out of scope: composer/journey canvases, mobile (<1024), new colour identity (tokens stay),
schema changes.
