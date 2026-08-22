"""Release-blocker contracts for canonical solution ARB submission."""

from pathlib import Path
import uuid

from app.models.arb_submission_evidence import ARBSubmissionEvidenceSnapshot
from app.models.architecture_review_board import ARBReviewItem
from app.models.solution_models import Solution
from app.models.solution_architect_models import (
    DriverType,
    SolutionAnalysisSession,
    SolutionDriver,
    SolutionGoal,
    SolutionProblemDefinition,
)
from app.models.solution_lifecycle_models import SolutionRisk
from app.models.user import User


ROOT = Path(__file__).resolve().parents[1]


def _source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_manual_arb_creation_rejects_solution_identity_before_legacy_service():
    source = _source("app/modules/architecture/routes/arb_routes.py")
    helper = source[source.index("def _create_arb_review_item"):source.index("@arb_bp.route(\"/reviews/create\"")]
    assert "solution_id" in helper
    assert "canonical evidence-gated submission endpoint" in helper
    assert helper.index("canonical evidence-gated submission endpoint") < helper.index("arb_service.submit_for_review")


def test_legacy_validation_engine_has_no_review_creation_or_status_mutation():
    source = _source("app/modules/architecture_assistant/validation_engine.py")
    method = source[source.index("    def submit_to_arb"):source.index("    def _validate_structure")]
    assert "ARBReviewItem(" not in method
    assert ".governance_status =" not in method
    assert "validation_result" not in method.split("def submit_to_arb", 1)[1].split(":", 1)[0]


def test_wizard_creation_ignores_client_review_linkage():
    source = _source("app/modules/solutions_strategic/v2/routes/solution_design_routes.py")
    method = source[source.index("def create_from_wizard"):source.index("db.session.flush()  # Get solution.id")]
    assert 'data.get("arb_review_id")' not in method
    assert "solution.arb_review_item_id" not in method
    assert "solution.arb_submission_date" not in method


def test_direct_route_ui_sends_named_attestations_with_evidence_notes():
    for path in (
        "app/templates/solutions/partials/_blueprint_governance.html",
        "app/templates/architecture_assistant/journey_v2_steps/_step6_review.html",
    ):
        source = _source(path)
        for name in ("design_reviewed", "security_impact_reviewed", "data_impact_reviewed"):
            assert name in source
        assert "direct_route_evidence" in source


def test_real_solution_endpoint_blocks_then_creates_one_canonical_snapshot(
    app, client, db_session, make_org, login_as
):
    app.config["SECRET_KEY"] = "arb-endpoint-integration-test"
    org = make_org("real-arb-endpoint")
    actor = User(
        email=f"arb-real-{uuid.uuid4().hex[:8]}@example.test",
        first_name="Real",
        last_name="Architect",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
        is_org_admin=True,
        is_platform_admin=True,
    )
    db_session.add(actor)
    db_session.flush()
    workspace = SolutionAnalysisSession(
        name="Direct route evidence fixture",
        created_by_id=actor.id,
        organization_id=org.id,
    )
    db_session.add(workspace)
    db_session.flush()
    solution = Solution(
        name=f"Real endpoint {uuid.uuid4().hex[:8]}",
        description="Real database submission contract",
        organization_id=org.id,
        created_by_id=actor.id,
        governance_status="draft",
        has_acm_domains=True,
        analysis_session_id=workspace.id,
    )
    db_session.add(solution)
    db_session.flush()
    problem = SolutionProblemDefinition(
        session_id=workspace.id,
        problem_description="Governed problem definition",
        organization_id=org.id,
    )
    db_session.add(problem)
    db_session.flush()
    driver = SolutionDriver(
        problem_id=problem.id,
        name="Governed driver",
        driver_type=DriverType.EXTERNAL,
        organization_id=org.id,
    )
    db_session.add(driver)
    db_session.flush()
    db_session.add_all([
        SolutionGoal(
            problem_id=problem.id,
            driver_id=driver.id,
            name="Governed goal",
            priority=1,
            organization_id=org.id,
        ),
        SolutionRisk(
            solution_id=solution.id,
            risk_name="Governed risk",
            risk_description="Evidence fixture risk",
            organization_id=org.id,
        ),
    ])
    db_session.flush()
    solution_id = solution.id
    login_as(client, actor)

    blocked = client.post(
        f"/solutions/{solution_id}/submit-for-arb",
        json={"human_reviewed": True},
    )
    assert blocked.status_code == 422, blocked.location
    assert blocked.get_json()["reason_codes"] == ["missing_direct_route_evidence"]
    assert ARBReviewItem.query.filter_by(solution_id=solution_id).count() == 0

    assertions = {
        "human_reviewed": True,
        "direct_route_evidence": {
            "design_reviewed": {"passed": True, "evidence": "Reviewed architecture diagrams and decisions."},
            "security_impact_reviewed": {"passed": True, "evidence": "Reviewed threat and control impacts."},
            "data_impact_reviewed": {"passed": True, "evidence": "Reviewed classification and lifecycle impacts."},
        },
    }
    created = client.post(f"/solutions/{solution_id}/submit-for-arb", json=assertions)
    assert created.status_code == 200, created.get_json()
    body = created.get_json()
    assert body["success"] is True
    assert ARBReviewItem.query.filter_by(solution_id=solution_id).count() == 1
    assert ARBSubmissionEvidenceSnapshot.query.filter_by(solution_id=solution_id).count() == 1

    retried = client.post(f"/solutions/{solution_id}/submit-for-arb", json=assertions)
    assert retried.status_code == 200
    assert retried.get_json()["idempotent"] is True
    assert ARBReviewItem.query.filter_by(solution_id=solution_id).count() == 1
    assert ARBSubmissionEvidenceSnapshot.query.filter_by(solution_id=solution_id).count() == 1
