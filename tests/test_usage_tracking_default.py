"""Usage tracking is on by default: one page-view row per module-directory
endpoint, keyed by endpoint name, with no personal data.

Per-organisation counts are a later change: `UsageAnalytics` carries no
`organization_id` column today, so `/usage-analytics/api/summary` reports
across every tenant. This module only pins that the page itself stays behind
`@login_required` and records the gap below rather than papering over it with
a scoped assertion the code does not actually make.
"""
import pytest

from app import db
from app.models.usage_analytics import UsageAnalytics
from app.models.user import User


def _user(org, tag, **overrides):
    kwargs = dict(
        email=f"usage-track-{tag}-{org.id}@example.com",
        first_name="Usage",
        last_name="Tracker",
        organization_id=org.id,
        confirmed=True,  # else before_request bounces to /account/unconfirmed
    )
    kwargs.update(overrides)
    u = User(**kwargs)
    u.password = "TestPass123!"
    db.session.add(u)
    db.session.flush()
    return u


@pytest.fixture
def analytics_on(app):
    """Flip ENABLE_USAGE_ANALYTICS on for the duration of one test, then
    restore TestingConfig's off-by-default value. The middleware hooks read
    this key from `current_app.config` at request time, so no second
    `create_app()` is needed."""
    original = app.config.get("ENABLE_USAGE_ANALYTICS")
    app.config["ENABLE_USAGE_ANALYTICS"] = True
    try:
        yield
    finally:
        app.config["ENABLE_USAGE_ANALYTICS"] = original


def test_directory_endpoint_writes_one_anonymous_row(
    db_session, make_org, client, login_as, analytics_on
):
    org = make_org("usage-directory")
    user = _user(org, "directory")
    login_as(client, user)

    before = UsageAnalytics.query.count()
    resp = client.get("/usage-analytics/")
    assert resp.status_code in (200, 302)

    rows = UsageAnalytics.query.order_by(UsageAnalytics.id.desc()).all()
    assert len(rows) == before + 1
    row = rows[0]
    assert row.feature_name == "usage_analytics.analytics_root"
    assert row.event_type == "page_view"
    assert row.ip_address is None
    assert row.user_agent is None
    assert row.referrer is None


def test_non_directory_endpoint_writes_nothing(
    db_session, make_org, client, login_as, analytics_on
):
    org = make_org("usage-non-directory")
    user = _user(org, "nondirectory")
    login_as(client, user)

    before = UsageAnalytics.query.count()
    # An API route under the same blueprint, but not itself a module-directory
    # link (only usage_analytics.analytics_root is listed there).
    resp = client.get("/usage-analytics/api/summary")
    assert resp.status_code == 200

    after = UsageAnalytics.query.count()
    assert after == before


def test_flag_off_writes_nothing(db_session, make_org, client, login_as, app):
    original = app.config.get("ENABLE_USAGE_ANALYTICS")
    app.config["ENABLE_USAGE_ANALYTICS"] = False
    try:
        org = make_org("usage-flag-off")
        user = _user(org, "flagoff")
        login_as(client, user)

        before = UsageAnalytics.query.count()
        resp = client.get("/usage-analytics/")
        assert resp.status_code in (200, 302)

        after = UsageAnalytics.query.count()
        assert after == before
    finally:
        app.config["ENABLE_USAGE_ANALYTICS"] = original


def test_config_flag_defaults():
    from config import Config, TestingConfig

    assert Config.ENABLE_USAGE_ANALYTICS is True
    assert TestingConfig.ENABLE_USAGE_ANALYTICS is False


def test_opted_out_user_writes_nothing(
    db_session, make_org, client, login_as, analytics_on
):
    org = make_org("usage-opt-out")
    user = _user(org, "optout")
    user.notification_preferences = {"analytics_opt_out": True}
    db.session.add(user)
    db.session.flush()
    login_as(client, user)

    before = UsageAnalytics.query.count()
    resp = client.get("/usage-analytics/")
    assert resp.status_code in (200, 302)

    after = UsageAnalytics.query.count()
    assert after == before


def test_summary_api_counts_rows_by_feature_name(
    db_session, make_org, client, login_as, analytics_on
):
    org = make_org("usage-summary")
    user = _user(org, "summary")
    login_as(client, user)

    client.get("/usage-analytics/")
    client.get("/usage-analytics/")

    resp = client.get("/usage-analytics/api/summary")
    assert resp.status_code == 200
    summary = resp.get_json()
    assert summary["usage_analytics.analytics_root"]["total_events"] >= 2


def test_dashboard_requires_login(client):
    resp = client.get("/usage-analytics/dashboard")
    assert resp.status_code in (302, 401)
    if resp.status_code == 302:
        assert "login" in resp.headers.get("Location", "").lower()
