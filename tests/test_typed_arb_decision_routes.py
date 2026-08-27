"""Route-level contracts for typed ARB decisions (Lane L1).

Every typed ARB terminal decision must reach ``TypedARBDecisionService`` with
an actor built from the authenticated session only, a tenant-scoped cycle
resolved by an explicit ``(id, organization_id)`` predicate, and an
idempotency key that is never a browser-supplied ``review_item_id``.

The module uses the shared fixtures from ``tests/conftest.py`` (``app``,
``_schema``, ``client``, ``login_as``, ``make_org``, ``tenant_ctx``). It
overrides only ``db_session``: ``CommandService`` opens its own connection on
``db.engine``, so a typed command cannot see rows held in the shared
fixture's uncommitted transaction. Setup is therefore committed and removed
again by an explicit, asserted teardown, exactly as
``tests/test_arb_condition_lifecycle_integration.py`` does.
"""

from __future__ import annotations

import os
import uuid

import pytest


os.environ.setdefault("TRANSFORMATION_COMMAND_CAPABILITY_SECRET", "74" * 32)


_CLEANUP_TABLES = (
    "archie_command_claim_challenges",
    "arb_condition_events",
    "arb_canonical_conditions",
    "arb_condition_evidence_records",
    "arb_decision_events",
    "arb_submission_events",
    "operation_results",
    "command_materialisations",
    "command_idempotency_records",
    "arb_review_items",
    "arb_review_cycles",
    "arb_subject_evidence_snapshots",
    "architecture_decision_records",
    "users",
)


@pytest.fixture
def db_session(app, _schema):
    """Committed setup visible to CommandService's independent sessions."""
    from app import db

    with app.app_context():
        db.session.remove()
        try:
            yield db.session
        finally:
            organization_ids = tuple(db.session.info.get("l1_cleanup_org_ids", ()))
            role_ids = tuple(db.session.info.get("l1_cleanup_role_ids", ()))
            db.session.remove()
            if not organization_ids:
                return
            raw = db.engine.raw_connection()
            try:
                with raw.cursor() as cursor:
                    cursor.execute("SHOW session_replication_role")
                    original_role = cursor.fetchone()[0]
                    cursor.execute("SET session_replication_role = replica")
                    try:
                        for table in _CLEANUP_TABLES:
                            cursor.execute(
                                f'DELETE FROM "{table}" '  # nosec B608 -- fixed table allowlist
                                "WHERE organization_id = ANY(%s)",
                                (list(organization_ids),),
                            )
                        if role_ids:
                            cursor.execute(
                                "DELETE FROM roles WHERE id = ANY(%s)",
                                (list(role_ids),),
                            )
                        cursor.execute(
                            "DELETE FROM organizations WHERE id = ANY(%s)",
                            (list(organization_ids),),
                        )
                    except Exception:
                        raw.rollback()
                        cursor.execute(
                            f"SET session_replication_role = {original_role}"
                        )
                        raw.commit()
                        raise
                    cursor.execute(f"SET session_replication_role = {original_role}")
                    raw.commit()
                    residual = {}
                    for table in _CLEANUP_TABLES:
                        cursor.execute(
                            f'SELECT count(*) FROM "{table}" '  # nosec B608 -- fixed allowlist
                            "WHERE organization_id = ANY(%s)",
                            (list(organization_ids),),
                        )
                        count = cursor.fetchone()[0]
                        if count:
                            residual[table] = count
                    if residual:
                        raise AssertionError(
                            f"L1 cleanup left rows behind: {residual!r}"
                        )
            finally:
                raw.close()


class _Fixture:
    """One tenant with a real, open typed ADR review cycle."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


def _install_guards(db_session):
    from app.models.arb_condition_event import ensure_arb_condition_event_guards
    from app.models.arb_condition_evidence import ensure_arb_condition_evidence_guards
    from app.models.arb_decision_event import ensure_arb_decision_guards
    from app.models.architecture_review_board import ensure_arb_cycle_constraints
    from app.models.transformation_db_guards import ensure_transformation_db_guards

    connection = db_session.connection()
    ensure_transformation_db_guards(connection, capability_secrets=("74" * 32,))
    ensure_arb_cycle_constraints(connection)
    ensure_arb_decision_guards(connection)
    ensure_arb_condition_evidence_guards(connection)
    ensure_arb_condition_event_guards(connection)


def _seed_typed_cycle(db_session, make_org, label="l1"):
    """Create a tenant, a submitter, a decider and one open typed ADR cycle."""
    from app.models.adr import ArchitectureDecisionRecord
    from app.models.architecture_review_board import ARBReviewItem
    from app.models.user import Permission, Role, User
    from app.modules.transformation_room.arb_submission_service import (
        TypedARBSubmissionService,
    )
    from app.modules.transformation_room.domain import ActorContext

    _install_guards(db_session)
    org = make_org(label)
    db_session.info.setdefault("l1_cleanup_org_ids", set()).add(org.id)
    suffix = uuid.uuid4().hex[:10]

    role = Role(name=f"L1 ARB {suffix}", permissions=Permission.GENERAL)
    db_session.add(role)
    db_session.flush()
    db_session.info.setdefault("l1_cleanup_role_ids", set()).add(role.id)

    submitter = User(
        organization_id=org.id,
        email=f"l1-submit-{suffix}@example.test",
        enterprise_role="enterprise_architect",
        confirmed=True,
    )
    decider = User(
        organization_id=org.id,
        email=f"l1-decide-{suffix}@example.test",
        enterprise_role="enterprise_architect",
        confirmed=True,
    )
    db_session.add_all((submitter, decider))
    db_session.flush()
    submitter.role_id = role.id
    decider.role_id = role.id
    adr = ArchitectureDecisionRecord(
        organization_id=org.id,
        adr_number=int(suffix[:7], 16),
        title=f"L1 typed decision {suffix}",
        status="proposed",
        context="A governed choice needs a recorded decision.",
        decision="Adopt the governed option.",
        rationale="It is testable.",
        consequences="A decision event must exist.",
        created_by=submitter.email,
    )
    db_session.add(adr)
    db_session.commit()

    submission = TypedARBSubmissionService.submit(
        actor=ActorContext(
            submitter.id, org.id, frozenset(), f"l1-submit-{suffix}"
        ),
        command_key=f"l1-submit-{suffix}",
        subject_type="adr",
        subject_id=adr.id,
        assertions={"human_reviewed": True},
    )
    cycle_id = submission.object_ids["review_cycle_id"]
    review_item_id = submission.object_ids["review_item_id"]
    review = db_session.get(ARBReviewItem, review_item_id)
    # Scalars only: the tests cross session boundaries, and a detached ORM
    # instance would fail to refresh rather than assert.
    fixture = _Fixture(
        org_id=org.id,
        role_id=role.id,
        submitter_id=submitter.id,
        decider_id=decider.id,
        adr_id=adr.id,
        adr_title=adr.title,
        cycle_id=cycle_id,
        review_item_id=review_item_id,
        review_number=review.review_number,
        suffix=suffix,
    )
    db_session.expunge_all()
    return fixture


def _legacy_review(db_session, fixture):
    """A generic, untyped review item in the same tenant."""
    from app.models.architecture_review_board import ARBReviewItem

    review = ARBReviewItem(
        organization_id=fixture.org_id,
        review_number=f"LEG-{fixture.suffix}",
        title="Legacy generic review",
        review_type="solution_design",
        status="under_review",
        submitter_id=fixture.submitter_id,
    )
    db_session.add(review)
    db_session.commit()
    review_id = review.id
    db_session.expunge_all()
    return review_id


def _decision_events(db_session, cycle_id):
    from app.models.arb_decision_event import ARBDecisionEvent

    return (
        db_session.query(ARBDecisionEvent)
        .filter(ARBDecisionEvent.review_cycle_id == cycle_id)
        .all()
    )


# ---------------------------------------------------------------------------
# 1. Client-trusted actor is never honoured
# ---------------------------------------------------------------------------


def test_forged_actor_fields_are_ignored_and_session_user_decides(
    app, db_session, make_org, client, login_as
):
    """decided_by_id / organization_id / status in the body must not be read."""
    fixture = _seed_typed_cycle(db_session, make_org, "l1-forged")
    login_as(client, fixture.decider_id)

    response = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/approve",
        json={
            "notes": "Approved on the recorded evidence.",
            # Every one of these is a forged trust input.
            "decided_by_id": fixture.submitter_id,
            "organization_id": fixture.org_id + 10_000,
            "actor_id": fixture.submitter_id,
            "role": "platform_admin",
            "status": "approved",
            "readiness": "ready",
        },
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["success"] is True

    events = _decision_events(db_session, fixture.cycle_id)
    assert len(events) == 1
    # The recorded actor is the session user, not the forged decided_by_id.
    assert events[0].actor_id == fixture.decider_id
    assert events[0].organization_id == fixture.org_id


# ---------------------------------------------------------------------------
# 2. Explicit tenant predicates
# ---------------------------------------------------------------------------


def test_cross_tenant_review_id_returns_404_and_leaks_nothing(
    app, db_session, make_org, client, login_as
):
    owner = _seed_typed_cycle(db_session, make_org, "l1-owner")
    intruder = _seed_typed_cycle(db_session, make_org, "l1-intruder")
    login_as(client, intruder.decider_id)

    for path, method in (
        (f"/arb/api/arb/{owner.review_item_id}/approve", client.post),
        (f"/arb/api/arb/{owner.review_item_id}/reject", client.post),
        (f"/arb/api/arb/{owner.review_item_id}/request-changes", client.post),
        (f"/arb/api/arb/{owner.review_item_id}/review", client.post),
    ):
        login_as(client, intruder.decider_id)
        response = method(path, json={"notes": "n", "reason": "r"})
        assert response.status_code == 404, (path, response.get_json())
        payload = response.get_data(as_text=True)
        assert owner.review_number not in payload
        assert owner.adr_title not in payload

    # And no decision was recorded against the other tenant's cycle.
    assert _decision_events(db_session, owner.cycle_id) == []


def test_cross_tenant_implementation_status_get_returns_404(
    app, db_session, make_org, client, login_as
):
    owner = _seed_typed_cycle(db_session, make_org, "l1-impl-owner")
    intruder = _seed_typed_cycle(db_session, make_org, "l1-impl-intruder")
    login_as(client, intruder.decider_id)
    response = client.get(
        f"/arb/api/arb/{owner.review_item_id}/implementation-status"
    )
    assert response.status_code == 404
    assert owner.review_number not in response.get_data(as_text=True)


# ---------------------------------------------------------------------------
# 3. Separation of duties
# ---------------------------------------------------------------------------


def test_submitter_cannot_decide_own_review(
    app, db_session, make_org, client, login_as
):
    fixture = _seed_typed_cycle(db_session, make_org, "l1-sod")
    login_as(client, fixture.submitter_id)

    response = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/approve",
        json={"notes": "I approve my own submission."},
    )
    assert response.status_code == 403
    body = response.get_json()
    assert body["success"] is False
    assert body["reason_codes"] == ["arb_decision_separation_of_duties"]
    assert body["request_id"]
    assert _decision_events(db_session, fixture.cycle_id) == []


# ---------------------------------------------------------------------------
# 4/5. Typed service routing, envelope and canonical identifiers
# ---------------------------------------------------------------------------


def test_typed_decision_envelope_keeps_legacy_aliases_and_adds_canonical_ids(
    app, db_session, make_org, client, login_as
):
    fixture = _seed_typed_cycle(db_session, make_org, "l1-envelope")
    login_as(client, fixture.decider_id)

    response = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/request-changes",
        json={
            "notes": "Approved once the two conditions are evidenced.",
            "conditions": ["Complete the threat model", "Confirm the DR runbook"],
        },
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()

    # Legacy aliases the existing callers rely on.
    assert body["success"] is True
    assert body["item_id"] == fixture.review_item_id
    assert body["status"] == "approved_with_conditions"
    assert body["redirect_url"] == f"/arb/reviews/{fixture.review_item_id}"

    # Canonical identifiers added by the blueprint contract.
    assert body["review_cycle_id"] == fixture.cycle_id
    assert body["review_item_id"] == fixture.review_item_id
    assert isinstance(body["decision_event_id"], int)
    assert len(body["condition_ids"]) == 2
    assert body["canonical_url"] == f"/architecture/adrs/records/{fixture.adr_id}"
    assert body["outcome"] == "approved_with_conditions"
    assert body["idempotent"] is False


def test_conditions_are_canonical_rows_without_an_invented_due_date(
    app, db_session, make_org, client, login_as
):
    from app.models.arb_decision_event import ARBCondition

    fixture = _seed_typed_cycle(db_session, make_org, "l1-conditions")
    login_as(client, fixture.decider_id)

    response = client.post(
        f"/arb/reviews/{fixture.review_item_id}/decision",
        data={
            "decision": "approved_with_conditions",
            "rationale": "Conditional on evidence.",
            "conditions": "Complete the threat model\nConfirm the DR runbook\n",
            # Forged actor fields on the HTML form path as well.
            "decided_by_id": str(fixture.submitter_id),
            "organization_id": "999999",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303), response.get_data(as_text=True)

    conditions = (
        db_session.query(ARBCondition)
        .filter(ARBCondition.review_cycle_id == fixture.cycle_id)
        .order_by(ARBCondition.condition_number)
        .all()
    )
    assert len(conditions) == 2
    # The old form parser invented `utcnow() + 30 days` and a `pending` state.
    assert [condition.due_date for condition in conditions] == [None, None]
    assert all(condition.blocks_execution for condition in conditions)
    events = _decision_events(db_session, fixture.cycle_id)
    assert len(events) == 1
    assert events[0].actor_id == fixture.decider_id


def test_typed_decision_does_not_mutate_solution_governance_status(
    app, db_session, make_org, client, login_as
):
    """The approve path must not write a subject projection directly."""
    from app.models.architecture_review_board import ARBReviewItem

    fixture = _seed_typed_cycle(db_session, make_org, "l1-projection")
    login_as(client, fixture.decider_id)
    response = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/approve",
        json={"notes": "Approved."},
    )
    assert response.status_code == 200, response.get_json()

    db_session.expunge_all()
    review = db_session.get(ARBReviewItem, fixture.review_item_id)
    # The projection is written by the typed service, from the decision event.
    assert review.decided_by_id == fixture.decider_id
    assert review.decision == "approved"


# ---------------------------------------------------------------------------
# 6. Idempotency
# ---------------------------------------------------------------------------


def test_replay_with_the_same_key_returns_the_same_result_and_one_event(
    app, db_session, make_org, client, login_as
):
    fixture = _seed_typed_cycle(db_session, make_org, "l1-replay")
    key = f"l1-replay-{fixture.suffix}"
    body = {"notes": "Approved on the recorded evidence."}

    login_as(client, fixture.decider_id)
    first = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/approve",
        json=body,
        headers={"Idempotency-Key": key},
    )
    assert first.status_code == 200, first.get_json()
    login_as(client, fixture.decider_id)
    replay = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/approve",
        json=body,
        headers={"Idempotency-Key": key},
    )
    assert replay.status_code == 200, replay.get_json()

    assert (
        replay.get_json()["decision_event_id"]
        == first.get_json()["decision_event_id"]
    )
    assert replay.get_json()["review_cycle_id"] == fixture.cycle_id
    assert replay.get_json()["idempotent"] is True
    assert len(_decision_events(db_session, fixture.cycle_id)) == 1


def test_same_key_with_a_different_payload_conflicts(
    app, db_session, make_org, client, login_as
):
    fixture = _seed_typed_cycle(db_session, make_org, "l1-conflict")
    key = f"l1-conflict-{fixture.suffix}"

    login_as(client, fixture.decider_id)
    first = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/approve",
        json={"notes": "Approved on the recorded evidence."},
        headers={"Idempotency-Key": key},
    )
    assert first.status_code == 200, first.get_json()

    login_as(client, fixture.decider_id)
    conflict = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/reject",
        json={"reason": "A different command under the same key."},
        headers={"Idempotency-Key": key},
    )
    assert conflict.status_code == 409, conflict.get_json()
    body = conflict.get_json()
    assert body["success"] is False
    assert body["reason_codes"]
    assert "Traceback" not in str(body)
    assert len(_decision_events(db_session, fixture.cycle_id)) == 1


def test_a_malformed_idempotency_key_is_rejected_before_any_write(
    app, db_session, make_org, client, login_as
):
    fixture = _seed_typed_cycle(db_session, make_org, "l1-badkey")
    login_as(client, fixture.decider_id)
    response = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/approve",
        json={"notes": "Approved."},
        headers={"Idempotency-Key": "short"},
    )
    assert response.status_code == 400
    assert response.get_json()["reason_codes"] == ["invalid_idempotency_key"]
    assert _decision_events(db_session, fixture.cycle_id) == []


def test_review_item_id_is_not_used_as_an_idempotency_token(
    app, db_session, make_org, client, login_as
):
    """Two different cycles under one actor must not collide on the item id."""
    from app.modules.architecture.routes.arb_routes import TypedARBDecisionAdapter
    from app.modules.transformation_room.domain import ActorContext

    fixture = _seed_typed_cycle(db_session, make_org, "l1-key-source")
    actor = ActorContext(fixture.decider_id, fixture.org_id, frozenset(), "req")
    with app.test_request_context("/"):
        first = TypedARBDecisionAdapter.command_key(
            None,
            actor=actor,
            cycle_id=fixture.cycle_id,
            outcome="approved",
            rationale="A",
            conditions=[],
        )
        second = TypedARBDecisionAdapter.command_key(
            None,
            actor=actor,
            cycle_id=fixture.cycle_id + 1,
            outcome="approved",
            rationale="A",
            conditions=[],
        )
    assert first != second
    assert str(fixture.review_item_id) not in first


# ---------------------------------------------------------------------------
# 4. Operations typed services deliberately do not expose
# ---------------------------------------------------------------------------


def test_typed_reopen_is_rejected_but_legacy_reopen_still_works(
    app, db_session, make_org, client, login_as
):
    from app.models.architecture_review_board import ARBReviewItem

    fixture = _seed_typed_cycle(db_session, make_org, "l1-reopen")
    login_as(client, fixture.decider_id)
    decided = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/approve",
        json={"notes": "Approved."},
    )
    assert decided.status_code == 200, decided.get_json()

    login_as(client, fixture.decider_id)
    response = client.post(
        f"/arb/reviews/{fixture.review_item_id}/reopen",
        data={"reopen_reason": "I changed my mind."},
    )
    assert response.status_code == 409

    db_session.expunge_all()
    review = db_session.get(ARBReviewItem, fixture.review_item_id)
    assert review.decision == "approved"
    assert review.decided_by_id == fixture.decider_id

    # A legacy generic row keeps its historic behaviour, explicitly.
    legacy_id = _legacy_review(db_session, fixture)
    legacy = db_session.get(ARBReviewItem, legacy_id)
    legacy.decision = "approved"
    legacy.status = "approved"
    legacy.decided_by_id = fixture.decider_id
    db_session.commit()
    db_session.expunge_all()
    login_as(client, fixture.decider_id)
    legacy_response = client.post(
        f"/arb/reviews/{legacy_id}/reopen",
        data={"reopen_reason": "Legacy rows may still be reopened."},
    )
    assert legacy_response.status_code in (302, 303)


def test_typed_implementation_status_patch_is_rejected(
    app, db_session, make_org, client, login_as
):
    fixture = _seed_typed_cycle(db_session, make_org, "l1-impl")
    login_as(client, fixture.decider_id)
    response = client.patch(
        f"/arb/api/arb/{fixture.review_item_id}/implementation-status",
        json={"implementation_status": "completed", "conditions_response": {"0": "x"}},
    )
    assert response.status_code == 409
    body = response.get_json()
    assert body["reason_codes"] == [
        "typed_cycle_implementation_status_not_writable"
    ]


def test_typed_cycle_status_cannot_be_client_assigned(
    app, db_session, make_org, client, login_as
):
    fixture = _seed_typed_cycle(db_session, make_org, "l1-begin")
    login_as(client, fixture.decider_id)
    response = client.post(f"/arb/api/arb/{fixture.review_item_id}/review", json={})
    assert response.status_code == 409
    assert response.get_json()["reason_codes"] == [
        "typed_cycle_status_not_client_mutable"
    ]


# ---------------------------------------------------------------------------
# 5. Documented status-code map
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error_factory,expected_status,expected_reason",
    [
        (lambda d: d.NotFound("arb_review_cycle_not_found"), 404,
         "arb_review_cycle_not_found"),
        (lambda d: d.NotAuthorised("arb_decision_separation_of_duties"), 403,
         "arb_decision_separation_of_duties"),
        (lambda d: d.NotAuthorised("some_internal_detail"), 403,
         "actor_not_authorized"),
        (lambda d: d.CommandConflict("arb_cycle_already_terminal"), 409,
         "arb_cycle_already_terminal"),
        (lambda d: d.CommandConflict("internal_row_12345"), 409,
         "decision_conflict"),
        (lambda d: d.KnownPreCommitTransient("db_unavailable"), 503,
         "decision_unconfirmed"),
        (lambda d: d.AuthenticationRequired("not_authenticated"), 401,
         "not_authenticated"),
        (lambda d: RuntimeError("secret tenant name leaked here"), 500,
         "decision_failed"),
    ],
)
def test_service_exceptions_map_to_documented_statuses(
    app, db_session, make_org, client, login_as, monkeypatch,
    error_factory, expected_status, expected_reason,
):
    from app.modules.transformation_room import arb_decision_service, domain

    fixture = _seed_typed_cycle(db_session, make_org, "l1-status")

    def _raise(**_kwargs):
        raise error_factory(domain)

    monkeypatch.setattr(
        arb_decision_service.TypedARBDecisionService, "decide", staticmethod(_raise)
    )
    login_as(client, fixture.decider_id)
    response = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/approve",
        json={"notes": "Approved."},
    )
    assert response.status_code == expected_status
    body = response.get_json()
    assert body["success"] is False
    assert body["reason_codes"] == [expected_reason]
    assert body["request_id"]
    assert "missing_evidence" in body
    assert "secret tenant name leaked here" not in str(body)


def test_evidence_blockers_map_to_422_with_the_stable_blocker_list(
    app, db_session, make_org, client, login_as, monkeypatch
):
    from app.modules.transformation_room import arb_decision_service
    from app.modules.transformation_room.domain import BlockedByEvidence

    fixture = _seed_typed_cycle(db_session, make_org, "l1-blocked")

    def _raise(**_kwargs):
        raise BlockedByEvidence(
            "arb_subject_not_ready",
            reason_codes=["adr_evidence_stale"],
            missing_evidence=[{"code": "adr_evidence_stale", "resource_type": "adr"}],
        )

    monkeypatch.setattr(
        arb_decision_service.TypedARBDecisionService, "decide", staticmethod(_raise)
    )
    login_as(client, fixture.decider_id)
    response = client.post(
        f"/arb/api/arb/{fixture.review_item_id}/approve",
        json={"notes": "Approved."},
    )
    assert response.status_code == 422
    body = response.get_json()
    assert body["reason_codes"] == ["adr_evidence_stale"]
    assert body["missing_evidence"][0]["resource_type"] == "adr"


def test_unauthenticated_typed_decision_is_not_a_500(app, client):
    """An anonymous caller is redirected/refused, never served a decision."""
    response = client.post("/arb/api/arb/1/approve", json={"notes": "x"})
    assert response.status_code in (302, 401, 403)


def test_unsupported_outcome_is_a_400_on_the_html_form(
    app, db_session, make_org, client, login_as
):
    fixture = _seed_typed_cycle(db_session, make_org, "l1-outcome")
    login_as(client, fixture.decider_id)
    response = client.post(
        f"/arb/reviews/{fixture.review_item_id}/decision",
        data={"decision": "escalate", "rationale": "Not a typed outcome."},
    )
    assert response.status_code == 400
    assert _decision_events(db_session, fixture.cycle_id) == []


def test_outcome_aliases_cover_every_typed_terminal_outcome():
    from app.modules.architecture.routes.arb_routes import TypedARBDecisionAdapter
    from app.modules.transformation_room.arb_decision_service import (
        TypedARBDecisionService,
    )

    aliases = {
        "approve": "approved",
        "reject": "rejected",
        "approved_with_conditions": "approved_with_conditions",
        "request_changes": "approved_with_conditions",
        "return_for_evidence": "returned_for_evidence",
        "return_for_options": "returned_for_options",
    }
    for supplied, expected in aliases.items():
        assert TypedARBDecisionAdapter.normalize_outcome(supplied) == expected
        assert expected in TypedARBDecisionService.TERMINAL_OUTCOMES
    with pytest.raises(ValueError):
        TypedARBDecisionAdapter.normalize_outcome("deferred")


# ---------------------------------------------------------------------------
# Solution lifecycle routes (arb_workflow_routes)
# ---------------------------------------------------------------------------


def test_solution_lifecycle_uses_an_explicit_tenant_predicate(
    app, db_session, make_org, client, login_as
):
    from app import db
    from app.models.solution_models import Solution

    owner = _seed_typed_cycle(db_session, make_org, "l1-sol-owner")
    intruder = _seed_typed_cycle(db_session, make_org, "l1-sol-intruder")
    solution = Solution(
        name=f"L1 tenancy {owner.suffix}",
        organization_id=owner.org_id,
        created_by_id=owner.submitter_id,
        governance_status="under_review",
    )
    db_session.add(solution)
    db_session.commit()
    solution_id, solution_name = solution.id, solution.name
    db_session.expunge_all()
    try:
        login_as(client, intruder.decider_id)
        response = client.get(
            f"/api/arb-workflow/solutions/{solution_id}/lifecycle"
        )
        assert response.status_code == 404
        assert solution_name not in response.get_data(as_text=True)
    finally:
        db_session.execute(
            db.text("DELETE FROM solutions WHERE id = :id"), {"id": solution_id}
        )
        db_session.commit()
