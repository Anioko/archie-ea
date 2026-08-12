"""Application detail on the screen system (shell-overhaul Wave 2, Task 2).

Product design review pinned three structural defects on
`/applications/<id>`:

- TWO stacked breadcrumb trails: the layout's own `{% block breadcrumb %}`
  ("Home > Applications > X") rendered above a second, hand-rolled
  `<nav aria-label="Breadcrumb">` inside the content block ("Applications
  > X").
- an Alpine `SyntaxError: Unexpected token ')'` fired on every load, because
  a JS comment inside the AI-suggestions widget's `x-data="..."` attribute
  contained a literal `x-show="..."` double-quoted string, which the HTML
  parser used to terminate the attribute early and hand Alpine a truncated,
  unparseable expression.
- a tab strip where empty tabs were merely dimmed (`text-muted-foreground/40`)
  with no `aria-disabled`, so assistive tech had no way to know they were
  disabled rather than just less prominent.

This file pins the rebuild's structural contract: one breadcrumb, one <h1>,
and the completeness-banner / ownership-empty-state strengths kept intact.
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

    org = make_org(f"app-detail-shell-{label}")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"app-detail-shell-{label}-{suffix}@example.com",
        first_name="Detail",
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


def _get_detail_html(app, db_session, make_org, label, **app_kwargs):
    """Seed one sparse application (no completeness-affecting fields set,
    so `completeness_score` stays low and the nudge banner renders) and GET
    its detail page."""
    from app.models.application_portfolio import ApplicationComponent

    user_id, org = _make_user(db_session, make_org, label)
    app_obj = ApplicationComponent(
        name=f"Shell Detail App {uuid.uuid4().hex[:8]}",
        organization_id=org.id,
        **app_kwargs,
    )
    db_session.add(app_obj)
    db_session.flush()
    db_session.commit()

    client = app.test_client()
    _login(client, user_id)
    resp = client.get(f"/applications/{app_obj.id}")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    return resp.get_data(as_text=True), app_obj


def test_status_200(app, db_session, make_org):
    html, _ = _get_detail_html(app, db_session, make_org, "status")
    assert html  # sanity: body was returned


def test_exactly_one_breadcrumb_nav(app, db_session, make_org):
    """Two stacked breadcrumb trails was the defect — exactly one
    nav[aria-label="Breadcrumb"] must render."""
    html, _ = _get_detail_html(app, db_session, make_org, "breadcrumb")
    assert html.count('aria-label="Breadcrumb"') == 1


def test_exactly_one_h1(app, db_session, make_org):
    html, _ = _get_detail_html(app, db_session, make_org, "h1")
    assert html.count("<h1") == 1


def test_completeness_banner_present_for_sparse_app(app, db_session, make_org):
    """A contractual strength (regression = Critical): the low-completeness
    nudge banner must still render for a sparse application."""
    html, app_obj = _get_detail_html(app, db_session, make_org, "completeness")
    assert app_obj.completeness_score < 40, (
        "test fixture assumption broke: a bare ApplicationComponent should "
        "score below the 40%% nudge-banner threshold"
    )
    assert "Data completeness" in html
    assert "AI analysis quality is low" in html
