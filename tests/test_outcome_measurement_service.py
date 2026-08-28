"""Append-only measured-outcome contracts for canonical Benefits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.models.benefit import Benefit
from app.models.implementation_migration import WorkPackage
from app.models.strategic import StrategicInitiative
from app.models.transformation_execution import OutcomeMeasurement
from app.models.transformation_programme import (
    ProgrammeOutcomeCommitment,
    ProgrammeRoleAssignment,
    ProgrammeWorkstream,
)
from app.models.user import User
from app.modules.transformation_room.command_service import canonical_request_digest
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandClaim,
    CommandResult,
    NotFound,
)
from app.modules.transformation_room.outcome_service import OutcomeMeasurementService


@dataclass(frozen=True)
class OutcomeScope:
    actor: ActorContext
    delegate_actor: ActorContext
    foreign_actor: ActorContext
    benefit_id: int
    organization_id: int


def _user(session, organization_id, role):
    suffix = uuid4().hex
    row = User(
        organization_id=organization_id,
        email=f"outcome-{suffix}@example.test",
        first_name="Outcome",
        last_name="Owner",
        enterprise_role=role,
        confirmed=True,
    )
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def make_outcome_scope(db_session, make_org):
    def make(*, baseline=Decimal("1000.00")):
        organization = make_org("outcome")
        foreign_organization = make_org("outcome-foreign")
        owner = _user(db_session, organization.id, "business_architect")
        delegate = _user(db_session, organization.id, "portfolio_manager")
        foreign = _user(db_session, foreign_organization.id, "business_architect")
        programme = StrategicInitiative(
            organization_id=organization.id,
            name="Measured transformation",
            record_kind="transformation_programme",
            status="in_progress",
            owner_id=owner.id,
        )
        db_session.add(programme)
        db_session.flush()
        workstream = ProgrammeWorkstream(
            organization_id=organization.id,
            programme_id=programme.id,
            workstream_type="application_rationalisation",
            objective="Measure the approved benefit",
            scope_expression={},
            lifecycle_stage="outcomes",
            lead_id=owner.id,
        )
        db_session.add(workstream)
        db_session.flush()
        db_session.add(
            ProgrammeRoleAssignment(
                organization_id=organization.id,
                programme_id=programme.id,
                workstream_id=workstream.id,
                user_id=delegate.id,
                role="outcome_owner",
                effective_from=date.today() - timedelta(days=1),
                assigned_by_id=owner.id,
            )
        )
        outcome = ProgrammeOutcomeCommitment(
            organization_id=organization.id,
            programme_id=programme.id,
            workstream_id=workstream.id,
            statement="Reduce annual run cost",
            owner_id=owner.id,
            improvement_direction="decrease",
            target_date=date.today(),
            lifecycle="monitoring",
        )
        db_session.add(outcome)
        db_session.flush()
        delivery = WorkPackage(
            organization_id=organization.id,
            name="Deliver cost reduction",
            strategic_initiative_id=programme.id,
            programme_workstream_id=workstream.id,
            owner_id=owner.id,
            status="completed",
            materialisation_key=uuid4().hex + uuid4().hex,
        )
        db_session.add(delivery)
        db_session.flush()
        benefit = Benefit(
            organization_id=organization.id,
            name=outcome.statement,
            description=outcome.statement,
            benefit_type=None,
            status="realising",
            measure="Annual run cost",
            unit="GBP/year",
            baseline_value=baseline,
            baseline_date=date.today() - timedelta(days=365) if baseline is not None else None,
            target_value=Decimal("750.00"),
            target_date=date.today(),
            owner_id=owner.id,
            measurement_method="finance-ledger:run-cost",
            measurement_frequency="quarterly",
            strategic_initiative_id=programme.id,
            programme_workstream_id=workstream.id,
            outcome_commitment_id=outcome.id,
            work_package_id=delivery.id,
            materialisation_key=uuid4().hex + uuid4().hex,
        )
        db_session.add(benefit)
        db_session.flush()
        return OutcomeScope(
            ActorContext(owner.id, organization.id, frozenset(), uuid4().hex),
            ActorContext(delegate.id, organization.id, frozenset(), uuid4().hex),
            ActorContext(foreign.id, foreign_organization.id, frozenset(), uuid4().hex),
            benefit.id,
            organization.id,
        )

    return make


def _install_command_harness(monkeypatch, session):
    cache = {}

    def execute(**kwargs):
        key = (
            kwargs["operation"],
            kwargs["natural_key"],
            canonical_request_digest(kwargs["payload"]),
        )
        kwargs["authorizer"](
            session,
            kwargs["actor"],
            kwargs["operation"],
            kwargs["natural_key"],
        )
        if key in cache:
            prior = cache[key]
            return CommandResult(
                False,
                True,
                prior.operation_result_id,
                prior.object_ids,
                prior.response,
            )
        claim = CommandClaim(
            1, 1, "e" * 64, key[2], kwargs["natural_key"], "{}", "f" * 64
        )
        with session.begin_nested():
            mutation = kwargs["handler"](session, claim)
            session.flush()
        result = CommandResult(
            True,
            False,
            len(cache) + 1,
            mutation.object_ids,
            mutation.response,
        )
        cache[key] = result
        return result

    monkeypatch.setattr(
        "app.modules.transformation_room.outcome_service.CommandService.execute",
        execute,
    )


def test_measured_miss_appends_observation_projects_benefit_and_creates_owner_follow_up(
    db_session, monkeypatch, make_outcome_scope
):
    scope = make_outcome_scope()
    _install_command_harness(monkeypatch, db_session)
    observed_at = datetime.now(timezone.utc)

    result = OutcomeMeasurementService.record(
        actor=scope.actor,
        benefit_id=scope.benefit_id,
        value=Decimal("800.00"),
        unavailable_reason=None,
        observed_at=observed_at,
        source_identity=" Finance-Ledger:Q4-Close ",
        source_version=" v4 ",
        command_key="measure-miss",
    )
    benefit = db_session.get(Benefit, scope.benefit_id)
    measurement = db_session.get(
        OutcomeMeasurement, result.object_ids["outcome_measurement_id"]
    )
    follow_up = db_session.get(
        WorkPackage, result.object_ids["owner_follow_up_work_package_id"]
    )

    assert measurement.value == Decimal("800.000000")
    assert measurement.source_identity == "finance-ledger:Q4-Close"
    assert measurement.source_version == "v4"
    assert benefit.actual_value == Decimal("800.00")
    assert benefit.actual_date == observed_at.date()
    assert benefit.status == "not_realised"
    assert result.response["variance"] == "50"
    assert follow_up.owner_id == scope.actor.user_id
    assert follow_up.context == "outcome_follow_up"
    assert db_session.get(Benefit, scope.benefit_id) is not None


def test_unavailable_measurement_retains_null_actual_and_does_not_invent_variance(
    db_session, monkeypatch, make_outcome_scope
):
    scope = make_outcome_scope()
    _install_command_harness(monkeypatch, db_session)

    result = OutcomeMeasurementService.record(
        actor=scope.actor,
        benefit_id=scope.benefit_id,
        value=None,
        unavailable_reason="Ledger close has not completed",
        observed_at=datetime.now(timezone.utc),
        source_identity="finance-ledger:q4-close",
        source_version="v4",
        command_key="measure-unavailable",
    )
    benefit = db_session.get(Benefit, scope.benefit_id)
    measurement = db_session.get(
        OutcomeMeasurement, result.object_ids["outcome_measurement_id"]
    )

    assert measurement.value is None
    assert measurement.unavailable_reason == "Ledger close has not completed"
    assert benefit.actual_value is None and benefit.actual_date is None
    assert result.response["variance"] is None
    assert result.object_ids["owner_follow_up_work_package_id"] is None


def test_missing_baseline_keeps_comparison_and_follow_up_null(
    db_session, monkeypatch, make_outcome_scope
):
    scope = make_outcome_scope(baseline=None)
    _install_command_harness(monkeypatch, db_session)

    result = OutcomeMeasurementService.record(
        actor=scope.actor,
        benefit_id=scope.benefit_id,
        value=Decimal("800.00"),
        unavailable_reason=None,
        observed_at=datetime.now(timezone.utc),
        source_identity="finance-ledger:q4-close",
        source_version="v4",
        command_key="measure-no-baseline",
    )
    benefit = db_session.get(Benefit, scope.benefit_id)

    assert benefit.actual_value == Decimal("800.00")
    assert benefit.status == "realising"
    assert result.response["variance"] is None
    assert result.object_ids["owner_follow_up_work_package_id"] is None


@pytest.mark.parametrize(
    ("value", "reason"),
    ((None, None), (Decimal("1"), "also unavailable")),
)
def test_measurement_requires_exactly_one_fact(
    monkeypatch, db_session, make_outcome_scope, value, reason
):
    scope = make_outcome_scope()
    _install_command_harness(monkeypatch, db_session)
    with pytest.raises(ValueError, match="exactly one"):
        OutcomeMeasurementService.record(
            actor=scope.actor,
            benefit_id=scope.benefit_id,
            value=value,
            unavailable_reason=reason,
            observed_at=datetime.now(timezone.utc),
            source_identity="finance-ledger:q4-close",
            source_version="v4",
            command_key=f"invalid-{value}-{reason}",
        )


def test_delegate_can_record_but_cross_tenant_identifier_is_not_found(
    db_session, monkeypatch, make_outcome_scope
):
    scope = make_outcome_scope()
    _install_command_harness(monkeypatch, db_session)
    delegated = OutcomeMeasurementService.record(
        actor=scope.delegate_actor,
        benefit_id=scope.benefit_id,
        value=Decimal("740.00"),
        unavailable_reason=None,
        observed_at=datetime.now(timezone.utc),
        source_identity="finance-ledger:q4-close",
        source_version="v4",
        command_key="delegated-measurement",
    )
    assert delegated.object_ids["outcome_measurement_id"] is not None

    with pytest.raises(NotFound, match="benefit_not_found"):
        OutcomeMeasurementService.record(
            actor=scope.foreign_actor,
            benefit_id=scope.benefit_id,
            value=Decimal("740.00"),
            unavailable_reason=None,
            observed_at=datetime.now(timezone.utc),
            source_identity="finance-ledger:q4-close",
            source_version="v4",
            command_key="foreign-measurement",
        )


def test_follow_up_failure_rolls_back_measurement_and_projection(
    db_session, monkeypatch, make_outcome_scope
):
    scope = make_outcome_scope()
    _install_command_harness(monkeypatch, db_session)

    def fail_follow_up(*_args, **_kwargs):
        raise RuntimeError("forced follow-up failure")

    monkeypatch.setattr(
        OutcomeMeasurementService, "_create_owner_follow_up", fail_follow_up
    )
    with pytest.raises(RuntimeError, match="forced follow-up failure"):
        OutcomeMeasurementService.record(
            actor=scope.actor,
            benefit_id=scope.benefit_id,
            value=Decimal("800.00"),
            unavailable_reason=None,
            observed_at=datetime.now(timezone.utc),
            source_identity="finance-ledger:q4-close",
            source_version="v4",
            command_key="rollback-measurement",
        )

    db_session.expire_all()
    benefit = db_session.get(Benefit, scope.benefit_id)
    assert benefit.actual_value is None and benefit.status == "realising"
    assert db_session.scalar(
        select(func.count()).select_from(OutcomeMeasurement).where(
            OutcomeMeasurement.organization_id == scope.organization_id,
            OutcomeMeasurement.benefit_id == scope.benefit_id,
        )
    ) == 0


def test_measurement_rows_are_immutable_after_insert(
    db_session, monkeypatch, make_outcome_scope
):
    scope = make_outcome_scope()
    _install_command_harness(monkeypatch, db_session)
    result = OutcomeMeasurementService.record(
        actor=scope.actor,
        benefit_id=scope.benefit_id,
        value=Decimal("700.00"),
        unavailable_reason=None,
        observed_at=datetime.now(timezone.utc),
        source_identity="finance-ledger:q4-close",
        source_version="v4",
        command_key="immutable-measurement",
    )
    measurement = db_session.get(
        OutcomeMeasurement, result.object_ids["outcome_measurement_id"]
    )

    with pytest.raises(
        DBAPIError, match="outcome measurements are append-only"
    ), db_session.begin_nested():
        db_session.execute(
            text(
                "UPDATE outcome_measurements SET value = 999 "
                "WHERE id = :measurement_id AND organization_id = :organization_id"
            ),
            {
                "measurement_id": measurement.id,
                "organization_id": scope.organization_id,
            },
        )
    db_session.expire(measurement)
    with pytest.raises(
        ValueError, match="outcome measurements are append-only"
    ), db_session.begin_nested():
        measurement.value = Decimal("999.00")
        db_session.flush()
