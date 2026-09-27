# F500-030: neutral architecture journey cards

Date: 2026-09-05. Scoped source candidate; no commit or deployment by this worker.

## Decision and scope

The owner rejects decorative colored card edges/corners. DESIGN.md supplies the existing neutral card, border and radius tokens; the frontend-design skill's structural-versus-decorative distinction informed the boundary. No new visual language or replacement stripe was introduced.

Eight sites in six templates now use a uniform `border border-border bg-card rounded-lg` treatment. Existing spacing, content, status text/icons and controls remain unchanged:

| Template | Selected surface |
|---|---|
| `architecture_assistant/architecture_journey_hub.html` | First introductory section; decorative absolute left strip removed |
| `architecture_assistant/journey_v3.html` | Co-pilot `div[x-show="currentStep <= 6"]` |
| `architecture_assistant/journey_v2_steps/_step1_clarify.html` | Enriched brief `div[x-show="clarifyPhase === 'enriched' && enrichedBrief"]` |
| `solutions/detail.html` | Both Jinja branches of the Executive Summary callout |
| `solutions/blueprint.html` | Repeated action and approval card divs, beneath their real x-for templates |
| `archimate/partials/_composer_overlays.html` | Repeated warning tile `[x-text="gap"]` |

Navigation active markers, selection controls, heading accents, progress/chart/timeline graphics, badges, toasts, diagnostic lists, print exports and unrelated cards were not changed. The gap heading's warning icon remains. Undo/Approve/Dismiss handlers and server operations were not modified.

## Reachability and original evidence

`journey_v2_routes.py:317,405` renders the hub at `/architecture-journey/`; lines 884,897 render journey-v3 at `/architecture-journey/<solution_id>`. Journey-v3 includes the step-one partial. `solution_design_routes.py:2839–2928` serves blueprint at `/solutions/<id>` by default, with `?edit=1` selecting detail (also used as fallback). The v2 module registers both blueprints and bootstrap selects that registration. Composer includes its overlays partial at `archimate/composer.html:2281`.

The initial complete-template styling probe with real CSS measured the hub strip at 4px wide, 188px high, blue `rgb(37, 99, 235)` against an already-neutral 1px card border. The co-pilot was blue 4px left/neutral 1px top; the enriched brief was green 4px left/translucent green 1px top. Original screenshots are local `.qa-f500-030-journey-hub-accent.png` and `.qa-f500-030-journey-card-accents.png`.

The adjacent composer tile entered scope only after its actual template was rendered by native Alpine: computed left border 2px `rgb(245, 158, 11)`, other sides 0px, background `rgba(241, 245, 249, 0.1)`. No source-only assumption justified that addition.

## Regression boundary and TDD

`tests/test_neutral_journey_cards.py` renders fragments extracted from the current real Jinja templates with actual committed CSS, Alpine and Lucide assets. Fixture state exercises the real x-if/x-for/x-show rendering, including recorded undone and dismissed states and disappearance of an empty gap list. It checks four equal 1px neutral borders, uniform 8px corners, the neutral card fill, absence of the hub stripe, recorded content, status icons and visible action affordances. Both light/dark themes and Chromium/Firefox/WebKit are enabled: 48 cases.

The fixture replaces only the surrounding page/data/network boundary; it does not load application/domain JavaScript or call backend actions. Consequently these tests prove rendered-style and conditional-markup behavior, not authenticated journey transitions, AI generation, approval execution, Undo persistence or production deployment. No external network/provider or database is used. Unexpected requests, console errors and page errors fail teardown.

Before production edits, six scoped states produced clean computed-style failures. The first run also exposed two fixture defects (an ambiguous hub fragment selector and a missing co-pilot state field); those were corrected, and the two focused controls then failed on their original styles with no fixture errors: 2 failed, 46 deselected in 18.88s. The original complete-template probe independently demonstrated the hub's colored strip. The source patch is only 8 insertions/9 deletions across the six templates.

## Verification

- Focused Python correctness lint: passed.
- Scoped `git diff --check`: passed.
- `python -m pytest tests/test_neutral_journey_cards.py -q --override-ini addopts='' --maxfail=3`: **48 passed in 105.49s**, including all three engines, both themes, summary branches and dynamic action/approval/gap states; no console/page-error teardown failures.
- `python scripts/verify.py --gate template-syntax`: **1 passed, 0 failed, 0 skipped**, 10.8s.
- Post-change actual-fragment screenshot: `.qa-f500-030-journey-hub-neutral.png`, visually inspected; the original blue left stripe is absent and the existing stage list remains.

The parent owns the shared CSS rebuild and its freshness check, repository-wide verification, CI and release. This worker did not alter generated CSS or bundle assets.

Parent independent verification: rebuilt stylesheet fingerprint `de5a7e07`,
freshness check passed, then all 48 browser cases passed without skips in
69.98 seconds. Full-app interactions, complete CI and deployed acceptance remain
outside this rendered-style result.
