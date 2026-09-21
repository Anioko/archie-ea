"""Existing review queue items are attributed to an organisation, safely.

``backfill-review-queue-org`` attributes an item from the users named on it (the
assigned reviewer and the user who decided it), never from the application it is
about: ``item_id`` is supplied by whoever queues the item, so it says which
application an item concerns, not who created it. The application only checks the
users. An item whose users all belong to the application's organisation takes
that organisation; so does an item with no known application whose users share
one organisation. Every other item keeps no organisation and is listed for
nobody. The command only touches items without an organisation, so it can run
again, on an empty table, and after new items exist.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")

NOT_FOUND = {"success": False, "error": "Review item not found"}


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
    """Items covering every outcome of the backfill."""
    from app.commands.backfill_review_queue_org import run_backfill

    # Settle any unattributed rows already in the database, and remember what is
    # left, so the counts below are exactly those of the rows seeded here.
    leftover = run_backfill()["left"]

    org_a, org_b = make_org("backfill-a"), make_org("backfill-b")
    user_a, user_a2, user_b, user_b2 = (
        _make_user(db_session, o) for o in (org_a, org_a, org_b, org_b)
    )
    app_a, app_b = _application(db_session, org_a), _application(db_session, org_b)

    items = {
        # About an application, and every user named belongs to its organisation.
        "application_and_reviewer": _unattributed_item(
            db_session, "capability_mapping", app_a.id, assigned_to=user_a
        ),
        "application_and_both_reviewers": _unattributed_item(
            db_session, "process_mapping", app_b.id, assigned_to=user_b, reviewed_by=user_b2
        ),
        # Not about a known application: the users share one organisation.
        "assigned_reviewer": _unattributed_item(
            db_session, "archimate_element", 999, assigned_to=user_a
        ),
        "deciding_user": _unattributed_item(
            db_session, "archimate_element", 999, reviewed_by=user_b
        ),
        "reviewers_agree": _unattributed_item(
            db_session, "archimate_element", 999, assigned_to=user_a, reviewed_by=user_a2
        ),
        "application_that_does_not_exist": _unattributed_item(
            db_session, "capability_mapping", 0, assigned_to=user_a2
        ),
        # Left without an organisation.
        "application_only": _unattributed_item(db_session, "capability_mapping", app_a.id),
        "other_application_only": _unattributed_item(db_session, "vendor_analysis", app_b.id),
        "application_of_another_organisation": _unattributed_item(
            db_session, "vendor_analysis", app_b.id, assigned_to=user_a
        ),
        "application_of_another_organisation_decided": _unattributed_item(
            db_session, "taxonomy_validation", app_b.id, reviewed_by=user_a
        ),
        "reviewers_disagree": _unattributed_item(
            db_session, "archimate_element", 999, assigned_to=user_a, reviewed_by=user_b
        ),
        "application_and_reviewers_disagree": _unattributed_item(
            db_session, "capability_mapping", app_a.id, assigned_to=user_a, reviewed_by=user_b
        ),
        "no_reviewers": _unattributed_item(db_session, "archimate_element", 999),
    }
    # Commit so a dry run, which rolls back its own statements, keeps these rows.
    db_session.commit()
    return {
        "items": items,
        "orgs": (org_a, org_b),
        "leftover": leftover,
        "expected": {
            "application_and_reviewer": org_a.id,
            "application_and_both_reviewers": org_b.id,
            "assigned_reviewer": org_a.id,
            "deciding_user": org_b.id,
            "reviewers_agree": org_a.id,
            "application_that_does_not_exist": org_a.id,
            "application_only": None,
            "other_application_only": None,
            "application_of_another_organisation": None,
            "application_of_another_organisation_decided": None,
            "reviewers_disagree": None,
            "application_and_reviewers_disagree": None,
            "no_reviewers": None,
        },
        "counts": {
            "attributed": {"reviewers_and_application": 2, "reviewers": 4},
            "left": {
                "application_only": 2,
                "no_evidence": 1,
                "reviewers_disagree": 2,
                "application_conflict": 2,
            },
            "by_organisation": {org_a.id: 4, org_b.id: 2},
        },
    }


def _expected_stats(seeded):
    """The stats a run over the seeded items reports, on top of what was left before."""
    counts = seeded["counts"]
    left = {name: seeded["leftover"][name] + n for name, n in counts["left"].items()}
    return {
        "attributed": counts["attributed"],
        "left": left,
        "by_organisation": counts["by_organisation"],
        "examined": sum(counts["attributed"].values()) + sum(left.values()),
        "remaining_nulls": sum(left.values()),
    }


def test_each_outcome_attributes_or_leaves_its_items(db_session, seeded):
    from app.commands.backfill_review_queue_org import run_backfill

    result = run_backfill()

    assert result == _expected_stats(seeded)
    for name, item_id in seeded["items"].items():
        assert _organisation_of(db_session, item_id) == seeded["expected"][name], name


def test_an_application_alone_never_attributes_an_item(db_session, seeded):
    """An item that names an application and no user stays unattributed."""
    from app.commands.backfill_review_queue_org import run_backfill

    run_backfill()

    for name in ("application_only", "other_application_only"):
        assert _organisation_of(db_session, seeded["items"][name]) is None, name


def test_users_of_another_organisation_than_the_application_leave_the_item_unattributed(
    db_session, seeded
):
    from app.commands.backfill_review_queue_org import run_backfill

    run_backfill()

    for name in (
        "application_of_another_organisation",
        "application_of_another_organisation_decided",
        "application_and_reviewers_disagree",
    ):
        assert _organisation_of(db_session, seeded["items"][name]) is None, name


def test_an_item_naming_another_organisations_application_is_visible_to_neither_after_the_backfill(
    db_session, client, login_as, make_org
):
    """The author's item about someone else's application is handed to nobody."""
    from app.commands.backfill_review_queue_org import run_backfill

    org_author, org_owner = make_org("backfill-author"), make_org("backfill-owner")
    author, owner = _make_user(db_session, org_author), _make_user(db_session, org_owner)
    application = _application(db_session, org_owner)
    other_org_item = _unattributed_item(
        db_session, "capability_mapping", application.id, assigned_to=author
    )
    owned_item = _unattributed_item(
        db_session, "capability_mapping", application.id, assigned_to=owner
    )
    db_session.commit()

    run_backfill()

    assert _organisation_of(db_session, other_org_item) is None
    assert _organisation_of(db_session, owned_item) == org_owner.id
    for user in (owner, author):
        login_as(client, user)
        response = client.get(f"/api/confidence/queue/{other_org_item}")
        assert (response.status_code, response.get_json()) == (404, NOT_FOUND)
        login_as(client, user)
        listing = client.get("/api/confidence/queue?limit=100").get_json()
        assert other_org_item not in {item["id"] for item in listing["items"]}
    # The owning organisation reads the item its own user was assigned; the author does not.
    login_as(client, owner)
    assert client.get(f"/api/confidence/queue/{owned_item}").status_code == 200
    login_as(client, author)
    assert client.get(f"/api/confidence/queue/{owned_item}").status_code == 404


def test_running_the_backfill_again_changes_nothing(db_session, seeded):
    from app.commands.backfill_review_queue_org import run_backfill

    first = run_backfill()
    stored = {name: _organisation_of(db_session, i) for name, i in seeded["items"].items()}
    second = run_backfill()

    # Only the items still without an organisation are examined the second time.
    assert second["attributed"] == {"reviewers_and_application": 0, "reviewers": 0}
    assert second["left"] == first["left"]
    assert second["by_organisation"] == {}
    assert second["remaining_nulls"] == first["remaining_nulls"]
    assert {name: _organisation_of(db_session, i) for name, i in seeded["items"].items()} == stored


def test_an_item_that_already_has_an_organisation_is_left_alone(db_session, seeded):
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill

    org_a, org_b = seeded["orgs"]
    application = _application(db_session, org_a)
    user_a = _make_user(db_session, org_a)
    item_id = _unattributed_item(
        db_session, "capability_mapping", application.id, assigned_to=user_a
    )
    db_session.execute(
        text("UPDATE review_queue_items SET organization_id = :org WHERE id = :id"),
        {"org": org_b.id, "id": item_id},
    )

    run_backfill()

    assert _organisation_of(db_session, item_id) == org_b.id


def test_a_dry_run_reports_the_counts_and_changes_nothing(db_session, seeded):
    from app.commands.backfill_review_queue_org import run_backfill

    dry = run_backfill(dry_run=True)

    assert dry == _expected_stats(seeded)
    for item_id in seeded["items"].values():
        assert _organisation_of(db_session, item_id) is None
    assert run_backfill() == dry


def test_a_dry_run_prints_each_outcome_and_where_items_would_land(app, db_session, seeded):
    from app.commands.backfill_review_queue_org import backfill_review_queue_org

    result = app.test_cli_runner().invoke(backfill_review_queue_org, ["--dry-run"])

    assert result.exit_code == 0, result.output
    org_a, org_b = seeded["orgs"]
    assert "(dry-run)" in result.output
    for name in (
        "reviewers_and_application",
        "reviewers",
        "application_only",
        "no_evidence",
        "reviewers_disagree",
        "application_conflict",
    ):
        assert name in result.output
    placed = "would attribute to: organisation %d: 4, organisation %d: 2" % (org_a.id, org_b.id)
    assert placed in result.output
    # Nothing was written.
    for item_id in seeded["items"].values():
        assert _organisation_of(db_session, item_id) is None


def test_the_backfill_runs_on_an_empty_table(db_session):
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill

    db_session.execute(text("DELETE FROM review_decisions"))
    db_session.execute(text("DELETE FROM review_queue_items"))

    empty = {
        "attributed": {"reviewers_and_application": 0, "reviewers": 0},
        "left": {
            "application_only": 0,
            "no_evidence": 0,
            "reviewers_disagree": 0,
            "application_conflict": 0,
        },
        "by_organisation": {},
        "examined": 0,
        "remaining_nulls": 0,
    }
    assert run_backfill() == empty
    assert run_backfill(dry_run=True) == empty


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
