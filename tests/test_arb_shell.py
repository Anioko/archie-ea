"""ARB dashboard + reviews on the screen system (shell-overhaul Wave 3, Task 3).

Product design review (P0 wave) found two defects on the ARB dashboard, both
data-honesty violations for a screen a Fortune-500 ARB chair uses to make
governance decisions:

- "Cycle Time 0.0 days" and "Approval Rate 0.0%" rendered over ZERO completed
  reviews -- a literal ``0.0`` formatted from a zero-denominator average is
  indistinguishable from a genuinely-measured zero and is exactly the
  fabricated-data class CLAUDE.md forbids. It must render the em dash.
- The Review Status donut chart rendered as an empty white box when there
  was no data -- there must be an honest empty-state instead.

This file also pins the page_shell migration (one <h1>, no header double-up).
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def _make_user(db_session, make_org, label):
    from app.models.user import User

    org = make_org(f"arb-shell-{label}")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"arb-shell-{label}-{suffix}@example.com",
        first_name="Arb",
        last_name="Shell",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    user.password = "Sup3rSecret!23"
    db_session.add(user)
    db_session.flush()
    db_session.commit()
    return user.id, org


def _empty_dashboard_data():
    return {
        "metrics": {
            "total_items": 0,
            "pending_items": 0,
            "approved_items": 0,
            "rejected_items": 0,
            "approval_rate": 0,
        },
        "recent_reviews": [],
        "upcoming_sessions": [],
        "review_types": [],
        "togaf_phases": [],
    }


def _empty_cycle_time():
    return {
        "period_days": 90,
        "total_reviews": 0,
        "avg_days": 0,
        "min_days": 0,
        "max_days": 0,
        "median_days": 0,
        "by_review_type": {},
        "by_priority": {},
    }


def _empty_standards_summary():
    return {"total_standards": 0, "mandatory_count": 0, "standards": []}


def _populated_dashboard_data():
    return {
        "metrics": {
            "total_items": 10,
            "pending_items": 3,
            "approved_items": 5,
            "rejected_items": 2,
            "approval_rate": 71.4,
        },
        "recent_reviews": [],
        "upcoming_sessions": [],
        "review_types": [],
        "togaf_phases": [],
    }


def _populated_cycle_time():
    return {
        "period_days": 90,
        "total_reviews": 7,
        "avg_days": 4.2,
        "min_days": 1,
        "max_days": 12,
        "median_days": 3,
        "by_review_type": {},
        "by_priority": {},
    }


def _patch_dashboard_services(monkeypatch, dashboard_data, cycle_time, standards_summary=None):
    import app.modules.architecture.routes.arb_routes as arb_routes

    monkeypatch.setattr(
        arb_routes.arb_service, "get_governance_dashboard", lambda: dashboard_data
    )
    monkeypatch.setattr(
        arb_routes.arb_analytics, "get_cycle_time_analytics", lambda days=90: cycle_time
    )
    monkeypatch.setattr(
        arb_routes.arb_analytics,
        "get_approval_trends",
        lambda months=12: {"trends": []},
    )
    monkeypatch.setattr(
        arb_routes.arb_analytics,
        "get_standard_compliance_summary",
        lambda: standards_summary or _empty_standards_summary(),
    )


def test_dashboard_has_exactly_one_h1(app, db_session, make_org, monkeypatch):
    user_id, _org = _make_user(db_session, make_org, "one-h1")
    _patch_dashboard_services(monkeypatch, _empty_dashboard_data(), _empty_cycle_time())

    client = app.test_client()
    _login(client, user_id)
    resp = client.get("/arb/")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    html = resp.get_data(as_text=True)

    assert html.count("<h1") == 1


def test_zero_completed_reviews_renders_dash_not_zero(app, db_session, make_org, monkeypatch):
    """The historical bug: an all-zero denominator formatted as "0.0 days"
    / "0.0%" instead of the em dash that means "not computed"."""
    user_id, _org = _make_user(db_session, make_org, "zero-metrics")
    _patch_dashboard_services(monkeypatch, _empty_dashboard_data(), _empty_cycle_time())

    client = app.test_client()
    _login(client, user_id)
    html = client.get("/arb/").get_data(as_text=True)

    assert "0.0 days" not in html
    assert "0.0%" not in html
    assert "—" in html


def test_populated_metrics_render_real_numbers(app, db_session, make_org, monkeypatch):
    """The honesty fix must not blank out genuinely-computed non-zero values."""
    user_id, _org = _make_user(db_session, make_org, "real-metrics")
    _patch_dashboard_services(
        monkeypatch, _populated_dashboard_data(), _populated_cycle_time()
    )

    client = app.test_client()
    _login(client, user_id)
    html = client.get("/arb/").get_data(as_text=True)

    assert "4.2 days" in html
    assert "71.4%" in html


def test_zero_reviews_shows_chart_empty_state(app, db_session, make_org, monkeypatch):
    user_id, _org = _make_user(db_session, make_org, "chart-empty")
    _patch_dashboard_services(monkeypatch, _empty_dashboard_data(), _empty_cycle_time())

    client = app.test_client()
    _login(client, user_id)
    html = client.get("/arb/").get_data(as_text=True)

    assert 'data-testid="arb-empty-status-chart"' in html
    assert 'id="arbStatusChart"' not in html


def test_populated_reviews_render_chart_canvas_not_empty_state(
    app, db_session, make_org, monkeypatch
):
    user_id, _org = _make_user(db_session, make_org, "chart-data")
    _patch_dashboard_services(
        monkeypatch, _populated_dashboard_data(), _populated_cycle_time()
    )

    client = app.test_client()
    _login(client, user_id)
    html = client.get("/arb/").get_data(as_text=True)

    assert 'id="arbStatusChart"' in html
    assert 'data-testid="arb-empty-status-chart"' not in html


def test_reviews_list_has_exactly_one_h1(app, db_session, make_org):
    user_id, _org = _make_user(db_session, make_org, "reviews-h1")

    client = app.test_client()
    _login(client, user_id)
    resp = client.get("/arb/reviews")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    html = resp.get_data(as_text=True)

    assert html.count("<h1") == 1


def test_sessions_list_still_has_exactly_one_h1(app, db_session, make_org):
    """/arb/sessions shares the same template as /arb/reviews -- the
    page_shell migration must not break the non-reviews branch."""
    user_id, _org = _make_user(db_session, make_org, "sessions-h1")

    client = app.test_client()
    _login(client, user_id)
    resp = client.get("/arb/sessions")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    html = resp.get_data(as_text=True)

    assert html.count("<h1") == 1
