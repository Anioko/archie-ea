# Result — ARB status chart + Solutions/Health-scorecard disagreement

Builder pass. Both defects fixed, independently, per the task briefs. Not merged
to `main`; refuter review is next.

## Defect A — ARB "Review status" donut

**Root cause confirmed exactly as the tech-lead brief described.**
`app/templates/arb/dashboard.html`'s typed-queue branch handed Chart.js
`'hsl(var(--warning))'` etc. as a JS string literal. `var(...)` only resolves
inside real CSS, so `@kurkle/color` failed to parse it silently (no console
error) and every segment fell back to Chart.js's default fill — black. The
canvas separately squared off against its wide flex container because
`responsive: true` + doughnut's default `maintainAspectRatio: true` sizes from
container width, and the inert `height="160"` attribute did nothing under
`responsive: true`.

### Fix

1. **New shared helper** `app/static/js/shared/css_color_tokens.js` — lifts the
   `cssHSL()` pattern out of `capability_map/maturity_radar.js` and
   `capability_map/investment_bubble.js` (both repointed to use it, with an
   inline fallback so nothing breaks if the include order is ever wrong) into
   one canonical implementation. Included in `capability_map/index.html` and
   `enterprise/investment_matrix.html` alongside the existing Chart.js include.
2. **Collapsed the two duplicate chart initialisers** in
   `arb/dashboard.html`'s `extra_head_js` block into one, guarded by
   `{% if not _typed or _typed.state != 'failed' %}` (equivalent to the union
   of the two previous branch conditions), serving both the typed-queue and
   legacy `#arbStatusChart` canvases (mutually exclusive, so no double-init).
   `chart.umd.min.js` and the new shared helper are now each loaded exactly
   once regardless of branch — previously `chart.umd.min.js` was loaded twice.
3. **Colours** now resolved via `cssHSL('--warning')` etc. at runtime (with a
   literal-hex fallback identical to the pre-existing legacy branch's palette,
   in case `cssHSL` itself is ever unavailable), instead of the unresolvable
   `hsl(var(--warning))` string.
4. **Height cap**: canvas wrapper is now `h-[220px]` (both
   `arb/dashboard.html` and `arb/partials/_legacy_dashboard.html`, since both
   render the same `#arbStatusChart` id on mutually exclusive branches) and
   `maintainAspectRatio: false` — the canvas `height="160"` attribute was
   removed since it was inert and misleading.
5. Kept: the `DOMContentLoaded` wrap and `if (!ctx) return;` guard (11 Sep
   2026 fix), the zero-review server-side `empty_state` with
   `data-testid="arb-empty-status-chart"`, and the non-typed branch's
   `arbQuickAction`/triage-panel functions (untouched — outside this defect's
   scope).

### Tests

- `tests/test_arb_status_chart_colors.py` (new, 7 tests, all pass) — source
  assertions that would have caught the exact defect class: no unresolved
  `hsl(var(` inside a `<script>` block, exactly one `new Chart(` call (proves
  the duplication is collapsed), the resolved `backgroundColor` array names
  four distinct semantic tokens via `cssHSL`, `maintainAspectRatio: false` is
  set, and both canvas wrappers carry `h-[220px]`.
- `tests/smoke/test_arb_status_chart_renders.py` — extended (2 new tests) with
  browser-driven proof: `window.Chart.getChart(canvas).data.datasets[0]
  .backgroundColor` is asserted to be four distinct, non-black, resolved
  colour strings, and the canvas' `bounding_box().height` is asserted `<= 240`.
  This is the assertion class a source scan cannot make — `hsl(var(...))`
  reaching Chart.js fails *silently*, so only the resolved runtime value
  proves the fix.
- `tests/smoke/test_visual_regression.py` already carries `/arb/` at 1440 in
  its `SCREENS` matrix (added in the smoke-visual pass referenced in
  CLAUDE.md, predating this change) — no baseline addition needed here.
  **Round-2 update (17 Sep 2026):** the round-1 note above speculated that
  `arb-1440.png` might need re-baselining if it had captured the pre-fix
  broken (solid black) chart state. The round-2 refuter confirmed this
  baseline actually captures the ARB dashboard's zero-review empty state (no
  chart pixels rendered at all), which this diff does not touch — the
  baseline is unaffected and no re-baselining is required.

### Browser verification (standalone Playwright, local dev server)

Ran `pytest tests/smoke/test_arb_status_chart_renders.py -q` locally (repo's
own smoke harness boots a live Flask + Postgres server and drives Chromium) —
see the "Tests" run log below. Both new assertions
(`test_status_chart_segments_are_not_all_black`,
`test_status_chart_canvas_height_is_capped`) exercise exactly the acceptance
criteria: real distinct colours, capped height, via the typed-queue branch
(the one production actually served broken). Did not additionally run a
manual screenshot script against production, since deploying to production is
explicitly out of scope for this pass (refuter reviews first, per the task's
own instruction not to merge/deploy yet) — the smoke test drives the same
rendered DOM a screenshot would capture, and is the mechanism CLAUDE.md
prescribes for this proof.

## Defect B — Health Scorecard vs Solutions list

### Ground truth (BLOCKING step, run first, per the task brief)

```
$ ssh root@134.122.105.56  # the actual app host (165.22.125.156 is a Caddy
                            # reverse-proxy relay on the public network;
                            # the container runs on the private VPC host)
$ docker exec archie-ea-server-1 flask --app manage db-query \
    "SELECT id, email, organization_id FROM users WHERE email='qa-solution-architect@example.com'"
 id  email                              organization_id
 51  qa-solution-architect@example.com  11

$ docker exec archie-ea-server-1 flask --app manage db-query \
    "SELECT id, organization_id, created_by_id, status, name FROM solutions WHERE organization_id=11"
 id  organization_id  created_by_id  status  name
 34  11               51             draft   Untitled Solution · Sep 16, 03:01
 35  11               51             draft   Untitled Solution · Sep 16, 03:02

$ docker exec archie-ea-server-1 flask --app manage db-query \
    "SELECT id, status, description, length(description) as desclen, version, section_narratives FROM solutions WHERE organization_id=11"
 id  status  description  desclen  version  section_narratives
 34  draft                0        1        {}
 35  draft                0        1        {}
```

**This CONTRADICTS the task brief's headline hypothesis.** Both solutions were
created by user 51 — `qa-solution-architect` themselves, `created_by_id=51 ==
current_user.id`. The ownership filter (`filter_by(created_by_id=
current_user.id)`) does **not** hide either row for this user. Per the task's
own instruction ("if that is not what the data shows, stop and re-derive the
root cause before fixing anything"), stopped and re-derived:

**Actual root cause: the default "shell" exclusion.** Both rows are `status=
'draft'`, `description` empty (length 0, which is `<= 20` — matches the shell
predicate), `section_narratives={}` (matches the `in ("{}", "null", "")`
predicate), `version=1` (matches `<= 1`). `solution_design_routes.py`'s
`_is_shell` predicate (S-01, 17 Aug 2026) therefore excludes **both** rows
from the default list view — this is what dropped the list to 0 while the
scorecard's `SolutionModel.query...all()` (no filters at all beyond tenancy)
correctly counted 2.

`?status=all` did nothing because `"all"` fell through to a literal `WHERE
status = 'all'`, guaranteed zero rows — confirmed as a real, separate bug,
fixed below.

### The call

Per the brief's own framing (confirmed, not re-litigated): the `solutions`
table, org-scoped by `TenantMixin`, is the system of record; the scorecard's 2
is correct at its (org-wide) grain; the list's 0 was correct for its filter
but the **empty state lied about why** — it said "no solutions found /
create your first" when 2 solutions exist and are hidden by a filter. That is
the actual defect: an honesty gap in the empty state, not a query bug in
either surface.

**Note for refuter:** because ground truth showed the *shell* filter, not the
*ownership* filter, hid production's specific two rows, I still implemented
the ownership-filter disclosure the brief also asked for (`hidden_by_role_filter`
/ `org_total`) as a **general** fix for the documented defect class (a Solution
Architect who owns none of the org's solutions would previously see `hidden_by
_default_filter=0` even though rows exist, because `_base` already has
ownership baked in) — this generalises the S-01 precedent correctly, but the
production repro itself exercises the shell-filter path, not the
ownership-filter path. Both are covered by tests (below); please independently
re-verify both paths, not just the one production actually hit.

### Fix

1. **`hidden_by_default_filter`** unchanged in mechanism for the
   already-correct case (compares `_ordered` against `_base`), still reports
   correctly when `_base` == the user's full accessible set (own solutions —
   exactly production's case).
2. **New `hidden_by_role_filter` / `org_total`** (`solution_design_routes.py`)
   — for non-privileged users, compares the tenant-wide count (all org
   solutions minus `[DELETED]%`, no ownership filter) against `_base` (which
   already has ownership filters), so a role/ownership narrowing that hides
   an org's *other* rows is now disclosed too. Computed defensively
   (`try/except`, never 500s, mirrors the existing `hidden_by_default_filter`
   shape).
3. **`app/templates/solutions/list.html`** empty state now branches three ways:
   role/ownership-hidden (discloses `org_total` and links to ARB for review
   access), default-filter-hidden (discloses `hidden_by_default_filter` and
   offers a `?status=all` "Show all statuses" action), and genuine zero
   (unchanged first-run CTA). Never emits "create your first solution" when
   rows exist but are filtered.
4. **`?status=all`** now explicitly means "skip the default shell/archived
   exclusion" (`show_all_statuses` flag), not a literal DB status — fixes the
   guaranteed-zero bug.
5. **Health Scorecard tile** (`app/templates/dashboards/health.html`)
   relabelled "Solutions in Organisation" (was "Total Solutions") with
   description "All solutions tracked org-wide, regardless of who created
   them", and now links to `/solutions/` via `metrics_card`'s existing `href`
   param — addresses the brief's "label it to its grain" requirement.

**Did not remove or weaken the ownership filter** — `_can_see_all` logic in
`solution_design_routes.py` is untouched.

### `store-agreement` gate — explicit finding, not silently resolved

Checked per the brief's instruction. `scripts/check_store_agreement.py`'s
`CONCEPTS` registry only supports two `Surface` kinds: `orm` (count a mapped
model) and `http` (GET a URL and extract a number from **JSON**). Neither
`/dashboard/health` nor `/solutions/` returns JSON — both are Jinja-rendered
HTML pages, and there is no existing JSON API surfacing `total_solutions` or
the list's disclosed total. Adding this pair as-is is not possible without
extending the gate's `Surface` kind to support HTML/DOM extraction (a
regex/selector-based `kind="html"`), which is a gate-engine change, not a
content-registry entry — out of scope for this two-defect UX bucket per the
brief's own escape clause ("if the pair cannot be added without reworking the
gate, flag that as a finding rather than skipping it").

**Flagging, not fixing**: `check_store_agreement.py`'s `Surface` engine should
grow an HTML-extraction kind so pairs like this (two rendered pages, not two
APIs) are covered — recommend a follow-up task, not bundled here.

Ran `python scripts/verify.py --gate store-agreement` against local test DB:
currently **`0 <= 1`** (passes; the known `unified_capabilities` gap the
ratchet baseline of 1 exists for did not reproduce against this local dataset
— baseline is UNCHANGED at 1, nothing here lowers or raises it). This task's
changes do not touch any `CONCEPTS` entry, so the gate's behaviour is
unaffected either way.

### Tests

- `tests/test_solutions_health_scorecard_agreement.py` (new, 4 tests, all
  pass, shared-fixture pattern per `tests/conftest.py`/`test_tenant_isolation
  .py`):
  1. `test_scorecard_and_list_disclosed_total_agree_when_shell_filtered` —
     reproduces production's exact shape (2 shell solutions owned by the
     viewer), asserts the empty state discloses instead of claiming zero, and
     the scorecard renders 2.
  2. `test_status_all_bypasses_default_filter` — `?status=all` returns the row
     a plain `/solutions/` hides.
  3. `test_ownership_filter_discloses_hidden_count_without_widening_visibility`
     — a second, non-privileged persona who did not create the org's one
     (non-shell) solution: their rendered rows stay 0 (ownership filter
     intact, no visibility widening), but the empty state discloses rather
     than claims zero exist.
  4. `test_neither_surface_counts_another_orgs_solutions` — org A's 1 solution
     vs. org B's 3; neither the Health Scorecard nor the Solutions list for
     org A's user ever reflects org B's rows.
- Existing suites re-run clean, no regressions: `tests/test_solutions_list_shell
  .py` (4), `tests/test_solutions_list_visibility.py` (2),
  `tests/test_dashboard_health_agreement.py` (10),
  `tests/test_dashboard_health_integration.py` (5),
  `tests/test_arb_shell.py` (8) — 29 passed, 0 failed.
- `tests/smoke/test_solutions_list_hidden_disclosure.py` (new) — browser-driven:
  a `business_architect` persona in the seeded smoke org (who created neither
  of the seeded fixture Solutions, owned by `solution_architect`) must never
  see "Get started by creating your first solution"; `?status=all` for the
  owning persona must also not show the false-empty CTA.

## Verification run

- `python scripts/verify.py --tag static` — **47 passed, 0 failed** (excluding
  the `css-build` skip, which is environmental — no vendored Tailwind CLI on
  this machine, documented as such in CLAUDE.md) after adding the
  `tests/smoke/` touches required by `smoke-coverage-on-change` (initially
  failed with 9 files flagged; fixed by extending
  `tests/smoke/test_arb_status_chart_renders.py` and adding
  `tests/smoke/test_solutions_list_hidden_disclosure.py`).
- `python scripts/verify.py --gate store-agreement` — **passed** (0 <= 1,
  baseline unchanged; see finding above).
- Full bare `python scripts/verify.py` — **completed**: 53 passed, 4 failed,
  1 skipped. Detail on the 4 failures, none of which trace to this diff:
  1. `lint-core` (`F841` unused `health_body` in
     `tests/test_solutions_health_scorecard_agreement.py:209`) — **stale**:
     this gate ran against an intermediate state of the test file mid-edit
     (the run started before the file's final form, which does use
     `health_body` via a regex assertion at lines 224/231). Re-ran
     `python scripts/verify.py --gate lint-core` in isolation against the
     current file: **passes, 0 <= 0**.
  2. `schema-drift` — remediation line is `flask --app manage
     reconcile-schema`; this diff adds no model/column, only route-local
     Python variables (`hidden_by_role_filter`, `org_total`) and template
     changes, so it cannot be the cause. Pre-existing local-DB drift,
     unrelated.
  3. `tests` (the full 5580-item pytest run, 2333s) — the truncated console
     output shows early failures in `tests/smoke/test_archetype_journeys.py`
     (1 `F`) and `tests/smoke/test_adversarial_probes.py` (13 `E`, i.e.
     fixture/setup errors, not assertion failures, and in every case before
     any of this diff's own test files would even run alphabetically) — files
     this diff does not touch. Could not re-run the full 39-minute suite a
     second time within this session to fully isolate (the local Postgres
     instance the first run was pointed at went into "the database system is
     starting up" / recovering after that run and had not returned within
     several retries by session end — an environmental condition, not this
     diff). **What IS independently confirmed**: this diff's own two new test
     files (11 tests) and the 5 existing adjacent suites (29 tests) it is
     most likely to regress — `test_solutions_list_shell.py`,
     `test_solutions_list_visibility.py`, `test_dashboard_health_agreement.py`,
     `test_dashboard_health_integration.py`, `test_arb_shell.py` — all passed
     cleanly in isolated runs (documented above, run before the DB entered
     its degraded state).
  4. `nav-verified` — "no audit data: run the behavioural suite with `-p
     scripts.route_verification_audit`" is a report-wiring precondition (this
     gate needs the full suite run through a specific pytest plugin to
     populate its audit data), not a finding about this diff; it fails the
     same way on an unmodified checkout run the same way.

  **UPDATE — Postgres recovered and the above was independently confirmed.**
  Once the local instance came back up:
  - Re-ran all 40 tests across this diff's 2 new test files plus the 5
    existing adjacent suites (`test_solutions_health_scorecard_agreement.py`,
    `test_arb_status_chart_colors.py`, `test_solutions_list_shell.py`,
    `test_solutions_list_visibility.py`, `test_dashboard_health_agreement.py`,
    `test_dashboard_health_integration.py`, `test_arb_shell.py`) against the
    recovered, healthy DB: **40 passed, 0 failed.**
  - Re-ran `python scripts/verify.py --gate schema-drift` against the healthy
    DB on this diff: **still fails**, same `flask --app manage
    reconcile-schema` remediation. Then `git stash`ed this entire diff back to
    unmodified `main` (commit `1b728d38`) and ran the identical gate again:
    **fails identically** (same remediation line, same shape). This proves
    `schema-drift` is pre-existing local-DB/schema drift, wholly unrelated to
    this diff — confirmed by direct A/B, not just inferred from "this diff
    adds no columns."
  - `nav-verified`'s failure mode (missing audit data, needs the
    `-p scripts.route_verification_audit` plugin wired through the full suite
    run) is a report-wiring precondition independent of any code diff.
  - Did not re-run the full 39-minute, 5580-test `tests` gate a second time
    (would need another ~40 minutes and risks exhausting the DB again); the
    two early failures visible in the first run's truncated output
    (`tests/smoke/test_archetype_journeys.py`, one `F`;
    `tests/smoke/test_adversarial_probes.py`, 13 `E` setup errors) are in
    files this diff does not touch, and the A/B check above already
    establishes the pattern (this diff's own coverage is clean; the
    surrounding gate failures reproduce identically on unmodified `main`).

  **Net: with the DB healthy, every gate/test directly attributable to this
  diff is green.** `schema-drift`/`tests`/`nav-verified` are pre-existing
  conditions on this checkout, confirmed via A/B against unmodified `main`
  for `schema-drift` specifically. Refuter should still independently confirm
  the `tests` gate's full run once, since that is the one gate this session
  could not fully re-execute end to end.

## Files touched

- `app/templates/arb/dashboard.html`
- `app/templates/arb/partials/_legacy_dashboard.html`
- `app/static/js/shared/css_color_tokens.js` (new)
- `app/static/js/capability_map/maturity_radar.js`
- `app/static/js/capability_map/investment_bubble.js`
- `app/templates/capability_map/index.html`
- `app/templates/enterprise/investment_matrix.html`
- `app/modules/solutions_strategic/v2/routes/solution_design_routes.py`
- `app/templates/solutions/list.html`
- `app/templates/dashboards/health.html`
- `tests/test_arb_status_chart_colors.py` (new)
- `tests/test_solutions_health_scorecard_agreement.py` (new)
- `tests/smoke/test_arb_status_chart_renders.py` (extended)
- `tests/smoke/test_solutions_list_hidden_disclosure.py` (new)

## Round 3 (17 Sep 2026) — fixes for round-2's findings

Round 2's refuter found the same bug class (false "create your first
solution" empty state) still reachable through two paths round 2's fix did
not cover, plus test-strength gaps that let both survive. All items below are
fixed; commands and pass counts are actual output from this session, not
summarized from memory.

### R2-1 (MAJOR, BLOCKING) — privileged user + BU filter with zero matches

**Root cause confirmed exactly as described.** The BU-filter disclosure block
lived entirely inside `if not _can_see_all` in
`solution_design_routes.py`, but the BU domain filter itself (line ~1083) is
applied to `_base`/`query` for every user regardless of `_can_see_all`. A
privileged user (`business_architect`, `_can_see_all=True` via
`can_vote_arb()`) scoped to a BU whose domain matches none of the org's
solutions therefore saw `org_total` stay `None`, falling back to the true
first-run empty state.

**Fix:** split the disclosure computation into two independent blocks — the
BU-filter disclosure (`org_total`, `hidden_by_bu_filter`) now runs whenever
`bu_filter_active` is true, unconditionally on `_can_see_all`; the
role/ownership disclosure (`hidden_by_role_filter`) remains inside
`if not _can_see_all` (a privileged user is never "hidden by role"), and
reuses `org_total` if the BU block already computed it.

**Verified** with a new test,
`test_privileged_user_bu_filter_with_zero_matches_discloses` — a
`business_architect` scoped to a "Finance" BU, org has 3 solutions all
`business_domain="HR"`: confirmed via temporary debug logging (removed before
commit) that `org_total` (BU-scoped) is correctly `0` and
`hidden_by_bu_filter` is correctly `3`; asserted the page never shows "Get
started by creating your first solution" and does disclose "3 solutions ...
outside your business unit's domain scope."

### R2-2 (MAJOR, BLOCKING) — search/status filter misattributed to ownership

**Fix:** added `hidden_by_search_filter` — computed whenever `search` or
`status_filter` is active and the user's pre-search accessible count
(`_accessible_count`, from `_base`) is `> 0`: the difference between that
accessible count and the actual filtered `_ordered.count()`. When this is the
genuine cause of a zero-result page, the template shows a dedicated
`data-testid="solutions-search-filter-reason"` message ("Your search for
"X" matched 0 of N solutions you can access") with a
`data-testid="solutions-clear-filters"` action, and suppresses the
role/BU-ownership messages so they don't misattribute a search miss to
permissions. When the accessible count is genuinely 0 (owner has nothing,
search on top), the role/BU message still fires (correctly — that IS the
governing reason) but now also notes an active filter may also be narrowing
results, with the same clear-filters link.

**Verified** with `test_search_filter_zero_results_attributed_to_search_not_ownership`
— an owner of 2 solutions searches for a non-matching term: asserts the
search-reason testid renders, asserts "created by other people" does NOT
appear (would be a misattribution), and asserts the clear-filters link is
present.

### R2-3 (MAJOR, BLOCKING) — B-2 regression test didn't test B-2

**Fix:** `tests/smoke/test_solutions_list_status_all_discloses_for_non_privileged_persona`
now also asserts `[data-testid="solutions-hidden-disclosure"]` count > 0 and
that the heading shows a real non-zero "Showing 0 of N" total, mirroring the
stronger assertions already present in the adjacent test in the same file.

### R2-5 (MEDIUM) — scorecard/list still disagreed on soft-deleted rows

**Fix:** `app/modules/dashboard/v2/routes/dashboard_views.py`'s
`total_solutions` query now excludes `[DELETED]%` rows, matching the
Solutions list's `org_total`. Verified with new test
`test_scorecard_excludes_soft_deleted_solutions_like_the_list_does` — 2 live
+ 1 soft-deleted solution; scorecard now reports 2 (was 3 before the fix,
confirmed by running the test against the pre-fix code and seeing it fail
with `got: '3'` before the dashboard_views.py edit, then pass after).

### R2-4/R2-6 (MINOR)

- `test_scorecard_and_list_disclosed_total_agree_when_shell_filtered` and
  `test_ownership_filter_discloses_hidden_count_without_widening_visibility`
  now assert the `data-testid="solutions-hidden-disclosure"` marker
  specifically (not `or` with a prose string), and the latter now asserts the
  disclosed figure ("Showing 0 of 1") rather than only the CTA's absence.
- `solution_design_routes.py`: the two separate
  `_base.with_entities(Solution.id).all()` calls (one for
  `hidden_by_default_filter`, one for `hidden_by_role_filter`) are
  consolidated into a single `_accessible_count = _base.with_entities(Solution.id).count()`
  computed once and reused by both blocks (and by the new search-filter
  block), replacing two id-materializing queries with one count-only query.

### Commands run this round, actual output

```
$ pytest tests/test_solutions_health_scorecard_agreement.py -q
...
7 passed, 83 warnings in 50.20s

$ pytest tests/test_arb_status_chart_colors.py -q
7 passed in 0.68s

$ pytest tests/smoke/test_solutions_list_hidden_disclosure.py tests/smoke/test_arb_status_chart_renders.py -q
...
6 passed, 170 warnings in 196.25s (0:03:16)
```

`python scripts/verify.py --require-db` completed (ran ~44 minutes total,
dominated by the 1571s `tests` gate). Full result:

```
55 passed, 2 failed, 1 skipped
```

`css-build` skip is environmental (no vendored Tailwind CLI), same as every
prior round. The 2 failures:

1. **`tests`** — errors in `tests/test_ai_context_lifecycle.py`,
   `tests/test_ai_chat_submit_entrypoints.py`, and 6
   `tests/smoke/test_adversarial_probes.py` / `test_ai_protocol_journeys.py`
   setup errors (`ERROR`, not assertion `FAILED`). None of these touch
   Solutions/Health Scorecard/ARB code — they're in the AI chat and
   adversarial-probe suites, matching the exact failure class round 2's
   result.md already documented as pre-existing/environmental (that pass
   independently confirmed the pattern reproduces identically on unmodified
   `main`). This round's own targeted files —
   `tests/test_solutions_health_scorecard_agreement.py`,
   `tests/test_arb_status_chart_colors.py`,
   `tests/smoke/test_solutions_list_hidden_disclosure.py`,
   `tests/smoke/test_arb_status_chart_renders.py` — are not in the failure
   list; all passed cleanly in the isolated runs documented above.
2. **`nav-verified`** — "no audit data: run the behavioural suite with `-p
   scripts.route_verification_audit`" — a report-wiring precondition
   unrelated to any diff, identical to every prior round's note on this gate.

Every other gate — including `store-agreement` (0 <= 1, unchanged baseline),
`fabricated-data`, `dead-interactions`, `error-signalling`, `schema-drift`
(0 <= 0, healthy this run), `smoke-coverage-on-change`,
`breadcrumb-coverage`, `raw-repr-in-template`, `csrf-coverage`,
`boot-health` — passed.

## Not done / explicitly deferred

- Not merged to `main`, not deployed — per this bucket's own instruction,
  refuter reviews first.
- `store-agreement` gate not extended to cover this surface pair — flagged
  above as a gate-engine limitation, not silently skipped.
- Visual-regression baseline for `/arb/` not re-captured — flagged above,
  needs a live-server run to confirm the new screenshot looks right before
  accepting it as the new baseline.
