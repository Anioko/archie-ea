# Application import rollback boundary

Date: 2026-09-05. Outcome: **blocked verification**, candidate implemented; not a claim of a verified exploitable cross-tenant deletion or a production fix.

## Established behavior

`POST /applications/rollback-import/<history_id>` accepts a history ID, not a client application-ID list. Its former owner check treated the bound `User.is_admin` method as a boolean. Ordinary users with the applications blueprint's GENERAL write permission consequently passed the owner/admin check. Viewer writes remain blocked by that blueprint guard.

Current manual and file import writers record `linked_applications.created_ids` and `updated_ids` in `import_settings` and `error_details`, respectively. The old rollback read only the legacy `import_settings.application_ids`, returning 400 for these normal records. With nonempty legacy IDs it referenced a nonexistent capability-mapping `application_id` attribute: the actual column is `application_component_id`. That raised before the first DELETE. No current successful destructive exploit is asserted.

The former deletion order was nevertheless unsafe to repair in isolation: two mapping tables have no TenantMixin, and received stored IDs before the applications were resolved inside the active tenant. The manual writer also accepts model attributes including organization/ArchiMate associations; stored IDs and links cannot replace rollback authorization. That separate writer defect was reported for investigation and is outside this patch.

## Candidate contract

The route requires an active tenant and selects/locks fresh tenant-scoped history, avoiding identity-map `get` reuse. It evaluates the actual admin result and allows only the owner or an administrator. Completed and partial imports are eligible for exactly seven elapsed UTC days; future, unknown, older, unsupported and already rolled-back imports are rejected. This intentionally corrects the old display-only `.days <= 7` rule, which admitted almost eight elapsed days.

All three historical ID representations are supported. JSON and container/ID types are validated; duplicate JSON keys, conflicting sources and created/updated overlap are rejected. Identical duplicate encodings and repeated integer IDs are compatible. Only recorded created applications are selected for deletion; updates are neither deleted nor restored.

Before any DELETE, the complete application set and associated element set are selected and locked under the active organization. Missing or foreign targets reject the operation atomically. Mapping deletion uses only the validated application IDs and the real capability FK. A narrow Core-table reverse-reference query includes surviving applications in every tenant, including soft-deleted applications, so a shared element is retained. Explicit org predicates additionally constrain application/element writes.

The read-only `rollback_import_eligibility(history, user, now=None)` helper exposes `can_rollback`, `rollback_reason`, and `rollback_created_count` to the history UI. This is preliminary display eligibility; POST still validates actual targets immediately before deletion. The UI worker owns the caller and explanation of unsupported update restoration.

Response shape stays compatible: success has `success`, `message`, and four `deleted` counters; errors have `success: false` and `error`. Missing/foreign history is 404, authorization failures 403, invalid eligibility/metadata/target state 400, unexpected transactional failures 500, success 200. No schema changes, production data operations or deployment were performed by this worker.

## Verification evidence

1. Before implementation, the initial focused policy test run failed 20 cases because the policy boundary did not exist. The unchanged HEAD handler was also replayed in memory using observable query doubles: legitimate legacy metadata returned 500 at the missing capability attribute; an unauthorized same-tenant actor also reached that 500 rather than 403; current nested metadata returned 400. All three baseline probes issued no DELETE. This is focused substitute evidence, not PostgreSQL exploit reproduction.
2. `python -m py_compile app/modules/applications/routes/import_export_routes.py tests/test_import_rollback_security.py tests/test_import_rollback_database.py`: passed.
3. `python -m ruff check app/modules/applications/routes/import_export_routes.py tests/test_import_rollback_security.py tests/test_import_rollback_database.py --select F,E4,E7,E9`: passed.
4. `python -m pytest tests/test_import_rollback_security.py -q --override-ini addopts=''`: **34 passed**. Actual policy and actual handler execution cover valid legacy/current forms, real callable-admin semantics, foreign/missing mixed sets, preserved updates and shared elements, malformed/conflicting metadata, duplicate keys, UTC boundary, partial/status/repeat behavior, and rejection before mutation. Handler database interactions use observable doubles; decorators and PostgreSQL are covered by the separate integration file.
5. `python -m pytest tests/test_import_rollback_database.py --collect-only -q --override-ini addopts=''`: **11 collected**. These use the repository's shared rollback fixture, real User/Role and mapping models, full POST boundary, before/after snapshots, same-tenant admin/owner denial, cached foreign history, all three legitimate representations, repeat requests, malicious complete-set failures, and same/cross-tenant shared elements.
6. PostgreSQL execution was **not run**: no explicit `TEST_DATABASE_URL` was configured. The integration file requires that explicit setting and asserts PostgreSQL plus the owned outer transaction. Collection is not a pass; production data was not used as a substitute. Parent must run these cases in its disposable PostgreSQL/CI verification environment.
7. `python scripts/verify.py --tag static`: **42 passed, 2 failed, 0 skipped** (exit 1). Failures: `raw-fetch-sites` measured 1 against baseline 0; `css-build` found committed CSS stale after a rebuild. Correctness, tenant scoping, raw SQL, template syntax/references and runtime CSRF coverage passed. These two remaining full-worktree failures were handed to the parent; this worker did not change unrelated fetch/UI/CSS files. The original verifier completed without restart.

Remaining proof gaps: real PostgreSQL transactional/ORM/constraint behavior, full required repository gates and fresh candidate review. The skill's fixed outcome is withheld until these are green.
