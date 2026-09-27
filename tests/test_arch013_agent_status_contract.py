"""ARCH-013: the AI agent's find_applications tool must report the same
lifecycle_status the Applications API/UI report for the same record — never
a differently-sourced value mislabelled as bare "status".

Root cause (confirmed by reading the code, not inferred): two model classes
are mapped onto the same `application_components` table via `extend_existing`
(a known legacy hazard, see CLAUDE.md) —
`app.models.application_component_fast.ApplicationComponent` (only
`deployment_status`) and `app.models.application_portfolio.ApplicationComponent`
(both `deployment_status` AND `lifecycle_status`, and the one
`/applications/api/list` and the Applications UI use). The agent tool used to
import the *fast* model and label its `deployment_status` as bare "status", so
for the same row the agent could report "development" (deployment_status)
while the UI correctly reported "operational" (lifecycle_status) — a
field-naming collision, not a simple mapping bug. `status` and
`lifecycle_status` ARE distinct fields; the fix makes the tool query the
canonical portfolio model and never emit an ambiguous "status" key.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def seeded_application(db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import ApplicationComponent

    org = make_org("arch013")
    with tenant_ctx(org.id):
        app_row = ApplicationComponent(
            name="ARCH-013 Contract Probe",
            organization_id=org.id,
            lifecycle_status="operational",
            deployment_status="development",
        )
        db_session.add(app_row)
        db_session.flush()
        yield app_row, org


def test_agent_tool_reports_lifecycle_status_matching_api_field(seeded_application):
    """The regression this finding demands: agent-reported status must match
    the field the API/UI expose, for a seeded record where the two candidate
    source fields deliberately disagree (operational vs development)."""
    from app.modules.ai_chat.tools.executor import ToolExecutor
    from app.models.application_portfolio import ApplicationComponent

    app_row, org = seeded_application

    executor = ToolExecutor.__new__(ToolExecutor)  # bypass __init__'s user lookup
    executor._resolver = None
    executor._org_id = org.id

    result = executor._tool_find_applications({"name_contains": "ARCH-013 Contract Probe"})
    assert result["success"] is True
    rows = result["result"]
    assert len(rows) == 1
    row = rows[0]

    # The key acceptance criterion: no bare "status" key presenting an
    # ambiguous concept to the model.
    assert "status" not in row

    # The agent-reported lifecycle_status must equal the API's source-of-truth
    # column for the same row — not the unrelated deployment_status.
    api_row = ApplicationComponent.query.get(app_row.id)
    assert row["lifecycle_status"] == api_row.lifecycle_status == "operational"

    # deployment_status is real and distinct — reported under its own name,
    # never conflated with lifecycle_status.
    assert row["deployment_status"] == "development"
    assert row["lifecycle_status"] != row["deployment_status"]
