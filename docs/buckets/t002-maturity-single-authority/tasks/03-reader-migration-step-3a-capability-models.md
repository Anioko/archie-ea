# Task 03 — Reader migration step 3a: `app/models/capability_models.py`, with step 3b guarded

## Objective
Repoint the **current-value** readers of `CapabilityMaturityAssessment.maturity_level`
(`app/models/capability_models.py:167`) and `.target_maturity_level` (`:180`), and the gap computation
`calculate_maturity_gap` (`:231-235`), at the task-01 accessor — **while leaving the assessment's own
historical write path, readers and trend endpoints completely intact** (step 3b).

## Context
Depends on tasks 01 and 02. This is the highest-risk step in T-002 and the one a happy-path review will
get wrong.

`CapabilityMaturityAssessment` (`app/models/capability_models.py:138-274`) is **one row per assessment
event**: `assessment_date`, `assessment_period`, `assessor_name`, `assessor_role`, `assessment_method`,
FK to `business_capability` at `:152-153`, and it already carries `TenantMixin`. It is a historical audit
trail, **not a duplicate cache**. Repointing it wholesale would redirect "what did the Q1 2024 assessment
record?" at a single current value that cannot answer the question. The distinction you are drawing:

- A read that asks **"what is this capability's maturity now?"** → repoint at the accessor.
- A read that asks **"what did assessment X record, and when, and by whom?"** → leave alone.
- `calculate_maturity_gap` (`:231-235`) and the `before_insert`/`before_update` hook
  `calculate_maturity_fields` (`:494-497`) compute a gap **within one assessment row** — that is a
  per-event derivation, and it stays. What must not survive is any caller using an assessment row as
  the answer to "current maturity".

Also verified and **explicitly out of scope** (name the exclusion in the report):
`CapabilityRoadmapItem.current_maturity_level` / `.target_maturity_level` at `:422-423`, and the
sub-dimension scores `people_/process_/technology_/data_/governance_maturity` at `:173-177`. The brief
does not name `:422-423` at all; it is a fifth duplicate, but it expresses a roadmap *plan*, not the
current value, so it is a follow-up question, not this task's.

## Constraints
- **Leave `CapabilityMaturityAssessment`'s write path, readers and trend endpoints untouched.** A
  migration that silently destroys the ability to answer a historical question is a regression even
  with every gate green.
- One commit, scoped to this step.
- No column dropped or renamed; annotate `:167` and `:180` as per-event historical values that are not
  the current-maturity authority.
- No new column, table, cache, route, template or query surface.
- Repointed readers render `no_maturity_recorded`, never `0`.
- Do not modify `app/commands/project_capabilities.py`.

## Deliverable
- Current-value readers of `:167` / `:180` repointed at the task-01 accessor; historical readers listed
  and deliberately left, each with a one-line reason in the report.
- Model annotations at `:167`, `:180`.
- Tests extending `app/modules/intelligence/tests/test_maturity_authority_readers.py`.
- Smoke-journey extension in the same diff for any repointed rendering path.

## Acceptance Criteria
1. Grep-level assertion: `maturity_level` / `target_maturity_level` from
   `app/models/capability_models.py` have no remaining **current-value** read outside the projection,
   the model file and the accessor — with `CapabilityMaturityAssessment`'s historical and trend reads
   excluded **by name**.
2. **Step 3b survives**: a test creates two assessments in different `assessment_period`s and asserts
   both are retrievable with `assessment_date` and `assessor_name` intact, and that the assessment
   write path still accepts writes.
3. A test asserts the trend readers still return **per-event rows**, not a single current value.
4. `calculate_maturity_gap` still computes within one assessment row; a test pins its behaviour.
5. Repointed readers return the authority's value, and `no_maturity_recorded` (not `0`) when absent.
6. No row deleted from `capability_maturity_assessment`: before/after row count asserted.
7. `python scripts/verify.py` (bare) green; `pytest -q` green.
8. Mutation proof: break one repointed reader, confirm the AC-5 test goes red, record the test id,
   restore.

## Handoff Target
`refuter`, then task 04. The refuter must specifically verify AC-2 and AC-3 — that assessment history
genuinely survived and was not merely left compiling — by reading the trend endpoint's output, not its
source.
