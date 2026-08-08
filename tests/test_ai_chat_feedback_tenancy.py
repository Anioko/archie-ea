"""Feedback rows must not be readable across organisations.

``AIChatFeedback.message_text`` stores the assistant's reply, which is portfolio
content. The model previously had no ``TenantMixin`` and no ``organization_id``,
so it sat outside the ``do_orm_execute`` filter entirely and the feedback
analytics dashboard aggregated every organisation's answers together.

Written against the shared fixtures in ``tests/conftest.py`` — see
``tests/test_tenant_isolation.py`` for the reference pattern.
"""

from app.models.ai_chat_feedback import AIChatFeedback


def _make_feedback(db_session, org_id, message_text, rating="up"):
    row = AIChatFeedback(
        organization_id=org_id,
        user_id=1,
        rating=rating,
        domain="architecture",
        persona="enterprise_architect",
        message_text=message_text,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_feedback_select_is_scoped_to_current_org(db_session, make_org, tenant_ctx):
    """Org A must not see org B's feedback rows."""
    org_a, org_b = make_org("a"), make_org("b")
    _make_feedback(db_session, org_a.id, "A's answer")
    b_row = _make_feedback(db_session, org_b.id, "B's portfolio detail")

    with tenant_ctx(org_a.id):
        visible = AIChatFeedback.query.all()
        visible_ids = {row.id for row in visible}

    assert b_row.id not in visible_ids, (
        "TENANT LEAK: org A's context returned org B's feedback row, which "
        "contains the assistant's answer about org B's portfolio."
    )
    assert all(row.organization_id == org_a.id for row in visible), (
        "TENANT LEAK: query returned feedback belonging to another organization."
    )


def test_feedback_cannot_be_reached_by_filtering_on_a_foreign_id(
    db_session, make_org, tenant_ctx
):
    """Explicitly filtering by another org's row id must still return nothing."""
    org_a, org_b = make_org("a"), make_org("b")
    b_row = _make_feedback(db_session, org_b.id, "B's portfolio detail")

    db_session.expunge_all()

    with tenant_ctx(org_a.id):
        found = AIChatFeedback.query.filter_by(id=b_row.id).first()

    assert found is None, (
        f"TENANT LEAK: org A retrieved org B's feedback row (id={b_row.id}) "
        "by filtering on its id."
    )


def test_feedback_insert_inherits_current_org(db_session, make_org, tenant_ctx):
    """A row written without an explicit org must inherit the request's org.

    This is the path the /ai-chat/feedback endpoint takes: it does not pass
    organization_id, relying on the tenant before_flush to set it.
    """
    org_a = make_org("a")

    with tenant_ctx(org_a.id):
        row = AIChatFeedback(
            user_id=1,
            rating="down",
            domain="architecture",
            persona="enterprise_architect",
            message_text="answer text",
        )
        db_session.add(row)
        db_session.flush()

        assert row.organization_id == org_a.id, (
            "The tenant before_flush did not set organization_id on insert, so "
            "the feedback endpoint would write unattributed rows."
        )


def test_the_endpoint_actually_writes_a_row(app, db_session, make_org):
    """POST /ai-chat/feedback must persist, and must not lie when it cannot.

    The other tests in this file construct AIChatFeedback directly, so they pass
    whether or not the endpoint works — they would have passed against the raw
    INSERT that referenced a column no model declared, raised UndefinedColumn on
    every call, swallowed it, and returned {"success": true} for a write that
    never happened. This test exercises the route.
    """
    from flask import g

    from app.extensions import db
    from app.models.ai_chat_feedback import AIChatFeedback
    from app.models.user import User

    org = make_org("fb-endpoint")
    user = User(
        email=f"fb-{org.id}@example.com", first_name="Fb", last_name="Probe",
        organization_id=org.id, confirmed=True,
    )
    user.password = "probe-password-123"
    db_session.add(user)
    db_session.flush()

    marker = f"answer text {org.id}"
    # A real request body: the view reads `request.json`, which is a property, so
    # it cannot be patched from outside — the context has to carry the payload.
    with app.test_request_context(
        "/ai-chat/feedback",
        method="POST",
        json={
            "rating": "up",
            "domain": "architecture",
            "persona": "enterprise_architect",
            "message_text": marker,
        },
    ):
        from flask_login import login_user

        g.current_org_id = org.id
        login_user(user)

        from app.modules.ai_chat.routes.chat_core import submit_message_feedback

        response = submit_message_feedback()

    payload = response[0].get_json() if isinstance(response, tuple) else response.get_json()
    status = response[1] if isinstance(response, tuple) else 200

    assert status == 200 and payload.get("success") is True, (
        f"the endpoint reported {status} {payload} — if it reports success, a row must exist"
    )

    rows = db.session.query(AIChatFeedback).filter_by(message_text=marker).all()
    assert len(rows) == 1, (
        "the endpoint returned success and wrote nothing. That is the exact "
        "failure this endpoint shipped with: a bare except that swallowed "
        "UndefinedColumn and reported success anyway."
    )
    assert rows[0].organization_id == org.id, "the written row was not attributed to the org"
