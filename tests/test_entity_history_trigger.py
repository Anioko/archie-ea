"""R1-B19 PR 1: the generic entity_history trigger and its backfill.

The trigger/table are schema objects, not something a per-test rolled-back
transaction should create and discard every time (and a savepoint rollback
would undo the CREATE TRIGGER along with everything else) -- installed once
per test session directly on the engine, like the schema itself.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text


@pytest.fixture(scope="session", autouse=True)
def _entity_history_trigger(app, _schema):
    """Install the entity_history trigger once, directly on the engine."""
    from app import db
    from app.commands.apply_entity_history_trigger import FUNCTION_SQL, TABLES

    with app.app_context():
        conn = db.engine.connect()
        try:
            conn.execute(text(FUNCTION_SQL))
            for table in TABLES:
                conn.execute(text(f'DROP TRIGGER IF EXISTS entity_history_trg ON "{table}"'))
                conn.execute(text(f"""
                    CREATE TRIGGER entity_history_trg
                    AFTER INSERT OR UPDATE ON "{table}"
                    FOR EACH ROW
                    EXECUTE FUNCTION entity_history_record_version()
                """))
            conn.commit()
        finally:
            conn.close()
    yield


def _element(db_session, org, name="El"):
    from app.models.archimate_core import ArchiMateElement

    el = ArchiMateElement(name=name, type="ApplicationComponent", layer="application",
                           organization_id=org.id)
    db_session.add(el)
    db_session.flush()
    return el


def test_insert_leaves_one_open_version(app, db_session, make_org):
    org = make_org("eh-insert")
    el = _element(db_session, org, name=f"El-{uuid.uuid4().hex[:6]}")

    rows = db_session.execute(text(
        "SELECT valid_to FROM entity_history WHERE table_name='archimate_elements' AND record_id=:id"
    ), {"id": el.id}).fetchall()

    assert len(rows) == 1
    assert rows[0][0] is None


def test_two_updates_leave_three_non_overlapping_versions(app, db_session, make_org):
    org = make_org("eh-double-update")
    el = _element(db_session, org, name=f"El-{uuid.uuid4().hex[:6]}")

    db_session.execute(text("UPDATE archimate_elements SET name = name || '-a' WHERE id=:id"), {"id": el.id})
    db_session.commit()
    db_session.execute(text("UPDATE archimate_elements SET name = name || '-b' WHERE id=:id"), {"id": el.id})
    db_session.commit()

    rows = db_session.execute(text(
        "SELECT valid_from, valid_to FROM entity_history "
        "WHERE table_name='archimate_elements' AND record_id=:id ORDER BY valid_from"
    ), {"id": el.id}).fetchall()

    assert len(rows) == 3
    # Non-overlapping: each row's valid_to equals the next row's valid_from.
    for i in range(len(rows) - 1):
        assert rows[i][1] == rows[i + 1][0]
    # Exactly one open (current) version.
    open_count = sum(1 for r in rows if r[1] is None)
    assert open_count == 1


def test_as_of_snapshot_matches_the_state_recorded_at_that_time(app, db_session, make_org):
    """A test that the as-of answer for a date equals a snapshot taken on
    that date -- proven directly against entity_history rather than a PR 2
    service that does not exist yet in this PR."""
    org = make_org("eh-as-of")
    el = _element(db_session, org, name="Original")
    original_name = el.name

    db_session.execute(text("UPDATE archimate_elements SET name = 'Changed' WHERE id=:id"), {"id": el.id})
    db_session.commit()

    version_at_creation = db_session.execute(text(
        "SELECT snapshot->>'name' FROM entity_history "
        "WHERE table_name='archimate_elements' AND record_id=:id AND valid_to IS NOT NULL"
    ), {"id": el.id}).scalar()

    assert version_at_creation == original_name


def test_entity_history_excludes_a_foreign_organisations_rows(app, db_session, make_org):
    """Two-organisation test: entity_history is TenantMixin, so the ambient
    ORM filter (not a raw query) must exclude another organisation's
    versions -- the same fence every other tenant-scoped table gets."""
    from flask import g

    from app.models.entity_history import EntityHistory

    org_a, org_b = make_org("eh-iso-a"), make_org("eh-iso-b")
    el_a = _element(db_session, org_a, name=f"El-A-{uuid.uuid4().hex[:6]}")
    el_b = _element(db_session, org_b, name=f"SECRET-El-B-{uuid.uuid4().hex[:6]}")

    g.current_org_id = org_a.id
    visible_ids = {h.record_id for h in EntityHistory.query.filter_by(table_name="archimate_elements").all()}
    assert el_a.id in visible_ids
    assert el_b.id not in visible_ids


def test_backfill_seeds_one_open_version_per_pre_existing_row_with_no_history(app, db_session, make_org):
    """backfill-entity-history seeds a row that predates the trigger (no
    entity_history row at all yet) with one open version; recorded_at is
    NULL ("unknown") with no matching audit-log entry, per TB-0023."""
    from click.testing import CliRunner

    from app.commands.backfill_entity_history import backfill_entity_history

    org = make_org("eh-backfill")
    el = _element(db_session, org, name=f"El-{uuid.uuid4().hex[:6]}")
    db_session.commit()
    el_id = el.id

    # This row already has a trigger-written open version (the INSERT
    # above). Simulate "predates the trigger" by deleting it, the same
    # state a row created before apply-entity-history-trigger first ran
    # would be in.
    db_session.execute(text(
        "DELETE FROM entity_history WHERE table_name='archimate_elements' AND record_id=:id"
    ), {"id": el_id})
    db_session.commit()

    runner = CliRunner()
    result = runner.invoke(backfill_entity_history, [])
    assert result.exit_code == 0, result.output

    row = db_session.execute(text(
        "SELECT valid_to, recorded_at, source FROM entity_history "
        "WHERE table_name='archimate_elements' AND record_id=:id"
    ), {"id": el_id}).fetchone()

    assert row is not None
    assert row[0] is None  # open
    assert row[1] is None  # no audit-log entry for this test row -> unknown
    assert row[2] == "backfill"


def test_backfill_is_idempotent(app, db_session, make_org):
    from click.testing import CliRunner

    from app.commands.backfill_entity_history import backfill_entity_history

    org = make_org("eh-backfill-idempotent")
    _element(db_session, org, name=f"El-{uuid.uuid4().hex[:6]}")
    db_session.commit()

    runner = CliRunner()
    first = runner.invoke(backfill_entity_history, [])
    second = runner.invoke(backfill_entity_history, ["--dry-run"])
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "would seed 0 version" in second.output
