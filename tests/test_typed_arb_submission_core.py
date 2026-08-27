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

    def snapshot(self, actor, subject, readiness):
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
    assert captured["natural_key"] == f"arb-submission:41:{subject_type}:9001"
    assert captured["payload"] == {
        "subject_type": subject_type,
        "subject_id": 9001,
        "assertions": {"human_reviewed": True},
    }
    assert calls == [
        ("load", 41, 9001),
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


def test_open_cycle_natural_key_is_subject_scoped_not_command_scoped(monkeypatch):
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

    assert natural_keys == ["arb-submission:41:adr:9001"] * 2


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
