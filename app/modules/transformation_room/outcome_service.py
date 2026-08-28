"""Append-only outcome observations and compatible Benefit projections."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
import unicodedata

from sqlalchemy import or_, select

from app import db
from app.models.benefit import Benefit
from app.models.transformation_execution import OutcomeMeasurement
from app.models.transformation_programme import (
    ProgrammeOutcomeCommitment,
    ProgrammeRoleAssignment,
)
from app.models.user import User
from app.modules.solutions_strategic.v2.services.strategic_service import StrategicService
from app.modules.transformation_room.command_service import (
    CommandService,
    OperationAuthorizer,
    canonical_request_digest,
)
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    CommandResult,
    DomainMutationResult,
    NotAuthorised,
    NotFound,
)


def _positive_id(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _required_text(value: Any, field: str, limit: int) -> str:
    normalized = (
        unicodedata.normalize("NFC", value).strip() if isinstance(value, str) else ""
    )
    if (
        not normalized
        or len(normalized) > limit
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise ValueError(f"invalid {field}")
    return normalized


def _source_identity(value: Any) -> str:
    identity = _required_text(value, "source_identity", 512)
    prefix, separator, opaque = identity.partition(":")
    if not separator:
        return identity.casefold()
    prefix = prefix.strip().casefold()
    opaque = opaque.strip()
    if not prefix or not opaque:
        raise ValueError("invalid source_identity")
    return f"{prefix}:{opaque}"


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("value must use Decimal or an exact decimal string")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("value must be numeric") from error
    if not parsed.is_finite():
        raise ValueError("value must be finite")
    return parsed


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return "0" if normalized == 0 else format(normalized, "f")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    return value.astimezone(timezone.utc)


class OutcomeMeasurementService:
    """Record facts without deleting a missed or unavailable promised outcome."""

    OPERATION = "outcome.measure"

    @classmethod
    def record(
        cls,
        *,
        actor: ActorContext,
        benefit_id: int,
        value: Decimal | None,
        unavailable_reason: str | None,
        observed_at: datetime,
        source_identity: str,
        source_version: str,
        command_key: str,
    ) -> CommandResult:
        command_key = _required_text(command_key, "command_key", 255)
        request = cls.validate_measurement(
            actor,
            benefit_id,
            value,
            unavailable_reason,
            observed_at,
            source_identity,
            source_version,
        )
        natural_key = (
            f"measurement:{benefit_id}:{request['source_identity']}:"
            f"{request['observed_at']}:{request['source_version']}"
        )
        return CommandService.execute(
            actor=actor,
            operation=cls.OPERATION,
            idempotency_key=command_key,
            payload=request,
            natural_key=natural_key,
            authorizer=cls.authorise_measurement(
                benefit_id,
                request["source_identity"],
                datetime.fromisoformat(request["observed_at"]),
                request["source_version"],
            ),
            natural_key_resolver=CommandService.fail_closed_pre_envelope_recovery,
            handler=lambda session, claim: cls._append_measurement_and_project(
                session, actor, request, claim
            ),
        )

    @classmethod
    def validate_measurement(
        cls,
        actor,
        benefit_id,
        value,
        unavailable_reason,
        observed_at,
        source_identity,
        source_version,
    ):
        if not isinstance(actor, ActorContext):
            raise TypeError("actor must be ActorContext")
        benefit_id = _positive_id(benefit_id, "benefit_id")
        has_value = value is not None
        has_reason = unavailable_reason is not None
        if has_value == has_reason:
            raise ValueError("exactly one of value or unavailable_reason is required")
        parsed_value = _decimal(value) if has_value else None
        reason = (
            _required_text(unavailable_reason, "unavailable_reason", 4000)
            if has_reason
            else None
        )
        observed = _utc(observed_at)
        identity = _source_identity(source_identity)
        version = _required_text(source_version, "source_version", 255)
        benefit = cls._load_benefit(db.session, actor, benefit_id, lock=False)
        cls._require_measurement_authority(
            db.session, actor, benefit, lock=False
        )
        return {
            "benefit_id": benefit_id,
            "value": _decimal_text(parsed_value) if parsed_value is not None else None,
            "unavailable_reason": reason,
            "observed_at": observed.isoformat(),
            "source_identity": identity,
            "source_version": version,
        }

    @classmethod
    def authorise_measurement(
        cls,
        benefit_id: int,
        source_identity: str,
        observed_at: datetime,
        source_version: str,
    ) -> OperationAuthorizer:
        expected_key = (
            f"measurement:{benefit_id}:{source_identity}:"
            f"{_utc(observed_at).isoformat()}:{source_version}"
        )

        def authorize(session, actor, operation, natural_key):
            if operation != cls.OPERATION or natural_key != expected_key:
                raise NotAuthorised("outcome_measurement_command_mismatch")
            benefit = cls._load_benefit(
                session, actor, benefit_id, lock=False
            )
            cls._require_measurement_authority(
                session, actor, benefit, lock=False
            )

        return authorize

    @classmethod
    def _append_measurement_and_project(cls, session, actor, request, _claim):
        benefit = cls._load_benefit(
            session, actor, request["benefit_id"], lock=True
        )
        cls._require_measurement_authority(session, actor, benefit, lock=True)
        if benefit.owner_id is None:
            raise CommandConflict("benefit_owner_required")
        observed_at = datetime.fromisoformat(request["observed_at"])
        duplicate = session.scalar(
            select(OutcomeMeasurement.id).where(
                OutcomeMeasurement.organization_id == actor.organization_id,
                OutcomeMeasurement.benefit_id == benefit.id,
                OutcomeMeasurement.source_identity == request["source_identity"],
                OutcomeMeasurement.source_version == request["source_version"],
                OutcomeMeasurement.observed_at == observed_at,
            )
        )
        if duplicate is not None:
            raise CommandConflict("outcome_measurement_already_recorded")
        value = Decimal(request["value"]) if request["value"] is not None else None
        measurement = OutcomeMeasurement(
            organization_id=actor.organization_id,
            benefit_id=benefit.id,
            value=value,
            unavailable_reason=request["unavailable_reason"],
            observed_at=observed_at,
            source_identity=request["source_identity"],
            source_version=request["source_version"],
            recorded_by_id=actor.user_id,
        )
        session.add(measurement)
        session.flush()

        variance = None
        missed = False
        realised = False
        if value is not None:
            benefit.actual_value = value
            benefit.actual_date = observed_at.date()
            if cls._is_comparable(benefit):
                target = Decimal(str(benefit.target_value))
                baseline = Decimal(str(benefit.baseline_value))
                variance = value - target
                if target > baseline:
                    realised = value >= target
                elif target < baseline:
                    realised = value <= target
                else:
                    realised = value == target
                missed = not realised
                benefit.status = "realised" if realised else "not_realised"
            else:
                benefit.status = "realising"
        session.flush()

        outcome = cls._lock_outcome(session, actor, benefit)
        if outcome is not None:
            if missed:
                outcome.lifecycle = "not_realised"
            elif realised:
                outcome.lifecycle = "realised"
            elif value is not None:
                outcome.lifecycle = "monitoring"
        follow_up = (
            cls._create_owner_follow_up(
                session, actor, benefit, measurement, value, variance
            )
            if missed
            else None
        )
        session.flush()
        object_ids = {
            "benefit_id": benefit.id,
            "outcome_measurement_id": measurement.id,
            "owner_follow_up_work_package_id": follow_up.id if follow_up else None,
        }
        response = {
            **object_ids,
            "actual_value": _decimal_text(value) if value is not None else None,
            "actual_date": benefit.actual_date.isoformat()
            if benefit.actual_date
            else None,
            "status": benefit.status,
            "variance": _decimal_text(variance) if variance is not None else None,
            "unit": benefit.unit if variance is not None else None,
        }
        return DomainMutationResult(
            object_ids,
            response,
            (
                {
                    "event_type": "transformation.outcome_measured",
                    "payload": response,
                },
            ),
        )

    @staticmethod
    def _is_comparable(benefit):
        return bool(
            benefit.unit
            and benefit.baseline_value is not None
            and benefit.target_value is not None
        )

    @classmethod
    def _create_owner_follow_up(
        cls, session, actor, benefit, measurement, value, variance
    ):
        key = canonical_request_digest(
            {
                "organization_id": actor.organization_id,
                "benefit_id": benefit.id,
                "measurement_id": measurement.id,
                "purpose": "outcome_owner_follow_up",
            }
        )
        measure_name = benefit.measure or benefit.name
        description = (
            f"Measured {measure_name}: {_decimal_text(value)} {benefit.unit}; "
            f"target: {_decimal_text(Decimal(str(benefit.target_value)))} "
            f"{benefit.unit}; variance: {_decimal_text(variance)} {benefit.unit}."
        )
        return StrategicService.create_transformation_work_package(
            session,
            organization_id=actor.organization_id,
            programme_id=benefit.strategic_initiative_id,
            workstream_id=benefit.programme_workstream_id,
            decision_brief_version_id=benefit.decision_brief_version_id,
            materialisation_key=key,
            name=_required_text(
                f"Outcome review: {benefit.name}"[:100], "follow-up name", 100
            ),
            description=description,
            owner_id=benefit.owner_id,
            start_date=date.today(),
            target_date=None,
            dependencies=(benefit.work_package_id,)
            if benefit.work_package_id is not None
            else (),
            context="outcome_follow_up",
            provenance={
                "source": "outcome_measurement",
                "benefit_id": benefit.id,
                "outcome_measurement_id": measurement.id,
            },
        )

    @staticmethod
    def _lock_outcome(session, actor, benefit):
        if benefit.outcome_commitment_id is None:
            return None
        return session.scalar(
            select(ProgrammeOutcomeCommitment)
            .where(
                ProgrammeOutcomeCommitment.id == benefit.outcome_commitment_id,
                ProgrammeOutcomeCommitment.organization_id == actor.organization_id,
                ProgrammeOutcomeCommitment.programme_id
                == benefit.strategic_initiative_id,
                or_(
                    ProgrammeOutcomeCommitment.workstream_id
                    == benefit.programme_workstream_id,
                    ProgrammeOutcomeCommitment.workstream_id.is_(None),
                ),
            )
            .with_for_update()
        )

    @staticmethod
    def _load_benefit(session, actor, benefit_id, *, lock):
        statement = select(Benefit).where(
            Benefit.id == benefit_id,
            Benefit.organization_id == actor.organization_id,
        )
        if lock:
            statement = statement.execution_options(
                populate_existing=True
            ).with_for_update()
        row = session.scalar(statement)
        if row is None:
            raise NotFound("benefit_not_found")
        return row

    @classmethod
    def _require_measurement_authority(
        cls, session, actor, benefit, *, lock
    ):
        user_statement = select(User).where(
            User.id == actor.user_id,
            User.organization_id == actor.organization_id,
        )
        if lock:
            user_statement = user_statement.with_for_update()
        user = session.scalar(user_statement)
        if user is None:
            raise NotAuthorised("outcome_measurement_not_authorised")
        if benefit.owner_id == actor.user_id:
            return
        if (
            benefit.strategic_initiative_id is None
            or benefit.programme_workstream_id is None
        ):
            raise NotAuthorised("outcome_measurement_not_authorised")
        today = date.today()
        statement = select(ProgrammeRoleAssignment).where(
            ProgrammeRoleAssignment.organization_id == actor.organization_id,
            ProgrammeRoleAssignment.programme_id
            == benefit.strategic_initiative_id,
            or_(
                ProgrammeRoleAssignment.workstream_id.is_(None),
                ProgrammeRoleAssignment.workstream_id
                == benefit.programme_workstream_id,
            ),
            ProgrammeRoleAssignment.user_id == actor.user_id,
            ProgrammeRoleAssignment.role == "outcome_owner",
            ProgrammeRoleAssignment.effective_from <= today,
            or_(
                ProgrammeRoleAssignment.effective_to.is_(None),
                ProgrammeRoleAssignment.effective_to >= today,
            ),
        )
        if lock:
            statement = statement.execution_options(
                populate_existing=True
            ).with_for_update()
        if session.scalar(statement) is None:
            raise NotAuthorised("outcome_measurement_not_authorised")


__all__ = ["OutcomeMeasurementService"]
