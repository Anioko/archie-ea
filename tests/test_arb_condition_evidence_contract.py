"""RED contract for condition-scoped ARB evidence (Package C3b).

The existing EvidenceRequest/EvidenceRecord aggregate is deliberately candidate-
scoped: its three programme/workstream/candidate foreign keys are mandatory and
its uniqueness and correction-chain invariants depend on that identity.  C3b
therefore specifies a dedicated immutable ARBConditionEvidenceRecord and treats
the canonical ARBCondition as the request being satisfied.  This avoids nullable
polymorphism and, critically, never fabricates transformation hierarchy IDs for
Solution, Architecture Model, or ADR reviews.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from app.models.mixins import TenantMixin
from app.modules.transformation_room.domain import (
    ActorContext,
    DomainMutationResult,
)


SUBJECT_TYPES = (
    "decision_brief",
    "solution",
    "architecture_model",
    "adr",
)


def _model_module():
    try:
        return importlib.import_module("app.models.arb_condition_evidence")
    except ModuleNotFoundError:
        pytest.fail(
            "C3b requires a dedicated immutable ARBConditionEvidenceRecord; "
            "candidate-scoped EvidenceRecord must not be generalized"
        )


def _service_module():
    try:
        return importlib.import_module(
            "app.modules.transformation_room.arb_condition_evidence_service"
        )
    except ModuleNotFoundError:
        pytest.fail("C3b requires TypedARBConditionEvidenceService")


def _actor():
    return ActorContext(73, 41, frozenset({"enterprise_architect"}), "c3b-red")


def test_condition_evidence_is_a_dedicated_tenant_immutable_aggregate():
    module = _model_module()
    record = module.ARBConditionEvidenceRecord
    assert issubclass(record, TenantMixin)
    columns = record.__table__.columns
    required = {
        "organization_id",
        "condition_id",
        "condition_revision",
        "decision_event_id",
        "review_cycle_id",
        "review_item_id",
        "subject_type",
        "subject_id",
        "decision_brief_id",
        "solution_id",
        "architecture_model_id",
        "adr_id",
        "decision_brief_version_id",
        "solution_evidence_snapshot_id",
        "subject_evidence_snapshot_id",
        "value_json",
        "content_hash",
        "source_identity",
        "source_type",
        "source_version",
        "source_checksum",
        "observed_at",
        "collected_at",
        "freshness_status",
        "freshness_expires_at",
        "freshness_rule_version",
        "created_by_id",
        "created_at",
    }
    assert required <= set(columns.keys())
    assert not {
        "programme_id",
        "workstream_id",
        "candidate_id",
    }.intersection(columns.keys())
    assert columns["content_hash"].nullable is False
    assert columns["source_checksum"].nullable is False
    assert callable(module.ensure_arb_condition_evidence_guards)


def test_condition_fulfilment_fk_accepts_only_the_dedicated_record():
    from app.models.arb_decision_event import ARBCondition

    targets = {
        foreign_key.target_fullname
        for foreign_key in ARBCondition.__table__.c.fulfilment_evidence_id.foreign_keys
    }
    assert targets == {"arb_condition_evidence_records.id"}


@pytest.mark.parametrize("subject_type", SUBJECT_TYPES)
def test_typed_shape_and_membership_are_explicit_for_every_subject(subject_type):
    module = _model_module()
    table = module.ARBConditionEvidenceRecord.__table__
    checks = " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if hasattr(constraint, "sqltext")
    )
    assert subject_type in checks
    assert "condition_id" in checks or callable(
        module.ensure_arb_condition_evidence_guards
    )
    # The PostgreSQL guard owns exact equality across record -> condition ->
    # decision event -> cycle/review, including tenant and pinned evidence IDs.
    assert module.CONDITION_EVIDENCE_MEMBERSHIP_IS_EXACT is True


def test_hash_source_and_freshness_are_append_only_guarded():
    module = _model_module()
    table = module.ARBConditionEvidenceRecord.__table__
    checks = " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "length(content_hash) = 64" in checks
    assert "length(source_checksum) = 64" in checks
    assert "freshness_status" in checks
    assert module.IMMUTABLE_CONDITION_EVIDENCE_FIELDS >= {
        "condition_id",
        "review_cycle_id",
        "subject_type",
        "subject_id",
        "value_json",
        "content_hash",
        "source_identity",
        "source_version",
        "source_checksum",
        "observed_at",
        "freshness_status",
        "freshness_expires_at",
        "freshness_rule_version",
    }


@pytest.mark.parametrize("subject_type", SUBJECT_TYPES)
def test_acceptance_uses_exact_condition_scoped_command(monkeypatch, subject_type):
    module = _service_module()
    captured = {}
    monkeypatch.setattr(
        module.TypedARBConditionEvidenceService,
        "_load_condition_graph",
        classmethod(
            lambda cls, session, actor, condition_id, for_update: (
                SimpleNamespace(id=601, revision=1),
                SimpleNamespace(),
                SimpleNamespace(),
                SimpleNamespace(),
            )
        ),
    )
    monkeypatch.setattr(
        module.TypedARBConditionEvidenceService,
        "_assert_exact_typed_membership",
        staticmethod(lambda condition, decision, cycle, review: None),
    )
    monkeypatch.setattr(
        module.TypedARBConditionEvidenceService,
        "authorise_acceptance",
        classmethod(lambda cls, session, actor, condition_id, **kwargs: None),
    )
    monkeypatch.setattr(
        module.TypedARBConditionEvidenceService,
        "_accept_locked",
        classmethod(
            lambda cls, **kwargs: DomainMutationResult(
                object_ids={
                    "condition_id": 601,
                    "condition_evidence_id": 701,
                    "review_cycle_id": 501,
                },
                response={"status": "fulfilled"},
                outbox_events=(),
            )
        ),
    )

    def execute(**kwargs):
        captured.update(kwargs)
        kwargs["authorizer"](
            SimpleNamespace(), kwargs["actor"], kwargs["operation"],
            kwargs["natural_key"],
        )
        return kwargs["handler"](
            SimpleNamespace(), SimpleNamespace(receipt_id=801, generation=1)
        )

    monkeypatch.setattr(module.CommandService, "execute", execute)
    payload = {
        "subject_type": subject_type,
        "source_identity": "cmdb:record:42",
        "source_type": "cmdb",
        "source_version": "7",
        "source_checksum": "a" * 64,
        "value_json": {"verified": True},
        "observed_at": "2026-08-27T10:00:00Z",
        "freshness_rule_version": "arb-condition-v1",
    }
    result = module.TypedARBConditionEvidenceService.accept(
        actor=_actor(), command_key=f"accept-{subject_type}", condition_id=601,
        evidence=payload,
    )

    assert result.object_ids["condition_evidence_id"] == 701
    assert captured["operation"] == "arb.condition.evidence.capture"
    assert captured["natural_key"] == "arb-condition-evidence:41:601:1"
    assert captured["payload"]["condition_id"] == 601
    assert captured["payload"]["condition_revision"] == 1
    assert captured["payload"]["evidence"]["freshness_status"] == "fresh"


def test_locked_acceptance_contract_requires_exact_pending_request_and_fresh_record():
    module = _service_module()
    service = module.TypedARBConditionEvidenceService
    assert service.ACCEPTED_CONDITION_STATUS == "evidence_submitted"
    assert service.REQUIRED_PRIOR_STATUS == "pending"
    assert service.ACCEPTABLE_FRESHNESS == frozenset({"fresh", "not_applicable"})
    assert callable(service._load_condition_graph_for_update)
    assert callable(service._assert_exact_typed_membership)
    assert callable(service._compute_content_hash)
    assert callable(service._reject_candidate_scope_fields)
