"""A tenant column added to an existing table gets its index and foreign key once.

``ensure_organization_index_and_fk`` is the one place the ``backfill-*-org``
commands finish a column that ``reconcile-schema`` added as a plain nullable
INTEGER. It finds what already exists by looking at the column, not at a
constraint or index name, so it never adds a duplicate, and a step that fails is
reported without aborting the caller's transaction.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")

SIBLING_TABLES = ["ai_chat_crud_approvals", "outcomes", "saved_diagrams", "review_queue_items"]


def _scratch_table(db_session, *, foreign_key=None, index=None, orphan_organization=False):
    """A table shaped like one reconcile-schema has just added the column to."""
    from sqlalchemy import text

    name = "zz_tenant_schema_" + uuid.uuid4().hex[:8]
    conn = db_session.connection()
    conn.execute(text(f'CREATE TABLE "{name}" (id SERIAL PRIMARY KEY, organization_id INTEGER)'))
    if foreign_key:
        conn.execute(
            text(
                f'ALTER TABLE "{name}" ADD CONSTRAINT {foreign_key} '
                "FOREIGN KEY (organization_id) REFERENCES organizations(id)"
            )
        )
    if index:
        conn.execute(text(f'CREATE INDEX {index} ON "{name}" (organization_id)'))
    if orphan_organization:
        conn.execute(text(f'INSERT INTO "{name}" (organization_id) VALUES (2147483000)'))
    return name


def _foreign_keys(db_session, table):
    from sqlalchemy import text

    return sorted(
        row[0]
        for row in db_session.connection().execute(
            text(
                "SELECT c.conname FROM pg_constraint c "
                "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
                "WHERE c.conrelid = to_regclass(:table) AND c.contype = 'f' "
                "AND a.attname = 'organization_id'"
            ),
            {"table": f'"{table}"'},
        )
    )


def _indexes(db_session, table):
    from sqlalchemy import text

    return sorted(
        row[0]
        for row in db_session.connection().execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE tablename = :table "
                "AND indexdef LIKE '%(organization_id)%'"
            ),
            {"table": table},
        )
    )


def _ensure(db_session, table, **kwargs):
    from app.commands.tenant_schema import ensure_organization_index_and_fk

    return ensure_organization_index_and_fk(db_session.connection(), table, **kwargs)


def test_neither_present_adds_both_under_the_conventional_names(db_session):
    table = _scratch_table(db_session)

    assert _ensure(db_session, table) == {"index": "added", "foreign_key": "added"}

    assert _foreign_keys(db_session, table) == [f"fk_{table}_organization"]
    assert _indexes(db_session, table) == [f"ix_{table}_organization_id"]


def test_a_second_run_finds_both_and_adds_nothing(db_session):
    table = _scratch_table(db_session)

    _ensure(db_session, table)
    second = _ensure(db_session, table)

    assert second == {"index": "present", "foreign_key": "present"}
    assert len(_foreign_keys(db_session, table)) == 1
    assert len(_indexes(db_session, table)) == 1


def test_a_foreign_key_under_another_name_is_recognised(db_session):
    """A database built by create_all names its foreign key differently."""
    table = _scratch_table(db_session, foreign_key="named_by_create_all_fkey")

    assert _ensure(db_session, table) == {"index": "added", "foreign_key": "present"}

    assert _foreign_keys(db_session, table) == ["named_by_create_all_fkey"]


def test_no_foreign_key_means_one_is_added_even_when_the_index_exists(db_session):
    table = _scratch_table(db_session, index="some_other_index_name")

    assert _ensure(db_session, table) == {"index": "present", "foreign_key": "added"}

    assert _indexes(db_session, table) == ["some_other_index_name"]
    assert _foreign_keys(db_session, table) == [f"fk_{table}_organization"]


def test_an_index_under_another_name_is_recognised(db_session):
    table = _scratch_table(db_session, index="some_other_index_name", foreign_key="already_here")

    assert _ensure(db_session, table) == {"index": "present", "foreign_key": "present"}

    assert _indexes(db_session, table) == ["some_other_index_name"]
    assert _foreign_keys(db_session, table) == ["already_here"]


def test_a_foreign_key_on_another_column_does_not_count(db_session):
    """Only a foreign key on organization_id to organizations satisfies the check."""
    from sqlalchemy import text

    name = "zz_tenant_schema_" + uuid.uuid4().hex[:8]
    db_session.connection().execute(
        text(
            f'CREATE TABLE "{name}" (id SERIAL PRIMARY KEY, organization_id INTEGER, '
            "created_by INTEGER REFERENCES users(id))"
        )
    )

    assert _ensure(db_session, name)["foreign_key"] == "added"

    assert _foreign_keys(db_session, name) == [f"fk_{name}_organization"]


def test_a_failing_step_is_reported_and_the_callers_work_survives(db_session):
    """A foreign key over a row naming no organisation fails alone."""
    from sqlalchemy import text

    table = _scratch_table(db_session, orphan_organization=True)
    lines = []

    result = _ensure(db_session, table, echo=lines.append)

    assert result["index"] == "added"
    assert result["foreign_key"].startswith("failed:")
    assert any(line.startswith(f"  ! {table}: foreign key skipped") for line in lines)
    # The failed step was rolled back on its own: the transaction is still usable
    # and the row written before the helper ran is still there.
    count = db_session.connection().execute(text(f'SELECT count(*) FROM "{table}"')).scalar()
    assert count == 1
    assert _indexes(db_session, table) == [f"ix_{table}_organization_id"]
    assert _foreign_keys(db_session, table) == []


def test_a_failing_step_raises_when_strict_and_the_transaction_is_still_usable(db_session):
    from sqlalchemy import text

    table = _scratch_table(db_session, orphan_organization=True)

    with pytest.raises(Exception):  # noqa: B017 - the driver's foreign key violation
        _ensure(db_session, table, strict=True)

    count = db_session.connection().execute(text(f'SELECT count(*) FROM "{table}"')).scalar()
    assert count == 1


def test_echo_reports_each_step(db_session):
    table = _scratch_table(db_session, foreign_key="already_here")
    lines = []

    _ensure(db_session, table, echo=lines.append)

    assert lines == [f"  + {table}: index", f"  = {table}: foreign key already present"]


def test_a_table_without_the_column_or_with_an_unsafe_name_is_refused(db_session):
    from sqlalchemy import text

    name = "zz_tenant_schema_" + uuid.uuid4().hex[:8]
    db_session.connection().execute(text(f'CREATE TABLE "{name}" (id SERIAL PRIMARY KEY)'))

    with pytest.raises(ValueError, match="does not exist"):
        _ensure(db_session, name)
    with pytest.raises(ValueError, match="not a plain table name"):
        _ensure(db_session, 'x"; DROP TABLE users; --')


@pytest.mark.parametrize("table", SIBLING_TABLES)
def test_each_backfill_command_table_ends_with_one_index_and_one_foreign_key(db_session, table):
    """The tables of the four commands that call the helper.

    Covers the shape of every table a backfill command finishes: after the helper
    runs, twice, the column has exactly one foreign key and one index.
    """
    first = _ensure(db_session, table)
    second = _ensure(db_session, table)

    assert not first["index"].startswith("failed") and not first["foreign_key"].startswith("failed")
    assert second == {"index": "present", "foreign_key": "present"}
    assert len(_foreign_keys(db_session, table)) == 1
    assert len(_indexes(db_session, table)) == 1
