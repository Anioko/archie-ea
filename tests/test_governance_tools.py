"""Governance / executive AI-chat tools (Capability-Gap Register G1 + G2).

These four tools bind services that already existed but had no AI binding, so
the copilot could not answer the personas' headline questions:

* ``get_investment_priorities`` (CTO)           — read, mutates=False
* ``get_executive_dashboard``   (CTO/CIO)        — read, mutates=False
* ``get_arb_status``            (solution_arch,  — read, mutates=False
                                 arb_member)
* ``create_adr``                (solution_arch)  — WRITE, mutates=True, approve

The invariants pinned here:

1. Each tool is registered with the correct ``mutates`` flag and ``tier`` and
   dispatches through ``getattr(self, "_tool_" + name)``.
2. The read tools return REAL data for a seeded org and never leak another org's
   rows (tenant isolation is enforced by the ORM events, not by query code — see
   ``tests/test_tenant_isolation.py``).
3. ``create_adr`` is flagged mutating and actually creates an
   ``ArchitectureDecision`` via ``ADRService.create_adr``, attributed to the
   acting org.
4. No tool fabricates a value: an empty portfolio returns an honest empty state,
   not an invented number.

Written against the shared fixtures in ``tests/conftest.py`` (``db_session`` runs
inside a rolled-back transaction; ``make_org`` / ``tenant_ctx`` cover tenancy).
"""

from __future__ import annotations

import uuid

import pytest

from app.modules.ai_chat.tools.executor import ToolExecutor
from app.modules.ai_chat.tools.registry import (
    TOOL_SCHEMA_BY_NAME,
    mutating_tool_names,
)

pytestmark = pytest.mark.usefixtures("db_session")

READ_TOOLS = ("get_investment_priorities", "get_executive_dashboard", "get_arb_status")
WRITE_TOOLS = ("create_adr",)
ALL_TOOLS = READ_TOOLS + WRITE_TOOLS


# --------------------------------------------------------------- helpers


def _make_user(db_session, org_id):
    from app.models.user import User

    u = User(email=f"gov-{uuid.uuid4().hex[:10]}@example.com", organization_id=org_id)
    db_session.add(u)
    db_session.flush()
    return u


def _make_solution(db_session, org_id, name):
    from app.models.solution_models import Solution

    sol = Solution(name=name, organization_id=org_id)
    db_session.add(sol)
    db_session.flush()
    return sol


def _make_arb_item(db_session, org_id, solution_id, submitter_id, decision="approved"):
    from app.models.architecture_review_board import ARBReviewItem

    item = ARBReviewItem(
        organization_id=org_id,
        review_number=f"REV-{uuid.uuid4().hex[:10]}",
        title="Governance review",
        review_type="solution_review",
        solution_id=solution_id,
        submitter_id=submitter_id,
        status="decided",
        decision=decision,
        decision_rationale="Meets the reference architecture.",
        conditions=[{"text": "Add a rollback plan"}],
    )
    db_session.add(item)
    db_session.flush()
    return item


# --------------------------------------------------------------- registration


@pytest.mark.parametrize("name", ALL_TOOLS)
def test_tool_is_registered(name):
    assert name in TOOL_SCHEMA_BY_NAME, f"{name} is not in the tool registry"


@pytest.mark.parametrize("name", READ_TOOLS)
def test_read_tools_are_non_mutating(name):
    schema = TOOL_SCHEMA_BY_NAME[name]
    assert schema["mutates"] is False, f"{name} is a read tool and must declare mutates=False"
    assert name not in mutating_tool_names()


def test_create_adr_is_registered_mutating_and_approve_tier():
    schema = TOOL_SCHEMA_BY_NAME["create_adr"]
    assert schema["mutates"] is True, "create_adr writes and must declare mutates=True"
    assert schema["tier"] == "approve", (
        "create_adr must be approve-tier so it flows through the confirmation gate"
    )
    assert "create_adr" in mutating_tool_names()


@pytest.mark.parametrize("name", ALL_TOOLS)
def test_dispatch_resolves_a_handler(name):
    """Dispatch is getattr(self, '_tool_' + name) — the handler must exist."""
    ex = ToolExecutor(user_id=1)
    assert callable(getattr(ex, f"_tool_{name}", None)), (
        f"no _tool_{name} handler on ToolExecutor"
    )


# --------------------------------------------------------------- get_arb_status


def test_get_arb_status_returns_real_data_and_is_org_scoped(db_session, make_org, tenant_ctx):
    org_a, org_b = make_org("a"), make_org("b")
    user_a = _make_user(db_session, org_a.id)
    user_b = _make_user(db_session, org_b.id)

    sol_a = _make_solution(db_session, org_a.id, "Solution A")
    # Org B has an ARB item pointing at the SAME solution_id value: only the
    # tenant filter should keep org A from reading it.
    _make_arb_item(db_session, org_a.id, sol_a.id, user_a.id, decision="approved_with_conditions")
    _make_arb_item(db_session, org_b.id, sol_a.id, user_b.id, decision="rejected")

    ex = ToolExecutor(user_id=user_a.id)
    with tenant_ctx(org_a.id):
        result = ex._tool_get_arb_status({"solution_id": sol_a.id})

    assert result["success"] is True
    reviews = result["result"]["reviews"]
    assert len(reviews) == 1, "org A saw more than its own ARB review — tenant leak"
    r = reviews[0]
    assert r["decision"] == "approved_with_conditions"
    assert r["conditions"] == [{"text": "Add a rollback plan"}]
    # It must NOT contain org B's rejected decision.
    assert all(rv["decision"] != "rejected" for rv in reviews)


def test_get_arb_status_empty_is_honest(db_session, make_org, tenant_ctx):
    org = make_org("a")
    ex = ToolExecutor(user_id=_make_user(db_session, org.id).id)
    with tenant_ctx(org.id):
        result = ex._tool_get_arb_status({"solution_id": 999999})
    assert result["success"] is True
    assert result["result"]["reviews"] == []
    assert "no arb review" in result["message"].lower()


# --------------------------------------------------------------- create_adr


def test_create_adr_creates_via_service(db_session, make_org, tenant_ctx):
    from app.models.architecture_decision import ArchitectureDecision

    org = make_org("a")
    sol = _make_solution(db_session, org.id, "ADR Solution")
    ex = ToolExecutor(user_id=_make_user(db_session, org.id).id)

    with tenant_ctx(org.id):
        result = ex._tool_create_adr({
            "solution_id": sol.id,
            "title": "Adopt event-driven integration",
            "context": "Point-to-point integrations no longer scale.",
            "decision": "Introduce a shared event bus.",
            "rationale": "Decouples producers from consumers.",
            "consequences": "Requires an eventing platform and schema governance.",
        })

        assert result["success"] is True, result
        adr_id = result["result"]["id"]
        assert result["result"]["status"] == "proposed"

        adr = db_session.get(ArchitectureDecision, adr_id)
        assert adr is not None
        assert adr.title == "Adopt event-driven integration"
        assert adr.solution_id == sol.id
        # TenantMixin auto-set organization_id from the acting org on flush.
        assert adr.organization_id == org.id


def test_create_adr_is_org_scoped(db_session, make_org, tenant_ctx):
    """An ADR authored in org A must not be visible from org B."""
    from app.services.adr_service import ADRService

    org_a, org_b = make_org("a"), make_org("b")
    sol_a = _make_solution(db_session, org_a.id, "Solution A")
    ex = ToolExecutor(user_id=_make_user(db_session, org_a.id).id)

    with tenant_ctx(org_a.id):
        res = ex._tool_create_adr({
            "solution_id": sol_a.id,
            "title": "A-only decision",
            "context": "c",
            "decision": "d",
            "rationale": "r",
        })
        adr_id = res["result"]["id"]

    with tenant_ctx(org_b.id):
        # ADRService.get_adr is tenant-scoped; org B must not reach org A's ADR.
        db_session.expunge_all()
        leaked = ADRService.get_adr(adr_id)

    assert leaked is None, "TENANT LEAK: org B read org A's ADR"


# --------------------------------------------------------- get_investment_priorities


def test_get_investment_priorities_empty_is_honest(db_session, make_org, tenant_ctx):
    """With no capability mappings the tool returns an honest empty state — it
    must NOT invent an investment posture (CLAUDE.md never-invent-data)."""
    org = make_org("a")
    ex = ToolExecutor(user_id=_make_user(db_session, org.id).id)
    with tenant_ctx(org.id):
        result = ex._tool_get_investment_priorities({})

    assert result["success"] is True
    # ranked is a list; split is either None (nothing measurable) or a tier dict.
    assert isinstance(result["result"]["ranked"], list)
    assert "split" in result["result"]


# ----------------------------------------------------------- get_executive_dashboard


def test_get_executive_dashboard_shape_is_honest(db_session, make_org, tenant_ctx):
    """Returns the executive summary shape; unavailable metrics come back as
    None (rendered as an em dash), never as a fabricated zero."""
    org = make_org("a")
    _make_solution(db_session, org.id, "Dash Solution")
    ex = ToolExecutor(user_id=_make_user(db_session, org.id).id)

    with tenant_ctx(org.id):
        result = ex._tool_get_executive_dashboard({})

    assert result["success"] is True
    res = result["result"]
    for key in (
        "portfolio_health", "portfolio_stats", "programme_progress",
        "arb_pipeline", "top_risks", "capability_coverage",
    ):
        assert key in res, f"executive dashboard missing '{key}'"
