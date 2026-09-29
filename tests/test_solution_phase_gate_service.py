"""Regression tests for solution phase gate status handling."""

from app.models.solution_models import Solution
from app.models.user import User
from app.modules.solutions_strategic.v2.services.solution_phase_gate_service import (
    SolutionPhaseGateService,
)


def test_get_all_phases_status_treats_unknown_current_phase_as_phase_a(
    db_session, make_org, tenant_ctx
):
    """Unknown stored phases must not break the all-phases overview."""
    org = make_org("phase_gate_unknown")
    user = User(
        email="phase-gate-unknown@example.test",
        first_name="Phase",
        last_name="Gate",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()

    solution = Solution(
        name="Unknown phase solution",
        organization_id=org.id,
        created_by_id=user.id,
        adm_phase="NOT-A-PHASE",
    )
    db_session.add(solution)
    db_session.flush()

    service = SolutionPhaseGateService()
    with tenant_ctx(org.id):
        phases = service.get_all_phases_status(solution.id)

    assert [phase["phase"] for phase in phases] == list("ABCDEFGH")
    assert phases[0]["status"] == "current"
    assert phases[0]["phase"] == "A"
    assert all(phase["status"] == "upcoming" for phase in phases[1:])
