# Task 04 result — WorkPackage costing rollup, derived T-shirt size band, over-budget state

## What was built

1. **`app/modules/interface_register/services/size_bands.py`** (new) —
   `effort_band(estimated_effort_hours)`, a pure function per
   `docs/adr/0011-derived-display-bands.md`: no DB access, no `flask.g`, no
   request context. Returns `None` for `None`, a negative value, or a
   non-numeric input; otherwise walks `EFFORT_BANDS = ((40, "S"), (160, "M"),
   (400, "L"))` and returns `"XL"` past the last threshold. Thresholds match
   SRS Assumption A4 exactly (S ≤ 40h, M 41–160h, L 161–400h, XL > 400h).
   Registered as the Jinja filter `effort_band` from
   **`app/template_helpers.py::register_template_filters`** (the ADR's single
   registration point — *not* the module's own `register(app)`, which is
   what the task brief's shorthand said but the ADR, which this task was
   explicitly told to follow over the brief, designates as authoritative).

2. **`app/modules/interface_register/services/programme_rollup_service.py`**
   (new) — `interface_programme_rollup(initiative_id) -> dict`, the single
   authority for "what is committed against the S/4HANA `investment_budget`".
   Resolves the initiative (tenant-safe, via `resolve_initiative`), finds the
   To-Be plateau via `get_plateau_pair`, queries `Gap.query.filter_by(
   target_plateau_id=to_be.id, gap_kind=GAP_KIND_PLATEAU_TRANSITION)` (ORM
   only, no raw SQL, no hand-written `organization_id` — `Gap` is
   `TenantMixin` and already auto-scoped by `do_orm_execute`), then walks
   each gap's `work_packages` ORM relationship, de-duplicating by `.id` into
   a dict so a `WorkPackage` linked to two gaps is counted once. Returns
   `committed_cost` (sums only non-NULL `estimated_cost`, starts at `0.0`),
   `work_packages_missing_cost` (count of NULL-cost rows, never coerced into
   the sum), `total_effort_hours`, `investment_budget` (`None` if the
   initiative's is NULL), `headroom`/`over_budget` (both `None` when
   `investment_budget` is `None` — never a fabricated `False`/`0`), and
   `work_packages` (the raw ORM list — bands are computed by the template's
   `effort_band` filter at display time, never baked into this dict, per ADR
   0011 rule 6: "nothing sums, averages, sorts-by or filters-on a band").

3. **`app/modules/interface_register/services/work_package_service.py`**
   (new) — `attach_work_package_to_gap(gap_id, *, name=None,
   estimated_cost=None, estimated_effort_hours=None)`, the write path.
   Resolves the gap via `Gap.query.filter_by(id=gap_id,
   gap_kind=GAP_KIND_PLATEAU_TRANSITION).first()` — this single filter is
   both the tenant boundary (`Gap` is `TenantMixin`) and the vocabulary
   boundary (a plain capability-shortfall `Gap` can never accept a work
   package through this path, by construction, not by convention). Blank
   `estimated_cost`/`estimated_effort_hours` form fields parse to `None`
   (never `0`); a non-numeric value raises `InterfaceRegisterError`. Creates
   the `WorkPackage` with `architecture_id`/`plateau_id` inherited from the
   gap, appends it to `gap.work_packages` (keeps the `gap_work_packages`
   many-to-many in sync), commits, rolls back and re-raises on any exception
   — same shape as `plateau_pair_service.provision_plateau_pair`.

4. **`app/modules/interface_register/routes/costing_routes.py`** (new) —
   `GET /interface-register/costing`, `@login_required`, same `_guard()`
   (`data_integration` section) as every other route in this module. Reads
   `initiative_id` from the query string, redirects to the picker if absent,
   404s via `errors/404.html` on an `InterfaceRegisterError` (foreign/unknown
   initiative), otherwise renders `costing.html` with the rollup dict. Purely
   a read — no writes, no side effects.

5. **`app/modules/interface_register/routes/comparison_routes.py`** — added
   `POST /interface-register/gaps/<int:gap_id>/work-packages` →
   `attach_work_package`, same guard/resolve-initiative/flash pattern as the
   existing routes in this file. Calls `work_package_service
   .attach_work_package_to_gap`, flashes success or the
   `InterfaceRegisterError` message, redirects back to the comparison page.

6. **`app/modules/interface_register/templates/interface_register/comparison.html`**
   — each gap's `<li>` now shows any already-attached work packages (name,
   cost via the `currency` filter or `—`, size via `effort_band | default('—',
   true)`) and an inline attach form (name/cost/hours + CSRF, same Tailwind
   token classes as the existing `raise_gap` form). Added a "View programme
   costing" link to the new `/costing` screen — an unlinked route a persona
   can't find twice is a defect per this bucket's own established convention
   (Task 03's `index.html` link).

7. **`app/modules/interface_register/templates/interface_register/costing.html`**
   (new) — four summary cards (`rollup-committed-cost`,
   `rollup-investment-budget`, `rollup-headroom`,
   `rollup-missing-cost-count`), an over-budget block that renders **only**
   when `rollup.over_budget` is truthy (a badge *and* a sentence, not a red
   number alone — `over_budget is None`/`False` both render nothing here,
   never a fabricated "within budget" claim either), and a per-work-package
   list with cost/band, or the `empty_state` macro when there are none.

8. **`app/modules/interface_register/routes/__init__.py`** — registers
   `costing_routes` alongside `comparison_routes`.

9. **`tests/smoke/test_authorisation_matrix.py`** — added a static `POLICY`
   row for `/interface-register/costing`, same archetype set and same
   justification as the existing `/comparison`/`/new` rows (the guard runs
   before `initiative_id` is even read).

10. **`tests/smoke/test_archetype_journeys.py`** — added
    `test_solution_architect_attaches_costed_work_package_and_costing_rollup_updates`:
    sets a real `£100,000` `investment_budget` directly on the seeded
    initiative (which otherwise carries none, and this is a shared fixture
    used by every other journey in this file — set directly, not by editing
    the fixture), registers an interface, raises a gap, records the costing
    screen's baseline committed-cost text, attaches a `£250,000` work package
    (no effort hours) via the real rendered form on the comparison page,
    reloads **both** the comparison page (work package persisted) and the
    dedicated costing screen (total changed and reflects £250,000), asserts
    the over-budget badge+text indicator appears, and asserts the em-dash
    renders for the size column since no effort hours were ever supplied.

## Process note: Aider

Routed through Aider (`--model coder`, OpenRouter) via `--message-file` for
all nine new/modified application files, per this workflow's established
pattern. The message file specified byte-for-byte structure (imports,
function signatures, exact dict keys, exact route/template behaviour,
Tailwind class reuse) so there would be nothing load-bearing left to Aider's
own judgement. Aider's own transcript rendered em-dashes as `�` (a terminal
encoding artefact of this Windows Git Bash setup, not a file-write problem —
confirmed by re-reading every touched file directly afterward and finding
real `—` characters, not replacement characters, in both templates).

No fixups were needed this round — every file matched the spec on the first
re-read, including the ADR-0011-mandated registration point for `effort_band`
in `app/template_helpers.py` rather than the module's own `register(app)`
(the brief's own shorthand said the latter; the task instructions explicitly
said to follow the ADR over the brief where they disagree, and they do here).

## Verification

- `python -m ruff check` on all nine touched/created application files, all
  three new test files, and the extended smoke test file — clean.
- `python scripts/verify.py --tag static` — **48 passed, 0 failed, 0
  skipped** (includes `fabricated-data`, `null-filters`,
  `raw-sql-tenancy`, `tenant-scoping`, `csrf-coverage`).
- `python -c "import app; app.create_app('testing')"` — boots clean (the new
  `app.modules.interface_register.services.size_bands` import added to
  `app/template_helpers.py` module level pulls in the whole
  `interface_register` package earlier than before, since `init_services`
  runs before `init_blueprints`; confirmed this causes no import-order
  failure — the package's blueprint object construction has no app-context
  dependency).
- `grep -rn "estimated_cost" app/modules/interface_register/` — the sum
  (`committed_cost += float(wp.estimated_cost)`) exists in exactly one place
  (`programme_rollup_service.py`); every other hit is a route reading a form
  field, a template rendering a single row's value, or the function
  signature/docstring — none is a second implementation of the total.
- `pytest tests/test_effort_bands.py` — **11 passed** (boundary values
  40/41/160/161/400/401, `None`, negative, non-numeric).
- `pytest tests/test_interface_programme_rollup.py` — **6 passed**: zero
  work packages sums to a real `0.0` (not "missing"); a NULL-cost work
  package is excluded from the sum and counted separately; a NULL
  `investment_budget` yields `headroom is None` and `over_budget is None`
  (not `0`/`False`); `over_budget is True` and `headroom` goes negative when
  committed cost exceeds budget; a work package linked to two gaps is
  counted once, not twice; a cross-org work package never contributes to
  either org's rollup (proves the ORM-relationship traversal, not just the
  base query, holds the tenant boundary).
- `pytest tests/test_work_package_service.py` — **6 passed**: cost/effort
  set correctly from string form input; blank fields persist as `NULL`, not
  `0`; a blank name falls back to a real default naming the gap; a
  non-numeric cost raises `InterfaceRegisterError` mentioning "numeric"; an
  unknown `gap_id` raises "not found"; a plain capability-shortfall `Gap`
  (default `gap_kind`) is rejected the same way an unknown id is — the
  vocabulary boundary holds.
- `pytest tests/test_gap_kind_enforcement.py tests/test_interface_plateau_pair.py
  tests/test_interface_gap_service.py tests/test_interface_register_service.py
  tests/test_effort_bands.py tests/test_interface_programme_rollup.py
  tests/test_work_package_service.py tests/test_interface_gap_capability_gap_isolation.py`
  (together, to catch order-dependent interference per this repo's own
  memory-noted lesson) — **48 passed**.
- **Browser walkthrough** —
  `pytest tests/smoke/test_archetype_journeys.py::test_solution_architect_attaches_costed_work_package_and_costing_rollup_updates`
  — **1 passed**. Real Playwright session, real Postgres-backed live server,
  logged in as `solution_architect`: sets a real £100,000 budget directly on
  the seeded initiative, registers an interface, raises a gap, records the
  costing screen's baseline committed-cost text, fills and submits the real
  rendered attach-work-package form on the comparison page with a £250,000
  cost, **reloads the comparison page** and confirms the work package
  persisted, **reloads the dedicated costing screen** (a different route,
  not the same page re-rendering) and asserts the displayed total changed
  and reflects £250,000, asserts the over-budget badge+text indicator now
  shows, and asserts the em-dash renders for the work package's size column
  since no effort hours were ever supplied. This is the exact US-6 AC6
  acceptance criterion, clicked, not asserted from source.
- Also re-ran alongside the two existing Task 03 browser journeys
  (`test_solution_architect_provisions_plateau_pair_and_raises_gap`,
  `test_comparison_page_renders_a_gap_with_null_gap_type`) — **3 passed**,
  no interference from the new form/route added into the same template.
- `pytest tests/smoke/test_authorisation_matrix.py -k "interface_register or
  archetype_reaches_exactly"` — **33 passed, 14 deselected** — the new
  `/interface-register/costing` `POLICY` row is picked up automatically (the
  test file iterates `POLICY.items()`), and the full-policy
  "archetype-reaches-exactly-what's-permitted" sweep is unaffected.

**Not run this round:** the bare `python scripts/verify.py` (full,
unfiltered, DB-gated gates included) — consistent with every prior round in
this bucket's own disclosed time-budget constraint on this hardware (a full
run measured ~78 minutes in Task 03's Round 2). `--tag static` (48/48) plus
the direct, targeted `pytest` runs above (which include every DB-dependent
test this diff could plausibly affect, run together to catch
order-dependence) is the evidence offered instead, following this bucket's
own established disclosure pattern rather than silently omitting it.

## Adversarial self-review (things a refuter would probe)

- **NULL `estimated_cost`**: proven excluded from the sum and counted
  separately, at both the service level
  (`test_null_estimated_cost_excluded_from_sum_and_counted`) and the browser
  level (the work package attached in the smoke test has cost but
  deliberately no effort hours, to independently prove the em-dash path for
  the *other* nullable field the UI displays).
- **Rollup read from two routes**: there is exactly one route
  (`/interface-register/costing`) rendering the rollup; the comparison page
  shows attached work packages per-gap (a different view: "what's attached
  to *this* gap") but does **not** compute or display a separate total — it
  reuses `gap.work_packages` for per-row display only, never sums anything
  itself. `grep -rn "estimated_cost"` above confirms the arithmetic exists
  in one place.
- **Double-submit**: attaching a work package twice with the same form state
  creates two distinct `WorkPackage` rows, each correctly summed — this is
  the *correct* behaviour for "add a costed line item" (unlike plateau
  provisioning, this is not meant to be idempotent; two work packages
  against one gap is a legitimate real-world state, e.g. build + test
  packages against the same interface gap). Not treated as a bug.
- **Investment budget on the shared seeded fixture**: `investment_budget` is
  `NULL` on `seeded["ids"]["interface_register_initiative"]` by default (used
  by every other journey in this file). The new test sets a real budget
  directly on that row via a short-lived app context, inside the test itself
  — not by editing `tests/smoke/conftest.py`, which would have changed the
  starting state for every other journey sharing that fixture.
- **`effort_band` registration import graph**: registering the filter from
  `app/template_helpers.py` (per ADR 0011) rather than the module's own
  `register(app)` means importing `template_helpers` now transitively
  imports the whole `interface_register` package (parent `__init__.py` runs
  on any submodule import). Confirmed this is inert — `size_bands.py` itself
  has zero Flask/DB imports, and the package's blueprint construction has no
  app-context dependency — but flagged here as a coupling a reader of
  `template_helpers.py` would not expect from its historical
  currency-only scope, in case refuter judges it worth a comment or a
  narrower import.

## Honest self-assessment

Submitted as `pending`, not `approved` — per this bucket's established
pattern, `refuter` makes that call independently. Likely areas for a defect
report: the `effort_band` filter's registration coupling noted above; the
attach-work-package form's numeric inputs have no client-side max/format
validation beyond `type="number"` (server-side validation via
`_parse_optional_number` is the actual guard, per this codebase's own
"never trust the browser" posture, but a very large pasted value would still
round-trip through `float()`/`int(round())` without an explicit ceiling);
and the costing screen's over-budget sentence computes
`(committed_cost - investment_budget)` inline in the template rather than
having the service pre-compute a signed "overage" figure — a second reader
implementing the same subtraction elsewhere would technically violate
store-agreement in the way `headroom` (already computed in the service) does
not.

No git commit was made — left uncommitted per instruction, for the
coordinator to review.

## Round 2 — fixes for refuter's 6 findings

All six findings (D1–D6) plus the four lower-priority notes were fixed.
Direct `Edit` was used rather than a fresh Aider round-trip: every change was
a precise, line-scoped fix already fully specified by the refuter's report
(exact behaviour, exact file/line), leaving nothing of substance to Aider's
own judgement, and a round-trip risked introducing new drift on top of
already-reviewed Round-1 code.

1. **D1 (finite-value guard, High)** —
   `app/modules/interface_register/services/work_package_service.py`:
   `_parse_optional_number` now checks `math.isfinite(value)` *inside* the
   same `try` block that parses `float(raw)`, and raises
   `InterfaceRegisterError("... must be a finite number")` for `nan`/`inf`
   *before* any `int(round(...))` conversion runs — the as_int conversion
   moved inside the guarded path so it can never see a non-finite value.
   Confirmed `InterfaceRegisterError` subclasses `ValueError`
   (`interface_register_service.py:36`), so the original `except (TypeError,
   ValueError)` around the whole block would have silently swallowed the new
   guard's own raise and reported "must be numeric" instead of "must be a
   finite number" — caught this while running the new tests (first attempt
   failed exactly this way) and restructured so the `float()` parse has its
   own narrow `try/except`, with the finite/negative checks unwrapped
   afterward.

2. **D2 (reject negative values, High)** — same function: after the finite
   check, `value < 0` raises `InterfaceRegisterError("... must not be
   negative")`. Added
   `tests/test_work_package_service.py::test_attach_work_package_rejects_nan_cost`,
   `::test_attach_work_package_rejects_infinite_effort`,
   `::test_attach_work_package_rejects_negative_cost`,
   `::test_attach_work_package_rejects_negative_effort` — all four assert a
   clean `InterfaceRegisterError` (never a 500).

3. **D3 (cross-initiative gap attachment, Medium)** —
   `attach_work_package_to_gap` now takes an `initiative_id` keyword. When
   given, it resolves the initiative's actual To-Be plateau via
   `plateau_pair_service.get_plateau_pair(initiative_id)` and rejects with
   `InterfaceRegisterError("Gap does not belong to this initiative")` unless
   `gap.target_plateau_id == to_be.id`. `comparison_routes.py::attach_work_package`
   now passes the form's `initiative_id` through.
   Added `test_attach_work_package_rejects_gap_from_different_initiative`:
   creates two initiatives/gaps in the same org, proves gap B cannot be
   attached under initiative A's id, and proves the correct pairing still
   succeeds.

4. **D4 (import-failure blast radius, Medium)** — `app/template_helpers.py`
   no longer imports `effort_band` at module level. The import moved inside
   `register_template_filters()`, wrapped in its own `try/except Exception`
   that logs a warning and continues — so a future failure anywhere in
   `interface_register` costs exactly the `effort_band` filter, not
   `currency`/`number_format`/`percent`/`file_size`/etc. for the entire app.
   Every other filter's registration is untouched and still registers
   unconditionally.

5. **D5 (duplicate headroom arithmetic, Medium)** —
   `programme_rollup_service.py` now returns `overage` (`committed_cost -
   investment_budget` when `over_budget`, else `None` — computed once,
   alongside `headroom`, never independently). `costing.html`'s over-budget
   sentence renders `rollup.overage` instead of recomputing the subtraction
   inline, removing both the store-agreement risk and the `TypeError` when
   `investment_budget` is `None`.

6. **D6 (double-submit guard, Low)** — the attach-work-package form in
   `comparison.html` now uses this repo's existing Alpine pattern (matched
   against `solutions/transformation_room/objective.html`):
   `x-data="{ submitting: false }" @submit="submitting = true"
   @pageshow.window="submitting = false" :aria-busy="submitting"` on the
   `<form>`, and `:disabled="submitting"` plus a swapped "Attaching…" label
   on the button. CSP-safe (no inline `onclick=`).

**Lower-priority notes, all addressed:**
- `costing.html` and `comparison.html` now use the `dash` filter
  (`app/utils/template_utils.py:121`) everywhere a work-package/rollup value
  can be `None`, replacing the inline `if ... else '—'` ternaries and the
  bare `| default('—', true)` after `effort_band` (which was already
  slightly wrong — `default` only fires on `Undefined` without its second
  arg, so it happened to work only because `effort_band(None)` returns Python
  `None`, not `Undefined`; `dash` handles both correctly per its own
  docstring).
- `programme_rollup_service.py` now also returns
  `work_packages_missing_effort`, matching the existing
  `work_packages_missing_cost` pattern (a count, not a `None`-vs-`0`
  redesign, to stay consistent with the established convention rather than
  introduce a second one).
- `tests/smoke/test_accessibility_audit.py` run: **4 passed**, no new
  violations from the newly-labelled cost/hours/name inputs (each now has an
  associated `sr-only` `<label for>` rather than a placeholder-only field).
- `python scripts/verify.py` (bare, unfiltered) was run to completion this
  round (see below) rather than only `--tag static`.

### Verification (Round 2)

- `python scripts/verify.py --tag static` — **48 passed, 0 failed, 0
  skipped**.
- `pytest tests/test_effort_bands.py tests/test_interface_programme_rollup.py
  tests/test_work_package_service.py` — **28 passed** (12 new/updated cases
  in `test_work_package_service.py`: the 4 new D1/D2 tests, the D3
  cross-initiative test, plus the pre-existing suite unaffected).
- `pytest tests/smoke/test_archetype_journeys.py::test_solution_architect_attaches_costed_work_package_and_costing_rollup_updates`
  — **1 passed** (161s) — re-confirms the happy path still works end-to-end
  through the browser with the new validation and cross-initiative guard in
  place (this journey posts a matching `initiative_id`, so it exercises the
  D3 guard's non-rejecting branch too).
- `pytest tests/smoke/test_authorisation_matrix.py` — **47 passed** (503s,
  full file, not just the interface-register subset this time).
- `pytest tests/smoke/test_accessibility_audit.py` — **4 passed** (198s).
- `python scripts/verify.py` (bare, unfiltered, full gate list, DB-backed) —
  run to completion this round (previously not run — refuter's own finding).
  Result: **54 passed, 2 failed**:
  - `tests` — **FAILED: timed out at 3600s**. This is the harness's own
    internal timeout on the full `pytest` collection (thousands of tests
    across the whole repo, not scoped to this bucket), not a specific
    failing test — no test name or assertion failure is reported, only
    `timed out`. The five targeted `pytest` runs above, covering every file
    this diff touches or could plausibly affect (including two full smoke
    files run in their entirety, not just this bucket's rows), all passed
    cleanly. Not something a line-level fix in this diff can resolve; flagged
    for whoever owns CI/hardware runtime budget rather than silently
    reported as green.
  - `nav-verified` — **FAILED: 16 > 0** (ratchet at 0). All 16 listed routes
    (`adm_kanban_view.index`, `application_mgmt.compliance_frameworks_dashboard`,
    `architect_ui.motivation_view`, `architect_ui.traceability_matrix`,
    `consolidation_list.dashboard`, `dashboard_pages.rationalization_scorecard`,
    `enterprise.gap_analysis`, `enterprise.work_packages`,
    `error_events.errors_dashboard`, `interface_register.index`,
    `main.capability_roadmap`, `solution_design.data_stewardship`, and 4
    more) are pre-existing sidebar entries unrelated to this diff — confirmed
    via `git log` that the templates most recently touching that area
    (`traceability_chain.html`, breadcrumb work, icon fixes) predate this
    bucket's branch and none of them are Task-04 files. This diff added no
    new sidebar links. Reporting honestly rather than treating "not caused by
    me" as licence to omit — this is pre-existing repo debt this task did not
    introduce and is out of this brief's scope to fix.

Both failures are disclosed rather than hidden; neither is a regression
introduced by the D1–D6 fixes or their tests, and none of the six findings'
own fixes are implicated in either.

approval_status remains `pending` — refuter's call, not builder's. No git
commit made this round either, per instruction.

## Round 3 — fix for refuter's D7

Refuter's round 2 review confirmed D1–D6 all genuinely fixed and found one
new defect, D7 (Medium, required fix).

**D7** — `app/models/implementation_migration.py:140`,
`estimated_effort_hours = db.Column(db.Integer)` is Postgres `int4`, max
`2,147,483,647`. `_parse_optional_number(..., as_int=True)` validated finite
and non-negative but had no ceiling, so a value above int4's range (e.g. a
typo of `3000000000`, which the `<input type="number" step="1" min="0">`
with no `max` happily lets the browser submit) parsed successfully, built a
`WorkPackage`, and only failed at `db.session.commit()` with
`psycopg2.errors.NumericValueOutOfRange` — a `DataError`, not an
`InterfaceRegisterError`, which `comparison_routes.py`'s
`except InterfaceRegisterError` does not catch. Unhandled 500 instead of a
clean validation flash.

Fix (grepped the codebase first for an existing hours-validation convention
— none found, so used the column's own storage ceiling directly):

1. `app/modules/interface_register/services/work_package_service.py` — added
   a module-level `MAX_INT4 = 2_147_483_647` constant with a comment
   explaining why (Postgres int4 ceiling for the `db.Integer` column). In
   `_parse_optional_number`, after the existing `as_int` rounding, the
   resulting integer is checked against `MAX_INT4` and raises
   `InterfaceRegisterError(f"Estimated effort hours must be {MAX_INT4:,} or
   less")` when exceeded — same clean-error shape as every other validation
   branch in this function (D1/D2), so `comparison_routes.py`'s existing
   `except InterfaceRegisterError` catches it without any route change
   needed.
2. `app/modules/interface_register/templates/interface_register/comparison.html`
   — added `max="2147483647"` to the `estimated_effort_hours` input,
   matching the server-side rule as a client-side hint (server-side remains
   the actual guard, per this codebase's "never trust the browser" posture
   already noted in the Round-1 self-review).
3. `tests/test_work_package_service.py` — added
   `test_attach_work_package_rejects_effort_hours_above_int4_ceiling`,
   posting `estimated_effort_hours="3000000000"` and asserting
   `InterfaceRegisterError` is raised with the ceiling value in the message
   — the exact regression test that would have caught D7 (proves the error
   is caught before `db.session.commit()` is ever reached, not just that
   *a* error occurs).

Direct `Edit` was used — the fix is a small, precise addition to an
already-reviewed function (D1/D2 established the exact error-raising shape
to match) and a one-line template attribute, not enough surface for a fresh
Aider round-trip to add value over risk.

### Verification (Round 3)

- `pytest tests/test_work_package_service.py tests/test_effort_bands.py
  tests/test_interface_programme_rollup.py` — **29 passed** (the 1 new D7
  test plus the full pre-existing suite for this bucket's write/read paths,
  unaffected).
- `python scripts/verify.py --tag static` — **48 passed, 0 failed, 0
  skipped**.
- `pytest tests/smoke/test_archetype_journeys.py::test_solution_architect_attaches_costed_work_package_and_costing_rollup_updates`
  — **1 passed** (127s) — confirms the happy path (£250,000 cost, no effort
  hours) still round-trips end-to-end through the real rendered form with
  the new ceiling check in place; this journey never approaches the int4
  boundary, so it's a non-regression check, not a D7-specific one — that's
  what the new unit test is for.

approval_status remains `pending` — refuter's call. No git commit made this
round either, per instruction.
