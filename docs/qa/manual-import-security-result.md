# Manual application imports: F500-080 and F500-081

Candidate implementation, 5 September 2026. Independent review and real PostgreSQL/browser execution remain required; this document does not claim deployment or complete release verification.

## Reconciled reachable boundaries

- `POST /dashboard/applications/import-manual` is the legacy blueprint's login-required writer. Its request JSON previously reached arbitrary attribute assignment on merge and any mapped column except `id` on create.
- `POST /applications/import-manual` is the actual manual-grid destination in `app/static/js/application_mgmt/application_import.js`. The unified blueprint additionally requires `Permission.GENERAL` for writes. Its vendor enrichment cleaner did not authorize incoming fields; merge accepted arbitrary attributes and create's system-field exclusion omitted tenant and mirror fields.
- Global CSRF protection and login remain active. The new local tests execute the actual handlers through a small Flask app, but do not substitute for complete application registration, global CSRF, blueprint authorization, or PostgreSQL tests.

## F500-080: explicit manual-write contract

`app/utils/manual_application_import.py` validates the entire batch before either writer starts application/history persistence. Both handlers require an active integer organization ID. Request objects, application arrays, row objects, names, allowed options, field types and lengths, alias consistency, and finite numeric values are validated. An unsupported field causes a clear 400 response; a missing tenant causes 403.

The legacy contract retains the manual grid's `app_id`, `name`, `component_type`, and `deployment_status`, plus the stored `application_code` and established `description` import field. The richer unified contract follows the categorized model fields in its `get_import_fields` handler and retains supported business dates, `date_format`, numeric and Boolean fields. `update` is normalized to `merge`, and `app_id` is mapped to the stored application code. Empty optional values preserve existing merge values. Numeric zero and Boolean false are retained in the richer writer.

Neither contract authorizes primary keys, organization IDs, ArchiMate mirror IDs, vendor-product foreign keys, model relationships, lifecycle/audit metadata, AI-discovery metadata, or arbitrary model attributes. Human-entered business lifecycle fields such as `lifecycle_status` remain permitted on the richer route; server timestamps and deletion state do not. The richer field-picker's virtual linking fields are explicitly rejected by manual import because that handler has no validated relationship resolver; they were previously silently dropped, not safely linked.

Existing ORM tenant filtering restricts duplicate lookup to the actor's organization. Server-side model hooks continue creating the application's owned ArchiMate mirror. Duplicate names within one submitted batch now honor merge/update/skip/duplicate, and rows created then merged within that batch retain created-only provenance, with disjoint created/updated ID sets.

## F500-081: truthful unified manual audit persistence

The original unified handler committed applications, then constructed `ImportSessionLog` using nonexistent fields while omitting required fields. Its exception was swallowed, leaving the successful import without the history used by the application import-history interface.

The unified writer now persists an owned `ApplicationImportHistory` record, created/updated provenance, and a correctly constructed `ImportSessionLog`. The existing before/after change descriptions remain available in detailed changes. Application writes, mirror creation, and both audit representations commit in one transaction. Row-processing or audit-persistence exceptions roll back that transaction and return failure rather than a successful import count. Unparseable business dates retain their existing explicit `skipped_fields` response and are recorded in the audit.

This atomicity claim is confined to the unified writer. The legacy writer still commits between rows; the new whole-batch input validation prevents malformed/protected input in a later row from allowing a valid prefix to persist, but does not establish atomic rollback for later database failures in that legacy path.

## Verification evidence

- Original legacy boundary: 61 failing cases and 1 passing authentication case before repair; the failures demonstrated malformed/protected payloads reaching the database sentinel.
- Original unified boundary: all 40 initial protected-field cases failed before repair.
- Legacy created/updated provenance interaction: merge and update failed with overlapping `[1]` audit IDs; skip and duplicate passed before the provenance correction.
- Unified missing-history interaction: all four duplicate-mode cases failed before audit repair.
- Final focused boundary/persistence-double suite: 211 passed. It executes real handler code, validates rejection before the database sentinel, and exercises accepted duplicate/audit behavior with an explicitly limited persistence double.
- Real PostgreSQL suite: 129 skipped because no explicit disposable `TEST_DATABASE_URL` was available in this worker. These are not passes. The suite uses the shared transaction fixtures and both real routes, tests foreign-org create/transfer, primary-key/mirror/audit injection, malformed later rows, legitimate fields/mirrors, duplicate modes, both audit models, and rollback on injected audit failure.
- All three changed production modules parse; scoped `git diff --check` is clean. Focused correctness lint passes with existing E402 violations at lines 37 and 95 of `import_sophisticated_routes.py` excluded; those imports were not changed by this work.
- The combined test command ran with pytest plugin autoload disabled and emitted the existing legacy `datetime.utcnow()` deprecation warnings plus an unused `base_url` configuration warning.

No production database, credentials, network mutation, commit, or deployment was used. Parent-owned complete verification and browser/manual-import persistence checks remain necessary before acceptance. File-upload import writers and mirror-deletion siblings were not modified or declared safe by this repair.
