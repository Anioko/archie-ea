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
