# Task 7 — Transformation option and decision-brief freeze report

## Status

Implemented and focused-green. Task 7 freezes immutable, content-addressed transformation-option versions and decision-brief versions with exact evidence/option citations, authorization fencing, replay authorization, PostgreSQL serialization, append-only database guards, and explicit tenant predicates.

The repository-wide `python scripts/verify.py` run was bounded during its long full-pytest phase at the coordinator's direction and produced no final summary; it is therefore recorded as **incomplete, not green**. The scoped Transformation Room suite and the required individual verification gates are green as detailed below.

## RED

The prescribed Task 7 tests were introduced before implementation and run against PostgreSQL using `TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5439/flask_test` (with the same URL supplied as `DATABASE_URL`). Collection failed as expected:

- `tests/test_transformation_option_service.py`: `ModuleNotFoundError: app.models.transformation_decision`
- `tests/test_decision_brief_service.py`: `ModuleNotFoundError: app.models.transformation_decision`
- Result: 0 tests collected, 2 collection errors.

After the model contract was added, the next RED was the intentionally absent `app.modules.transformation_room.decision_service` implementation.

## GREEN

All database-backed commands below used the exact PostgreSQL URL `postgresql://postgres@127.0.0.1:5439/flask_test` for both `TEST_DATABASE_URL` and `DATABASE_URL`.

- Task 7 plus database guards: **47 passed** in 47.63 seconds.
- Complete Transformation Room Task 1–7/runtime-role suite: **220 passed** in 80.26 seconds.
- `schema-drift`: **1 passed, 0 failed, 0 skipped**, measurement `0 <= 0`.
- `raw-sql-tenancy`: **1 passed, 0 failed, 0 skipped**, measurement `0 <= 0`.
- `lint-core`: **1 passed, 0 failed, 0 skipped**.
- `compile`: **1 passed, 0 skipped**.
- `undefined-exports`: **1 passed, 0 failed, 0 skipped**.
- Final changed-file `ruff check`: **all checks passed**.
- Final `git diff --check`: **clean**.

The 220-test run includes the Task 3 command fencing/runtime-role tests, Task 4 discovery, Task 5 gating, Task 6 evidence/history/global-head concurrency tests, Task 7 option/brief tests, and direct database-guard tests. Warnings are existing SQLAlchemy/datetime/detached-user and ArchiMate-listener warnings; there were no failures or skips in this scoped run.

## Immutable transformation options

- A mutable `TransformationOption` root owns the stable identity and optimistic `revision`; an immutable `TransformationOptionVersion` captures a monotonic version and exact source revision.
- Canonical content includes explicit nulls, sorted JSON keys and identifiers, normalized decimal strings, currency, all assumptions/dependencies/impacts/risks, reversibility, transition, capability/value-stream links, rationale, and benefit/cost/risk ranges. SHA-256 is computed from those server-built bytes.
- Freeze locks the programme, workstream, and option root; checks current membership, current authority, expected revision, mandatory fields, currency, and finite numeric values; then inserts one immutable version and advances the root exactly once.
- Unique constraints on `(option_id, version)` and `(option_id, source_revision)` provide a final database backstop.
- Comparison accepts only exact version identifiers, enforces cardinality and tenant/workstream/candidate scope, and reads persisted version content. Duplicate/missing identifiers and client-submitted totals are rejected. Mixed currency produces an explicit conflict and null comparable range rather than a fabricated zero or conversion.

### Option-version race evidence

The PostgreSQL race test pauses the first transaction after its real `SELECT ... FOR UPDATE` on the option root, starts a second transaction, verifies that it is blocked, and then releases the first. The outcome is exactly one successful freeze, one `stale_revision` conflict, one immutable version, and one root increment to revision 2.

## Immutable decision briefs

- A mutable `DecisionBrief` root owns the stable identity and optimistic revision; `DecisionBriefVersion` is the immutable frozen snapshot.
- Freeze pins the exact recommended option version, the exact compared option versions and their canonical content, exact evidence records and head state, outcome/measure identifiers, unknowns/conflicts, expected impacts, policy/legal exception fields, human-review assertions, and freeze metadata.
- Two genuinely distinct option contents are mandatory. A single option is allowed only when a named, persisted policy/legal constraint, reason, and current authority are present. Different identifiers for identical content do not satisfy distinctness.
- AI-assisted briefs require a recorded human review and explicit acknowledgement of material unknowns. The stored acknowledgements and review note are part of the canonical payload and hash.
- One immutable option citation per exact option version, one immutable evidence citation per exact evidence record, and one immutable decision event are written atomically with the brief version and root revision.
- Altering an in-memory projection of persisted frozen content causes hash verification to fail.

### Brief-version race evidence

The PostgreSQL race test pauses the first transaction after its real brief-root lock, starts a second transaction, verifies blocking, and releases the first. The result is exactly one successful brief freeze, one `stale_revision` conflict, one immutable brief version, one decision event, and one root increment.

## Evidence citations and currentness

- Task 7 consumes Task 6's global evidence head identity: `(organization_id, subject_type, subject_id, claim_key, source_identity)`.
- The locked handler loads exact supplied evidence records and all relevant global heads with explicit organization and subject scope, locks heads in deterministic identity order, and pins record ID, record revision, head revision, current record pointer, freshness state, and whether the cited record was current at freeze.
- An expired, stale, or superseded citation blocks freeze unless that exact evidence record is explicitly acknowledged. An acknowledged superseded record remains pinned with `was_current=false` and the exact current-record/head pointer captured for audit.
- No metric, amount, score, conversion, or evidence value is synthesized when source data is absent or incomparable.

## Authorization, replay, and lock-time recheck

- Operation-specific authorizers bind organization, operation, resource identity, and natural command key, then consult current Task 3 role state.
- Preflight is advisory only. The transaction locks programme/workstream/root rows, reloads current roles, and reruns the relevant gate before persisting.
- The handler-lock test pauses after the brief root is locked, commits a role revocation in another transaction, then proves the frozen operation is denied by the mandatory lock-time authorizer recheck.
- A command replay after role revocation is also denied before any persisted idempotency result can be returned. Replay therefore does not become an authorization bypass.
- Mutable draft readiness and captured client revision values are deliberately not trusted by the authorizer; the locked handler owns those concurrency/state checks.

## Database immutability and tenancy

- PostgreSQL append-only triggers protect `transformation_option_versions`, `decision_brief_versions`, both citation tables, and `decision_events` from direct `UPDATE` and `DELETE`.
- Driver-level tests demonstrate rejection across every Task 7 immutable artifact; ORM-only protections are not relied upon.
- Task 7 queries and mutations carry explicit `organization_id` predicates, including out-of-request service work, locking queries, cleanup, and database-guard test probes.
- Runtime-role installation/grants and the pre-existing fixed `search_path` transformation guard functions remain green.

## Schema and reconcile posture

- All new tenant-owned models use `TenantMixin` and explicit indexes/foreign keys/checks.
- New columns are nullable where existing-database reconciliation requires tolerance; service validation supplies the stronger domain invariant at freeze time.
- `create_all()` creates the new tables for fresh databases; the existing add-only `reconcile-schema` path detects/adds mapped columns without introducing legacy hand-written `ALTER TABLE` statements.
- The schema-drift gate is green against the Task 7 model set.

## Files

- `app/models/transformation_decision.py`
- `app/modules/transformation_room/decision_service.py`
- `app/models/transformation_db_guards.py`
- `app/modules/transformation_room/gate_service.py`
- `app/models/__init__.py`
- `tests/test_transformation_option_service.py`
- `tests/test_decision_brief_service.py`
- `tests/test_transformation_db_guards.py`

No template, CSS, or front-end JavaScript file was changed.

## Commit and concerns

- Commit subject: `feat: freeze transformation decision briefs`
- Concern: the repository-wide verifier was intentionally stopped before its full-pytest phase completed, so no repository-wide green claim is made. Focused Task 7, complete Transformation Room, schema, tenancy, compile, export, lint, and direct database immutability evidence are all green.
