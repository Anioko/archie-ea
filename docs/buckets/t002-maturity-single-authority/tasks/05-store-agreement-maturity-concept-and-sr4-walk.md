# Task 05 — Register the maturity concept in `store-agreement`, walk SR-4, write the build report

## Objective
Make the maturity authority **measurable** by registering a maturity concept in the `store-agreement`
gate's registry, drive the SR-4 reader surfaces in a browser before and after the first projection run,
and write T-002's build report.

## Context
Depends on tasks 01-04.

**The brief's acceptance criterion 10 is not satisfiable as written, and this task is the correction.**
`scripts/check_store_agreement.py`'s `CONCEPTS` registry (`:129-161`) contains exactly three concepts —
`capabilities` (population counts across `orm:BusinessCapability`, `orm:UnifiedCapability`,
`GET /dashboard/api/capabilities`, `GET /api/v1/capabilities/`), `applications`, and `gaps`. There is
**no maturity concept**. The gate is registered in `scripts/verify.py:1623-1632` (tags `["boot","db"]`,
not `static`) and `verification_baseline.json` carries `"store_agreement": 1` — that `1` is a
**capability-count** disagreement, not a maturity one. Do not claim "the maturity ratchet moved 1 → 0"
against it; that would be exactly the "a large number that means nothing" failure CLAUDE.md warns about.

The registry's own comment block (`:163-178`) is the model to follow: a concept that would manufacture
findings is named as a deliberate exclusion rather than added hollow. A maturity concept is legitimate
because, after tasks 01-04, every surface genuinely answers one question from one row.

**SR-4 is 18 route files, not eight.** The brief's "eight" is stale prose carried from `CLAUDE.md`.
Verified by `rg -l "UnifiedCapability|unified_capabilities" app/**/routes/**/*.py` — 66 occurrences
across 18 files:

`app/routes/sidebar_api_hardened.py` (3), `app/routes/unified_low_priority_routes.py` (1),
`app/modules/ai_chat/routes/chat_workflows.py` (4),
`app/modules/governance/routes/consolidation_list_routes.py` (4),
`app/modules/governance/routes/capability_management_routes.py` (2),
`app/modules/governance/routes/capability_governance_routes.py` (3),
`app/modules/applications/routes/list_views.py` (5),
`app/modules/applications/routes/vendor_api_routes.py` (5),
`app/modules/solutions_strategic/v2/routes/solution_design_routes.py` (6),
`app/modules/solutions_strategic/v2/routes/solution_ai_routes.py` (3),
`app/modules/architecture/routes/architecture_assistant_routes.py` (3),
`app/modules/architecture/routes/architecture_routes.py` (1),
`app/modules/architecture/routes/arb_routes.py` (4),
`app/modules/capabilities/routes/process_routes.py` (2),
`app/modules/capabilities/routes/domain_routes.py` (1),
`app/modules/capabilities/routes/maturity_routes.py` (3),
`app/modules/capabilities/routes/mapping_routes.py` (14),
`app/modules/capabilities/routes/export_routes.py` (2).

The component extended is `scripts/check_store_agreement.py`'s existing `CONCEPTS` registry and
`tests/smoke/` — not a new checker, not a new harness.

## Constraints
- Adding a concept is an entry in `CONCEPTS` **and nothing else** (`:127`).
- Do not baseline the new concept's finding count at whatever it happens to measure. If it measures
  non-zero, that is a live disagreement: fix it or state why it is correct, per the precedent that
  baselining `store-agreement` at 0 on day one would have hidden the defect it exists to surface.
- Update `verification_baseline.json` only via `python scripts/verify.py --update-baseline`, and only
  downward. Raising a baseline is a regression requiring justification in the report.
- If a maturity concept would manufacture findings (e.g. comparing a per-event assessment count against
  a population), **do not add it** — add the named exclusion to the `:163-178` comment block instead,
  and say so in the report. A hollow entry defeats the file.
- No new store, route, screen or dependency. L0 exposes nothing.
- `CLAUDE.md`'s gate table and `docs/DELIVERY_CONTRACT.md` must not drift — the `docs-drift` gate is
  must-be-0.

## Deliverable
1. A maturity concept in `CONCEPTS`, or a documented named exclusion, per the constraint above.
2. **The SR-4 walk**: all 18 route files' user-facing surfaces opened in a browser, as a real persona
   from `ARCHETYPES` (`tests/smoke/conftest.py`), **before** the first projection run and **after**.
   Playwright is the standard here, not curl and not a source read. For each surface, state whether its
   rendering changed from empty to populated.
3. Any persona-visible route touched during T-002 gets a row in
   `tests/smoke/test_authorisation_matrix.py` stating which archetypes should and should not reach it,
   and its primary journey extends `tests/smoke/test_archetype_journeys.py`.
4. **The build report** at `docs/buckets/t002-maturity-single-authority/build-report.md`, containing:
   FR-2 → DE-5 → each test id; the before-and-after SR-4 walk for all 18 files; the `store-agreement`
   command output before and after with the exact counts; the mutation proofs from tasks 01-04 with the
   test id that went red in each; the precondition evidence from task 01; and an explicit statement of
   the three brief corrections (maturity concept absent from the registry, 18 files not 8, the
   `capability_models.py:422-423` fifth duplicate left out of scope).

## Acceptance Criteria
1. No surface in the SR-4 walk returns an error, and **no page renders a `0` where the store holds no
   value** — a capability with no maturity renders `no_maturity_recorded` from the T-001 vocabulary
   (`app/modules/intelligence/services/reason_codes.py`).
2. `python scripts/verify.py --gate store-agreement` output recorded before and after; the count did not
   rise. If the maturity concept was added and measures non-zero, the report names the disagreeing
   surfaces and the decision taken.
3. `python scripts/verify.py` **bare** (not `--tag static`) is green — a `PARTIAL RUN` line in the
   output means the evidence does not count.
4. `pytest -q` green, and `pytest tests/smoke/` green, including the new authorisation-matrix rows.
5. `gh run list --limit 5` confirms CI is green on the branch — checked explicitly, not assumed.
6. The report can point at the clicked-through journey, not at a status line. "Green and deployed" is
   necessary and not sufficient.
7. A reviewer can confirm from the diff alone that no maturity table, column or cache, and no REST
   route, template or query surface, was added by T-002 as a whole.

## Handoff Target
`refuter` for the final pre-merge gate — a real Claude refuter, not a cheaper reviewer alias, because
this touches a live production read path across 18 route files. The refuter must independently
re-run the SR-4 walk rather than reading the report's account of it. Then `release-manager`.
