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

## Review fix round 1 — authorization freshness and governed acceptance

Fix commit subject: `fix: close transformation evidence review findings`.
The exact SHA is recorded in the parent handoff because this report and the fix
are committed together.

The transition snapshot no longer performs or caches an authority lookup before
the aggregate locks. The only mutating-handler authority decision occurs after
the programme/workstream locks; the locked workstream, persisted runtime user
and deterministically ordered assignments use `populate_existing` so the
identity map cannot substitute a stale row. A real two-session RED committed an
assignment revocation after the former snapshot read but before the locked
authority read and observed the transition incorrectly succeed. The same
interleaving is GREEN and denies with `transition_not_authorised`.

Acceptance now requires the exact `submitted_evidence_id`, proves that record is
the current head for the exact tenant/subject/claim, rejects a conflict record,
and rejects a submitted attestation while a current disagreement remains
unresolved. Decision-authority resolution advances a separate governed head and
atomically replaces the request's submitted pointer, after which the resolution
can be accepted. The initial REDs accepted a different current source and an
unresolved attestation; both are now denied.

Attestation comparison now evaluates every current non-conflict source head.
Any disagreement produces one deterministic conflict citing all current leaves
plus the attestation, ordered by source identity and record ID. The three-source
RED showed one agreement suppressing two disagreements; the corrected case is
GREEN and stable regardless of source insertion order.

Claim-head identity remains global at
`(tenant, subject_type, subject_id, claim_key, source_identity)`. Candidate and
workstream IDs remain provenance, not ownership of an accepted head. Active
evidence enumerates accepted subject memberships in explicit
programme/workstream/candidate order and succeeds through any authorized
membership rather than whichever candidate PostgreSQL happens to return first.
A same-subject two-workstream RED denied the authorized second membership; the
GREEN case proves both relevant requests can accept the same governed current
record under their own locked request authority.

## Review fix round 1 — existing schema and one-to-one ledger

Long-lived `evidence_requests` tables now reconcile
`ck_evidence_request_waiver_complete` after the nullable waiver columns are
added. Dry-run reports `CHECK NOT VALID THEN VALIDATE`; apply installs and
validates it without blocking the column-add phase, partial waiver state fails
at PostgreSQL, and a second apply is a no-op. The representative pre-Task-6
schema test was RED because reconciliation reported no constraint work and is
now GREEN.

The guarded database function, rather than runtime ORM code, is now the only
creator of an evidence-head event. Runtime has SELECT but no INSERT on
`evidence_head_events` and retains EXECUTE on the seven-argument guarded advance
function. The allowed receipt bindings are exact:

- `evidence.observe` and the attested leaf of `evidence.attest` use
  `evidence:{candidate_id}:{claim_key}:{sha256(source_identity UTF-8)}:{new_revision}`;
- the conflict move under `evidence.attest` must name the exact evidence request
  and cite the same-transaction attestation event that the receipt key binds;
- `evidence.conflict.resolve` uses
  `evidence-conflict-resolution:{conflict_id}:{governing_evidence_id}` and the
  record's source identity, JSON IDs and governing citation must agree.

The function validates the operation/key/record/request binding before it
inserts the event and advances the locked head. A deferred constraint trigger
enforces the converse at commit: every new event must resolve to the exact
tenant head movement, new record/predecessor, revision, actor, receipt,
generation and transaction. Existing uniqueness constraints retain one event
per `(tenant, head, revision)` and one event per new record. The RED suite showed
an orphan event successfully reserving the next revision and unrelated live
receipts reaching the old "missing event" check. GREEN proves orphan insertion
rolls back, both unrelated operation and malformed evidence natural key are
rejected, valid observation/attestation/conflict/resolution flows still create
exactly one event, and the restricted runtime role cannot insert one directly.

## Review fix round 1 verification

Both `DATABASE_URL` and `TEST_DATABASE_URL` were set to
`postgresql://postgres@127.0.0.1:5439/flask_test` for database-backed runs.

- Complete Task 6 files: **42 passed**, 0 failed.
- Full Transformation Room regression including real head races: **187
  passed**, 0 failed.
- Focused changed service/guard/programme/runtime/reconciliation files: **79
  passed**, 0 failed.
- `schema-drift`, `raw-sql-tenancy`, `lint-core`, `compile` and
  `undefined-exports`: each **1 passed**, 0 failed, 0 skipped.
- Focused Ruff over all changed Python/test files: **all checks passed**.
- `git diff --check`: clean.

The only remaining concern is the repository's pre-existing warning volume
(SQLAlchemy lifecycle/deprecation and detached test-user warnings); no new test
failure, gate failure or skip remains in this fix round.

## Review fix round 2 — global resolution provenance and conflict binding

Fix commit subject: `fix: bind global evidence resolution provenance`. The
exact SHA is recorded in the parent handoff because the report and fix are
committed together.

Conflict resolution now keeps the resolving request/candidate as the
authorization and resolution-record provenance boundary while treating the
selected leaf's candidate as provenance only. The locked handler still loads
the conflict's exact tenant request, candidate, workstream and programme and
rechecks decision authority there. It then accepts a cited leaf from any
candidate only when the leaf has the exact actor tenant, subject type/ID and
claim key and is the current record of its exact source-identity head.

The two-workstream RED first failed with
`governing_evidence_not_found` solely because the selected current cited leaf
had been observed through the second candidate. The same case is GREEN and the
new resolution retains the first/request candidate as its provenance while
naming the second candidate's current leaf as governing evidence. Separate
tests prove a cited but superseded leaf is rejected as noncurrent, a current
post-conflict leaf is rejected as uncited, and even a maliciously cited
foreign-tenant row is rejected before resolution persistence.

The definer's `evidence.attest` conflict branch now requires the cited
same-transaction attestation event's candidate to equal the new conflict
record/request candidate. This closes a database-only confused-deputy path in
which a correctly fenced candidate-B attestation receipt and event could derive
its valid natural key and then advance candidate A's otherwise exact conflict
head.

The RED integration used the actual restricted runtime login, real tables,
same transaction, live receipt/token/lease, guarded function and deferred
ledger trigger; candidate B's receipt successfully advanced both B's
attestation and A's conflict. The corrected function rejects the second move
with `attestation candidate does not match conflict request candidate`, rolls
the transaction back, and the counterpart with both records/request on
candidate B commits two exactly bound events. No trigger or runtime privilege
was bypassed or mocked.

### Review fix round 2 verification

Both database variables used the required
`postgresql://postgres@127.0.0.1:5439/flask_test` URL.

- Task 6 evidence/concurrency/guard/runtime files: **50 passed**, 0 failed.
- Full Transformation Room regression: **193 passed**, 0 failed.
- `schema-drift`, `raw-sql-tenancy`, `lint-core`, `compile` and
  `undefined-exports`: each **1 passed**, 0 failed, 0 skipped.
- Focused Ruff over every changed Python/test file: **all checks passed**.
- `git diff --check`: clean.

The only concern remains the repository's pre-existing warning volume; this
round introduced no test failure, gate failure or skip.
