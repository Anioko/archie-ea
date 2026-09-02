"""F-12, Capgemini dry-run: the impact-analysis fallback fabricated
estimated_financial_risk as `total_affected * 25000` (a literal per-dependency
dollar figure with no source) whenever the affected application had no real
total_cost_of_ownership. CLAUDE.md's never-invent-data rule: a 0/computed
number that isn't backed by real data must render as None -> "-", not a
plausible-looking figure. Assert the fallback now returns None in that case.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_impact_fallback_reports_none_not_fabricated_cost(app, db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.archimate_core import ArchiMateElement
    from app.models.business_capability import BusinessCapability
    from app.models.application_capability import ApplicationCapabilityMapping
    from app.modules.solutions_strategic.v2.routes.strategic_routes import (
        _build_solution_impact_fallback,
    )

    org = make_org("impact-analysis-no-fab-cost")
    with tenant_ctx(org.id):
        application = ApplicationComponent(
            name="Legacy Order Router", organization_id=org.id,
            total_cost_of_ownership=None,
        )
        db_session.add(application)
        capability = BusinessCapability(name="Order Routing", organization_id=org.id)
        db_session.add(capability)
        db_session.commit()

        db_session.add(ApplicationCapabilityMapping(
            application_component_id=application.id,
            business_capability_id=capability.id,
            organization_id=org.id,
        ))
        db_session.commit()

        element = ArchiMateElement(
            name="Legacy Order Router", type="ApplicationComponent",
            application_component_id=application.id, organization_id=org.id,
        )
        db_session.add(element)
        db_session.commit()

        with app.app_context():
            result = _build_solution_impact_fallback(element.id)
            assert result is not None
            assert result["total_affected"] > 0
            assert result["estimated_financial_risk"] is None
