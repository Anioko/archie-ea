"""LLMInteraction records the organisation a language-model call was made for.

TB-0098 (this slice): the row needs an organisation so a later budget check can
be scoped per organisation instead of summing every tenant's spend together.
The budget check itself is handled separately; this only covers what gets
written to ``llm_interactions``.

Security fix (F-4 follow-up): three logged-in, no-admin-check reads used to
answer with every organisation's language-model activity combined. Every real
row is written through a direct ``LLMInteraction(...)`` constructor (in
``llm_service_impl.py``, ``multi_modal_llm_service.py``, ``document_processor.py``
and ``document_analysis_service.py``) or through ``LLMService.log_decision`` --
``LLMCostTracker.track_interaction`` has no caller in this codebase. The tests
below write rows the same way production does, then prove the three fixed
reads answer from the caller's own organisation only:

  - ``GET /ai-chat/analytics/domains``
  - ``GET /ai-chat/analytics/quality``
  - ``LLMService.get_decision_log`` (service level -- the route
    ``/api/agentic-gaps/decision-logs`` always returns ``[]`` regardless of
    this fix, because it reads a ``project_id`` column ``LLMInteraction``
    does not have; that is a pre-existing bug, out of scope here).
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org, email=None):
    from app.models.user import Role, User

    role = Role.query.filter_by(name="Administrator").first()
    if role is None:
        Role.insert_roles()
        role = Role.query.filter_by(name="Administrator").first()

    user = User(
        email=email or f"llm-spend-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="User",
        organization_id=org.id,
        role=role,
        confirmed=True,
    )
    user.password = uuid.uuid4().hex
    db_session.add(user)
    db_session.flush()
    return user


def _write_interaction(db_session, org, *, provider, response="ok", **kwargs):
    """Write a row the way production does: a direct constructor call, not
    through LLMCostTracker.track_interaction (which nothing calls)."""
    from app.models import LLMInteraction

    interaction = LLMInteraction(
        provider=provider,
        model_name="claude-opus-5",
        response=response,
        organization_id=org.id,
        **kwargs,
    )
    db_session.add(interaction)
    db_session.flush()
    return interaction


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


class TestDomainAndQualityAnalyticsAreScopedToTheCallersOrganisation:
    """F-4 follow-up: /ai-chat/analytics/domains and /ai-chat/analytics/quality
    used to sum every organisation's LLMInteraction rows together and answer
    any logged-in caller with the combined total. Each assertion here fails on
    origin/main, where organization_id does not exist at all and every row
    (from every organisation) is counted for every caller.
    """

    def test_domain_analytics_answers_only_the_callers_organisation(
        self, app, db_session, make_org, login_as, client
    ):
        org_a = make_org("domain-a")
        org_b = make_org("domain-b")
        user_a = _make_user(db_session, org_a)
        user_b = _make_user(db_session, org_b)

        for _ in range(3):
            _write_interaction(db_session, org_a, provider="openai")
        for _ in range(5):
            _write_interaction(db_session, org_b, provider="anthropic")

        login_as(client, user_a)
        resp_a = client.get("/ai-chat/analytics/domains")
        assert resp_a.status_code == 200
        domains_a = {d["domain"]: d["message_count"] for d in resp_a.get_json()["analytics"]["domains"]}
        assert domains_a.get("openai") == 3
        assert "anthropic" not in domains_a

        login_as(client, user_b)
        resp_b = client.get("/ai-chat/analytics/domains")
        assert resp_b.status_code == 200
        domains_b = {d["domain"]: d["message_count"] for d in resp_b.get_json()["analytics"]["domains"]}
        assert domains_b.get("anthropic") == 5
        assert "openai" not in domains_b

    def test_quality_metrics_answers_only_the_callers_organisation(
        self, app, db_session, make_org, login_as, client
    ):
        org_a = make_org("quality-a")
        org_b = make_org("quality-b")
        user_a = _make_user(db_session, org_a)
        user_b = _make_user(db_session, org_b)

        for _ in range(2):
            _write_interaction(db_session, org_a, provider="openai")
        for _ in range(7):
            _write_interaction(db_session, org_b, provider="anthropic")

        login_as(client, user_a)
        resp_a = client.get("/ai-chat/analytics/quality")
        assert resp_a.status_code == 200
        assert resp_a.get_json()["metrics"]["total_interactions"] == 2

        login_as(client, user_b)
        resp_b = client.get("/ai-chat/analytics/quality")
        assert resp_b.status_code == 200
        assert resp_b.get_json()["metrics"]["total_interactions"] == 7


class TestDecisionLogIsScopedToTheCallersOrganisation:
    """F-4 follow-up, service level: the route (/api/agentic-gaps/decision-logs)
    always returns [] because get_decision_log's project_id filter reads a
    column LLMInteraction does not have (pre-existing bug, not fixed here) --
    so this proves the fix directly against LLMService.get_decision_log.
    """

    def test_get_decision_log_returns_only_the_current_organisations_decisions(
        self, db_session, make_org, tenant_ctx
    ):
        from app.modules.ai_chat.services.llm_service_impl import LLMService

        org_a = make_org("decision-a")
        org_b = make_org("decision-b")

        with tenant_ctx(org_a.id):
            LLMService.log_decision(
                decision_type="gap_analysis",
                context={"gap_id": 1},
                decision={"recommendation": "org-a-decision"},
                rationale="org A's own decision",
            )
        with tenant_ctx(org_b.id):
            LLMService.log_decision(
                decision_type="gap_analysis",
                context={"gap_id": 2},
                decision={"recommendation": "org-b-decision"},
                rationale="org B's own decision",
            )
        db_session.flush()

        with tenant_ctx(org_a.id):
            logs_a = LLMService.get_decision_log()
        recommendations_a = {log["decision"].get("recommendation") for log in logs_a}
        assert "org-a-decision" in recommendations_a
        assert "org-b-decision" not in recommendations_a

        with tenant_ctx(org_b.id):
            logs_b = LLMService.get_decision_log()
        recommendations_b = {log["decision"].get("recommendation") for log in logs_b}
        assert "org-b-decision" in recommendations_b
        assert "org-a-decision" not in recommendations_b
