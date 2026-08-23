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

## Review fix round 1/5 — 23 August 2026

This section supersedes the narrower original descriptions wherever they differ. The review hardening was implemented test-first against the same PostgreSQL database URL for both `TEST_DATABASE_URL` and `DATABASE_URL`.

### RED and GREEN

- The first review test tranche exposed **19 failing assertions and one fixture setup error** across evidence gates, decision scope, evidence-universe completeness, authority validation, integrity binding, citation immutability, partial uniqueness, governed-subject naming, and expiry projection.
- Two final focused RED checks then demonstrated that a request could borrow currentness from a differently identified source head, and that readiness rejected a corrupt historical option even when its latest version was valid. Both now pass.
- Final Task 7/gate/guard/reconciliation suite: **118 passed** in 67.03 seconds.
- Complete Transformation Room core suite: **213 passed** in 77.95 seconds.
- Rationalisation discovery suite: **27 passed** in 37.50 seconds.
- `schema-drift`, `raw-sql-tenancy`, `lint-core`, `compile`, and `undefined-exports`: **all green, zero failures, zero skips**.
- Changed-file Ruff, byte compilation, and `git diff --check`: green.

### Current evidence and strict decision scope

- Discover and Evidence gates now consume Task 6's actual `EvidenceRequest`, `EvidenceClaimHead`, and `EvidenceRecord` fields. Acceptance requires an accepted request whose evidence is the current record of the exact `(subject_type, subject_id, claim_key, source_identity)` head.
- Effective freshness is computed from both the persisted label and expiry timestamp. Current conflicts block until a current governance-resolution record for the same subject and claim explicitly cites the conflict.
- Candidate briefs accept only option versions for that exact candidate. Workstream briefs accept only workstream-scoped options where `candidate_id IS NULL`; candidate options cannot leak into a workstream decision.
- Gate and readiness evaluation group by stable option root, consume only each root's latest version, verify the latest version hash, and preserve exact candidate-versus-workstream scope. A corrupt superseded version does not replace or contaminate a valid latest version.

### Complete frozen universe and authority

- The locked freeze handler derives the required evidence universe from every current global head in the decision scope and every persisted request for the scoped candidates. Caller-supplied citations cannot omit a material current source.
- Heads, records, and requests are locked in deterministic identity order. Required requests must be accepted against the exact current non-conflict record; omitted heads, unaccepted evidence, and unresolved current conflicts fail closed. `blockers_cleared` is persisted only after those checks complete.
- The persisted decision authority is reloaded by explicit tenant ID and must hold a current server-derived decision role for the programme/workstream. User and role-assignment rows are locked through commit. Foreign-tenant and same-tenant non-authorities are rejected.
- Task 3's operation-specific authorizer still runs before claim/replay and the locked handler still owns mutable revision/readiness checks. The full suite keeps the option/brief race, revocation, and replay tests green.

### Integrity and immutable membership

- The option SHA-256 envelope now binds organization, workstream, candidate, logical option/version metadata, canonical content, every duplicated cost/benefit/risk bound, currency, and technology flag. Comparison and gate consumers verify the digest before using current versions.
- Capability and value-stream identifiers are locked and validated against their canonical tenant-scoped models; missing and foreign identifiers are rejected rather than copied into a frozen payload.
- The brief digest binds scope, normalized frozen payload, recommendation, sorted option/evidence/outcome/measure memberships, policy, submitter, authority, review, blocker, and acknowledgement fields.
- Citation `UPDATE`/`DELETE` remain append-only. New PostgreSQL `BEFORE INSERT` guards permit citation creation only in the transaction that created the parent brief version, using the immutable row's `xmin`, and only for IDs already bound into the parent's hashed membership. Later runtime inserts fail with `decision brief citation membership is frozen`.
- Citation freshness records the computed effective state at freeze, including `expired` when the expiry timestamp has elapsed, while retaining the exact acknowledgement flag.

### Schema and governed subject contract

- Decision-brief uniqueness now uses two PostgreSQL partial unique indexes: `(organization_id, workstream_id)` for workstream briefs and `(organization_id, workstream_id, candidate_id)` for candidate briefs.
- Reconciliation creates the seven Task 7 tables in dependency order and installs both partial indexes idempotently. Catalog checks and creates are bound to the active schema so a same-named table or index later on `search_path` cannot mask missing local schema objects.
- Governed brief matching consistently uses the canonical `brief_id` root field; version links continue to use their explicit brief-version identifier.

### Round commit and concerns

- Round commit subject: `fix: harden transformation decision evidence`.
- No Task 7-scoped failures or skips remain. The earlier repository-wide verifier concern remains unchanged: no new repository-wide green claim is made beyond the explicit suites and gates above.

## Review fix round 2/5 — 23 August 2026

This section supersedes the round-1 citation-membership implementation and extends the gate, option-currentness, and schema descriptions. The changes were implemented test-first against PostgreSQL with `postgresql://postgres@127.0.0.1:5439/flask_test` supplied explicitly as both `TEST_DATABASE_URL` and `DATABASE_URL`.

### RED and GREEN

- The first round-2 RED run produced **6 failures**: two real Task 6 waiver integration cases, stale-option and option-version race cases, nested-savepoint citation creation, and non-public guard installation.
- The final combined Task 1–7 Transformation Room, runtime-role, direct-guard, and reconciliation suite is **253 passed** in 109.04 seconds, with no failures or skips.
- The direct guard/runtime-role tranche is **31 passed** in 47.20 seconds.
- The gate and reconciliation tranche is **62 passed** in 52.72 seconds.
- `schema-drift`, `raw-sql-tenancy`, `lint-core`, `compile`, and `undefined-exports` are green with zero failures and zero skips. Changed-file Ruff and `git diff --check` are green.
- A repository-wide `python scripts/verify.py` run was started after the focused green evidence, but produced no output or final summary during its long full-test phase and was bounded under the coordinator's standing instruction. It is recorded as **incomplete, not green**; the explicit 253-test and individual-gate results above are the completion evidence.

### Task 6 waiver projection and gates

- Policy snapshots now load persisted Task 6 `EvidenceRequest` waivers rather than projecting an empty waiver collection. The gate consumes the canonical `waiver_id`, `waiver_authority_id`, `waiver_reason`, `waiver_expires_at`, `interim_accountable_id`, `waived_at`, request status, tenant, candidate, and claim fields.
- Only an exact waiver whose `waiver_id` equals its request ID, whose request is `declined` or `expired`, whose authority is currently authorized in the tenant/programme/workstream, whose interim accountable user is in the tenant, and whose expiry is still future can release the request.
- Real service-created declined and expired waivers release Discover readiness. Mismatched IDs, elapsed expiry, and a persisted same-tenant non-authority fail closed. Evidence request completion applies the same Task 6 contract for both declined and expired statuses.

### Latest scoped alternatives and serialization

- Brief freeze now locks every logical option root in deterministic ID order for the brief's exact workstream/candidate scope, then locks and derives each root's latest immutable version.
- Every requested version must be the latest version of its logical option, and the requested set must equal the complete set of latest scoped alternatives. A stale v1 after v2 is committed returns `option_version_not_latest`; omitting a latest alternative returns `option_version_set_not_current`.
- Readiness and gate evaluation continue to expose only latest versions in the same exact scope. The new PostgreSQL race pauses option v2 creation while it owns the real workstream lock, proves brief freeze blocks, then commits v2; brief freeze subsequently observes v1 as stale and creates no brief version.

### Function-only citation membership

- The prior `xmin::bigint = txid_current()` membership exception has been removed. It was unsound across PostgreSQL subtransactions and mixed a 32-bit row XID with an epoch-wide transaction identifier.
- Runtime direct `INSERT` is revoked on both citation tables. Citation rows are created only by `archie_insert_decision_brief_citations(...)`, a `SECURITY DEFINER` function with a fixed `pg_catalog` plus target-schema search path.
- The function verifies the exact in-progress Task 3 receipt ID, operation, natural key, actor, lease generation, claim token, and unexpired lease; the still-draft brief root and source revision; the immutable parent scope and actor; and sorted unique option/evidence memberships matching the frozen hash-bound payload. It derives all citation values from that parent payload rather than trusting caller-supplied citation rows.
- A deploy-owner direct post-freeze insert remains rejected by the membership trigger. Runtime direct insert is rejected by privilege. Legitimate service creation places the parent version and function call inside a real nested savepoint, and the PostgreSQL integration test proves both citation sets are created successfully without XID equality assumptions.

### Schema-aware guard installation and reconciliation

- Guard creation, inspection, trigger repair, privilege repair, and advisory locking now resolve the connection's current target schema. Schema, table, trigger, function, and runtime-role identifiers are quoted through the PostgreSQL dialect rather than interpolated as untrusted names.
- Every definer function is rendered with a fixed `search_path = pg_catalog, <quoted-target-schema>` and explicitly qualified target objects. Public-schema production behavior is preserved when `current_schema()` is `public`.
- The isolated long-lived-schema test reconciles twice, requires zero semantic guard drift, proves all functions and trigger targets remain in the non-public schema, rejects a direct immutable-row update, and rejects a direct citation insert. Dry-run inspection now correctly reports guards missing from the active isolated schema instead of borrowing same-named public functions.

### Round commit and concerns

- Intended commit subject: `fix: fence decision citations across schemas`.
- No round-2 scoped failure or skip remains. The only verification limitation is the explicitly incomplete repository-wide verifier run described above; the complete 253-test Transformation Room suite and required individual gates are green.

## Review fix round 3/5 — 23 August 2026

This section supersedes round 2's parent-version-plus-citation-function protocol. The round was implemented test-first with `postgresql://postgres@127.0.0.1:5439/flask_test` supplied explicitly as both `TEST_DATABASE_URL` and `DATABASE_URL`.

### RED and GREEN

- The round-3 RED run produced **4 failures**: the restricted runtime role successfully composed a forged draft, receipt, brief version, and citation call; freeze accepted a scope containing a third logical option root with no version; and two waiver cases were released by raw request fields without a valid Task 6 waiver projection.
- The complete Transformation Room Task 1–7, runtime-role, direct-guard, and reconciliation slice is **230 passed** in 136.84 seconds, with no failures or skips.
- The direct guard/runtime/reconciliation tranche is **49 passed** in 95.03 seconds.
- After the final deterministic lock-order review, normal freeze/hash verification, nested-savepoint creation, the real same-revision concurrency race, and the restricted-role exploit are **4 passed**; the waiver-projection and guard-installation checks are **5 passed**.
- `compile`, `undefined-names`, `redefinitions`, `lint-core`, `raw-sql-tenancy` (`0 <= 0`), `boot-health`, and `schema-drift` (`0 <= 0`) are green with zero failures and zero skips. Changed-file Ruff and `git diff --check` are green.
- The aggregate `python scripts/verify.py --tag static` run produced no summary within the bounded window and was stopped. Its relevant correctness, compilation, lint, and tenancy gates were then run individually and passed. No aggregate-static or repository-wide green claim is made.

### Atomic server-owned brief freeze

- Runtime can no longer insert a `decision_briefs` draft, a `decision_brief_versions` row, or either citation membership. The runtime role retains read access, while the deploy owner retains schema/reconciliation authority. The obsolete citation-only definer is dropped during idempotent guard installation.
- `archie_freeze_decision_brief_version(...)` is the only runtime entry point. In one fixed-search-path `SECURITY DEFINER` operation it locks the active programme/workstream, exact draft and expected revision, exact in-progress Task 3 receipt, current users/role assignments, scoped option roots/versions, candidates, global evidence heads/records/requests, outcomes, and measures in deterministic order.
- The operation binds tenant, actor, `brief.freeze` operation, natural key, request digest, receipt ID, claim token, lease generation and expiry, draft identity/revision, current decision authority, and any policy/legal exception authority. Revocation or scope changes observed at the lock boundary fail before an artifact is inserted.
- The server validates the canonical frozen payload against persisted draft/programme/candidate facts, the complete latest option universe, exact version content, current/acknowledged evidence and head state, effective expiry, accepted request/current-head relationships, explicit conflict resolution, outcomes, measures, unknown acknowledgements, and the human-review assertion.
- `archie_canonical_jsonb(...)` supplies deterministic recursive JSON rendering inside PostgreSQL. The freeze operation recomputes the Task 3 request SHA-256 and the complete decision-brief integrity envelope, inserts the version and both sorted citation sets, and advances the draft to frozen atomically. The Python verifier accepts the resulting digest, proving parity with the persisted contract.
- A legitimate service freeze continues to work inside a nested savepoint. The real PostgreSQL two-session same-revision test still yields one frozen version and one losing stale command. A restricted-role forged draft/receipt/version/citation sequence fails and leaves zero artifacts.

### Complete latest option scope

- Every eligible `TransformationOption` root in the exact candidate or workstream scope must have an immutable version. The selected set must equal the latest version of every root; an unversioned third root now returns `option_version_missing` instead of disappearing from comparison and readiness.
- Existing one-option policy/legal exception coverage now constructs a genuine one-root scope. It therefore continues to prove the exception rule without contradicting complete-root membership.

### Authority-validated Task 6 waiver projection

- Evidence gate completion derives waived request IDs only from `snapshot.evidence_waivers` entries that pass the existing tenant, identity, status, expiry, interim-accountable, and current-authority validation.
- Truthy `waiver_id`, `waiver_authority_id`, or `interim_accountable_id` fields on a raw request never release a blocker. Missing projection and a projection with a nonexistent authority both retain `required_evidence_incomplete`; valid persisted Task 6 declined and expired waivers remain green.

### Schema, immutability, and reconciliation

- Guard inspection and repair now track the canonical JSON and atomic freeze functions in both public and isolated non-public schemas, with fixed `pg_catalog` plus explicitly quoted target-schema search paths.
- Runtime grants expose only the evidence-head advance and atomic brief-freeze operations. Direct version/citation/draft writes remain revoked after repeated role bootstrap and guard reconciliation.
- Partial decision-brief uniqueness, immutable update/delete triggers, post-freeze citation membership triggers, schema-drift detection, and isolated-schema idempotence remain green.

### Round commit and concerns

- Intended commit subject: `fix: make decision brief freeze server-owned`.
- No round-3 scoped failure or skip remains. The only limitation is the bounded aggregate-static/repository-wide verifier noted above; the explicit 230-test Transformation Room slice, post-review focused concurrency/runtime checks, and required individual gates are the completion evidence.
