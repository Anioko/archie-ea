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
