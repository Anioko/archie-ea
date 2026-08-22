"""Versioned, pure lifecycle gate and transition tests."""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.models.transformation_programme import ProgrammeWorkstream
from app.modules.transformation_room.domain import ActorContext, BlockedByEvidence, NotFound
from app.modules.transformation_room.gate_service import TransformationGateService
from app.modules.transformation_room.programme_service import TransformationProgrammeService

from tests.test_transformation_programme_service import _intake, programme_fixture


def test_objective_gate_is_pure_and_transition_is_locked(programme_fixture):
    """Catches gate evaluation mutating state or transition bypassing revision/event handling."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="gate-ready",
        request=_intake(programme_fixture.owner_id),
    )
    workstream_id = created.object_ids["workstream_id"]

    evaluated = TransformationGateService.evaluate(
        actor=programme_fixture.actor,
        workstream_id=workstream_id,
        target_stage="discover",
    )
    with Session(db.engine) as session:
        unchanged = session.scalar(
            select(ProgrammeWorkstream).where(
                ProgrammeWorkstream.id == workstream_id,
                ProgrammeWorkstream.organization_id == programme_fixture.organization_id,
            )
        )
        assert unchanged.lifecycle_stage == "objective"
        assert unchanged.revision == 1

    transitioned = TransformationGateService.transition(
        actor=programme_fixture.actor,
        workstream_id=workstream_id,
        target_stage="discover",
        expected_revision=1,
        command_key="to-discover",
    )
    replayed = TransformationGateService.transition(
        actor=programme_fixture.actor,
        workstream_id=workstream_id,
        target_stage="discover",
        expected_revision=1,
        command_key="to-discover",
    )

    assert evaluated.allowed is True
    assert evaluated.policy_version == "transformation-r1.1"
    assert transitioned.response["lifecycle_stage"] == "discover"
    assert replayed.operation_result_id == transitioned.operation_result_id
    with Session(db.engine) as session:
        changed = session.get(ProgrammeWorkstream, workstream_id)
        assert changed.lifecycle_stage == "discover"
        assert changed.revision == 2


def test_objective_gate_returns_stable_blockers_and_denial_does_not_mutate(programme_fixture):
    """Catches an incomplete objective advancing or returning transient prose-only errors."""
    request = replace(
        _intake(programme_fixture.owner_id),
        scope_expression={},
        target_date=None,
        target_date_unavailable_reason="Date depends on portfolio review",
    )
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="gate-blocked",
        request=request,
    )
    workstream_id = created.object_ids["workstream_id"]

    gate = TransformationGateService.evaluate(
        actor=programme_fixture.actor,
        workstream_id=workstream_id,
        target_stage="discover",
    )
    assert gate.allowed is False
    assert {blocker.code for blocker in gate.blockers} == {"scope_required"}

    with pytest.raises(BlockedByEvidence) as denied:
        TransformationGateService.transition(
            actor=programme_fixture.actor,
            workstream_id=workstream_id,
            target_stage="discover",
            expected_revision=1,
            command_key="blocked-transition",
        )
    assert [item.code for item in denied.value.blockers] == ["scope_required"]
    with Session(db.engine) as session:
        unchanged = session.get(ProgrammeWorkstream, workstream_id)
        assert unchanged.lifecycle_stage == "objective"
        assert unchanged.revision == 1


def test_gate_load_is_explicitly_tenant_scoped(programme_fixture):
    """Catches a valid foreign workstream ID revealing readiness across tenants."""
    foreign_actor = ActorContext(
        programme_fixture.foreign_owner_id,
        programme_fixture.foreign_organization_id,
        frozenset(),
        "foreign-create",
    )
    created = TransformationProgrammeService.create_programme(
        actor=foreign_actor,
        command_key="foreign-gate",
        request=_intake(programme_fixture.foreign_owner_id),
    )
    with pytest.raises(NotFound, match="workstream_not_found"):
        TransformationGateService.evaluate(
            actor=programme_fixture.actor,
            workstream_id=created.object_ids["workstream_id"],
            target_stage="discover",
        )
