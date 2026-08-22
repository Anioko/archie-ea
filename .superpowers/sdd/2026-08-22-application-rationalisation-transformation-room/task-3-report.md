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

The review fix replaces that shared-session preparation entirely. The command
uses an independent SQLAlchemy session, so authorization reads, already-flushed
ORM writes and raw-SQL writes in the caller transaction remain untouched.

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

---

# Review fix round 1/5 — runtime isolation and recovery hardening

Status: **DONE_WITH_CONCERNS**

Commit subject: `fix: harden transformation command execution`

This section records the reviewer-required scope beyond the original Task 3
file list. Deployment/configuration changes were necessary to make database
guards an invariant under the credentials actually used by web and worker
processes.

## Additional files changed

- `.env.example`
- `docker-compose.yml`
- `docker-compose.optimized.yml`
- `scripts/database/configure_roles.py` (created)
- `scripts/database/deploy-schema.sh` (created)
- `app/commands/reconcile_schema.py`
- `app/models/transformation_db_guards.py`
- `app/modules/transformation_room/command_service.py`
- `tests/test_transformation_command_service.py`
- `tests/test_transformation_db_guards.py`
- `tests/test_transformation_runtime_role.py` (created)
- this report

Task 1 programme/canonical-link models and Task 2 capability-tenancy files
remain unchanged.

## Review RED evidence

Every PostgreSQL test below used both `DATABASE_URL` and `TEST_DATABASE_URL` as
`postgresql://postgres@127.0.0.1:5439/flask_test`.

### Actual runtime role and compose boundary

```powershell
pytest -q tests/test_transformation_runtime_role.py::test_compose_paths_separate_database_deployment_from_runtime tests/test_transformation_runtime_role.py::test_role_bootstrap_is_idempotent_and_runtime_cannot_bypass_guards
```

Initial result before the bootstrap/deploy/runtime split:

```text
FAILED test_compose_paths_separate_database_deployment_from_runtime
assert {'database-bootstrap', 'schema-deploy'} <= services.keys()
FAILED test_role_bootstrap_is_idempotent_and_runtime_cannot_bypass_guards
ModuleNotFoundError: No module named 'scripts.database.configure_roles'
2 failed, 8 warnings in 21.06s
```

The final privilege audit added checks for all non-extension public functions
and the optimized backup credential. Before the corresponding fix:

```text
FAILED test_compose_paths_separate_database_deployment_from_runtime
AssertionError: assert 'postgres' == '${POSTGRES_PASSWORD}'
FAILED test_role_bootstrap_is_idempotent_and_runtime_cannot_bypass_guards
assert (2,) == (0,)
2 failed, 9 warnings in 22.12s
```

The `(2,)` was the count of application-owned public functions still executable
by the direct-login runtime role. The role test deliberately authenticates as
`archie_runtime`; `SET ROLE` from the bootstrap superuser was rejected as proof
because PostgreSQL retains the superuser `session_user` in that setup.

### Actor-bound result reconciliation

```powershell
pytest -q tests/test_transformation_command_service.py::test_cross_actor_same_natural_key_cannot_replay_persisted_result
```

```text
FAILED test_cross_actor_same_natural_key_cannot_replay_persisted_result
Failed: DID NOT RAISE <class 'app.modules.transformation_room.domain.CommandConflict'>
1 failed, 12 warnings in 32.08s
```

The database-side finalization proof was independently pinned by temporarily
removing the actor predicate from the receipt trigger:

```powershell
pytest -q tests/test_transformation_db_guards.py::test_receipt_guard_rejects_result_owned_by_another_actor
```

```text
FAILED test_receipt_guard_rejects_result_owned_by_another_actor
Failed: DID NOT RAISE <class 'psycopg2.Error'>
1 failed, 10 warnings in 28.41s
```

### Domain-row-only reconciliation adapter

```powershell
pytest -q tests/test_transformation_command_service.py::test_domain_row_only_crash_is_reconciled_by_operation_resolver
```

```text
FAILED test_domain_row_only_crash_is_reconciled_by_operation_resolver
TypeError: CommandService.execute() got an unexpected keyword argument 'natural_key_resolver'
1 failed, 11 warnings in 20.88s
```

### Heartbeat/reclaim while handler is paused

```powershell
pytest -q tests/test_transformation_command_service.py::test_heartbeat_completes_while_handler_is_paused tests/test_transformation_command_service.py::test_reclaim_completes_while_expired_handler_is_paused
```

```text
FAILED test_heartbeat_completes_while_handler_is_paused
FAILED test_reclaim_completes_while_expired_handler_is_paused
assert completed_while_paused is False
2 failed, 14 warnings in 32.09s
```

### Caller transaction preservation

```powershell
pytest -q tests/test_transformation_command_service.py::test_execute_owns_domain_transaction_after_request_identity_read tests/test_transformation_command_service.py::test_preflushed_orm_write_is_not_rolled_back_by_command tests/test_transformation_command_service.py::test_raw_sql_write_is_not_rolled_back_by_command
```

```text
FAILED test_execute_owns_domain_transaction_after_request_identity_read
FAILED test_preflushed_orm_write_is_not_rolled_back_by_command
FAILED test_raw_sql_write_is_not_rolled_back_by_command
assert db.session().in_transaction() is True
3 failed, 19 warnings in 21.55s
```

### Disabled, miswired and tampered guards

```powershell
pytest -q tests/test_transformation_db_guards.py::test_schema_dry_run_reports_disabled_guard_without_mutating_it
```

```text
FAILED test_schema_dry_run_reports_disabled_guard_without_mutating_it
assert 'trigger_disabled:trg_transformation_result_immutable' in []
1 failed, 9 warnings in 32.88s
```

```powershell
pytest -q tests/test_transformation_db_guards.py::test_guard_installation_replaces_miswired_same_name_trigger
```

```text
FAILED test_guard_installation_replaces_miswired_same_name_trigger
assert 'archie_guard_transformation_receipt' == 'archie_reject_transformation_mutation'
1 failed, 9 warnings in 27.29s
```

```powershell
pytest -q tests/test_transformation_db_guards.py::test_schema_dry_run_reports_tampered_guard_function_then_apply_repairs_it
```

```text
FAILED test_schema_dry_run_reports_tampered_guard_function_then_apply_repairs_it
assert 'function_body:archie_reject_transformation_mutation' in []
1 failed, 9 warnings in 23.35s
```

## Review GREEN evidence — final tree

Individual transition evidence:

```text
cross-actor service: 1 passed, 12 warnings in 22.77s
cross-actor receipt trigger: 1 passed, 10 warnings in 21.63s
domain-row-only resolver: 1 passed, 11 warnings in 21.28s
paused-handler heartbeat: 1 passed, 11 warnings in 21.99s
paused-handler reclaim: passed in the two-test correction run
caller transaction preservation: 3 passed, 19 warnings in 20.24s
miswired trigger repair: 1 passed, 9 warnings in 20.65s
disabled trigger + tampered function: 2 passed, 10 warnings in 29.15s
runtime role + compose final privilege audit: 2 passed, 9 warnings in 20.83s
```

Fresh consolidated command:

```powershell
pytest -q tests/test_transformation_command_service.py tests/test_transformation_db_guards.py tests/test_transformation_runtime_role.py
```

```text
collected 40 items
tests/test_transformation_command_service.py .................. [ 45%]
tests/test_transformation_db_guards.py ....................     [ 95%]
tests/test_transformation_runtime_role.py ..                    [100%]
40 passed, 83 warnings in 35.90s
```

Fresh prior-interface regression command:

```powershell
pytest -q tests/test_transformation_programme_models.py tests/test_schema_reconciliation.py tests/test_capability_tenancy_cutover.py tests/test_tenant_isolation.py
```

```text
64 passed, 139 warnings in 46.52s
```

Repository gates on the final tree:

```text
python scripts/verify.py --gate schema-drift
ok schema-drift 46.1s [0 <= 0]
1 passed, 0 failed, 0 skipped

python scripts/verify.py --gate raw-sql-tenancy
ok raw-sql-tenancy 20.2s [0 <= 0]
1 passed, 0 failed, 0 skipped

python scripts/verify.py --tag static
30 passed, 0 failed, 1 skipped
```

The static skip remains only `css-build`: this checkout has no vendored
Tailwind executable. There are no template/CSS/JavaScript changes. Relevant
`ruff check` reports `All checks passed!`; `git diff --check` is empty.

## Runtime role, guard and deployment evidence

- `database-bootstrap` alone receives the PostgreSQL bootstrap credential and
  idempotently creates/rotates `archie_deploy` and `archie_runtime` as login,
  non-superuser, non-createdb, non-createrole, non-replication,
  non-bypass-RLS roles. It transfers database/schema/application-object
  ownership to `archie_deploy`.
- A one-shot `schema-deploy` service runs init, reconciliation and backfills as
  the owner. Main compose server/worker and optimized web/web-dev authenticate
  only as `archie_runtime` and wait for successful schema deployment.
- The actual direct-login runtime role proves permitted receipt/result/outbox
  INSERTs, receipt protocol-column UPDATE, outbox delivery-metadata UPDATE and
  sequence use. It has no ownership, DELETE, TRUNCATE or immutable-result UPDATE
  privilege and zero EXECUTE privilege on non-extension public functions.
- Direct attempts to change `session_replication_role`, assume the deploy role,
  disable/drop triggers, truncate results, update results, delete receipts,
  invoke a guard function, or create a public-schema table all fail under that
  same actual runtime login.
- Existing and default function privileges are revoked from PUBLIC/runtime;
  extension functions are left under extension ownership. Guard installation
  remains a deployment-owner action and narrows the three transformation tables
  after the general application DML grants. Both role setup and guard setup are
  idempotent.

## Actor, resolver, lock and atomicity design

- Result lookup now includes `organization_id`, actor, operation and natural
  key. A same-tenant, same-operation/key result owned by a different actor
  yields opaque `natural_key_owned_by_another_actor`; the receipt trigger also
  requires the result actor to equal the receipt actor.
- `OperationNaturalKeyResolver` is an explicit operation adapter contract. It
  receives an independent domain session, actor, natural key and fenced claim;
  when the domain row exists but `OperationResult` does not, it reconstructs the
  immutable mutation envelope, then atomically writes result, outbox and receipt
  finalization without invoking the mutation handler.
- Execution performs a non-locking fence read before domain work. The handler
  never holds the receipt row lock, so heartbeat/reclaim commits while a real
  handler transaction is paused. The final boundary locks and rechecks the exact
  tenant/actor/receipt/generation/token before result/outbox/finalization. A
  reclaimed stale worker loses that fence and its domain transaction rolls back.
- Command execution owns an independent SQLAlchemy session. It neither commits
  nor rolls back the request/caller session; preflushed ORM and raw-SQL writes
  stay present and remain under caller control while the command result commits
  independently.

## Guard drift and idempotence design

- Dry-run inspection compares trigger relation/name, enabled state, event/timing
  shape and exact function schema/identity. It also compares normalized function
  bodies, `SECURITY DEFINER` and the hardened search path.
- Dry-run records drift in reconciliation output without DDL. Apply replaces
  function definitions and drops/recreates disabled, miswired or malformed
  same-name triggers under an advisory lock, then audits that no drift remains.

## Review self-review

- Mutation checks: removing actor predicates breaks both actor tests; restoring
  a pre-handler `FOR UPDATE` breaks both paused-worker tests; removing the final
  fence permits the stale worker; removing the resolver reruns the handler;
  using Flask's scoped session breaks all three caller-transaction tests;
  name-only trigger inspection breaks disabled/miswired/body-drift tests.
- Runtime-role verification uses a new network authentication, not inherited
  `SET ROLE` state or mocks. Positive DML is exercised before every bypass denial.
- All supplied IDs in new SQL retain explicit organization predicates. The
  raw-SQL tenancy gate is zero and Task 1/2 regression suites pass.
- The optimized backup password was also corrected to use the configured
  bootstrap secret; no credential value is hard-coded in compose.

## Review concerns

1. Docker is unavailable in this Windows test environment, so the compose
   documents are parsed structurally rather than executed with
   `docker compose config`. The role bootstrap itself is exercised twice against
   PostgreSQL and the runtime bypass matrix uses a real direct login.
2. The unchanged missing Tailwind CLI leaves `css-build` skipped. No frontend
   artifact is in review scope.

---

# Review fix round 2/5 — complete trigger semantics, replay auth and isolated roles

Status: **DONE_WITH_CONCERNS**

Commit subject: `fix: close transformation replay bypasses`

## Files changed in this round

- `app/models/transformation_db_guards.py`
- `app/modules/transformation_room/command_service.py`
- `scripts/database/configure_roles.py`
- `tests/test_transformation_command_service.py`
- `tests/test_transformation_db_guards.py`
- `tests/test_transformation_runtime_role.py`
- this report

Task 1 programme/canonical-link models and Task 2 capability-tenancy files
remain unchanged.

## Round 2 RED evidence

Every PostgreSQL command below used both `DATABASE_URL` and
`TEST_DATABASE_URL` as
`postgresql://postgres@127.0.0.1:5439/flask_test`.

### Conditional and column-limited trigger bypasses

```powershell
pytest -q tests/test_transformation_db_guards.py::test_schema_reconciliation_repairs_conditional_or_column_limited_guard
```

The parametrized test replaces the result guard first with the correct
name/function plus `WHEN (false)`, then with the correct name/function plus
`UPDATE OF created_at`. Before inspecting `tgqual` and `tgattr`:

```text
FAILED ...[...WHEN (false)-trigger_when-WHEN (false)]
assert False
FAILED ...[...UPDATE OF created_at...-trigger_columns-UPDATE OF created_at]
assert False
2 failed, 10 warnings in 27.15s
```

Both failures were the dry-run drift list incorrectly remaining empty.

### Mandatory authorization before either replay path

```powershell
pytest -q tests/test_transformation_command_service.py::test_result_replay_runs_authorizer_before_returning_persisted_result tests/test_transformation_command_service.py::test_cross_actor_domain_row_recovery_is_authorized_before_resolver
```

```text
FAILED test_result_replay_runs_authorizer_before_returning_persisted_result
TypeError: CommandService.execute() got an unexpected keyword argument 'authorizer'
FAILED test_cross_actor_domain_row_recovery_is_authorized_before_resolver
TypeError: CommandService.execute() got an unexpected keyword argument 'authorizer'
2 failed, 15 warnings in 24.53s
```

### Per-test role identity injection

The runtime-role test was first moved to a disposable database with unique
deploy/runtime role names and asked guard installation to narrow that injected
runtime role:

```powershell
pytest -q tests/test_transformation_runtime_role.py::test_role_bootstrap_is_idempotent_and_runtime_cannot_bypass_guards
```

```text
FAILED test_role_bootstrap_is_idempotent_and_runtime_cannot_bypass_guards
TypeError: ensure_transformation_db_guards() got an unexpected keyword argument 'runtime_role'
1 failed, 1 warning in 4.28s
```

### Drifted privilege-bearing membership

After role injection was green, the isolated test granted its runtime role both
the deployment-owner role and a separate `CREATEDB` role, then reran bootstrap.
Before membership repair:

```powershell
pytest -q tests/test_transformation_runtime_role.py::test_role_bootstrap_is_idempotent_and_runtime_cannot_bypass_guards
```

```text
FAILED test_role_bootstrap_is_idempotent_and_runtime_cannot_bypass_guards
AssertionError: assert [('task3_deploy_...',), ('task3_privileged_...',)] == []
1 failed, 1 warning in 3.38s
```

## Round 2 GREEN evidence

Individual transitions:

```text
conditional/column-limited trigger detection+repair:
2 passed, 10 warnings in 30.74s

persisted-result denial + cross-actor domain-only denial + authorized same-actor recovery:
3 passed, 18 warnings in 30.79s

unique injected runtime role after guard-role parameterization:
1 passed, 1 warning in 3.52s

membership repair plus direct SET ROLE/bypass matrix:
1 passed, 1 warning in 3.33s
```

Fresh consolidated Task 3 suite:

```powershell
pytest -q tests/test_transformation_command_service.py tests/test_transformation_db_guards.py tests/test_transformation_runtime_role.py
```

```text
collected 44 items
tests/test_transformation_command_service.py .................... [ 45%]
tests/test_transformation_db_guards.py ......................     [ 95%]
tests/test_transformation_runtime_role.py ..                      [100%]
44 passed, 91 warnings in 56.49s
```

Fresh prior-interface regression suite:

```powershell
pytest -q tests/test_transformation_programme_models.py tests/test_schema_reconciliation.py tests/test_capability_tenancy_cutover.py tests/test_tenant_isolation.py
```

```text
64 passed, 139 warnings in 55.13s
```

Final repository gates:

```text
python scripts/verify.py --gate schema-drift
ok schema-drift 45.0s [0 <= 0]
1 passed, 0 failed, 0 skipped

python scripts/verify.py --gate raw-sql-tenancy
ok raw-sql-tenancy 18.0s [0 <= 0]
1 passed, 0 failed, 0 skipped

python scripts/verify.py --tag static
30 passed, 0 failed, 1 skipped
```

The sole static skip remains `css-build` because this checkout has no vendored
Tailwind executable; this round has no frontend changes. Relevant `ruff check`
reports `All checks passed!` and `git diff --check` is empty.

## Trigger-definition evidence and design

- Inspection now treats a canonical guard trigger as enabled, ordinary,
  row-level, `BEFORE UPDATE OR DELETE`, wired to the exact public guard function,
  with `tgqual IS NULL` and empty `tgattr`. A same-name/function trigger with a
  predicate or column list is drift even though its `tgtype` is unchanged.
- Dry-run reports `trigger_when:<name>` or `trigger_columns:<name>` and leaves the
  tampered `pg_get_triggerdef()` unchanged. Apply drops/recreates it, verifies no
  remaining semantic drift, and a direct immutable-result UPDATE again raises
  the append-only database exception.

## Replay authorization evidence and design

- `OperationAuthorizer` is a mandatory contract independent of the mutation
  handler and natural-key resolver. It receives the independent command session,
  actor, operation and natural key.
- `claim_or_reconcile()` calls it before receipt creation and before consulting
  any `OperationResult`; `execute_claim()` calls it before any domain resolver.
  The ordinary `execute()` path authorizes once during claim/reconciliation and
  carries that authorization directly into its private execution boundary.
- A denying authorizer prevents persisted-result replay without returning a
  result ID. Cross-actor domain-row-only recovery is denied before a receipt is
  inserted and before either resolver or handler runs; final counts remain one
  pre-existing domain row, zero results and zero outbox events.
- The authorized same-actor domain-row-only test still reconstructs one immutable
  result/outbox/finalization without invoking the mutation handler. Resolvers do
  not duplicate or hide authorization logic.

## Membership and test-isolation evidence and design

- Idempotent bootstrap enumerates every direct role granted to the runtime role
  and revokes it. This removes direct deployment-owner membership and arbitrary
  privilege-bearing membership, closing all direct and indirect `SET ROLE` paths
  from the runtime identity while preserving its explicit DML grants.
- The test creates a unique `task3_roles_*` database plus unique
  `task3_deploy_*`, `task3_runtime_*` and `task3_privileged_*` roles. It installs
  real minimal transformation tables as the unique deploy owner, injects the
  unique runtime name into real guard installation, authenticates directly as
  that role, and runs the positive DML plus bypass matrix.
- Fixture teardown terminates only connections to its unique database, drops the
  database, then drops runtime, privileged and deploy roles in dependency order
  inside `finally`, so it runs after assertion failure as well as success. After
  the RED and GREEN runs an administrator query measured:

```text
databases []
roles []
```

  for `task3_roles_%` and `task3_%`; no fixed cluster-global role password or
  ownership was changed by the test.

## Round 2 self-review

- Mutation checks: omitting `tgqual` makes the `WHEN(false)` case fail; omitting
  `tgattr` makes the `UPDATE OF` case fail; moving authorization after result or
  resolver makes the respective denial test fail; retaining any runtime
  membership makes the membership query and a direct `SET ROLE` attempt fail.
- The injected runtime role is quoted as an SQL identifier while role existence
  remains parameterized. Production deployment retains the default
  `archie_runtime`; injection exists only to make the real installer safely
  testable without cluster-global mutation.
- All supplied command IDs retain explicit organization predicates. The
  raw-SQL-tenancy gate remains zero, role fixture identifiers are random and
  bounded, and all temporary cluster objects are absent after teardown.

## Round 2 concerns

1. The unchanged missing Tailwind CLI leaves `css-build` skipped; there are no
   frontend artifacts in this round.
2. Docker remains unavailable in this Windows test environment. Compose
   structure was already pinned in round 1; this round exercises role drift,
   cleanup and bypass denial directly against PostgreSQL.
