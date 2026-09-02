"""Workforce-transition analysis reads BusinessRole's (previously orphaned) fields.

The people dimension of a transformation: role-to-role transitions, retiring roles,
headcount delta, skills gap. These come from existing BusinessRole columns that no
code read before. Tests pin the computation and the no-fabrication invariant.
"""

import pytest

from app.models.business_layer import BusinessRole
from app.services.workforce_transition_service import WorkforceTransitionService


@pytest.mark.usefixtures("db_session")
def test_transition_picture(db_session, make_org, tenant_ctx):
    org = make_org("wf")
    with tenant_ctx(org.id):
        to_be = BusinessRole(
            name="Revenue Operations Lead", organization_id=org.id,
            current_filled_positions=0, forecasted_demand=15,
            required_skills='["Salesforce", "RevOps"]',
        )
        db_session.add(to_be)
        db_session.commit()
        as_is = BusinessRole(
            name="Sales Rep", organization_id=org.id,
            current_filled_positions=10, replacement_role_id=to_be.id,
            required_skills='["Cold Calling"]',
        )
        # mark the old role retiring
        as_is.deprecated_date = __import__("datetime").date.today()
        db_session.add(as_is)
        db_session.commit()

        result = WorkforceTransitionService.analyze()

        # one role-to-role transition, headcount moving 10 → 15
        assert len(result["transitions"]) == 1
        t = result["transitions"][0]
        assert t["from_role"] == "Sales Rep" and t["to_role"] == "Revenue Operations Lead"
        assert t["headcount_from"] == 10 and t["headcount_to"] == 15

        # the old role is flagged retiring
        assert any(r["role"] == "Sales Rep" for r in result["retiring_roles"])

        # headcount: retiring role contributes 0 to target, replacement carries 15
        assert result["headcount"] == {"current": 10, "target": 15, "delta": 5}

        # skills the growing role needs that the shrinking one didn't supply
        assert result["skills_gap"] == ["RevOps", "Salesforce"]


@pytest.mark.usefixtures("db_session")
def test_empty_estate_returns_empty_not_fabricated(db_session, make_org, tenant_ctx):
    org = make_org("wf")
    with tenant_ctx(org.id):
        result = WorkforceTransitionService.analyze()
        assert result["role_count"] == 0
        assert result["transitions"] == []
        assert result["retiring_roles"] == []
        assert result["headcount"] == {"current": 0, "target": 0, "delta": 0}
        assert result["skills_gap"] == []
