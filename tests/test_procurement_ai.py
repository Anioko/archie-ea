"""Regression tests for the Procurement AI assist endpoints.

Four advisory endpoints: a per-contract renewal brief, a per-licence
compliance remediation plan, an org-wide licence position summary, and
org-wide spend recommendations. All four are advisory only - nothing is
written back to the underlying rows - and are gated behind
FeatureFlagService plus the same @requires_procurement role check the rest
of this module uses.

Uses the shared fixtures in tests/conftest.py (db_session rolls everything
back) and the logged-in-client / auth-cache pattern from
tests/test_arb_review_ai.py and tests/test_procurement_pages.py.
"""

from __future__ import annotations

import datetime as _dt
import json
import uuid

import pytest


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def procurement_user(db_session, make_org, client):
    """A confirmed procurement-role user in a fresh org, logged into the test client."""
    from app.models.user import User

    org = make_org("procurement-ai")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"procurement-ai-{suffix}@example.com",
        first_name="Procurement",
        last_name="AI",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="procurement",
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


def _make_contract(db_session, org, **overrides):
    from app.models.application_portfolio import VendorContract

    suffix = uuid.uuid4().hex[:8]
    kwargs = dict(
        organization_id=org.id,
        contract_name=f"Contract {suffix}",
        contract_number=f"CN-{suffix}",
        status="active",
        contract_type="subscription",
        contract_category="software",
        contract_value=100000.0,
        annual_cost=50000.0,
        currency="USD",
        start_date=_dt.date.today() - _dt.timedelta(days=300),
        end_date=_dt.date.today() + _dt.timedelta(days=20),
        renewal_date=_dt.date.today() + _dt.timedelta(days=20),
    )
    kwargs.update(overrides)
    contract = VendorContract(**kwargs)
    db_session.add(contract)
    db_session.flush()
    return contract


def _make_license(db_session, org, contract, **overrides):
    from app.models.license_entitlement import LicenseEntitlement

    kwargs = dict(
        organization_id=org.id,
        contract_id=contract.id,
        product_name="Widget Suite",
        license_type="named_user",
        quantity_entitled=100,
        quantity_deployed=120,
        quantity_used=90,
        compliance_status="over_deployed",
    )
    kwargs.update(overrides)
    lic = LicenseEntitlement(**kwargs)
    db_session.add(lic)
    db_session.flush()
    return lic


_BRIEF_JSON = json.dumps(
    {
        "summary": "The contract renews in 20 days with moderate over-deployment risk.",
        "stance": "renegotiate",
        "leverage_points": ["Long tenure with vendor", "Under-utilized seats elsewhere"],
        "risks": ["Price escalation on renewal"],
        "questions_for_vendor": ["Can true-up pricing be locked for 2 years?"],
        "rationale": "Renegotiating captures leverage from tenure while addressing over-deployment.",
    }
)

_REMEDIATION_JSON = json.dumps(
    {
        "summary": "This licence is over-deployed by 20 seats against entitlement.",
        "options": [
            {"option": "Purchase true-up seats", "tradeoff": "Immediate cost, stays compliant"},
            {"option": "Reclaim unused seats", "tradeoff": "No cost, requires deployment audit"},
        ],
        "recommended_option": "Reclaim unused seats",
        "rationale": "Deployment audit likely finds inactive seats before a true-up is needed.",
    }
)

_POSITION_JSON = json.dumps(
    {
        "summary": "One licence is over-deployed; overall entitlement usage is otherwise healthy.",
        "anomalies": ["Widget Suite is over-deployed by 20 seats"],
        "recommended_actions": ["Run a deployment audit for Widget Suite"],
    }
)

_SPEND_JSON = json.dumps(
    {
        "summary": "Software spend dominates the portfolio.",
        "recommendations": [
            {"title": "Consolidate software vendors", "detail": "Two vendors overlap in capability.", "category": "software"}
        ],
    }
)


# ---------------------------------------------------------------------------
# 1. Renewal brief
# ---------------------------------------------------------------------------


def test_renewal_brief_happy_path(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module
    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: _BRIEF_JSON))

    contract = _make_contract(db_session, org)
    _clear_auth_caches()

    resp = client.post(f"/procurement/api/contracts/{contract.id}/ai-renewal-brief")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    brief = resp.get_json()["brief"]
    assert brief["stance"] == "renegotiate"
    assert brief["leverage_points"] == ["Long tenure with vendor", "Under-utilized seats elsewhere"]

    # Advisory only: the contract row is unchanged.
    db_session.refresh(contract)
    assert contract.status == "active"
    assert contract.contract_name.startswith("Contract ")


def test_renewal_brief_llm_failure_is_502(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(_boom))

    contract = _make_contract(db_session, org)
    _clear_auth_caches()

    resp = client.post(f"/procurement/api/contracts/{contract.id}/ai-renewal-brief")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_renewal_brief_unparseable_is_502(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: "not json at all")
    )

    contract = _make_contract(db_session, org)
    _clear_auth_caches()

    resp = client.post(f"/procurement/api/contracts/{contract.id}/ai-renewal-brief")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_renewal_brief_unknown_contract_is_404(procurement_user, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    _clear_auth_caches()
    resp = client.post("/procurement/api/contracts/999999999/ai-renewal-brief")
    assert resp.status_code == 404


def test_renewal_brief_disabled_is_503(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: False)

    contract = _make_contract(db_session, org)
    _clear_auth_caches()

    resp = client.post(f"/procurement/api/contracts/{contract.id}/ai-renewal-brief")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 2. Compliance remediation
# ---------------------------------------------------------------------------


def test_remediation_happy_path(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: _REMEDIATION_JSON)
    )

    contract = _make_contract(db_session, org)
    lic = _make_license(db_session, org, contract)
    _clear_auth_caches()

    resp = client.post(f"/procurement/api/compliance/violations/{lic.id}/ai-remediation")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    remediation = resp.get_json()["remediation"]
    assert remediation["recommended_option"] == "Reclaim unused seats"
    assert remediation["recommended_option"] in [o["option"] for o in remediation["options"]]

    # Advisory only: the licence row is unchanged.
    db_session.refresh(lic)
    assert lic.compliance_status == "over_deployed"
    assert lic.quantity_deployed == 120


def test_remediation_llm_failure_is_502(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(_boom))

    contract = _make_contract(db_session, org)
    lic = _make_license(db_session, org, contract)
    _clear_auth_caches()

    resp = client.post(f"/procurement/api/compliance/violations/{lic.id}/ai-remediation")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_remediation_unparseable_is_502(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: "not json at all")
    )

    contract = _make_contract(db_session, org)
    lic = _make_license(db_session, org, contract)
    _clear_auth_caches()

    resp = client.post(f"/procurement/api/compliance/violations/{lic.id}/ai-remediation")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_remediation_recommended_option_not_in_options_is_502(db_session, procurement_user, client, monkeypatch):
    """The parser enforces recommended_option must be one of options[].option."""
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    bad_json = json.dumps(
        {
            "summary": "x",
            "options": [{"option": "A", "tradeoff": "t"}],
            "recommended_option": "Not an offered option",
            "rationale": "x",
        }
    )
    import app.modules.procurement.procurement_ai_service as svc_module
    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: bad_json))

    contract = _make_contract(db_session, org)
    lic = _make_license(db_session, org, contract)
    _clear_auth_caches()

    resp = client.post(f"/procurement/api/compliance/violations/{lic.id}/ai-remediation")
    assert resp.status_code == 502


def test_remediation_unknown_license_is_404(procurement_user, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    _clear_auth_caches()
    resp = client.post("/procurement/api/compliance/violations/999999999/ai-remediation")
    assert resp.status_code == 404


def test_remediation_disabled_is_503(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: False)

    contract = _make_contract(db_session, org)
    lic = _make_license(db_session, org, contract)
    _clear_auth_caches()

    resp = client.post(f"/procurement/api/compliance/violations/{lic.id}/ai-remediation")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 3. Licence position (org-wide, no id)
# ---------------------------------------------------------------------------


def test_licenses_position_happy_path(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: _POSITION_JSON)
    )

    contract = _make_contract(db_session, org)
    _make_license(db_session, org, contract)
    _clear_auth_caches()

    resp = client.post("/procurement/api/licenses/ai-position")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    position = resp.get_json()["position"]
    assert position["anomalies"] == ["Widget Suite is over-deployed by 20 seats"]


def test_licenses_position_llm_failure_is_502(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(_boom))
    _clear_auth_caches()

    resp = client.post("/procurement/api/licenses/ai-position")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_licenses_position_unparseable_is_502(db_session, procurement_user, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: "not json at all")
    )
    _clear_auth_caches()

    resp = client.post("/procurement/api/licenses/ai-position")
    assert resp.status_code == 502


def test_licenses_position_disabled_is_503(procurement_user, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: False)

    _clear_auth_caches()
    resp = client.post("/procurement/api/licenses/ai-position")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 4. Spend recommendations (org-wide, no id)
# ---------------------------------------------------------------------------


def test_spend_recommendations_happy_path(db_session, procurement_user, client, monkeypatch):
    org, user = procurement_user
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: _SPEND_JSON)
    )

    _make_contract(db_session, org)
    _clear_auth_caches()

    resp = client.post("/procurement/api/spend/ai-recommendations")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["summary"] == "Software spend dominates the portfolio."
    assert body["recommendations"][0]["category"] == "software"


def test_spend_recommendations_llm_failure_is_502(db_session, procurement_user, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(_boom))
    _clear_auth_caches()

    resp = client.post("/procurement/api/spend/ai-recommendations")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_spend_recommendations_unparseable_is_502(procurement_user, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.procurement.procurement_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: "not json at all")
    )
    _clear_auth_caches()

    resp = client.post("/procurement/api/spend/ai-recommendations")
    assert resp.status_code == 502


def test_spend_recommendations_disabled_is_503(procurement_user, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: False)

    _clear_auth_caches()
    resp = client.post("/procurement/api/spend/ai-recommendations")
    assert resp.status_code == 503
