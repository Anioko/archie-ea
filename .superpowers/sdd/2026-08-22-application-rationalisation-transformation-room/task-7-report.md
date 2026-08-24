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

## Review fix round 4/5 — 23 August 2026

This section supersedes round 3's runtime receipt trust and SQL canonical-JSON
hashing architecture. The round was implemented test-first with
`postgresql://postgres@127.0.0.1:5439/flask_test` supplied explicitly as both
`TEST_DATABASE_URL` and `DATABASE_URL`.

### RED evidence

- The deployment-compose test first failed because neither schema deployment nor
  application runtime received a transformation command capability secret.
- The restricted-role receipt-boundary test first failed because the owner-only
  key table and signed claim function did not exist; temporarily reverting the
  execution-capability check then made the unsigned freeze exploit test fail with
  `DID NOT RAISE`.
- The exact-document hash test first failed because `DecisionBriefVersion` had no
  `canonical_document`; the next run caught the corresponding missing column on
  the long-lived PostgreSQL schema before additive reconciliation was corrected.
- Governed creation first failed with `AttributeError` because
  `DecisionBriefService.create_brief` did not exist. Normal/replay, cross-tenant,
  non-authority, concurrency, unsigned-capability and post-claim revocation cases
  were then driven green.
- The binary-float fact test first failed with `DID NOT RAISE`; decimal-domain
  validation now rejects IEEE-754 floats before option canonicalization.

### Server-issued command capabilities

- Runtime direct `INSERT` on `command_idempotency_records` is revoked. A runtime
  SQL session cannot read `archie_command_capability_keys`, whose key material is
  owner-only, and it cannot execute the internal HMAC/verifier functions.
- `CommandService` canonicalizes and HMAC-SHA256 signs a claim document binding
  tenant, actor, operation, idempotency key, request digest, natural key, claim
  token, request ID and lease. `archie_claim_transformation_command(text,text)` is
  the sole receipt create/reclaim/reconcile path and verifies that exact signed
  document before touching a receipt.
- A second signed execution document binds the resulting receipt ID, generation
  and token to the same tenant/actor/operation/key/digest/natural key. Both the
  brief-create and brief-freeze definers require it; an unsigned or altered
  execution claim fails with SQLSTATE `42501`.
- The current secret and comma-separated previous secrets are supplied from the
  deployment environment. Reconciliation provisions current/overlap keys without
  exposing them, marks removed keys inactive, and preserves their audit rows.
  The rotation test proves the old key works during overlap, fails after retirement,
  and the new key continues to mint claims. No secret is logged or returned.
- Production fails closed when the current capability secret is absent. Both
  compose paths pass the key only to schema deployment and application processes,
  never the database bootstrap service; `.env.example` documents generation and
  overlap rotation.

### One canonical UTF-8 document

- Python's canonical serializer now creates the exact request and brief hash
  documents. PostgreSQL parses each supplied text only to compare its JSON value
  with the locked server-derived payload, then hashes the original UTF-8 text
  bytes. It never independently re-renders JSON.
- `DecisionBriefVersion.canonical_document` stores those exact bytes as text via
  additive existing-database reconciliation. `verify_hash` parses the stored
  document, compares it with reconstructed persisted facts, requires Python
  canonical form, and hashes that same stored UTF-8 document.
- The obsolete recursive `archie_canonical_jsonb(jsonb)` function is dropped on
  reconciliation. Tests cover exponent-form floats, Decimal-backed option/outcome/
  measure facts, non-ASCII key ordering, nested objects and UTC timezone values;
  a valid canonical document for a different snapshot is rejected at the DB
  boundary.
- Numeric option facts reject binary float input and require `Decimal` or an exact
  decimal string before canonicalization.

### Governed draft creation

- `DecisionBriefService.create_brief` (also exported as `DecisionService`) is the
  authorized/idempotent application path for candidate or workstream decision
  scopes. It binds the natural scope, exact request digest and command receipt.
- `archie_create_decision_brief(text,text,text)` is a fixed-search-path
  `SECURITY DEFINER` boundary. It verifies the signed execution claim and exact
  request document, locks the active tenant programme/workstream, and rechecks the
  current actor role, accepted candidate (when candidate-scoped), exact recommendation
  option scope, decision authority and policy/legal exception authority before
  inserting revision 1 in draft state.
- Existing exact drafts reconcile idempotently; a different or non-draft case in
  the same partial-unique scope fails closed. Concurrent callers converge on one
  draft, and a contender reconciles through its original idempotency key.
- Runtime retains no direct draft `INSERT`. Tests prove normal creation, replay,
  cross-tenant denial, same-tenant non-authority denial, concurrent convergence,
  unsigned-capability denial and a committed role revocation between receipt claim
  and locked creation.

### Final GREEN evidence

All database-backed commands used the port-5439 PostgreSQL URL above.

- Task 3 command regressions: **27 passed** in 21.65 seconds.
- Final Task 7/runtime/guard/reconciliation tranche: **96 passed** in 164.33
  seconds, with no failures or skips.
- Complete Transformation Room programme/command/discovery/gate/evidence/option/
  brief/guard/runtime/reconciliation suite: **269 passed** in 205.16 seconds,
  with no failures or skips.
- Security hardening regression: **25 passed**.
- Static verifier: **30 passed, 0 failed, 1 skipped**. The sole skip is the
  pre-existing absent vendored Tailwind CLI for `css-build`; it is explicitly not
  counted as verified. No template, CSS or front-end JavaScript changed.
- `boot-health` and `schema-drift`: **2 passed, 0 failed, 0 skipped**;
  schema drift measurement remains `0 <= 0`.
- `deployed-deps` and `dependency-cves`: **2 passed, 0 failed, 0 skipped**;
  CVE measurement is `2 <= 3`.
- Changed-file Ruff and `git diff --check`: green.

### Files and concern

- Capability/config/deployment: `.env.example`, `config.py`, both compose files,
  `app/modules/transformation_room/command_service.py`, domain claim type, and
  `app/models/transformation_db_guards.py`.
- Exact hash and governed creation: `app/models/transformation_decision.py` and
  `app/modules/transformation_room/decision_service.py`.
- Regression coverage: command, option, brief, DB-guard, runtime-role and schema-
  reconciliation tests.
- The only unverified static gate is the unchanged `css-build` tooling absence
  stated above. The requested Task 3, Task 7/runtime, complete Transformation Room,
  boot/schema, dependency/security and changed-file checks are green.

Round commit subject: `fix: require signed transformation commands`.

## Review fix round 5/5 — 23 August 2026

This section supersedes the round-4 role-bootstrap privilege description.  The
round was implemented test-first with
`postgresql://postgres@127.0.0.1:5439/flask_test` supplied explicitly as both
`TEST_DATABASE_URL` and `DATABASE_URL`.

### RED evidence

- The Compose-order test failed because neither deployment path had a
  post-schema ACL completion service on which every runtime process depended.
- A fresh-table test showed the deploy role's default ACL immediately gave a
  future table `SELECT`, `INSERT`, `UPDATE`, and `DELETE`, its sequence usage,
  and its function public execution before any deliberate privilege review.
- Installing the Task 7 guards and rerunning `configure_database_roles()` gave
  runtime `SELECT`, `INSERT`, `UPDATE`, and `DELETE` on the raw-secret
  `archie_command_capability_keys` table and reopened protected draft/version/
  citation writes.  It also revoked the four approved definer-function grants.
- An injected exception immediately after a real table grant demonstrated the
  missing fail-closed runtime fence: the database ACL transaction rolled back,
  but runtime remained able to log in.
- The first concurrency probe paused before the transaction commit and passed,
  so it was discarded as incapable of catching the reported break.  Its
  replacement ran restricted read/write attackers across the bootstrap commit
  and failed because runtime read the capability-key material and could commit a
  forged decision-brief draft after the broad grant became visible.
- The first compatibility run then exposed seven legitimate-control failures:
  the old blanket defaults had implicitly supplied ordinary-table DML and
  protected insert-sequence access during schema creation.  Those dependencies
  were replaced with the post-schema finalizer and explicit protected-sequence
  grants; the least-privilege defaults were not relaxed.

### Monotonic least-privilege bootstrap

- `transformation_privilege_policy.py` is now the dependency-free single source
  of truth for the exact protected table privileges, the two column-scoped
  update grants, the four runtime-callable definer functions, and the absolute
  no-access capability-key table.  Both role bootstrap and guard reconciliation
  consume it, so either may run repeatedly without undoing the other.
- The bootstrap no longer executes an `ALL TABLES` or default-write grant.  In
  one transaction per target database it takes an advisory lock, transfers
  ownership, revokes public/runtime relation and sequence ACLs, grants ordinary
  application DML one quoted object at a time, applies the exact protected ACL,
  grants only sequences needed by directly insertable tables, revokes all future
  table/sequence/function defaults, and restores only the approved functions.
- Before any target ACL work, a cluster-wide serialized phase commits runtime as
  `NOLOGIN`, strips memberships and database grants, and terminates its existing
  target-database sessions.  Runtime is restored to `LOGIN` only after every
  target ACL transaction commits.  Any failure rolls back the target ACL in
  full and deliberately leaves runtime fenced rather than exposing an old or
  partial state.
- `archie_command_capability_keys` is never the target of a runtime grant.  Its
  table ACL and the internal HMAC/verifier functions remain owner/deploy only.
  Protected receipts, immutable records, evidence heads/events, drafts,
  versions, citations and decision events retain the guard contract's exact
  table, column, sequence and function privileges with no `DELETE`, `TRUNCATE`,
  schema `CREATE`, ownership, or unrestricted `UPDATE` path.
- Future deploy-owned tables, sequences and functions start with no runtime or
  public access.  A post-schema `database-acl` one-shot explicitly classifies
  the now-existing objects and commits their safe ACL.  Both Compose paths now
  enforce `database-bootstrap -> schema-deploy -> database-acl -> app`, and web,
  development and worker processes cannot start when ACL finalization fails.
  Neither bootstrap/ACL service receives the transformation command secret.

### Final GREEN evidence

All database-backed commands used the port-5439 PostgreSQL URL above.

- Focused future-default, guard-rerun, rollback/fence, concurrency, capability-
  distribution and Compose-order tranche: **6 passed**.
- Actual restricted-runtime bypass matrix: **16 passed** in 51.85 seconds.
- Task 3 command regressions: **27 passed** in 44.28 seconds.
- Task 7 option/brief/guard/runtime/schema-reconciliation tranche:
  **100 passed** in 152.75 seconds.
- Complete Transformation Room programme/command/discovery/gate/evidence/
  option/brief/guard/runtime/reconciliation slice: **273 passed** in 180.01
  seconds, with no failures or skips.
- Security hardening regression: **25 passed**.
- Static verifier: **30 passed, 0 failed, 1 skipped**.  The sole skip remains the
  unchanged absent vendored Tailwind CLI for `css-build`; it is not counted as
  verified, and no template, CSS or front-end JavaScript changed.
- `boot-health`: **1 passed, 0 failed, 0 skipped**.
- `schema-drift`: the first run competed with the simultaneous boot-health app
  reflection and failed without producing a drift measurement; the required
  isolated rerun was **1 passed, 0 failed, 0 skipped**, measurement `0 <= 0`.
- `deployed-deps` and `dependency-cves`: each **1 passed, 0 failed, 0 skipped**;
  the CVE measurement is `2 <= 3`.
- Changed-file Ruff, byte compilation and `git diff --check`: green.

### Self-review

- Re-traced the concrete source-to-sink path after implementation.  No other
  blanket current/default table grant remains in the repository.  The only
  bootstrap callers are the two pre-schema and two post-schema Compose services
  plus the real PostgreSQL tests.
- Challenged the shared policy by checking both outcomes for every protected
  table: permitted reads/inserts and column updates still work in the full
  runtime matrix, while key reads, forged drafts/versions/citations, arbitrary
  function execution, full updates, deletes, truncation, trigger/DDL bypass and
  role escalation remain denied.  HMAC capability issuance/rotation, exact
  canonical UTF-8 hashes, governed draft creation, replay, revocation and
  concurrency tests remain green through the Task 3 and Task 7 suites.
- Mutation check: removing the key no-access entry, restoring default writes,
  broadening any protected mapping, removing transaction rollback/runtime
  fencing, or bypassing the final Compose dependency is caught by at least one
  new behavior-level PostgreSQL or deployment-order test.
- Legitimate controls prove fresh objects are unusable before ACL finalization,
  ordinary application insert/update/read/delete works afterwards, protected
  insert sequences still work, and repeated bootstrap/guard installation is
  monotonic on existing databases.
- Remaining verification limitation: the unchanged `css-build` gate cannot run
  without the vendored Tailwind CLI.  No aggregate repository-wide full-pytest
  claim is made; the owning 273-test Transformation slice and the explicit gates
  above are the recorded completion evidence.

Round commit subject: `fix: make transformation ACL bootstrap monotonic`.
