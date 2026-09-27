"""A legacy ARB row must not stop the application from booting.

`ensure_arb_cycle_constraints` installs the typed-ARB guards from an
`after_create` metadata event, so it runs inside `db.create_all()` — which is
what `flask init-db` calls (manage.py) and what the container runs on EVERY
start, before gunicorn (docker-compose: init-db -> reconcile-schema ->
gunicorn).

It adds each guard `NOT VALID` and then immediately ran
`ALTER TABLE ... VALIDATE CONSTRAINT`. Postgres' VALIDATE scans the whole table
and raises `CheckViolation` if any *pre-existing* row fails, so a single legacy
`arb_review_cycles` row aborted create_all() and the container never served.
The function also drops and re-adds a guard whenever its definition drifts from
the model, so any release that changes the typed-ARB shape re-validated it
against all historical rows — turning a data-shape mismatch into a crash loop.

The fix keeps the guard installed and ENFORCED (Postgres applies a NOT VALID
constraint to every INSERT and UPDATE; NOT VALID only means the rows already
present have not been *proven* to conform) and reports the offenders instead of
raising. That is the actionable administrative state; a boot loop is not.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.usefixtures("_schema")


def _pg(connection):
    return connection.dialect.name == "postgresql"


def test_validate_helper_leaves_the_guard_installed_when_legacy_rows_fail(app):
    """The regression, exercised against a real non-conforming row.

    Builds a throwaway table with a deliberately violating row, then asks the
    real helper to validate a guard over it. Before the fix the equivalent
    unguarded `VALIDATE CONSTRAINT` raised IntegrityError straight through
    `create_all()`.
    """
    from app import db
    from app.models.architecture_review_board import (
        _validate_without_aborting_boot,
    )

    table = f"arb_boot_safety_{uuid.uuid4().hex[:10]}"

    with app.app_context():
        with db.engine.connect() as connection:
            if not _pg(connection):
                pytest.skip("typed ARB guards are PostgreSQL-only")

            transaction = connection.begin()
            try:
                connection.exec_driver_sql(
                    f"CREATE TABLE {table} (id serial primary key, cycle_number int)"
                )
                # The legacy row: cycle_number must be > 0 and this one is not.
                connection.exec_driver_sql(f"INSERT INTO {table} (cycle_number) VALUES (0)")
                connection.exec_driver_sql(
                    f"ALTER TABLE {table} ADD CONSTRAINT ck_{table} "
                    "CHECK (cycle_number > 0) NOT VALID"
                )

                validated = _validate_without_aborting_boot(
                    connection, table, f"ck_{table}", "check constraint"
                )
                assert validated is False, (
                    "a non-conforming legacy row must be reported, not validated"
                )

                # 1. The connection is still usable — the failed VALIDATE was
                #    contained in a SAVEPOINT. Without that, every later DDL in
                #    create_all() dies with InFailedSqlTransaction.
                assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 1

                # 2. The guard is still installed, and still NOT VALID.
                convalidated = connection.scalar(
                    text(
                        "SELECT convalidated FROM pg_constraint "
                        "WHERE conname = :name"
                    ),
                    {"name": f"ck_{table}"},
                )
                assert convalidated is False, "the guard must remain installed"

                # 3. And it is genuinely ENFORCED for new rows. This is the
                #    property that makes leaving it NOT VALID acceptable
                #    rather than a silent loosening of governance.
                from sqlalchemy.exc import IntegrityError

                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.exec_driver_sql(
                            f"INSERT INTO {table} (cycle_number) VALUES (0)"
                        )
            finally:
                transaction.rollback()


def test_validate_helper_validates_when_every_row_conforms(app):
    """The healthy path must still fully validate — no silent downgrade."""
    from app import db
    from app.models.architecture_review_board import (
        _validate_without_aborting_boot,
    )

    table = f"arb_boot_ok_{uuid.uuid4().hex[:10]}"

    with app.app_context():
        with db.engine.connect() as connection:
            if not _pg(connection):
                pytest.skip("typed ARB guards are PostgreSQL-only")

            transaction = connection.begin()
            try:
                connection.exec_driver_sql(
                    f"CREATE TABLE {table} (id serial primary key, cycle_number int)"
                )
                connection.exec_driver_sql(f"INSERT INTO {table} (cycle_number) VALUES (1)")
                connection.exec_driver_sql(
                    f"ALTER TABLE {table} ADD CONSTRAINT ck_{table} "
                    "CHECK (cycle_number > 0) NOT VALID"
                )

                assert _validate_without_aborting_boot(
                    connection, table, f"ck_{table}", "check constraint"
                ) is True

                convalidated = connection.scalar(
                    text(
                        "SELECT convalidated FROM pg_constraint "
                        "WHERE conname = :name"
                    ),
                    {"name": f"ck_{table}"},
                )
                assert convalidated is True, (
                    "a conforming table must end up fully validated"
                )
            finally:
                transaction.rollback()
