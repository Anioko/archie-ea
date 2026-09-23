"""Onboarding routes and the profile store, against the shared db_session fixture."""
import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org, *, onboarding_completed=False):
    from app.models.user import User
    import uuid

    user = User(
        email=f"onboard-{uuid.uuid4().hex[:8]}@example.com",
        first_name="On",
        last_name="Board",
        confirmed=True,
        organization_id=org.id,
    )
    if onboarding_completed:
        import datetime
        user.onboarding_completed_at = datetime.datetime.utcnow()
    db_session.add(user)
    db_session.flush()
    return user




def test_profile_write_only_touches_the_onboarding_key(app, db_session, make_org):
    from app.modules.onboarding.services import profile

    org = make_org("profile")
    org.settings = {"other_key": "untouched"}
    db_session.add(org)
    db_session.flush()

    profile.write(org, stage="growing")

    assert org.settings["other_key"] == "untouched"
    assert org.settings["onboarding"]["stage"] == "growing"


def test_profile_write_merges_rather_than_replaces(app, db_session, make_org):
    from app.modules.onboarding.services import profile

    org = make_org("merge")
    profile.write(org, stage="pre_revenue")
    profile.write(org, company_size="5 people")

    assert org.settings["onboarding"]["stage"] == "pre_revenue"
    assert org.settings["onboarding"]["company_size"] == "5 people"


def test_index_redirects_to_welcome_for_a_genuinely_new_org(app, db_session, make_org, client, login_as):
    org = make_org("new")
    user = _make_user(db_session, org)
    login_as(client, user)
    resp = client.get("/onboarding/", follow_redirects=False)
    assert resp.status_code in (302, 308)
    assert resp.headers["Location"].endswith("/onboarding/welcome")


def test_index_redirects_to_first_question_when_org_already_onboarded(app, db_session, make_org, client, login_as):
    """An invited team member enters at Screen 3, per onboarding-prd-v1 §3."""
    from app.modules.onboarding.services import profile

    org = make_org("existing")
    profile.write(org, stage="growing")
    user = _make_user(db_session, org)
    login_as(client, user)
    resp = client.get("/onboarding/", follow_redirects=False)
    assert resp.status_code in (302, 308)
    assert resp.headers["Location"].endswith("/onboarding/first-question")


def test_index_redirects_to_dashboard_once_onboarding_is_complete(app, db_session, make_org, client, login_as):
    org = make_org("done")
    user = _make_user(db_session, org, onboarding_completed=True)
    login_as(client, user)
    resp = client.get("/onboarding/", follow_redirects=False)
    assert resp.status_code in (302, 308)
    assert "/dashboard/overview" in resp.headers["Location"]


def test_gap_action_accept_keeps_the_gap_visible(app, db_session, make_org):
    """Redesign v3 §4/§5: accepted gaps are never counted as filled."""
    from app.modules.onboarding.routes import _recorded_for_org
    from app.modules.onboarding.services import profile

    org = make_org("accept")
    profile.write(org, stage="pre_revenue", accepted_gaps={
        "roles:founder_ceo": {"reason": "Not yet", "at": "2026-01-01T00:00:00", "by_user_id": 1}
    })
    recorded = _recorded_for_org(org)

    assert "founder_ceo" not in recorded["roles"], (
        "an accepted gap must stay a gap, not be treated as recorded/filled"
    )


def test_gap_action_assign_marks_the_gap_recorded(app, db_session, make_org):
    from app.modules.onboarding.routes import _recorded_for_org
    from app.modules.onboarding.services import profile

    org = make_org("assign")
    profile.write(org, stage="pre_revenue", assigned_gaps={
        "roles:founder_ceo": {"assignee": "Jo", "at": "2026-01-01T00:00:00", "by_user_id": 1}
    })
    recorded = _recorded_for_org(org)

    assert "founder_ceo" in recorded["roles"], "an assigned gap should count as recorded"
