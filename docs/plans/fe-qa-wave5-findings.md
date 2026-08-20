# Frontend QA waves 5+6 — audit findings & remaining backlog

## Fixed in wave 6 (e97f786, deploy-20260813-fe-qa-wave6)

- P0 stored XSS in ai_chat/panels.js (entity names/descriptions into innerHTML
  unescaped) — now Platform.sanitize.escape everywhere.
- 22 sweep-confirmed 500 routes → 404/empty-200/503 (18 were get_or_404
  swallowed by broad except). Pinned by tests/test_route_sweep_fixes.py.
- 4 bare int()/float() write-handlers → field-named 400s; billing upgrade's
  silent-failure redirect now flashes. Pinned by tests/test_input_validation_400.py.
- 3 per-keystroke searches (vendor_catalog, apqc_browser,
  process_suggestion_modal) → 300ms debounce + AbortController.
- design-tokens gate now scans app/modules/*/templates; the 132 banned-colour
  uses that hid there are migrated; 539 more on-tint badge combos moved to
  -emphasis across 227 templates.
- Route sweep harness works now: tests/test_route_sweep_scratch.py (untracked)
  against TEST_DATABASE_URL=…5439/flask_test (run reconcile-schema on that DB
  first; the Postgres is Spanish-locale, so a missing DB shows as
  UnicodeDecodeError). 1,720 routes tested; remaining 5xx are by-design
  501/503s and 3 binary-download false positives.


Audit date: 13 Aug 2026. Fleet: 6 read-only auditors over the deployed commit
(`deploy-20260813-w4-phaseB` @ d1b50d7). Fixed-and-deployed in
`deploy-20260813-fe-qa-wave5` @ 67711f1; everything below is what remains.

IMPORTANT: the local `fix/design-review-p0-wave` branch is 99 commits BEHIND
production. Base all new work on the droplet's deployed branch (see the
prod-deploy memory: proxy-jump to 10.106.0.6, remote `deployfork`).

## Fixed in wave 5 (67711f1)

1. P0 `window.modalManager` did not exist — every modal action in review_queue,
   solutions/detail, roadmap_builder, duplicate_detection, vendor_catalog,
   import_history threw TypeError. Object shim added in `app/static/js/ui/modal.js`.
2. P0 CSRF: 601 raw mutating `fetch()` sites, many without X-CSRFToken →
   400 "dead button" under global CSRFProtect. Same-origin injection safety net
   added in `app/static/js/core/03-fetch.js`.
3. A11y AA contrast: `--muted-foreground` 46.9%→45% (~498 bg-muted chips);
   new `--success-emphasis`; emphasis swaps on capability_map, dashboards/overview,
   applications/list_simple; full token migration of procurement/compliance_dashboard.

## Remaining backlog (counts from the audit scanners in the 13 Aug session scratchpad)

### P1
- **~463 bare `text-destructive`** small-text uses (3.76:1 on white). Swap to
  `text-destructive-emphasis` where the text is < 18.66px bold. Only the three
  audited pages were fixed. Same for bare `text-warning` (~2.1:1) outside
  capability_map, and `text-success` on tints (207 co-occurrences, token now exists).
- ~~235 loops with no empty state~~ **CORRECTED (wave 8): the 235 figure was
  heavily inflated** — most flagged loops sit inside `{% if %}` wrappers that
  already carry an empty state one level up, invisible to the line-level
  scanner. The 8 worst files contained only 4 real gaps, fixed in 9838e5c.
  Treat remaining EmptyState rows in findings.csv as leads needing the same
  wrapper check, not as a count.
- **Non-banned raw colours: true count is 4,552** (the audit's 404 undercounted;
  wave 9 measured all families/utilities). Now frozen by the
  `design-tokens-extended` ratchet gate (verification_baseline.json:
  design_tokens_extended). Burn down by file — worst: codegen/_wb_ide.html
  (291), codegen/_wb_right_panel.html (240), applications/rationalization.html
  (171), solutions/detail.html (152). Lower the baseline after each cleanup.
- ~~175 heading-hierarchy violations~~ **CORRECTED (wave 9): false positives.**
  Every audited admin page gets its h1 from the shared page_header() macro and
  card titles use the site-wide card_title() h3 convention; axe (heading-order
  rule included) passes clean. If h1->h3 card titles are ever judged an issue,
  fix once in components/card.html, not per-template.
- **Migrate the 601 raw fetch() sites to `Platform.fetch`** (the safety net makes
  them work; the wrapper also gives error toasts + loading states for free).

### P2
- ~~375 loading states~~ **RE-REVALIDATED (wave 11): mostly not a defect.**
  The wave-10 "72 with no affordance" figure was still trigger-blind: all 8
  sampled admin/integration templates are server-rendered with CLICK-triggered
  fetches only — no on-load gap exists, and their buttons already disable
  in-flight. The real category is "on-load fetch + no affordance", which needs
  a trigger-aware scan (DOMContentLoaded/init()/Alpine init) before any fixing.
  154 unpaginated tables equally unvalidated — same check required first.
- 163 inline style attributes; 35 hardcoded #fff/#000 (2 P1 dark-canvas cases:
  capability_map/network.html:21, capability_roadmap/capability_roadmap.html:47).
- 6 hardcoded currency symbols (admin/billing.html £-prices may be legit plan
  copy — check with product before "fixing").
- Static assets served `Cache-Control: max-age=0` (Flask default) — consider
  SEND_FILE_MAX_AGE + fingerprinted asset URLs (manifest.json already exists).
- ~~Favicon returns an empty 204~~ DONE (wave 9): brand-mark favicon.svg via partials/_head.html.

### Audits that did not complete (session limit) — rerun their scanners
- **Route 500 sweep**: `scratchpad/sweep.py` + `test_sweep.py` were written but
  results never landed. Rerun against TEST_DATABASE_URL=…5439/archie_test.
- **Forms audit**: `scan_forms2.py` + `raw_fetch_results.json` (601 sites,
  per-site CSRF flags) exist; per-route server-side-validation pass never ran.
- **JS logic audit** (races, double-submit, envelope bugs): its sub-fleet died
  mid-flight; one confirmed finding (modalManager) is fixed, the rest unknown.
- ~~Playwright a11y re-baseline~~ DONE (wave 8, 9838e5c):
  `a11y_baseline.json` is now EMPTY — zero accepted WCAG violations across all
  8 audited pages, /ai-chat included.

## Product decision needed: dark mode is dormant (found 14 Aug, wave 8 audit)

`shadcn_tokens.css` ships a complete `.dark` palette and templates carry
hundreds of `dark:` variants — but no main layout ever applies the class or
reads `prefers-color-scheme`; only `composer_base.html` does. Users cannot get
dark mode anywhere else, so the "35 hardcoded #fff/#000" findings are dormant
there too. Shipping it = add a toggle + honor prefers-color-scheme in
base/admin_base + a dedicated dark visual QA wave. Do not flip it on casually.

## Colour burn-down trajectory (14 Aug, waves 9-22)

COMPLETE (wave 25): 4552 -> 12 in one day, across 17 burn-down waves.
The 12 remaining are instance_detail.html's layer_colors {% set %} dict
(inline markers syntactically impossible; documented adjacent). Every
other raw colour is migrated or carries a reasoned design-tokens-ok
marker. The ratchet holds the floor at 12. Conventions
established: purple = AI-generated indicator; data-viz scales (heatmaps,
Sankey, 5x5 risk grids) stay raw; RAG scales beyond 3 tiers stay raw;
ArchiMate layer legends align to DESIGN.md's table; token-on-token
hovers become opacity shifts.

## Scanner scope gap (wave 24): JS assets

check_design_tokens.py reads only templates. app/static/js/components/
risk_heatmap.js (and possibly other JS) builds class strings with raw
colours including banned-family ones (dark:bg-red-900). A future wave
should extend the scanner to app/static/js/**/*.js class-string literals
or sweep them once manually.

## Product decision needed: 5,300 lines of orphaned solutions JS (wave 26)

app/static/js/solutions/detail.js (3,433 lines, registers Alpine component
solutionDetail), detail-phase-crud.js, detail-phase-e.js, detail-ai.js and
session_detail.js are loaded by NO template. The live /solutions/<id> page is
blueprint.html (inline components); twelve partials' header comments still
claim they run "within solutionDetail() x-data scope" - that component never
instantiates. Decide: delete the five files + fix the partial comments, or
restore includes and reconcile with the inline components. Do not guess -
either direction changes real behavior contracts.
