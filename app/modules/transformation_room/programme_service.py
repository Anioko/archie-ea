"""Business-first Transformation Programme aggregate commands."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import db
from app.models.strategic import StrategicInitiative
from app.models.transformation_programme import (
    IMPROVEMENT_DIRECTIONS,
    ISO_4217_CURRENCIES,
    MEASURE_AGGREGATIONS,
    PROGRAMME_ROLES,
    WORKSTREAM_TYPES,
    MeasureDefinition,
    ProgrammeOutcomeCommitment,
    ProgrammeRoleAssignment,
    ProgrammeWorkstream,
)
from app.models.user import User
from app.modules.transformation_room.command_service import CommandService, OperationAuthorizer
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    CommandResult,
    DomainMutationResult,
    NotAuthorised,
    NotFound,
    ProgrammeIntake,
    ProgrammeView,
)


CREATE_ROLES = frozenset(
    {"enterprise_architect", "chief_architect", "cto", "platform_admin", "organization_admin", "administrator"}
)
OBJECTIVE_ROLES = CREATE_ROLES | frozenset({"programme_owner", "workstream_lead"})
ROLE_ASSIGNMENT_ROLES = CREATE_ROLES | frozenset({"programme_owner"})
ARCHIVE_ROLES = frozenset({"programme_owner", "platform_admin", "organization_admin", "administrator"})
READ_ROLES = CREATE_ROLES | frozenset(
    {
        "portfolio_manager",
        "business_architect",
        "application_architect",
        "arb_member",
        "programme_owner",
        "workstream_lead",
        "evidence_owner",
        "decision_authority",
        "delivery_lead",
        "outcome_owner",
        "contributor",
    }
)


def _required_text(value: Any, field: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def _optional_text(value: Any) -> str | None:
    normalized = value.strip() if isinstance(value, str) else ""
    return normalized or None


def _date(value: Any, field: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{field} must be an ISO date") from error
    raise ValueError(f"{field} must be an ISO date")


def _decimal(value: Any, field: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field} must be numeric") from error
    if not parsed.is_finite():
        raise ValueError(f"{field} must be finite")
    return parsed


def canonical_role_assignment_key(payload: Mapping[str, Any]) -> str:
    """Stable identity for one effective-dated programme role assignment."""
    identity = {
        "programme_id": payload["programme_id"],
        "workstream_id": payload.get("workstream_id"),
        "user_id": payload["user_id"],
        "role": payload["role"],
        "effective_from": payload["effective_from"],
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return f"role-assignment:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


class TransformationProgrammeService:
    """Owns programme intake and aggregate-level mutations."""

    @classmethod
    def create_programme(
        cls,
        *,
        actor: ActorContext,
        command_key: str,
        request: ProgrammeIntake,
    ) -> CommandResult:
        validated = cls.validate_intake(actor=actor, request=request)
        natural_key = f"programme-intake:{command_key}"
        return CommandService.execute(
            actor=actor,
            operation="programme.create",
            idempotency_key=command_key,
            payload=asdict(validated),
            natural_key=natural_key,
            authorizer=cls.authorise_create_programme(validated, natural_key),
            handler=lambda session, claim: cls._insert_intake_graph(
                session=session, actor=actor, request=validated, claim=claim
            ),
        )

    @classmethod
    def validate_intake(cls, *, actor: ActorContext, request: ProgrammeIntake) -> ProgrammeIntake:
        if not isinstance(request, ProgrammeIntake):
            raise TypeError("request must be ProgrammeIntake")
        name = _required_text(request.name, "name")
        objective = _required_text(request.objective, "objective")
        if request.workstream_type not in WORKSTREAM_TYPES:
            raise ValueError("workstream_type is not supported")
        if not isinstance(request.scope_expression, Mapping):
            raise ValueError("scope_expression must be an object")
        target_date = _date(request.target_date, "target_date")
        target_reason = _optional_text(request.target_date_unavailable_reason)
        if target_date is None and target_reason is None:
            raise ValueError("target_date_unavailable_reason is required when target_date is unavailable")

        outcome = dict(request.outcome) if isinstance(request.outcome, Mapping) else {}
        statement = _required_text(outcome.get("statement"), "outcome.statement")
        owner_id = outcome.get("owner_id")
        if not isinstance(request.owner_id, int) or request.owner_id <= 0:
            raise ValueError("owner_id must be a positive integer")
        if not isinstance(owner_id, int) or owner_id <= 0:
            raise ValueError("outcome.owner_id must be a positive integer")
        direction = outcome.get("direction")
        if direction not in IMPROVEMENT_DIRECTIONS:
            raise ValueError("outcome.direction is not supported")
        measure = dict(outcome.get("measure") or {})
        measure["metric_name"] = _required_text(measure.get("metric_name"), "outcome.measure.metric_name")
        measure["unit"] = _required_text(measure.get("unit"), "outcome.measure.unit")
        aggregation = measure.get("aggregation")
        if aggregation not in MEASURE_AGGREGATIONS:
            raise ValueError("outcome.measure.aggregation is not supported")
        currency = _optional_text(measure.get("currency"))
        if currency is not None:
            currency = currency.upper()
            if currency not in ISO_4217_CURRENCIES:
                raise ValueError("outcome.measure.currency must be an ISO 4217 code")
        baseline = _decimal(measure.get("baseline_value"), "outcome.measure.baseline_value")
        target = _decimal(measure.get("target_value"), "outcome.measure.target_value")
        unavailable_reason = _optional_text(measure.get("unavailable_reason"))
        if baseline is None and unavailable_reason is None:
            raise ValueError("outcome.measure.unavailable_reason is required when baseline is unavailable")
        if target is None:
            raise ValueError("outcome.measure.target_value is required")
        measure.update(
            currency=currency,
            baseline_value=baseline,
            target_value=target,
            unavailable_reason=unavailable_reason,
        )
        outcome.update(statement=statement, owner_id=owner_id, direction=direction, measure=measure)

        with Session(db.engine) as session:
            for supplied_id, field in ((request.owner_id, "owner"), (owner_id, "outcome_owner")):
                found = session.scalar(
                    select(User.id).where(
                        User.id == supplied_id,
                        User.organization_id == actor.organization_id,
                    )
                )
                if found is None:
                    raise NotFound(f"{field}_not_found")

        return replace(
            request,
            name=name,
            objective=objective,
            target_date=target_date,
            target_date_unavailable_reason=target_reason,
            scope_expression=dict(request.scope_expression),
            outcome=outcome,
        )

    @classmethod
    def authorise_create_programme(
        cls, validated: ProgrammeIntake, natural_key: str
    ) -> OperationAuthorizer:
        def authorize(session: Session, actor: ActorContext, operation: str, supplied_key: str) -> None:
            if operation != "programme.create" or supplied_key != natural_key:
                raise NotAuthorised("programme_create_command_mismatch")
            user = cls._load_runtime_user(session, actor)
            if not cls._server_roles(user).intersection(CREATE_ROLES):
                raise NotAuthorised("programme_create_not_authorised")
            owner = session.scalar(
                select(User.id).where(
                    User.id == validated.owner_id,
                    User.organization_id == actor.organization_id,
                )
            )
            if owner is None:
                raise NotFound("owner_not_found")

        return authorize

    @classmethod
    def _insert_intake_graph(cls, *, session, actor, request, claim) -> DomainMutationResult:
        outcome_data = request.outcome
        measure_data = outcome_data["measure"]
        programme = StrategicInitiative(
            organization_id=actor.organization_id,
            name=request.name,
            description=request.objective,
            record_kind="transformation_programme",
            status="draft",
            owner_id=request.owner_id,
            target_completion_date=request.target_date,
            revision=1,
        )
        workstream = ProgrammeWorkstream(
            organization_id=actor.organization_id,
            programme=programme,
            workstream_type=request.workstream_type,
            objective=request.objective,
            scope_expression=dict(request.scope_expression),
            lifecycle_stage="objective",
            lead_id=request.owner_id,
            target_date=request.target_date,
            target_date_unavailable_reason=request.target_date_unavailable_reason,
            revision=1,
        )
        assignment = ProgrammeRoleAssignment(
            organization_id=actor.organization_id,
            programme=programme,
            workstream=None,
            user_id=request.owner_id,
            role="programme_owner",
            effective_from=date.today(),
            assigned_by_id=actor.user_id,
        )
        outcome = ProgrammeOutcomeCommitment(
            organization_id=actor.organization_id,
            programme=programme,
            workstream=workstream,
            statement=outcome_data["statement"],
            owner_id=outcome_data["owner_id"],
            improvement_direction=outcome_data["direction"],
            target_date=request.target_date,
            lifecycle="committed",
        )
        measure_values = {
            "baseline_amount" if measure_data["currency"] else "baseline_value": measure_data["baseline_value"],
            "target_amount" if measure_data["currency"] else "target_value": measure_data["target_value"],
        }
        measure = MeasureDefinition(
            organization_id=actor.organization_id,
            outcome_commitment=outcome,
            metric_name=measure_data["metric_name"],
            unit=measure_data["unit"],
            currency=measure_data["currency"],
            aggregation=measure_data["aggregation"],
            unavailable_reason=measure_data["unavailable_reason"],
            target_date=request.target_date,
            **measure_values,
        )
        session.add_all([programme, assignment, workstream, outcome, measure])
        session.flush()
        object_ids = {
            "programme_id": programme.id,
            "role_assignment_id": assignment.id,
            "workstream_id": workstream.id,
            "outcome_commitment_id": outcome.id,
            "measure_definition_id": measure.id,
        }
        response = dict(object_ids)
        return DomainMutationResult(
            object_ids=object_ids,
            response=response,
            outbox_events=(
                {
                    "event_type": "programme.created",
                    "payload": {
                        **object_ids,
                        "organization_id": actor.organization_id,
                        "actor_id": actor.user_id,
                        "command_receipt_id": claim.receipt_id,
                    },
                },
            ),
        )

    @classmethod
    def assign_role(
        cls,
        *,
        actor: ActorContext,
        programme_id: int,
        workstream_id: int | None,
        user_id: int,
        role: str,
        effective_from: date,
        effective_to: date | None,
        expected_revision: int,
        command_key: str,
    ) -> CommandResult:
        if role not in PROGRAMME_ROLES:
            raise ValueError("role is not supported")
        effective_from = _date(effective_from, "effective_from")
        effective_to = _date(effective_to, "effective_to")
        if effective_to is not None and effective_to < effective_from:
            raise ValueError("effective_to must not precede effective_from")
        programme, workstream, user = cls.load_assignment_scope(
            actor=actor,
            programme_id=programme_id,
            workstream_id=workstream_id,
            user_id=user_id,
        )
        cls.authorise_role_assignment(actor, programme, workstream, role)
        payload = {
            "programme_id": programme.id,
            "workstream_id": workstream_id,
            "user_id": user.id,
            "role": role,
            "effective_from": effective_from.isoformat(),
            "effective_to": effective_to.isoformat() if effective_to else None,
            "expected_revision": expected_revision,
        }
        return CommandService.execute(
            actor=actor,
            operation="programme.assign_role",
            idempotency_key=command_key,
            payload=payload,
            natural_key=canonical_role_assignment_key(payload),
            authorizer=cls.authorise_role_assignment_replay(payload),
            handler=lambda session, claim: cls._insert_role_assignment(
                session, actor, programme, workstream, user, payload, claim
            ),
        )

    @classmethod
    def load_assignment_scope(cls, *, actor, programme_id, workstream_id, user_id):
        with Session(db.engine) as session:
            programme = cls._programme_query(session, actor, programme_id).scalar_one_or_none()
            if programme is None:
                raise NotFound("programme_not_found")
            workstream = None
            if workstream_id is not None:
                workstream = session.execute(
                    select(ProgrammeWorkstream).where(
                        ProgrammeWorkstream.id == workstream_id,
                        ProgrammeWorkstream.programme_id == programme_id,
                        ProgrammeWorkstream.organization_id == actor.organization_id,
                    )
                ).scalar_one_or_none()
                if workstream is None:
                    raise NotFound("workstream_not_found")
            user = session.execute(
                select(User).where(User.id == user_id, User.organization_id == actor.organization_id)
            ).scalar_one_or_none()
            if user is None:
                raise NotFound("user_not_found")
            session.expunge_all()
            return programme, workstream, user

    @classmethod
    def authorise_role_assignment(cls, actor, programme, workstream, role) -> None:
        with Session(db.engine) as session:
            cls._require_programme_authority(
                session,
                actor,
                programme.id,
                workstream.id if workstream else None,
                ROLE_ASSIGNMENT_ROLES,
                "role_assignment_not_authorised",
            )

    @classmethod
    def authorise_role_assignment_replay(cls, payload) -> OperationAuthorizer:
        expected_key = canonical_role_assignment_key(payload)

        def authorize(session, actor, operation, natural_key):
            if operation != "programme.assign_role" or natural_key != expected_key:
                raise NotAuthorised("role_assignment_command_mismatch")
            programme = cls._programme_query(session, actor, payload["programme_id"]).scalar_one_or_none()
            if programme is None:
                raise NotFound("programme_not_found")
            cls._require_active_programme(programme)
            workstream_id = payload.get("workstream_id")
            if workstream_id is not None:
                workstream = session.scalar(
                    select(ProgrammeWorkstream.id).where(
                        ProgrammeWorkstream.id == workstream_id,
                        ProgrammeWorkstream.programme_id == programme.id,
                        ProgrammeWorkstream.organization_id == actor.organization_id,
                    )
                )
                if workstream is None:
                    raise NotFound("workstream_not_found")
            assigned_user = session.scalar(
                select(User.id).where(
                    User.id == payload["user_id"],
                    User.organization_id == actor.organization_id,
                )
            )
            if assigned_user is None:
                raise NotFound("user_not_found")
            cls._require_programme_authority(
                session,
                actor,
                programme.id,
                workstream_id,
                ROLE_ASSIGNMENT_ROLES,
                "role_assignment_not_authorised",
            )

        return authorize

    @classmethod
    def _insert_role_assignment(cls, session, actor, programme, workstream, user, payload, claim):
        locked_programme = cls._programme_query(
            session, actor, payload["programme_id"], lock=True
        ).scalar_one_or_none()
        if locked_programme is None:
            raise NotFound("programme_not_found")
        cls._require_active_programme(locked_programme)
        locked_stream = None
        if payload["workstream_id"] is not None:
            locked_stream = session.execute(
                select(ProgrammeWorkstream).where(
                    ProgrammeWorkstream.id == payload["workstream_id"],
                    ProgrammeWorkstream.programme_id == payload["programme_id"],
                    ProgrammeWorkstream.organization_id == actor.organization_id,
                ).with_for_update()
            ).scalar_one_or_none()
            if locked_stream is None:
                raise NotFound("workstream_not_found")
            if locked_stream.revision != payload["expected_revision"]:
                raise CommandConflict("stale_revision")
            aggregate = locked_stream
            aggregate_type = "workstream"
        else:
            if locked_programme.revision != payload["expected_revision"]:
                raise CommandConflict("stale_revision")
            aggregate = locked_programme
            aggregate_type = "programme"
        cls._require_programme_authority(
            session,
            actor,
            payload["programme_id"],
            payload["workstream_id"],
            ROLE_ASSIGNMENT_ROLES,
            "role_assignment_not_authorised",
        )
        assignment = ProgrammeRoleAssignment(
            organization_id=actor.organization_id,
            programme_id=payload["programme_id"],
            workstream_id=payload["workstream_id"],
            user_id=payload["user_id"],
            role=payload["role"],
            effective_from=date.fromisoformat(payload["effective_from"]),
            effective_to=date.fromisoformat(payload["effective_to"]) if payload["effective_to"] else None,
            assigned_by_id=actor.user_id,
        )
        session.add(assignment)
        aggregate.revision += 1
        session.flush()
        response = {
            "role_assignment_id": assignment.id,
            "revision": aggregate.revision,
            "aggregate_type": aggregate_type,
        }
        return DomainMutationResult(
            response,
            response,
            ({"event_type": "programme.role_assigned", "payload": {**response, "programme_id": payload["programme_id"]}},),
        )

    @classmethod
    def update_objective(
        cls,
        *,
        actor: ActorContext,
        workstream_id: int,
        objective: str,
        scope_expression: Mapping[str, Any],
        expected_revision: int,
        command_key: str,
    ) -> CommandResult:
        objective = _required_text(objective, "objective")
        if not isinstance(scope_expression, Mapping):
            raise ValueError("scope_expression must be an object")
        payload = {
            "workstream_id": workstream_id,
            "objective": objective,
            "scope_expression": dict(scope_expression),
            "expected_revision": expected_revision,
        }
        return CommandService.execute(
            actor=actor,
            operation="workstream.update_objective",
            idempotency_key=command_key,
            payload=payload,
            natural_key=f"objective:{workstream_id}:{expected_revision}",
            authorizer=cls.authorise_objective_update(workstream_id, expected_revision),
            handler=lambda session, claim: cls._update_objective_locked(session, actor, payload, claim),
        )

    @classmethod
    def authorise_objective_update(cls, workstream_id, expected_revision) -> OperationAuthorizer:
        expected_key = f"objective:{workstream_id}:{expected_revision}"

        def authorize(session, actor, operation, natural_key):
            if operation != "workstream.update_objective" or natural_key != expected_key:
                raise NotAuthorised("objective_update_command_mismatch")
            stream = session.execute(
                select(ProgrammeWorkstream).where(
                    ProgrammeWorkstream.id == workstream_id,
                    ProgrammeWorkstream.organization_id == actor.organization_id,
                )
            ).scalar_one_or_none()
            if stream is None:
                raise NotFound("workstream_not_found")
            programme = cls._programme_query(session, actor, stream.programme_id).scalar_one_or_none()
            if programme is None:
                raise NotFound("programme_not_found")
            cls._require_active_programme(programme)
            cls._require_programme_authority(
                session, actor, stream.programme_id, stream.id, OBJECTIVE_ROLES, "objective_update_not_authorised"
            )

        return authorize

    @classmethod
    def _update_objective_locked(cls, session, actor, payload, claim):
        stream_scope = session.execute(
            select(ProgrammeWorkstream).where(
                ProgrammeWorkstream.id == payload["workstream_id"],
                ProgrammeWorkstream.organization_id == actor.organization_id,
            )
        ).scalar_one_or_none()
        if stream_scope is None:
            raise NotFound("workstream_not_found")
        programme = cls._programme_query(
            session, actor, stream_scope.programme_id, lock=True
        ).scalar_one_or_none()
        if programme is None:
            raise NotFound("programme_not_found")
        cls._require_active_programme(programme)
        stream = session.execute(
            select(ProgrammeWorkstream).where(
                ProgrammeWorkstream.id == payload["workstream_id"],
                ProgrammeWorkstream.programme_id == programme.id,
                ProgrammeWorkstream.organization_id == actor.organization_id,
            ).with_for_update()
        ).scalar_one()
        if stream.revision != payload["expected_revision"]:
            raise CommandConflict("stale_revision")
        cls._require_programme_authority(
            session, actor, stream.programme_id, stream.id, OBJECTIVE_ROLES, "objective_update_not_authorised"
        )
        before_revision = stream.revision
        stream.objective = payload["objective"]
        stream.scope_expression = dict(payload["scope_expression"])
        stream.revision += 1
        session.flush()
        response = {"workstream_id": stream.id, "revision": stream.revision}
        return DomainMutationResult(
            response,
            response,
            ({"event_type": "workstream.objective_updated", "payload": {**response, "before_revision": before_revision}},),
        )

    @classmethod
    def archive(
        cls,
        *,
        actor: ActorContext,
        programme_id: int,
        expected_revision: int,
        command_key: str,
    ) -> CommandResult:
        payload = {"programme_id": programme_id, "expected_revision": expected_revision}
        return CommandService.execute(
            actor=actor,
            operation="programme.archive",
            idempotency_key=command_key,
            payload=payload,
            natural_key=f"programme-archive:{programme_id}:{expected_revision}",
            authorizer=cls.authorise_programme_archive(programme_id, expected_revision),
            handler=lambda session, claim: cls._archive_locked(session, actor, payload, claim),
        )

    @classmethod
    def authorise_programme_archive(cls, programme_id, expected_revision) -> OperationAuthorizer:
        expected_key = f"programme-archive:{programme_id}:{expected_revision}"

        def authorize(session, actor, operation, natural_key):
            if operation != "programme.archive" or natural_key != expected_key:
                raise NotAuthorised("programme_archive_command_mismatch")
            programme = cls._programme_query(session, actor, programme_id).scalar_one_or_none()
            if programme is None:
                raise NotFound("programme_not_found")
            cls._require_programme_authority(
                session, actor, programme_id, None, ARCHIVE_ROLES, "programme_archive_not_authorised"
            )

        return authorize

    @classmethod
    def _archive_locked(cls, session, actor, payload, claim):
        programme = cls._programme_query(session, actor, payload["programme_id"], lock=True).scalar_one_or_none()
        if programme is None:
            raise NotFound("programme_not_found")
        if programme.revision != payload["expected_revision"]:
            raise CommandConflict("stale_revision")
        cls._require_programme_authority(
            session, actor, programme.id, None, ARCHIVE_ROLES, "programme_archive_not_authorised"
        )
        if programme.status == "archived":
            raise CommandConflict("programme_already_archived")
        programme.status = "archived"
        programme.archived_at = datetime.now(timezone.utc)
        programme.revision += 1
        session.flush()
        response = {"programme_id": programme.id, "status": programme.status, "revision": programme.revision}
        return DomainMutationResult(
            response,
            response,
            ({"event_type": "programme.archived", "payload": response},),
        )

    @classmethod
    def get_programme(cls, *, actor: ActorContext, programme_id: int) -> ProgrammeView:
        programme = cls.load_programme_for_tenant(actor, programme_id)
        cls.authorise_read(actor, programme)
        workstreams = cls.load_workstreams_for_tenant(actor, programme.id)
        from app.modules.transformation_room.gate_service import TransformationGateService

        next_action = None
        if programme.status != "archived" and programme.archived_at is None:
            next_action = TransformationGateService.next_action(actor=actor, workstreams=workstreams)
        return ProgrammeView(
            programme.id,
            tuple(row.id for row in workstreams),
            programme.status,
            programme.owner_id,
            next_action,
        )

    @classmethod
    def load_programme_for_tenant(cls, actor, programme_id):
        with Session(db.engine) as session:
            programme = cls._programme_query(session, actor, programme_id).scalar_one_or_none()
            if programme is None:
                raise NotFound("programme_not_found")
            session.expunge(programme)
            return programme

    @classmethod
    def load_workstreams_for_tenant(cls, actor, programme_id):
        with Session(db.engine) as session:
            rows = session.scalars(
                select(ProgrammeWorkstream)
                .where(
                    ProgrammeWorkstream.programme_id == programme_id,
                    ProgrammeWorkstream.organization_id == actor.organization_id,
                )
                .order_by(ProgrammeWorkstream.id)
            ).all()
            session.expunge_all()
            return rows

    @classmethod
    def authorise_read(cls, actor, programme):
        with Session(db.engine) as session:
            persisted = cls._programme_query(session, actor, programme.id).scalar_one_or_none()
            if persisted is None:
                raise NotFound("programme_not_found")
            cls._require_programme_authority(
                session,
                actor,
                persisted.id,
                None,
                READ_ROLES,
                "programme_read_not_authorised",
            )

    @staticmethod
    def _require_active_programme(programme) -> None:
        if programme.status == "archived" or programme.archived_at is not None:
            raise CommandConflict("programme_archived")

    @staticmethod
    def _programme_query(session, actor, programme_id, lock=False):
        statement = select(StrategicInitiative).where(
            StrategicInitiative.id == programme_id,
            StrategicInitiative.organization_id == actor.organization_id,
            StrategicInitiative.record_kind == "transformation_programme",
        )
        if lock:
            statement = statement.with_for_update()
        return session.execute(statement)

    @staticmethod
    def _load_runtime_user(session, actor):
        user = session.execute(
            select(User).where(
                User.id == actor.user_id,
                User.organization_id == actor.organization_id,
            )
        ).scalar_one_or_none()
        if user is None:
            raise NotAuthorised("actor_not_authorised")
        return user

    @staticmethod
    def _server_roles(user) -> set[str]:
        roles = {user.enterprise_role} if user.enterprise_role else set()
        if user.is_org_admin:
            roles.add("organization_admin")
        if user.is_platform_admin:
            roles.add("platform_admin")
        try:
            if user.role and user.role.name:
                roles.add(user.role.name.strip().lower())
        except Exception:
            pass
        return roles

    @classmethod
    def _require_programme_authority(
        cls,
        session,
        actor,
        programme_id,
        workstream_id,
        allowed_roles,
        denial_reason,
    ):
        user = cls._load_runtime_user(session, actor)
        roles = cls._server_roles(user)
        today = date.today()
        assigned = session.scalars(
            select(ProgrammeRoleAssignment.role).where(
                ProgrammeRoleAssignment.organization_id == actor.organization_id,
                ProgrammeRoleAssignment.programme_id == programme_id,
                or_(
                    ProgrammeRoleAssignment.workstream_id.is_(None),
                    ProgrammeRoleAssignment.workstream_id == workstream_id,
                ),
                ProgrammeRoleAssignment.user_id == actor.user_id,
                ProgrammeRoleAssignment.effective_from <= today,
                or_(
                    ProgrammeRoleAssignment.effective_to.is_(None),
                    ProgrammeRoleAssignment.effective_to >= today,
                ),
            )
        ).all()
        roles.update(assigned)
        if not roles.intersection(allowed_roles):
            raise NotAuthorised(denial_reason)


__all__ = ["TransformationProgrammeService", "canonical_role_assignment_key"]
