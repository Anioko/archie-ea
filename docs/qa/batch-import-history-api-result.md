# Batch-job history GET repair

2026-09-05. This changes only the BatchJob list endpoint
`GET /api/import-history`. It does not migrate the application-import history
page or change job details, progress, statistics, rollback, retry, or export
endpoints. No production database or external import operation was accessed.

## Behavior and policy

`app/api/import_history_routes.py` now serializes real `BatchJobType` and
`BatchJobStatus` values as their lowercase JSON values. Numeric progress is a
JSON number rather than a Decimal string; NULL progress remains NULL instead of
being presented as a measured zero. Existing job count fields retain their
batch-item meanings; they are not renamed to application Created/Updated counts.

The optional status parameter is trimmed, case-normalized and converted to the
actual mapped `BatchJobStatus` before querying PostgreSQL. The seven allowed
values are pending, running, paused, completed, failed, cancelled and recovering.
Unknown values, including application-history-only `partial`, return 400.
Blank filters are absent filters.

Dates are strictly YYYY-MM-DD UTC calendar dates over the existing naive UTC
`created_at` column: from-day midnight is included, next-day midnight after the
to-day is excluded. Fractional seconds at the end of the selected day are
included. Impossible/noncanonical dates, reversed ranges and an overflowing
9999-12-31 upper bound return 400 before a database query. Filter errors are
explicit JSON errors; operational query errors retain the existing 500 response.

All filters apply before pagination. The total is the full matching query total,
including when a requested page is empty. Results order by created_at descending
and then id descending so equal timestamps cannot shuffle between pages. Existing
page/per-page parsing and size limits remain in force.

The list retains `created_by_id == current_user.id` and login_required; it does
not grant administrators access to other users' jobs. BatchJob has no TenantMixin
or organization_id. Its existing organization separation is indirect through
globally unique authenticated user ownership, not an ORM tenant predicate. The
new PostgreSQL fixtures explicitly include another user in the same organization
and a user in a different organization and expect both sets of jobs to be absent.

The unused BatchProcessingService constructor was removed from this GET path;
the list query does not require service initialization. Other endpoint uses of
that service are unchanged.

## Evidence and limits

The original standalone enum regression was moved with the page worker's
coordination from `tests/test_import_history_filters.py` into the owned
`tests/test_batch_import_history_api.py`. The page worker removed the old test
and its unused imports, avoiding competing edits.

Before the API repair the new local suite reported **16 failed, 1 passed**:
normal Flask serialization returned 500 for real model enums; invalid filters
were not rejected as 400. After the repair the final combined command was:

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_base_url.plugin tests/test_batch_import_history_api.py tests/test_batch_import_history_database.py -q --tb=short
```

Result: **17 passed, 20 skipped**, one pre-existing datetime.utcnow deprecation
warning in vendor_organization.py. Focused correctness lint (`F,E4,E7,E9`), Python
compilation of the API and both new test modules, and diff whitespace checks
passed.

The 17 executed tests run the real Flask route, login handling, normal JSON
serialization, actual enum types and actual SQLAlchemy column predicates. Their
query/pagination boundary is an explicit double: emitted datetime bounds and
enum conversion are asserted, but these tests do not claim PostgreSQL execution.
They also check unauthenticated exclusion, true total, numeric/null progress and
invalid-filter rejection before query access.

The 20 PostgreSQL tests use the shared repaired rollback db_session, make_org and
login_as fixtures. They are collected but **not locally executed** because no
explicit TEST_DATABASE_URL/PostgreSQL was available. Cases cover each real enum
status, separate/combined/cleared date filters, midnight and microsecond edges,
empty results, matching totals across pages including an out-of-range page,
stable equal-timestamp pagination and same-org/foreign-user exclusion. These
tests must pass in database-backed CI before the next wave is qualified.

No full verification/CI/deployment success is claimed by this bounded repair.
The root agent owns next-wave integration; no commits were made here.
