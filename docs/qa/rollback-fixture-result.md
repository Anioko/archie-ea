# Shared database fixture rollback repair

2026-09-05. Scope: shared test-session isolation; no application behavior, database
cleanup, deployment, or production database access.

## Cause and decision

CI run 33969038274, backend job 101314172585, reported six setup errors in
`test_framework_catalog_database.py`: `db_session.get_bind()` returned an Engine,
so the required `in_transaction()` safety check could not succeed. That check was
correct and remains unchanged.

The installed Flask-SQLAlchemy 3.1.1 `Session.get_bind()` first consults
`db.engines` for mapped statements, table clauses, and the default bind. Setting
`session.configure(bind=connection)` did not override those paths. The old
fixture opened an outer transaction that application session operations did not
join. SQLAlchemy 2.0.36 was used for the local reproduction.

The fixture now temporarily subclasses the existing session factory class. It
retains Flask-SQLAlchemy's bind-key resolution and replaces the resolved engine
with the outer connection owned by the fixture. There is one connection and
outer transaction per distinct configured engine. Session commits release
savepoints; fixture teardown rolls back each outer transaction and closes its
connection. Session rollback remains usable within a test.

`db.engines` is not modified, preserving real engine APIs. Existing scoped-session
event handlers are inherited, including the target used by tenant middleware.
The original session class and complete factory options are restored even after
a test exception, before leaving the fixture's dedicated application context.
Sessions in an already-existing caller context are preserved. Newly created
sessions after `remove()` and in nested app contexts use the same owned
connections.

Direct calls to `db.engine.connect()` or other independently opened connections
remain outside the session fixture's rollback contract. Such tests must own and
roll back their own transactions; replacing real engines with Connection objects
would break engine APIs and was deliberately avoided.

## Verification

The new real-library harness in `tests/test_db_session_binding.py` uses a tiny
Flask application and disposable SQLite databases, never the Archie app factory.
It tests fixture routing and cleanup only; it is not evidence of PostgreSQL
application correctness. SQLite uses explicit BEGIN to avoid sqlite3's legacy
savepoint behavior.

Before the repair, both harness cases failed because the returned bind was an
Engine instead of a Connection. After the repair, both pass. Checks cover mapped
and unmapped routing, a named bind, commits and rollback, an inherited before-flush
handler's persisted effect, session recreation, nested and pre-existing app
contexts, normal and exceptional teardown, factory restoration, and zero rows
remaining when measured through independent post-teardown connections.

Final local command:

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_base_url.plugin tests/test_db_session_binding.py tests/test_db_session_rollback_database.py -q
```

Result: **2 passed, 2 skipped**. The two skipped cases require an explicit
`TEST_DATABASE_URL` and PostgreSQL. They are not claimed as passes. Those new
integration cases drive the real shared fixture lifecycle on the real app,
commit a uniquely identified synthetic organization, verify that independent
observers cannot see it before teardown, and measure its absence after normal or
exceptional teardown. They also check mapped/unmapped connection identity and
restored configuration. They are collected for CI.

Focused correctness lint (`F,E4,E7,E9`), Python compilation of all three changed
test files, and `git diff --check` passed locally. Full application and PostgreSQL
qualification remains the root agent's CI responsibility.

## Prior-test residue risk

Before this repair, tests that committed through the shared fixture could leave
synthetic rows in persistent test databases. Tests that merely flushed generally
rolled back when their real session was removed, but the unused outer transaction
was not a valid isolation guarantee. No assumption is made about previous row
counts. Disposable CI databases can be replaced by the normal CI lifecycle;
persistent test databases require a scoped inventory before removing any known
synthetic residue. No cleanup or production database access was performed.
