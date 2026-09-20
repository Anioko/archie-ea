"""Review queue items belong to one organisation and are visible only to it.

A signed-in user lists, reads, counts and decides the items of their own
organisation. An item id that belongs to another organisation answers exactly as
an id that does not exist, and a request that names it changes nothing.

Paths covered, each with items in two organisations (and a third with none):

* detail          GET  /api/confidence/queue/<id>
* decisions       GET  /api/confidence/queue/<id>/decisions
* assign          POST /api/confidence/queue/<id>/assign
* submit decision POST /api/confidence/queue/<id>/review
* approve         POST /api/review-queue/<id>/approve
* reject          POST /api/review-queue/<id>/reject
* bulk approve    POST /api/review-queue/bulk-approve
* bulk reject     POST /api/review-queue/bulk-reject
* queue listing   GET  /api/confidence/queue and GET /api/review-queue
* pending listing GET  /reviews/api/pending and the service call behind it
* statistics      GET  /api/confidence/statistics and /api/review-queue/statistics

plus how a new item takes its organisation, and that an item with no
organisation is listed for nobody.
"""

from __future__ import annotations

import json
import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")

NOT_FOUND = {"success": False, "error": "Review item not found"}


def _make_user(db_session, org):
    from werkzeug.security import generate_password_hash

    from app.models.user import User

    user = User(
        email=f"review-{uuid.uuid4().hex[:10]}@example.com",
        first_name="Review",
        last_name="Tester",
        confirmed=True,
        organization_id=org.id,
        password_hash=generate_password_hash(uuid.uuid4().hex),
    )
    db_session.add(user)
    db_session.flush()
    return user


def _add_item(db_session, org, *, status=None, assigned_to=None, **fields):
    """Create a queue item and attribute it to ``org`` (None leaves it unattributed).

    The organisation is written with an UPDATE, the way the backfill does it, so
    a fixture states its owner explicitly instead of taking it from whatever
    request context happens to be active.
    """
    from sqlalchemy import text

    from app.models.confidence_review import ReviewQueueItem, ReviewStatus

    values = {
        "item_type": "capability_mapping",
        "item_id": 1,
        "item_name": f"Mapping {uuid.uuid4().hex[:8]}",
        "item_data": json.dumps({"note": uuid.uuid4().hex[:8]}),
        "confidence_score": 0.55,
        "status": status or ReviewStatus.PENDING,
        "assigned_to_id": getattr(assigned_to, "id", None),
    }
    values.update(fields)
    item = ReviewQueueItem(**values)
    db_session.add(item)
    db_session.flush()
    db_session.execute(
        text("UPDATE review_queue_items SET organization_id = :org WHERE id = :id"),
        {"org": org.id if org is not None else None, "id": item.id},
    )
    db_session.expire(item)
    return item


def _row(db_session, item_id):
    """The stored row, read without the tenant filter."""
    from sqlalchemy import text

    row = db_session.execute(
        text(
            "SELECT status, assigned_to_id, reviewed_by_id, review_notes, "
            "review_decision, rejection_reason, organization_id "
            "FROM review_queue_items WHERE id = :id"
        ),
        {"id": item_id},
    ).mappings().one()
    return dict(row)


def _decision_count(db_session, item_id):
    from sqlalchemy import text

    return db_session.execute(
        text("SELECT count(*) FROM review_decisions WHERE review_item_id = :id"),
        {"id": item_id},
    ).scalar()


def _missing_id(db_session):
    from sqlalchemy import text

    return db_session.execute(
        text("SELECT COALESCE(MAX(id), 0) + 1000000 FROM review_queue_items")
    ).scalar()


@pytest.fixture
def world(db_session, make_org):
    """Organisation A and B with two items each, and organisation C with none."""
    from app.models.confidence_review import ReviewStatus

    org_a, org_b, org_c = make_org("review-a"), make_org("review-b"), make_org("review-c")
    user_a, user_b, user_c = (_make_user(db_session, o) for o in (org_a, org_b, org_c))
    a_items = [_add_item(db_session, org_a) for _ in range(2)]
    b_items = [_add_item(db_session, org_b) for _ in range(2)]
    # Give each organisation a settled item too, so counts span several statuses.
    a_done = _add_item(db_session, org_a, status=ReviewStatus.APPROVED, quality_score=0.8)
    b_done = _add_item(db_session, org_b, status=ReviewStatus.REJECTED)
    return {
        "orgs": (org_a, org_b, org_c),
        "users": (user_a, user_b, user_c),
        "a": a_items + [a_done],
        "b": b_items + [b_done],
        "missing": _missing_id(db_session),
    }


def _call(client, login_as, user, method, url, body=None):
    login_as(client, user)
    response = getattr(client, method)(url, json=body) if body is not None else getattr(client, method)(url)
    return response.status_code, response.get_json()


# --------------------------------------------------------------------------- reads


def test_detail_of_another_organisations_item_answers_as_an_unknown_id(
    client, login_as, world
):
    user_a, user_b, _user_c = world["users"]
    own, foreign = world["a"][0], world["b"][0]

    status_b, body_b = _call(client, login_as, user_a, "get", f"/api/confidence/queue/{foreign.id}")
    status_m, body_m = _call(client, login_as, user_a, "get", f"/api/confidence/queue/{world['missing']}")
    assert (status_b, body_b) == (status_m, body_m) == (404, NOT_FOUND)

    status, body = _call(client, login_as, user_a, "get", f"/api/confidence/queue/{own.id}")
    assert status == 200 and body["review_item"]["id"] == own.id
    assert body["review_item"]["item_name"] == own.item_name

    # The owner still reads it.
    status, body = _call(client, login_as, user_b, "get", f"/api/confidence/queue/{foreign.id}")
    assert status == 200 and body["review_item"]["item_name"] == foreign.item_name


def test_decisions_of_another_organisations_item_answer_as_an_unknown_id(
    db_session, client, login_as, world
):
    from app.models.confidence_review import ReviewDecision

    user_a, user_b, _user_c = world["users"]
    own, foreign = world["a"][0], world["b"][0]
    for item, reviewer in ((own, user_a), (foreign, user_b)):
        db_session.add(
            ReviewDecision(
                review_item_id=item.id,
                decision_type="approve",
                decision_reason=f"note {uuid.uuid4().hex[:8]}",
                reviewer_id=reviewer.id,
            )
        )
    db_session.flush()

    status_b, body_b = _call(client, login_as, user_a, "get", f"/api/confidence/queue/{foreign.id}/decisions")
    status_m, body_m = _call(client, login_as, user_a, "get", f"/api/confidence/queue/{world['missing']}/decisions")
    assert status_b == status_m == 404
    assert body_b == body_m

    status, body = _call(client, login_as, user_a, "get", f"/api/confidence/queue/{own.id}/decisions")
    assert status == 200 and body["total_decisions"] == 1
    assert body["decisions"][0]["reviewer_id"] == user_a.id

    status, body = _call(client, login_as, user_b, "get", f"/api/confidence/queue/{foreign.id}/decisions")
    assert status == 200 and body["total_decisions"] == 1


def test_queue_listing_returns_only_the_callers_items(client, login_as, world):
    user_a, user_b, user_c = world["users"]
    a_ids, b_ids = {i.id for i in world["a"]}, {i.id for i in world["b"]}

    _, body = _call(client, login_as, user_a, "get", "/api/confidence/queue?limit=100")
    listed = {item["id"] for item in body["items"]}
    assert listed == a_ids
    assert body["total_items"] == len(a_ids)

    _, body = _call(client, login_as, user_b, "get", "/api/confidence/queue?limit=100")
    assert {item["id"] for item in body["items"]} == b_ids

    # An organisation with no items sees none, with or without filters.
    for url in (
        "/api/confidence/queue?limit=100",
        "/api/confidence/queue?status=pending",
        "/api/confidence/queue?item_type=capability_mapping",
    ):
        _, body = _call(client, login_as, user_c, "get", url)
        assert body["items"] == [] and body["total_items"] == 0, url


def test_assigned_listing_returns_only_the_callers_items(client, login_as, db_session, world):
    """The user-scoped listing also stops at the organisation boundary."""
    org_a, org_b, _org_c = world["orgs"]
    user_a, _user_b, _user_c = world["users"]
    own = _add_item(db_session, org_a, assigned_to=user_a)
    # An item of another organisation that names this user as its reviewer.
    foreign = _add_item(db_session, org_b, assigned_to=user_a)

    status, body = _call(client, login_as, user_a, "get", "/api/review-queue")
    assert status == 200
    listed = {item["id"] for item in body["items"]}
    assert own.id in listed
    assert foreign.id not in listed
    assert body["total_items"] == len(body["items"])


def test_pending_listing_returns_nothing_for_an_organisation_without_items(
    client, login_as, world
):
    _user_a, _user_b, user_c = world["users"]

    status, body = _call(client, login_as, user_c, "get", "/reviews/api/pending")
    assert status == 200
    assert body == {"success": True, "pending_count": 0, "items": []}


def test_pending_reviews_returns_only_the_callers_pending_items(tenant_ctx, world):
    """The default pending listing (no user filter) stops at the organisation boundary."""
    from app.services.confidence_review_service import ConfidenceReviewService

    org_a, org_b, org_c = world["orgs"]
    pending_a = {i.id for i in world["a"][:2]}
    pending_b = {i.id for i in world["b"][:2]}
    service = ConfidenceReviewService()

    with tenant_ctx(org_a.id):
        assert {item.id for item in service.get_pending_reviews()} == pending_a
    with tenant_ctx(org_b.id):
        assert {item.id for item in service.get_pending_reviews()} == pending_b
    with tenant_ctx(org_c.id):
        assert service.get_pending_reviews() == []


@pytest.mark.parametrize(
    "url, extract",
    [
        ("/api/confidence/statistics", lambda body: body["statistics"]),
        ("/api/review-queue/statistics", lambda body: body["statistics"]),
    ],
)
def test_statistics_count_only_the_callers_items(client, login_as, world, url, extract):
    user_a, user_b, user_c = world["users"]

    stats = extract(_call(client, login_as, user_a, "get", url)[1])
    assert stats["total_items"] == len(world["a"]) == 3
    assert stats["pending_items"] == 2
    assert stats["approved_items"] == 1
    assert stats["rejected_items"] == 0
    assert stats["approval_rate"] == 100.0

    stats = extract(_call(client, login_as, user_b, "get", url)[1])
    assert stats["total_items"] == len(world["b"]) == 3
    assert stats["approved_items"] == 0
    assert stats["rejected_items"] == 1

    stats = extract(_call(client, login_as, user_c, "get", url)[1])
    assert stats["total_items"] == 0 and stats["pending_items"] == 0
    assert stats["average_confidence_score"] == 0.0


def test_queue_listing_response_carries_the_callers_statistics(client, login_as, world):
    user_a, _user_b, user_c = world["users"]

    _, body = _call(client, login_as, user_a, "get", "/api/review-queue")
    assert body["statistics"]["total_items"] == len(world["a"])

    _, body = _call(client, login_as, user_c, "get", "/api/review-queue")
    assert body["items"] == []
    assert body["statistics"]["total_items"] == 0


# -------------------------------------------------------------------------- writes

DECISION = {
    "decision_type": "approve",
    "decision_reason": "Reviewed",
    "reviewer_role": "architect",
}


def _processed_assign(stored, answer, user):
    return answer[1]["success"] is True and stored["assigned_to_id"] == user.id


def _processed_decision(stored, answer, user):
    # The request reached the item: it was not answered as an unknown id.
    return answer[1] != NOT_FOUND


def _processed_take(stored, answer, user):
    # Approve and reject take a pending item into review under the caller.
    return answer[1] != NOT_FOUND and stored["assigned_to_id"] == user.id


# name -> (url, body factory, status the item starts in, check that the request was processed)
WRITE_PATHS = {
    "assign": (
        "/api/confidence/queue/{id}/assign",
        lambda user: {"reviewer_id": user.id},
        "PENDING",
        _processed_assign,
    ),
    "submit_decision": (
        "/api/confidence/queue/{id}/review",
        lambda user: {**DECISION, "reviewer_id": user.id},
        "IN_REVIEW",
        _processed_decision,
    ),
    "approve": ("/api/review-queue/{id}/approve", lambda user: {}, "PENDING", _processed_take),
    "reject": ("/api/review-queue/{id}/reject", lambda user: {}, "PENDING", _processed_take),
}


@pytest.mark.parametrize("path", sorted(WRITE_PATHS))
def test_write_to_another_organisations_item_answers_as_an_unknown_id(
    db_session, client, login_as, make_org, path
):
    from app.models.confidence_review import ReviewStatus

    url, body_for, status_name, processed = WRITE_PATHS[path]
    status = getattr(ReviewStatus, status_name)
    org_a, org_b = make_org("write-a"), make_org("write-b")
    user_a, user_b = _make_user(db_session, org_a), _make_user(db_session, org_b)
    own = _add_item(db_session, org_a, status=status)
    foreign = _add_item(db_session, org_b, status=status)
    missing = _missing_id(db_session)
    before = _row(db_session, foreign.id)

    # Another organisation's id answers as an unknown id, and changes nothing.
    answer_foreign = _call(client, login_as, user_a, "post", url.format(id=foreign.id), body_for(user_a))
    answer_missing = _call(client, login_as, user_a, "post", url.format(id=missing), body_for(user_a))
    assert answer_foreign == answer_missing
    assert answer_foreign[1] == NOT_FOUND
    assert _row(db_session, foreign.id) == before
    assert _decision_count(db_session, foreign.id) == 0

    # The caller's own item is processed.
    answer_own = _call(client, login_as, user_a, "post", url.format(id=own.id), body_for(user_a))
    assert processed(_row(db_session, own.id), answer_own, user_a), answer_own

    # The owning organisation can still act on its item after the attempt.
    answer_owner = _call(client, login_as, user_b, "post", url.format(id=foreign.id), body_for(user_b))
    assert processed(_row(db_session, foreign.id), answer_owner, user_b), answer_owner


@pytest.mark.parametrize("url", ["/api/review-queue/bulk-approve", "/api/review-queue/bulk-reject"])
def test_bulk_decision_acts_only_on_the_callers_items(
    db_session, client, login_as, make_org, url
):
    org_a, org_b = make_org("bulk-a"), make_org("bulk-b")
    user_a, _user_b = _make_user(db_session, org_a), _make_user(db_session, org_b)
    a_items = [_add_item(db_session, org_a) for _ in range(2)]
    b_items = [_add_item(db_session, org_b) for _ in range(2)]
    missing = _missing_id(db_session)
    before = {item.id: _row(db_session, item.id) for item in b_items}

    ids = [a_items[0].id, b_items[0].id, a_items[1].id, b_items[1].id, missing]
    status_code, body = _call(client, login_as, user_a, "post", url, {"item_ids": ids})

    assert status_code == 200
    results = body["results"]
    assert len(results) == len(ids)
    # Another organisation's ids read as an unknown id, like the id that is not there.
    assert results[1] == results[3] == results[4] == NOT_FOUND
    # The caller's own ids were processed.
    assert results[0] != NOT_FOUND and results[2] != NOT_FOUND
    assert body["successful_count"] + body["failed_count"] == len(ids)
    for item in b_items:
        assert item.item_name not in json.dumps(body)

    for item in a_items:
        assert _row(db_session, item.id)["assigned_to_id"] == user_a.id
    for item in b_items:
        assert _row(db_session, item.id) == before[item.id]
        assert _decision_count(db_session, item.id) == 0


def _decision_data(item, reviewer):
    from decimal import Decimal

    from app.services.confidence_review_service import ReviewDecisionData

    return ReviewDecisionData(
        review_item_id=item.id,
        decision_type="approve",
        decision_reason="Reviewed",
        reviewer_id=reviewer.id,
        reviewer_role="architect",
        reviewer_experience_level="senior",
        quality_assessment={},
        identified_issues=[],
        suggested_improvements=[],
        human_confidence_estimate=Decimal("0.9"),
        ai_accuracy_assessment=4,
        correction_made=False,
        corrected_data={},
        review_duration_seconds=30,
    )


def test_service_records_a_decision_on_the_callers_item_and_not_on_another_organisations(
    db_session, tenant_ctx, make_org
):
    from app.models.confidence_review import ReviewStatus
    from app.services.confidence_review_service import ConfidenceReviewService

    org_a, org_b = make_org("svc-a"), make_org("svc-b")
    user_a = _make_user(db_session, org_a)
    own = _add_item(db_session, org_a, status=ReviewStatus.IN_REVIEW)
    foreign = _add_item(db_session, org_b, status=ReviewStatus.IN_REVIEW)
    before = _row(db_session, foreign.id)
    service = ConfidenceReviewService()

    with tenant_ctx(org_a.id):
        refused = service.submit_review_decision(_decision_data(foreign, user_a))
        recorded = service.submit_review_decision(_decision_data(own, user_a))

    assert refused == NOT_FOUND
    assert _row(db_session, foreign.id) == before
    assert _decision_count(db_session, foreign.id) == 0

    assert recorded["success"] is True and recorded["status"] == "approved"
    stored = _row(db_session, own.id)
    assert stored["status"] == "APPROVED"
    assert stored["reviewed_by_id"] == user_a.id
    assert stored["review_decision"] == "approve"
    assert _decision_count(db_session, own.id) == 1


def test_an_item_already_loaded_in_the_session_is_still_not_found_for_another_organisation(
    db_session, tenant_ctx, make_org
):
    """A row already held in the session is still looked up under the caller's scope."""
    from app.models.confidence_review import ReviewQueueItem
    from app.services.confidence_review_service import ConfidenceReviewService

    org_a, org_b = make_org("held-a"), make_org("held-b")
    user_a = _make_user(db_session, org_a)
    foreign = _add_item(db_session, org_b)
    before = _row(db_session, foreign.id)
    service = ConfidenceReviewService()

    with tenant_ctx(org_b.id):
        held = ReviewQueueItem.query.filter_by(id=foreign.id).one()
        assert held.item_name == foreign.item_name

    with tenant_ctx(org_a.id):
        assert service.assign_review_item(foreign.id, user_a.id) == NOT_FOUND
        assert service.approve_item(foreign.id, user_a.id) == NOT_FOUND
        assert service.reject_item(foreign.id, user_a.id) == NOT_FOUND

    assert _row(db_session, foreign.id) == before


# ------------------------------------------------------------------ creating items


def _queue_item(**overrides):
    from datetime import datetime

    from app.services.confidence_review_service import ReviewQueueItemData

    values = {
        "item_type": "capability_mapping",
        "item_id": 0,
        "item_name": f"Queued {uuid.uuid4().hex[:8]}",
        "item_data": {"note": "queued"},
        "confidence_score": 0.5,
        "confidence_factors": {},
        "ai_model_used": "test-model",
        "generation_timestamp": datetime.utcnow(),
        "threshold_name": "test",
    }
    values.update(overrides)
    return ReviewQueueItemData(**values)


def _queue(item_data):
    from app.services.confidence_review_service import ConfidenceReviewService

    evaluation = {
        "success": True,
        "action": {"action": "queue_for_review", "priority": 5, "estimated_review_time": 24},
    }
    result = ConfidenceReviewService().add_to_review_queue(item_data, evaluation)
    assert result["success"], result
    return result["review_item_id"]


def _global_threshold(db_session):
    """An active global threshold, which evaluation falls back to."""
    from app.models.confidence_review import ConfidenceThreshold

    threshold = ConfidenceThreshold(
        threshold_name=f"Global {uuid.uuid4().hex[:8]}",
        threshold_type="global",
        minimum_confidence=0.6,
        auto_approval_threshold=0.8,
        rejection_threshold=0.3,
        is_active=True,
    )
    db_session.add(threshold)
    db_session.flush()
    return threshold


def _application(db_session, org):
    from app.models.application_portfolio import ApplicationComponent

    application = ApplicationComponent(
        name=f"App {uuid.uuid4().hex[:8]}", organization_id=org.id
    )
    db_session.add(application)
    db_session.flush()
    return application


def test_item_queued_by_a_request_carries_the_callers_organisation(
    db_session, client, login_as, make_org
):
    org_a, org_b = make_org("create-a"), make_org("create-b")
    user_a, user_b = _make_user(db_session, org_a), _make_user(db_session, org_b)
    application = _application(db_session, org_a)
    _global_threshold(db_session)
    name = f"Created {uuid.uuid4().hex[:8]}"

    status_code, body = _call(
        client,
        login_as,
        user_a,
        "post",
        "/api/confidence/evaluate",
        {
            "item_type": "capability_mapping",
            "item_id": application.id,
            "item_name": name,
            "confidence_score": 0.5,
        },
    )
    assert status_code == 200 and body["requires_review"] is True, body
    item_id = body["queue_result"]["review_item_id"]
    assert _row(db_session, item_id)["organization_id"] == org_a.id

    # It is listed for its organisation and for nobody else.
    _, listing = _call(client, login_as, user_a, "get", "/api/confidence/queue?limit=100")
    assert item_id in {item["id"] for item in listing["items"]}
    _, listing = _call(client, login_as, user_b, "get", "/api/confidence/queue?limit=100")
    assert item_id not in {item["id"] for item in listing["items"]}


def test_item_queued_in_a_request_names_the_callers_organisation_not_the_applications(
    db_session, tenant_ctx, make_org
):
    org_a, org_b = make_org("owner-a"), make_org("owner-b")
    application_of_b = _application(db_session, org_b)

    with tenant_ctx(org_a.id):
        item_id = _queue(_queue_item(item_id=application_of_b.id))

    assert _row(db_session, item_id)["organization_id"] == org_a.id


def test_item_queued_outside_a_request_takes_the_reviewed_applications_organisation(
    db_session, make_org
):
    org = make_org("job")
    application = _application(db_session, org)

    item_id = _queue(_queue_item(item_id=application.id))

    assert _row(db_session, item_id)["organization_id"] == org.id


def test_item_with_no_known_organisation_is_listed_for_nobody(
    db_session, client, login_as, make_org
):
    from sqlalchemy import text

    org_a, org_b = make_org("none-a"), make_org("none-b")
    user_a, user_b = _make_user(db_session, org_a), _make_user(db_session, org_b)
    # An item type whose item_id does not identify an application, queued with no
    # request: nothing says which organisation owns it.
    item_id = _queue(_queue_item(item_type="archimate_element", item_id=7))
    db_session.execute(
        text("UPDATE review_queue_items SET organization_id = NULL WHERE id = :id"),
        {"id": item_id},
    )
    assert _row(db_session, item_id)["organization_id"] is None

    for user in (user_a, user_b):
        status_code, body = _call(client, login_as, user, "get", f"/api/confidence/queue/{item_id}")
        assert (status_code, body) == (404, NOT_FOUND)
        _, listing = _call(client, login_as, user, "get", "/api/confidence/queue?limit=100")
        assert item_id not in {item["id"] for item in listing["items"]}
        _, stats = _call(client, login_as, user, "get", "/api/confidence/statistics")
        assert stats["statistics"]["total_items"] == 0
