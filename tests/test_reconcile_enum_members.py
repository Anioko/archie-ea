"""reconcile-schema must add missing PostgreSQL enum labels, additively.

Measured in production on 5 Sep 2026: `batchjobstatus` is shared by two models
with different Python members and lacked RUNNING / RECOVERING, so
BatchProcessingService could never mark a job running.  ADD COLUMN cannot
repair a label set; this pins the enum counterpart.
"""

import uuid

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, text
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
        added, failed = [], []
        _ensure_enum_members(dry_run=False, existing_tables={tablename}, added=added, failed=failed)
        assert failed == []
        assert added == [f"enum {typname} += RUNNING", f"enum {typname} += RE'COVERING"]
        assert set(_labels(typname)) == {"PENDING", "DONE", "RUNNING", "RE'COVERING"}

        # Idempotent: a second pass adds nothing and fails nothing.
        added, failed = [], []
        _ensure_enum_members(dry_run=False, existing_tables={tablename}, added=added, failed=failed)
        assert (added, failed) == ([], [])


def test_dry_run_reports_without_altering(app, probe_enum):
    from app.commands.reconcile_schema import _ensure_enum_members

    typname, tablename = probe_enum
    with app.app_context():
        added, failed = [], []
        _ensure_enum_members(dry_run=True, existing_tables={tablename}, added=added, failed=failed)
        assert f"enum {typname} += RUNNING" in added
        assert failed == []
        assert _labels(typname) == ["PENDING", "DONE"]


def test_batch_job_models_share_one_type_and_the_union_is_declared():
    """The two BatchJobStatus enums must keep resolving to one PG type name so
    the reconciler unions their labels rather than leaving one model unstorable."""
    from app.models.batch_import import BatchImportJob
    from app.models.batch_processing import BatchJob

    a = BatchJob.__table__.c.status.type
    b = BatchImportJob.__table__.c.status.type
    assert a.name == b.name == "batchjobstatus"
    assert {"RUNNING", "RECOVERING"} <= set(a.enums)
