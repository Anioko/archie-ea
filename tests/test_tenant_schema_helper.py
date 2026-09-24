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


def _strict_snapshot(conn, table):
    """Pin identities and definitions, not just names or object counts."""
    from sqlalchemy import text

    params = {"table": f'public."{table}"'}
    return {
        "rows": conn.execute(text(f'SELECT to_jsonb(t) FROM public."{table}" t ORDER BY id')).all(),
        "indexes": conn.execute(text(
            "SELECT indexrelid, pg_get_indexdef(indexrelid), indisvalid FROM pg_index "
            "WHERE indrelid = to_regclass(:table) ORDER BY indexrelid"
        ), params).all(),
        "constraints": conn.execute(text(
            "SELECT oid, conname, convalidated, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = to_regclass(:table) ORDER BY oid"
        ), params).all(),
    }


@pytest.mark.parametrize("shape", [
    "missing", "conventional", "alternate", "composite", "wrong_column", "other_table",
    "view", "other_namespace", "truncated", "missing_column", "missing_collision",
])
def test_strict_planner_index_identities_are_read_only(db_session, shape):
    from sqlalchemy import event, text

    from app.commands.tenant_schema import plan_organization_index_and_fk

    conn = db_session.connection()
    table = _scratch_table(db_session)
    if shape == "truncated":
        long_name = "zz_" + uuid.uuid4().hex + "x" * 25
        conn.execute(text(f'ALTER TABLE public."{table}" RENAME TO "{long_name}"'))
        table = long_name
    conventional = f"ix_{table}_organization_id"
    if shape in {"missing_column", "missing_collision"}:
        conn.execute(text(f'ALTER TABLE public."{table}" DROP COLUMN organization_id'))
    if shape in {"conventional", "alternate", "composite"}:
        name = conventional if shape == "conventional" else "idx_" + uuid.uuid4().hex
        columns = "organization_id, id" if shape == "composite" else "organization_id"
        conn.execute(text(f'CREATE INDEX "{name}" ON public."{table}" ({columns})'))
        if shape == "composite":
            conn.execute(text(f'CREATE INDEX "{conventional}" ON public."{table}" (id)'))
    elif shape in {"wrong_column", "truncated", "missing_collision"}:
        conn.execute(text(f'CREATE INDEX "{conventional}" ON public."{table}" (id)'))
    elif shape == "other_table":
        other = _scratch_table(db_session)
        conn.execute(text(f'CREATE INDEX "{conventional}" ON public."{other}" (organization_id)'))
    elif shape == "view":
        conn.execute(text(f'CREATE VIEW public."{conventional}" AS SELECT 1 AS id'))
    elif shape == "other_namespace":
        conn.execute(text(f'CREATE TEMP TABLE "{conventional}" (id INTEGER)'))
    before = _strict_snapshot(conn, table)
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(conn, "before_cursor_execute", observe)
    conflict = shape in {"wrong_column", "other_table", "view", "truncated", "missing_collision"}
    missing = shape in {"missing_column", "missing_collision"}
    try:
        if conflict:
            with pytest.raises(ValueError, match="occupied"):
                plan_organization_index_and_fk(conn, table, column_missing=missing)
        else:
            plan = plan_organization_index_and_fk(conn, table, column_missing=missing)
            assert plan == {"index": "present" if shape in {"conventional", "alternate", "composite"}
                            else "add", "foreign_key": "add"}
    finally:
        event.remove(conn, "before_cursor_execute", observe)
    assert statements and set(statements) == {"SELECT"}
    assert _strict_snapshot(conn, table) == before
    if conflict:
        with pytest.raises(ValueError, match="does not exist" if missing else "occupied"):
            _ensure(db_session, table, strict=True)
        assert _strict_snapshot(conn, table) == before
    elif not missing:
        _ensure(db_session, table, strict=True)
        after = _strict_snapshot(conn, table)
        assert _ensure(db_session, table, strict=True) == {"index": "present", "foreign_key": "present"}
        assert _strict_snapshot(conn, table) == after
        assert all(row in after["indexes"] for row in before["indexes"])


@pytest.mark.parametrize("shape", [
    "no_action", "cascade", "not_valid", "wrong_target", "wrong_target_column",
    "wrong_source", "composite", "orphan", "conventional_check",
])
def test_strict_fk_identity_and_existing_owners(db_session, make_org, shape):
    from sqlalchemy import text

    from app.commands.tenant_schema import plan_organization_index_and_fk

    org_id = make_org("strict-fk").id
    table = _scratch_table(db_session)
    conn = db_session.connection()
    conn.execute(text(f'ALTER TABLE public."{table}" ADD COLUMN other_id INTEGER'))
    name = f"fk_{table}_organization" if shape in {"wrong_source", "conventional_check"} else "fk_" + uuid.uuid4().hex
    if shape == "orphan":
        assert conn.execute(text("SELECT 1 FROM public.organizations WHERE id = -1")).first() is None
        conn.execute(text(f'INSERT INTO public."{table}" (organization_id) VALUES (-1)'))
    else:
        conn.execute(text(f'INSERT INTO public."{table}" (organization_id) VALUES (:org)'), {"org": org_id})
        if shape == "conventional_check":
            definition = "CHECK (organization_id > 0)"
        elif shape == "wrong_target_column":
            # Same target relation, different integer key: target identity alone
            # cannot establish the required organizations.id contract.
            conn.execute(text("ALTER TABLE public.organizations ADD COLUMN tenant_schema_probe INTEGER UNIQUE"))
            conn.execute(text("UPDATE public.organizations SET tenant_schema_probe = :org WHERE id = :org"), {"org": org_id})
            definition = "FOREIGN KEY (organization_id) REFERENCES public.organizations(tenant_schema_probe)"
        elif shape in {"wrong_target", "composite"}:
            other = _scratch_table(db_session)
            conn.execute(text(f'ALTER TABLE public."{other}" ADD UNIQUE (organization_id)'))
            conn.execute(text(f'ALTER TABLE public."{other}" ADD UNIQUE (organization_id, id)'))
            conn.execute(text(f'INSERT INTO public."{other}" (id, organization_id) VALUES (:org, :org)'), {"org": org_id})
            source = "organization_id, other_id" if shape == "composite" else "organization_id"
            destination = "organization_id, id" if shape == "composite" else (
                "organization_id" if shape == "wrong_target_column" else "id"
            )
            definition = f'FOREIGN KEY ({source}) REFERENCES public."{other}" ({destination})'
        else:
            source = "other_id" if shape == "wrong_source" else "organization_id"
            definition = f"FOREIGN KEY ({source}) REFERENCES public.organizations(id)"
            definition += " ON DELETE CASCADE" if shape == "cascade" else " ON DELETE NO ACTION"
            if shape == "not_valid":
                definition += " NOT VALID"
        conn.execute(text(f'ALTER TABLE public."{table}" ADD CONSTRAINT "{name}" {definition}'))
    before = _strict_snapshot(conn, table)
    if shape in {"no_action", "cascade"}:
        assert plan_organization_index_and_fk(conn, table)["foreign_key"] == "present"
        assert _ensure(db_session, table, strict=True) == {"index": "added", "foreign_key": "present"}
        assert _strict_snapshot(conn, table)["constraints"] == before["constraints"]
        assert _strict_snapshot(conn, table)["rows"] == before["rows"]
    else:
        for operation in (lambda: plan_organization_index_and_fk(conn, table),
                          lambda: _ensure(db_session, table, strict=True)):
            with pytest.raises(ValueError, match="conflicting constraint|invalid existing"):
                operation()
            assert _strict_snapshot(conn, table) == before
            assert conn.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.parametrize("fault", ["index_sql", "fk_sql", "catalog_sql", "index_postcondition", "fk_postcondition"])
def test_strict_step_sql_failure_restores_savepoint_and_allows_retry(db_session, fault):
    from sqlalchemy import event, text

    table = _scratch_table(db_session)
    conn = db_session.connection()
    conn.execute(text(f'INSERT INTO public."{table}" (organization_id) VALUES (NULL)'))
    before = _strict_snapshot(conn, table)
    fired, ddl_seen = [], []

    def fail_before(connection, cursor, statement, parameters, context, executemany):
        sql = statement.upper()
        if sql.startswith(("CREATE INDEX", "ALTER TABLE")):
            ddl_seen.append(sql)
        trigger = ((fault == "index_sql" and sql.startswith("CREATE INDEX"))
                   or (fault == "fk_sql" and "ADD CONSTRAINT" in sql)
                   or (fault == "catalog_sql" and ddl_seen and "PG_CATALOG" in sql))
        if trigger and not fired:
            fired.append(statement)
            cursor.execute("SELECT 1 / 0")

    def remove_object(connection, cursor, statement, parameters, context, executemany):
        if fired:
            return
        if fault == "index_postcondition" and statement.startswith("CREATE INDEX"):
            cursor.execute(f'DROP INDEX public."ix_{table}_organization_id"')
            fired.append(statement)
        elif fault == "fk_postcondition" and "ADD CONSTRAINT" in statement:
            cursor.execute(f'ALTER TABLE public."{table}" DROP CONSTRAINT "fk_{table}_organization"')
            fired.append(statement)

    event.listen(conn, "before_cursor_execute", fail_before)
    event.listen(conn, "after_cursor_execute", remove_object)
    try:
        with pytest.raises(Exception, match="division by zero|postcondition"):
            _ensure(db_session, table, strict=True)
    finally:
        event.remove(conn, "before_cursor_execute", fail_before)
        event.remove(conn, "after_cursor_execute", remove_object)
    assert fired
    after = _strict_snapshot(conn, table)
    assert after["rows"] == before["rows"]
    assert after["constraints"] == before["constraints"]
    if fault in {"index_sql", "catalog_sql", "index_postcondition"}:
        assert after["indexes"] == before["indexes"]
    else:
        assert _indexes(db_session, table) == [f"ix_{table}_organization_id"]
    assert conn.execute(text("SELECT 1")).scalar_one() == 1
    _ensure(db_session, table, strict=True)
    assert _ensure(db_session, table, strict=True) == {"index": "present", "foreign_key": "present"}


def test_default_mode_retains_broad_fk_and_savepoint_contract(db_session):
    from sqlalchemy import text

    table = _scratch_table(db_session)
    conn = db_session.connection()
    conn.execute(text(
        f'ALTER TABLE public."{table}" ADD CONSTRAINT "fk_{table}_legacy" '
        'FOREIGN KEY (organization_id) REFERENCES public.organizations(id) NOT VALID'
    ))
    before = _strict_snapshot(conn, table)
    assert _ensure(db_session, table) == {"index": "added", "foreign_key": "present"}
    assert _strict_snapshot(conn, table)["constraints"] == before["constraints"]
    with pytest.raises(ValueError, match="conflicting constraint"):
        _ensure(db_session, table, strict=True)
    assert conn.execute(text("SELECT 1")).scalar_one() == 1


def test_strict_public_identity_ignores_search_path_shadows(db_session):
    from sqlalchemy import text

    from app.commands.tenant_schema import plan_organization_index_and_fk

    table = _scratch_table(db_session)
    conn = db_session.connection()
    conn.execute(text(f'CREATE TEMP TABLE "{table}" (id INTEGER, organization_id INTEGER)'))
    conn.execute(text("CREATE TEMP TABLE organizations (id INTEGER PRIMARY KEY)"))
    conn.execute(text("SET LOCAL search_path = pg_temp, public"))
    assert plan_organization_index_and_fk(conn, table) == {"index": "add", "foreign_key": "add"}
    assert _ensure(db_session, table, strict=True) == {"index": "added", "foreign_key": "added"}
    rows = conn.execute(text(
        "SELECT conrelid, confrelid FROM pg_constraint WHERE conname = :name"
    ), {"name": f"fk_{table}_organization"}).all()
    assert rows == [tuple(conn.execute(text(
        "SELECT to_regclass(:table)::oid, 'public.organizations'::regclass::oid"
    ), {"table": f'public."{table}"'}).one())]
    assert conn.execute(text(
        "SELECT count(*) FROM pg_index WHERE indrelid = to_regclass(:table)"
    ), {"table": f'pg_temp."{table}"'}).scalar_one() == 0


def test_strict_catalog_preflight_sql_error_preserves_caller(db_session):
    from sqlalchemy import event, text

    table = _scratch_table(db_session)
    conn = db_session.connection()
    conn.execute(text(f'INSERT INTO public."{table}" (organization_id) VALUES (NULL)'))
    before = _strict_snapshot(conn, table)
    fired = []

    def fail_catalog(connection, cursor, statement, parameters, context, executemany):
        if "pg_catalog.pg_class" in statement and not fired:
            fired.append(statement)
            cursor.execute("SELECT 1 / 0")

    event.listen(conn, "before_cursor_execute", fail_catalog)
    try:
        with pytest.raises(Exception, match="division by zero"):
            _ensure(db_session, table, strict=True)
    finally:
        event.remove(conn, "before_cursor_execute", fail_catalog)
    assert fired
    assert _strict_snapshot(conn, table) == before
    assert conn.execute(text("SELECT 1")).scalar_one() == 1
    assert _ensure(db_session, table, strict=True) == {"index": "added", "foreign_key": "added"}
