"""Regression tests for Business-Architect drafting assist:
    - POST /value-streams/api/<id>/ai-suggest-mappings
    - POST /business-model/api/<id>/ai-draft-block
    - POST /business-case/api/<id>/ai-draft-section

All three are advisory only: they never write to the database themselves.
Value-stream suggestions are applied through the grid's existing mapping
endpoint; BMC/business-case drafts are fed into the existing inline editors
and saved through the existing save endpoints. Uses the shared fixtures in
tests/conftest.py (db_session rolls everything back) and the logged-in-
client / auth-cache pattern from tests/test_arb_review_ai.py, per CLAUDE.md.
"""

from __future__ import annotations

import json
import uuid

import pytest


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_org(db_session, make_org, client):
    """A confirmed business_architect user in a fresh org, logged into the test client."""
    from app.models.user import User

    org = make_org("biz-arch-ai")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"biz-arch-ai-{suffix}@example.com",
        first_name="Biz",
        last_name="Architect",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="business_architect",
    )
    db_session.add(user)
    db_session.flush()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True

    _clear_auth_caches()
    return org, user


def _clear_auth_caches():
    """Anything that touches current_user on the shared app context
    re-caches an anonymous user in `g`; call this right before each
    test-client request."""
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _make_value_stream(db_session, org, **overrides):
    from app.models.unified_capability import ValueStream, ValueStreamStage

    suffix = uuid.uuid4().hex[:8]
    kwargs = dict(
        name=f"Order to Cash {suffix}",
        code=f"VS-{suffix}",
        description="From customer order to cash collection.",
        organization_id=org.id,
    )
    kwargs.update(overrides)
    vs = ValueStream(**kwargs)
    db_session.add(vs)
    db_session.flush()

    stage1 = ValueStreamStage(
        name="Order Capture",
        description="Capture the customer order.",
        value_stream_id=vs.id,
        stage_order=1,
        organization_id=org.id,
    )
    stage2 = ValueStreamStage(
        name="Fulfillment",
        description="Fulfill the order.",
        value_stream_id=vs.id,
        stage_order=2,
        organization_id=org.id,
    )
    db_session.add_all([stage1, stage2])
    db_session.flush()
    return vs, [stage1, stage2]


def _make_capability(db_session, name=None):
    from app.models.unified_capability import UnifiedCapability

    suffix = uuid.uuid4().hex[:8]
    cap = UnifiedCapability(
        name=name or f"Order Management {suffix}",
        code=f"CAP-{suffix}",
        level=1,
    )
    db_session.add(cap)
    db_session.flush()
    return cap


def _map_capability_to_value_stream(db_session, org, capability, value_stream, stage):
    """A tenant-scoped CapabilityValueStreamMapping row — this is what
    makes a capability show up in this org's AI-suggestion context (see
    value_stream_ai_service._org_scoped_capability_names). organization_id
    is set explicitly since these rows are built outside a live request
    (TenantMixin's auto-set-on-flush needs g.current_org_id)."""
    from app.models.unified_capability import CapabilityValueStreamMapping

    mapping = CapabilityValueStreamMapping(
        capability_id=capability.id,
        value_stream_id=value_stream.id,
        value_stream_stage_id=stage.id,
        organization_id=org.id,
    )
    db_session.add(mapping)
    db_session.flush()
    return mapping


def _make_canvas(db_session, org, **overrides):
    from app.models.business_model import BusinessModelCanvas

    suffix = uuid.uuid4().hex[:8]
    kwargs = dict(
        name=f"Canvas {suffix}",
        description="A test canvas.",
        organization_id=org.id,
        value_propositions="Faster onboarding for enterprise customers.",
    )
    kwargs.update(overrides)
    canvas = BusinessModelCanvas(**kwargs)
    db_session.add(canvas)
    db_session.flush()
    return canvas


def _make_business_case(db_session, org, user, **overrides):
    from app.models.business_case import BusinessCase

    suffix = uuid.uuid4().hex[:8]
    kwargs = dict(
        title=f"Case {suffix}",
        description="A test business case.",
        status="draft",
        organization_id=org.id,
        created_by_id=user.id,
        problem_statement="Manual invoicing is slow and error-prone.",
    )
    kwargs.update(overrides)
    case = BusinessCase(**kwargs)
    db_session.add(case)
    db_session.flush()
    return case


# ---------------------------------------------------------------------------
# 1. POST /value-streams/api/<id>/ai-suggest-mappings
# ---------------------------------------------------------------------------

_VS_VALID_LLM_JSON_TEMPLATE = (
    '{{"suggestions": [{{"stage": "{stage}", "capability": "{capability}", '
    '"rationale": "Directly supports this stage."}}], '
    '"summary": "One mapping suggested."}}'
)


def test_ai_suggest_mappings_happy_path(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    vs, stages = _make_value_stream(db_session, org)
    cap = _make_capability(db_session, name="Order Management")
    _map_capability_to_value_stream(db_session, org, cap, vs, stages[0])

    import app.modules.capabilities.services.value_stream_ai_service as svc_module

    raw = _VS_VALID_LLM_JSON_TEMPLATE.format(stage=stages[0].name, capability=cap.name)
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: raw)
    )

    from app.models.unified_capability import CapabilityValueStreamMapping

    before_count = CapabilityValueStreamMapping.query.count()

    _clear_auth_caches()
    resp = client.post(f"/value-streams/api/{vs.id}/ai-suggest-mappings")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["suggestions"] == [
        {"stage": stages[0].name, "capability": cap.name, "rationale": "Directly supports this stage."}
    ]
    assert data["summary"] == "One mapping suggested."

    # Advisory only: nothing was written to the mapping table.
    after_count = CapabilityValueStreamMapping.query.count()
    assert after_count == before_count


def test_ai_suggest_mappings_llm_failure_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    vs, stages = _make_value_stream(db_session, org)
    cap = _make_capability(db_session, name="Order Management")
    _map_capability_to_value_stream(db_session, org, cap, vs, stages[0])

    import app.modules.capabilities.services.value_stream_ai_service as svc_module

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(_boom))

    _clear_auth_caches()
    resp = client.post(f"/value-streams/api/{vs.id}/ai-suggest-mappings")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_suggest_mappings_unparseable_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    vs, stages = _make_value_stream(db_session, org)
    cap = _make_capability(db_session, name="Order Management")
    _map_capability_to_value_stream(db_session, org, cap, vs, stages[0])

    import app.modules.capabilities.services.value_stream_ai_service as svc_module

    monkeypatch.setattr(
        svc_module.LLMService,
        "generate_from_prompt",
        staticmethod(lambda *a, **k: "not json at all"),
    )

    _clear_auth_caches()
    resp = client.post(f"/value-streams/api/{vs.id}/ai-suggest-mappings")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_suggest_mappings_no_org_capabilities_is_200_without_llm(
    db_session, make_org, logged_in_org, client, monkeypatch
):
    """No tenant-scoped capability mapping in this org yet — the route must
    short-circuit to 200-with-null and never call the LLM at all (nothing to
    suggest against, and no reason to touch an external model)."""
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    vs, stages = _make_value_stream(db_session, org)
    # A UnifiedCapability exists in the shared catalog, but this org has
    # never mapped it anywhere — so it must not appear in the context.
    _make_capability(db_session, name="Order Management")

    import app.modules.capabilities.services.value_stream_ai_service as svc_module

    calls = []
    monkeypatch.setattr(
        svc_module.LLMService,
        "generate_from_prompt",
        staticmethod(lambda *a, **k: calls.append(1)),
    )

    _clear_auth_caches()
    resp = client.post(f"/value-streams/api/{vs.id}/ai-suggest-mappings")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["suggestions"] is None
    assert "message" in data
    assert calls == []


def test_ai_suggest_mappings_drops_invented_pairs(db_session, make_org, logged_in_org, client, monkeypatch):
    """The LLM naming a stage/capability outside the real context is dropped;
    if every suggestion is invented, that's a 502 (never a fabricated fallback)."""
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    vs, stages = _make_value_stream(db_session, org)
    cap = _make_capability(db_session, name="Order Management")
    _map_capability_to_value_stream(db_session, org, cap, vs, stages[0])

    import app.modules.capabilities.services.value_stream_ai_service as svc_module

    raw = json.dumps(
        {
            "suggestions": [
                {
                    "stage": "A Stage That Does Not Exist",
                    "capability": "A Capability That Does Not Exist",
                    "rationale": "Invented.",
                }
            ],
            "summary": "Invented mapping.",
        }
    )
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: raw)
    )

    _clear_auth_caches()
    resp = client.post(f"/value-streams/api/{vs.id}/ai-suggest-mappings")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_suggest_mappings_unknown_id_is_404(logged_in_org, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    _clear_auth_caches()
    resp = client.post("/value-streams/api/999999999/ai-suggest-mappings")
    assert resp.status_code == 404


def test_ai_suggest_mappings_disabled_is_503(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: False)

    vs, stages = _make_value_stream(db_session, org)

    _clear_auth_caches()
    resp = client.post(f"/value-streams/api/{vs.id}/ai-suggest-mappings")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 2. POST /business-model/api/<id>/ai-draft-block
# ---------------------------------------------------------------------------

_BMC_VALID_LLM_JSON = json.dumps(
    {
        "content": "Enterprise customers\nMid-market resellers",
        "based_on": ["value_propositions"],
    }
)


def test_ai_draft_block_happy_path(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    canvas = _make_canvas(db_session, org)

    import app.modules.business_model_canvas.ai_service as svc_module

    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: _BMC_VALID_LLM_JSON)
    )

    _clear_auth_caches()
    resp = client.post(
        f"/business-model/api/{canvas.id}/ai-draft-block",
        json={"block": "customer_segments"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    draft = data["draft"]
    assert draft["block"] == "customer_segments"
    assert draft["content"] == "Enterprise customers\nMid-market resellers"
    assert draft["based_on"] == ["value_propositions"]

    # Advisory only: nothing was written to the canvas block.
    db_session.refresh(canvas)
    assert canvas.customer_segments is None


def test_ai_draft_block_llm_failure_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    canvas = _make_canvas(db_session, org)

    import app.modules.business_model_canvas.ai_service as svc_module

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(_boom))

    _clear_auth_caches()
    resp = client.post(
        f"/business-model/api/{canvas.id}/ai-draft-block",
        json={"block": "customer_segments"},
    )
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_draft_block_unparseable_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    canvas = _make_canvas(db_session, org)

    import app.modules.business_model_canvas.ai_service as svc_module

    monkeypatch.setattr(
        svc_module.LLMService,
        "generate_from_prompt",
        staticmethod(lambda *a, **k: "not json at all"),
    )

    _clear_auth_caches()
    resp = client.post(
        f"/business-model/api/{canvas.id}/ai-draft-block",
        json={"block": "customer_segments"},
    )
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_draft_block_invalid_block_key_is_400(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    canvas = _make_canvas(db_session, org)

    _clear_auth_caches()
    resp = client.post(
        f"/business-model/api/{canvas.id}/ai-draft-block",
        json={"block": "not_a_real_block"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_ai_draft_block_unknown_id_is_404(logged_in_org, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    _clear_auth_caches()
    resp = client.post(
        "/business-model/api/999999999/ai-draft-block",
        json={"block": "customer_segments"},
    )
    assert resp.status_code == 404


def test_ai_draft_block_disabled_is_503(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: False)

    canvas = _make_canvas(db_session, org)

    _clear_auth_caches()
    resp = client.post(
        f"/business-model/api/{canvas.id}/ai-draft-block",
        json={"block": "customer_segments"},
    )
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 3. POST /business-case/api/<id>/ai-draft-section
# ---------------------------------------------------------------------------

_BC_VALID_LLM_JSON = json.dumps(
    {
        "content": "Consolidate onto a single billing platform.",
        "based_on": ["problem_statement"],
    }
)


def test_ai_draft_section_happy_path(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    case = _make_business_case(db_session, org, user)

    import app.modules.business_case.ai_service as svc_module

    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: _BC_VALID_LLM_JSON)
    )

    _clear_auth_caches()
    resp = client.post(
        f"/business-case/api/{case.id}/ai-draft-section",
        json={"section": "recommended_option"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    draft = data["draft"]
    assert draft["section"] == "recommended_option"
    assert draft["content"] == "Consolidate onto a single billing platform."
    assert draft["based_on"] == ["problem_statement"]

    # Advisory only: nothing was written to the business case section.
    db_session.refresh(case)
    assert case.recommended_option is None


def test_ai_draft_section_llm_failure_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    case = _make_business_case(db_session, org, user)

    import app.modules.business_case.ai_service as svc_module

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(_boom))

    _clear_auth_caches()
    resp = client.post(
        f"/business-case/api/{case.id}/ai-draft-section",
        json={"section": "recommended_option"},
    )
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_draft_section_unparseable_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    case = _make_business_case(db_session, org, user)

    import app.modules.business_case.ai_service as svc_module

    monkeypatch.setattr(
        svc_module.LLMService,
        "generate_from_prompt",
        staticmethod(lambda *a, **k: "not json at all"),
    )

    _clear_auth_caches()
    resp = client.post(
        f"/business-case/api/{case.id}/ai-draft-section",
        json={"section": "recommended_option"},
    )
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_draft_section_invalid_section_key_is_400(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    case = _make_business_case(db_session, org, user)

    _clear_auth_caches()
    resp = client.post(
        f"/business-case/api/{case.id}/ai-draft-section",
        json={"section": "not_a_real_section"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_ai_draft_section_unknown_id_is_404(logged_in_org, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    _clear_auth_caches()
    resp = client.post(
        "/business-case/api/999999999/ai-draft-section",
        json={"section": "recommended_option"},
    )
    assert resp.status_code == 404


def test_ai_draft_section_disabled_is_503(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: False)

    case = _make_business_case(db_session, org, user)

    _clear_auth_caches()
    resp = client.post(
        f"/business-case/api/{case.id}/ai-draft-section",
        json={"section": "recommended_option"},
    )
    assert resp.status_code == 503
