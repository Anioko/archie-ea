"""Governed ACTION/UPDATE ai-chat tools (Capability-Gap Register G2).

Covers the two WRITE tools that turn the copilot from reader/proposer into a
governed actor:

  * record_capability_maturity — record a maturity assessment on a business
    capability (EA / business-architect headline gap).
  * score_rationalization — compute + persist an app's TIME rationalization
    score (EA / portfolio-manager headline gap).

Both are mutates=True / tier 'approve', so they flow through the existing
confirmation gate. Written against the shared fixtures in tests/conftest.py
(db_session rolls back; make_org / tenant_ctx cover multi-tenant setup).
"""

import pytest

from app.modules.ai_chat.tools.executor import ToolExecutor
from app.modules.ai_chat.tools.registry import TOOL_SCHEMA_BY_NAME


# --------------------------------------------------------------------------- #
# Registration: both are declared as approved writes.                         #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", ["record_capability_maturity", "score_rationalization"])
def test_tool_registered_as_approved_write(name):
    schema = TOOL_SCHEMA_BY_NAME.get(name)
    assert schema is not None, f"{name} is not registered"
    assert schema["mutates"] is True, f"{name} must declare mutates=True"
    assert schema["tier"] == "approve", f"{name} must be tier 'approve'"


def test_both_tools_are_dispatchable():
    ex = ToolExecutor(user_id=1)
    for name in ("record_capability_maturity", "score_rationalization"):
        assert callable(getattr(ex, f"_tool_{name}", None)), f"no handler for {name}"


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _make_capability(db_session, name="Test Capability", current=None, target=None):
    from app.models.business_capabilities import BusinessCapability

    cap = BusinessCapability(
        name=name,
        current_maturity_level=current,
        target_maturity_level=target,
    )
    db_session.add(cap)
    db_session.flush()
    return cap


def _make_application(db_session, name="Test App"):
    from app.models.application_portfolio import ApplicationComponent

    app_c = ApplicationComponent(name=name)
    db_session.add(app_c)
    db_session.flush()
    return app_c


# --------------------------------------------------------------------------- #
# record_capability_maturity                                                  #
# --------------------------------------------------------------------------- #

def test_record_capability_maturity_updates_columns(db_session, make_org, tenant_ctx):
    org = make_org("A")
    ex = ToolExecutor(user_id=1)

    with tenant_ctx(org.id):
        cap = _make_capability(db_session)
        result = ex._tool_record_capability_maturity(
            {"capability_id": cap.id, "current_maturity": 2, "target_maturity": 4}
        )
        assert result["success"] is True, result

        from app.models.business_capabilities import BusinessCapability
        reread = BusinessCapability.query.filter_by(id=cap.id).first()
        assert reread.current_maturity_level == 2
        assert reread.target_maturity_level == 4
        assert reread.maturity_gap == 2
        assert reread.maturity_assessment_date is not None


def test_record_capability_maturity_target_optional(db_session, make_org, tenant_ctx):
    org = make_org("A")
    ex = ToolExecutor(user_id=1)
    with tenant_ctx(org.id):
        cap = _make_capability(db_session)
        result = ex._tool_record_capability_maturity(
            {"capability_id": cap.id, "current_maturity": 3}
        )
        assert result["success"] is True
        assert result["result"]["current_maturity_level"] == 3
        # target untouched -> gap not computed
        assert result["result"]["target_maturity_level"] is None


@pytest.mark.parametrize("bad", [0, 6, -1, 10])
def test_record_capability_maturity_rejects_out_of_range(db_session, make_org, tenant_ctx, bad):
    org = make_org("A")
    ex = ToolExecutor(user_id=1)
    with tenant_ctx(org.id):
        cap = _make_capability(db_session, current=1)
        result = ex._tool_record_capability_maturity(
            {"capability_id": cap.id, "current_maturity": bad}
        )
        assert result["success"] is False
        assert "1 and 5" in result["error"]
        # Rejected, not clamped: the original value is untouched.
        from app.models.business_capabilities import BusinessCapability
        reread = BusinessCapability.query.filter_by(id=cap.id).first()
        assert reread.current_maturity_level == 1


def test_record_capability_maturity_rejects_out_of_range_target(db_session, make_org, tenant_ctx):
    org = make_org("A")
    ex = ToolExecutor(user_id=1)
    with tenant_ctx(org.id):
        cap = _make_capability(db_session)
        result = ex._tool_record_capability_maturity(
            {"capability_id": cap.id, "current_maturity": 3, "target_maturity": 9}
        )
        assert result["success"] is False
        assert "target_maturity" in result["error"]


def test_record_capability_maturity_is_org_scoped(db_session, make_org, tenant_ctx):
    """A capability seeded in org A is invisible - and unwritable - from org B."""
    org_a = make_org("A")
    org_b = make_org("B")
    ex = ToolExecutor(user_id=1)

    with tenant_ctx(org_a.id):
        cap = _make_capability(db_session, name="Org A Capability")
        cap_id = cap.id

    # From org B, the same id must read back as not-found (honest), never cross-written.
    with tenant_ctx(org_b.id):
        result = ex._tool_record_capability_maturity(
            {"capability_id": cap_id, "current_maturity": 5}
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    # And org A's row is unchanged.
    with tenant_ctx(org_a.id):
        from app.models.business_capabilities import BusinessCapability
        reread = BusinessCapability.query.filter_by(id=cap_id).first()
        assert reread is not None
        assert reread.current_maturity_level is None


# --------------------------------------------------------------------------- #
# score_rationalization                                                       #
# --------------------------------------------------------------------------- #

def test_score_rationalization_persists_or_surfaces_honestly(db_session, make_org, tenant_ctx):
    """Either the score persists, or an honest failure is surfaced - never a
    fabricated score."""
    org = make_org("A")
    ex = ToolExecutor(user_id=1)

    with tenant_ctx(org.id):
        app_c = _make_application(db_session, name="Scoreable App")
        result = ex._tool_score_rationalization({"app_id": app_c.id})

        assert "success" in result
        if result["success"]:
            # A real score row must now exist for this app.
            from app.models.application_rationalization import (
                ApplicationRationalizationScore,
            )
            row = ApplicationRationalizationScore.query.filter_by(
                application_component_id=app_c.id
            ).first()
            assert row is not None
            assert result["result"]["score_id"] == row.id
            assert result["result"]["rationalization_action"] is not None
        else:
            # Honest failure: an error message, and no invented score fields.
            assert result.get("error")
            assert "result" not in result


def test_score_rationalization_is_org_scoped(db_session, make_org, tenant_ctx):
    org_a = make_org("A")
    org_b = make_org("B")
    ex = ToolExecutor(user_id=1)

    with tenant_ctx(org_a.id):
        app_c = _make_application(db_session, name="Org A App")
        app_id = app_c.id

    with tenant_ctx(org_b.id):
        result = ex._tool_score_rationalization({"app_id": app_id})
        assert result["success"] is False
        assert "not found" in result["error"].lower()


def test_score_rationalization_requires_app_id(db_session, make_org, tenant_ctx):
    org = make_org("A")
    ex = ToolExecutor(user_id=1)
    with tenant_ctx(org.id):
        result = ex._tool_score_rationalization({})
        assert result["success"] is False
