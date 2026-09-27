"""Real LLM patch synthesis for the genome-as-substrate copilot.

Pins the synthesis half of the flow (app/modules/genome/patch/synth.py) — the
piece that turns a free-text request into a candidate genome patch dict by
prompting the existing LLM service. The LLM is ALWAYS mocked here (a callable
injected via context["llm_service"]); no real/paid completion is ever made.

Invariants under test:

  1. LLM returns a valid JSON patch  -> propose QUEUES a pending approval,
     nothing is applied to the model.
  2. LLM returns prose / invalid JSON / a schema-violating patch -> REJECTED,
     fail-closed, NOTHING queued, the error is surfaced (no fabricated fallback).
  3. LLM returns JSON wrapped in ```json fences -> parsed and queued (robust).
  4. The synthesized patch's target.organization_id is the ACTING org, even when
     the model emits a different org id (no cross-org write).

Uses the shared fixtures in tests/conftest.py (app, db_session, make_org,
tenant_ctx) — the same ones tests/test_genome_patch_flow.py adopts.
"""

import json
import uuid

import pytest

from app.modules.genome.patch.synth import (
    PatchSynthesisError,
    _extract_json_object,
    llm_patch_source,
)


# --------------------------------------------------------------------------- #
# Helpers (mirrors tests/test_genome_patch_flow.py — a fresh scratch DB has no  #
# seeded roles, so build the acting user explicitly).                          #
# --------------------------------------------------------------------------- #

def _writer_role(db_session):
    from app.models.user import Permission, Role

    role = Role.query.filter_by(name="GenomeSynthWriter").first()
    if role is None:
        role = Role(name="GenomeSynthWriter", permissions=Permission.GENERAL)
        db_session.add(role)
        db_session.flush()
    return role


def _make_admin(db_session, org, label):
    from app.models.user import User

    user = User(
        email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Genome",
        last_name="Synth",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    user.role = _writer_role(db_session)
    db_session.add(user)
    db_session.flush()
    return user


def _valid_patch_json(org_id, name="Fraud Detection"):
    return json.dumps(
        {
            "target": {"organization_id": org_id, "domain": "motivation"},
            "operation": "add",
            "element": {
                "archimate_type": "Capability",
                "layer": "strategy",
                "name": name,
                "description": "Detect and prevent fraudulent transactions.",
            },
            "provenance": {
                "proposed_by": "ai_copilot",
                "rationale": "Portfolio scan found no capability covering fraud detection.",
                "archimate_anchor": "Driver:Regulatory Pressure",
                "source": "ai_copilot",
            },
        }
    )


def _stub_llm(response_text):
    """A mock LLM completion callable (prompt) -> str. Records the prompt."""

    calls = []

    def _complete(prompt):
        calls.append(prompt)
        return response_text

    _complete.calls = calls
    return _complete


def _element_count_by_name(org_id, name):
    from app import db
    from app.models.models import ArchiMateElement

    # tenancy-ok: explicit org filter for a cross-org assertion.
    return (
        db.session.query(ArchiMateElement)
        .filter(
            ArchiMateElement.organization_id == org_id,
            ArchiMateElement.name == name,
        )
        .count()
    )


# --------------------------------------------------------------------------- #
# Unit-level: the JSON extractor is deterministic and fail-closed.            #
# --------------------------------------------------------------------------- #

def test_extract_plain_json_object():
    out = _extract_json_object('{"a": 1, "b": "x"}')
    assert out == {"a": 1, "b": "x"}


def test_extract_json_in_code_fence():
    raw = "Here is the patch:\n```json\n{\"a\": 1}\n```\nThanks!"
    assert _extract_json_object(raw) == {"a": 1}


def test_extract_json_in_bare_fence():
    raw = "```\n{\"a\": 2}\n```"
    assert _extract_json_object(raw) == {"a": 2}


def test_extract_prose_fails_closed():
    with pytest.raises(PatchSynthesisError):
        _extract_json_object("I think you should add a fraud capability.")


def test_extract_empty_fails_closed():
    with pytest.raises(PatchSynthesisError):
        _extract_json_object("   ")


def test_extract_json_array_is_not_a_patch():
    # A JSON array is valid JSON but not a patch object -> fail closed.
    with pytest.raises(PatchSynthesisError):
        _extract_json_object("[1, 2, 3]")


# --------------------------------------------------------------------------- #
# llm_patch_source: org handling and fail-closed contract (no DB needed).     #
# --------------------------------------------------------------------------- #

def test_synth_requires_org_in_context():
    with pytest.raises(PatchSynthesisError):
        llm_patch_source("propose a capability", {"llm_service": _stub_llm("{}")})


def test_synth_forces_acting_org_no_cross_org():
    # Model emits org 999; acting org is 7 — the synthesized patch MUST carry 7.
    stub = _stub_llm(_valid_patch_json(999))
    patch = llm_patch_source(
        "propose a capability",
        {"organization_id": 7, "proposed_by": "42", "llm_service": stub},
    )
    assert patch["target"]["organization_id"] == 7
    # The prompt embedded the acting org, not the model's hallucination.
    assert "7" in stub.calls[0]


def test_synth_prose_response_fails_closed():
    stub = _stub_llm("You might want a fraud capability, but I'm not sure.")
    with pytest.raises(PatchSynthesisError):
        llm_patch_source(
            "propose a capability",
            {"organization_id": 1, "llm_service": stub},
        )


def test_synth_llm_call_failure_fails_closed():
    def _boom(_prompt):
        raise RuntimeError("provider down")

    with pytest.raises(PatchSynthesisError):
        llm_patch_source(
            "propose a capability",
            {"organization_id": 1, "llm_service": _boom},
        )


# --------------------------------------------------------------------------- #
# End-to-end through the proposer + real approval gate (DB-backed).           #
# --------------------------------------------------------------------------- #

def test_synth_valid_json_queues_pending_approval(app, db_session, make_org, tenant_ctx):
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval, ApprovalStatus
    from app.modules.genome.patch.proposer import (
        APPLY_ENTITY_TYPE,
        propose_genome_patch,
    )

    org = make_org("genome-synth-ok")
    user = _make_admin(db_session, org, "genome-synth-ok")
    name = f"Synth Capability {uuid.uuid4().hex[:6]}"
    stub = _stub_llm(_valid_patch_json(org.id, name=name))

    with tenant_ctx(org.id):
        assert _element_count_by_name(org.id, name) == 0

        out = propose_genome_patch(
            request_text="propose a fraud detection capability",
            user_id=user.id,
            context={
                "organization_id": org.id,
                "proposed_by": str(user.id),
                "llm_service": stub,
            },
        )
        assert out["success"] is True, out
        assert out["status"] == "pending_approval"

        appr = AIChatCRUDApproval.query.get(out["approval_id"])
        assert appr is not None
        assert appr.status == ApprovalStatus.PENDING
        assert appr.entity_type == APPLY_ENTITY_TYPE

        # Queued only — nothing applied.
        assert _element_count_by_name(org.id, name) == 0
        # Synthesized patch carries the acting org.
        assert out["patch"]["target"]["organization_id"] == org.id


def test_synth_fenced_json_queues_pending_approval(app, db_session, make_org, tenant_ctx):
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval, ApprovalStatus
    from app.modules.genome.patch.proposer import propose_genome_patch

    org = make_org("genome-synth-fence")
    user = _make_admin(db_session, org, "genome-synth-fence")
    name = f"Fenced Capability {uuid.uuid4().hex[:6]}"
    fenced = "Sure, here is the patch:\n```json\n" + _valid_patch_json(org.id, name=name) + "\n```"
    stub = _stub_llm(fenced)

    with tenant_ctx(org.id):
        out = propose_genome_patch(
            request_text="propose a capability",
            user_id=user.id,
            context={
                "organization_id": org.id,
                "proposed_by": str(user.id),
                "llm_service": stub,
            },
        )
        assert out["success"] is True, out
        appr = AIChatCRUDApproval.query.get(out["approval_id"])
        assert appr.status == ApprovalStatus.PENDING
        assert _element_count_by_name(org.id, name) == 0


def test_synth_prose_is_rejected_nothing_queued(app, db_session, make_org, tenant_ctx):
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval
    from app.modules.genome.patch.proposer import propose_genome_patch

    org = make_org("genome-synth-prose")
    user = _make_admin(db_session, org, "genome-synth-prose")
    stub = _stub_llm("I recommend adding a fraud detection capability to your model.")

    with tenant_ctx(org.id):
        before = AIChatCRUDApproval.query.count()
        out = propose_genome_patch(
            request_text="propose a capability",
            user_id=user.id,
            context={
                "organization_id": org.id,
                "proposed_by": str(user.id),
                "llm_service": stub,
            },
        )
        # Fail closed: not queued, error surfaced, no fabricated fallback patch.
        assert out["success"] is False, out
        assert "error" in out
        assert AIChatCRUDApproval.query.count() == before


def test_synth_schema_violating_patch_is_rejected(app, db_session, make_org, tenant_ctx):
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval
    from app.modules.genome.patch.proposer import propose_genome_patch

    org = make_org("genome-synth-bad")
    user = _make_admin(db_session, org, "genome-synth-bad")
    # Valid JSON, but a schema-violating patch: unknown type, no provenance.
    bad = json.dumps(
        {
            "target": {"organization_id": org.id, "domain": "motivation"},
            "operation": "obliterate",
            "element": {"archimate_type": "Wormhole", "layer": "strategy", "name": "X"},
        }
    )
    stub = _stub_llm(bad)

    with tenant_ctx(org.id):
        before = AIChatCRUDApproval.query.count()
        out = propose_genome_patch(
            request_text="propose a capability",
            user_id=user.id,
            context={
                "organization_id": org.id,
                "proposed_by": str(user.id),
                "llm_service": stub,
            },
        )
        # Deterministic validator rejects it -> status rejected, nothing queued.
        assert out["success"] is False, out
        assert out.get("status") == "rejected"
        assert out.get("errors")
        assert AIChatCRUDApproval.query.count() == before
