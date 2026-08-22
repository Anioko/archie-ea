"""Business-first Transformation Programme service contracts."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app import db
from app.models.organization import Organization
from app.models.solution_models import Solution
from app.models.strategic import StrategicInitiative
from app.models.transformation_execution import OperationOutboxEvent
from app.models.transformation_programme import (
    MeasureDefinition,
    ProgrammeOutcomeCommitment,
    ProgrammeRoleAssignment,
    ProgrammeWorkstream,
)
from app.models.user import User
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    NotAuthorised,
    NotFound,
    ProgrammeIntake,
)
from app.modules.transformation_room.programme_service import TransformationProgrammeService


@dataclass(frozen=True)
class ProgrammeFixture:
    organization_id: int
    foreign_organization_id: int
    owner_id: int
    foreign_owner_id: int
    actor: ActorContext


@pytest.fixture(scope="module", autouse=True)
def transformation_schema(app, _schema):
    from app.commands.reconcile_schema import _reconcile

    with app.app_context():
        _added, failed, _missing, _blocking = _reconcile(dry_run=False)
        assert failed == []


@pytest.fixture
def programme_fixture(app, _schema):
    suffix = uuid.uuid4().hex[:12]
    with app.app_context():
        db.session.remove()
        organization = Organization(name=f"Programme Org {suffix}", slug=f"programme-{suffix}")
        foreign = Organization(name=f"Foreign Org {suffix}", slug=f"foreign-{suffix}")
        db.session.add_all([organization, foreign])
        db.session.flush()
        owner = User(
            email=f"architect-{suffix}@example.test",
            organization_id=organization.id,
            confirmed=True,
            enterprise_role="enterprise_architect",
        )
        foreign_owner = User(
            email=f"foreign-{suffix}@example.test",
            organization_id=foreign.id,
            confirmed=True,
            enterprise_role="enterprise_architect",
        )
        db.session.add_all([owner, foreign_owner])
        db.session.flush()
        fixture = ProgrammeFixture(
            organization.id,
            foreign.id,
            owner.id,
            foreign_owner.id,
            ActorContext(owner.id, organization.id, frozenset({"forged_role"}), f"request-{suffix}"),
        )
        db.session.commit()
        db.session.remove()
        try:
            yield fixture
        finally:
            db.session.remove()
            with db.engine.begin() as connection:
                connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
                for table_name in (
                    "transformation_outbox_events",
                    "operation_results",
                    "command_idempotency_records",
                    "measure_definitions",
                    "programme_outcome_commitments",
                    "programme_role_assignments",
                    "programme_workstreams",
                    "solutions",
                    "strategic_initiatives",
                    "users",
                ):
                    connection.execute(
                        text(f'DELETE FROM "{table_name}" WHERE organization_id IN (:org, :foreign)'),
                        {"org": fixture.organization_id, "foreign": fixture.foreign_organization_id},
                    )
                connection.execute(
                    text("DELETE FROM organizations WHERE id IN (:org, :foreign)"),
                    {"org": fixture.organization_id, "foreign": fixture.foreign_organization_id},
                )


def _intake(owner_id: int, **changes) -> ProgrammeIntake:
    values = {
        "name": "Simplify the application estate",
        "objective": "Reduce duplicated capability cost without service loss",
        "owner_id": owner_id,
        "target_date": date(2027, 6, 30),
        "target_date_unavailable_reason": None,
        "workstream_type": "application_rationalisation",
        "scope_expression": {"business_units": ["Retail"]},
        "outcome": {
            "statement": "Reduce annual run cost",
            "owner_id": owner_id,
            "direction": "decrease",
            "measure": {
                "metric_name": "Annual run cost",
                "unit": "GBP",
                "currency": "GBP",
                "aggregation": "sum",
                "baseline_value": None,
                "unavailable_reason": "Finance baseline requested",
                "target_value": "900000.00",
            },
        },
    }
    values.update(changes)
    return ProgrammeIntake(**values)


def _rows(fixture: ProgrammeFixture):
    with Session(db.engine) as session:
        programme = session.execute(
            select(StrategicInitiative).where(
                StrategicInitiative.organization_id == fixture.organization_id,
                StrategicInitiative.record_kind == "transformation_programme",
            )
        ).scalar_one_or_none()
        return {
            "programme": programme,
            "workstreams": session.scalars(
                select(ProgrammeWorkstream).where(
                    ProgrammeWorkstream.organization_id == fixture.organization_id
                )
            ).all(),
            "roles": session.scalars(
                select(ProgrammeRoleAssignment).where(
                    ProgrammeRoleAssignment.organization_id == fixture.organization_id
                )
            ).all(),
            "outcomes": session.scalars(
                select(ProgrammeOutcomeCommitment).where(
                    ProgrammeOutcomeCommitment.organization_id == fixture.organization_id
                )
            ).all(),
            "measures": session.scalars(
                select(MeasureDefinition).where(
                    MeasureDefinition.organization_id == fixture.organization_id
                )
            ).all(),
            "solutions": session.scalar(
                select(db.func.count()).select_from(Solution).where(
                    Solution.organization_id == fixture.organization_id
                )
            ),
            "events": session.scalars(
                select(OperationOutboxEvent).where(
                    OperationOutboxEvent.organization_id == fixture.organization_id
                )
            ).all(),
        }


def test_create_programme_persists_one_business_graph_and_replays_exactly(programme_fixture):
    """Catches business intake creating a Solution, duplicate graph, or lossy result envelope."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="business-intake",
        request=_intake(programme_fixture.owner_id),
    )
    replayed = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="business-intake",
        request=_intake(programme_fixture.owner_id),
    )

    rows = _rows(programme_fixture)
    assert created.created is True and created.idempotent is False
    assert replayed.created is False and replayed.idempotent is True
    assert replayed.operation_result_id == created.operation_result_id
    assert replayed.object_ids == created.object_ids
    assert set(created.object_ids) >= {
        "programme_id", "workstream_id", "outcome_commitment_id", "measure_definition_id"
    }
    assert rows["programme"].record_kind == "transformation_programme"
    assert rows["programme"].owner_id == programme_fixture.owner_id
    assert len(rows["workstreams"]) == len(rows["roles"]) == len(rows["outcomes"]) == len(rows["measures"]) == 1
    assert rows["workstreams"][0].lead_id == programme_fixture.owner_id
    assert rows["roles"][0].role == "programme_owner"
    assert rows["measures"][0].baseline_amount is None
    assert str(rows["measures"][0].target_amount) == "900000.00"
    assert rows["solutions"] == 0
    assert len(rows["events"]) == 1
    assert rows["events"][0].event_type == "programme.created"


def test_create_programme_requires_persisted_server_role_not_actor_claim(programme_fixture):
    """Catches forged ActorContext roles authorising a user whose persisted role was removed."""
    with Session(db.engine) as session, session.begin():
        user = session.get(User, programme_fixture.owner_id)
        user.enterprise_role = "application_manager"

    forged = ActorContext(
        programme_fixture.owner_id,
        programme_fixture.organization_id,
        frozenset({"enterprise_architect", "chief_architect", "platform_admin"}),
        "forged-request",
    )
    with pytest.raises(NotAuthorised, match="programme_create_not_authorised"):
        TransformationProgrammeService.create_programme(
            actor=forged,
            command_key="forged-role",
            request=_intake(programme_fixture.owner_id),
        )
    assert _rows(programme_fixture)["programme"] is None


def test_create_programme_hides_cross_tenant_owner(programme_fixture):
    """Catches a globally valid foreign user ID being accepted or disclosed."""
    with pytest.raises(NotFound, match="owner_not_found"):
        TransformationProgrammeService.create_programme(
            actor=programme_fixture.actor,
            command_key="foreign-owner",
            request=_intake(programme_fixture.foreign_owner_id),
        )


def test_nullable_target_date_requires_persisted_reason(programme_fixture):
    """Catches an unknown programme horizon being silently stored as blank."""
    with pytest.raises(ValueError, match="target_date_unavailable_reason"):
        TransformationProgrammeService.create_programme(
            actor=programme_fixture.actor,
            command_key="missing-date-reason",
            request=_intake(programme_fixture.owner_id, target_date=None),
        )


def test_assign_role_reauthorises_replay_from_current_server_state(programme_fixture):
    """Catches persisted role-command success replaying after the caller loses authority."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="role-programme",
        request=_intake(programme_fixture.owner_id),
    )
    result = TransformationProgrammeService.assign_role(
        actor=programme_fixture.actor,
        programme_id=created.object_ids["programme_id"],
        workstream_id=created.object_ids["workstream_id"],
        user_id=programme_fixture.owner_id,
        role="contributor",
        effective_from=date.today(),
        effective_to=None,
        expected_revision=1,
        command_key="assign-contributor",
    )
    assert result.object_ids["role_assignment_id"] > 0

    with Session(db.engine) as session, session.begin():
        user = session.get(User, programme_fixture.owner_id)
        user.enterprise_role = "application_manager"
        owner_assignment = session.execute(
            select(ProgrammeRoleAssignment).where(
                ProgrammeRoleAssignment.organization_id == programme_fixture.organization_id,
                ProgrammeRoleAssignment.programme_id == created.object_ids["programme_id"],
                ProgrammeRoleAssignment.role == "programme_owner",
            )
        ).scalar_one()
        owner_assignment.effective_from = date.today() - timedelta(days=2)
        owner_assignment.effective_to = date.today() - timedelta(days=1)

    with pytest.raises(NotAuthorised, match="role_assignment_not_authorised"):
        TransformationProgrammeService.assign_role(
            actor=programme_fixture.actor,
            programme_id=created.object_ids["programme_id"],
            workstream_id=created.object_ids["workstream_id"],
            user_id=programme_fixture.owner_id,
            role="contributor",
            effective_from=date.today(),
            effective_to=None,
            expected_revision=1,
            command_key="assign-contributor",
        )


def test_programme_role_assignment_locks_and_advances_programme_revision(programme_fixture):
    """Catches programme-scoped role writes ignoring their expected aggregate revision."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="programme-role-revision",
        request=_intake(programme_fixture.owner_id),
    )
    programme_id = created.object_ids["programme_id"]
    assigned = TransformationProgrammeService.assign_role(
        actor=programme_fixture.actor,
        programme_id=programme_id,
        workstream_id=None,
        user_id=programme_fixture.owner_id,
        role="contributor",
        effective_from=date.today(),
        effective_to=None,
        expected_revision=1,
        command_key="programme-role-write",
    )
    assert assigned.response["revision"] == 2
    with Session(db.engine) as session:
        assert session.get(StrategicInitiative, programme_id).revision == 2

    with pytest.raises(CommandConflict, match="stale_revision"):
        TransformationProgrammeService.assign_role(
            actor=programme_fixture.actor,
            programme_id=programme_id,
            workstream_id=None,
            user_id=programme_fixture.owner_id,
            role="evidence_owner",
            effective_from=date.today(),
            effective_to=None,
            expected_revision=1,
            command_key="stale-programme-role-write",
        )


def test_workstream_role_assignment_locks_and_advances_workstream_revision(programme_fixture):
    """Catches workstream-scoped role writes leaving the aggregate revision unchanged."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="workstream-role-revision",
        request=_intake(programme_fixture.owner_id),
    )
    assigned = TransformationProgrammeService.assign_role(
        actor=programme_fixture.actor,
        programme_id=created.object_ids["programme_id"],
        workstream_id=created.object_ids["workstream_id"],
        user_id=programme_fixture.owner_id,
        role="contributor",
        effective_from=date.today(),
        effective_to=None,
        expected_revision=1,
        command_key="workstream-role-write",
    )
    assert assigned.response["revision"] == 2
    with Session(db.engine) as session:
        assert session.get(ProgrammeWorkstream, created.object_ids["workstream_id"]).revision == 2
    with pytest.raises(CommandConflict, match="stale_revision"):
        TransformationProgrammeService.assign_role(
            actor=programme_fixture.actor,
            programme_id=created.object_ids["programme_id"],
            workstream_id=created.object_ids["workstream_id"],
            user_id=programme_fixture.owner_id,
            role="evidence_owner",
            effective_from=date.today(),
            effective_to=None,
            expected_revision=1,
            command_key="stale-workstream-role-write",
        )


def test_concurrent_programme_role_assignments_allow_one_revision_winner(app, programme_fixture):
    """Catches two writers both committing against the same programme revision."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="concurrent-role-programme",
        request=_intake(programme_fixture.owner_id),
    )
    start = threading.Barrier(3)
    results = []
    errors = []

    def assign(role):
        with app.app_context():
            start.wait(timeout=5)
            try:
                results.append(
                    TransformationProgrammeService.assign_role(
                        actor=programme_fixture.actor,
                        programme_id=created.object_ids["programme_id"],
                        workstream_id=None,
                        user_id=programme_fixture.owner_id,
                        role=role,
                        effective_from=date.today(),
                        effective_to=None,
                        expected_revision=1,
                        command_key=f"concurrent-role-{role}",
                    )
                )
            except Exception as error:  # asserted after both workers finish
                errors.append(error)
            finally:
                db.session.remove()

    threads = [
        threading.Thread(target=assign, args=(role,), daemon=True)
        for role in ("contributor", "evidence_owner")
    ]
    for thread in threads:
        thread.start()
    start.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=10)

    assert len(results) == 1
    assert results[0].response["revision"] == 2
    assert len(errors) == 1
    assert isinstance(errors[0], CommandConflict)
    assert errors[0].reason == "stale_revision"


def test_update_objective_checks_revision_and_changes_only_owned_fields(programme_fixture):
    """Catches stale or broad workstream updates bypassing the locked command handler."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="objective-programme",
        request=_intake(programme_fixture.owner_id),
    )
    result = TransformationProgrammeService.update_objective(
        actor=programme_fixture.actor,
        workstream_id=created.object_ids["workstream_id"],
        objective="Remove duplicate services while protecting customer journeys",
        scope_expression={"business_units": ["Retail", "Commercial"]},
        expected_revision=1,
        command_key="objective-update",
    )
    assert result.response["revision"] == 2
    with Session(db.engine) as session:
        stream = session.get(ProgrammeWorkstream, created.object_ids["workstream_id"])
        assert stream.objective == "Remove duplicate services while protecting customer journeys"
        assert stream.scope_expression == {"business_units": ["Retail", "Commercial"]}
        assert stream.lifecycle_stage == "objective"
        assert stream.workstream_type == "application_rationalisation"

    with pytest.raises(CommandConflict, match="stale_revision"):
        TransformationProgrammeService.update_objective(
            actor=programme_fixture.actor,
            workstream_id=created.object_ids["workstream_id"],
            objective="Stale overwrite",
            scope_expression={"business_units": ["Retail"]},
            expected_revision=1,
            command_key="stale-objective-update",
        )


def test_archive_is_soft_versioned_and_retains_children(programme_fixture):
    """Catches programme archive deleting history or accepting a stale aggregate revision."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="archive-programme",
        request=_intake(programme_fixture.owner_id),
    )
    archived = TransformationProgrammeService.archive(
        actor=programme_fixture.actor,
        programme_id=created.object_ids["programme_id"],
        expected_revision=1,
        command_key="archive-command",
    )
    assert archived.response["status"] == "archived"
    assert archived.response["revision"] == 2
    with Session(db.engine) as session:
        programme = session.get(StrategicInitiative, created.object_ids["programme_id"])
        assert programme.archived_at is not None
        assert programme.revision == 2
        assert session.scalar(
            select(db.func.count()).select_from(ProgrammeWorkstream).where(
                ProgrammeWorkstream.programme_id == programme.id,
                ProgrammeWorkstream.organization_id == programme_fixture.organization_id,
            )
        ) == 1


def test_archived_programme_rejects_role_and_objective_mutations(programme_fixture):
    """Catches archived history remaining writable through aggregate child commands."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="archived-mutation-programme",
        request=_intake(programme_fixture.owner_id),
    )
    TransformationProgrammeService.archive(
        actor=programme_fixture.actor,
        programme_id=created.object_ids["programme_id"],
        expected_revision=1,
        command_key="archive-before-mutation",
    )
    with pytest.raises(CommandConflict, match="programme_archived"):
        TransformationProgrammeService.assign_role(
            actor=programme_fixture.actor,
            programme_id=created.object_ids["programme_id"],
            workstream_id=created.object_ids["workstream_id"],
            user_id=programme_fixture.owner_id,
            role="contributor",
            effective_from=date.today(),
            effective_to=None,
            expected_revision=1,
            command_key="archived-role-write",
        )
    with pytest.raises(CommandConflict, match="programme_archived"):
        TransformationProgrammeService.update_objective(
            actor=programme_fixture.actor,
            workstream_id=created.object_ids["workstream_id"],
            objective="Attempted archived change",
            scope_expression={"business_units": ["Retail"]},
            expected_revision=1,
            command_key="archived-objective-write",
        )
    view = TransformationProgrammeService.get_programme(
        actor=programme_fixture.actor,
        programme_id=created.object_ids["programme_id"],
    )
    assert view.lifecycle == "archived"
    assert view.next_action is None


def test_active_programme_read_prioritises_earliest_stage_across_detached_workstreams(
    programme_fixture,
):
    """Catches next action using ID rather than lifecycle risk after session detach."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="active-multiple-workstreams",
        request=_intake(programme_fixture.owner_id),
    )
    with Session(db.engine) as session, session.begin():
        first = session.get(ProgrammeWorkstream, created.object_ids["workstream_id"])
        first.lifecycle_stage = "approved"
        second = ProgrammeWorkstream(
            organization_id=programme_fixture.organization_id,
            programme_id=created.object_ids["programme_id"],
            workstream_type="process",
            objective="Simplify fulfilment hand-offs",
            scope_expression={"business_units": ["Retail"]},
            lifecycle_stage="objective",
            lead_id=programme_fixture.owner_id,
            target_date=date(2027, 9, 30),
        )
        session.add(second)
        session.flush()
        second_id = second.id

    view = TransformationProgrammeService.get_programme(
        actor=programme_fixture.actor,
        programme_id=created.object_ids["programme_id"],
    )

    assert view.workstream_ids == (created.object_ids["workstream_id"], second_id)
    assert view.next_action is not None
    assert view.next_action.resource_id == second_id


@pytest.mark.parametrize("non_finite", ["NaN", "Infinity", "-Infinity", Decimal("NaN")])
def test_intake_rejects_non_finite_measure_values(programme_fixture, non_finite):
    """Catches PostgreSQL Numeric special values entering governed outcome measures."""
    intake = _intake(programme_fixture.owner_id)
    measure = {**intake.outcome["measure"], "target_value": non_finite}
    outcome = {**intake.outcome, "measure": measure}
    with pytest.raises(ValueError, match="finite"):
        TransformationProgrammeService.create_programme(
            actor=programme_fixture.actor,
            command_key=f"non-finite-{str(non_finite)}",
            request=_intake(programme_fixture.owner_id, outcome=outcome),
        )


@pytest.mark.parametrize(
    "failing_type",
    [ProgrammeRoleAssignment, ProgrammeWorkstream, ProgrammeOutcomeCommitment, MeasureDefinition],
)
def test_subordinate_failure_rolls_back_entire_programme_graph(programme_fixture, failing_type):
    """Catches any subordinate insert leaving a partial programme aggregate committed."""
    def fail_selected_insert(session, _flush_context, _instances):
        if any(isinstance(row, failing_type) for row in session.new):
            raise RuntimeError(f"forced {failing_type.__name__} failure")

    event.listen(Session, "before_flush", fail_selected_insert)
    try:
        with pytest.raises(RuntimeError, match="forced"):
            TransformationProgrammeService.create_programme(
                actor=programme_fixture.actor,
                command_key=f"rollback-{failing_type.__name__}",
                request=_intake(programme_fixture.owner_id),
            )
    finally:
        event.remove(Session, "before_flush", fail_selected_insert)

    rows = _rows(programme_fixture)
    assert rows["programme"] is None
    assert rows["workstreams"] == rows["roles"] == rows["outcomes"] == rows["measures"] == []
    assert rows["solutions"] == 0
    assert rows["events"] == []
