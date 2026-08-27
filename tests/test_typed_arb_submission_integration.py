"""PostgreSQL integration proof for the typed ARB submission command."""

from __future__ import annotations

from dataclasses import dataclass
import uuid

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app import db
from app.models.adr import ArchitectureDecisionRecord
from app.models.architecture_review_board import ARBReviewCycle, ARBReviewItem
from app.models.transformation_db_guards import ensure_transformation_db_guards
from app.models.transformation_decision import ARBSubjectEvidenceSnapshot
from app.models.transformation_execution import OperationResult
from app.models.organization import Organization
from app.models.arb_submission_evidence import (
    ARBSubmissionEvidenceSnapshot,
    ensure_evidence_immutability_triggers,
)
from app.models.solution_architect_models import (
    DriverType,
    SolutionAnalysisSession,
    SolutionDriver,
    SolutionGoal,
    SolutionProblemDefinition,
)
from app.models.solution_lifecycle_models import SolutionRisk
from app.models.solution_models import Solution
from app.models.user import User
from app.modules.transformation_room.arb_submission_service import (
    TypedARBSubmissionService,
)
from app.modules.transformation_room.domain import ActorContext, NotFound


@dataclass(frozen=True)
class _ADRScope:
    actor: ActorContext
    organization_id: int
    user_id: int
    adr_id: int
    foreign_actor: ActorContext


@dataclass(frozen=True)
class _SolutionScope:
    actor: ActorContext
    organization_id: int
    solution_id: int


@pytest.fixture(scope="module", autouse=True)
def _command_guards(app, _schema):
    with app.app_context(), db.engine.begin() as connection:
        ensure_transformation_db_guards(connection)
        ensure_evidence_immutability_triggers(connection)


@pytest.fixture
def adr_scope(app, _schema):
    suffix = uuid.uuid4().hex[:12]
    with app.app_context():
        db.session.remove()
        organization = Organization(
            name=f"Typed ARB integration {suffix}",
            slug=f"typed-arb-integration-{suffix}",
        )
        foreign = Organization(
            name=f"Typed ARB foreign {suffix}",
            slug=f"typed-arb-foreign-{suffix}",
        )
        db.session.add_all((organization, foreign))
        db.session.flush()
        user = User(
            organization_id=organization.id,
            email=f"typed-arb-{suffix}@example.test",
            enterprise_role="enterprise_architect",
            confirmed=True,
        )
        foreign_user = User(
            organization_id=foreign.id,
            email=f"typed-arb-foreign-{suffix}@example.test",
            enterprise_role="enterprise_architect",
            confirmed=True,
        )
        db.session.add_all((user, foreign_user))
        db.session.flush()
        adr = ArchitectureDecisionRecord(
            organization_id=organization.id,
            adr_number=int(suffix[:7], 16),
            title=f"Adopt governed integration {suffix}",
            status="proposed",
            context="Services require reliable asynchronous integration.",
            decision="Use durable domain events through the enterprise broker.",
            rationale="This isolates producers and consumers.",
            consequences="Teams own schema compatibility.",
            created_by=user.email,
        )
        db.session.add(adr)
        db.session.commit()
        scope = _ADRScope(
            actor=ActorContext(
                user.id,
                organization.id,
                frozenset({"enterprise_architect"}),
                f"typed-arb-{suffix}",
            ),
            organization_id=organization.id,
            user_id=user.id,
            adr_id=adr.id,
            foreign_actor=ActorContext(
                foreign_user.id,
                foreign.id,
                frozenset({"enterprise_architect"}),
                f"typed-arb-foreign-{suffix}",
            ),
        )
        db.session.remove()
        try:
            yield scope
        finally:
            db.session.remove()
            with db.engine.begin() as connection:
                connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
                for table_name in (
                    "transformation_outbox_events",
                    "operation_results",
                    "command_materialisations",
                    "command_idempotency_records",
                    "arb_review_items",
                    "arb_review_cycles",
                    "arb_subject_evidence_snapshots",
                    "architecture_decision_records",
                    "users",
                ):
                    connection.execute(
                        text(
                            f'DELETE FROM "{table_name}" '
                            "WHERE organization_id IN (:organization_id, :foreign_id)"
                        ),
                        {
                            "organization_id": scope.organization_id,
                            "foreign_id": scope.foreign_actor.organization_id,
                        },
                    )
                connection.execute(
                    text("DELETE FROM organizations WHERE id IN (:own, :foreign)"),
                    {
                        "own": scope.organization_id,
                        "foreign": scope.foreign_actor.organization_id,
                    },
                )


@pytest.fixture
def solution_scope(app, _schema):
    suffix = uuid.uuid4().hex[:12]
    with app.app_context():
        db.session.remove()
        organization = Organization(
            name=f"Typed ARB solution {suffix}",
            slug=f"typed-arb-solution-{suffix}",
        )
        db.session.add(organization)
        db.session.flush()
        user = User(
            organization_id=organization.id,
            email=f"typed-arb-solution-{suffix}@example.test",
            enterprise_role="enterprise_architect",
            confirmed=True,
        )
        db.session.add(user)
        db.session.flush()
        workspace = SolutionAnalysisSession(
            organization_id=organization.id,
            name=f"Governed workspace {suffix}",
            created_by_id=user.id,
        )
        db.session.add(workspace)
        db.session.flush()
        problem = SolutionProblemDefinition(
            organization_id=organization.id,
            session_id=workspace.id,
            problem_description="Replace brittle synchronous integration.",
        )
        db.session.add(problem)
        db.session.flush()
        driver = SolutionDriver(
            organization_id=organization.id,
            problem_id=problem.id,
            name="Resilience",
            driver_type=DriverType.TECHNOLOGY,
        )
        goal = SolutionGoal(
            organization_id=organization.id,
            problem_id=problem.id,
            name="Reliable event delivery",
        )
        solution = Solution(
            organization_id=organization.id,
            name=f"Governed solution {suffix}",
            description="A fully evidenced integration solution.",
            created_by_id=user.id,
            analysis_session_id=workspace.id,
            governance_status="draft",
        )
        db.session.add_all((driver, goal, solution))
        db.session.flush()
        db.session.add(
            SolutionRisk(
                organization_id=organization.id,
                solution_id=solution.id,
                risk_name="Schema drift",
                risk_description="Consumers may lag schema changes.",
                impact="medium",
                probability="medium",
                mitigation="Use versioned schemas and compatibility checks.",
                created_by_id=user.id,
            )
        )
        db.session.commit()
        scope = _SolutionScope(
            actor=ActorContext(
                user.id,
                organization.id,
                frozenset({"enterprise_architect"}),
                f"typed-arb-solution-{suffix}",
            ),
            organization_id=organization.id,
            solution_id=solution.id,
        )
        db.session.remove()
        try:
            yield scope
        finally:
            db.session.remove()
            raw = db.engine.raw_connection()
            try:
                with raw.cursor() as cursor:
                    cursor.execute("SET session_replication_role = replica")
                    cursor.execute(
                        "DELETE FROM arb_submission_evidence_snapshots "
                        "WHERE organization_id = %s",
                        (scope.organization_id,),
                    )
                raw.commit()
            finally:
                raw.close()
            with db.engine.begin() as connection:
                connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
                for table_name in (
                    "transformation_outbox_events",
                    "operation_results",
                    "command_materialisations",
                    "command_idempotency_records",
                    "arb_review_items",
                    "arb_review_cycles",
                    "solution_risks",
                    "solution_goals",
                    "solution_drivers",
                    "solutions",
                    "solution_problem_definitions",
                    "solution_analysis_sessions",
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


def _submit(scope, command_key):
    return TypedARBSubmissionService.submit(
        actor=scope.actor,
        command_key=command_key,
        subject_type="adr",
        subject_id=scope.adr_id,
        assertions={"human_reviewed": True},
    )


def _counts(scope):
    with Session(db.engine) as session:
        predicates = (
            ARBReviewCycle.organization_id == scope.organization_id,
            ARBReviewCycle.subject_type == "adr",
            ARBReviewCycle.subject_id == scope.adr_id,
        )
        return {
            "snapshots": session.scalar(
                select(db.func.count())
                .select_from(ARBSubjectEvidenceSnapshot)
                .where(
                    ARBSubjectEvidenceSnapshot.organization_id == scope.organization_id,
                    ARBSubjectEvidenceSnapshot.adr_id == scope.adr_id,
                )
            ),
            "cycles": session.scalar(
                select(db.func.count()).select_from(ARBReviewCycle).where(*predicates)
            ),
            "items": session.scalar(
                select(db.func.count())
                .select_from(ARBReviewItem)
                .where(
                    ARBReviewItem.organization_id == scope.organization_id,
                    ARBReviewItem.subject_type == "adr",
                    ARBReviewItem.subject_id == scope.adr_id,
                )
            ),
            "results": session.scalar(
                select(db.func.count())
                .select_from(OperationResult)
                .where(
                    OperationResult.organization_id == scope.organization_id,
                    OperationResult.operation == "arb.submit",
                )
            ),
        }


def test_real_adr_submission_is_atomic_and_same_key_replay_is_stable(app, adr_scope):
    with app.app_context():
        first = _submit(adr_scope, "adr-submit")
        replay = _submit(adr_scope, "adr-submit")

    assert first.created is True
    assert replay.idempotent is True
    assert replay.object_ids == first.object_ids
    assert _counts(adr_scope) == {
        "snapshots": 1,
        "cycles": 1,
        "items": 1,
        "results": 1,
    }
    with Session(db.engine) as session:
        cycle = session.get(ARBReviewCycle, first.object_ids["review_cycle_id"])
        item = session.get(ARBReviewItem, first.object_ids["review_item_id"])
        snapshot = session.get(
            ARBSubjectEvidenceSnapshot, first.object_ids["evidence_id"]
        )
        assert cycle.subject_evidence_snapshot_id == snapshot.id
        assert item.review_cycle_id == cycle.id
        assert item.subject_evidence_snapshot_id == snapshot.id
        assert cycle.review_number == item.review_number
        assert snapshot.content_hash == snapshot.recompute_content_hash()


def test_real_solution_submission_pins_legacy_evidence_into_typed_graph(
    app, solution_scope, tenant_ctx
):
    assertions = {
        "human_reviewed": True,
        "direct_route_evidence": {
            name: {"passed": True, "evidence": f"{name} checked"}
            for name in (
                "design_reviewed",
                "security_impact_reviewed",
                "data_impact_reviewed",
            )
        },
    }
    with app.app_context(), tenant_ctx(solution_scope.organization_id):
        result = TypedARBSubmissionService.submit_legacy_solution(
            actor=solution_scope.actor,
            command_key="solution-submit",
            solution_id=solution_scope.solution_id,
            assertions=assertions,
        )

    assert result.created is True
    with Session(db.engine) as session:
        snapshot = session.get(
            ARBSubmissionEvidenceSnapshot, result.object_ids["evidence_id"]
        )
        cycle = session.get(ARBReviewCycle, result.object_ids["review_cycle_id"])
        item = session.get(ARBReviewItem, result.object_ids["review_item_id"])
        assert snapshot.solution_id == solution_scope.solution_id
        assert snapshot.content_hash == snapshot.recompute_content_hash()
        assert cycle.solution_id == item.solution_id == solution_scope.solution_id
        assert cycle.solution_evidence_snapshot_id == snapshot.id
        assert item.solution_evidence_snapshot_id == snapshot.id
        assert item.review_cycle_id == cycle.id
        assert snapshot.review_item_id == item.id
        assert session.scalar(
            select(db.func.count())
            .select_from(ARBSubmissionEvidenceSnapshot)
            .where(
                ARBSubmissionEvidenceSnapshot.organization_id
                == solution_scope.organization_id,
                ARBSubmissionEvidenceSnapshot.solution_id
                == solution_scope.solution_id,
            )
        ) == 1
        constraint = session.execute(
            text(
                """
                SELECT c.condeferrable, c.condeferred
                FROM pg_constraint AS c
                JOIN pg_class AS t ON t.oid = c.conrelid
                JOIN pg_namespace AS n ON n.oid = t.relnamespace
                WHERE n.nspname = current_schema()
                  AND t.relname = 'arb_submission_evidence_snapshots'
                  AND c.conname = 'fk_arb_submission_snapshot_review_item'
                """
            )
        ).one()
        assert constraint == (True, True)


def test_different_command_key_reconciles_to_the_same_open_cycle(app, adr_scope):
    with app.app_context():
        first = _submit(adr_scope, "first-command")
        contender = _submit(adr_scope, "second-command")

    assert first.created is True
    assert contender.idempotent is True
    assert contender.object_ids == first.object_ids
    assert _counts(adr_scope) == {
        "snapshots": 1,
        "cycles": 1,
        "items": 1,
        "results": 1,
    }


def test_cross_tenant_subject_is_uniform_not_found_and_creates_no_receipt(app, adr_scope):
    with app.app_context(), pytest.raises(NotFound, match="arb_subject_not_found"):
        TypedARBSubmissionService.submit(
            actor=adr_scope.foreign_actor,
            command_key="foreign-command",
            subject_type="adr",
            subject_id=adr_scope.adr_id,
            assertions={"human_reviewed": True},
        )

    assert _counts(adr_scope) == {
        "snapshots": 0,
        "cycles": 0,
        "items": 0,
        "results": 0,
    }


def test_review_item_insert_failure_rolls_back_snapshot_cycle_and_result(app, adr_scope):
    def fail_review_insert(_mapper, _connection, _target):
        raise RuntimeError("forced typed ARB review insert failure")

    event.listen(ARBReviewItem, "before_insert", fail_review_insert)
    try:
        with app.app_context(), pytest.raises(
            RuntimeError, match="forced typed ARB review insert failure"
        ):
            _submit(adr_scope, "forced-rollback")
    finally:
        event.remove(ARBReviewItem, "before_insert", fail_review_insert)

    assert _counts(adr_scope) == {
        "snapshots": 0,
        "cycles": 0,
        "items": 0,
        "results": 0,
    }
