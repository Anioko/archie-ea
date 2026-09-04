"""The CTO-tab hero panel and the lazy-loaded Executive Summary fragment must
report the SAME "Capability Coverage %" for the same tenant.

4 Sep 2026: caught live from a user screenshot — the hero showed 100%, the
Executive Summary fragment (same page, same tenant, moments apart) showed 0%.
Root cause: two independent computations, one counting capabilities with a
mapped application (ApplicationCapabilityMapping), the other counting
capabilities with a mapped solution (SolutionCapabilityMapping) — a much
sparser relationship. Same label, same 20% weight in an identically-shaped
health-score composite, genuinely different tables.

Fixed by routing both through app/modules/dashboard/v2/services/
capability_coverage.py::compute_l1_capability_coverage. This test seeds a
tenant with capabilities mapped to applications but NOT to any solution, so
the pre-fix SolutionCapabilityMapping-based path would report 0% while the
ApplicationCapabilityMapping-based path reports non-zero — exactly the
divergence observed live.
"""

from __future__ import annotations

from app import db
from app.models.business_capability import BusinessCapability
from app.models.organization import Organization


def _org(db_session, slug):
    o = Organization(name=f"CapCov {slug}", slug=slug)
    db.session.add(o)
    db.session.flush()
    return o


def test_capability_coverage_is_computed_from_application_mappings_not_solution_mappings(
    db_session,
):
    """A capability mapped to an application only (no solution mapping) must
    still count as covered — the pre-fix service path would have missed it."""
    from app.modules.dashboard.v2.services.capability_coverage import (
        compute_l1_capability_coverage,
    )
    from app.modules.dashboard.v2.services.executive_dashboard_service import (
        ExecutiveDashboardService,
    )
    from app.models.application_capability import ApplicationCapabilityMapping
    from app.models.application_portfolio import ApplicationComponent

    org = _org(db_session, "shared-source")

    covered_cap = BusinessCapability(
        name="Order Management", organization_id=org.id, level=1
    )
    uncovered_cap = BusinessCapability(
        name="Vendor Risk", organization_id=org.id, level=1
    )
    db.session.add_all([covered_cap, uncovered_cap])
    db.session.flush()

    app_obj = ApplicationComponent(name="Order Service", organization_id=org.id)
    db.session.add(app_obj)
    db.session.flush()

    mapping = ApplicationCapabilityMapping(
        organization_id=org.id,
        application_component_id=app_obj.id,
        business_capability_id=covered_cap.id,
    )
    db.session.add(mapping)
    db.session.flush()

    from flask import g
    g.current_org_id = org.id

    direct = compute_l1_capability_coverage()
    assert direct["total"] == 2
    assert direct["covered"] == 1
    assert direct["percentage"] == 50.0

    via_service = ExecutiveDashboardService()._get_capability_coverage()
    assert via_service == direct, (
        "the Executive Summary fragment's capability-coverage number must be "
        "identical to the shared computation, not independently derived"
    )
