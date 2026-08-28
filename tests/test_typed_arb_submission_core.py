"""RED contracts for the sole typed-subject ARB submission command.

These tests deliberately specify the service boundary before its implementation.
The model and adapter contracts live in their own test modules; this module owns
the missing orchestration contract: command replay, one atomic cycle graph, and
legacy Solution compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from types import SimpleNamespace

import pytest

from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    CommandResult,
    DomainMutationResult,
    GovernedSubject,
    NotFound,
    PinnedEvidence,
)


SUBJECT_CASES = (
    ("decision_brief", "decision_brief_id", "decision_brief_version_id", "decision_brief_version"),
    ("solution", "solution_id", "solution_evidence_snapshot_id", "solution_evidence_snapshot"),
    ("architecture_model", "architecture_model_id", "subject_evidence_snapshot_id", "arb_subject_evidence_snapshot"),
    ("adr", "adr_id", "subject_evidence_snapshot_id", "arb_subject_evidence_snapshot"),
)


@pytest.fixture(autouse=True)
def _isolate_command_boundary_from_database_authority(monkeypatch, request):
    module = _submission_module()
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "authorise_submit",
        classmethod(lambda cls, session, actor, subject_type, subject_id: None),
    )
    if request.node.name not in {
        "test_decision_brief_same_version_terminal_reuses_predecessor_anchor",
        "test_decision_brief_new_version_anchors_successor_after_terminal_cycle",
    }:
        monkeypatch.setattr(
            module.TypedARBSubmissionService,
            "_submission_anchor",
            classmethod(
                lambda cls, session, organization_id, subject_type, subject_id,
                logical_version_id=None: "root"
            ),
            raising=False,
        )
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_existing_command_receipt",
        classmethod(lambda cls, session, actor, command_key: None),
        raising=False,
    )
    monkeypatch.setattr(
        module.CommandService,
        "resolve_materialisation",
        classmethod(lambda cls, session, **kwargs: None),
    )


def _submission_module():
    try:
        return importlib.import_module(
            "app.modules.transformation_room.arb_submission_service"
        )
    except ModuleNotFoundError:
        pytest.fail(
            "Package C1 requires app.modules.transformation_room."
            "arb_submission_service.TypedARBSubmissionService"
        )


def _actor(org_id=41, user_id=73):
    return ActorContext(
        user_id=user_id,
        organization_id=org_id,
        roles=frozenset({"enterprise_architect"}),
        request_id="typed-arb-contract",
    )


def test_locked_handler_reuses_visible_natural_key_winner(monkeypatch):
    module = _submission_module()
    winner = DomainMutationResult(
        object_ids={"review_item_id": 91},
        response={"status": "submitted"},
        outbox_events=(),
    )
    monkeypatch.setattr(
        module.CommandService,
        "resolve_materialisation",
        classmethod(lambda cls, session, **kwargs: winner),
    )
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_lock_subject_submission",
        classmethod(lambda cls, session, actor, subject: None),
    )
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_authorise_submission_context",
        classmethod(lambda cls, session, actor, subject_type, subject_id, assertions: None),
    )
    adapter = SimpleNamespace(
        evaluate=lambda *_args, **_kwargs: pytest.fail(
            "a visible natural-key winner must return before re-evaluation"
        )
    )

    result = module.TypedARBSubmissionService._submit_locked(
        session=object(),
        actor=_actor(),
        subject=GovernedSubject("adr", 17, 41, "ADR-17", None),
        adapter=adapter,
        assertions={},
        claim=SimpleNamespace(),
        claimed_anchor="root",
    )

    assert result is winner


@dataclass
class _AdapterProbe:
    subject_type: str
    organization_id: int
    evidence_type: str
    evidence_id: int
    calls: list

    review_type = "architecture_change"

    def load(self, actor, subject_id):
        self.calls.append(("load", actor.organization_id, subject_id))
        if actor.organization_id != self.organization_id:
            raise NotFound("arb_subject_not_found")
        return GovernedSubject(
            self.subject_type,
            subject_id,
            self.organization_id,
            f"Governed {self.subject_type}",
            self.evidence_id if self.subject_type == "decision_brief" else None,
        )

    def evaluate(self, actor, subject, assertions):
        self.calls.append(("evaluate", subject.subject_id, dict(assertions)))
        return SimpleNamespace(ready=True, reason_codes=[], missing_evidence=[])

    def snapshot(self, actor, subject, readiness, *, review_item_id=None):
        self.calls.append(("snapshot", subject.subject_id, readiness.ready))
        return PinnedEvidence(self.evidence_type, self.evidence_id, "a" * 64)

    def canonical_url(self, subject):
        return f"/governance/{subject.subject_type}/{subject.subject_id}"


def _command_result(*, created=True, object_ids=None):
    object_ids = object_ids or {"review_cycle_id": 101, "review_item_id": 102, "evidence_id": 103}
    return CommandResult(
        created=created,
        idempotent=not created,
        operation_result_id=104,
        object_ids=object_ids,
        response={**object_ids, "status": "submitted"},
    )


@pytest.mark.parametrize(
    ("subject_type", "subject_fk", "evidence_fk", "evidence_type"),
    SUBJECT_CASES,
)
def test_submit_routes_all_subject_types_through_one_command_and_atomic_handler(
    monkeypatch, subject_type, subject_fk, evidence_fk, evidence_type
):
    """Every subject uses the same replay-safe command and graph writer."""
    module = _submission_module()
    calls = []
    adapter = _AdapterProbe(subject_type, 41, evidence_type, 103, calls)
    captured = {}

    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)

    def execute(**kwargs):
        captured.update(kwargs)
        # The handler is the atomic boundary: snapshot, cycle, and item must be
        # performed inside CommandService's fenced transaction, not beforehand.
        assert calls == [("load", 41, 9001)]
        mutation = kwargs["handler"](SimpleNamespace(), SimpleNamespace())
        assert isinstance(mutation, DomainMutationResult)
        return _command_result(object_ids=dict(mutation.object_ids))

    monkeypatch.setattr(module.CommandService, "execute", execute)
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_reserve_review_item_id",
        staticmethod(lambda session: 777),
    )
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_lock_subject_submission",
        classmethod(
            lambda cls, session, actor, subject: calls.append(
                ("advisory_lock", actor.organization_id, subject.subject_type, subject.subject_id)
            )
        ),
    )
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_insert_submission_graph",
        classmethod(
            lambda cls, **kwargs: (
                calls.append(("graph", kwargs["subject"].subject_type, kwargs["pinned_evidence"].evidence_type)),
                DomainMutationResult(
                    object_ids={
                        "review_cycle_id": 101,
                        "review_item_id": 102,
                        "evidence_id": 103,
                    },
                    response={
                        "review_cycle_id": 101,
                        "review_item_id": 102,
                        "evidence_id": 103,
                        "status": "submitted",
                    },
                    outbox_events=(),
                ),
            )[1]
        ),
    )

    result = module.TypedARBSubmissionService.submit(
        actor=_actor(),
        command_key=f"submit-{subject_type}",
        subject_type=subject_type,
        subject_id=9001,
        assertions={"human_reviewed": True},
    )

    assert result.created is True
    assert result.object_ids == {
        "review_cycle_id": 101,
        "review_item_id": 102,
        "evidence_id": 103,
    }
    assert captured["operation"] == "arb.submit"
    assert captured["idempotency_key"] == f"submit-{subject_type}"
    assert captured["natural_key"] == (
        f"arb-submission:41:{subject_type}:9001:after:root"
    )
    assert captured["payload"] == {
        "subject_type": subject_type,
        "subject_id": 9001,
        "assertions": {"human_reviewed": True},
    }
    assert calls == [
        ("load", 41, 9001),
        ("advisory_lock", 41, subject_type, 9001),
        ("evaluate", 9001, {"human_reviewed": True}),
        ("snapshot", 9001, True),
        ("graph", subject_type, evidence_type),
    ]


def test_replay_returns_the_original_ids_without_re_evaluating_or_resnapshotting(monkeypatch):
    module = _submission_module()
    calls = []
    adapter = _AdapterProbe("adr", 41, "arb_subject_evidence_snapshot", 103, calls)
    winner = _command_result()

    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)
    monkeypatch.setattr(module.CommandService, "execute", lambda **kwargs: winner)

    first = module.TypedARBSubmissionService.submit(
        actor=_actor(), command_key="same-command", subject_type="adr", subject_id=9001,
        assertions={"human_reviewed": True},
    )
    replay = module.TypedARBSubmissionService.submit(
        actor=_actor(), command_key="same-command", subject_type="adr", subject_id=9001,
        assertions={"human_reviewed": True},
    )

    assert first.object_ids == replay.object_ids
    # Loading is pre-authorisation and may occur on each HTTP request; governed
    # evaluation and snapshot creation must remain inside the uncalled handler.
    assert calls == [("load", 41, 9001), ("load", 41, 9001)]


def test_foreign_tenant_subject_is_rejected_before_a_command_receipt_is_claimed(monkeypatch):
    module = _submission_module()
    adapter = _AdapterProbe("architecture_model", 99, "arb_subject_evidence_snapshot", 103, [])
    claimed = False

    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)

    def execute(**kwargs):
        nonlocal claimed
        claimed = True

    monkeypatch.setattr(module.CommandService, "execute", execute)

    with pytest.raises(NotFound, match="arb_subject_not_found"):
        module.TypedARBSubmissionService.submit(
            actor=_actor(org_id=41), command_key="foreign", subject_type="architecture_model",
            subject_id=9001, assertions={"human_reviewed": True},
        )
    assert claimed is False


def test_subordinate_write_failure_escapes_handler_so_command_service_can_roll_back(monkeypatch):
    module = _submission_module()
    adapter = _AdapterProbe("adr", 41, "arb_subject_evidence_snapshot", 103, [])
    rollback_error = RuntimeError("forced review-item insert failure")

    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_lock_subject_submission",
        classmethod(lambda cls, session, actor, subject: None),
    )
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_insert_submission_graph",
        classmethod(lambda cls, **kwargs: (_ for _ in ()).throw(rollback_error)),
    )

    def execute(**kwargs):
        return kwargs["handler"](SimpleNamespace(), SimpleNamespace())

    monkeypatch.setattr(module.CommandService, "execute", execute)

    with pytest.raises(RuntimeError, match="forced review-item insert failure"):
        module.TypedARBSubmissionService.submit(
            actor=_actor(), command_key="rollback", subject_type="adr", subject_id=9001,
            assertions={"human_reviewed": True},
        )


def test_first_submission_and_open_cycle_retries_keep_root_anchor(monkeypatch):
    module = _submission_module()
    adapter = _AdapterProbe("adr", 41, "arb_subject_evidence_snapshot", 103, [])
    natural_keys = []
    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)

    def execute(**kwargs):
        natural_keys.append(kwargs["natural_key"])
        return _command_result(created=len(natural_keys) == 1)

    monkeypatch.setattr(module.CommandService, "execute", execute)
    for command_key in ("browser-a", "browser-b"):
        module.TypedARBSubmissionService.submit(
            actor=_actor(), command_key=command_key, subject_type="adr", subject_id=9001,
            assertions={"human_reviewed": True},
        )

    assert natural_keys == ["arb-submission:41:adr:9001:after:root"] * 2


def test_terminal_cycle_becomes_anchor_for_successor(monkeypatch):
    module = _submission_module()
    adapter = _AdapterProbe("adr", 41, "arb_subject_evidence_snapshot", 103, [])
    captured = {}
    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_submission_anchor",
        classmethod(
            lambda cls, session, organization_id, subject_type, subject_id,
            logical_version_id=None: 515
        ),
    )
    monkeypatch.setattr(
        module.CommandService,
        "execute",
        lambda **kwargs: captured.update(kwargs) or _command_result(),
    )

    module.TypedARBSubmissionService.submit(
        actor=_actor(), command_key="successor", subject_type="adr", subject_id=9001
    )

    assert captured["natural_key"] == "arb-submission:41:adr:9001:after:515"


def test_open_successor_retries_keep_its_predecessor_anchor(monkeypatch):
    module = _submission_module()
    adapter = _AdapterProbe("adr", 41, "arb_subject_evidence_snapshot", 103, [])
    natural_keys = []
    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_submission_anchor",
        classmethod(
            lambda cls, session, organization_id, subject_type, subject_id,
            logical_version_id=None: 515
        ),
    )
    monkeypatch.setattr(
        module.CommandService,
        "execute",
        lambda **kwargs: natural_keys.append(kwargs["natural_key"])
        or _command_result(created=len(natural_keys) == 1),
    )

    for key in ("successor-winner", "lost-browser-key"):
        module.TypedARBSubmissionService.submit(
            actor=_actor(), command_key=key, subject_type="adr", subject_id=9001
        )

    assert natural_keys == ["arb-submission:41:adr:9001:after:515"] * 2


def test_authorizer_accepts_replay_after_winner_opens_same_anchor(monkeypatch):
    module = _submission_module()
    adapter = _AdapterProbe("adr", 41, "arb_subject_evidence_snapshot", 103, [])
    captured = {}
    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)
    monkeypatch.setattr(
        module.CommandService,
        "execute",
        lambda **kwargs: captured.update(kwargs) or _command_result(created=False),
    )

    module.TypedARBSubmissionService.submit(
        actor=_actor(), command_key="replay", subject_type="adr", subject_id=9001
    )
    captured["authorizer"](
        SimpleNamespace(),
        _actor(),
        "arb.submit",
        "arb-submission:41:adr:9001:after:root",
    )


def test_authorizer_rejects_anchor_that_changed_before_claim_revalidation(monkeypatch):
    module = _submission_module()
    adapter = _AdapterProbe("adr", 41, "arb_subject_evidence_snapshot", 103, [])
    captured = {}
    anchors = iter(("root", 515))
    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_submission_anchor",
        classmethod(
            lambda cls, session, organization_id, subject_type, subject_id,
            logical_version_id=None: next(anchors)
        ),
    )
    monkeypatch.setattr(
        module.CommandService,
        "execute",
        lambda **kwargs: captured.update(kwargs) or _command_result(),
    )

    module.TypedARBSubmissionService.submit(
        actor=_actor(), command_key="raced", subject_type="adr", subject_id=9001
    )
    with pytest.raises(CommandConflict, match="arb_submission_anchor_changed"):
        captured["authorizer"](
            SimpleNamespace(),
            _actor(),
            "arb.submit",
            "arb-submission:41:adr:9001:after:root",
        )


def test_locked_handler_fails_closed_when_anchor_changes_before_lock(monkeypatch):
    module = _submission_module()
    adapter = _AdapterProbe("adr", 41, "arb_subject_evidence_snapshot", 103, [])
    subject = adapter.load(_actor(), 9001)
    anchors = iter(("root", 515))
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_submission_anchor",
        classmethod(
            lambda cls, session, organization_id, subject_type, subject_id,
            logical_version_id=None: next(anchors)
        ),
    )
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_lock_subject_submission",
        classmethod(lambda cls, session, actor, subject: None),
    )

    claimed = module.TypedARBSubmissionService._submission_anchor(
        object(), 41, "adr", 9001
    )
    with pytest.raises(CommandConflict, match="arb_submission_anchor_changed"):
        module.TypedARBSubmissionService._submit_locked(
            session=object(), actor=_actor(), subject=subject, adapter=adapter,
            assertions={}, claim=SimpleNamespace(), claimed_anchor=claimed,
        )


@pytest.mark.parametrize("subject_type", [case[0] for case in SUBJECT_CASES])
def test_same_key_terminal_replay_reuses_receipt_natural_key(monkeypatch, subject_type):
    module = _submission_module()
    evidence_type = dict((case[0], case[3]) for case in SUBJECT_CASES)[subject_type]
    adapter = _AdapterProbe(subject_type, 41, evidence_type, 103, [])
    captured = {}
    original_key = f"arb-submission:41:{subject_type}:9001:after:root"
    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_submission_anchor",
        classmethod(
            lambda cls, session, organization_id, subject_type, subject_id,
            logical_version_id=None: 515
        ),
    )
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_existing_command_receipt",
        classmethod(
            lambda cls, session, actor, command_key: SimpleNamespace(
                id=77, natural_key=original_key, status="succeeded",
                completed_at=object(), operation_result_id=88,
            )
        ),
    )
    monkeypatch.setattr(
        module.CommandService,
        "execute",
        lambda **kwargs: captured.update(kwargs) or _command_result(created=False),
    )

    module.TypedARBSubmissionService.submit(
        actor=_actor(), command_key="same-key", subject_type=subject_type,
        subject_id=9001,
    )

    assert captured["natural_key"] == original_key


@pytest.mark.parametrize("proven", [True, False])
def test_terminal_replay_authorizer_requires_completed_materialisation(
    monkeypatch, proven
):
    module = _submission_module()
    adapter = _AdapterProbe("adr", 41, "arb_subject_evidence_snapshot", 103, [])
    captured = {}
    receipt = SimpleNamespace(
        id=77,
        natural_key="arb-submission:41:adr:9001:after:root",
    )
    monkeypatch.setattr(module, "get_arb_subject_adapter", lambda value: adapter)
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_submission_anchor",
        classmethod(
            lambda cls, session, organization_id, subject_type, subject_id,
            logical_version_id=None: 515
        ),
    )
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_existing_command_receipt",
        classmethod(lambda cls, session, actor, command_key: receipt),
    )
    monkeypatch.setattr(
        module.TypedARBSubmissionService,
        "_receipt_proves_submission",
        classmethod(lambda cls, *args: proven),
    )
    monkeypatch.setattr(
        module.CommandService,
        "execute",
        lambda **kwargs: captured.update(kwargs) or _command_result(created=False),
    )
    module.TypedARBSubmissionService.submit(
        actor=_actor(), command_key="same-key", subject_type="adr", subject_id=9001
    )

    def call():
        captured["authorizer"](
            SimpleNamespace(), _actor(), "arb.submit", receipt.natural_key
        )
    if proven:
        call()
    else:
        with pytest.raises(CommandConflict, match="arb_submission_anchor_changed"):
            call()


def test_decision_brief_same_version_terminal_reuses_predecessor_anchor():
    module = _submission_module()
    terminal = SimpleNamespace(
        id=515, closed_at=object(), predecessor_cycle_id=414,
        decision_brief_version_id=103,
    )
    session = SimpleNamespace(
        execute=lambda statement: SimpleNamespace(
            scalar_one_or_none=lambda: terminal
        )
    )

    anchor = module.TypedARBSubmissionService._submission_anchor(
        session, 41, "decision_brief", 9001, logical_version_id=103
    )

    assert anchor == 414


def test_decision_brief_new_version_anchors_successor_after_terminal_cycle():
    module = _submission_module()
    terminal = SimpleNamespace(
        id=515, closed_at=object(), predecessor_cycle_id=414,
        decision_brief_version_id=103,
    )
    session = SimpleNamespace(
        execute=lambda statement: SimpleNamespace(
            scalar_one_or_none=lambda: terminal
        )
    )

    anchor = module.TypedARBSubmissionService._submission_anchor(
        session, 41, "decision_brief", 9001, logical_version_id=104
    )

    assert anchor == 515


def test_first_cycle_lock_key_is_deterministic_and_subject_scoped():
    """Concurrent first submissions must serialize even before a history row exists."""
    module = _submission_module()
    service = module.TypedARBSubmissionService

    same_a = service._subject_lock_key(41, "architecture_model", 9001)
    same_b = service._subject_lock_key(41, "architecture_model", 9001)

    assert same_a == same_b
    assert -(2**63) <= same_a < 2**63
    assert same_a != service._subject_lock_key(42, "architecture_model", 9001)
    assert same_a != service._subject_lock_key(41, "adr", 9001)
    assert same_a != service._subject_lock_key(41, "architecture_model", 9002)


def test_first_cycle_advisory_lock_serializes_independent_transactions(app):
    """A second PostgreSQL transaction cannot enter the empty-history gap."""
    from app import db

    module = _submission_module()
    lock_key = module.TypedARBSubmissionService._subject_lock_key(
        41, "architecture_model", 9001
    )
    with app.app_context():
        first = db.engine.raw_connection()
        second = db.engine.raw_connection()
        try:
            with first.cursor() as first_cursor, second.cursor() as second_cursor:
                first_cursor.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
                second_cursor.execute(
                    "SELECT pg_try_advisory_xact_lock(%s)", (lock_key,)
                )
                assert second_cursor.fetchone()[0] is False
                second.rollback()

                first.rollback()
                second_cursor.execute(
                    "SELECT pg_try_advisory_xact_lock(%s)", (lock_key,)
                )
                assert second_cursor.fetchone()[0] is True
                second.rollback()
        finally:
            first.close()
            second.close()


def test_legacy_solution_entrypoint_delegates_and_preserves_response_shape(monkeypatch):
    """The old Solution API remains a compatibility adapter, never a second writer."""
    module = _submission_module()
    expected = _command_result()
    captured = {}

    def submit(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(module.TypedARBSubmissionService, "submit", submit)
    result = module.TypedARBSubmissionService.submit_legacy_solution(
        actor=_actor(),
        command_key="legacy-solution-command",
        solution_id=9001,
        workspace_id=812,
        assertions={"human_reviewed": True},
    )

    assert result is expected
    assert captured == {
        "actor": _actor(),
        "command_key": "legacy-solution-command",
        "subject_type": "solution",
        "subject_id": 9001,
        "assertions": {"human_reviewed": True, "workspace_id": 812},
    }
