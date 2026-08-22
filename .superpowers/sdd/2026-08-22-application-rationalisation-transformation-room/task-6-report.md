# Task 6 report — versioned evidence and guarded claim heads

Status: **DONE_WITH_CONCERNS**

Commit subject: `feat: govern transformation evidence chains`

The exact commit SHA is recorded in the parent handoff because this report and
the implementation are committed together.

## Outcome

Implemented immutable, typed evidence versions; unique per-source claim heads;
append-only head events; evidence request submission, acceptance, decline,
expiry and expiring unavailable waivers; canonical application-inventory and
human-attestation sources; disagreement conflicts; governed decision-authority
resolution; and active-evidence reads through current head pointers only.

The database owns head integrity. A fixed-search-path `SECURITY DEFINER`
function validates the locked head, exact chain predecessor, revision, actor,
tenant, live fenced receipt generation/token/lease and same-transaction event,
then performs the compare-and-swap update. Direct record/event mutation and
invalid head insert/update/delete attempts fail at PostgreSQL.

## Prerequisite Task 4 authorization-race closure

Closed the four older authorization time-of-check/time-of-use gaps required by
the Task 6 ledger ruling:

- programme creation locks and reloads the persisted runtime `User`, then
  derives the create role before constructing or persisting the first domain
  row;
- objective update, programme archive and lifecycle transition request the
  shared locked programme-authority check after their aggregate locks;
- the shared check locks the runtime user first and every relevant
  programme/workstream assignment in primary-key order, matching Task 5's lock
  order, and retains those locks through command commit; and
- the canonical `User` model has no active/disabled account predicate, so none
  was invented. Authorization uses only the persisted role fields that the
  model actually supports.

### Prerequisite RED evidence

The real two-session tests first failed all four commit-before-revocation cases
because the revoker did not wait on a row lock. In the opposite serialization,
programme creation also failed with `DID NOT RAISE NotAuthorised` when role
revocation committed before the locked handler. Objective, archive and
transition already rejected the revocation-first ordering but did not hold the
authority locks through commit.

### Prerequisite GREEN evidence

- `test_task4_mutation_commit_serializes_with_authority_revocation` — **4
  passed**, covering create, objective, archive and transition. Each test pauses
  after the real locked user/ordered assignment query and observes the revoker
  waiting on a PostgreSQL row lock before allowing the command to commit.
- `test_task4_locked_handler_denies_revocation_that_commits_first` — **4
  passed**, covering the same mutations. Revocation-first is denied by the real
  locked handler with no unauthorized domain write.

No mocks replace authorization, SQL execution, transaction ownership or row
locking in these tests.

## Task 6 RED evidence

With both database variables set to
`postgresql://postgres@127.0.0.1:5439/flask_test`, the prescribed initial run

```text
pytest -q tests/test_transformation_evidence_service.py \
  tests/test_evidence_head_concurrency.py \
  tests/test_transformation_db_guards.py -k evidence
```

failed during collection because `EvidenceClaimHead` (and consequently the
evidence service interfaces) did not exist. This was the expected feature RED.

Later database-guard RED evidence exposed a real bypass in the first
implementation: a non-empty head could be inserted directly because the new
guard trigger covered UPDATE/DELETE but not INSERT. The arbitrary-current test
failed with `DID NOT RAISE`. The corrected trigger is
`BEFORE INSERT OR UPDATE OR DELETE`; its inspected PostgreSQL trigger shape is
now part of the idempotent guard contract.

The broader regression also exposed the expected runtime-role contract change:
the old test expected no executable application function, while Task 6 must
grant exactly the fenced seven-argument head-advance function. The updated test
asserts that exact function signature and no other non-extension function.

## Evidence schema and service behavior

`EvidenceRecord` stores JSON values with explicit type, unit, currency and
classification; canonical source identity/type/record/URI/version/checksum and
system; collector and AI provenance; observed, valid and freshness timestamps;
confidence method; citations; predecessor; creator; and immutable creation
time. `EvidenceClaimHead` enforces the exact unique key
`(organization_id, subject_type, subject_id, claim_key, source_identity)`.
`EvidenceHeadEvent` binds every move to its old/new records, actor, receipt,
generation, reason, revision and transaction ID.

The application-inventory adapter tenant-loads and then locks the canonical
application, snapshots only canonical inventory fields, calculates canonical
JSON SHA-256, gives unversioned adapters a content-addressed snapshot version,
normalizes source/URI namespaces without folding adapter-specific opaque keys,
and applies the required 90-day `inventory-r1.1` freshness rule.

Request behavior is explicit:

- an assigned user or persisted architect override can submit a human
  attestation from its separate `attestation:user:<id>` source;
- matching evidence moves `open -> submitted -> accepted` only through the
  locked acceptance command and a current-head check;
- disagreement creates an immutable conflict citing the canonical and
  attestation leaves and does not silently select either source;
- decision authority can select only a cited, still-current leaf, recording a
  new rationale-bearing resolution on its own guarded source/head;
- decline and expiry remain incomplete and do not create accepted evidence;
  and
- only persisted decision authority can add a time-bounded unavailable waiver
  with same-tenant interim accountability.

Every mutating interface passes a named source/request/conflict-specific
`OperationAuthorizer` to `CommandService`. Receipt/replay authorization
tenant-loads captured IDs. The handler then locks programme/workstream/scope,
request where relevant, persisted runtime user and deterministically ordered
role assignments, and rechecks mutable state and persisted authority before
writing.

## Race and rollback evidence

`tests/test_evidence_head_concurrency.py` uses independent SQLAlchemy sessions
and actual PostgreSQL locks for both revision-zero roots and two corrections
from revision N. The first command is paused after the real `FOR UPDATE` head
read; the second transaction contends on the same unique head/row lock. In each
case exactly one command succeeds, the loser receives
`CommandConflict(stale_head_revision)`, the head advances once, exactly one
record and one head event survive for that revision, and the losing transaction
leaves no orphan record.

The ordinary successful service path also proves the guarded function advances
one valid event/record/head exactly once. A stale revision is rejected before
the immutable record insert and leaves row counts unchanged.

## Direct PostgreSQL guard evidence

Separate raw PostgreSQL connections prove that all of these attempts fail and
roll back:

- arbitrary non-empty/current head insertion;
- historical pointer restoration;
- cross-tenant pointer/key mutation;
- wrong-subject pointer/key mutation;
- a revision jump;
- a leaf with the wrong predecessor;
- a direct head move with no matching same-transaction event/live command;
- record or event UPDATE/DELETE; and
- deleting a head with history.

Guard installation is advisory-locked, repairs function bodies and trigger
shape idempotently, fixes `search_path`, revokes direct runtime head updates and
all unsafe function execution, and grants only the fenced head-advance
function. The runtime-role integration test is green with that exact privilege.

## GREEN evidence

Final commands used both `DATABASE_URL` and `TEST_DATABASE_URL` set to the exact
PostgreSQL URL above.

- Prescribed Task 6 files — **35 passed**, 0 failed:
  `tests/test_transformation_evidence_service.py`,
  `tests/test_evidence_head_concurrency.py`, and
  `tests/test_transformation_db_guards.py`.
- Full Transformation Room regression — **179 passed**, 0 failed, covering
  command fencing, models, programmes, gates, discovery, evidence, concurrency,
  database guards and runtime roles.
- `python scripts/verify.py --gate schema-drift` — **1 passed**, `0 <= 0`, no
  skips.
- `python scripts/verify.py --gate raw-sql-tenancy` — **1 passed**, `0 <= 0`, no
  skips.
- `python scripts/verify.py --gate lint-core` — **1 passed**, `0 <= 0`, no
  skips.
- `python scripts/verify.py --gate compile` — **1 passed**, no skips.
- `python scripts/verify.py --gate undefined-exports` — **1 passed**, `0 <= 0`,
  no skips.
- Focused Ruff over every changed Python/test file — **all checks passed**.
- `git diff --check` — clean.

An initial schema-drift invocation set only `TEST_DATABASE_URL`; Flask's CLI
therefore inspected the worktree's default database and correctly reported
unapplied drift there. Re-running with both database variables set to the
mandated exact URL reported zero drift. No schema workaround or destructive
database action was used.

## Schema deployment and self-review

The reconciler includes all transformation candidate/evidence tables and the
submitted/accepted evidence foreign keys. New tables are created by the normal
`create_all()` path; the columns added to Task 5's existing `EvidenceRequest`
shell are nullable and therefore safe for the repository's add-only existing
database reconciler.

The active-evidence query reaches records only through
`EvidenceClaimHead.current_record_id` and explicitly binds organization,
subject and accepted candidate. All supplied IDs are paired with the exact
actor organization. No route, template, CSS or front-end file changed.

## Concerns / handoff

- The suite emits the repository's existing SQLAlchemy/datetime and detached
  test-user warnings; there are no new failures or skips.
- This task provides the domain service and persistence boundary only. A later
  route/UI task must expose it without weakening the authorizer or locked
  handler contracts.
- The parent integration wave should run the repository-wide verifier after all
  SDD task commits are assembled. This task's commit basis is the complete
  179-test Transformation Room regression plus all mandated Task 6 gates above.
