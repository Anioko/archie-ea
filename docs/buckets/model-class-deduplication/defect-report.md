# Refuter defect report — PR #20 (commit 424162db / 9cfe2af6)

**Status: this bucket had NO builder-to-refuter handoff before PR #20 merged.**
The builder (this session) reviewed its own diff and merged without an
independent pass — the exact single-developer failure mode the SDLC roster
exists to prevent. Called out directly by the repo owner; corrected by
running a genuinely independent review after the fact (fresh agent context,
no memory of authoring the diff, read-only tools only, instructed to hunt for
defects against the actual code and task briefs, not against a provided
summary).

## Defect found (CONFIRMED, fixed in a follow-up commit)

**`app/services/motivation_bridge_service.py` silently creates
permanently-invisible Outcome and Principle rows on every `flask
bridge-motivation` run against a multi-org install.**

- `motivation_bridge_service.py` runs exclusively under the `flask --app
  manage bridge-motivation` CLI — no Flask request context (the module's own
  docstring says so).
- `_create_archimate_element()` already handled this correctly: it takes
  `organization_id` explicitly, with a comment explaining that
  `TenantMixin`'s `_default_org_id()` (`app/models/mixins/core.py`) can only
  guess an org when exactly one exists, and returns `None` on any multi-org
  install.
- `_find_or_create_outcome()` and `_find_or_create_principle()` did **not**
  apply the same pattern: they built `Outcome(...)`/`Principle(...)` without
  passing `organization_id`, even though both already receive `org_id` as a
  parameter.
- Before PR #20, this was harmless — neither model had `TenantMixin`. PR #20
  gave both `TenantMixin` with `organization_id` nullable (matching the
  existing `Principle` pattern in `models.py`), which meant the INSERT no
  longer raises on a multi-org install — it silently writes
  `organization_id = NULL`.
- Net effect: every future `bridge-motivation` run on a multi-org install
  would create rows invisible to every tenant-scoped view (`organization_id
  = g.current_org_id` never matches `NULL`) — actively growing the exact
  backlog `app/commands/backfill_outcome_org.py` exists to drain, with zero
  error signal.
- This was a **regression introduced by PR #20's own diff**, not a
  pre-existing gap: the diff's author (this session) clearly understood the
  hazard (wrote the comment on `_create_archimate_element`) but didn't apply
  the same fix to the two model constructors the same diff made
  tenant-scoped.

**Fix**: pass `organization_id=org_id` in both constructors, matching
`_create_archimate_element`'s existing pattern. Evidence in
`tests/test_motivation_bridge_org_scoping.py` — two tests, each demonstrated
red-then-green against the actual pre-fix/post-fix code.

**A subtlety in the test itself, worth recording**: the first two versions of
this test passed against the *broken* code, for two different accidental
reasons, before a genuinely red result was achieved:
1. `_default_org_id()`'s single-org fallback silently "fixed" the row
   whenever the test database happened to hold exactly one organization at
   that moment — masked by adding a second, decoy organization.
2. `flask.g.current_org_id`, set inside a `tenant_ctx(...)` block used only
   to set up fixture data, leaked past that block and was still visible when
   the code under test ran — this repo's own `tests/conftest.py` documents
   the identical trap for `login_as`. Fixed by explicitly clearing
   `g.current_org_id` before the assertion.

This second point is itself evidence for the report above: a review that
only reads the diff, without actually running it red-then-green, would not
have caught this.

## Reviewed and found sound

- `ApplicationComponent` (`app/models/application_component_fast.py`): gets
  `TenantMixin` only, not `OptimisticLockMixin`, as the task brief specifies.
  No code was found that assumes both mixins are always present together.
- `app/commands/backfill_outcome_org.py`: both `UPDATE` statements are
  correct. The scenario "parent row itself has NULL organization_id" cannot
  occur — `archimate_elements.organization_id` and
  `architecture_models.organization_id` are both `TenantMixin` `NOT NULL`
  columns, so the join can never propagate a NULL. Idempotency and
  dry-run/rollback handling are correct.
- The `organization_id` nullable override on `Outcome` is identical in both
  `app/models/models.py` and `app/models/motivation_extended.py` — no
  divergence.
- Each task's diff hunk stays confined to its own declared file/class scope;
  `models.py` is touched only for the `Outcome` fix, as intended.
- `ArchiMateRelationship`/`Principle` fast-init additions correctly match
  their siblings' existing pattern.

## Not yet independently re-reviewed

The fix for the defect above (the `motivation_bridge_service.py` change and
its test) has not itself been through a second independent refuter pass —
only self-verified with red-then-green evidence, the same limitation this
report exists to flag. Recommend a follow-up pass before treating this bucket
as fully closed.
