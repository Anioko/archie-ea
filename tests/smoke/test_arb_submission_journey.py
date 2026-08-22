"""Real-browser contract for the evidence-gated ARB submission journey."""

import uuid
from pathlib import Path
import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]
ROOT = Path(__file__).resolve().parents[2]
@pytest.fixture
def arb_solution(seeded):
    from app import create_app, db
    from app.models.solution_models import Solution
    from app.models.user import User

    app = create_app("testing")
    with app.app_context():
        user = User.query.filter_by(email=seeded["emails"]["solution_architect"]).one()
        solution = Solution(
            name=f"Evidence dossier {uuid.uuid4().hex[:8]}",
            description="Browser fixture for governed ARB submission.",
            organization_id=user.organization_id,
            created_by_id=user.id,
            governance_status="draft",
            has_acm_domains=True,
        )
        db.session.add(solution)
        db.session.commit()
        solution_id = solution.id

    yield solution_id

    with app.app_context():
        solution = db.session.get(Solution, solution_id)
        if solution is not None:
            db.session.delete(solution)
            db.session.commit()


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").dispatch_event("click")
    page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)


def _open_dossier(page, base, solution_id):
    page.goto(base + f"/solutions/{solution_id}", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    dossier = page.get_by_test_id("arb-evidence-dossier")
    dossier.wait_for(state="visible", timeout=PAGE_TIMEOUT)
    return page


def _complete_attestations(dossier):
    dossier.get_by_role("checkbox", name="Architecture design reviewed").check()
    dossier.get_by_role("textbox", name="Architecture design reviewed evidence note").fill("Reviewed architecture diagrams and decision rationale.")
    dossier.get_by_role("checkbox", name="Security impact reviewed").check()
    dossier.get_by_role("textbox", name="Security impact reviewed evidence note").fill("Reviewed threat and control impacts.")
    dossier.get_by_role("checkbox", name="Data impact reviewed").check()
    dossier.get_by_role("textbox", name="Data impact reviewed evidence note").fill("Reviewed data classification and lifecycle impacts.")


def test_journey_template_keeps_failure_taxonomy_and_canonical_success_contract():
    template = (ROOT / "app/templates/architecture_assistant/journey_v2_steps/_step6_review.html").read_text(encoding="utf-8")
    assert "Submission service unavailable" in template
    assert "Submission not permitted" in template
    assert "Submission context not found" in template
    assert "arbSubmissionError.kind === 'blocked'" in template
    assert "arbSubmitResult.review_item_id && arbSubmitResult.review_number" in template
    assert 'role="status" aria-live="polite" aria-atomic="true"' in template


def test_blocked_submission_recovers_once_to_one_canonical_review(browser, live_server, seeded, arb_solution):
    page = browser.new_page()
    attempts = []

    def submission(route):
        attempts.append(route.request.post_data_json)
        if len(attempts) == 1:
            route.fulfill(status=422, content_type="application/json", body='{"success":false,"reason_codes":["missing_named_artifacts"],"missing_evidence":[{"code":"artifact_missing","name":"Transition plan","action":"Persist the transition plan in the workbench."}]}')
        else:
            route.fulfill(status=200, content_type="application/json", body='{"success":true,"data":{"review_item_id":417,"review_number":"ARB-2026-0417","snapshot_id":91,"idempotent":false}}')

    page.route(f"**/solutions/{arb_solution}/submit-for-arb", submission)
    try:
        _login(page, live_server, seeded["emails"]["solution_architect"])
        dossier = _open_dossier(page, live_server, arb_solution)
        review_assertion = dossier.get_by_role("checkbox", name="I have reviewed")
        submit = page.locator("#bp-submit-arb-btn")
        assert submit.get_attribute("type") == "button"
        assert submit.inner_text().strip() == "Submit to ARB"

        assert submit.is_disabled()
        review_assertion.focus()
        page.keyboard.press("Space")
        assert review_assertion.is_checked()
        _complete_attestations(dossier)
        page.keyboard.press("Tab")
        assert submit.evaluate("element => element === document.activeElement")

        panel = page.locator("[x-data^='arbReadinessPanel']")
        panel.evaluate("element => { Alpine.$data(element).submission.state = 'submitting'; }")
        page.get_by_role("button", name="Submitting…").wait_for(state="visible")
        assert submit.is_disabled()
        panel.evaluate("element => { Alpine.$data(element).submission.state = 'idle'; }")

        submit.click(no_wait_after=True)
        blocker = page.get_by_test_id("arb-missing-evidence")
        blocker.wait_for(state="visible")
        assert "Transition plan" in blocker.inner_text()
        assert "Persist the transition plan" in blocker.inner_text()
        assert not page.get_by_text("Submitted to the Architecture Review Board", exact=True).is_visible()
        assert not page.get_by_role("link", name="Open canonical review").is_visible()

        dossier.get_by_role("button", name="Try submission again").click()
        page.get_by_text("Submitted to the Architecture Review Board", exact=True).wait_for(state="visible")
        canonical = page.get_by_role("link", name="Open canonical review")
        assert canonical.count() == 1
        assert canonical.get_attribute("href") == "/arb/reviews/417"
        assert len(attempts) == 2
        assert all(attempt["human_reviewed"] is True for attempt in attempts)
        assert all(set(attempt["direct_route_evidence"]) == {"design_reviewed", "security_impact_reviewed", "data_impact_reviewed"} for attempt in attempts)
    finally:
        page.close()


@pytest.mark.parametrize(
    ("status", "reason_code", "expected_heading"),
    [
        (503, "evaluator_unavailable", "Submission service unavailable"),
        (503, "submission_failed", "Submission service unavailable"),
        (403, "actor_not_authorized", "Submission not permitted"),
        (404, "solution_not_found", "Submission context not found"),
    ],
)
def test_non_evidence_failures_never_render_evidence_recovery(
    browser, live_server, seeded, arb_solution, status, reason_code, expected_heading
):
    page = browser.new_page()
    page.route(
        f"**/solutions/{arb_solution}/submit-for-arb",
        lambda route: route.fulfill(
            status=status,
            content_type="application/json",
            body='{"success":false,"reason_codes":["' + reason_code + '"],"missing_evidence":[]}',
        ),
    )
    try:
        _login(page, live_server, seeded["emails"]["solution_architect"])
        dossier = _open_dossier(page, live_server, arb_solution)
        dossier.get_by_role("checkbox", name="I have reviewed").check()
        _complete_attestations(dossier)
        dossier.get_by_role("button", name="Submit to ARB").click()
        error = page.get_by_test_id("arb-submission-error")
        error.wait_for(state="visible")
        assert expected_heading in error.inner_text()
        assert "Complete the evidence" not in error.inner_text()
        assert page.get_by_role("link", name="Open canonical review").count() == 0
    finally:
        page.close()
