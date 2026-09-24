"""backfill-review-queue-org derives each NULL-org review_queue_items row's
organization from its user FKs in a stated order of preference.

Scenario: items created before the TenantMixin migration, with
organization_id NULL, seeded for two different organisations via their
assigned_to_id / reviewed_by_id / escalated_to_id user references, plus
one unresolvable row (all user FKs NULL).
"""
import uuid

import pytest


def _user(db_session, org, label="u"):
    from app.models.user import User

    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"{label}-{suffix}@example.com",
        first_name="Test",
        last_name=label,
        organization_id=org.id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _item(db_session, org_id=None, item_name=None, assigned_to_id=None,
          reviewed_by_id=None, escalated_to_id=None):
    """Create a review queue item, optionally with NULL organization_id."""
    from app.models.confidence_review import ReviewQueueItem, ReviewStatus

    if item_name is None:
        item_name = f"item-{uuid.uuid4().hex[:8]}"
    row = ReviewQueueItem(
        organization_id=org_id,
        item_type="capability_mapping",
        item_id=1,
        item_name=item_name,
        item_data='{"key":"value"}',
        confidence_score=0.75,
        confidence_factors='{"factor":0.8}',
        ai_model_used="test-model",
        status=ReviewStatus.PENDING,
        review_priority=5,
        assigned_to_id=assigned_to_id,
        reviewed_by_id=reviewed_by_id,
        escalated_to_id=escalated_to_id,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _run(dry_run=False):
    """Invoke the backfill CLI command and return its output."""
    from app import create_app

    app = create_app("testing")
    runner = app.test_cli_runner()
    args = ["backfill-review-queue-org"]
    if dry_run:
        args.append("--dry-run")
    result = runner.invoke(args=args)
    return result


@pytest.fixture
def two_orgs(db_session, make_org):
    org_a = make_org("rq-backfill-a")
    org_b = make_org("rq-backfill-b")
    return org_a, org_b


def test_items_get_own_organisation(db_session, two_orgs):
    """Two NULL-org items, each with an assigned_to user in a different org,
    must each receive their user's organisation."""
    org_a, org_b = two_orgs
    user_a = _user(db_session, org_a, "reviewer-a")
    user_b = _user(db_session, org_b, "reviewer-b")

    item_a = _item(db_session, org_id=None, item_name="A-item", assigned_to_id=user_a.id)
    item_b = _item(db_session, org_id=None, item_name="B-item", assigned_to_id=user_b.id)
    db_session.commit()

    assert item_a.organization_id is None
    assert item_b.organization_id is None

    result = _run()
    assert result.exit_code == 0, f"backfill failed: {result.output}"

    db_session.refresh(item_a)
    db_session.refresh(item_b)

    assert item_a.organization_id == org_a.id, (
        f"item A should get org {org_a.id}, got {item_a.organization_id}"
    )
    assert item_b.organization_id == org_b.id, (
        f"item B should get org {org_b.id}, got {item_b.organization_id}"
    )


def test_dry_run_changes_nothing(db_session, two_orgs):
    """A dry run must report counts but leave organization_id NULL."""
    org_a, _org_b = two_orgs
    user_a = _user(db_session, org_a, "reviewer-a")

    item = _item(db_session, org_id=None, item_name="dry-run-item", assigned_to_id=user_a.id)
    db_session.commit()

    assert item.organization_id is None

    result = _run(dry_run=True)
    assert result.exit_code == 0
    assert "dry run" in result.output.lower()

    db_session.refresh(item)
    assert item.organization_id is None, "dry-run must not write"


def test_unresolvable_item_stays_null(db_session, two_orgs):
    """An item with no user FKs at all must stay NULL and be reported."""
    org_a, _org_b = two_orgs

    item = _item(db_session, org_id=None, item_name="orphan-item",
                 assigned_to_id=None, reviewed_by_id=None, escalated_to_id=None)
    db_session.commit()

    assert item.organization_id is None

    result = _run()
    # The command does not exit non-zero for unresolvable rows — it reports
    # them and leaves them NULL, same as backfill_ai_chat_feedback_org.
    assert result.exit_code == 0

    db_session.refresh(item)
    assert item.organization_id is None, "unresolvable item must stay NULL"


def test_backfill_is_idempotent(db_session, two_orgs):
    """Running twice must not change an already-backfilled row."""
    org_a, _org_b = two_orgs
    user_a = _user(db_session, org_a, "reviewer-a")

    item = _item(db_session, org_id=None, item_name="idempotent-item", assigned_to_id=user_a.id)
    db_session.commit()

    _run()
    db_session.refresh(item)
    first_org = item.organization_id
    assert first_org == org_a.id

    result2 = _run()
    assert result2.exit_code == 0

    db_session.refresh(item)
    assert item.organization_id == first_org, "idempotent re-run must not change org"


def test_reviewed_by_fallback(db_session, two_orgs):
    """When assigned_to_id is NULL, fall back to reviewed_by_id."""
    org_a, _org_b = two_orgs
    user_a = _user(db_session, org_a, "reviewer-a")

    item = _item(db_session, org_id=None, item_name="reviewed-by-item",
                 assigned_to_id=None, reviewed_by_id=user_a.id)
    db_session.commit()

    _run()
    db_session.refresh(item)

    assert item.organization_id == org_a.id


def test_escalated_to_fallback(db_session, two_orgs):
    """When assigned_to_id and reviewed_by_id are both NULL, fall back to escalated_to_id."""
    org_a, _org_b = two_orgs
    user_a = _user(db_session, org_a, "escalation-target")

    item = _item(db_session, org_id=None, item_name="escalated-item",
                 assigned_to_id=None, reviewed_by_id=None, escalated_to_id=user_a.id)
    db_session.commit()

    _run()
    db_session.refresh(item)

    assert item.organization_id == org_a.id


def test_preference_order_assigned_over_reviewed(db_session, two_orgs):
    """When both assigned_to_id and reviewed_by_id are set (to different orgs),
    assigned_to_id wins."""
    org_a, org_b = two_orgs
    user_a = _user(db_session, org_a, "assignee-a")
    user_b = _user(db_session, org_b, "reviewer-b")

    item = _item(db_session, org_id=None, item_name="pref-order-item",
                 assigned_to_id=user_a.id, reviewed_by_id=user_b.id)
    db_session.commit()

    _run()
    db_session.refresh(item)

    assert item.organization_id == org_a.id, (
        "assigned_to_id must take precedence over reviewed_by_id"
    )