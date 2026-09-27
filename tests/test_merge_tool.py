"""Governed merge_capabilities ai-chat tool (Capability-Gap Register G3).

Closes G3: the copilot could DETECT duplicate capabilities but had no governed
way to RESOLVE them. merge_capabilities lets the copilot PROPOSE a merge which a
human approves (mutates=True / tier 'approve') before it runs.

Safety properties under test:
  * registered as an approved write (mutates=True, tier 'approve');
  * repoint-then-retire actually repoints an ApplicationCapabilityMapping from
    the removed capability onto the kept one — no orphaned mapping — and the
    duplicate is soft-deleted (is_deprecated), not left live;
  * org-scoped: a capability in another org cannot be resolved or merged;
  * self-merge rejected;
  * non-existent id rejected.

Written against the shared fixtures in tests/conftest.py (db_session rolls back;
make_org / tenant_ctx cover multi-tenant setup).
"""

import pytest

from app.modules.ai_chat.tools.executor import ToolExecutor
from app.modules.ai_chat.tools.registry import TOOL_SCHEMA_BY_NAME


# --------------------------------------------------------------------------- #
# Registration                                                                #
# --------------------------------------------------------------------------- #

def test_merge_tool_registered_as_approved_write():
    schema = TOOL_SCHEMA_BY_NAME.get("merge_capabilities")
    assert schema is not None, "merge_capabilities is not registered"
    assert schema["mutates"] is True, "merge_capabilities must declare mutates=True"
    assert schema["tier"] == "approve", "merge_capabilities must be tier 'approve'"


def test_merge_tool_is_dispatchable():
    ex = ToolExecutor(user_id=1)
    assert callable(getattr(ex, "_tool_merge_capabilities", None))


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _make_capability(db_session, name, parent_id=None):
    from app.models.business_capabilities import BusinessCapability

    cap = BusinessCapability(name=name, parent_capability_id=parent_id)
    db_session.add(cap)
    db_session.flush()
    return cap


def _make_application(db_session, name="Merge Test App"):
    from app.models.application_portfolio import ApplicationComponent

    app_c = ApplicationComponent(name=name)
    db_session.add(app_c)
    db_session.flush()
    return app_c


def _make_app_mapping(db_session, app_id, cap_id, org_id):
    # ApplicationCapabilityMapping is NOT a TenantMixin model — organization_id
    # is a plain non-nullable column, so it must be set explicitly.
    from app.models.application_capability import ApplicationCapabilityMapping

    m = ApplicationCapabilityMapping(
        application_component_id=app_id,
        business_capability_id=cap_id,
        organization_id=org_id,
    )
    db_session.add(m)
    db_session.flush()
    return m


# --------------------------------------------------------------------------- #
# The core property: repoint-then-retire actually repoints                    #
# --------------------------------------------------------------------------- #

def test_merge_repoints_mapping_and_soft_deletes_duplicate(db_session, make_org, tenant_ctx):
    org = make_org("A")
    ex = ToolExecutor(user_id=1)

    with tenant_ctx(org.id):
        keep = _make_capability(db_session, "Customer Management")
        remove = _make_capability(db_session, "Manage Customer")
        app_c = _make_application(db_session)
        mapping = _make_app_mapping(db_session, app_c.id, remove.id, org.id)
        mapping_id = mapping.id

        result = ex._tool_merge_capabilities(
            {"keep_capability_id": keep.id, "remove_capability_id": remove.id,
             "rationale": "same capability, different name"}
        )
        assert result["success"] is True, result
        assert result["result"]["app_mappings_repointed"] == 1

        # The mapping now points at the KEPT capability — the repoint happened.
        from app.models.application_capability import ApplicationCapabilityMapping
        reread_map = ApplicationCapabilityMapping.query.filter_by(id=mapping_id).first()
        assert reread_map is not None, "mapping was orphaned/deleted, not repointed"
        assert reread_map.business_capability_id == keep.id

        # The duplicate is retired (soft-deleted), not live and not hard-deleted.
        from app.models.business_capabilities import BusinessCapability
        reread_remove = BusinessCapability.query.filter_by(id=remove.id).first()
        assert reread_remove is not None, "duplicate was hard-deleted (should be soft)"
        assert reread_remove.is_deprecated is True
        assert reread_remove.deprecated_as_of is not None
        assert str(keep.id) in (reread_remove.deprecation_notes or "")

        # No mapping is left pointing at the removed capability (no orphan).
        orphans = ApplicationCapabilityMapping.query.filter_by(
            business_capability_id=remove.id
        ).all()
        assert orphans == []

        # Before-state snapshot is present and records the repointed reference.
        snap = result["result"]["before_state"]
        assert snap["removed_capability"]["id"] == remove.id
        assert mapping_id in snap["repointed_app_mapping_ids"]


def test_merge_reparents_children(db_session, make_org, tenant_ctx):
    org = make_org("A")
    ex = ToolExecutor(user_id=1)
    with tenant_ctx(org.id):
        keep = _make_capability(db_session, "Finance")
        remove = _make_capability(db_session, "Financial")
        child = _make_capability(db_session, "Accounts Payable", parent_id=remove.id)

        result = ex._tool_merge_capabilities(
            {"keep_capability_id": keep.id, "remove_capability_id": remove.id}
        )
        assert result["success"] is True, result
        assert result["result"]["children_repointed"] == 1

        from app.models.business_capabilities import BusinessCapability
        reread_child = BusinessCapability.query.filter_by(id=child.id).first()
        assert reread_child.parent_capability_id == keep.id


# --------------------------------------------------------------------------- #
# Rejections                                                                   #
# --------------------------------------------------------------------------- #

def test_merge_rejects_self_merge(db_session, make_org, tenant_ctx):
    org = make_org("A")
    ex = ToolExecutor(user_id=1)
    with tenant_ctx(org.id):
        cap = _make_capability(db_session, "Only One")
        result = ex._tool_merge_capabilities(
            {"keep_capability_id": cap.id, "remove_capability_id": cap.id}
        )
        assert result["success"] is False
        assert "itself" in result["error"].lower()
        # Untouched.
        from app.models.business_capabilities import BusinessCapability
        reread = BusinessCapability.query.filter_by(id=cap.id).first()
        assert reread.is_deprecated in (False, None)


def test_merge_rejects_nonexistent_id(db_session, make_org, tenant_ctx):
    org = make_org("A")
    ex = ToolExecutor(user_id=1)
    with tenant_ctx(org.id):
        keep = _make_capability(db_session, "Real Capability")
        result = ex._tool_merge_capabilities(
            {"keep_capability_id": keep.id, "remove_capability_id": 999999999}
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()


def test_merge_is_org_scoped(db_session, make_org, tenant_ctx):
    """A capability seeded in org A cannot be merged from org B — neither as the
    kept nor the removed side."""
    org_a = make_org("A")
    org_b = make_org("B")
    ex = ToolExecutor(user_id=1)

    with tenant_ctx(org_a.id):
        keep_a = _make_capability(db_session, "Org A Keep")
        remove_a = _make_capability(db_session, "Org A Remove")
        keep_a_id, remove_a_id = keep_a.id, remove_a.id

    with tenant_ctx(org_b.id):
        # Org B has its own kept capability, but tries to remove org A's row.
        keep_b = _make_capability(db_session, "Org B Keep")
        result = ex._tool_merge_capabilities(
            {"keep_capability_id": keep_b.id, "remove_capability_id": remove_a_id}
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

        # And the reverse: org A's capability as the kept side is invisible too.
        remove_b = _make_capability(db_session, "Org B Remove")
        result2 = ex._tool_merge_capabilities(
            {"keep_capability_id": keep_a_id, "remove_capability_id": remove_b.id}
        )
        assert result2["success"] is False
        assert "not found" in result2["error"].lower()

    # Org A's rows are untouched — nothing was cross-merged or retired.
    with tenant_ctx(org_a.id):
        from app.models.business_capabilities import BusinessCapability
        assert BusinessCapability.query.filter_by(id=remove_a_id).first().is_deprecated in (False, None)
        assert BusinessCapability.query.filter_by(id=keep_a_id).first().is_deprecated in (False, None)
