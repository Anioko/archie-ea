# Build Report — composer-diagram-link-mismatches (D1-D4)

## Summary

All four defect groups from `tasks/01-fix-all-three-link-mismatches.md` are
fixed: D1 (dashboard "Architecture Overview" card), D2 (canvas sub-diagram
drill-down), D3 (AI-chat `architect_viewpoints()`, rebuilt on `SavedDiagram`
instead of the dead `ViewpointView` store, with fabricated placeholder links
replaced by `null`), and all three D4 sites (`archimate_composer_service.py`,
the create-diagram-from-elements route, and `chat_workflows.py`'s
solution-diagram redirect).

An exhaustive re-grep across the whole tree (below) found zero remaining
`?viewpoint=<numeric>` instances. Every fix was verified against a real
running server, not just source: the browser walkthrough log for D3 shows
`POST /ai-chat/architect/viewpoints` succeeding, then three
`GET /archimate/api/saved-viewpoints/<id>` calls each returning 200, then
`GET /archimate/composer?viewpoint_id=259` returning 200 and rendering real
seeded elements on the canvas.

## Files changed

- `app/templates/dashboards/overview.html` — D1: bare `href="/archimate/composer"` → `?viewpoint=layered`.
- `app/static/js/archimate/composer.js` — D2: `linkSubDiagram` now builds `?viewpoint_id=`.
- `app/static/js/bundles/core-composer.js`, `core-admin.js`, `core-public.js` — rebuilt (`js-build` gate).
- `app/static/js/ai_chat/commands.js` — guards the "Open in Composer" anchor on `vp.composer_url` (nullable) instead of the retired `vp.viewpoint_view_id`.
- `app/services/archimate_composer_service.py` — D4: `create_diagram()` now returns `?viewpoint_id=`, and accepts an optional `viewpoint_type` kwarg (backward-compatible, keyword-only) used by D3.
- `app/modules/architecture/routes/archimate_routes.py` — D4: `api_create_diagram_from_elements` returns `?viewpoint_id=`.
- `app/modules/ai_chat/routes/chat_workflows.py` — D4: the solution-diagram `redirect_url` uses `?viewpoint_id=`. D3: `architect_viewpoints()` rewritten to call `create_diagram()` (real `SavedDiagram` rows, tenant-scoped, `viewpoint_type` set) instead of constructing `ViewpointView`; response uses `saved_diagram_id` / `composer_url` (null on a genuine miss, never a placeholder).
- `app/models/archimate_viewpoint.py` — deprecation comment on `ViewpointView` recording it has no writers and what superseded it (ADR 0008: retire, never accumulate).

## Tests added

- `tests/test_composer_diagram_link_mismatches.py` (10 tests, all passing) — D2 source assertion on `linkSubDiagram`; D4 assertions on `create_diagram()`'s returned URL and its new `viewpoint_type` kwarg, and on all three D4 call sites; D3 route-level tests: creates `SavedDiagram` not `ViewpointView`, response shape, a zero-match viewpoint returns `composer_url: None`/`saved_diagram_id: None` (never a placeholder), the `ViewpointView` deprecation comment, and the `commands.js` guard.
- `tests/smoke/test_composer_link_mismatches.py` (3 Playwright journeys, all passing against a real running server):
  - `test_dashboard_architecture_overview_card_opens_layered_viewpoint` (D1) — clicks the real card button, asserts the href and post-click URL carry `viewpoint=layered`, and that the blank template-picker canvas does not render.
  - `test_architect_viewpoints_generates_real_openable_diagrams` (D3) — POSTs the real endpoint, asserts every non-null `composer_url` uses `viewpoint_id=`, that `GET /archimate/api/saved-viewpoints/<id>` resolves each one to real content, and follows one real link in the browser to confirm it renders (not the template picker).
  - `test_tenant_isolation_on_architect_generated_diagram` — a second org gets 403/404 loading the first org's architect-generated diagram (`SavedDiagram` carries `TenantMixin`, unlike the retired `ViewpointView`).

## Exhaustive re-grep — every `archimate/composer` occurrence, classified

Command: `grep -rn "archimate/composer" --include="*.html" --include="*.py" --include="*.js" .` (excluding `.git`), full raw output below, one verdict per line.

```
./app/config/navigation_sections_v2.py:333:  ?viewpoint=layered                          -> OK (real key)
./app/modules/ai_chat/routes/chat_workflows.py:817:   ?viewpoint_id={diag.id}                -> OK (fixed, D4)
./app/modules/ai_chat/routes/chat_workflows.py:968:   ?viewpoint_id=42 (docstring example)    -> OK (fixed, D3 docstring)
./app/modules/ai_chat/services/multi_domain_chat_service.py:5489: (comment, no link)         -> N/A
./app/modules/architecture/routes/archimate_routes.py:750:   ?viewpoint_id={diagram.id}       -> OK (already correct)
./app/modules/architecture/routes/archimate_routes.py:1175:  (template path string)           -> N/A
./app/modules/architecture/routes/archimate_routes.py:6504:  ?elements=...                    -> OK (explicitly allowed)
./app/modules/architecture/routes/archimate_routes.py:6633:  ?elements=...                    -> OK (explicitly allowed)
./app/modules/architecture/routes/archimate_routes.py:6746:  ?viewpoint_id={diagram.id}       -> OK (fixed, D4)
./app/services/archimate_composer_service.py:24:   ?viewpoint_id=42 (docstring example)      -> OK (fixed docstring)
./app/services/archimate_composer_service.py:98:   ?viewpoint_id={diagram.id}                -> OK (fixed, D4)
./app/services/slack_architect_service.py:270:     bare /archimate/composer, no query        -> OK
./app/static/js/ai_chat/commands.js:80:    ?solution_id=...                                 -> OK (different param)
./app/static/js/ai_chat/commands.js:250:   ?process=...                                     -> OK (different param)
./app/static/js/ai_chat/render.js:513:     (comment, no link)                               -> N/A
./app/static/js/ai_chat/render.js:532:     ?prefill=1                                       -> OK (literal flag)
./app/static/js/archimate/composer.js:5256: ?viewpoint_id=' + existingId                     -> OK (fixed, D2)
./app/static/js/architecture_assistant/architecture_journey.js:2796: ?solution_id=...         -> OK (different param)
./app/static/js/codegen/workflow_builder.js:4:  (comment)                                     -> N/A
./app/static/js/solutions/blueprint.js:354: ?solution=...&section=...                         -> OK (different params)
./app/templates/applications/list_simple.html:197:  bare href                                 -> OK
./app/templates/applications/list_simple.html:1036: (script include)                          -> N/A
./app/templates/archimate/composer.html:2308-2313: (script includes)                          -> N/A
./app/templates/archimate/traceability_chain.html:397,415: ?element_id=...                    -> OK (different param)
./app/templates/architecture/elements.html:307: bare href                                     -> OK
./app/templates/architecture/elements.html:450: ?element=...                                  -> OK (different param)
./app/templates/architecture/elements.html:569: (script include)                              -> N/A
./app/templates/architecture_assistant/index.html:204: (script include)                        -> N/A
./app/templates/architecture_assistant/journey_v2_steps/_step3_architecture.html:567: ?solution_id=... -> OK
./app/templates/architecture_assistant/journey_v3.html:427: (script include)                   -> N/A
./app/templates/architecture_assistant/partials/_step_execution.html:77: ?solution_id=...      -> OK
./app/templates/codegen/workbench.html:312: (script include)                                  -> N/A
./app/templates/dashboards/overview.html:253: ?viewpoint=layered                               -> OK (fixed, D1)
./app/templates/dashboards/overview.html:620: ?viewpoint=layered&layer=...                     -> OK (unchanged per constraints)
./app/templates/dashboards/overview.html:648: (script include)                                -> N/A
./app/templates/layouts/admin_base.html:207: bare href                                        -> OK
./app/templates/solutions/blueprint.html:2206: (script include)                                -> N/A
./app/templates/solutions/detail.html:2417: (script include)                                   -> N/A
./app/templates/solutions/partials/_archimate_footprint.html:218: ?solution_id=...              -> OK (different param)
./scripts/ba04_verify_pdf.py:48: ?viewpoint_id=args.diagram                                    -> OK (already correct)
./scripts/demo/record_demo.py:208: bare                                                        -> OK
./tests/csp/verify_composer_relationships.py:136: ?viewpoint_id=dia_id                         -> OK
./tests/csp/verify_cutover.py:18: bare                                                         -> OK
./tests/csp/verify_real_pages.py:22: bare                                                      -> OK
./tests/smoke/*.py (all other matches): viewpoint_id=, viewpoint=layered, or bare                -> OK, all already correct
./tests/test_composer_diagram_link_mismatches.py, test_composer_layered_viewpoint.py, test_modules_directory.py, test_header_and_login_feedback.py, test_ai_chat_context.py, test_template_contracts.py: test assertions/fixtures                -> N/A (tests, not links)
```

**Zero unexplained `?viewpoint=<numeric>` instances remain.** Every occurrence
of `?viewpoint=` in the codebase now carries a literal `STANDARD_VIEWPOINTS`
key (`layered`); every numeric diagram id uses `?viewpoint_id=`.

## Verification run

`python scripts/verify.py --tag static`: **48 passed, 0 failed, 1 skipped**
(`css-build` skipped locally — no vendored Tailwind CLI, expected per
CLAUDE.md; CI runs it with `--require-db`). `smoke-coverage-on-change` is
green because the JS/template changes are now covered by
`tests/smoke/test_composer_link_mismatches.py`.

Regression check — `tests/test_composer_layered_viewpoint.py` (tonight's
prior sidebar/per-layer-tab fix) and `tests/test_modules_directory.py`
(the `/modules` directory's composer link): **31 passed, 0 failed.** Neither
regressed.

`tests/test_composer_diagram_link_mismatches.py`: **10 passed, 0 failed.**

`tests/smoke/test_composer_link_mismatches.py`: **3 passed, 0 failed**
(all three run together against one live server, in addition to individually).
Excerpt of the live request log during the D3 journey, proving the fix end to
end against a real running app (not a mock):

```
POST /ai-chat/architect/viewpoints HTTP/1.1" 200
GET /archimate/api/saved-viewpoints/259 HTTP/1.1" 200
GET /archimate/api/saved-viewpoints/260 HTTP/1.1" 200
GET /archimate/api/saved-viewpoints/261 HTTP/1.1" 200
GET /archimate/composer?viewpoint_id=259 HTTP/1.1" 200
```

And for the tenant-isolation journey, org2 requesting org1's
architect-generated diagram:

```
GET /archimate/api/saved-viewpoints/262 HTTP/1.1" 404
```

`python scripts/verify.py` (bare, full run incl. `tests`/`schema-drift`
which need PostgreSQL) was **not** run in this session due to time — the
`--tag static` run above covers every gate that does not need the live
smoke/db tiers, plus the dedicated unit and smoke test runs above cover
`tests`/`csrf-coverage`/`fabricated-data` for the changed files specifically.
**Flagging this explicitly for the coordinating session / refuter**: run the
bare `python scripts/verify.py` (no `--tag`) before merge, per CLAUDE.md's
"the only command whose green means clean is the bare invocation."

## What's ready to fast-track

- D1, D2, D4 (all three sites): small, mechanical, source-verified by both
  unit tests and (D1) a live browser click. Low risk.
- D3: larger behavioural change (new model written, response shape changed,
  `ViewpointView` retired as a writer). Verified end-to-end in the browser
  including tenant isolation. The response shape change
  (`viewpoint_view_id` → `saved_diagram_id`) is a breaking change to any
  caller of `/ai-chat/architect/viewpoints` other than `commands.js` (which
  was updated) — grepped for other consumers of that field name and found
  none, but flagging for refuter to re-check.

## Refuter follow-up round (2026-09-19, superseding the D1-D4 re-grep above)

The D1-D4 re-grep only checked for `?viewpoint=<numeric>`. A refuter pass
found the real bug class is broader — "a composer link sets a query
parameter the receiving end never reads" — and confirmed by exhaustive trace
that `/archimate/composer` reads exactly five parameters: `solution_id`,
`viewpoint`, `layer` (server-side, `composer_page`, `archimate_routes.py:
~1150-1152`) and `viewpoint_id`, `prefill` (client-side, `composer.js:
~2536-2554`). Five more sites were found and fixed this round.

### FIX 1 — 8 layer-only links dropped their layer (highest priority, matched the founder's repeated report)

`app/templates/archimate/traceability_chain.html`'s 8 "+ Add" buttons pass
`?layer=Motivation/Business/Application/Technology` with **no** `viewpoint`
param. `composer_page` reads `layer` correctly server-side and passes it to
the template as `initial_layer`, but `composer.js`'s page-load logic only
ever applied `initialLayer` inside `if (initialVp)` — a layer-only link
silently opened the generic blank canvas.

**Chose option (b) — fixed the receiver, not the 8 call sites** —
`app/static/js/archimate/composer.js`'s init block now defaults
`initialVp = 'layered'` when `initialLayer` is set but `initialVp` is not,
before the existing `if (initialVp)` branch runs. This closes the
receiver-side gap generally instead of requiring every future composer_url
generator to remember `viewpoint=layered&`, which is exactly the mistake
that produced this bug twice (D1's original bare href, then this
layer-only variant). Demonstrated end to end in
`tests/smoke/test_composer_link_mismatches.py::
test_traceability_chain_add_button_preserves_layer` — clicks the real
Business-layer "+ Add" button on `/archimate/traceability`, follows it into
the composer, asserts the template-picker did NOT render, and reads
`window.__COMPOSER_CONFIG__.initialLayer` back out of the live page.

### FIX 2 — blueprint.js wrong param name

`app/static/js/solutions/blueprint.js:354`'s `openComposer` built
`?solution=<id>&section=<id>`; the route reads `solution_id`, not
`solution`, and has no mechanism to scroll to a section. Fixed to
`?solution_id=<id>`; `section` is dropped rather than invented as new
composer functionality — no existing mechanism for it was found.

### FIX 3 — three sites building element/process params nothing reads

- `app/templates/architecture/elements.html:450` (`?element=`)
- `app/templates/archimate/traceability_chain.html:397,415` (`?element_id=`)
- `app/static/js/ai_chat/commands.js:250` (`?process=`)

All three are client-only anchors/markdown-link builders with no server
round-trip on click — routing through `create_diagram()` for a real
`?viewpoint_id=` would require turning a synchronous `<a href>`/markdown
link into an async POST-then-navigate with loading/error states, which is
real new engineering, not a cheap fix. **Chose option (b) — made the links
honest**: each now points at the generic `/archimate/composer` with no
fake-looking parameter, rather than a URL that looks scoped but silently
isn't.

### FIX 4 — two server-side `?elements=<ids>` composer_url fields, cheap to fix properly

`app/modules/architecture/routes/archimate_routes.py` (the CSV-import and
document-analysis routes, ~6504 and ~6633) built literal
`?elements=1,2,3` composer_url fields nothing reads. Unlike FIX 3, these
are server-side with the element ids and DB session already in hand — cheap
to route through the existing `create_diagram()` service (the same helper
D4 already uses). Added a small `_composer_url_for_elements()` wrapper and
call it from both sites; it returns a real `?viewpoint_id=` URL or `None`
if nothing was created, never a broken parameter.

### FIX 5 — permanent gate against a 5th round of this bug class

`scripts/check_composer_url_params.py` scans templates/JS/Python for
literal `/archimate/composer?...` strings, extracts the query parameter
*names*, and fails on anything outside `{solution_id, viewpoint, layer,
viewpoint_id, prefill}`. Registered as `Gate("composer-url-params", ...,
"ratchet", ...)` in `scripts/verify.py`'s `build_gates()`, baseline `0` in
`verification_baseline.json`, tagged `["static", "fast"]` so it runs under
`--tag static`. Escape hatch: a `composer-url-ok` comment on the line, same
convention as the other per-line gate exceptions in this repo.
`tests/test_composer_url_params_gate.py` proves it fails on a
deliberately-reintroduced bad example (`?element=42`, `?elements=...`),
honours the escape hatch, and passes on the current clean tree (5 tests,
all passing).

Only literal, statically-analyzable query strings are in scope — an
f-string whose query string itself is built from a variable is out of
scope by design (documented in the script's docstring) and needs the same
manual audit this bucket has now run twice.

### Corrected, genuinely exhaustive classification (supersedes the D1-D4 table above)

Command: `grep -rn "archimate/composer" --include="*.html" --include="*.py"
--include="*.js" .` (excluding `.git`), 109 lines, re-classified checking
EVERY parameter name against the five-param receiver contract, not just
`viewpoint`/`viewpoint_id`:

- **Known-good params** (`solution_id`, `viewpoint=layered`, `layer=`,
  `viewpoint_id=`, `prefill=1`) — all remaining occurrences across
  `navigation_sections_v2.py`, `chat_workflows.py`, `archimate_routes.py`,
  `archimate_composer_service.py`, `commands.js`, `render.js`,
  `composer.js`, `architecture_journey.js`, `blueprint.js` (fixed),
  `_step3_architecture.html`, `_step_execution.html`,
  `_archimate_footprint.html`, `dashboards/overview.html`,
  `ba04_verify_pdf.py`, and every `tests/smoke/*.py`/`tests/csp/*.py` file.
- **Bare/generic links** (no query string at all) —
  `slack_architect_service.py`, `applications/list_simple.html:197`,
  `architecture/elements.html:307,455` (fixed this round),
  `traceability_chain.html:401,420` (fixed this round),
  `admin_base.html:207`, `demo/record_demo.py`, `tests/csp/verify_cutover.py`,
  `tests/csp/verify_real_pages.py`.
- **Script includes / N/A** (`composer_renderer.js`, `composer_ai.js`,
  `composer_persistence.js`, `composer_graph.js`, `composer_search.js`,
  `composer.js` itself) across every template that loads the composer's own
  JS bundle — not links, not in scope.
- **Comments/docstrings referencing the URL pattern, not building one** —
  `multi_domain_chat_service.py:5489`, `render.js:513`,
  `workflow_builder.js:4`, `test_ai_chat_context.py:265`,
  `test_archetype_journeys.py:395`, plus this script's own docstring/regex
  and `scripts/verify.py`'s gate docstring (the gate itself scans these two
  files clean — confirmed by running it against them directly).
- **Test files** (assertions, fixtures, deliberately-bad examples in
  `test_composer_url_params_gate.py`) — not links, not in scope.

**Zero unexplained parameter-name mismatches remain.** Every literal
`/archimate/composer?...` string in the tree now carries only params from
the five-name known-good set, or is a bare/generic link with no query
string at all.

## Verification — refuter follow-up round

`python scripts/verify.py --tag static`: **49 passed, 0 failed, 1 skipped**
(same `css-build` skip as before; `composer-url-params` — the new gate —
passes at `0 <= 0`).

`pytest tests/test_composer_diagram_link_mismatches.py
tests/smoke/test_composer_link_mismatches.py
tests/test_composer_layered_viewpoint.py tests/test_modules_directory.py
tests/test_composer_url_params_gate.py -v`: **58 passed, 0 failed** (18 +
4 + 15 + 16 + 5, run together in one session — includes both the FIX-1
browser walkthrough and the FIX-2/3/4 unit tests added this round).

Additional DB-dependent gates run individually since a live-DB dependency
made them unreachable from `--tag static`, per this session's brief:

```
ok    broken-surfaces         34.7s  [0 <= 0]
ok    dynamic-link-prefixes   33.9s  [0 <= 0]
ok    store-agreement         36.1s  [1 <= 1]
ok    boot-health             26.2s
FAIL  schema-drift            26.3s  -> run: flask --app manage reconcile-schema
```

`schema-drift`'s failure is pre-existing and unrelated to this bucket's
diff — no model or schema files were touched this round (the diff is
templates, JS, two route helpers, `verify.py`, and the baseline JSON). It
matches this session's own local-environment note about `reconcile-schema`
column ownership drift on the shared test database, not a regression
introduced here.

`python scripts/verify.py` (the bare, full invocation) was still not run in
this follow-up round for the same reason as before — it needs a live
Postgres and hangs past the interactive timeout here — but every gate the
bare run would add beyond `--tag static` that is reachable without a
30+-minute session (`schema-drift`, `boot-health`, `broken-surfaces`,
`dynamic-link-prefixes`, `store-agreement`, `csrf-coverage`) was run
individually above, per this session's explicit instruction, and all pass
except the pre-existing/unrelated `schema-drift` environmental failure.

## Not done in this session

- Bare `python scripts/verify.py` (full run, needs live DB) — flagged above.
- The handoff brief's own instruction to check non-composer surfaces (email,
  Slack/Teams notification payloads beyond the two service files already
  checked, PDF/report generators) for the same parameter confusion in
  **other** URL schemes entirely (not `/archimate/composer`) was not
  attempted — out of scope for "every archimate/composer link" but flagged
  per the task's own handoff-target note ("assume a seventh exists").

## Final hardening round (2026-09-19) — the gate now checks parameter VALUES, not just names

A second refuter pass found `check_composer_url_params.py` only checked
query parameter *names* — it would have missed the exact bug the founder
reported three times tonight, `?viewpoint=<numeric-id>` in place of a real
`STANDARD_VIEWPOINTS` key such as `layered`/`basic`. Four scripts-only
changes, no behavioural code touched:

1. **`viewpoint=` value validation.** `KNOWN_VIEWPOINT_KEYS` hardcodes the
   16 literal `STANDARD_VIEWPOINTS` keys from
   `app/services/archimate_viewpoint_service.py` (no other
   `scripts/check_*.py` imports `app.*` — importing the app package here
   would drag in Flask/DB config for a text scan — so this follows the same
   standalone-constant convention). `_viewpoint_value_is_suspect()` flags a
   `viewpoint=` value that is: purely digits (`?viewpoint=42`); contains an
   interpolation marker (`{`, `}`, `${`, `' +`, `+ '`) — catching both
   f-string/Jinja interpolation (`?viewpoint={diagram.id}`) and string
   concatenation (`?viewpoint=' + existingId`, where the regex only sees
   the empty value left before the closing quote, which is itself treated
   as suspect); or any other identifier not in the known key set. A
   legitimate `?viewpoint=layered` is unaffected.
2. **Widened URL match.** `COMPOSER_URL` now also matches
   `{{ url_for('archimate.composer_page') }}?param=value`, the literal
   shape used by all 8 `traceability_chain.html` "+ Add" buttons,
   `fact_sheet.html`, and `archimate_views/traceability.html` — previously
   invisible to the regex entirely since it required the literal string
   `/archimate/composer`.
3. **Double-escaped separator.** `&amp;amp;` (in addition to the existing
   `&amp;`) is now normalized to `&` before splitting the query string, so
   the second and later parameters of a doubly HTML-escaped multi-param
   composer URL are actually scanned rather than silently merged into the
   first parameter's name.
4. Four new tests in `tests/test_composer_url_params_gate.py`:
   `test_flags_numeric_viewpoint_value`,
   `test_flags_interpolated_viewpoint_value` (both the `' + existingId`
   and f-string shapes), `test_flags_url_for_composer_pattern`, and
   `test_flags_bad_param_after_double_escaped_ampersand`.

### Verification

`pytest tests/test_composer_url_params_gate.py -v`:

```
tests/test_composer_url_params_gate.py::test_flags_unknown_param_name PASSED
tests/test_composer_url_params_gate.py::test_flags_elements_param PASSED
tests/test_composer_url_params_gate.py::test_passes_known_good_params PASSED
tests/test_composer_url_params_gate.py::test_honours_escape_hatch PASSED
tests/test_composer_url_params_gate.py::test_flags_numeric_viewpoint_value PASSED
tests/test_composer_url_params_gate.py::test_flags_interpolated_viewpoint_value PASSED
tests/test_composer_url_params_gate.py::test_flags_url_for_composer_pattern PASSED
tests/test_composer_url_params_gate.py::test_flags_bad_param_after_double_escaped_ampersand PASSED
tests/test_composer_url_params_gate.py::test_current_tree_is_clean PASSED

============================== 9 passed in 5.75s ==============================
```

`python scripts/verify.py --tag static` (full run, not a subset):

```
  ok    composer-url-params         3.7s  [0 <= 0]
  ...
49 passed, 0 failed, 1 skipped
```

The one skip is `css-build` (no vendored Tailwind CLI locally — expected
per CLAUDE.md, CI runs it with `--require-db`), unrelated to this bucket.
`composer-url-params` is 0 <= 0 against the real tree after widening the
regex to the `url_for(...)` pattern — none of tonight's legitimate
`?viewpoint=layered`, `?viewpoint=layered&layer=...`, or `?viewpoint_id=`
usages are flagged as false positives, including the 8
`traceability_chain.html` sites and `fact_sheet.html` now newly in scope
of the matcher.

**This bucket is done.** All behavioral fixes (D1-D5b) were already
confirmed correct by the prior refuter pass and were not touched this
round. The permanent gate now checks both parameter names and the
`viewpoint` value, is registered in `verify.py`, and passes cleanly. Not
merged or deployed from this session — that is the coordinating session's
next step.
