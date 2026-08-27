"""RED contracts for Package C2's typed ARB terminal decision engine."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    CommandResult,
    DomainMutationResult,
    NotAuthorised,
)


TERMINAL_OUTCOMES = (
    "approved",
    "approved_with_conditions",
    "rejected",
    "returned_for_evidence",
    "returned_for_options",
)


def _decision_module():
    try:
        return importlib.import_module(
            "app.modules.transformation_room.arb_decision_service"
        )
    except ModuleNotFoundError:
        pytest.fail(
            "Package C2 requires app.modules.transformation_room."
            "arb_decision_service.TypedARBDecisionService"
        )


def _actor(*, user_id=73, org_id=41, roles=frozenset({"platform_admin"})):
    return ActorContext(user_id, org_id, roles, "typed-arb-decision-contract")


def _result(*, created=True, cycle_id=501, review_id=502, event_id=503):
    ids = {
        "review_cycle_id": cycle_id,
        "review_item_id": review_id,
        "decision_event_id": event_id,
    }
    return CommandResult(
        created=created,
        idempotent=not created,
        operation_result_id=504,
        object_ids=ids,
        response={**ids, "status": "approved"},
    )


@pytest.mark.parametrize("outcome", TERMINAL_OUTCOMES)
def test_every_terminal_outcome_uses_one_exact_cycle_scoped_command(monkeypatch, outcome):
    module = _decision_module()
    captured = {}
    calls = []

    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "authorise_decision",
        classmethod(
            lambda cls, session, actor, cycle_id: calls.append(
                ("authority", actor.user_id, actor.organization_id, cycle_id)
            )
        ),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_decide_locked",
        classmethod(
            lambda cls, **kwargs: (
                calls.append(
                    (
                        "locked",
                        kwargs["cycle_id"],
                        kwargs["outcome"],
                        kwargs["rationale"],
                        kwargs["conditions"],
                    )
                ),
                DomainMutationResult(
                    object_ids={
                        "review_cycle_id": 501,
                        "review_item_id": 502,
                        "decision_event_id": 503,
                    },
                    response={"status": outcome},
                    outbox_events=(),
                ),
            )[1]
        ),
    )

    def execute(**kwargs):
        captured.update(kwargs)
        kwargs["authorizer"](
            SimpleNamespace(), kwargs["actor"], kwargs["operation"], kwargs["natural_key"]
        )
        mutation = kwargs["handler"](SimpleNamespace(), SimpleNamespace())
        assert isinstance(mutation, DomainMutationResult)
        return _result()

    monkeypatch.setattr(module.CommandService, "execute", execute)
    conditions = (
        [{"code": "SEC-1", "text": "Complete threat model"}]
        if outcome == "approved_with_conditions"
        else []
    )
    canonical_conditions = (
        [
            {
                "condition_number": "SEC-1",
                "description": "Complete threat model",
                "category": None,
                "due_date": None,
                "blocks_execution": True,
            }
        ]
        if conditions
        else []
    )

    module.TypedARBDecisionService.decide(
        actor=_actor(roles=frozenset({"viewer"})),
        command_key=f"decision-{outcome}",
        cycle_id=501,
        outcome=outcome,
        rationale="Recorded by the board",
        conditions=conditions,
    )

    assert captured["operation"] == "arb.decision.record"
    assert captured["natural_key"] == "arb-decision:41:501"
    assert captured["payload"] == {
        "cycle_id": 501,
        "outcome": outcome,
        "rationale": "Recorded by the board",
        "conditions": canonical_conditions,
    }
    assert calls == [
        ("authority", 73, 41, 501),
        ("locked", 501, outcome, "Recorded by the board", canonical_conditions),
    ]


def test_authorizer_rejects_wrong_operation_or_natural_key(monkeypatch):
    module = _decision_module()
    captured = {}
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "authorise_decision",
        classmethod(lambda cls, session, actor, cycle_id: None),
    )

    def execute(**kwargs):
        captured.update(kwargs)
        return _result()

    monkeypatch.setattr(module.CommandService, "execute", execute)
    module.TypedARBDecisionService.decide(
        actor=_actor(), command_key="decision", cycle_id=501,
        outcome="approved", rationale="Approved", conditions=[],
    )

    with pytest.raises(NotAuthorised, match="arb_decision_command_mismatch"):
        captured["authorizer"](
            SimpleNamespace(), _actor(), "arb.submit", "arb-decision:41:501"
        )
    with pytest.raises(NotAuthorised, match="arb_decision_command_mismatch"):
        captured["authorizer"](
            SimpleNamespace(), _actor(), "arb.decision.record", "arb-decision:41:999"
        )


def test_same_command_replay_returns_stable_graph_and_does_not_run_handler(monkeypatch):
    module = _decision_module()
    winner = _result()
    handler_calls = 0
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "authorise_decision",
        classmethod(lambda cls, session, actor, cycle_id: None),
    )

    def execute(**kwargs):
        nonlocal handler_calls
        # CommandService reconciles the immutable result without invoking handler.
        assert callable(kwargs["handler"])
        return winner

    monkeypatch.setattr(module.CommandService, "execute", execute)
    args = dict(
        actor=_actor(), command_key="same", cycle_id=501,
        outcome="rejected", rationale="Evidence is insufficient", conditions=[],
    )
    first = module.TypedARBDecisionService.decide(**args)
    replay = module.TypedARBDecisionService.decide(**args)

    assert first.object_ids == replay.object_ids
    assert handler_calls == 0


def test_replay_revalidates_current_server_decision_authority(monkeypatch):
    module = _decision_module()
    checks = []

    def authority(cls, session, actor, cycle_id):
        checks.append(cycle_id)
        if len(checks) == 2:
            raise NotAuthorised("arb_decision_not_authorised")

    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "authorise_decision",
        classmethod(authority),
    )

    def execute(**kwargs):
        kwargs["authorizer"](
            SimpleNamespace(), kwargs["actor"], kwargs["operation"], kwargs["natural_key"]
        )
        return _result(created=len(checks) == 1)

    monkeypatch.setattr(module.CommandService, "execute", execute)
    args = dict(
        actor=_actor(roles=frozenset({"platform_admin"})), command_key="revoked",
        cycle_id=501, outcome="approved", rationale="Approved", conditions=[],
    )
    module.TypedARBDecisionService.decide(**args)
    with pytest.raises(NotAuthorised, match="arb_decision_not_authorised"):
        module.TypedARBDecisionService.decide(**args)
    assert checks == [501, 501]


@pytest.mark.parametrize(
    ("cycle_status", "expected_reason"),
    (
        ("historical_unverified", "historical_unverified_cycle_not_decidable"),
        ("approved", "arb_cycle_already_terminal"),
        ("rejected", "arb_cycle_already_terminal"),
        ("returned_for_evidence", "arb_cycle_already_terminal"),
    ),
)
def test_locked_engine_rejects_historical_and_terminal_cycles(
    monkeypatch, cycle_status, expected_reason
):
    module = _decision_module()
    cycle = SimpleNamespace(
        id=501,
        organization_id=41,
        status=cycle_status,
        closed_at=None if cycle_status == "historical_unverified" else object(),
    )
    session = SimpleNamespace()
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_load_cycle_and_review_for_update",
        classmethod(lambda cls, session, actor, cycle_id: (cycle, SimpleNamespace(id=502))),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_lock_subject_decision",
        classmethod(lambda cls, session, actor, cycle_id: None),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_assert_cycle_review_projection_equal",
        staticmethod(lambda cycle, review: None),
    )

    with pytest.raises(CommandConflict, match=expected_reason):
        module.TypedARBDecisionService._decide_locked(
            session=session,
            actor=_actor(),
            cycle_id=501,
            outcome="approved",
            rationale="Approved",
            conditions=[],
            claim=SimpleNamespace(receipt_id=701, generation=1),
        )


def test_projection_and_event_contract_are_explicit_on_service_type():
    module = _decision_module()
    service = module.TypedARBDecisionService

    assert service.TERMINAL_OUTCOMES == frozenset(TERMINAL_OUTCOMES)
    assert service.OPEN_STATUSES == frozenset(
        {"submitted", "under_review", "pending_information", "pending_info", "pending"}
    )
    assert service.DECISION_EVENT_TYPE == "decided"
    assert callable(service._load_cycle_and_review_for_update)
    assert callable(service._assert_cycle_review_projection_equal)


def test_handler_rechecks_authority_after_locks(monkeypatch):
    module = _decision_module()
    cycle = SimpleNamespace(
        id=501, status="submitted", closed_at=None,
    )
    review = SimpleNamespace(id=502, status="submitted", decision=None)
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_lock_subject_decision",
        classmethod(lambda cls, session, actor, cycle_id: None),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_load_cycle_and_review_for_update",
        classmethod(lambda cls, session, actor, cycle_id: (cycle, review)),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_assert_cycle_review_projection_equal",
        staticmethod(lambda cycle, review: None),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "authorise_decision",
        classmethod(
            lambda cls, session, actor, cycle_id, **kwargs: (_ for _ in ()).throw(
                NotAuthorised("arb_decision_not_authorised")
            )
        ),
    )

    with pytest.raises(NotAuthorised, match="arb_decision_not_authorised"):
        module.TypedARBDecisionService._decide_locked(
            session=SimpleNamespace(), actor=_actor(), cycle_id=501,
            outcome="approved", rationale="Approved", conditions=[],
            claim=SimpleNamespace(receipt_id=701, generation=1),
        )


def test_conditions_are_canonical_and_reject_duplicates_or_bad_dates():
    module = _decision_module()
    canonical = module.TypedARBDecisionService._canonical_conditions(
        [{"code": "SEC-1", "text": "Threat model", "due_date": "2026-09-30"}]
    )
    assert canonical == [
        {
            "condition_number": "SEC-1",
            "description": "Threat model",
            "category": None,
            "due_date": "2026-09-30",
            "blocks_execution": True,
        }
    ]
    with pytest.raises(ValueError, match="unique"):
        module.TypedARBDecisionService._canonical_conditions(
            [{"code": "SEC-1", "text": "A"}, {"code": "SEC-1", "text": "B"}]
        )
    with pytest.raises(ValueError, match="ISO"):
        module.TypedARBDecisionService._canonical_conditions(
            [{"code": "SEC-1", "text": "A", "due_date": "tomorrow"}]
        )
    with pytest.raises(ValueError, match="control characters"):
        module.TypedARBDecisionService._canonical_conditions(
            [{"code": "SEC\n1", "text": "A"}]
        )
    with pytest.raises(ValueError, match="exceeds 80"):
        module.TypedARBDecisionService._canonical_conditions(
            [{"code": "X" * 81, "text": "A"}]
        )
    normalized = module.TypedARBDecisionService._canonical_conditions(
        [{"code": " SEC   1 ", "text": "  Complete   review  "}]
    )
    assert normalized[0]["condition_number"] == "SEC 1"
    assert normalized[0]["description"] == "Complete review"


def test_handler_authority_mode_locks_server_user_row(monkeypatch):
    module = _decision_module()
    statements = []
    user = SimpleNamespace(
        id=73, is_org_admin=False, is_platform_admin=False,
        enterprise_role="chief_architect",
    )

    class Result:
        def scalar_one_or_none(self):
            return user

    session = SimpleNamespace(
        execute=lambda statement: statements.append(statement) or Result()
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_load_cycle_and_review",
        classmethod(
            lambda cls, session, actor, cycle_id, for_update: (
                SimpleNamespace(id=501, subject_type="adr"),
                SimpleNamespace(submitter_id=99),
            )
        ),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_assert_cycle_review_projection_equal",
        staticmethod(lambda cycle, review: None),
    )

    module.TypedARBDecisionService.authorise_decision(
        session, _actor(), 501, for_update=True
    )

    assert statements[0]._for_update_arg is not None


@pytest.mark.parametrize("board_authorized", [True, False])
def test_non_brief_board_member_authority_is_server_derived(
    monkeypatch, board_authorized
):
    module = _decision_module()
    user = SimpleNamespace(
        id=73, is_org_admin=False, is_platform_admin=False, enterprise_role="viewer"
    )
    session = SimpleNamespace(
        execute=lambda statement: SimpleNamespace(
            scalar_one_or_none=lambda: user
        )
    )
    cycle = SimpleNamespace(id=501, subject_type="adr")
    review = SimpleNamespace(submitter_id=99, arb_session_id=601)
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_load_cycle_and_review",
        classmethod(lambda cls, session, actor, cycle_id, for_update: (cycle, review)),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_assert_cycle_review_projection_equal",
        staticmethod(lambda cycle, review: None),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_has_board_authority",
        staticmethod(lambda session, actor, review, for_update: board_authorized),
    )

    if board_authorized:
        module.TypedARBDecisionService.authorise_decision(session, _actor(), 501)
    else:
        with pytest.raises(NotAuthorised, match="not_authorised"):
            module.TypedARBDecisionService.authorise_decision(session, _actor(), 501)


@pytest.mark.parametrize("assigned", [True, False])
def test_decision_brief_denies_unassigned_architect(monkeypatch, assigned):
    module = _decision_module()
    user = SimpleNamespace(
        id=73, is_org_admin=False, is_platform_admin=False,
        enterprise_role="enterprise_architect",
    )
    session = SimpleNamespace(
        execute=lambda statement: SimpleNamespace(
            scalar_one_or_none=lambda: user
        )
    )
    cycle = SimpleNamespace(id=501, subject_type="decision_brief")
    review = SimpleNamespace(submitter_id=99)
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_load_cycle_and_review",
        classmethod(lambda cls, session, actor, cycle_id, for_update: (cycle, review)),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_assert_cycle_review_projection_equal",
        staticmethod(lambda cycle, review: None),
    )
    monkeypatch.setattr(
        module.TypedARBDecisionService,
        "_has_decision_brief_authority",
        staticmethod(lambda session, actor, cycle, for_update: assigned),
    )

    if assigned:
        module.TypedARBDecisionService.authorise_decision(session, _actor(), 501)
    else:
        with pytest.raises(NotAuthorised, match="not_authorised"):
            module.TypedARBDecisionService.authorise_decision(session, _actor(), 501)


def test_named_decision_authority_is_denied_after_canonical_authority_expires(
    monkeypatch
):
    module = _decision_module()
    results = iter(
        (
            SimpleNamespace(
                scalar_one_or_none=lambda: SimpleNamespace(
                    id=801, workstream_id=901, decision_authority_id=73
                )
            ),
            SimpleNamespace(
                scalar_one_or_none=lambda: SimpleNamespace(id=901, programme_id=1001)
            ),
            SimpleNamespace(first=lambda: None),
        )
    )
    session = SimpleNamespace(execute=lambda statement: next(results))
    monkeypatch.setattr(
        module,
        "_decision_brief_service",
        lambda: SimpleNamespace(
            _user_has_decision_authority=lambda *args, **kwargs: False
        ),
    )

    assert module.TypedARBDecisionService._has_decision_brief_authority(
        session,
        _actor(),
        SimpleNamespace(decision_brief_id=801),
        for_update=True,
    ) is False
