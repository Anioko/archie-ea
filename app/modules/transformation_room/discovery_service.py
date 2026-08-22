"""Deterministic application rationalisation discovery and candidate acceptance."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from flask import current_app
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, aliased

from app import db
from app.models.application_capability import ApplicationCapabilityMapping
from app.models.application_owner import ApplicationOwner
from app.models.application_portfolio import ApplicationComponent
from app.models.application_rationalization import ApplicationDependency
from app.models.strategic import StrategicInitiative
from app.models.transformation_evidence import (
    CandidateSignal,
    EvidenceRequest,
    TransformationCandidate,
)
from app.models.transformation_programme import ProgrammeWorkstream
from app.models.user import User
from app.modules.transformation_room.command_service import (
    CommandService,
    OperationAuthorizer,
)
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    CommandResult,
    DiscoveryCandidate,
    DiscoveryFilters,
    DiscoverySignal,
    DomainMutationResult,
    NotAuthorised,
    NotFound,
)
from app.modules.transformation_room.programme_service import (
    OBJECTIVE_ROLES,
    READ_ROLES,
    TransformationProgrammeService,
)


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list, set, frozenset)):
        values = [_canonical_value(item) for item in value]
        return sorted(values) if isinstance(value, (set, frozenset)) else values
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("signal values must be finite")
    return value


def _signal_digest(
    *,
    application_id: int,
    rule_code: str,
    rule_version: str,
    source_record_ids: Mapping[str, Sequence[int]],
    observed_values: Mapping[str, Any],
    confidence: Decimal | None,
    unknown_code: str | None,
) -> str:
    """Bind the rule and source facts, not the wall-clock evaluation instant."""
    document = _canonical_value(
        {
            "application_id": application_id,
            "rule_code": rule_code,
            "rule_version": rule_version,
            "source_record_ids": source_record_ids,
            "observed_values": observed_values,
            "confidence": confidence,
            "unknown_code": unknown_code,
        }
    )
    canonical = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _SignalRule:
    code: str
    unknown_code: str

    def __init__(self, ruleset_version: str):
        self.rule_version = f"{ruleset_version}/{self.code}/1"

    def evaluate(
        self,
        actor: ActorContext,
        application: ApplicationComponent,
        *,
        session=None,
        evaluated_at: datetime | None = None,
    ) -> DiscoverySignal:
        active_session = session or db.session
        evaluated = evaluated_at or datetime.now(timezone.utc)
        sources, values, confidence, unknown = self.observe(
            active_session, actor, application, evaluated
        )
        canonical_sources = {
            key: tuple(sorted(set(record_ids)))
            for key, record_ids in sorted(sources.items())
        }
        canonical_values = _canonical_value(values)
        digest = _signal_digest(
            application_id=application.id,
            rule_code=self.code,
            rule_version=self.rule_version,
            source_record_ids=canonical_sources,
            observed_values=canonical_values,
            confidence=confidence,
            unknown_code=unknown,
        )
        return DiscoverySignal(
            rule_code=self.code,
            rule_version=self.rule_version,
            source_record_ids={key: list(ids) for key, ids in canonical_sources.items()},
            evaluated_at=evaluated,
            observed_values=canonical_values,
            confidence=confidence,
            unknown_code=unknown,
            content_hash=digest,
        )

    def observe(self, session, actor, application, evaluated_at):
        raise NotImplementedError


class _CapabilityOverlapRule(_SignalRule):
    code = "capability_overlap"
    unknown_code = "capability_overlap_unavailable"

    def observe(self, session, actor, application, evaluated_at):
        mappings = session.scalars(
            select(ApplicationCapabilityMapping).where(
                ApplicationCapabilityMapping.organization_id == actor.organization_id,
                ApplicationCapabilityMapping.application_component_id == application.id,
                ApplicationCapabilityMapping.is_active.is_(True),
            )
        ).all()
        capability_ids = sorted({row.business_capability_id for row in mappings})
        sources = {
            "application_components": [application.id],
            "application_capability_mapping": [row.id for row in mappings],
            "business_capability": capability_ids,
        }
        if not capability_ids:
            return (
                sources,
                {"capability_ids": None, "overlapping_application_ids": None, "overlap_count": None},
                None,
                self.unknown_code,
            )
        sibling_rows = session.execute(
            select(
                ApplicationCapabilityMapping.id,
                ApplicationCapabilityMapping.application_component_id,
            )
            .join(
                ApplicationComponent,
                and_(
                    ApplicationComponent.id
                    == ApplicationCapabilityMapping.application_component_id,
                    ApplicationComponent.organization_id == actor.organization_id,
                ),
            )
            .where(
                ApplicationCapabilityMapping.organization_id == actor.organization_id,
                ApplicationCapabilityMapping.application_component_id != application.id,
                ApplicationCapabilityMapping.business_capability_id.in_(capability_ids),
                ApplicationCapabilityMapping.is_active.is_(True),
                ApplicationComponent.deleted_at.is_(None),
            )
        ).all()
        sibling_ids = sorted({row.application_component_id for row in sibling_rows})
        sources["application_components"].extend(sibling_ids)
        sources["application_capability_mapping"].extend(row.id for row in sibling_rows)
        return (
            sources,
            {
                "capability_ids": capability_ids,
                "overlapping_application_ids": sibling_ids,
                "overlap_count": len(sibling_ids),
            },
            Decimal("1"),
            None,
        )


class _CostRule(_SignalRule):
    code = "cost"
    unknown_code = "cost_unavailable"

    def observe(self, session, actor, application, evaluated_at):
        del session, evaluated_at
        value = application.total_cost_of_ownership
        return (
            {"application_components": [application.id]},
            {"total_cost_of_ownership": value},
            Decimal("1") if value is not None else None,
            None if value is not None else self.unknown_code,
        )


class _EndOfLifeRule(_SignalRule):
    code = "end_of_life"
    unknown_code = "end_of_life_unavailable"

    def observe(self, session, actor, application, evaluated_at):
        del session
        value = application.end_of_life_date
        observed = {
            "end_of_life_date": value,
            "as_of_date": evaluated_at.date(),
            "days_until_end_of_life": (value - evaluated_at.date()).days
            if value is not None
            else None,
        }
        return (
            {"application_components": [application.id]},
            observed,
            Decimal("1") if value is not None else None,
            None if value is not None else self.unknown_code,
        )


class _RiskRule(_SignalRule):
    code = "risk"
    unknown_code = "risk_unavailable"
    _FIELDS = ("technical_risk", "business_risk", "vendor_risk", "obsolescence_risk")

    def observe(self, session, actor, application, evaluated_at):
        del session, evaluated_at
        values = {field: getattr(application, field) for field in self._FIELDS}
        complete = all(value is not None for value in values.values())
        return (
            {"application_components": [application.id]},
            values,
            Decimal("1") if complete else None,
            None if complete else self.unknown_code,
        )


class _TechnicalHealthRule(_SignalRule):
    code = "technical_health"
    unknown_code = "technical_health_unavailable"

    def observe(self, session, actor, application, evaluated_at):
        del session, evaluated_at
        value = application.health_status
        return (
            {"application_components": [application.id]},
            {"health_status": value},
            Decimal("1") if value is not None else None,
            None if value is not None else self.unknown_code,
        )


class _DependencyConcentrationRule(_SignalRule):
    code = "dependency_concentration"
    unknown_code = "dependency_data_unavailable"

    def observe(self, session, actor, application, evaluated_at):
        del evaluated_at
        source_application = aliased(ApplicationComponent)
        target_application = aliased(ApplicationComponent)
        dependencies = session.scalars(
            select(ApplicationDependency)
            .join(
                source_application,
                and_(
                    source_application.id == ApplicationDependency.source_app_id,
                    source_application.organization_id == actor.organization_id,
                ),
            )
            .join(
                target_application,
                and_(
                    target_application.id == ApplicationDependency.target_app_id,
                    target_application.organization_id == actor.organization_id,
                ),
            )
            .where(
                ApplicationDependency.organization_id == actor.organization_id,
                or_(
                    ApplicationDependency.source_app_id == application.id,
                    ApplicationDependency.target_app_id == application.id,
                ),
                ApplicationDependency.status != "removed",
                source_application.deleted_at.is_(None),
                target_application.deleted_at.is_(None),
            )
            .order_by(ApplicationDependency.id)
        ).all()
        if not dependencies:
            return (
                {"application_components": [application.id], "application_dependencies": []},
                {"dependency_record_ids": None, "dependency_count": None},
                None,
                self.unknown_code,
            )
        dependency_ids = [row.id for row in dependencies]
        connected_ids = sorted(
            {
                app_id
                for row in dependencies
                for app_id in (row.source_app_id, row.target_app_id)
                if app_id != application.id
            }
        )
        return (
            {
                "application_components": [application.id, *connected_ids],
                "application_dependencies": dependency_ids,
            },
            {
                "dependency_record_ids": dependency_ids,
                "dependency_count": len(dependency_ids),
                "connected_application_ids": connected_ids,
                "critical_dependency_count": sum(
                    row.dependency_strength in {"critical", "high"}
                    for row in dependencies
                ),
            },
            Decimal("1"),
            None,
        )


class _OwnerDataGapsRule(_SignalRule):
    code = "owner_data_gaps"
    unknown_code = "owner_data_gaps_unavailable"

    def observe(self, session, actor, application, evaluated_at):
        del evaluated_at
        owners = session.scalars(
            select(ApplicationOwner)
            .join(
                User,
                and_(
                    User.id == ApplicationOwner.user_id,
                    User.organization_id == actor.organization_id,
                ),
            )
            .where(
                ApplicationOwner.organization_id == actor.organization_id,
                ApplicationOwner.application_id == application.id,
            )
            .order_by(ApplicationOwner.id)
        ).all()
        legacy = {
            field: getattr(application, field)
            for field in ("application_owner", "business_owner", "technical_owner")
        }
        has_legacy_owner = any(
            isinstance(value, str) and value.strip() for value in legacy.values()
        )
        return (
            {
                "application_components": [application.id],
                "application_owners": [row.id for row in owners],
            },
            {
                "owner_record_ids": [row.id for row in owners],
                "legacy_owner_fields": legacy,
                "missing_owner": not owners and not has_legacy_owner,
            },
            Decimal("1"),
            None,
        )


class RationalisationDiscoveryService:
    """Discovers inspectable signals and accepts their recomputed citations."""

    RULESET_VERSION = "app-rationalisation-r1.1"
    ACCEPTANCE_ROLES = OBJECTIVE_ROLES

    @classmethod
    def signal_rules(cls):
        return (
            _CapabilityOverlapRule(cls.RULESET_VERSION),
            _CostRule(cls.RULESET_VERSION),
            _EndOfLifeRule(cls.RULESET_VERSION),
            _RiskRule(cls.RULESET_VERSION),
            _TechnicalHealthRule(cls.RULESET_VERSION),
            _DependencyConcentrationRule(cls.RULESET_VERSION),
            _OwnerDataGapsRule(cls.RULESET_VERSION),
        )

    @classmethod
    def discover(
        cls,
        *,
        actor: ActorContext,
        workstream_id: int,
        filters: DiscoveryFilters,
    ) -> Sequence[DiscoveryCandidate]:
        cls._validate_filters(filters)
        session = db.session
        workstream = cls.load_rationalisation_workstream(
            actor, workstream_id, session=session
        )
        applications = cls.load_scoped_applications(
            actor, workstream, filters, session=session
        )
        evaluated_at = datetime.now(timezone.utc)
        candidates = []
        for application in applications:
            signals = tuple(
                rule.evaluate(
                    actor,
                    application,
                    session=session,
                    evaluated_at=evaluated_at,
                )
                for rule in cls.signal_rules()
            )
            candidates.append(cls.to_discovery_candidate(application, signals))
        return tuple(sorted(candidates, key=lambda item: item.application_id))

    @classmethod
    def accept_candidate(
        cls,
        *,
        actor: ActorContext,
        workstream_id: int,
        application_id: int,
        signal_digests: Sequence[str],
        inclusion_reason: str,
        command_key: str,
    ) -> CommandResult:
        if not isinstance(workstream_id, int) or workstream_id <= 0:
            raise ValueError("workstream_id must be a positive integer")
        if not isinstance(application_id, int) or application_id <= 0:
            raise ValueError("application_id must be a positive integer")
        reason = inclusion_reason.strip() if isinstance(inclusion_reason, str) else ""
        if not reason:
            raise ValueError("inclusion_reason is required")
        if not isinstance(command_key, str) or not command_key.strip():
            raise ValueError("command_key is required")
        digests = tuple(sorted(signal_digests))
        if not digests or len(set(digests)) != len(digests):
            raise ValueError("signal_digests must contain unique signal hashes")
        if any(
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            for digest in digests
        ):
            raise ValueError("signal_digests must contain SHA-256 hexadecimal digests")
        request = {
            "workstream_id": workstream_id,
            "application_id": application_id,
            "signal_digests": digests,
            "inclusion_reason": reason,
        }
        return CommandService.execute(
            actor=actor,
            operation="candidate.accept",
            idempotency_key=command_key.strip(),
            payload=request,
            natural_key=f"candidate:{workstream_id}:application:{application_id}",
            authorizer=cls.authorise_candidate_acceptance(
                workstream_id, application_id
            ),
            handler=lambda session, claim: cls._accept_recomputed_candidate(
                session, actor, request, claim
            ),
        )

    @classmethod
    def load_rationalisation_workstream(
        cls, actor: ActorContext, workstream_id: int, *, session=None
    ) -> ProgrammeWorkstream:
        active_session = session or db.session
        workstream, programme = cls._load_workstream_graph(
            active_session, actor, workstream_id, lock=False
        )
        if workstream.workstream_type != "application_rationalisation":
            raise NotFound("rationalisation_workstream_not_found")
        TransformationProgrammeService._require_active_programme(programme)
        TransformationProgrammeService._require_programme_authority(
            active_session,
            actor,
            programme.id,
            workstream.id,
            READ_ROLES,
            "candidate_discovery_not_authorised",
        )
        if workstream.lifecycle_stage != "discover":
            raise CommandConflict("candidate_discovery_requires_discover_stage")
        return workstream

    @classmethod
    def load_scoped_applications(
        cls,
        actor: ActorContext,
        workstream: ProgrammeWorkstream,
        filters: DiscoveryFilters,
        *,
        session=None,
    ) -> Sequence[ApplicationComponent]:
        active_session = session or db.session
        statement = select(ApplicationComponent).where(
            ApplicationComponent.organization_id == actor.organization_id
        )
        if not filters.include_archived:
            statement = statement.where(ApplicationComponent.deleted_at.is_(None))
        scope = workstream.scope_expression if isinstance(workstream.scope_expression, Mapping) else {}
        scoped_ids = cls._positive_ids(scope.get("application_ids", ()), "scope.application_ids")
        excluded_ids = cls._positive_ids(
            scope.get("excluded_application_ids", ()), "scope.excluded_application_ids"
        )
        if scoped_ids:
            statement = statement.where(ApplicationComponent.id.in_(scoped_ids))
        if excluded_ids:
            statement = statement.where(ApplicationComponent.id.not_in(excluded_ids))
        if filters.capability_ids:
            mapped_ids = select(ApplicationCapabilityMapping.application_component_id).where(
                ApplicationCapabilityMapping.organization_id == actor.organization_id,
                ApplicationCapabilityMapping.business_capability_id.in_(filters.capability_ids),
                ApplicationCapabilityMapping.is_active.is_(True),
            )
            statement = statement.where(ApplicationComponent.id.in_(mapped_ids))
        if filters.business_unit_ids:
            owned_ids = (
                select(ApplicationOwner.application_id)
                .join(
                    User,
                    and_(
                        User.id == ApplicationOwner.user_id,
                        User.organization_id == actor.organization_id,
                    ),
                )
                .where(
                    ApplicationOwner.organization_id == actor.organization_id,
                    User.business_unit_id.in_(filters.business_unit_ids),
                )
            )
            statement = statement.where(ApplicationComponent.id.in_(owned_ids))
        return tuple(active_session.scalars(statement.order_by(ApplicationComponent.id)).all())

    @classmethod
    def to_discovery_candidate(
        cls,
        application: ApplicationComponent,
        signals: Sequence[DiscoverySignal],
    ) -> DiscoveryCandidate:
        unknown_codes = tuple(
            signal.unknown_code for signal in signals if signal.unknown_code is not None
        )
        confidence = None
        if not unknown_codes:
            confidences = [signal.confidence for signal in signals]
            confidence = sum(confidences, Decimal("0")) / Decimal(len(confidences))
        return DiscoveryCandidate(
            application_id=application.id,
            signal_digests=tuple(signal.content_hash for signal in signals),
            confidence=confidence,
            unknown_codes=unknown_codes,
            signals=tuple(signals),
        )

    @classmethod
    def authorise_candidate_acceptance(
        cls, workstream_id: int, application_id: int
    ) -> OperationAuthorizer:
        expected_key = f"candidate:{workstream_id}:application:{application_id}"

        def authorize(
            session: Session,
            actor: ActorContext,
            operation: str,
            natural_key: str,
        ) -> None:
            if operation != "candidate.accept" or natural_key != expected_key:
                raise NotAuthorised("candidate_acceptance_command_mismatch")
            workstream, programme = cls._load_workstream_graph(
                session, actor, workstream_id, lock=False
            )
            if workstream.workstream_type != "application_rationalisation":
                raise NotFound("rationalisation_workstream_not_found")
            application = cls._load_application(
                session, actor, application_id, lock=False
            )
            if not cls._is_in_workstream_scope(workstream, application.id):
                raise NotAuthorised("candidate_outside_workstream_scope")
            TransformationProgrammeService._require_active_programme(programme)
            TransformationProgrammeService._require_programme_authority(
                session,
                actor,
                programme.id,
                workstream.id,
                cls.ACCEPTANCE_ROLES,
                "candidate_acceptance_not_authorised",
            )

        return authorize

    @classmethod
    def _accept_recomputed_candidate(
        cls, session, actor, request, claim
    ) -> DomainMutationResult:
        del claim
        workstream, programme = cls._load_workstream_graph(
            session, actor, request["workstream_id"], lock=True
        )
        if workstream.workstream_type != "application_rationalisation":
            raise NotFound("rationalisation_workstream_not_found")
        TransformationProgrammeService._require_active_programme(programme)
        if workstream.lifecycle_stage != "discover":
            raise CommandConflict("candidate_acceptance_requires_discover_stage")
        application = cls._load_application(
            session, actor, request["application_id"], lock=True
        )
        if not cls._is_in_workstream_scope(workstream, application.id):
            raise NotAuthorised("candidate_outside_workstream_scope")
        existing = session.scalar(
            select(TransformationCandidate.id)
            .where(
                TransformationCandidate.organization_id == actor.organization_id,
                TransformationCandidate.workstream_id == workstream.id,
                TransformationCandidate.subject_type == "application",
                TransformationCandidate.subject_id == application.id,
            )
            .with_for_update()
        )
        if existing is not None:
            raise CommandConflict("candidate_already_accepted", candidate_id=existing)

        evaluated_at = CommandService._database_now(session)
        current_signals = tuple(
            rule.evaluate(
                actor,
                application,
                session=session,
                evaluated_at=evaluated_at,
            )
            for rule in cls.signal_rules()
        )
        current_by_digest = {signal.content_hash: signal for signal in current_signals}
        selected_digests = tuple(request["signal_digests"])
        if any(digest not in current_by_digest for digest in selected_digests):
            raise CommandConflict("candidate_signals_stale")
        selected_signals = tuple(
            signal for signal in current_signals if signal.content_hash in selected_digests
        )
        if len(selected_signals) != len(selected_digests):
            raise CommandConflict("candidate_signals_stale")

        candidate = TransformationCandidate(
            organization_id=actor.organization_id,
            workstream_id=workstream.id,
            subject_type="application",
            subject_id=application.id,
            inclusion_status="accepted",
            inclusion_reason=request["inclusion_reason"],
            accepted_by_id=actor.user_id,
            accepted_at=evaluated_at,
            revision=1,
        )
        session.add(candidate)
        session.flush()
        persisted_signals = []
        for signal in selected_signals:
            payload = {
                "observed_values": signal.observed_values,
                "confidence": str(signal.confidence)
                if signal.confidence is not None
                else None,
                "unknown_code": signal.unknown_code,
            }
            persisted = CandidateSignal(
                organization_id=actor.organization_id,
                candidate_id=candidate.id,
                rule_code=signal.rule_code,
                rule_version=signal.rule_version,
                payload_json=_canonical_value(payload),
                source_record_ids=_canonical_value(signal.source_record_ids),
                evaluated_at=signal.evaluated_at,
                content_hash=signal.content_hash,
            )
            session.add(persisted)
            persisted_signals.append(persisted)
        evidence_request = None
        if not cls._application_has_owner(session, actor, application):
            assignee_id = cls._owner_request_assignee(
                session, actor, workstream
            )
            evidence_request = EvidenceRequest(
                organization_id=actor.organization_id,
                workstream_id=workstream.id,
                candidate_id=candidate.id,
                subject_type="application",
                subject_id=application.id,
                claim_key="application_owner",
                assigned_to_id=assignee_id,
                required=True,
                status="open",
                created_by_id=actor.user_id,
                revision=1,
            )
            session.add(evidence_request)
        session.flush()

        object_ids = {"candidate_id": candidate.id}
        object_ids.update(
            {
                f"signal_{signal.rule_code}_id": signal.id
                for signal in persisted_signals
            }
        )
        if evidence_request is not None:
            object_ids["evidence_request_id"] = evidence_request.id
        response = {
            "candidate_id": candidate.id,
            "signal_ids": [signal.id for signal in persisted_signals],
            "evidence_request_id": evidence_request.id
            if evidence_request is not None
            else None,
        }
        return DomainMutationResult(
            object_ids=object_ids,
            response=response,
            outbox_events=(
                {
                    "event_type": "candidate.accepted",
                    "payload": {
                        "candidate_id": candidate.id,
                        "workstream_id": workstream.id,
                        "application_id": application.id,
                        "signal_digests": list(selected_digests),
                    },
                },
            ),
        )

    @staticmethod
    def _validate_filters(filters: DiscoveryFilters) -> None:
        if not isinstance(filters, DiscoveryFilters):
            raise TypeError("filters must be DiscoveryFilters")
        RationalisationDiscoveryService._positive_ids(
            filters.business_unit_ids, "filters.business_unit_ids"
        )
        RationalisationDiscoveryService._positive_ids(
            filters.capability_ids, "filters.capability_ids"
        )

    @staticmethod
    def _positive_ids(values, field: str) -> tuple[int, ...]:
        if values is None:
            return ()
        try:
            normalized = tuple(values)
        except TypeError as error:
            raise ValueError(f"{field} must be a sequence") from error
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in normalized
        ):
            raise ValueError(f"{field} must contain positive integers")
        return tuple(sorted(set(normalized)))

    @staticmethod
    def _load_workstream_graph(session, actor, workstream_id, *, lock):
        statement = select(ProgrammeWorkstream).where(
            ProgrammeWorkstream.id == workstream_id,
            ProgrammeWorkstream.organization_id == actor.organization_id,
        )
        if lock:
            statement = statement.with_for_update()
        workstream = session.scalar(statement)
        if workstream is None:
            raise NotFound("workstream_not_found")
        programme_statement = select(StrategicInitiative).where(
            StrategicInitiative.id == workstream.programme_id,
            StrategicInitiative.organization_id == actor.organization_id,
            StrategicInitiative.record_kind == "transformation_programme",
        )
        if lock:
            programme_statement = programme_statement.with_for_update()
        programme = session.scalar(programme_statement)
        if programme is None:
            raise NotFound("programme_not_found")
        return workstream, programme

    @staticmethod
    def _load_application(session, actor, application_id, *, lock):
        statement = select(ApplicationComponent).where(
            ApplicationComponent.id == application_id,
            ApplicationComponent.organization_id == actor.organization_id,
            ApplicationComponent.deleted_at.is_(None),
        )
        if lock:
            statement = statement.with_for_update()
        application = session.scalar(statement)
        if application is None:
            raise NotFound("application_not_found")
        return application

    @classmethod
    def _is_in_workstream_scope(cls, workstream, application_id):
        scope = workstream.scope_expression if isinstance(workstream.scope_expression, Mapping) else {}
        included = cls._positive_ids(scope.get("application_ids", ()), "scope.application_ids")
        excluded = cls._positive_ids(
            scope.get("excluded_application_ids", ()), "scope.excluded_application_ids"
        )
        return (not included or application_id in included) and application_id not in excluded

    @staticmethod
    def _application_has_owner(session, actor, application):
        owner_id = session.scalar(
            select(ApplicationOwner.id)
            .join(
                User,
                and_(
                    User.id == ApplicationOwner.user_id,
                    User.organization_id == actor.organization_id,
                ),
            )
            .where(
                ApplicationOwner.organization_id == actor.organization_id,
                ApplicationOwner.application_id == application.id,
            )
            .limit(1)
        )
        if owner_id is not None:
            return True
        return any(
            isinstance(value, str) and value.strip()
            for value in (
                application.application_owner,
                application.business_owner,
                application.technical_owner,
            )
        )

    @staticmethod
    def _owner_request_assignee(session, actor, workstream):
        configured_id = current_app.config.get(
            "TRANSFORMATION_PORTFOLIO_STEWARD_ID"
        )
        if (
            isinstance(configured_id, int)
            and not isinstance(configured_id, bool)
            and configured_id > 0
        ):
            steward_id = session.scalar(
                select(User.id).where(
                    User.organization_id == actor.organization_id,
                    User.id == configured_id,
                )
            )
            if steward_id is not None:
                return steward_id
        architect_id = session.scalar(
            select(User.id).where(
                User.organization_id == actor.organization_id,
                User.id == workstream.lead_id,
            )
        )
        if architect_id is None:
            raise CommandConflict("owner_request_assignee_unavailable")
        return architect_id


__all__ = ["RationalisationDiscoveryService"]
