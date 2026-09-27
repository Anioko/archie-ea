"""F-21, Capgemini walkthrough: a role being replaced (replacement_role_id
set) never showed on the "retiring roles" list unless someone also flipped
its operational_status or deprecated_date — so a transition the page's own
"Role transitions" table reported as happening was invisible on the KPI
that is supposed to summarise it.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_role_with_replacement_counts_as_retiring(app, db_session, make_org, tenant_ctx):
    from app.models.business_layer import BusinessRole
    from app.services.workforce_transition_service import WorkforceTransitionService

    org = make_org("workforce-transition-retiring")
    with tenant_ctx(org.id):
        new_role = BusinessRole(name="Cloud Platform Engineer", organization_id=org.id,
                                 current_filled_positions=0, forecasted_demand=3)
        db_session.add(new_role)
        db_session.commit()

        old_role = BusinessRole(name="On-Prem Sysadmin", organization_id=org.id,
                                 current_filled_positions=5, forecasted_demand=0,
                                 replacement_role_id=new_role.id)
        db_session.add(old_role)
        db_session.commit()

        with app.app_context():
            result = WorkforceTransitionService.analyze()
            retiring_names = {r["role"] for r in result["retiring_roles"]}
            assert "On-Prem Sysadmin" in retiring_names
