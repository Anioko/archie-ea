# Task 3 report — fenced commands, immutable results and database guards

Status: **DONE_WITH_CONCERNS**

Commit subject: `feat: add fenced transformation commands`

The commit SHA is reported by the Task 3 status contract after this report and
the implementation are committed together; a commit cannot contain its own SHA.

## Files changed

- `app/models/transformation_execution.py` (created)
- `app/modules/transformation_room/__init__.py` (created)
- `app/modules/transformation_room/domain.py` (created)
- `app/modules/transformation_room/command_service.py` (created)
- `app/models/transformation_db_guards.py` (created)
- `app/models/__init__.py`
- `app/commands/reconcile_schema.py`
- `tests/test_transformation_command_service.py` (created)
- `tests/test_transformation_db_guards.py` (created)
- `.superpowers/sdd/2026-08-22-application-rationalisation-transformation-room/task-3-report.md` (created)

No Task 1 programme/delivery-link model or Task 2 capability-tenancy file was
changed.

## RED evidence

Every database command used both `DATABASE_URL` and `TEST_DATABASE_URL` set to
`postgresql://postgres@127.0.0.1:5439/flask_test`.

### Required missing implementation

Command:

```powershell
pytest -q tests/test_transformation_command_service.py tests/test_transformation_db_guards.py
```

Observed before production code existed:

```text
collected 0 items / 2 errors
ModuleNotFoundError: No module named 'app.models.transformation_execution'
ModuleNotFoundError: No module named 'app.models.transformation_db_guards'
ERROR tests/test_transformation_command_service.py
ERROR tests/test_transformation_db_guards.py
2 errors in 3.55s
```

This was the required import-level RED, before any Task 3 production file was
created.

### At-least-once outbox delivery without payload mutation

Command:

```powershell
pytest -q tests/test_transformation_db_guards.py::test_outbox_delivery_metadata_advances_without_mutating_event
```

Observed against the initial all-update-rejecting trigger:

```text
FAILED test_outbox_delivery_metadata_advances_without_mutating_event
psycopg2.errors.ObjectNotInPrerequisiteState:
transformation operation results and outbox rows are append-only
1 failed, 9 warnings in 20.46s
```

The final guard keeps event identity/type/payload immutable while permitting
monotonic `delivery_attempts` and `published_at` updates.

### Reconciliation deployment hook

The already-written hook was removed before adding this test, then restored only
after RED.

```powershell
pytest -q tests/test_transformation_db_guards.py::test_schema_reconciliation_restores_missing_guard_idempotently
```

```text
FAILED test_schema_reconciliation_restores_missing_guard_idempotently
assert 0 == 1
1 failed, 9 warnings in 36.29s
```

This proved a dropped result trigger remained absent without the
`reconcile-schema` hook.

### Terminal authorization failure

The non-retryable exception branch was removed before adding this test, then
restored only after RED.

```powershell
pytest -q tests/test_transformation_command_service.py::test_authorisation_failure_is_terminal_and_never_replayed_as_success
```

```text
FAILED test_authorisation_failure_is_terminal_and_never_replayed_as_success
AssertionError: assert 'in_progress' == 'failed_non_retryable'
1 failed, 9 warnings in 22.51s
```

### Request-shaped pre-existing read transaction

```powershell
pytest -q tests/test_transformation_command_service.py::test_execute_owns_domain_transaction_after_request_identity_read
```

```text
FAILED test_execute_owns_domain_transaction_after_request_identity_read
sqlalchemy.exc.InvalidRequestError:
A transaction is already begun on this Session.
1 failed, 9 warnings in 31.57s
```

The final service ends only a clean authorization/user-read transaction before
claiming. It rejects a session with pending writes rather than silently rolling
them back.

## GREEN evidence — final tree

### Exact focused Task 3 command

```powershell
pytest -q tests/test_transformation_command_service.py tests/test_transformation_db_guards.py
```

```text
tests/test_transformation_command_service.py ............ [ 42%]
tests/test_transformation_db_guards.py ................   [100%]
28 passed, 56 warnings in 29.32s
```

The warnings are existing dependency/deprecation warnings; there were no Task 3
warnings, failures or skips.

### Required database gates

```text
python scripts/verify.py --gate schema-drift
ok schema-drift 31.8s [0 <= 0]
1 passed, 0 failed, 0 skipped

python scripts/verify.py --gate raw-sql-tenancy
ok raw-sql-tenancy 12.2s [0 <= 0]
1 passed, 0 failed, 0 skipped
```

### Required Ruff check

```powershell
ruff check app/modules/transformation_room/domain.py app/modules/transformation_room/command_service.py app/models/transformation_execution.py app/models/transformation_db_guards.py app/models/__init__.py app/commands/reconcile_schema.py tests/test_transformation_command_service.py tests/test_transformation_db_guards.py
```

```text
All checks passed!
```

`git diff --check` emitted no output and exited zero.

### Task 1/2 and reconciliation regression surface

```powershell
pytest -q tests/test_transformation_programme_models.py tests/test_schema_reconciliation.py tests/test_capability_tenancy_cutover.py tests/test_tenant_isolation.py
```

```text
64 passed, 139 warnings in 45.39s
```

### Wider static verifier

```powershell
python scripts/verify.py --tag static
```

```text
30 passed, 0 failed, 1 skipped
```

The one skipped gate was `css-build`: this checkout has no vendored Tailwind CLI
at `scripts/bin/tailwindcss[.exe]`. A skip is not reported as a pass. Task 3 has
no template, CSS or front-end JavaScript changes.

## Race, lease and token evidence

- A claim is committed in a dedicated short SQLAlchemy session by PostgreSQL
  `INSERT ... ON CONFLICT DO NOTHING` on
  `(organization_id, actor_id, operation, idempotency_key)`.
- Every supplied receipt/result ID query also includes the actor's explicit
  `organization_id`; the foreign-tenant supplied-ID regression reaches
  `StaleClaim` before the handler and leaves zero domain/result/outbox rows.
- A first claim records generation 1 and a 256-bit cryptographically random
  token. Expired/retryable reclaim is locked, increments exactly to generation
  2, changes the token and increments the attempt count. An active lease returns
  positive `retry_after_seconds`, receipt ID and generation metadata.
- The required two-thread pause/reclaim/resume test uses a `threading.Barrier`,
  an event, independent scoped sessions and database-time expiry. Generation 2
  commits one domain row/result/outbox row; the resumed generation-1 worker gets
  `StaleClaim`. Final counts are exactly `(1, 1, 1)`.
- The database receipt trigger rejects generation skips and old-token heartbeat;
  the service heartbeat can only extend the same unexpired generation/token.
- Request digest reuse with changed payload is `CommandConflict`/HTTP 409 before
  any domain write.

## Reconciliation and atomicity evidence

- Claim-then-crash leaves only the independent receipt. After database-time
  expiry, reconciliation increments the fence and commits exactly one effect.
- Domain-insert-then-`KnownPreCommitTransient` flushes a real programme row, then
  rolls the transaction back. A short fenced transaction records
  `retryable_failure`, no result and the error class. Recovery increments the
  generation and produces one canonical effect.
- Result-then-fail-before-commit is simulated with a real deferred PostgreSQL
  constraint trigger on `operation_results`. The error fires at COMMIT after the
  result/outbox/finalisation work; domain, result, outbox and receipt finalisation
  all roll back. The independently committed receipt remains reconcilable.
- Commit-then-lost-response discards the first `CommandResult` and repeats the
  request. Replay returns the same persisted operation-result ID, object IDs and
  response, with `created=False`/`idempotent=True`; no handler effect repeats.
- An expired receipt with a separately committed immutable result repairs to
  success without running the handler. A successful natural-key domain row whose
  receipt pointer/status is deliberately damaged under test-only trigger bypass
  is likewise repaired from the unique
  `(organization_id, operation, natural_key)` result and returns the exact
  canonical response.
- Authorization failures roll back all domain work and become terminal
  `failed_non_retryable`; a same-digest repeat does not run the handler and is
  never returned as success.

## Guard installation and idempotence

- `ensure_transformation_db_guards()` takes one transaction-scoped advisory lock,
  replaces two `SECURITY DEFINER` functions with
  `search_path=pg_catalog, public`, revokes public function execution and direct
  table update/delete privileges, and creates exactly three enabled triggers.
- Running installation twice leaves exactly one trigger on each of
  `command_idempotency_records`, `operation_results` and
  `transformation_outbox_events`.
- Direct psycopg2 driver statements prove database enforcement independently of
  SQLAlchemy statement inspection: comment-prefixed update, CTE delete and
  schema-qualified update/delete all fail.
- Operation results reject every update/delete. Outbox event identity, result,
  ordinal, type, payload and creation time reject mutation/delete; only monotonic
  delivery metadata advances. Receipt tenant/actor/operation/key/digest/natural
  key and terminal result reject mutation/delete.
- Dropping the result trigger and running `_reconcile(dry_run=False)` restores it;
  a second reconciliation keeps the count at exactly one. The three tables are
  also in the add-only transformation table creation path for long-lived schemas.

## Design choices

- `CommandIdempotencyRecord`, `OperationResult` and `OperationOutboxEvent` all
  inherit `TenantMixin`. Operation results carry the immutable request digest,
  source receipt/generation, object IDs and canonical response; their unique
  tenant/operation/natural key is the recovery registry.
- The receipt intentionally stores `operation_result_id` without a cyclic FK;
  `OperationResult.receipt_id` has the physical `RESTRICT` FK, and the database
  finalisation trigger permits the reverse pointer only when the referenced
  result matches tenant, operation, digest and natural key.
- The short claim transaction is separate from the domain transaction. Domain
  mutation, outbox rows, immutable result and receipt finalisation share one
  transaction. Unknown/uncertain exceptions leave the lease reconcilable instead
  of asserting success or failure.
- `canonical_request_digest()` is SHA-256 over UTF-8, sorted, whitespace-free JSON
  with deterministic Decimal/date/datetime/frozenset serialization and rejects
  NaN.
- Frozen shared domain contracts follow the approved plan so later tasks import
  one actor/claim/result/error vocabulary rather than redefining it.

## Self-review

- Mutation review: removing digest comparison breaks the changed-payload test;
  removing generation/token checks breaks the stale-worker/heartbeat tests;
  splitting result/finalisation transactions breaks the deferred-COMMIT test;
  removing explicit organization predicates breaks the foreign-tenant test and
  raw-SQL gate; removing a trigger/hook breaks direct-driver/reconciliation tests.
- Confirmed Task 1 programme and canonical delivery-link files are untouched.
- Confirmed Task 2 capability tenancy and cutover files are untouched.
- Confirmed tests use committed unique tenant fixtures and independent sessions;
  teardown disables triggers only inside a transaction and deletes only the
  recorded test organization ID. No production or unrelated data was touched.
- Confirmed direct-SQL tests execute through the real psycopg2 connection, not a
  mock, regex guard or SQLAlchemy event.
- Confirmed no `print`, `console.log`, fabricated data, raw tenant query without an
  organization predicate, unrelated file or scratch artifact is included.

## Concerns

1. The repository's vendored Tailwind CLI is absent, so the unrelated static
   `css-build` gate was skipped and is not claimed green. Task 3 has no frontend
   changes.
2. The full untagged repository verifier (database tests plus Playwright smoke)
   was not part of this focused Task 3 execution. The exact Task 3 suite, required
   database gates, wider static verifier and 64-test prior-interface regression
   surface are recorded above; overall release verification remains with the
   release coordinator after later dependent tasks land.
