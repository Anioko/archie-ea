# Task Brief: T-002 — Capability Maturity Single Authority

## Objective
Make `unified_capabilities.current_maturity_level` / `target_maturity_level` the single maturity
authority: schedule the existing projection on a recurring job and repoint all four current-value
reader families at it, so the `store-agreement` ratchet for capability maturity moves 1 → 0, with
`CapabilityMaturityAssessment`'s historical trail left intact.

## Context
This is T-002 from a larger, already-planned SDLC pipeline (`archie-ea-four-intelligences-extension`,
tracked in a separate `sdlc-orchestrator` repo — not this one). The full, authoritative task brief for
T-002 is reproduced verbatim below; it is the actual spec, not my summary of it. Read it in full before
writing any code.

**Important prior-work correction the original brief could not have known:** since that brief was
written, PR #23 ("unified_capabilities gets a real producer") merged into this repo's `main` tonight.
It wired `app/commands/project_capabilities.py`'s existing producer into the ONE-SHOT deploy script
(`scripts/database/deploy-schema.sh`) and added write-time sync on individual capability writes — but
it did **NOT** add the recurring APScheduler-based interval job this brief's Deliverable #1 calls for
(no `app/jobs/` file, no `app/_bootstrap/extensions.py` registration), and it did **NOT** touch any of
the three reader-family model files (`app/models/capabilities.py`, `app/models/capability_models.py`,
`app/models/capability_gap_analysis.py`) that this brief's reader-migration steps 2-4 require. Verified
directly: `python scripts/verify.py --gate store-agreement` currently reads `1 <= 1`, not `0`, confirming
the reader migration has not happened. Do not re-do PR #23's already-merged deploy-script/write-time-sync
work; do not write a second producer or modify `project_capabilities.py`'s SQL, per the brief's own
constraint. Your job is: (a) the recurring scheduled job, (b) the full four-reader-family migration,
(c) everything else the brief below specifies.

---

# T-002 — L0b · Capability maturity: one authority, scheduled producer, reader migration
(verbatim from the sdlc-orchestrator pipeline's tasks/T-002-maturity-single-authority.md)

## Objective
Make `unified_capabilities.current_maturity_level` / `target_maturity_level` the single maturity authority by
scheduling the projection that already exists and repointing all four current-value reader families at it, so
the `store-agreement` ratchet for capability maturity moves 1 → 0 with assessment history left intact.

## Context
- **Design source.** `sdd-v2.md` § DA-3 (the authority, the producer, the six-step migration plan with step 3
  split), § OA-3 (the projection staleness objective), § OA-5 (L0 ships before any query surface), § C-4 (one
  system of record per concept; copies declare `source_table`/`source_id`; retire with `retired_into_id`).
  `adr/ADR-005-capability-maturity-single-authority-v2.md` in full.
  `implementation-plan-v1.md` § 4 decisions D-1, D-2, D-3 and D-7, which this brief implements. (These live in
  the sdlc-orchestrator repo's bucket, not this one — if you need to check them and can't reach that repo, ask
  the coordinator rather than guessing.)
- **The four duplicate definitions, each verified this session.**
  `app/models/business_capabilities.py:66-67` (`current_maturity_level`, `target_maturity_level`);
  `app/models/capabilities.py:118-119` (`target_maturity`, `current_maturity`) — note the SDD's short name
  `capabilities.py:118-119` is ambiguous, because `app/api/v1/capabilities.py` and `app/compat/capabilities.py`
  also exist and carry neither attribute; `app/models/capabilities.py` is the file meant;
  `app/models/capability_models.py:167` (`maturity_level`) and `:180` (`target_maturity_level`), with the gap
  computation in `calculate_maturity_gap` at `:231-236`;
  `app/models/capability_gap_analysis.py:208` (`current_maturity`) and `:213` (`required_maturity_level`).
  The intended canonical pair is `app/models/unified_capability.py:193-194`, with the composite index at
  `:307`, the provenance columns `source_table`/`source_id`/`source_org_id`/`source_checksum` at `:151-158`,
  the retirement pointer `retired_into_id` at `:159-163`, and `HybridCapabilityTenantMixin` at `:47-62`
  applied at `:106`. **Re-verify all line numbers against the current checked-out code before relying on
  them — they may have drifted since this brief was written.**
- **The producer already exists — this is the central fact of this task.**
  `app/commands/project_capabilities.py` (697 lines) projects `business_capability` into
  `unified_capabilities`, writing `source_table='business_capability'`, `source_id`, `source_org_id` and an
  md5 `source_checksum` over the source row, upserting on the provenance unique key
  (`ON CONFLICT (source_table, source_id) ... WHERE source_checksum IS DISTINCT FROM EXCLUDED.source_checksum`)
  so a re-run touches only changed rows. It writes `current_maturity_level` and `target_maturity_level` among
  other columns, resolves the parent hierarchy, and self-classifies `scope='tenant'`. Its callable core is
  `run_projection(connection, *, apply, row_limit=None)` at `:521` and
  `execute_projection_with_audit(engine, *, report_path, apply, row_limit=None)` at `:607`; the CLI entry
  `flask project-capabilities` is defined at `:639-654` and registered at `app/_bootstrap/cli.py:313`.
  **Do not write a second producer.** ADR-005-v2's step 1 is satisfied by putting this one on a schedule.
- **Why the projection runs all-tenant with no tenant context, and not through `run_for_each_tenant`.**
  `_protect_reference_capability_writes` (`app/models/unified_capability.py:502-517`) returns early when there
  is no request context or `g.current_org_id` is None, and otherwise raises `PermissionError` for a
  `UnifiedCapability` whose `organization_id` differs from `g.current_org_id`. `run_for_each_tenant` sets
  `g.current_org_id` per tenant, so driving an all-tenant projection through it would refuse on the first
  foreign row. The command's own module docstring states it can only run outside a request context. The
  scheduled wrapper therefore uses `job_lock` (`app/jobs/tenant_safe_job.py:199-246`), a standalone context
  manager that takes a session-level advisory lock on a dedicated connection and sets no tenant context. This
  satisfies DR-4 in full: the producer is a **scheduled batch and explicitly not an ORM event hook**, and the
  reason DR-4 gives still holds — three raw-SQL writers update `business_capability`'s maturity columns
  directly (`app/modules/capabilities/routes/maturity_routes.py:176-185`, `:268-273`, `:311-315`) and would
  never fire an ORM event.
- **Two preconditions the projection enforces itself.** `run_projection` raises `ProjectionBlocked` unless a
  valid unique index named `uq_unified_capabilities_provenance` on `(source_table, source_id)` exists,
  directing the operator to `scripts/migrate_unified_capability_provenance.sql`; without it the projection is
  not idempotent and a re-run double-inserts. And on a pre-cutover database the plan step refuses unless
  `app/commands/cutover_capability_tenancy.CLASSIFIES_PROVENANCE_ONLY_TENANT` is truthy, because a projected
  row carries provenance but no application, benefit or work-package links and would classify as `ambiguous`,
  blocking `run_cutover` for the whole database. **PR #23 may already have satisfied one or both of these on
  this specific database — check before assuming either is still open.**
- **Step 3b, which the migration must not violate.** `CapabilityMaturityAssessment`
  (`app/models/capability_models.py:138-190`) is one row per assessment event — `assessment_date`,
  `assessment_period`, `assessor_name`, `assessor_role`, `assessment_method` and a foreign key to
  `business_capability` at `:152-154` — and it already carries `TenantMixin`. It is a historical audit trail,
  not a duplicate cache. It keeps its own write path and its own readers. Repointing it would redirect "what
  did the Q1 2024 assessment record" at a single current value that cannot answer the question.
- **Scheduler.** `init_scheduler(app)` at `app/_bootstrap/extensions.py:224-233` builds a
  `BackgroundScheduler` and returns early under `app.testing` (`:226-227`); the existing interval-job pattern
  with `max_instances=1` is at `:398-405`. **Re-verify these line numbers too.**
- **Risk carried.** SR-4: eight route files read `unified_capabilities` and today answer from an empty store;
  writing the projection changes what they return from empty to populated. That is correct and visible, and it
  is walked in a browser before and after.

## Constraints
- **Do not write a second producer, and do not modify the projection's SQL.** The permitted change to
  `app/commands/project_capabilities.py` is none; the scheduled job imports and calls its existing core. If a
  genuine defect is found in it, stop and report rather than editing, because that file is co-designed with
  `app/commands/cutover_capability_tenancy.py` and both hold interlocking advisory locks.
- **Do not create a maturity table, column or cache anywhere.** The authority is the existing column pair.
- The scheduled job must not set `g.current_org_id` and must not run inside a request context. Serialise it
  with `job_lock`; a contended lock records a skipped run rather than silently doing nothing.
- **Leave `CapabilityMaturityAssessment` alone** (step 3b). Its write path, its readers and its trend endpoints
  are untouched. A migration that silently destroys the ability to answer a historical question is a regression
  even with every gate green.
- Superseded rows are marked with `retired_into_id` — retire, never drop (step 6). No row is deleted by this
  task.
- The source columns on `business_capability` remain in place as the producer's **source**, marked as such in
  the model docstring (step 5). They are not dropped and not renamed.
- No new store, container or third-party dependency. No REST route, no screen, no new query surface: this is an
  L0 task and L0 exposes nothing.
- **Forbidden territory.** Connector configuration, review-queue and ServiceNow configuration-loader code
  (SR-11, SR-12, SR-13) are out of scope and untouched.
- Every reader repointed must read the authority through one accessor, not by copying the column name into a
  fifth place. A reader that needs both current and target reads both from the same row.
- Do not touch or re-do anything PR #23 (`scripts/database/deploy-schema.sh`'s producer wiring, write-time
  sync in `app/models/business_capabilities.py`) already merged — verify current state first, build only what's
  still missing.

## Deliverable
- A scheduled projection job: a small module under `app/jobs/` that calls
  `execute_projection_with_audit(db.engine, report_path=None, apply=True)` inside `job_lock("capability_projection")`,
  logging the returned payload, plus its registration on the existing APScheduler in
  `app/_bootstrap/extensions.py` following the `max_instances=1` interval pattern. Default interval 15 minutes,
  configurable downward.
- Precondition work, completed and evidenced rather than assumed: the
  `uq_unified_capabilities_provenance` unique index installed from
  `scripts/migrate_unified_capability_provenance.sql`, and the cutover classifier's
  `CLASSIFIES_PROVENANCE_ONLY_TENANT` condition satisfied or the projection ordered after the cutover, whichever
  the target database's state requires — evidenced by a clean `flask project-capabilities --dry-run`.
- Reader migration, one commit per step so each is separately reviewable:
  step 2 — `app/models/capabilities.py:118-119` and its readers;
  step 3a — `app/models/capability_models.py:167`, `:180` and `calculate_maturity_gap` at `:231-236` and their
  readers;
  step 4 — `app/models/capability_gap_analysis.py:208`, `:213` and their readers;
  step 5 — the direct readers of `app/models/business_capabilities.py:66-67`, with the model docstring updated
  to state that those columns are the projection's source and not a read target.
- Step 6: superseded rows carry a non-null `retired_into_id`.
- Observability: a projection-staleness signal — the count of rows whose `source_checksum` disagrees with the
  freshly computed source checksum, and the timestamp of the last successful projection run — emitted on the
  same structured-record path the rest of the module uses, so OA-3's objective is measured rather than assumed.
- Tests under `app/modules/intelligence/tests/` or the repository's conventional location for job tests:
  `test_capability_projection_job.py` and `test_maturity_authority_readers.py`.
- A build report listing FR-2 → DE-5 → each test id, the before-and-after browser walk of the eight readers
  (SR-4), the `store-agreement` ratchet value before and after, and the mutation proof with the test id that
  went red.

## Acceptance Criteria
1. `flask project-capabilities --dry-run` completes without raising `ProjectionBlocked`, and its report shows
   the provenance index present and the plan non-empty. This is the evidence both preconditions are met.
2. After one scheduled run, every `business_capability` row has a matching `unified_capabilities` row with
   `source_table='business_capability'`, a non-null `source_id` and a non-null `source_checksum`; a test asserts
   the counts agree and that no projected row has a null checksum.
3. The projection is idempotent: a second run immediately after the first writes zero rows, asserted by row
   count and by the returned payload, because every checksum matches.
4. A change to a `business_capability` maturity value made through the **raw-SQL** path — the statement shape at
   `app/modules/capabilities/routes/maturity_routes.py:176-185` — is reflected in `unified_capabilities` after
   the next projection run. This is the case an ORM event hook would miss, and it is why the producer is a
   scheduled batch.
5. The job sets no tenant context: a test asserts `g.current_org_id` is unset during the run and that the run
   completes across more than one organisation's capabilities in a single pass.
6. Lock behaviour: two concurrent invocations result in one run and one recorded skip, never two runs and never
   a silent no-op reported as success.
7. The job is not registered under `app.testing`, matching the surrounding scheduler jobs.
8. Reader migration is complete: a grep-level assertion that `target_maturity` / `current_maturity`
   (`app/models/capabilities.py`), `maturity_level` / `target_maturity_level`
   (`app/models/capability_models.py`) and `current_maturity` / `required_maturity_level`
   (`app/models/capability_gap_analysis.py`) have no remaining **current-value read** outside the projection
   and the models themselves. Historical and trend reads of `CapabilityMaturityAssessment` are excluded from
   this assertion by name, and a test asserts those reads still function.
9. `CapabilityMaturityAssessment` still receives writes and its trend readers still return per-event rows; a
   test creates two assessments in different periods and asserts both are retrievable with their
   `assessment_date` and `assessor_name` intact.
10. The `store-agreement` ratchet for capability maturity reads 1 before the change and 0 after, recorded in
    the build report with both command outputs.
11. SR-4 walk: the eight route files that read `unified_capabilities` are opened in a browser before and after
    the first projection run, and the report states for each whether its rendering changed from empty to
    populated. No page returns an error and no page renders a `0` where the store holds no value — a capability
    with no maturity renders the `no_maturity_recorded` reason from the T-001 vocabulary, never a zero.
12. Projection staleness is observable: the checksum-disagreement count and the last successful run timestamp
    are emitted and readable, so the OA-3 objective — 95% of source maturity changes reflected within one
    projection cycle — can be measured rather than asserted.
13. Mutation proof, recorded with the test id that went red: disable the scheduled job's registration and
    confirm item 4 goes red; re-enable it.
14. Superseded rows carry a non-null `retired_into_id`; no row was deleted by this task, asserted by a
    before-and-after row count on both tables.
15. No maturity table, column or cache was created; no REST route, template or query surface was added. A
    reviewer can confirm this from the diff alone.
16. The existing test suite is green, including the capability route tests whose rendering changed under SR-4.

## Handoff Target
`tech-lead` first — verify the exact current state against PR #23's merged changes and re-confirm every
path:line citation above against the current checked-out code (they may have drifted), scope into concrete
task file(s) under `docs/buckets/t002-maturity-single-authority/tasks/`. Then standard `builder` → `refuter`
cycle, same rigor as every other bucket tonight — this touches a live production read path across eight
route files, no shortcuts. The refuter must specifically check item 4 (raw-SQL write path), item 9
(assessment history survived), and item 11 (before-and-after walk), since each is a path a happy-path review
would not reach.
