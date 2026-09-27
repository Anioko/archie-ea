from __future__ import annotations

import uuid

import pytest
from flask import g
from flask_login import login_user

from app.models.architecture_review_board import ARBReviewItem
from app.models.solution_models import Solution
from app.models.user import User
from app.modules.transformation_room.domain import (
    BlockedByEvidence,
    CommandConflict,
    CommandResult,
    KnownPreCommitTransient,
    NotAuthorised,
    NotFound,
)


def _actor(session, org):
    actor = User(
        email=f"typed-route-{uuid.uuid4().hex[:8]}@example.test",
        first_name="Typed",
        last_name="Submitter",
        organization_id=org.id,
        enterprise_role="solution_architect",
        is_org_admin=True,
    )
    session.add(actor)
    session.flush()
    return actor


def _solution(session, org, actor):
    solution = Solution(
        name=f"Typed route {uuid.uuid4().hex[:8]}",
        organization_id=org.id,
        created_by_id=actor.id,
        governance_status="draft",
    )
    session.add(solution)
    session.flush()
    return solution


def _command_result(*, idempotent=False):
    return CommandResult(
        created=not idempotent,
        idempotent=idempotent,
        operation_result_id=97,
        object_ids={
            "review_cycle_id": 41,
            "review_item_id": 42,
            "evidence_id": 43,
        },
        response={
            "review_cycle_id": 41,
            "review_item_id": 42,
            "evidence_id": 43,
            "review_number": "REV-2026-TYPED",
            "canonical_url": "/solutions/9?tab=governance",
        },
    )


def test_http_adapter_uses_authenticated_tenant_and_discards_forged_state(
    app, db_session, make_org, monkeypatch
):
    from app.modules.transformation_room.arb_submission_adapter import (
        TypedARBSubmissionAdapter,
    )

    org = make_org("typed-http-adapter")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    calls = []

    def submit(**kwargs):
        calls.append(kwargs)
        return _command_result()

    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionService.submit_legacy_solution",
        submit,
    )
    payload = {
        "actor_id": actor.id + 500,
        "organization_id": org.id + 500,
        "role": "platform_admin",
        "workspace_id": 999,
        "solution_id": solution.id + 500,
        "readiness": {"ready": True},
        "validation_result": {"passed": True},
        "cost_source": "manual_override",
        "direct_route_evidence": {"design_reviewed": {"passed": True}},
        "decided_by_id": actor.id + 500,
        "human_reviewed": True,
    }
    with app.test_request_context(
        "/submit",
        method="POST",
        json=payload,
        headers={"Idempotency-Key": "browser-action-12345", "X-Request-ID": "req-9"},
    ):
        g.current_org_id = org.id
        login_user(actor)
        result = TypedARBSubmissionAdapter.submit_solution_from_request(
            solution_id=solution.id,
            payload=payload,
        )

    assert calls == [
        {
            "actor": calls[0]["actor"],
            "command_key": "browser-action-12345",
            "solution_id": solution.id,
            "workspace_id": None,
            "assertions": {"human_reviewed": True},
        }
    ]
    assert calls[0]["actor"].user_id == actor.id
    assert calls[0]["actor"].organization_id == org.id
    assert calls[0]["actor"].roles == frozenset(
        {"solution_architect", "organization_admin"}
    )
    assert calls[0]["actor"].request_id == "req-9"
    assert result.success is True
    assert result.review_cycle_id == 41
    assert result.review_item_id == 42
    assert result.snapshot_id == 43
    assert result.canonical_url == "/solutions/9?tab=governance"


def test_generated_command_key_is_stable_for_the_same_open_submission_action(
    app, db_session, make_org, monkeypatch
):
    from app.modules.transformation_room.arb_submission_adapter import (
        TypedARBSubmissionAdapter,
    )

    org = make_org("typed-generated-key")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    command_keys = []

    def submit(**kwargs):
        command_keys.append(kwargs["command_key"])
        return _command_result(idempotent=len(command_keys) > 1)

    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionService.submit_legacy_solution",
        submit,
    )
    for _ in range(2):
        with app.test_request_context("/submit", method="POST", json={}):
            g.current_org_id = org.id
            login_user(actor)
            result = TypedARBSubmissionAdapter.submit_solution_from_request(
                solution_id=solution.id,
                payload={},
            )

    assert len(command_keys) == 2
    assert command_keys[0] == command_keys[1]
    assert command_keys[0].startswith("arb-solution-")
    assert result.idempotent is True


def test_http_adapter_rejects_malformed_idempotency_key_before_submission(
    app, db_session, make_org, monkeypatch
):
    from app.modules.transformation_room.arb_submission_adapter import (
        TypedARBSubmissionAdapter,
    )

    org = make_org("typed-invalid-key")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    called = False

    def submit(**_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionService.submit_legacy_solution",
        submit,
    )
    with app.test_request_context(
        "/submit", method="POST", headers={"Idempotency-Key": "bad key"}
    ):
        g.current_org_id = org.id
        login_user(actor)
        result = TypedARBSubmissionAdapter.submit_solution_from_request(
            solution_id=solution.id,
            payload={},
        )

    assert called is False
    assert result.success is False
    assert result.reason_codes == ["invalid_idempotency_key"]
    assert result.http_status == 400


@pytest.mark.parametrize(
    ("error", "reason_codes", "http_status"),
    [
        (NotFound("arb_subject_not_found"), ["solution_not_found"], 404),
        (NotAuthorised("arb_submission_not_authorised"), ["actor_not_authorized"], 403),
        (
            BlockedByEvidence(
                "arb_subject_not_ready",
                reason_codes=["human_review_required"],
                missing_evidence=[{"code": "human_review_required"}],
            ),
            ["human_review_required"],
            422,
        ),
        (
            BlockedByEvidence(
                "arb_subject_not_ready",
                reason_codes=["evaluator_unavailable"],
                missing_evidence=[{"code": "evaluator_unavailable"}],
            ),
            ["evaluator_unavailable"],
            503,
        ),
        (CommandConflict("arb_readiness_stale"), ["arb_readiness_stale"], 409),
        (CommandConflict("secret-internal-detail"), ["submission_conflict"], 409),
        (KnownPreCommitTransient("database_timeout"), ["submission_failed"], 503),
    ],
)
def test_adapter_maps_domain_errors_to_safe_legacy_results(
    app,
    db_session,
    make_org,
    monkeypatch,
    error,
    reason_codes,
    http_status,
):
    from app.modules.transformation_room.arb_submission_adapter import (
        TypedARBSubmissionAdapter,
    )

    org = make_org(f"typed-error-{http_status}")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)

    def submit(**_kwargs):
        raise error

    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionService.submit_legacy_solution",
        submit,
    )
    before = db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count()
    with app.test_request_context("/submit", method="POST"):
        g.current_org_id = org.id
        login_user(actor)
        result = TypedARBSubmissionAdapter.submit_solution_from_request(
            solution_id=solution.id,
            payload={},
        )

    assert result.success is False
    assert result.reason_codes == reason_codes
    assert result.http_status == http_status
    assert db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count() == before


def test_http_adapter_returns_not_found_for_cross_tenant_solution_without_writing(
    app, db_session, make_org
):
    from app.modules.transformation_room.arb_submission_adapter import (
        TypedARBSubmissionAdapter,
    )

    actor_org = make_org("typed-request-org")
    other_org = make_org("typed-foreign-org")
    actor = _actor(db_session, actor_org)
    other_actor = _actor(db_session, other_org)
    solution = _solution(db_session, other_org, other_actor)

    with app.test_request_context("/submit", method="POST"):
        g.current_org_id = actor_org.id
        login_user(actor)
        result = TypedARBSubmissionAdapter.submit_solution_from_request(
            solution_id=solution.id,
            payload={"human_reviewed": True},
        )

    assert result.success is False
    assert result.reason_codes == ["solution_not_found"]
    assert result.http_status == 404
    assert db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count() == 0
