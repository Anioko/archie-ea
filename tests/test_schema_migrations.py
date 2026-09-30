"""Versioned schema changes: the baseline and the expand-and-contract examples.

These drive the same commands the deploy runs (scripts/database/deploy-schema.sh)
as subprocesses against throwaway databases, because what is under test is the
deploy sequence itself: ``init-db``, then ``schema-upgrade``, then
``reconcile-schema``.

- On a database built by ``init-db`` + ``reconcile-schema`` (every deployed
  database) the baseline revision changes nothing.
- On an empty database the baseline builds the full schema.
- A database stamped with a revision from before the baseline upgrades instead
  of stopping the deploy.
- The two example revisions are idempotent, and their down steps restore the
  prior type and nullability without losing a row, refusing (and changing
  nothing) when restoring them would discard data.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE = "20260926_baseline"
RELAX = "20260926_relax_owner_app"
HEAD = "20260926_widen_element_name"

_DEFAULT_URL = "postgresql://postgres:postgres@127.0.0.1:5432/archie_test"


def _server_url():
    return make_url(os.environ.get("TEST_DATABASE_URL") or _DEFAULT_URL)


def _admin_engine():
    return create_engine(
        _server_url().set(database="postgres"), isolation_level="AUTOCOMMIT"
    )


@pytest.fixture(scope="module")
def scratch_databases():
    """Create throwaway databases on the test server; drop them afterwards."""
    admin = _admin_engine()
    created = []

    def make(label, template="template0"):
        name = f"archie_schema_{label}_{uuid.uuid4().hex[:8]}"
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{template}"'))
        created.append(name)
        return _server_url().set(database=name).render_as_string(hide_password=False)

    yield make

    with admin.connect() as conn:
        for name in created:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


# Runs several CLI commands against one app instance, so a sequence of deploy
# steps pays for one application boot instead of one per command. Stops at
# the first command that fails. An exception a command raises (a refused down
# step, for instance) is part of that command's output.
_DRIVER = r"""
import json, sys
from flask.cli import FlaskGroup
from manage import app
cli = FlaskGroup(create_app=lambda: app)  # what `flask --app manage` builds
runner = app.test_cli_runner()
results = []
for args in json.loads(sys.argv[1]):
    r = runner.invoke(cli=cli, args=args)
    text = r.output
    if r.exception is not None and not isinstance(r.exception, SystemExit):
        text += "\n" + type(r.exception).__name__ + ": " + str(r.exception)
    results.append([r.exit_code, text])
    if r.exit_code:
        break
print("@@RESULTS@@" + json.dumps(results))
"""


def _flask(url, *commands, check=True):
    """Run each command (a list of CLI arguments) in order; return (exit code, output).

    The exit code is the first non-zero one, else 0; output joins every
    command's output.
    """
    env = dict(os.environ)
    env.update(DATABASE_URL=url, TEST_DATABASE_URL=url, DEV_DATABASE_URL=url)
    env.setdefault("FLASK_CONFIG", "testing")
    proc = subprocess.run(
        [sys.executable, "-c", _DRIVER, json.dumps([list(c) for c in commands])],
        cwd=REPO_ROOT, env=env, capture_output=True, timeout=1800,
        # Explicit encoding, not text=True's locale default: the CLI commands
        # print unicode checkmarks/arrows, and Windows' default locale codec
        # (cp1252) cannot decode them -- the pipe reader thread then crashes
        # mid-read and leaves proc.stdout/stderr as None, which the += below
        # cannot concatenate. errors="replace" keeps a decode surprise from
        # crashing the reader thread on any other unexpected byte too.
        encoding="utf-8", errors="replace",
    )
    raw = proc.stdout + proc.stderr
    assert "@@RESULTS@@" in proc.stdout, f"command driver did not finish:\n{raw[-4000:]}"
    results = json.loads(proc.stdout.rsplit("@@RESULTS@@", 1)[1].splitlines()[0])
    code = next((c for c, _ in results if c), 0)
    output = "\n".join(o for _, o in results)
    if check:
        ran = [" ".join(c) for c in commands[:len(results)]]
        assert code == 0 and len(results) == len(commands), (
            f"flask {ran[-1]} failed:\n{output[-4000:]}"
        )
    return code, output


def _snapshot(url):
    """Every column, index and constraint in the current schema."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            columns = set(conn.execute(text(
                "SELECT table_name, column_name, data_type, character_maximum_length, "
                "is_nullable, column_default FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name <> 'alembic_version'"
            )).all())
            indexes = set(conn.execute(text(
                "SELECT tablename, indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = current_schema() AND tablename <> 'alembic_version'"
            )).all())
            constraints = set(conn.execute(text(
                "SELECT c.conrelid::regclass::text, c.conname, pg_get_constraintdef(c.oid) "
                "FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
                "WHERE n.nspname = current_schema() "
                "AND c.conrelid::regclass::text <> 'alembic_version'"
            )).all())
    finally:
        engine.dispose()
    return {"columns": columns, "indexes": indexes, "constraints": constraints}


def _tables(snapshot):
    return {row[0] for row in snapshot["columns"]}


def _recorded(url):
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT to_regclass('alembic_version')")).scalar() is None:
                return []
            return [r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version"))]
    finally:
        engine.dispose()


def _column(url, table, column):
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(text(
                "SELECT character_maximum_length, is_nullable "
                "FROM information_schema.columns WHERE table_schema = current_schema() "
                "AND table_name = :t AND column_name = :c"
            ), {"t": table, "c": column}).one()
    finally:
        engine.dispose()


def _deploy_schema(url):
    """The table and column steps of scripts/database/deploy-schema.sh before this change."""
    _flask(
        url,
        ["init-db"],
        ["reconcile-schema"],
        ["apply-unified-capability-provenance-migration"],
    )


@pytest.fixture(scope="module")
def deployed_template(scratch_databases):
    """One database built the way every deployed one is; copied per test."""
    url = scratch_databases("deployed")
    _deploy_schema(url)
    return make_url(url).database


@pytest.fixture
def deployed_db(scratch_databases, deployed_template):
    return scratch_databases("copy", template=deployed_template)


# ------------------------------------------------------------ baseline


def test_baseline_changes_nothing_on_a_database_built_by_init_db_and_reconcile(deployed_db):
    before = _snapshot(deployed_db)
    assert _recorded(deployed_db) == []

    # The upgrade, then reconcile-schema, the drift detector that runs next.
    _, output = _flask(
        deployed_db, ["schema-upgrade", "--to", BASELINE], ["reconcile-schema", "--dry-run"]
    )

    assert _recorded(deployed_db) == [BASELINE], output
    after = _snapshot(deployed_db)
    assert after["columns"] == before["columns"]
    assert after["indexes"] == before["indexes"]
    assert after["constraints"] == before["constraints"]
    assert "reconcile-schema: 0 column(s) would add." in output, output
    assert "table(s) absent" not in output, output


def test_upgrade_on_an_empty_database_builds_the_full_schema(scratch_databases, deployed_db):
    empty = scratch_databases("empty")
    assert _tables(_snapshot(empty)) == set()

    _flask(empty, ["schema-upgrade", "--to", BASELINE])

    # Every table, as init-db would have created it.
    assert _recorded(empty) == [BASELINE]
    deployed = _snapshot(deployed_db)
    assert _tables(_snapshot(empty)) == _tables(deployed)

    # The rest of the deploy sequence then finishes exactly the schema an
    # init-db-built database has: the same columns, indexes and constraints.
    _flask(empty, ["reconcile-schema"], ["apply-unified-capability-provenance-migration"])
    built = _snapshot(empty)
    assert built["columns"] == deployed["columns"]
    assert built["indexes"] == deployed["indexes"]
    assert built["constraints"] == deployed["constraints"]


# ------------------------------------------------ expand / contract examples


def _insert(conn, table, values):
    """Insert one row, filling any other required column with a unique dummy."""
    required = conn.execute(text(
        "SELECT column_name, data_type, udt_name FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = :t "
        "AND is_nullable = 'NO' AND column_default IS NULL AND is_identity = 'NO'"
    ), {"t": table}).all()
    row = dict(values)
    for name, data_type, udt in required:
        if name in row:
            continue
        if data_type in ("integer", "bigint", "smallint", "numeric", "double precision", "real"):
            row[name] = 1
        elif data_type == "boolean":
            row[name] = False
        elif data_type.startswith("timestamp") or data_type == "date":
            row[name] = "2026-01-01"
        elif data_type in ("json", "jsonb"):
            row[name] = "{}"
        elif data_type == "uuid":
            row[name] = str(uuid.uuid4())
        elif data_type == "USER-DEFINED":
            row[name] = conn.execute(text(
                "SELECT enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = :u ORDER BY enumsortorder LIMIT 1"
            ), {"u": udt}).scalar()
        else:
            row[name] = uuid.uuid4().hex[:8]
    cols = ", ".join(f'"{c}"' for c in row)
    params = ", ".join(f":{c}" for c in row)
    conn.execute(text(f'INSERT INTO "{table}" ({cols}) VALUES ({params})'), row)


def _seed(url, rows):
    """Insert fixture rows with foreign keys and triggers off (superuser session)."""
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL session_replication_role = replica"))
        for table, values in rows:
            _insert(conn, table, values)
    engine.dispose()


def _rows(url):
    """Each organisation's element names and owner application ids."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            elements = sorted(conn.execute(text(
                "SELECT organization_id, name FROM archimate_elements ORDER BY 1, 2"
            )).all())
            owners = sorted(conn.execute(text(
                "SELECT organization_id, application_id FROM application_owners "
                "ORDER BY 1, 2 NULLS FIRST"
            )).all(), key=lambda r: (r[0], r[1] is not None, r[1] or 0))
    finally:
        engine.dispose()
    return elements, owners


def test_example_revisions_are_idempotent_and_reversible_without_data_loss(deployed_db):
    url = deployed_db
    org_a, org_b = 101, 202
    _seed(url, [
        ("archimate_elements", {"organization_id": org_a, "name": "A" * 100}),
        ("archimate_elements", {"organization_id": org_b, "name": "B element"}),
        ("application_owners", {"organization_id": org_a, "application_id": 11, "user_id": 1}),
        ("application_owners", {"organization_id": org_b, "application_id": 22, "user_id": 2}),
    ])
    assert tuple(_column(url, "application_owners", "application_id")) == (None, "NO")
    assert tuple(_column(url, "archimate_elements", "name")) == (100, "NO")
    seeded = _rows(url)

    # The database carries a stamp from the archived pre-baseline history, as a
    # long-lived one may. The upgrade replaces it instead of stopping the deploy.
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        ))
        conn.execute(text("INSERT INTO alembic_version VALUES ('fac924608f6e')"))
    engine.dispose()

    _, output = _flask(url, ["schema-upgrade"])
    assert "fac924608f6e" in output, output
    assert _recorded(url) == [HEAD]
    assert tuple(_column(url, "application_owners", "application_id")) == (None, "YES")
    assert _column(url, "archimate_elements", "name")[0] == 500
    assert _rows(url) == seeded

    # Each revision's upgrade step, run again on the expanded schema, changes nothing.
    from app.commands.schema_migrations import relax_not_null, widen_varchar

    engine = create_engine(url)
    with engine.begin() as conn:
        assert relax_not_null(conn, "application_owners", "application_id") is False
        assert widen_varchar(conn, "archimate_elements", "name", 500) is False
    engine.dispose()
    assert tuple(_column(url, "application_owners", "application_id")) == (None, "YES")
    assert _column(url, "archimate_elements", "name")[0] == 500

    # Down while every row still fits the old shape: type and NOT NULL come back,
    # every organisation keeps every row.
    _flask(url, ["db", "downgrade", BASELINE])
    assert _recorded(url) == [BASELINE]
    assert tuple(_column(url, "application_owners", "application_id")) == (None, "NO")
    assert _column(url, "archimate_elements", "name")[0] == 100
    assert _rows(url) == seeded

    # Use the expanded shape as organisation B, then try to go down again.
    _flask(url, ["schema-upgrade"])
    long_name = "L" * 400
    _seed(url, [
        ("archimate_elements", {"organization_id": org_b, "name": long_name}),
        ("application_owners", {"organization_id": org_b, "application_id": None, "user_id": 3}),
    ])
    expanded = _rows(url)

    code, output = _flask(url, ["db", "downgrade", BASELINE], check=False)
    assert code != 0
    assert "cannot be narrowed without truncating" in output, output[-3000:]
    # Refused: nothing changed, nothing lost, still recorded at head.
    assert _recorded(url) == [HEAD]
    assert _column(url, "archimate_elements", "name")[0] == 500
    assert _rows(url) == expanded
    assert (org_b, long_name) in expanded[0]
    assert all(org != org_a for org, name in expanded[0] if name == long_name)

    # With the long name shortened, the name narrows, and the next down step
    # refuses on the NULL owner: each revision commits or rolls back on its own.
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE archimate_elements SET name = 'short' WHERE name = :n"
        ), {"n": long_name})
    engine.dispose()
    code, output = _flask(url, ["db", "downgrade", BASELINE], check=False)
    assert code != 0
    assert "NOT NULL cannot be restored" in output, output[-3000:]
    assert _recorded(url) == [RELAX]
    assert _column(url, "archimate_elements", "name")[0] == 100
    assert tuple(_column(url, "application_owners", "application_id")) == (None, "YES")
    assert (org_b, None) in _rows(url)[1]


def test_expand_and_contract_helpers_are_idempotent_on_their_own(deployed_db):
    from app.commands.schema_migrations import (
        ContractBlocked,
        column_state,
        narrow_varchar,
        relax_not_null,
        tighten_not_null,
        widen_varchar,
    )

    engine = create_engine(deployed_db)
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            conn.execute(text("CREATE TABLE ec_probe (label VARCHAR(10) NOT NULL)"))
            conn.execute(text("INSERT INTO ec_probe VALUES ('0123456789')"))

            assert relax_not_null(conn, "ec_probe", "label") is True
            assert relax_not_null(conn, "ec_probe", "label") is False
            assert widen_varchar(conn, "ec_probe", "label", 40) is True
            assert widen_varchar(conn, "ec_probe", "label", 40) is False
            assert column_state(conn, "ec_probe", "label") == {
                "data_type": "character varying", "max_length": 40, "nullable": True,
            }

            conn.execute(text("INSERT INTO ec_probe VALUES (NULL), (:v)"), {"v": "x" * 30})
            with pytest.raises(ContractBlocked):
                tighten_not_null(conn, "ec_probe", "label")
            with pytest.raises(ContractBlocked):
                narrow_varchar(conn, "ec_probe", "label", 10)
            assert column_state(conn, "ec_probe", "label")["max_length"] == 40

            conn.execute(text("DELETE FROM ec_probe WHERE label IS NULL OR length(label) > 10"))
            assert tighten_not_null(conn, "ec_probe", "label") is True
            assert tighten_not_null(conn, "ec_probe", "label") is False
            assert narrow_varchar(conn, "ec_probe", "label", 10) is True
            assert narrow_varchar(conn, "ec_probe", "label", 10) is False
            assert conn.execute(text("SELECT label FROM ec_probe")).scalar() == "0123456789"
            trans.rollback()
    finally:
        engine.dispose()
