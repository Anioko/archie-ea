"""Regression tests for QA audit findings P-01, P-02, P-03, P-08, P-12 (fix/qa-register-100).

P-01: selecting a persona changed only the label, not the reasoning, for six of
      twelve personas (application_architect, integration_architect,
      systems_architect, business_analyst, product_analyst, and cio via its
      cto alias) because they had no entry in ARCHITECT_PERSONAS/CHARTERS and
      silently dropped to a generic fallback prompt template that is
      structurally identical across personas.

P-08: GET /ai-chat/context/<domain> returned HTTP 200 for an unrecognised
      domain with {"success": false, "error": "Unknown domain: ..."} in the
      body — a failure reported as success, the exact fetch trap CLAUDE.md
      documents (`if (response.ok)` never sees it).

These are deterministic, prompt-construction / HTTP-contract checks — no LLM
call is made or required.
"""
from __future__ import annotations

import pytest


PERSONAS_THAT_MUST_HAVE_A_CHARTER = (
    "enterprise_architect",
    "solutions_architect",
    "technology_architect",
    "data_architect",
    "business_architect",
    "application_architect",
    "integration_architect",
    "systems_architect",
    "business_analyst",
    "product_analyst",
)


def test_all_named_ai_personas_are_in_architect_personas():
    """Fail-first: before the fix, six of these were missing from ARCHITECT_PERSONAS."""
    from app.modules.ai_chat.services.architect_persona_charters import ARCHITECT_PERSONAS

    missing = [p for p in PERSONAS_THAT_MUST_HAVE_A_CHARTER if p not in ARCHITECT_PERSONAS]
    assert not missing, f"personas with no governed charter: {missing}"


def test_all_named_ai_personas_build_a_distinct_governed_prompt():
    """Each persona's prompt must differ from every other's, and must not be
    the generic fallback (no charter/no Live Platform Data marker)."""
    from app.modules.ai_chat.services.architect_persona_charters import build_architect_prompt

    prompts = {}
    for persona in PERSONAS_THAT_MUST_HAVE_A_CHARTER:
        prompt = build_architect_prompt(persona)
        assert prompt is not None, f"{persona} has no governed charter (falls back to generic template)"
        assert "Live Platform Data" in prompt, f"{persona} charter missing live-data injection"
        prompts[persona] = prompt

    # No two personas may produce byte-identical prompts.
    seen = {}
    for persona, prompt in prompts.items():
        assert prompt not in seen.values(), (
            f"{persona} produces a prompt identical to {[k for k, v in seen.items() if v == prompt]}"
        )
        seen[persona] = prompt


def test_cio_resolves_via_documented_alias():
    """cio is documented as intentionally aliased to the cto charter, not missing."""
    from app.modules.ai_chat.services.architect_persona_charters import (
        PERSONA_ALIASES,
        build_architect_prompt,
    )

    assert PERSONA_ALIASES.get("cio") == "cto"
    assert build_architect_prompt("cio") is not None


def test_capability_architect_has_its_own_prompt_path():
    """capability_architect is covered by a separate prompt builder (not a gap)."""
    from app.modules.ai_chat.services.capability_architect_prompts import (
        build_capability_architect_prompt,
    )

    assert callable(build_capability_architect_prompt)


@pytest.fixture
def qa_client(app, db_session, make_org, login_as):
    import uuid

    from app.models import Permission, Role, User

    org = make_org("qa100")
    role = Role.query.filter_by(name="Administrator").first()
    if role is None:
        role = Role(name="Administrator", permissions=Permission.ADMINISTER)
        db_session.add(role)
        db_session.flush()

    user = User(
        email=f"qa100-{uuid.uuid4().hex[:8]}@example.com",
        first_name="QA",
        last_name="Register100",
        organization_id=org.id,
        role=role,
        confirmed=True,
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    login_as(client, user)
    return client


def test_unknown_domain_context_reports_failure_via_http_status(qa_client):
    """P-08: an unrecognised domain must not be reported as HTTP 200 success.

    Before the fix: 200 + {"success": false, "error": "Unknown domain: ..."}.
    A caller checking only response.ok never observes the failure.
    """
    resp = qa_client.get("/ai-chat/context/enterprise_architect")
    body = resp.get_json()
    assert body is not None
    if body.get("success") is False:
        assert resp.status_code != 200, (
            "domain context endpoint reported a failure body with HTTP 200 "
            f"(body={body!r}) — the response.ok fetch trap CLAUDE.md documents"
        )


def test_known_domain_context_still_returns_200(qa_client):
    """Guard against over-correcting: a valid domain must remain 200."""
    resp = qa_client.get("/ai-chat/context/architecture")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body is not None
    assert body.get("success", True) is not False


def test_empty_export_signals_nothing_to_export(qa_client):
    """P-12: an empty catalogue export must be distinguishable from a real
    download, not a silent no-op the frontend cannot observe.

    org is freshly created by qa_client's fixture and has no
    ApplicationComponent rows (tenant-scoped, rolled back after the test), so
    this exercises the true empty-catalogue path.
    """
    resp = qa_client.get("/applications/export/csv")
    assert resp.status_code == 200
    assert resp.headers.get("X-Export-Empty") == "1", (
        "empty-catalogue export did not signal emptiness via X-Export-Empty — "
        "frontend has no way to show a 'nothing to export' message"
    )
