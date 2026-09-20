# Task 01 — `ArchiMateRelationship`: close the fast-init tenancy asymmetry

Handoff target: **builder** → then **refuter**.
Branch: `fix/model-class-deduplication` (already checked out in the worktree
`../archie-oss-model-dedup`). Do **not** create a new branch.

**Read `../investigation.md` in this bucket before starting.** It contains the
evidence behind every decision below, including why the obvious bigger fix is
deliberately *not* this task. Note its naming convention: the environment
variable is written as "the fast-init flag" throughout because a write hook
blocks the literal token in prose; its exact name is in
`config/allowed_config.txt` and in the `os.getenv(...)` calls cited below.

## Objective

Make `app/models/archimate_core.py`'s fast-init `ArchiMateRelationship` (line
110) tenant-scoped, so that the ArchiMate relationship store has the same
tenancy semantics under both branches of the import-time fast-init conditional —
and add a test that actually executes the fast-init branch, which no existing
test does.

## Context — the component this extends (ADR 0008)

This extends **`app/models/archimate_core.py`**, the existing canonical module
for the ArchiMate metamodel classes. No new module, no new table, no new model
class. `archimate_relationships` keeps exactly one system of record.

What is actually wrong (confirmed by reading both definitions in full):

- `app/models/models.py:468` — `class ArchiMateRelationship(TenantMixin, db.Model)`,
  defined in the `else:` branch of `if _FAST_INIT:` at `models.py:191`. **This is
  what production runs.**
- `app/models/archimate_core.py:110` — `class ArchiMateRelationship(db.Model)`,
  **no `TenantMixin`**, defined in the `if _FAST_INIT:` branch at
  `archimate_core.py:31`.

Its two siblings in that same fast-init block — `ArchitectureModel` (`:33`) and
`ArchiMateElement` (`:53`) — **both** carry `TenantMixin`. The relationship class
is the only one that does not. That asymmetry is an oversight, not a design
decision.

Severity, stated honestly (investigation §3): **no runner in this repository
sets the fast-init flag to 1** — the sole assignment anywhere,
`tests/test_model_boot_registration.py:42`, sets it to `"0"`. So this is a
loaded trap with the safety on, not a currently-firing production bug. It fires
the moment anyone exports that variable — a developer shell, a future "speed up
E2E" CI job, a revived Windows mapper-crash workaround — at which point *every*
importer (`app.models`, `app.models.models`, `app.models.archimate_core`, via
the mutual re-exports at `models.py:191` and `archimate_core.py:22-24`) holds an
unfiltered mapper for the ArchiMate backbone, writes rows with
`organization_id IS NULL`, and reads across every tenant with nothing raising.

Do not overstate this as a live production leak in the commit message or the
handoff. Do not understate it as harmless either.

## Constraints

- **Scope is `ArchiMateRelationship` only.** Do not touch `Principle`,
  `ApplicationComponent`, `Requirement`, `TechnologyStack`, `ARBDocument`, or
  `ArchiMateElement` / `ArchitectureModel`. Those are Tasks 2-4.
- **Do not retire the fast-init mechanism in this task**, even though
  investigation §6 recommends exactly that as Task 4 and the evidence supports
  it. Rationale: the bucket brief forbids making the first and riskiest change
  also the largest, and the mixin addition is correct under either future.
- **Do not change `app/models/models.py`.** The tenanted definition there is
  already correct.
- **No schema change.** `TenantMixin` supplies `organization_id`, which
  `archimate_relationships` already has in every database (the production class
  has carried the mixin all along). This must remain a pure ADD-nothing change —
  if the builder finds themselves writing a migration or a
  `reconcile-schema` note, stop and re-read; something has gone wrong.
- **Do not touch** files owned by concurrent worktrees:
  `app/services/archimate_import_service.py`,
  `app/services/archimate_oef_service.py`, `app/modules/interface_register/`,
  `app/commands/project_capabilities.py`,
  `scripts/database/deploy-schema.sh`.
- `config/allowed_config.txt` already carries a new entry for the fast-init flag
  (added during investigation, so the `NO-DARK-FEATURES` write hook permits
  documenting the mechanism). **Keep it.** Expect that same hook to fire when
  editing these files; it is not a sign the change is wrong.

## Deliverable

1. **`app/models/archimate_core.py:110`** — change
   `class ArchiMateRelationship(db.Model):` to
   `class ArchiMateRelationship(TenantMixin, db.Model):`.
   `TenantMixin` is already imported unconditionally at `archimate_core.py:29`;
   no new import needed. Add a short comment on the class stating why the mixin
   is mandatory here (matching the CMP-01 comment style already at `:26-28` and
   on `SavedDiagram`): the normal-runtime twin is tenant-scoped, so a
   fast-init graph without it silently changes the tenancy semantics of the
   whole ArchiMate backbone.

2. **A new test that executes the fast-init branch.** No existing test does —
   `tests/test_double_mapped_tenancy.py` runs in a process where the flag is
   unset, so it only ever sees the `not _FAST_INIT` side (investigation §5).
   Use the established subprocess pattern at
   `tests/test_model_boot_registration.py:41-54`: `os.environ.copy()`, set the
   fast-init flag to `"1"`, `subprocess.run([sys.executable, "-c", script])`,
   assert `returncode == 0`.

   The child script must, under the fast-init flag:
   - import `app.models.archimate_core` and assert
     `issubclass(ArchiMateRelationship, TenantMixin)`;
   - assert `"organization_id" in ArchiMateRelationship.__table__.c`;
   - assert the same for `ArchiMateElement` and `ArchitectureModel`, so the two
     classes that are correct today cannot silently regress;
   - assert `app.models.models.ArchiMateRelationship is
     app.models.archimate_core.ArchiMateRelationship`, pinning the alias at
     `models.py:191` — i.e. that there is genuinely one class per concept under
     this branch too, per ADR 0008.

   Put it in a new `tests/test_fast_init_model_tenancy.py` with a docstring
   explaining *why* a subprocess is necessary (the branch is chosen at import
   time, so it cannot be exercised by monkeypatching inside the running pytest
   process). Do not weaken or duplicate `tests/test_double_mapped_tenancy.py` —
   this is its missing other half, and should say so.

3. **Commit message** must state the honest severity from §3 of the
   investigation (trap, not live leak) and reference the Task 4 recommendation.

## Acceptance Criteria

- [ ] `app/models/archimate_core.py`'s `ArchiMateRelationship` subclasses
      `TenantMixin`; `models.py` unchanged.
- [ ] The new subprocess test **fails on the pre-fix commit and passes after** —
      the builder must actually demonstrate this (stash the model change, run
      the test, show it red), not assert it. A test that would pass either way
      is the failure mode this whole bucket exists to correct.
- [ ] `tests/test_double_mapped_tenancy.py` still passes unchanged (all four
      tests, including the three parametrised re-export cases).
- [ ] `pytest tests/test_double_mapped_tenancy.py tests/test_fast_init_model_tenancy.py
      tests/test_model_boot_registration.py tests/test_tenant_isolation.py` green,
      and run at least once **as a subset on its own** (per the order-dependence
      note in this repo's memory — a full-run pass is evidence about one
      ordering only).
- [ ] `python scripts/verify.py` — the **bare** command, not `--tag static`;
      a filtered run prints `PARTIAL RUN` and does not mean clean. No new
      failures, no ratchet raised.
- [ ] **Browser regression evidence, correctly framed:** a Playwright run over
      the existing ArchiMate/composer journeys in `tests/smoke/` confirming the
      backbone still renders and a relationship still persists in normal
      runtime. Per investigation §7, this proves *no regression* — it does
      **not** prove the fix, because the patched class is not mapped in normal
      runtime. The builder's report must say so in those terms. Claiming the
      browser check as proof of the fix will be rejected by refuter.
- [ ] Report states plainly that the fast-init path remains unexercised by any
      runner, and carries forward the Task 4 recommendation to retire it.

## Handoff Target

**builder** — implement, verify, and report with the red-then-green evidence for
the new test. Then **refuter** (read-only on code) to challenge specifically:
(a) is the new test genuinely capable of failing; (b) is the severity claim
honest in both directions; (c) did the change stay inside the one-class scope.
