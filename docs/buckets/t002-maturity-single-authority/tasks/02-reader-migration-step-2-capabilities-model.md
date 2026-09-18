# Task 02 — Reader migration step 2: `app/models/capabilities.py`

## Objective
Repoint every **current-value** reader of `EnterpriseCapability.target_maturity` /
`.current_maturity` (`app/models/capabilities.py:118-119`) at the task-01 accessor on
`UnifiedCapability`, leaving the columns themselves in place and marked as superseded.

## Context
Depends on task 01 (accessor + scheduled producer) being merged and green. ADR-005-v2's migration step 2.

Verified current state in this worktree:
- `app/models/capabilities.py:118` `target_maturity`, `:119` `current_maturity`, `:120` `maturity_gap`
  — all on the same model, all Integer, no defaults documented as measured.
- **Out of scope, do not touch and say so in the report**: `:243` `maturity_level` on a different model,
  and `:487-490` `process_maturity` / `technology_maturity` / `skills_maturity` /
  `governance_maturity` — these are sub-dimension scores, not the authority's column pair. Naming the
  exclusion is required; silently leaving them reads as an oversight.
- Readers are found with, at minimum:
  `rg -n "target_maturity|current_maturity" app/ --glob '!app/models/capability_models.py'` then filtering
  to those resolving to `capabilities.py`'s model. Enumerate them in the report; do not sample.

The component extended is `app/models/capabilities.py` itself plus each calling site. Per ADR 0008 rule
3, one accessor per concept — a reader needing both current and target reads **both from the same row**
through the task-01 accessor, never by re-deriving one from the other.

## Constraints
- One commit, separately reviewable, scoped to this step only.
- Columns are **not dropped and not renamed** (retire, never accumulate). Mark them in the model
  docstring/inline comment as superseded by `unified_capabilities.current_maturity_level` /
  `target_maturity_level`, with the accessor named.
- No new column, table or cache. No new route, template or query surface.
- A reader that currently renders `0` for an unknown maturity must, after repointing, render the T-001
  `no_maturity_recorded` reason code — the em-dash/`—` rule and CLAUDE.md's "never invent data" rule
  both apply. A `0` that means "not computed" is a defect, not a migration detail.
- `CapabilityMaturityAssessment` is untouched by this task.
- Do not modify `app/commands/project_capabilities.py`.

## Deliverable
- Every current-value reader of `capabilities.py:118-119` repointed at the task-01 accessor.
- The two columns annotated as superseded, in place.
- An exhaustive enumeration of the readers found and what each now reads, in the build report — a
  full-tree scan, not a sample.
- Test coverage in `app/modules/intelligence/tests/test_maturity_authority_readers.py` (created here,
  extended by tasks 03/04).
- If any repointed reader renders in a template, the corresponding `tests/smoke/` journey is extended
  in the same diff — the `smoke-coverage-on-change` gate is must-be-0 and will block otherwise.

## Acceptance Criteria
1. A grep-level assertion (a real test, not a report claim) that `target_maturity` / `current_maturity`
   from `app/models/capabilities.py` have **no remaining current-value read** outside the projection,
   the model file itself, and the accessor. Historical/trend reads of `CapabilityMaturityAssessment`
   are excluded **by name** in the assertion.
2. A test asserts each repointed reader returns the authority's value for a capability with maturity,
   and `no_maturity_recorded` — not `0` — for one without.
3. No row deleted, no column dropped: a before/after row count on `capabilities`-backed tables, and a
   diff review confirming column declarations are still present.
4. `python scripts/verify.py` (bare) green, including `fabricated-data`, `smoke-coverage-on-change`
   and `store-agreement`. `pytest -q` green.
5. Mutation proof: break the accessor call in one repointed reader, confirm the AC-2 test goes red,
   record the test id, restore.

## Handoff Target
`refuter`, then task 03. The refuter checks the grep assertion cannot pass vacuously (it must fail if a
reader is added back) and that no repointed path now renders a zero.
