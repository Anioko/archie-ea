# Framework catalog empty-collection fix

Date: 2026-09-05. Local handler validation passed; PostgreSQL/browser execution
remains pending integration.

The legacy `GET /dashboard/api/templates/frameworks` now returns its real queried
array even when empty (`200 []`), matching the existing application API. Removed
the empty-result 503 and unsupported instruction to seed framework data. The
database query, authentication decorator, and existing database error handling
are unchanged. No framework data, seed command, frontend caller, adversarial
exception, or baseline change was added.

Evidence before and after:

- First changed the real-Flask-handler boundary test to require an empty array
  with HTTP 200. The initial focused run failed with `503 == 200`: 1 failed,
  3 passed, 9 deselected (57.91 seconds). This reproduced the actual old handler
  branch rather than asserting source text.
- After removing that branch, `python -m pytest
  tests/test_availability_response_contracts.py -q` passed all 13 tests with six
  existing dependency/model deprecation warnings (39.52 seconds). Framework
  coverage includes empty and populated responses, unauthenticated 401, and
  injected database failure returning JSON 500 through the real blueprint
  error handler. The AI test bodies were not changed.
- `python -m py_compile tests/test_framework_catalog_database.py
  app/application_mgmt/template_api_routes.py`: passed.
- `python -m pytest tests/test_framework_catalog_database.py --collect-only -q`:
  six cases collected; none executed.
- `python -m ruff check --config ruff.toml
  app/application_mgmt/template_api_routes.py
  tests/test_availability_response_contracts.py
  tests/test_framework_catalog_database.py`: passed. An earlier invocation with
  command-line rule selection overrode repository exclusions and reported ten
  pre-existing SQLAlchemy boolean-comparison findings; these were not modified.
- Scoped `git diff --check`: passed.

The new PostgreSQL module uses the shared `db_session`, `make_org`, `client`, and
`login_as` fixtures. Both the legacy and canonical endpoints are covered for an
empty active catalog, inactive-only fixture data, and populated data with sorted,
distinct active framework values. The module requires explicit
`TEST_DATABASE_URL`; that variable is absent locally, so no database test was
executed or counted as passing.

Catalog setup asserts that its shared connection is already in a transaction,
temporarily deactivates existing active reference rows in that transaction, and
never commits. The shared fixture rolls back the changes, including generated
users, organization, role and custom synthetic templates. Nothing is deleted.
The templates are explicitly test-only custom data, not packaged third-party
framework content. The PostgreSQL tests do not replace the database query with
a double. Their empty case means zero active rows; it does not require deleting
any pre-existing inactive rows from a shared test database.

These six real-database cases and the root-owned authenticated-browser API
checks still require CI execution against the explicitly isolated candidate
database. No picker rendering, production deployment, full verification run,
or database integration pass is claimed by this bounded result.
