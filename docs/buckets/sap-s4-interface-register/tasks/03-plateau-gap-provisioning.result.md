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
