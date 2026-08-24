# Task 11 report — Transformation Room experience

## Status

DONE_WITH_CONCERNS

The approved Transformation Room UI is implemented over the persisted Task 1–7 domain. The create → redirect 404 is removed, canonical transformation programmes are visible from the portfolio, and every approved room URL is stable and tenant-safe. Task 8 typed ARB and Task 9 execution/outcome materialisation remain explicitly unavailable; the UI does not manufacture readiness, actions, dates, confidence, progress or outcome actuals.

## Delivered

- Registered stable server-rendered room routes for programme overview, workstreams, every stage deep link, governance and roadmap inside the established `solution_design` URL space.
- Redirected the canonical `record_kind=transformation_programme` root to its overview while leaving legacy `initiative_type` records on the existing technology cockpit.
- Broadened the programme portfolio query to include canonical records, linked those records to the room, and retained legacy records safely.
- Removed the duplicate legacy creation modal, its Alpine component and the competing CTA. The portfolio now has one creation path through the approved business-first wizard.
- Added tenant-scoped read projections for programme/workstream context and persisted objective, discovery, evidence, option and decision-brief resources.
- Added one consistent breadcrumb hierarchy, intent navigation, a directly addressable stage rail and a complete programme header: objective, lifecycle, owner, next action, evidence posture and expected outcome.
- Added an objective form whose mutation delegates to `TransformationProgrammeService.update_objective`; it validates that the URL programme owns the workstream before mutation and uses optimistic revision plus an idempotency key.
- Rendered Decision, Execute, Outcomes, Governance and Roadmap as inspectable but explicitly “Not available in this release”. Persisted Task 7 decision briefs may be read, but no typed ARB or Task 9 behavior is implied.
- Kept non-technology programmes free of target-platform, clean-core and technology-solution claims.
- Made the owner search an ARIA combobox with active-descendant semantics, arrow-key movement, Enter selection, Escape close and stale hidden-ID clearing. Responsive layouts use the existing token/component contract.
- Added a separate Chief Architect transformation posture from canonical programme records. Unlike measures retain their own nullable value and reason; solution conformance remains separately named.
- Did not add an Architecture Journey handoff because no safe persisted programme-link contract exists in the approved Task 1–7 surface.

## Test-first evidence

The initial focused run produced the intended red state: 6 failures and 3 passes. Failures covered the canonical root redirect, canonical list visibility/link, objective route, stable room URLs and owner combobox accessibility. Production implementation followed that red run.

Final evidence:

- `pytest -q` over the 12 relevant Task 1–7 transformation suites plus the new route/template tests: **288 passed** in 341.16 seconds.
- Focused Task 11 route/template suite: **10 passed** in 41.22 seconds.
- Final Chief Architect posture regression after review refinement: **1 passed**.
- Scoped Ruff check over changed Python and tests: **passed**.
- `git diff --check`: **passed**.
- Verification gates `template-syntax`, `template-references`, `fabricated-data`, `design-tokens`, and `boot-health`: **all passed, no skips**.
- `python scripts/build_css.py --check`: **passed**; committed CSS is current.

## Self-review

- Tenant membership is repeated in every new read query; foreign programme/workstream IDs resolve to 404.
- The objective POST proves programme/workstream ownership before invoking the mutation service.
- Later-stage route POSTs are rejected, and their GET views contain no fake actions or metrics.
- Null values render as an em dash with an adjacent unavailable/empty reason where one exists.
- Option and decision version integrity is verified using the existing domain services; evidence checksum presence is not mislabelled as whole-record verification.
- Cross-domain dependency posture counts persisted dependency entries. Decision ageing, delivery confidence and outcome variance stay null with exact reasons.
- No new public-CDN asset, custom colour, console logging, native alert/confirm or direct command-service mutation was introduced.
- `requirements-test.txt` was already modified outside this task and was not touched or staged.

## Concern

The new Playwright smoke test collected both 390px and 1024px cases, but the shared live-server harness returned no result for several minutes and the execution session ended before a pass/fail result was produced. This is not counted as a pass. The equivalent server-rendered accessibility/responsive contracts are covered by the green template tests, and boot/template/CSS gates are green, but browser-level evidence remains unavailable from this run.

## Review fix round 1/5 — 24 August 2026

All ten Important findings and the related Minor findings were addressed:

- The legacy technology-first `POST /solutions/programmes` is retired with an explicit 410 response and canonical wizard URL; it cannot create a bypass record.
- Evidence, option versions and decision-brief versions are checksum-verified on read. A compromised set is suppressed and rendered as an explicit integrity-unavailable state.
- Cross-domain dependencies are now null with the honest explanation that persisted dependencies are not classified by transformation domain.
- The canonical blocker `next_action_url` is rendered when it is a safe Transformation Room URL.
- Technology workstreams alone explain that Solution/platform/vendor elaboration happens after programme approval; the wizard does not collect fields the canonical intake would discard.
- Enterprise Architect and CTO navigation exposes Transformation programmes. The EA's duplicate ArchiMate Elements destination was retired so the sidebar ratchet remains at 26.
- Resource projections distinguish available, empty, failed and unknown states. Synchronous server rendering has no transient client-side loading phase, so no fabricated loading state is emitted.
- The smoke journey now performs real create-to-objective submission, stable deep-link refresh, keyboard combobox/focus interaction, later-stage honesty, a server error response, and axe checks at mobile and desktop widths. Converting it to the async Playwright API resolved the repository fixture's sync-in-async-loop failure and exposed three real defects: a duplicated owner input binding, handler expressions that did not invoke keyboard functions, and a submit expression that did not invoke submission. All three are fixed.
- Central card, metric and empty-state macros replace compatible hand-built structures.
- Stage navigation consumes `TransformationGateService.NEXT_STAGE`; links use `url_for` and expose `aria-current`.

The 772-line read-model split is deferred because this review changed cohesive projection/integrity behavior and the file has focused coverage; splitting it during the correctness fix would add movement without changing risk.

### Fix-round test evidence

- Initial focused RED run: **7 failed, 10 passed**, covering the missing retired route, integrity suppression, authoritative transitions, blocker action, technology-only guidance, sidebar entry and explicit resource failure/unknown states.
- `pytest -q tests/test_transformation_room_routes.py tests/test_transformation_room_templates.py tests/test_sidebar_budgets.py tests/test_transformation_gate_service.py tests/test_transformation_option_service.py tests/test_transformation_evidence_service.py --maxfail=10`: **149 passed** in 45.25 seconds.
- Final route/template/sidebar regression after removing the duplicate EA link: **37 passed** in 26.33 seconds.
- Scoped Ruff: **passed**.
- `python scripts/verify.py --tag static`: **31 passed, 0 failed, 0 skipped** (including template syntax/references, fabricated data, sidebar links and rebuilt CSS).
- `python scripts/verify.py --gate boot-health`: **1 passed, 0 failed, 0 skipped**.
- `git diff --check`: **passed**.

### Browser verification concern

The async browser harness now launches and executes application behavior, but the final full run is **not counted green**. The shared host exhausted memory while Werkzeug served static assets (`MemoryError`) and zstd reported `Allocation error: not enough memory`; resulting asset requests returned 500. This is environmental rather than evidence of a passing product journey. The mandatory CI Playwright/axe job must pass before merge or deployment.

## Review fix round 2/5 — 24 August 2026

- Replaced the async smoke implementation and `pytest.mark.asyncio` dependency with the repository-supported package-scoped synchronous Playwright browser fixture. With the asyncio plugin explicitly disabled and strict markers enabled, the file collects two ordinary test functions.
- Made failed stage projections structurally total: every stage now receives its complete template-facing resource-key map, empty resource tuples, a `failed` state and the explicit database-unavailable reason. There is no loading projection because these pages are synchronous server renders with no asynchronous resource-loading phase.
- Added a route-render regression that forces the loader to raise `SQLAlchemyError` for all seven stages and proves each response is HTTP 200 with the failure alert rather than a Jinja exception.
- The now-running browser test exposed and closed two accessibility defects: the mobile navigation opener's `aria-controls` lacked a matching sidebar ID, and explanatory paragraphs were invalid children of the programme-context definition list.
- The smoke's deliberate stale-revision 409 is awaited through DOM completion and asserted through the rendered visible alert; its expected browser resource error is not misclassified as pre-error console noise.

### Fix-round test evidence

- RED: `pytest --collect-only -q -p no:asyncio --strict-markers tests/smoke/test_transformation_room_journeys.py` failed collection with `asyncio not found in markers`.
- RED: forced objective-stage loader failure raised `jinja2.exceptions.UndefinedError: 'dict object' has no attribute 'outcomes'`.
- Green strict collection without pytest-asyncio: **2 functions collected**.
- Forced failure route render across objective, discover, evidence, options, decision, execute and outcomes: **1 passed**.
- Focused routes/templates/sidebar: **38 passed** in 27.57 seconds.
- Synchronous browser/axe journey at 390px and 1024px: **2 passed** in 69.70 seconds. This covers create to objective, stable refresh, keyboard owner selection/focus state, later-stage honesty, a rendered server conflict and axe serious/critical rules.
- Scoped Ruff: **passed**.
- `python scripts/verify.py --tag static`: **31 passed, 0 failed, 0 skipped**.
- `python scripts/verify.py --gate boot-health`: **1 passed, 0 failed, 0 skipped**.

### Concern update

The prior browser-OOM concern is superseded by the successful synchronous full run above. CI remains the authoritative Linux/gunicorn execution, but there is no outstanding local browser failure in this round.
