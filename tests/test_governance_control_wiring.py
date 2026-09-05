"""Regression coverage for governance controls that previously rendered dead."""

from types import SimpleNamespace

from bs4 import BeautifulSoup


def _render(app, template_name, **context):
    with app.test_request_context("/"):
        html = app.jinja_env.get_template(template_name).render(**context)
    return BeautifulSoup(html, "html.parser")


def test_governance_entry_points_link_to_existing_workflows(app):
    expected = {
        "governance/adr_list.html": ("New ADR", "/architecture/decisions/new"),
        "governance/arb_reviews.html": ("Schedule Review", "/arb/sessions"),
    }

    for template_name, (label, href) in expected.items():
        page = _render(app, template_name)
        control = page.find("a", string=lambda value: value and label in value)
        assert control is not None, f"{label} must be a real link"
        assert control["href"] == href


def test_risk_register_add_control_opens_a_complete_create_form(app):
    page = _render(app, "governance/risk_register.html", risks=[], grid=[], total=0)

    add = page.find(attrs={"data-modal-open": "create-enterprise-risk"})
    assert add is not None
    form = page.select_one("#create-enterprise-risk form")
    assert form is not None
    assert form.select_one('[name="title"][required]') is not None
    assert form.select_one('[name="likelihood"][required]') is not None
    assert form.select_one('[name="impact"][required]') is not None


def test_governance_dashboard_review_links_use_the_payload_destination(app):
    page = _render(app, "governance/dashboard.html")

    link = page.select_one('[data-governance-review-link][\\:href="review.url"]')
    assert link is not None
    assert page.select_one("[data-governance-standard-edit]") is None


def test_recent_review_payload_targets_the_reviewed_solution(app):
    from app.modules.governance.routes.governance_dashboard_routes import (
        _serialize_recent_review,
    )

    review = SimpleNamespace(
        id=7,
        solution_id=42,
        submitted_at=None,
        arb_decision="pending",
    )
    solution = SimpleNamespace(name="Customer Portal")

    with app.test_request_context("/"):
        payload = _serialize_recent_review(review, solution)

    assert payload["url"] == "/solutions/42"


def test_arb_decision_title_links_to_canonical_decision_detail(app):
    decision = SimpleNamespace(
        id=42,
        decision_id="ADR-0042",
        title="Adopt event streaming",
        decision_type="technology",
        horizon="strategic",
        authority_level="enterprise_arb",
        status="accepted",
        valid_from=None,
        enterprise_level=True,
    )
    page = _render(
        app,
        "arb/decisions.html",
        decisions=[decision],
        valid_horizons=[],
        valid_authority_levels=[],
        valid_statuses=[],
        valid_decision_types=[],
    )

    link = page.find("a", string=lambda value: value and "Adopt event streaming" in value)
    assert link is not None
    assert link["href"] == "/architecture/decisions/42"
