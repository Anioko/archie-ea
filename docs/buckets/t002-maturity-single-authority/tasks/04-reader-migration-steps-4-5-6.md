# Task 04 — Reader migration steps 4, 5 and 6: gap analysis, the source model, and retirement

## Objective
Complete the reader migration: repoint `app/models/capability_gap_analysis.py`'s current-value readers
(step 4), repoint the direct readers of `app/models/business_capabilities.py:67-68` and mark those
columns as the projection's **source, not a read target** (step 5), and mark every superseded row with a
non-null `retired_into_id` (step 6).

## Context
Depends on tasks 01, 02, 03.

Verified current state:
- `app/models/capability_gap_analysis.py:208` `current_maturity = Column(db.Integer, default=1)` and
  `:213` `required_maturity_level = Column(db.Integer, default=3)`, both serialised at `:305` and `:308`.
  **Note the `default=1` / `default=3`** — these are exactly the invented-data defaults that
  `business_capabilities.py:61-66` documents having removed. Repointing these readers is also the fix
  for a fabricated value; call that out in the report.
- `app/models/business_capabilities.py:67-68` `current_maturity_level` / `target_maturity_level`, now
  `nullable=True` with no default after PR #23, `:69` `maturity_gap`, `:70`
  `maturity_assessment_date`, `:71` `maturity_assessment_notes`. These are the **producer's source** —
  `project_capabilities.py` reads them and the write-time listeners at `:778-790` mirror them. They stay.
  Note `business_capabilities.py:180-181` serialises them in `to_dict()`; decide deliberately whether
  that serialiser is a source read (fine) or a current-value read (repoint), and record which.
- `retired_into_id` on `app/models/unified_capability.py:159-163`, with the self-referential
  relationship at `:274` (`foreign_keys=[retired_into_id]`).
- The three raw-SQL writers that must keep writing the source:
  `app/modules/capabilities/routes/maturity_routes.py:177-199`, `:269-273`, `:313-318`.

## Constraints
- **Do not drop or rename `business_capabilities.py:67-68`.** They remain in place as the producer's
  source, marked as such in the model docstring.
- **Retire, never drop.** No row is deleted by this task, on any table. Superseded rows get
  `retired_into_id`; nothing is removed.
- `retired_into_id` is an existing nullable column — do not add a new one. Per CLAUDE.md's schema rules
  the only safe new column is nullable/defaulted, and none is needed here.
- The raw-SQL writers in `maturity_routes.py` keep writing `business_capability`; they are the source
  path the scheduled job exists to catch. Do not repoint them at `unified_capabilities`.
- No new column, table, cache, route, template or query surface. Forbidden territory (SR-11/12/13)
  untouched.
- Repointed readers render `no_maturity_recorded`, never `0` — this matters most here, given the
  `default=1` / `default=3` above.
- One commit per step (4, 5, 6) so each is separately reviewable.

## Deliverable
- Step 4: every current-value reader of `capability_gap_analysis.py:208` / `:213` repointed at the
  task-01 accessor; the columns annotated as superseded; their `default=1` / `default=3` addressed
  (removed or documented as unreachable) so no fabricated maturity survives.
- Step 5: the direct readers of `business_capabilities.py:67-68` repointed; the `BusinessCapability`
  docstring (`:31-37`) updated to state plainly that these columns are the projection's source and not
  a read target, naming the accessor as the read path.
- Step 6: superseded rows carry a non-null `retired_into_id`, applied through a reversible,
  measured-before-and-after operation, with the before/after counts recorded.
- Tests extending `app/modules/intelligence/tests/test_maturity_authority_readers.py`.
- Smoke-journey extension in the same diff for any repointed rendering path.

## Acceptance Criteria
1. Grep-level assertion: `current_maturity` / `required_maturity_level` from
   `app/models/capability_gap_analysis.py` have no remaining current-value read outside the projection,
   the model file and the accessor.
2. A test asserts a gap-analysis surface with no recorded maturity returns `no_maturity_recorded`, not
   `1` and not `3` — i.e. the old defaults can no longer reach a user.
3. `business_capabilities.py`'s docstring states the source-not-read-target role; a reviewer can
   confirm the columns are still declared and still written by the raw-SQL path.
4. A raw-SQL update through the `maturity_routes.py:177-199` shape still succeeds and still reaches
   `unified_capabilities` on the next scheduled run (re-assert task 01's AC-4 after step 5).
5. Superseded rows carry a non-null `retired_into_id`; **no row was deleted by this task**, asserted by
   a before-and-after row count on both `business_capability` and `unified_capabilities`.
6. No maturity table, column or cache created; no REST route, template or query surface added — a
   reviewer can confirm this from the diff alone.
7. `python scripts/verify.py` (bare) green, including `fabricated-data` and `schema-drift`;
   `pytest -q` green, including the capability route tests whose rendering changed.
8. Mutation proof: break one repointed reader, confirm AC-2 goes red, record the test id, restore.

## Handoff Target
`refuter`, then task 05. The refuter must verify AC-5 by row count rather than by the diff, and AC-4 by
executing the raw-SQL shape rather than reading it.
