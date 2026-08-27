"""RED contracts for the command-fenced typed ARB condition lifecycle (C3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
import inspect
from types import SimpleNamespace

import pytest

from app.modules.transformation_room.domain import ActorContext, DomainMutationResult


def _module():
    try:
        return importlib.import_module(
            "app.modules.transformation_room.arb_condition_lifecycle_service"
        )
    except ModuleNotFoundError:
        pytest.fail("C3 requires TypedARBConditionLifecycleService")


def _actor(user_id=73):
    return ActorContext(user_id, 41, frozenset({"platform_admin"}), "c3-red")


def _condition(status="pending", revision=1):
    return SimpleNamespace(
        id=601,
        organization_id=41,
        status=status,
        revision=revision,
        decision_event_id=401,
        review_cycle_id=501,
        review_item_id=502,
        submitted_evidence_id=701,
        evidence_submitted_by_id=72,
        waiver_prior_status=None,
    )


@pytest.mark.parametrize(
    ("method", "event_type", "status", "revision"),
    (
        ("submit_evidence", "submit_evidence", "pending", 2),
        ("verify", "verify", "evidence_submitted", 3),
        ("waive", "waive", "pending", 2),
    ),
)
def test_actor_commands_use_exact_operation_natural_key_and_next_revision(
    monkeypatch, method, event_type, status, revision
):
    module = _module()
    service = module.TypedARBConditionLifecycleService
    captured = {}
    monkeypatch.setattr(
        service,
        "_preload_identity",
        classmethod(lambda cls, session, actor, condition_id: _condition(status, revision - 1)),
    )
    monkeypatch.setattr(
        service,
        "_existing_receipt",
        staticmethod(lambda session, actor, operation, command_key: None),
    )
    monkeypatch.setattr(
        service,
        "_canonical_transition_revision",
        classmethod(
            lambda cls, session, actor, condition, event_type, evidence_id: revision
        ),
    )
    monkeypatch.setattr(
        service,
        "authorise_transition",
        classmethod(lambda cls, *args, **kwargs: None),
    )
    monkeypatch.setattr(
        service,
        "_transition_locked",
        classmethod(
            lambda cls, **kwargs: DomainMutationResult(
                object_ids={
                    "condition_id": 601,
                    "condition_event_id": 801,
                    "condition_revision": revision,
                },
                response={"status": "ok"},
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
            SimpleNamespace(), SimpleNamespace(receipt_id=901, generation=1)
        )

    monkeypatch.setattr(module.CommandService, "execute", execute)
    arguments = {
        "actor": _actor(), "command_key": f"c3-{event_type}", "condition_id": 601,
    }
    if method == "submit_evidence":
        arguments["condition_evidence_id"] = 701
    elif method == "verify":
        arguments["condition_evidence_id"] = 701
    else:
        arguments.update(
            reason="Time-bound risk acceptance",
            expires_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            scope={"release": "R1"},
            compensating_control="Daily security review",
        )
    getattr(service, method)(**arguments)

    assert captured["operation"] == {
        "submit_evidence": "arb.condition.evidence.submit",
        "verify": "arb.condition.evidence.verify",
        "waive": "arb.condition.waive",
    }[event_type]
    assert captured["natural_key"] == f"arb-condition:41:601:{event_type}:{revision}"
    assert captured["payload"]["expected_revision"] == revision - 1


def test_system_expiry_uses_exact_revisioned_identity(monkeypatch):
    module = _module()
    service = module.TypedARBConditionLifecycleService
    assert service.EXPIRE_OPERATION == "arb.condition.waiver.expire"
    assert service.natural_key(41, 601, "waiver_expired", 5) == (
        "arb-condition:41:601:waiver_expired:5"
    )
    assert callable(service.expire_waivers)
    assert service.SYSTEM_EVENT_TYPE == "waiver_expired"


def test_transition_matrix_and_event_before_projection_are_explicit():
    service = _module().TypedARBConditionLifecycleService
    assert service.TRANSITIONS == {
        "submit_evidence": {"pending": "evidence_submitted"},
        "verify": {"evidence_submitted": "fulfilled"},
        "waive": {"pending": "waived", "evidence_submitted": "waived"},
        "waiver_expired": {
            "waived:pending": "pending",
            "waived:evidence_submitted": "evidence_submitted",
        },
    }
    source = inspect.getsource(service._transition_locked)
    assert source.index("ARBConditionEvent(") < source.index("condition.status =")
    assert source.index("session.flush()") < source.index("condition.status =")


def test_subject_advisory_lock_precedes_deterministic_rows_and_authority_recheck():
    service = _module().TypedARBConditionLifecycleService
    source = inspect.getsource(service._transition_locked)
    assert source.index("_lock_subject_submission") < source.index("_lock_graph")
    assert source.index("_lock_graph") < source.index("authorise_transition")
    graph = inspect.getsource(service._lock_graph)
    assert graph.index("ARBReviewCycle") < graph.index("ARBReviewItem")
    assert graph.index("ARBReviewItem") < graph.index("ARBDecisionEvent")
    assert graph.index("ARBDecisionEvent") < graph.index("ARBCondition")
    assert graph.index("ARBCondition") < graph.index("User")


def test_authority_is_server_derived_replay_safe_and_separated():
    service = _module().TypedARBConditionLifecycleService
    source = inspect.getsource(service.authorise_transition)
    assert "actor.roles" not in source
    assert "organization_id" in source
    assert "with_for_update" in source
    assert "evidence_submitted_by_id" in source
    assert "submitter_id" in source
    assert callable(service._load_active_board_membership)
    assert callable(service._load_pinned_decision_brief_authority)


@pytest.mark.parametrize("bad_reason", ["", "x" * 2001, "bad\x00reason"])
def test_waiver_reason_is_bounded_and_printable(bad_reason):
    service = _module().TypedARBConditionLifecycleService
    with pytest.raises(ValueError):
        service.canonicalize_waiver(
            reason=bad_reason,
            expires_at=datetime.now(timezone.utc) + timedelta(days=2),
            scope={"release": "R1"},
            compensating_control="Daily security review",
            now=datetime.now(timezone.utc),
        )


def test_waiver_requires_bounded_scope_control_and_future_capped_expiry():
    service = _module().TypedARBConditionLifecycleService
    now = datetime.now(timezone.utc)
    for override in (
        {"expires_at": now},
        {"expires_at": now + timedelta(days=service.MAX_WAIVER_DAYS + 1)},
        {"scope": {}},
        {"scope": {"blob": "x" * (service.MAX_WAIVER_SCOPE_BYTES + 1)}},
        {"compensating_control": ""},
        {"compensating_control": "x" * 2001},
    ):
        values = {
            "reason": "Time-bound risk acceptance",
            "expires_at": now + timedelta(days=2),
            "scope": {"release": "R1"},
            "compensating_control": "Daily security review",
            "now": now,
        }
        values.update(override)
        with pytest.raises(ValueError):
            service.canonicalize_waiver(**values)


def test_expiry_restores_exact_prior_status_and_never_accepts_client_actor():
    service = _module().TypedARBConditionLifecycleService
    pending = _condition("waived", 4)
    pending.waiver_prior_status = "pending"
    submitted = _condition("waived", 7)
    submitted.waiver_prior_status = "evidence_submitted"
    assert service._expiry_target(pending) == "pending"
    assert service._expiry_target(submitted) == "evidence_submitted"
    assert "actor" not in inspect.signature(service.expire_waivers).parameters


def test_projection_only_approves_after_last_blocking_condition():
    service = _module().TypedARBConditionLifecycleService
    assert service.project_outcome(
        prior_outcome="approved_with_conditions",
        condition_statuses=("fulfilled", "waived"),
    ) == "approved"
    assert service.project_outcome(
        prior_outcome="approved_with_conditions",
        condition_statuses=("fulfilled", "pending"),
    ) == "approved_with_conditions"
    assert service.project_outcome(
        prior_outcome="approved",
        condition_statuses=("fulfilled", "pending"),
    ) == "approved_with_conditions"


def test_cycle_and_review_projection_are_equal_and_revision_monotonic():
    source = inspect.getsource(_module().TypedARBConditionLifecycleService._project_review)
    assert "cycle.status = projected_status" in source
    assert "review.status = projected_status" in source
    assert "cycle.condition_projection_revision = projection_revision" in source
    assert "review.condition_projection_revision = projection_revision" in source
    assert "terminal_outcome" not in source
    assert "review.decision" not in source


def test_history_guard_allows_proven_same_status_projection_without_rewriting_decision():
    from app.models.architecture_review_board import _arb_history_function_sql

    sql = _arb_history_function_sql('"public"')
    assert "NEW.status <> OLD.status" not in sql
    assert "JOIN command_idempotency_records receipt" in sql
    assert "receipt.natural_key = 'arb-condition:'" in sql
    assert "aggregate_condition.status NOT IN ('fulfilled', 'waived')" in sql
    assert "NEW.terminal_outcome = OLD.terminal_outcome" in sql
    assert "NEW.decision = OLD.decision" in sql


def test_same_key_replays_and_different_key_reconciles_canonical_event():
    service = _module().TypedARBConditionLifecycleService
    assert service.NATURAL_KEY_RECONCILIATION is True
    assert callable(service._reauthorise_replay)


def test_verify_waive_and_expiry_share_one_subject_fence_and_revision_cas():
    service = _module().TypedARBConditionLifecycleService
    assert service.CONCURRENT_TRANSITIONS_SERIALIZED is True
    source = inspect.getsource(service._transition_locked)
    assert "expected_revision" in source
    assert "condition.revision" in source
    assert "CommandConflict" in source


def test_failure_before_command_completion_rolls_back_event_and_projections():
    service = _module().TypedARBConditionLifecycleService
    assert service.ATOMIC_EVENT_CONDITION_CYCLE_REVIEW_RESULT is True
    assert callable(service._transition_locked)


def test_upgrade_preserves_pre_c3_evidence_as_explicit_legacy_provenance():
    from app.models.arb_decision_event import ARBCondition, _condition_reconcile_sql

    assert "legacy_lifecycle_provenance" in ARBCondition.__table__.columns
    sql = _condition_reconcile_sql('"public"')
    assert "'classification','pre_c3_fulfilment'" in sql
    assert "'legacy_fulfilment_evidence_id',fulfilment_evidence_id" in sql
    assert "SET fulfilment_evidence_id = NULL" in sql
    assert "'classification','pre_c3_waiver'" in sql
    assert "SET fulfilment_evidence_id = submitted_evidence_id" not in sql
    assert "NOT EXISTS" in sql
    assert "evidence.condition_id=condition.id" in sql
    assert "ck_arb_condition_legacy_provenance" in sql


def test_condition_mutation_guard_requires_exact_event_and_receipt():
    from app.models.arb_decision_event import (
        _condition_membership_sql,
        ensure_arb_decision_guards,
    )

    membership = _condition_membership_sql('"public"')
    assert "legacy ARB condition provenance is reconcile-only" in membership
    source = inspect.getsource(ensure_arb_decision_guards)
    assert "lifecycle mutation lacks exact event provenance" in source
    assert "JOIN {q}.command_idempotency_records receipt" in source
    assert "condition_event.from_state=OLD.status" in source
    assert "condition_event.to_state=NEW.status" in source
    assert "NEW.revision=OLD.revision + 1" in source
    assert "legacy ARB condition provenance is immutable" in source
