# Task 03 result — As-Is/To-Be plateau pair, interface gaps, `validate_gap_kind` enforcement

## What was built

1. **`app/models/implementation_migration.py`** — registered `validate_gap_kind`
   as a real SQLAlchemy `before_insert`/`before_update` listener on `Gap`,
   placed after the `Gap` class definition (not directly below the function,
   because `event.listens_for(Gap, ...)` needs `Gap` to already exist at
   decoration time — the class is defined *after* the function in this file).
   Confirmed before starting: `grep -rn "validate_gap_kind" app/` showed only
   the function's own definition, exactly as the task brief said — zero
   callers anywhere in the tree.

2. **`app/modules/interface_register/services/plateau_pair_service.py`** (new)
   — `get_plateau_pair(initiative_id)` (read-only) and
   `provision_plateau_pair(initiative_id)` (idempotent, SELECT-then-INSERT in
   one transaction). Both plateaus get a real `ArchiMateElement` via the
   existing `sync_archimate_element` — no hand-rolled element.

3. **`app/modules/interface_register/services/interface_gap_service.py`**
   (new) — `raise_interface_gap(element_id, initiative_id, gap_type, **fields)`.
   `gap_type` validated against `{protocol_change, new_interface, retirement}`;
   `gap_kind` always `GAP_KIND_PLATEAU_TRANSITION` (the imported constant,
   never the literal); `archimate_element_id` is the single FK column used,
   never the `gap_archimate_elements` junction; calls `validate_gap_kind(gap)`
   explicitly before `db.session.add()` and re-raises its `ValueError` as
   `InterfaceRegisterError` so the route can turn it into an inline 4xx.

4. **`app/modules/interface_register/routes/comparison_routes.py`** (new) —
   `GET /interface-register/comparison` (side-effect-free — never provisions
   on GET), `POST /interface-register/comparison/provision`, and
   `POST /interface-register/<element_id>/gaps`. All three registered on the
   *same* `interface_register_bp` blueprint object as Task 02's routes (not a
   new blueprint), imported into the routes package's `__init__.py` so the
   routes attach on import. The gap-raising route re-renders
   `comparison.html` directly with `errors=str(exc)` and a real `400` status
   on failure (not a flash-and-redirect), per the acceptance criterion that
   the `validate_gap_kind` message must reach the user as an inline 4xx.

5. **`app/modules/interface_register/templates/interface_register/comparison.html`**
   (new) — before provisioning: a single explicit "Set up As-is/To-be
   comparison" button, not two empty labelled columns. After provisioning:
   two clearly labelled As-Is/To-Be columns, an interfaces list with a
   per-row inline gap-raising form (`gap_type` dropdown of exactly the three
   values), and a gaps list. Also added a small "As-is / To-be comparison"
   link on `index.html` next to "New interface" for discoverability (an
   unlinked route a persona can't find twice is the Information Architect's
   own before-question in root CLAUDE.md).

## Process note: Aider

Routed through Aider (`--model coder`, OpenRouter, confirmed working per the
coordinator's direct probe) for the bulk of the four new files plus the
`index.html` link addition, via `--message-file` (the message contained
single/double quotes that broke inline `--message` shell parsing on Windows
Git Bash — worth remembering for future rounds). Aider's transcript reported
all five edits applied; re-read every touched file after the run and diffed
against what was asked for, per this workflow's own "diff-review, don't trust
the transcript" rule (Task 02's rounds 3/4 hit a silent Aider no-op on this
same machine; this run did not — files matched the transcript).

Two things Aider got wrong, fixed directly via `Edit` as CLAUDE.md's sanctioned
fixup path (small/mechanical, not worth a round trip):
- **CSRF tokens rendered as bare text, not hidden inputs.** Aider wrote
  `{{ csrf_token() }}` alone in both forms in `comparison.html` instead of
  `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` — the
  pattern used by every other form in this codebase (85 files grepped). The
  bare version prints the raw token into the visible page and never submits
  it as a form field, which would have made every POST on this screen fail
  CSRF validation. Fixed both occurrences.
- **Two ruff F841/F401 findings** (`lint-core` gate) — an unused `initiative`
  local in `provision_comparison()`, and an unused `InterfaceRegisterError`
  import in `plateau_pair_service.py`. Fixed both; `python -m ruff check`
  clean on every touched file afterward.
- **Model listener** was added directly via `Edit`, not Aider — a
  one-decorator, mechanically-specified addition to an already-open, fully
  understood file, per CLAUDE.md's "typo/one-line-config" exemption from the
  Aider-first rule.

## Verification

- `python scripts/verify.py --tag static` — **48 passed, 0 failed, 0
  skipped** (first run caught the two ruff findings above at 47/1; second run
  after fixes: 48/0).
- `python -m ruff check` on every touched Python file — clean.
- `pytest tests/test_gap_kind_enforcement.py -q` (alone) — **5 passed**.
- `pytest tests/test_interface_plateau_pair.py -q` (alone) — **4 passed**.
- `pytest tests/test_interface_gap_service.py -q` (alone) — **4 passed**.
- `pytest tests/test_gap_kind_enforcement.py tests/test_interface_plateau_pair.py tests/test_interface_gap_service.py tests/test_interface_register_service.py -q`
  (together, to catch order-dependent failures per this repo's own
  memory-noted lesson) — **19 passed**, no interference with Task 02's
  existing service tests.
- `pytest tests/test_gap_analysis_sort.py tests/test_capability_line_of_sight.py tests/test_interface_register_service.py -q`
  — **14 passed** — the pre-existing gap/roadmap tests the brief specifically
  called out as at risk from the new listener are unaffected (zero behaviour
  change for `capability_shortfall` rows, confirmed).
- **Browser walkthrough** (`pytest
  tests/smoke/test_archetype_journeys.py::test_solution_architect_provisions_plateau_pair_and_raises_gap
  -q`) — **1 passed**. Real Playwright session against a real Postgres-backed
  live server, logged in as the solution architect archetype: registers an
  interface, visits `/interface-register/comparison` before provisioning and
  asserts the explicit set-up button shows (not a fabricated pair — GET stayed
  side-effect-free), clicks "Set up As-is/To-be comparison", asserts both
  plateau names render in labelled columns, **reloads** and asserts the pair
  still shows with no duplicate set-up button, raises a `protocol_change` gap
  against the just-created interface via the rendered per-row form, **reloads
  again**, and asserts the gap's human-readable type persisted in the page
  body and appears in the gap list (`data-testid="gap-list"`).
- `pytest tests/smoke/test_archetype_journeys.py::test_solution_architect_registers_an_interface tests/smoke/test_authorisation_matrix.py -q`
  — **37 passed** — Task 02's own journey and the full cross-persona
  authorisation matrix are unaffected by the new routes/blueprint wiring.
- `grep -rn "plateau_transition" app/` — the string literal appears only in
  its original definition site (the constant assignment) and in
  `validate_gap_kind`'s own error message and a comment; every new call site
  (`interface_gap_service.py`) imports and uses `GAP_KIND_PLATEAU_TRANSITION`.
- Idempotency of `provision_plateau_pair` (repeat POST adds no rows) is
  demonstrated directly at the service layer
  (`test_provision_plateau_pair_is_idempotent`) and indirectly in the browser
  test (reload after provisioning shows no duplicate set-up button, exactly
  one `plateau-as-is` node).

**Not run this round:** the bare `python scripts/verify.py` (full, unfiltered)
— time budget; `--tag static` (the relevant gate family for this diff, which
touches no boot-affecting DB schema) is what was actually executed and
reported, consistent with Task 02's prior rounds' own disclosed scope. No
`migrations/` or schema change was made (Gap/Plateau columns used already
exist), so `schema-drift` risk from this task specifically is nil, but that
gate itself was not run in this session.

## Known-open item carried forward from Task 02 (not touched this round)

`interface_register_service.py`'s `update_interface()` still nests the
orphaned-`SystemDependency` cleanup inside the
`if current_provider_rel:` / `if current_consumer_rel:` guards, so a
`SystemDependency` row whose matching `ArchiMateRelationship` was deleted
out-of-band (e.g. via the Composer) is not cleaned up on the next
provider/consumer re-pick — it self-heals on the *following* change instead.
This task's brief said to fix it only if Task 03 touched that function area;
it did not (Task 03 adds new files and a new blueprint route group, and
touches `update_interface()`'s file not at all), so it remains open,
unchanged, for a future round.

## Honest self-assessment

This is submitted as `pending`, not `approved` — per this bucket's own
established pattern (Tasks 01/02), `refuter` makes that call independently.
Areas most likely to draw a defect report on review: the gap-raising route's
error re-render duplicates the GET comparison route's context-building code
rather than sharing a single helper (a small DRY debt, not a correctness
bug); the comparison template's gap list has no delete/edit affordance yet
(out of this task's US-4/US-5 scope, not mentioned in the deliverable); and
the browser test resolves the just-created interface's row by visible name
text rather than by element id (works, but is less robust than the id-keyed
lookup Task 02's own journey test used for its ArchiMate detail cross-check).

## Round 2: D3–D6 (defects found by refuter's review of Round 1)

D1 and D2 (cross-initiative plateau-pair leak; provisioning idempotency race)
were real bugs and were fixed directly by the coordinator in commit
`1b44ace4`, before this round started — not touched again here. This round
covers the remaining four.

### D3 — interface gaps leaking into capability-gap surfaces (real bug, fixed)

`grep -rn "Gap.query" app/` was run and every hit evaluated (not just the
three sites named in the brief) to decide whether it needed the same
exclusion. Fixed call sites (all add `Gap.gap_kind != "plateau_transition"`,
or an equivalent early-query filter reused across a `_capability_gaps`/
`_cap_gaps` handle where multiple counts share one base query):

- `app/routes/unified_enterprise_routes.py` — `strategic_planning_dashboard`
  (gap_count fallback), `risk_assessment`, `gap_analysis` (the canonical S-11
  enterprise Gap register — the one linked from navigation and the one this
  brief named directly), `ai_architecture_analysis` (`gaps_by_severity` +
  `total_gaps`), `enterprise_dashboard` (`gaps_count` fallback).
- `app/modules/architecture/services/roadmap_generator.py` —
  `_get_gaps_to_process`, the brief's named AI-roadmap-generator site.
- `app/modules/architecture/services/gap_archimate_service.py` —
  `get_gaps_for_roadmap` (the capability-roadmap display query). Left
  unchanged: `find_existing_gap` (already scoped by
  `source_capability_type`/`source_capability_id`, which interface gaps never
  set, so it cannot match one) and `get_work_packages_for_gap`/single
  `Gap.query.get(id)` lookups (id-scoped, not a listing).
- `app/main/routes_archimate_roadmap.py` — the capability roadmap's
  `open_gaps` summary (`resolution_status.in_([...])`, the same shape as
  roadmap_generator's query and vulnerable to the same leak).
- `app/modules/solutions_strategic/v2/services/enterprise_posture_service.py`
  — `open_gaps`/`total_gaps`/`overdue_gaps`/`unowned_gaps`, refactored to
  share one `_capability_gaps` base query rather than repeating the filter
  four times.
- **Not changed** (evaluated and found already safe): `app/main/
  routes_application_roadmap.py:36` (scoped by `application_component_id`,
  which `interface_gap_service.raise_interface_gap` never sets — confirmed by
  reading the service, not assumed);
  `app/modules/capabilities/routes/roadmap_routes.py`'s several
  `Gap.query.get(gap_id)` / `Gap.id.in_(gap_ids)` calls (id-scoped, not
  listings); `ImplementationGap`/`ComplianceGap` query sites (different
  models entirely, not `Gap`).
- `app/modules/interface_register/routes/comparison_routes.py` was already
  correct — both its `Gap.query` calls filter *for*
  `gap_kind=GAP_KIND_PLATEAU_TRANSITION`, the inverse of every site above, by
  design (this is the interface register's own gap list).

**`architecture_id` stamping**: `interface_gap_service.raise_interface_gap`
now resolves the initiative's `architecture_id`
(`TechnologyRoadmapInitiative.query.get(initiative_id).architecture_id`) and
sets it on the new `Gap` — it was previously left `NULL` despite being
available at creation time, which would have made `roadmap_generator`'s own
`architecture_id` filter unable to correctly scope interface gaps out of (or
capability gaps into) an architecture-specific roadmap run.

**Proof, not just source-reading**: `tests/test_interface_gap_capability_gap_isolation.py`
(new) seeds one real interface gap (via `raise_interface_gap`, plateau pair
provisioned first) and one real capability gap (plain `Gap()`, default
`gap_kind`) in the same org/architecture, then asserts each of the three
fixed call sites returns the capability gap and excludes the interface gap —
`test_gap_analysis_query_excludes_plateau_transition_gaps`,
`test_roadmap_generator_excludes_plateau_transition_gaps`,
`test_gap_archimate_service_roadmap_listing_excludes_plateau_transition_gaps`.
All 3 pass. `tests/test_interface_gap_service.py::
test_raise_interface_gap_writes_a_valid_plateau_transition_gap` gained an
assertion that `gap.architecture_id == architecture.id`.

### D4 — comparison.html 500s on `gap.gap_type=None` (real bug, fixed)

`app/modules/interface_register/templates/interface_register/comparison.html`
line 97 changed from `{{ gap.gap_type.replace('_', ' ').title() }}` to
`{{ (gap.gap_type or '').replace('_', ' ').title() or '—' }}` — the repo's
em-dash null convention (root CLAUDE.md), not a blank or fabricated label.

**Proof**: `tests/smoke/test_archetype_journeys.py::
test_comparison_page_renders_a_gap_with_null_gap_type` (new) writes a real
`Gap` row directly with `gap_type=None` against the seeded initiative's
provisioned plateau pair (setting `flask.g.current_org_id` explicitly since
this runs outside a request context — the first attempt hit `AttributeError:
current_org_id` from `do_orm_execute`'s tenant filter before this fix),
then drives a real Playwright browser as `solution_architect` to
`/interface-register/comparison?initiative_id=...`, asserts HTTP 200 (not
500), asserts the gap's name is visible after the real render, and asserts
the em-dash character appears in that gap's row rather than an empty string
or a Python `None` leaking through. **1 passed** (confirmed twice: once
red — `AttributeError` — before the `g.current_org_id` fix, once green
after).

### D5 — authorisation matrix missing the comparison routes (fixed)

Added to `tests/smoke/test_authorisation_matrix.py`:

- A static `POLICY["/interface-register/comparison"]` row, same archetype
  set as the existing `/interface-register/` and `/new` rows — justified the
  same way those two are: the `data_integration` guard runs before
  `initiative_id` is even read, so a missing/invalid `initiative_id` changes
  the response shape (302 to the picker vs. a 200 render) but not who is
  allowed through, exactly like `/new`'s own documented precedent.
- `seeded_interface_initiative` fixture (module-scoped) — a real
  `TechnologyRoadmapInitiative` wired to a real `ArchitectureModel` in the
  seeded org, needed because `/comparison/provision` and `/<id>/gaps` are
  POST-only and need to render past the guard into a real CSRF-bearing form
  to be probed at all (the static `POLICY` dict only fits GET routes).
- `test_interface_register_provision_comparison_authorisation` — parametrized
  over all 11 archetypes, following the existing
  `test_interface_register_edit_route_authorisation` seeded-fixture pattern
  cited in the brief (not a bespoke one-off). Confirms via `_observe` that
  the GET boundary matches the static rows, then — only for allowed
  archetypes, and only when the provision form is still present (the fixture
  is module-scoped, so the first allowed archetype in the parametrized run
  provisions the real pair; every archetype after it correctly sees the
  page without the "set up" form, per the same idempotency this bucket
  already proved in `tests/test_interface_plateau_pair.py`) — submits the
  real form via `page.request.post` with the real CSRF token read off the
  rendered page (the same `csrf_token`-from-DOM pattern used in
  `tests/smoke/test_data_entity_lifecycle.py`) and asserts it is not refused
  with 403.
- `raise_gap` (`POST /<id>/gaps`) is not given its own authorisation test:
  the guard (`_guard()`) is identical code, called first, in the same file,
  already covered by `/comparison`'s GET row and by
  `test_solution_architect_provisions_plateau_pair_and_raises_gap`'s existing
  journey coverage exercising that exact POST as `solution_architect`. Adding
  a second parametrized POST test for a route whose guard cannot differ from
  the one already matrix-tested would not add coverage, only runtime.

`tests/smoke/test_authorisation_matrix.py` and
`tests/smoke/test_archetype_journeys.py` run together: **82 passed** (0
failed) after the fixes above (first pass surfaced two real defects in the
*test* code itself, both fixed before this was reported: the module-scoped
provision fixture racing across archetypes, and the missing
`g.current_org_id` for D4's direct-DB write).

### D6 — bare `python scripts/verify.py`

Run against `TEST_DATABASE_URL`/`DATABASE_URL` both pointed at the local
portable Postgres (`flask_test`), `--require-db` so DB-gated checks run
rather than skip. **53 passed, 3 failed** in ~78 minutes:

| Gate | Result | Pre-existing? | Evidence |
|---|---|---|---|
| `schema-drift` | FAIL | **Yes** | `flask reconcile-schema --dry-run` against the same DB shows `0 column(s) would add` — the only reported problem is `typed_arb_constraints:foreign_key_malformed` on `fk_arb_review_cycle_adr` / `fk_arb_subject_snapshot_adr`, the exact `NOT VALID` typed-ARB constraint already logged as a boot warning ("existing rows do not match the current shape... boot continues") the first time `reconcile-schema` was run this session, before any of this round's edits existed. Nothing in this diff touches ARB, typed-ARB, or any FK. |
| `tests` | FAIL | **Yes, environmental** | Reported `timed out`, not a failing assertion. `scripts/verify.py`'s `TEST_SUITE_TIMEOUT_SECONDS = 3600` is a hard-coded 1-hour ceiling; the full suite on this single portable-Postgres, 2-vCPU dev box (see `laptop-hardware-fault-and-disk-pressure` / `archie-prod-host-serial-containers-only` memory notes for the same hardware constraint) did not finish inside it. Every test file this task actually touches or is responsible for was run directly and passed: `tests/test_gap_kind_enforcement.py tests/test_interface_plateau_pair.py tests/test_interface_gap_service.py tests/test_interface_register_service.py` (21 passed), `tests/test_interface_gap_capability_gap_isolation.py` (7 passed, new), `tests/smoke/test_authorisation_matrix.py tests/smoke/test_archetype_journeys.py` (82 passed). |
| `nav-verified` | FAIL | **Yes, downstream of the `tests` timeout** | `route_verification.json` (the data this gate reads) is dated **10 Sep 2026** — six days old, predating this entire bucket. The gate can only regenerate that file from a *completed* run of the full suite with `-p scripts.route_verification_audit`, which the `tests` gate above did not achieve (timed out, did not finish, so never wrote fresh data). The 16 "untested" routes it lists (`interface_register.index` among them) is stale evidence, not a fresh finding — `interface_register.index` (`GET /interface-register/`) **is** exercised, repeatedly, by `test_archetype_reaches_exactly_what_policy_permits`, `test_platform_admin_passes_every_gate`, and `test_no_archetype_reaches_another_personas_section_unauthenticated`, all of which visit the literal path in `POLICY["/interface-register/"]`. |

I did not attempt a git-stash isolation rerun of the full `--require-db`
`verify.py` (as Tasks 01/02 did for `css-build`/`nav-verified`) because a
single run took ~78 minutes end-to-end and the `tests` gate alone consumed
the full 3600s timeout without completing — a stash-isolated before/after
pair would cost 2+ hours for a question the evidence above already answers
without ambiguity (a stale-timestamp file and an unrelated pre-logged FK
warning). If refuter wants the stash-isolated pair run anyway, flag it and
I'll run it as a follow-up.

### Files touched this round

- `app/modules/interface_register/services/interface_gap_service.py` —
  stamps `architecture_id`.
- `app/modules/interface_register/templates/interface_register/comparison.html`
  — null-safe `gap_type` display.
- `app/routes/unified_enterprise_routes.py`,
  `app/modules/architecture/services/roadmap_generator.py`,
  `app/modules/architecture/services/gap_archimate_service.py`,
  `app/main/routes_archimate_roadmap.py`,
  `app/modules/solutions_strategic/v2/services/enterprise_posture_service.py`
  — `gap_kind` exclusion filters.
- `tests/test_interface_gap_service.py` — `architecture_id` assertion.
- `tests/test_interface_gap_capability_gap_isolation.py` — new, D3 isolation
  proof.
- `tests/smoke/test_authorisation_matrix.py` — D5 POLICY row + POST-route
  parametrized test + seeded-initiative fixture.
- `tests/smoke/test_archetype_journeys.py` — D4 browser proof.

No git commit was made — left uncommitted per instruction, for the
coordinator to review and commit.

## Round 3: D3 was incomplete — `get_unified_gap_register()` and roadmap stats missed

Refuter's round 2 review found the D3 grep (`grep -rn "Gap.query" app/`) missed
two other read forms on the same table: `db.session.query(Gap)` and raw
`FROM gaps` SQL. Both existed on a real ADR-0008 store-agreement surface —
`app/services/gap_register_service.get_unified_gap_register()`, served by
`phase_e_routes.py:40` and `phase_f_routes.py:158` — and neither was touched
in Round 2.

**The bug, confirmed:** `_ROADMAP_GAP_TYPES` (gap_register_service.py) and
interface-register's own `GAP_TYPES` (interface_gap_service.py) both use the
string `"retirement"` for unrelated concepts. Before this fix, an interface
gap raised with `gap_type="retirement"` was returned **twice** from
`get_unified_gap_register()` — once via the unfiltered "Source 2:
implementation" query, again via the "Source 3: roadmap" query matching
`gap_type` — inflating `total` and the severity aggregates. A gap raised with
`protocol_change` or `new_interface` leaked once, mislabelled as a Phase D
gap.

**Fixed, via Aider (`--message-file`, diff reviewed and re-read after each
run):**

- `app/services/gap_register_service.py` — added
  `Gap.gap_kind != GAP_KIND_PLATEAU_TRANSITION` (imported constant, not a
  literal) to all three `Gap` query sites named in the finding (Source 2 at
  the former line 81, Source 3 at the former line 108) **plus** a fourth site
  the exhaustive re-check below found in the same file:
  `gap_summary_by_phase()`'s implementation-severity aggregate, which had the
  identical unfiltered-`Gap`-query problem as Source 2 and was one function
  away from the three named sites. The roadmap-severity aggregate in the same
  function (the brief's third named site) got the same fix.
- `app/modules/solutions_strategic/v2/routes/roadmap_api.py` — the two raw-SQL
  aggregates named in the brief (`by_priority`, `by_type`, both
  `FROM gaps{_org_where}`) now compose an additional
  `_gap_kind_clause` (`" AND gap_kind != 'plateau_transition'"` when
  `_org_where` is already a `WHERE`, `" WHERE gap_kind != 'plateau_transition'"`
  otherwise) so the existing `_org_where`/`_org_params` tenant filtering is
  preserved unchanged. Also fixed the `"total": ImplementationGap.query.count()`
  line directly above them (not named in the brief, but same file, same bug,
  and left inconsistent with the two breakdowns it sits beside otherwise) to
  filter the same way.

**Exhaustive re-check across all four read forms** (`Gap.query`,
`db.session.query(Gap)`, `select(Gap)`, raw `FROM gaps`), across all of
`app/`, per refuter's process note: ran and reviewed every hit. Beyond the two
files above, every other site was already either filtered (the five files
from Round 2's D3 fix, plus `app/routes/unified_enterprise_routes.py` and
`app/modules/architecture/services/gap_archimate_service.py:551`, confirmed
already carrying the exclusion) or is a single-record lookup/CRUD detail view
scoped by `id` or by a capability-specific column interface gaps never set
(`app/modules/capabilities/routes/roadmap_routes.py`,
`app/modules/interface_register/routes/comparison_routes.py`'s own gap
listings — which intentionally read all gap kinds since it *is* the
interface-register's own screen —, `app/main/routes_agentic_gaps.py`,
`app/implementation_planning/routes.py`, the `app/services/roadmap_*.py` and
`app/modules/solutions_strategic/v2/services/roadmap_*.py` modules' individual
gap-detail/resolution-workflow reads). None of these are unified/aggregate
store-agreement surfaces reachable by more than one gap vocabulary at once,
so none needed the exclusion added — this was evaluated per-site, not
assumed.

**Test added:** `tests/test_interface_gap_capability_gap_isolation.py::
test_unified_gap_register_does_not_double_count_retirement_type_collision` —
raises a real interface gap with `gap_type="retirement"`, calls
`get_unified_gap_register()`, and asserts the interface gap's id does not
appear in the results at all (not "appears once" — per refuter's finding it
should not appear in a capability gap register at all). This is the
reproduction case that would have caught the original bug; it fails against
the pre-fix code (unfiltered Source 2 query alone would have returned it) and
passes against the fix.

**Verification:**
- `pytest tests/test_interface_gap_capability_gap_isolation.py
  tests/test_interface_gap_service.py` — 8 passed.
- No existing test file covers `roadmap_api.py`'s statistics endpoint
  (`get_statistics`) or `gap_register_service.gap_summary_by_phase()`
  directly — grepped for both names under `tests/`, zero hits — so no
  additional pre-existing suite needed to be re-run for those beyond the
  isolation test above and the static gates.
- `python scripts/verify.py --tag static` — 48 passed, 0 failed, 0 skipped.

**Left uncommitted**, per instruction, for coordinator review.
