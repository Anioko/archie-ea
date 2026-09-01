"""Genome-as-substrate first increment (ADR 0009 / ADR 0010).

Pins the four invariants of the genome-patch flow, using the shared fixtures in
tests/conftest.py:

  (a) a malformed patch is REJECTED by the deterministic validator, fail-closed,
      with the concrete errors surfaced (not swallowed, not coerced);
  (b) a proposed VALID patch is QUEUED through the EXISTING approval gate and is
      NOT applied — no ArchiMateElement exists until approval;
  (c) an APPROVED patch applies: the element is created with provenance and a
      matching ArchiMateElement row exists (the ArchiMate backbone);
  (d) org-scoping — a patch applied for org A does not leak into org B.

The LLM proposal step is stubbed (a fixed patch dict); what is under test is
that whatever is proposed is validated + queued deterministically, and only an
approved patch mutates the model.
"""

import uuid

import pytest


def _writer_role(db_session):
    """A Role carrying GENERAL permission (what can()/approve checks).

    A fresh scratch DB has no seeded roles, so assign one explicitly rather than
    rely on the default-role lookup in User.__init__.
    """
    from app.models.user import Permission, Role

    role = Role.query.filter_by(name="GenomeWriter").first()
    if role is None:
        role = Role(name="GenomeWriter", permissions=Permission.GENERAL)
        db_session.add(role)
        db_session.flush()
    return role


def _make_admin(db_session, org, label):
    from app.models.user import User

    user = User(
        email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Genome",
        last_name="Patch",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    user.role = _writer_role(db_session)
    db_session.add(user)
    db_session.flush()
    return user


def _valid_patch(org_id, name="Fraud Detection", anchor="Driver:Regulatory Pressure"):
    return {
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
            "archimate_anchor": anchor,
            "source": "ai_copilot",
        },
    }


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
# (a) malformed patch is rejected, fail-closed                                #
# --------------------------------------------------------------------------- #

def test_malformed_patch_is_rejected_with_errors():
    from app.modules.genome.patch.validator import validate_genome_patch

    # Missing provenance entirely, bad operation, unknown archimate_type.
    bad = {
        "target": {"organization_id": 1, "domain": "motivation"},
        "operation": "obliterate",
        "element": {"archimate_type": "Wormhole", "layer": "strategy", "name": "X"},
    }
    result = validate_genome_patch(bad)
    assert result.valid is False
    assert not result  # __bool__
    joined = " | ".join(result.errors)
    assert "provenance" in joined
    assert "operation" in joined
    assert "archimate_type" in joined or "Wormhole" in joined


def test_provenance_without_rationale_is_rejected():
    from app.modules.genome.patch.validator import validate_genome_patch

    bad = _valid_patch(1)
    bad["provenance"]["rationale"] = "   "  # whitespace-only, not a real reason
    result = validate_genome_patch(bad)
    assert result.valid is False
    assert any("rationale" in e for e in result.errors)


def test_modify_without_element_id_is_rejected():
    from app.modules.genome.patch.validator import validate_genome_patch

    bad = _valid_patch(1)
    bad["operation"] = "modify"  # but no element_id
    result = validate_genome_patch(bad)
    assert result.valid is False
    assert any("element_id" in e for e in result.errors)


def test_non_dict_patch_is_rejected():
    from app.modules.genome.patch.validator import validate_genome_patch

    assert validate_genome_patch("not a patch").valid is False
    assert validate_genome_patch(None).valid is False


def test_valid_patch_passes_validation():
    from app.modules.genome.patch.validator import validate_genome_patch

    assert validate_genome_patch(_valid_patch(42)).valid is True


# --------------------------------------------------------------------------- #
# (b) valid proposal is QUEUED, not applied                                   #
# --------------------------------------------------------------------------- #

def test_valid_proposal_is_queued_not_applied(app, db_session, make_org, tenant_ctx):
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval, ApprovalStatus
    from app.modules.genome.patch.proposer import (
        APPLY_ENTITY_TYPE,
        propose_genome_patch,
    )

    org = make_org("genome-b")
    user = _make_admin(db_session, org, "genome-b")
    name = f"Queued Capability {uuid.uuid4().hex[:6]}"
    patch = _valid_patch(org.id, name=name)

    with tenant_ctx(org.id):
        # Precondition: element does not exist.
        assert _element_count_by_name(org.id, name) == 0

        out = propose_genome_patch(
            request_text="propose a missing capability",
            user_id=user.id,
            patch_source=lambda *_a, **_k: patch,
        )
        assert out["success"] is True, out
        assert out["status"] == "pending_approval"
        approval_id = out["approval_id"]

        # A pending approval exists, carrying the patch, keyed to the apply tool.
        appr = AIChatCRUDApproval.query.get(approval_id)
        assert appr is not None
        assert appr.status == ApprovalStatus.PENDING
        assert appr.operation_type == "tool_use"
        assert appr.entity_type == APPLY_ENTITY_TYPE

        # Crucially: NOTHING was applied to the model.
        assert _element_count_by_name(org.id, name) == 0


def test_invalid_proposal_is_not_queued(app, db_session, make_org, tenant_ctx):
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval
    from app.modules.genome.patch.proposer import propose_genome_patch

    org = make_org("genome-b2")
    user = _make_admin(db_session, org, "genome-b2")

    with tenant_ctx(org.id):
        before = AIChatCRUDApproval.query.count()
        out = propose_genome_patch(
            request_text="propose something broken",
            user_id=user.id,
            patch_source=lambda *_a, **_k: {"element": {"name": "X"}},  # invalid
        )
        assert out["success"] is False
        assert out["status"] == "rejected"
        assert out["errors"]
        # Nothing queued.
        assert AIChatCRUDApproval.query.count() == before


# --------------------------------------------------------------------------- #
# (c) approved patch applies, with provenance + synced ArchiMateElement       #
# --------------------------------------------------------------------------- #

def test_approved_patch_applies_with_provenance_and_synced_element(
    app, db_session, make_org, tenant_ctx
):
    from app.models.models import ArchiMateElement
    from app.modules.ai_chat.services.ai_chat_approval_service import (
        AIChatApprovalService,
    )
    from app.modules.genome.patch.applier import (
        GENOME_PATCH_SOURCE,
        verify_element_synced,
    )
    from app.modules.genome.patch.proposer import propose_genome_patch

    org = make_org("genome-c")
    requester = _make_admin(db_session, org, "genome-c-req")
    approver = _make_admin(db_session, org, "genome-c-appr")
    name = f"Approved Capability {uuid.uuid4().hex[:6]}"
    patch = _valid_patch(org.id, name=name)

    with tenant_ctx(org.id):
        proposed = propose_genome_patch(
            request_text="propose a missing capability",
            user_id=requester.id,
            patch_source=lambda *_a, **_k: patch,
        )
        assert proposed["success"] is True, proposed
        approval_id = proposed["approval_id"]
        assert _element_count_by_name(org.id, name) == 0  # still not applied

        # Approve via a DISTINCT approver (service refuses self-approval).
        svc = AIChatApprovalService(user_id=approver.id)
        executed = svc.approve_and_execute(approval_id)
        assert executed["success"] is True, executed

        # The element now exists (the ArchiMate backbone row IS the field).
        assert _element_count_by_name(org.id, name) == 1
        elem = (
            db_session.query(ArchiMateElement)
            .filter(
                ArchiMateElement.organization_id == org.id,
                ArchiMateElement.name == name,
            )
            .first()
        )
        assert elem is not None
        assert elem.type == "Capability"
        assert elem.acm_source == GENOME_PATCH_SOURCE
        assert verify_element_synced(elem.id, org.id) is True

        # Provenance is attached and attributable.
        prov = (elem.custom_properties or {}).get("genome_provenance")
        assert prov is not None
        assert prov["rationale"].startswith("Portfolio scan")
        assert prov["archimate_anchor"]
        assert prov["applied_by_user_id"] == approver.id


# --------------------------------------------------------------------------- #
# (d) org-scoping — a patch for org A does not leak to org B                   #
# --------------------------------------------------------------------------- #

def test_applied_patch_is_org_scoped(app, db_session, make_org, tenant_ctx):
    from app.models.models import ArchiMateElement
    from app.modules.genome.patch.applier import apply_genome_patch

    org_a = make_org("genome-d-a")
    org_b = make_org("genome-d-b")
    user_a = _make_admin(db_session, org_a, "genome-d-a")
    name = f"OrgA Only {uuid.uuid4().hex[:6]}"
    patch = _valid_patch(org_a.id, name=name)

    with tenant_ctx(org_a.id):
        out = apply_genome_patch(patch, user_a.id)
        assert out["success"] is True, out
        assert out["result"]["organization_id"] == org_a.id

    # Org A sees it.
    with tenant_ctx(org_a.id):
        assert _element_count_by_name(org_a.id, name) == 1
        # The tenant middleware alone (no explicit org filter) also scopes it in.
        assert ArchiMateElement.query.filter_by(name=name).count() == 1

    # Org B does NOT — neither by explicit filter nor via the middleware.
    with tenant_ctx(org_b.id):
        assert _element_count_by_name(org_b.id, name) == 0
        assert ArchiMateElement.query.filter_by(name=name).count() == 0
