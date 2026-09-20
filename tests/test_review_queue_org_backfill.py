"""Existing review queue items are attributed to an organisation, safely.

``backfill-review-queue-org`` gives each item without an organisation the first
answer that applies: the organisation of the reviewed application, then the
organisation shared by the assigned reviewer and the deciding user. An item
neither rule resolves keeps no organisation, so it is listed for nobody. The
command only touches items without an organisation, so it can run again, on an
empty table, and after new items exist.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org):
    from werkzeug.security import generate_password_hash

    from app.models.user import User

    user = User(
        email=f"backfill-{uuid.uuid4().hex[:10]}@example.com",
        first_name="Backfill",
        last_name="Tester",
        confirmed=True,
        organization_id=org.id,
        password_hash=generate_password_hash(uuid.uuid4().hex),
    )
    db_session.add(user)
    db_session.flush()
    return user


def _application(db_session, org):
    from app.models.application_portfolio import ApplicationComponent

    application = ApplicationComponent(name=f"App {uuid.uuid4().hex[:8]}", organization_id=org.id)
    db_session.add(application)
    db_session.flush()
    return application


def _unattributed_item(db_session, item_type, item_id, assigned_to=None, reviewed_by=None):
    """An item as it exists before the backfill: no organisation."""
    from sqlalchemy import text

    from app.models.confidence_review import ReviewQueueItem

    item = ReviewQueueItem(
        item_type=item_type,
        item_id=item_id,
        item_name=f"Item {uuid.uuid4().hex[:8]}",
        confidence_score=0.5,
        assigned_to_id=getattr(assigned_to, "id", None),
        reviewed_by_id=getattr(reviewed_by, "id", None),
    )
    db_session.add(item)
    db_session.flush()
    db_session.execute(
        text("UPDATE review_queue_items SET organization_id = NULL WHERE id = :id"),
        {"id": item.id},
    )
    db_session.expire(item)
    return item.id


def _organisation_of(db_session, item_id):
    from sqlalchemy import text

    return db_session.execute(
        text("SELECT organization_id FROM review_queue_items WHERE id = :id"), {"id": item_id}
    ).scalar()


@pytest.fixture
def seeded(db_session, make_org):
    """Items covering every rule and every way to stay unattributed."""
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill

    # Settle any unattributed rows already in the database, so the counts below
    # are exactly those of the rows seeded here.
    run_backfill()
    leftover = db_session.execute(
        text("SELECT count(*) FROM review_queue_items WHERE organization_id IS NULL")
    ).scalar()

    org_a, org_b = make_org("backfill-a"), make_org("backfill-b")
    user_a, user_a2, user_b = (_make_user(db_session, o) for o in (org_a, org_a, org_b))
    app_a, app_b = _application(db_session, org_a), _application(db_session, org_b)

    items = {
        # Rule 1: the reviewed application's organisation.
        "application": _unattributed_item(db_session, "capability_mapping", app_a.id),
        # The application wins over a reviewer from another organisation.
        "application_over_reviewer": _unattributed_item(
            db_session, "vendor_analysis", app_b.id, assigned_to=user_a
        ),
        # Rule 2: an item type with no application behind it, resolved by reviewers.
        "assigned_reviewer": _unattributed_item(
            db_session, "archimate_element", 999, assigned_to=user_a
        ),
        "deciding_user": _unattributed_item(
            db_session, "archimate_element", 999, reviewed_by=user_b
        ),
        "reviewers_agree": _unattributed_item(
            db_session, "archimate_element", 999, assigned_to=user_a, reviewed_by=user_a2
        ),
        # Left without an organisation.
        "reviewers_disagree": _unattributed_item(
            db_session, "archimate_element", 999, assigned_to=user_a, reviewed_by=user_b
        ),
        "no_reviewers": _unattributed_item(db_session, "archimate_element", 999),
        "unknown_application": _unattributed_item(db_session, "capability_mapping", 0),
    }
    # Commit so a dry run, which rolls back its own statements, keeps these rows.
    db_session.commit()
    return {
        "items": items,
        "orgs": (org_a, org_b),
        "leftover": leftover,
        "expected": {
            "application": org_a.id,
            "application_over_reviewer": org_b.id,
            "assigned_reviewer": org_a.id,
            "deciding_user": org_b.id,
            "reviewers_agree": org_a.id,
            "reviewers_disagree": None,
            "no_reviewers": None,
            "unknown_application": None,
        },
    }


def test_each_rule_attributes_its_items_and_the_rest_stay_unattributed(db_session, seeded):
    from app.commands.backfill_review_queue_org import run_backfill

    result = run_backfill()

    assert result == {"by_application": 2, "by_reviewer": 3, "remaining_nulls": seeded["leftover"] + 3}
    for name, item_id in seeded["items"].items():
        assert _organisation_of(db_session, item_id) == seeded["expected"][name], name


def test_running_the_backfill_again_changes_nothing(db_session, seeded):
    from app.commands.backfill_review_queue_org import run_backfill

    first = run_backfill()
    stored = {name: _organisation_of(db_session, i) for name, i in seeded["items"].items()}
    second = run_backfill()

    assert second == {"by_application": 0, "by_reviewer": 0, "remaining_nulls": first["remaining_nulls"]}
    assert {name: _organisation_of(db_session, i) for name, i in seeded["items"].items()} == stored


def test_an_item_that_already_has_an_organisation_is_left_alone(db_session, seeded):
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill

    org_a, org_b = seeded["orgs"]
    application = _application(db_session, org_a)
    item_id = _unattributed_item(db_session, "capability_mapping", application.id)
    db_session.execute(
        text("UPDATE review_queue_items SET organization_id = :org WHERE id = :id"),
        {"org": org_b.id, "id": item_id},
    )

    run_backfill()

    assert _organisation_of(db_session, item_id) == org_b.id


def test_a_dry_run_reports_the_counts_and_changes_nothing(db_session, seeded):
    from app.commands.backfill_review_queue_org import run_backfill

    dry = run_backfill(dry_run=True)

    assert dry == {"by_application": 2, "by_reviewer": 3, "remaining_nulls": seeded["leftover"] + 3}
    for item_id in seeded["items"].values():
        assert _organisation_of(db_session, item_id) is None
    assert run_backfill() == dry


def test_the_backfill_runs_on_an_empty_table(db_session):
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill

    db_session.execute(text("DELETE FROM review_decisions"))
    db_session.execute(text("DELETE FROM review_queue_items"))

    assert run_backfill() == {"by_application": 0, "by_reviewer": 0, "remaining_nulls": 0}
    assert run_backfill(dry_run=True) == {"by_application": 0, "by_reviewer": 0, "remaining_nulls": 0}


def test_the_backfill_leaves_one_index_and_one_foreign_key_on_the_column(db_session):
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill

    run_backfill()
    run_backfill()

    foreign_keys = db_session.execute(
        text(
            "SELECT count(*) FROM pg_constraint c "
            "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
            "WHERE c.conrelid = 'review_queue_items'::regclass AND c.contype = 'f' "
            "AND a.attname = 'organization_id'"
        )
    ).scalar()
    indexes = db_session.execute(
        text(
            "SELECT count(*) FROM pg_indexes WHERE tablename = 'review_queue_items' "
            "AND indexdef LIKE '%(organization_id)%'"
        )
    ).scalar()
    assert foreign_keys == 1
    assert indexes == 1
