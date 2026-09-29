"""LLMInteraction records the organisation a language-model call was made for.

The row needs an organisation so a later budget check can be scoped per
organisation instead of summing every tenant's spend together. The budget
check itself is handled separately; this only covers what gets written to
``llm_interactions``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _track(db_session, **kwargs):
    from app.modules.ai_chat.services.llm_cost_tracker import LLMCostTracker

    tracker = LLMCostTracker()
    tracker.track_interaction(
        model_name="claude-opus-5",
        provider="anthropic",
        input_tokens=100,
        output_tokens=50,
        **kwargs,
    )
    db_session.flush()

    from app.models import LLMInteraction

    return LLMInteraction.query.order_by(LLMInteraction.id.desc()).first()


def test_interaction_tracked_in_organisation_context_records_that_organisation(
    db_session, make_org, tenant_ctx
):
    org_b = make_org("b")

    with tenant_ctx(org_b.id):
        interaction = _track(db_session)

    assert interaction.organization_id == org_b.id


def test_interaction_tracked_with_no_organisation_context_records_null(
    db_session, app
):
    with app.test_request_context("/"):
        interaction = _track(db_session)

    assert interaction.organization_id is None


def test_explicit_organisation_argument_is_recorded(db_session, make_org):
    org = make_org("explicit")

    interaction = _track(db_session, organization_id=org.id)

    assert interaction.organization_id == org.id
