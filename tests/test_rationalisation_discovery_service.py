"""Deterministic, evidence-citing application rationalisation discovery."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import db
from app.models.application_capability import ApplicationCapabilityMapping
from app.models.application_portfolio import ApplicationComponent
from app.models.application_rationalization import ApplicationDependency
from app.models.business_capabilities import BusinessCapability
from app.models.organization import Organization
from app.models.strategic import StrategicInitiative
from app.models.transformation_evidence import (
    CandidateSignal,
    EvidenceRequest,
    TransformationCandidate,
)
from app.models.transformation_programme import ProgrammeWorkstream
from app.models.user import User
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    DiscoveryFilters,
    NotAuthorised,
)
from app.modules.transformation_room.discovery_service import (
    RationalisationDiscoveryService,
)


@dataclass(frozen=True)
class DiscoveryScope:
    organization_id: int
    actor_id: int
    portfolio_peer_id: int
    steward_id: int
    workstream_id: int
    application_id: int
    sibling_application_id: int
    unknown_application_id: int
    dependency_id: int
    capability_id: int
    mapping_ids: tuple[int, int]
    actor: ActorContext


def _seed_scope(session, *, suffix: str, commit: bool = False) -> DiscoveryScope:
    organization = Organization(
        name=f"Discovery Org {suffix}", slug=f"discovery-{suffix}"
    )
    session.add(organization)
    session.flush()
    architect = User(
        email=f"architect-{suffix}@example.test",
        organization_id=organization.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    portfolio_peer = User(
        email=f"portfolio-peer-{suffix}@example.test",
        organization_id=organization.id,
        confirmed=True,
        enterprise_role="portfolio_manager",
    )
    steward = User(
        email=f"steward-{suffix}@example.test",
        organization_id=organization.id,
        confirmed=True,
        enterprise_role="portfolio_manager",
    )
    session.add_all((architect, portfolio_peer, steward))
    session.flush()
    target = ApplicationComponent(
        organization_id=organization.id,
        name=f"Target {suffix}",
        total_cost_of_ownership=125000.0,
        end_of_life_date=date(2027, 3, 31),
        technical_risk="high",
        business_risk="medium",
        vendor_risk="low",
        obsolescence_risk="critical",
        health_status="at_risk",
    )
    sibling = ApplicationComponent(
        organization_id=organization.id,
        name=f"Sibling {suffix}",
        total_cost_of_ownership=95000.0,
    )
    unknown = ApplicationComponent(
        organization_id=organization.id,
        name=f"Unknown {suffix}",
    )
    session.add_all((target, sibling, unknown))
    session.flush()
    capability = BusinessCapability(
        organization_id=organization.id,
        name=f"Customer servicing {suffix}",
        code=f"DISC-{suffix}",
        level=2,
    )
    session.add(capability)
    session.flush()
    target_mapping = ApplicationCapabilityMapping(
        organization_id=organization.id,
        application_component_id=target.id,
        business_capability_id=capability.id,
        coverage_percentage=80,
        is_active=True,
    )
    sibling_mapping = ApplicationCapabilityMapping(
        organization_id=organization.id,
        application_component_id=sibling.id,
        business_capability_id=capability.id,
        coverage_percentage=75,
        is_active=True,
    )
    dependency = ApplicationDependency(
        organization_id=organization.id,
        source_app_id=target.id,
        target_app_id=sibling.id,
        dependency_type="api_call",
        dependency_strength="critical",
        status="active",
    )
    programme = StrategicInitiative(
        organization_id=organization.id,
        name=f"Application rationalisation {suffix}",
        description="Reduce duplicated cost without disrupting service",
        record_kind="transformation_programme",
        status="draft",
        owner_id=architect.id,
        revision=1,
    )
    session.add_all((target_mapping, sibling_mapping, dependency, programme))
    session.flush()
    workstream = ProgrammeWorkstream(
        organization_id=organization.id,
        programme_id=programme.id,
        workstream_type="application_rationalisation",
        objective="Remove avoidable application duplication",
        scope_expression={"application_ids": [target.id, unknown.id]},
        lifecycle_stage="discover",
        lead_id=architect.id,
        revision=1,
    )
    session.add(workstream)
    session.flush()
    scope = DiscoveryScope(
        organization_id=organization.id,
        actor_id=architect.id,
        portfolio_peer_id=portfolio_peer.id,
        steward_id=steward.id,
        workstream_id=workstream.id,
        application_id=target.id,
        sibling_application_id=sibling.id,
        unknown_application_id=unknown.id,
        dependency_id=dependency.id,
        capability_id=capability.id,
        mapping_ids=(target_mapping.id, sibling_mapping.id),
        actor=ActorContext(
            architect.id,
            organization.id,
            frozenset({"forged_client_role"}),
            f"request-{suffix}",
        ),
    )
    if commit:
        session.commit()
    else:
        session.flush()
    return scope


def _discover(scope: DiscoveryScope):
    return RationalisationDiscoveryService.discover(
        actor=scope.actor,
        workstream_id=scope.workstream_id,
        filters=DiscoveryFilters(business_unit_ids=(), capability_ids=()),
    )


def test_discovery_exposes_seven_real_signals_and_writes_nothing(db_session):
    """Catches opaque scores, fabricated fallbacks, unstable order, or read-side writes."""
    scope = _seed_scope(db_session, suffix=uuid.uuid4().hex[:10])
    before = (
        db_session.scalar(select(func.count()).select_from(TransformationCandidate)),
        db_session.scalar(select(func.count()).select_from(CandidateSignal)),
    )

    discovered = _discover(scope)

    assert [item.application_id for item in discovered] == [
        scope.application_id,
        scope.unknown_application_id,
    ]
    target = discovered[0]
    assert [signal.rule_code for signal in target.signals] == [
        "capability_overlap",
        "cost",
        "end_of_life",
        "risk",
        "technical_health",
        "dependency_concentration",
        "owner_data_gaps",
    ]
    assert target.signal_digests == tuple(
        signal.content_hash for signal in target.signals
    )
    for signal in target.signals:
        assert signal.rule_version.startswith(
            RationalisationDiscoveryService.RULESET_VERSION
        )
        assert signal.evaluated_at is not None
        assert len(signal.content_hash) == 64
        assert isinstance(signal.source_record_ids, dict)
        assert isinstance(signal.observed_values, dict)

    by_rule = {signal.rule_code: signal for signal in target.signals}
    assert by_rule["capability_overlap"].observed_values == {
        "capability_ids": [scope.capability_id],
        "overlapping_application_ids": [scope.sibling_application_id],
        "overlap_count": 1,
    }
    assert set(by_rule["capability_overlap"].source_record_ids["application_capability_mapping"]) == set(
        scope.mapping_ids
    )
    assert by_rule["cost"].observed_values["total_cost_of_ownership"] == 125000.0
    assert by_rule["end_of_life"].observed_values["end_of_life_date"] == "2027-03-31"
    assert by_rule["risk"].observed_values["obsolescence_risk"] == "critical"
    assert by_rule["technical_health"].observed_values["health_status"] == "at_risk"
    assert by_rule["dependency_concentration"].source_record_ids[
        "application_dependencies"
    ] == [scope.dependency_id]
    assert by_rule["owner_data_gaps"].observed_values["owner_record_ids"] == []
    assert by_rule["owner_data_gaps"].observed_values["missing_owner"] is True
    assert db_session.scalar(select(func.count()).select_from(TransformationCandidate)) == before[0]
    assert db_session.scalar(select(func.count()).select_from(CandidateSignal)) == before[1]


def test_missing_inputs_are_named_unknowns_never_numeric_zero(db_session):
    """Catches absent inventory facts being presented as measured zeroes."""
    scope = _seed_scope(db_session, suffix=uuid.uuid4().hex[:10])

    unknown = next(
        item for item in _discover(scope) if item.application_id == scope.unknown_application_id
    )
    by_rule = {signal.rule_code: signal for signal in unknown.signals}

    assert unknown.confidence is None
    assert set(unknown.unknown_codes) >= {
        "capability_overlap_unavailable",
        "cost_unavailable",
        "end_of_life_unavailable",
        "risk_unavailable",
        "technical_health_unavailable",
        "dependency_data_unavailable",
    }
    assert by_rule["cost"].observed_values == {"total_cost_of_ownership": None}
    assert by_rule["cost"].confidence is None
    assert by_rule["dependency_concentration"].observed_values == {
        "dependency_record_ids": None,
        "dependency_count": None,
    }


@pytest.fixture
def committed_scope(app, _schema):
    """Persist prerequisites because fenced commands intentionally use new sessions."""
    suffix = uuid.uuid4().hex[:10]
    with app.app_context():
        db.session.remove()
        scope = _seed_scope(db.session, suffix=suffix, commit=True)
        previous_steward = app.config.get("TRANSFORMATION_PORTFOLIO_STEWARD_ID")
        app.config["TRANSFORMATION_PORTFOLIO_STEWARD_ID"] = scope.steward_id
        try:
            yield scope
        finally:
            if previous_steward is None:
                app.config.pop("TRANSFORMATION_PORTFOLIO_STEWARD_ID", None)
            else:
                app.config["TRANSFORMATION_PORTFOLIO_STEWARD_ID"] = previous_steward
            db.session.remove()
            with db.engine.begin() as connection:
                connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
                for table_name in (
                    "transformation_outbox_events",
                    "operation_results",
                    "command_idempotency_records",
                    "candidate_signals",
                    "evidence_requests",
                    "transformation_candidates",
                    "application_dependencies",
                    "application_capability_mapping",
                    "programme_workstreams",
                    "strategic_initiatives",
                    "application_owners",
                    "application_components",
                    "business_capability",
                    "users",
                ):
                    connection.execute(
                        text(
                            f'DELETE FROM "{table_name}" '
                            "WHERE organization_id = :organization_id"
                        ),
                        {"organization_id": scope.organization_id},
                    )
                connection.execute(
                    text("DELETE FROM organizations WHERE id = :organization_id"),
                    {"organization_id": scope.organization_id},
                )


def test_acceptance_recomputes_citations_replays_and_does_not_copy_application(
    committed_scope,
):
    """Catches duplicate inventory rows, uncited acceptance, replay duplication, or gate advance."""
    scope = committed_scope
    discovered = next(
        item for item in _discover(scope) if item.application_id == scope.application_id
    )
    with Session(db.engine) as session:
        app_count_before = session.scalar(
            select(func.count())
            .select_from(ApplicationComponent)
            .where(ApplicationComponent.organization_id == scope.organization_id)
        )

    created = RationalisationDiscoveryService.accept_candidate(
        actor=scope.actor,
        workstream_id=scope.workstream_id,
        application_id=scope.application_id,
        signal_digests=discovered.signal_digests,
        inclusion_reason="  Duplicate capability and material risk  ",
        command_key="accept-target",
    )
    replayed = RationalisationDiscoveryService.accept_candidate(
        actor=scope.actor,
        workstream_id=scope.workstream_id,
        application_id=scope.application_id,
        signal_digests=discovered.signal_digests,
        inclusion_reason="Duplicate capability and material risk",
        command_key="accept-target",
    )

    with Session(db.engine) as session:
        candidate = session.scalar(
            select(TransformationCandidate).where(
                TransformationCandidate.organization_id == scope.organization_id,
                TransformationCandidate.workstream_id == scope.workstream_id,
                TransformationCandidate.subject_type == "application",
                TransformationCandidate.subject_id == scope.application_id,
            )
        )
        signals = session.scalars(
            select(CandidateSignal)
            .where(
                CandidateSignal.organization_id == scope.organization_id,
                CandidateSignal.candidate_id == candidate.id,
            )
            .order_by(CandidateSignal.rule_code)
        ).all()
        request = session.scalar(
            select(EvidenceRequest).where(
                EvidenceRequest.organization_id == scope.organization_id,
                EvidenceRequest.candidate_id == candidate.id,
                EvidenceRequest.claim_key == "application_owner",
            )
        )
        workstream = session.scalar(
            select(ProgrammeWorkstream).where(
                ProgrammeWorkstream.organization_id == scope.organization_id,
                ProgrammeWorkstream.id == scope.workstream_id,
            )
        )
        app_count_after = session.scalar(
            select(func.count())
            .select_from(ApplicationComponent)
            .where(ApplicationComponent.organization_id == scope.organization_id)
        )

    assert created.created is True and created.idempotent is False
    assert replayed.created is False and replayed.idempotent is True
    assert replayed.operation_result_id == created.operation_result_id
    assert candidate.inclusion_reason == "Duplicate capability and material risk"
    assert {row.content_hash for row in signals} == set(discovered.signal_digests)
    assert len(signals) == 7
    assert request.required is True and request.status == "open"
    assert request.assigned_to_id == scope.steward_id
    assert workstream.lifecycle_stage == "discover" and workstream.revision == 1
    assert app_count_after == app_count_before

    with pytest.raises(CommandConflict, match="candidate_already_accepted"):
        RationalisationDiscoveryService.accept_candidate(
            actor=scope.actor,
            workstream_id=scope.workstream_id,
            application_id=scope.application_id,
            signal_digests=discovered.signal_digests,
            inclusion_reason="Same subject, second command",
            command_key="accept-target-again",
        )


def test_acceptance_rejects_stale_signal_digest(committed_scope):
    """Catches acceptance persisting facts that changed after discovery."""
    scope = committed_scope
    discovered = next(
        item for item in _discover(scope) if item.application_id == scope.application_id
    )
    with Session(db.engine) as session, session.begin():
        application = session.scalar(
            select(ApplicationComponent).where(
                ApplicationComponent.organization_id == scope.organization_id,
                ApplicationComponent.id == scope.application_id,
            )
        )
        application.total_cost_of_ownership = 130000.0

    with pytest.raises(CommandConflict, match="candidate_signals_stale"):
        RationalisationDiscoveryService.accept_candidate(
            actor=scope.actor,
            workstream_id=scope.workstream_id,
            application_id=scope.application_id,
            signal_digests=discovered.signal_digests,
            inclusion_reason="Signals must still match",
            command_key="stale-signals",
        )

    with Session(db.engine) as session:
        assert session.scalar(
            select(func.count())
            .select_from(TransformationCandidate)
            .where(TransformationCandidate.organization_id == scope.organization_id)
        ) == 0


def test_owner_request_falls_back_to_workstream_architect_without_configuration(
    app, committed_scope
):
    """Catches arbitrary portfolio users being guessed when no steward is configured."""
    scope = committed_scope
    app.config.pop("TRANSFORMATION_PORTFOLIO_STEWARD_ID", None)
    discovered = next(
        item
        for item in _discover(scope)
        if item.application_id == scope.unknown_application_id
    )

    result = RationalisationDiscoveryService.accept_candidate(
        actor=scope.actor,
        workstream_id=scope.workstream_id,
        application_id=scope.unknown_application_id,
        signal_digests=discovered.signal_digests,
        inclusion_reason="Missing source facts require governed follow-up",
        command_key="architect-owner-request",
    )

    with Session(db.engine) as session:
        request = session.scalar(
            select(EvidenceRequest).where(
                EvidenceRequest.organization_id == scope.organization_id,
                EvidenceRequest.id == result.object_ids["evidence_request_id"],
            )
        )
    assert request.assigned_to_id == scope.actor_id


def test_acceptance_replay_reauthorises_from_persisted_role(committed_scope):
    """Catches immutable command replay bypassing current candidate authority."""
    scope = committed_scope
    discovered = next(
        item for item in _discover(scope) if item.application_id == scope.application_id
    )
    RationalisationDiscoveryService.accept_candidate(
        actor=scope.actor,
        workstream_id=scope.workstream_id,
        application_id=scope.application_id,
        signal_digests=discovered.signal_digests,
        inclusion_reason="Authorised first call",
        command_key="reauthorise-replay",
    )
    with Session(db.engine) as session, session.begin():
        architect = session.scalar(
            select(User).where(
                User.organization_id == scope.organization_id,
                User.id == scope.actor_id,
            )
        )
        architect.enterprise_role = "application_manager"

    with pytest.raises(NotAuthorised, match="candidate_acceptance_not_authorised"):
        RationalisationDiscoveryService.accept_candidate(
            actor=scope.actor,
            workstream_id=scope.workstream_id,
            application_id=scope.application_id,
            signal_digests=discovered.signal_digests,
            inclusion_reason="Authorised first call",
            command_key="reauthorise-replay",
        )


def test_candidate_signal_is_database_immutable(committed_scope):
    """Catches accepted signal citations being edited after their command commits."""
    scope = committed_scope
    discovered = next(
        item for item in _discover(scope) if item.application_id == scope.application_id
    )
    result = RationalisationDiscoveryService.accept_candidate(
        actor=scope.actor,
        workstream_id=scope.workstream_id,
        application_id=scope.application_id,
        signal_digests=discovered.signal_digests,
        inclusion_reason="Freeze the discovery basis",
        command_key="immutable-signal",
    )
    signal_id = next(
        value for key, value in result.object_ids.items() if key.startswith("signal_")
    )

    with Session(db.engine) as session:
        signal = session.scalar(
            select(CandidateSignal).where(
                CandidateSignal.organization_id == scope.organization_id,
                CandidateSignal.id == signal_id,
            )
        )
        signal.payload_json = {"observed_values": {"forged": True}}
        with pytest.raises(Exception, match="append-only"):
            session.commit()
