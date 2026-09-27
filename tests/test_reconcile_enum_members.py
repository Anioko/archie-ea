"""reconcile-schema must add missing PostgreSQL enum labels, additively.

Measured in production on 5 Sep 2026: `batchjobstatus` is shared by two models
with different Python members and lacked RUNNING / RECOVERING, so
BatchProcessingService could never mark a job running.  ADD COLUMN cannot
repair a label set; this pins the enum counterpart.
"""

import uuid

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, text
from sqlalchemy.dialects.postgresql import ENUM

from app import db


@pytest.fixture
def probe_enum(app):
    """A committed enum type + table outside the rollback fixture.

    ALTER TYPE ... ADD VALUE runs on its own autocommit connection, so the type
    must be visible to other connections: created and dropped with autocommit.
    """
    suffix = uuid.uuid4().hex[:8]
    typname = f"reconcile_probe_status_{suffix}"
    tablename = f"reconcile_probe_{suffix}"
    with app.app_context():
        with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"CREATE TYPE {typname} AS ENUM ('PENDING', 'DONE')"))
            conn.execute(text(f"CREATE TABLE {tablename} (id integer primary key, status {typname})"))
        table = Table(
            tablename, db.metadata,
            Column("id", Integer, primary_key=True),
            Column("status", ENUM("PENDING", "RUNNING", "DONE", "RE'COVERING", name=typname, create_type=False)),
        )
        try:
            yield typname, tablename
        finally:
            db.metadata.remove(table)
            with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {tablename}"))
                conn.execute(text(f"DROP TYPE IF EXISTS {typname}"))


def _labels(typname):
    return db.session.execute(text(
        "SELECT e.enumlabel FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid "
        "WHERE t.typname = :n ORDER BY e.enumsortorder"), {"n": typname}).scalars().all()


def test_missing_labels_are_added_and_existing_ones_untouched(app, probe_enum):
    from app.commands.reconcile_schema import _ensure_enum_members

    typname, tablename = probe_enum
    with app.app_context():
        assert _labels(typname) == ["PENDING", "DONE"]
        added, failed, blocking = [], [], []
        _ensure_enum_members(dry_run=False, existing_tables={tablename}, added=added, failed=failed, blocking=blocking)
        assert (failed, blocking) == ([], [])
        assert added == [f"enum {typname} += RUNNING", f"enum {typname} += RE'COVERING"]
        assert set(_labels(typname)) == {"PENDING", "DONE", "RUNNING", "RE'COVERING"}

        # Idempotent: a second pass adds nothing and fails nothing.
        added, failed, blocking = [], [], []
        _ensure_enum_members(dry_run=False, existing_tables={tablename}, added=added, failed=failed, blocking=blocking)
        assert (added, failed, blocking) == ([], [], [])


def test_dry_run_reports_without_altering(app, probe_enum):
    from app.commands.reconcile_schema import _ensure_enum_members

    typname, tablename = probe_enum
    with app.app_context():
        added, failed, blocking = [], [], []
        _ensure_enum_members(dry_run=True, existing_tables={tablename}, added=added, failed=failed, blocking=blocking)
        assert f"enum {typname} += RUNNING" in added
        assert (failed, blocking) == ([], [])
        assert _labels(typname) == ["PENDING", "DONE"]


def test_insufficient_privilege_is_reported_as_blocking_not_failed(app, probe_enum):
    """Measured in production 6 Sep 2026: the deploy role doesn't own every
    enum type any more than it owns every table (the pre-existing table-
    ownership gap this same command already tolerates via `blocking`).
    ALTER TYPE then raises InsufficientPrivilege, which previously landed in
    `failed` and made reconcile-schema - and the whole deploy - exit 1. A
    missing enum label degrades one write path; it must not block deploying
    everything else, the same way a missing table's ownership doesn't.

    Uses a real, unprivileged PostgreSQL role rather than a mocked
    connection, so this proves the actual driver exception (message and
    all) is classified correctly, not just an exception object this test
    constructed by hand.
    """
    from app.commands.reconcile_schema import _ensure_enum_members

    typname, tablename = probe_enum
    suffix = uuid.uuid4().hex[:8]
    role = f"reconcile_probe_role_{suffix}"

    with app.app_context():
        with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD 'probe'"))
            conn.execute(text(f"GRANT CONNECT ON DATABASE {conn.engine.url.database} TO {role}"))
            conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
            conn.execute(text(f"GRANT SELECT ON pg_type, pg_enum TO {role}"))
        try:
            restricted_url = db.engine.url.set(username=role, password="probe")
            restricted_engine = create_engine(restricted_url)
            real_engine = db.engine
            db.session.remove()
            app.extensions["sqlalchemy"].engines[None] = restricted_engine
            try:
                added, failed, blocking = [], [], []
                _ensure_enum_members(
                    dry_run=False, existing_tables={tablename}, added=added, failed=failed, blocking=blocking,
                )
            finally:
                app.extensions["sqlalchemy"].engines[None] = real_engine
                db.session.remove()
                restricted_engine.dispose()

            assert added == []
            assert failed == []
            assert len(blocking) == 2
            assert all("insufficient privilege" in item for item in blocking)
            assert any(typname in item for item in blocking)
            # Untouched: the denied ALTER never took effect.
            assert _labels(typname) == ["PENDING", "DONE"]
        finally:
            with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text(f"REVOKE ALL PRIVILEGES ON DATABASE {conn.engine.url.database} FROM {role}"))
                conn.execute(text(f"DROP OWNED BY {role}"))
                conn.execute(text(f"DROP ROLE IF EXISTS {role}"))


def test_batch_job_models_share_one_type_and_the_union_is_declared():
    """The two BatchJobStatus enums must keep resolving to one PG type name so
    the reconciler unions their labels rather than leaving one model unstorable."""
    from app.models.batch_import import BatchImportJob
    from app.models.batch_processing import BatchJob

    a = BatchJob.__table__.c.status.type
    b = BatchImportJob.__table__.c.status.type
    assert a.name == b.name == "batchjobstatus"
    assert {"RUNNING", "RECOVERING"} <= set(a.enums)
