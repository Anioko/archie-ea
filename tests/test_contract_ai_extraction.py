"""AI clause extraction for vendor contracts.

POST /procurement/api/contracts/ai-extract
(app/modules/procurement/crud_routes.py::contract_ai_extract, backed by
app/modules/procurement/contract_extraction_service.py::extract_contract_terms).

Covers:
- happy path: mocked LLM JSON -> extracted fields, with fields absent from the
  text (or absent from the model's response) coming back null - never a
  fabricated value (CLAUDE.md never-invent-data rule).
- LLM failure -> 502 with the real error message, no fabricated body.
- empty text -> 400.
- AI disabled (the default under the test config) -> 503.

Uses the shared fixtures in tests/conftest.py (db_session rolls back) plus the
_clear_auth_caches pattern from tests/test_bounded_ai_endpoints.py - anything
that touches current_user on the shared app context re-caches an anonymous
user in `g`, so it has to be cleared right before every client request.
"""

from __future__ import annotations

import json
import uuid

import pytest


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_procurement(db_session, make_org, client):
    """A confirmed Procurement-role user in a fresh org, logged into the test client."""
    from app.models.user import User

    org = make_org("contract-ai-extract")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"procurement-{suffix}@example.com",
        first_name="Procurement",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="procurement",
    )
    db_session.add(user)
    db_session.flush()
    # Committed, not just flushed - a lazy load off this row elsewhere in the
    # request (e.g. flask-login re-fetching the user) can otherwise fail
    # against the rolled-back-on-teardown transaction. See
    # tests/test_ai_wiring_ui.py for the same note.
    db_session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True

    _clear_auth_caches()
    return org


def _clear_auth_caches():
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)


ENDPOINT = "/procurement/api/contracts/ai-extract"

SAMPLE_TEXT = (
    "MASTER SERVICES AGREEMENT between Acme Corp and Contoso Ltd.\n"
    "Contract No: MSA-2026-0042.\n"
    "Effective start date: 2026-01-01. Term ends 2027-12-31.\n"
    "This agreement renews automatically unless either party gives 90 days "
    "written notice prior to the end of the then-current term.\n"
    "Total contract value: USD 250,000. Payment terms: Net 30.\n"
    "Either party may terminate for uncured material breach with 30 days cure period.\n"
    "Liability is capped at fees paid in the preceding 12 months."
)

FAKE_LLM_JSON = {
    "contract_name": "Master Services Agreement",
    "contract_number": "MSA-2026-0042",
    "vendor_name": "Contoso Ltd",
    "start_date": "2026-01-01",
    "end_date": "2027-12-31",
    "renewal_date": None,
    "notice_period_days": 90,
    "auto_renewal": True,
    "contract_value": 250000,
    "currency": "USD",
    "payment_terms": "Net 30",
    "termination_clause_summary": "Either party may terminate for uncured material breach with a 30 day cure period.",
    "liability_cap": "Fees paid in the preceding 12 months",
    "risk_flags": None,
}


def _patch_llm(monkeypatch, *, returns=None, raises=None):
    import app.modules.procurement.contract_extraction_service as svc_module

    def _fake_generate_from_prompt(prompt, **kwargs):
        if raises is not None:
            raise raises
        return json.dumps(returns)

    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(_fake_generate_from_prompt)
    )


def _enable_ai(monkeypatch):
    import app.services.feature_flag_service as ffs_module

    monkeypatch.setattr(ffs_module.FeatureFlagService, "is_ai_enabled", staticmethod(lambda feature="all": True))


# --------------------------------------------------------------- happy path


def test_extract_happy_path_returns_stated_fields_and_nulls_the_rest(
    client, logged_in_procurement, db_session, monkeypatch
):
    _enable_ai(monkeypatch)
    _patch_llm(monkeypatch, returns=FAKE_LLM_JSON)

    _clear_auth_caches()
    resp = client.post(ENDPOINT, json={"text": SAMPLE_TEXT})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    extracted = body["extracted"]

    assert extracted["contract_number"] == "MSA-2026-0042"
    assert extracted["vendor_name"] == "Contoso Ltd"
    assert extracted["start_date"] == "2026-01-01"
    assert extracted["end_date"] == "2027-12-31"
    assert extracted["notice_period_days"] == 90
    assert extracted["auto_renewal"] is True
    assert extracted["contract_value"] == 250000.0
    assert extracted["currency"] == "USD"
    # Never fabricated: the model said null, so the API says null too.
    assert extracted["renewal_date"] is None
    assert extracted["risk_flags"] is None


def test_extract_omitted_response_keys_come_back_null_not_fabricated(
    client, logged_in_procurement, db_session, monkeypatch
):
    """The model may not echo every key. A missing key must not be silently
    dropped or defaulted to something that looks computed - it must be null,
    same as an explicit null, so the UI renders it as em-dash."""
    _enable_ai(monkeypatch)
    partial = {"contract_name": "Support Agreement"}
    _patch_llm(monkeypatch, returns=partial)

    _clear_auth_caches()
    resp = client.post(ENDPOINT, json={"text": "Support agreement, minimal text."})

    assert resp.status_code == 200
    extracted = resp.get_json()["extracted"]
    assert extracted["contract_name"] == "Support Agreement"
    for key in (
        "contract_number", "vendor_name", "start_date", "end_date", "renewal_date",
        "notice_period_days", "auto_renewal", "contract_value", "currency",
        "payment_terms", "termination_clause_summary", "liability_cap", "risk_flags",
    ):
        assert extracted[key] is None, f"{key} should be null, got {extracted[key]!r}"


# --------------------------------------------------------------- failures


def test_extract_llm_failure_returns_502_with_real_message_no_fabricated_body(
    client, logged_in_procurement, db_session, monkeypatch
):
    _enable_ai(monkeypatch)
    _patch_llm(monkeypatch, raises=RuntimeError("provider timed out after 60s"))

    _clear_auth_caches()
    resp = client.post(ENDPOINT, json={"text": SAMPLE_TEXT})

    assert resp.status_code == 502
    body = resp.get_json()
    assert "provider timed out after 60s" in body["error"]
    assert "extracted" not in body


def test_extract_non_json_llm_response_returns_502_not_fabricated(
    client, logged_in_procurement, db_session, monkeypatch
):
    _enable_ai(monkeypatch)
    import app.modules.procurement.contract_extraction_service as svc_module

    monkeypatch.setattr(
        svc_module.LLMService,
        "generate_from_prompt",
        staticmethod(lambda prompt, **kwargs: "Sure, here is a summary of the contract..."),
    )

    _clear_auth_caches()
    resp = client.post(ENDPOINT, json={"text": SAMPLE_TEXT})

    assert resp.status_code == 502
    body = resp.get_json()
    assert "extracted" not in body
    assert body["error"]


def test_extract_empty_text_returns_400(client, logged_in_procurement, db_session, monkeypatch):
    _enable_ai(monkeypatch)
    _clear_auth_caches()
    resp = client.post(ENDPOINT, json={"text": "   "})
    assert resp.status_code == 400


def test_extract_oversized_text_returns_400(client, logged_in_procurement, db_session, monkeypatch):
    _enable_ai(monkeypatch)
    _clear_auth_caches()
    resp = client.post(ENDPOINT, json={"text": "x" * 40_001})
    assert resp.status_code == 400


def test_extract_ai_disabled_returns_503(client, logged_in_procurement, db_session, monkeypatch):
    """No patch of is_ai_enabled here - AI is off by default under the test
    config (no LLM provider configured), so the feature-flag gate must 503
    before the service is ever called."""
    _clear_auth_caches()
    resp = client.post(ENDPOINT, json={"text": SAMPLE_TEXT})
    assert resp.status_code == 503
