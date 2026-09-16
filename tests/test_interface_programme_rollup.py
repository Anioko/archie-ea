"""Task 04: programme_rollup_service.interface_programme_rollup -- the single
authority for "what is committed against the S/4HANA investment_budget".

Against the shared fixtures in tests/conftest.py per root CLAUDE.md.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_architecture(db_session, org_id, name="Rollup Test Architecture"):
    from app.models.archimate_core import ArchitectureModel

    arch = ArchitectureModel(name=name, organization_id=org_id)
    db_session.add(arch)
    db_session.flush()
    return arch


def _make_initiative(
    db_session, architecture_id, name="Rollup Test Initiative", investment_budget=None
):
    from app.models.implementation_migration import TechnologyRoadmapInitiative

    initiative = TechnologyRoadmapInitiative(
        name=name,
        fiscal_year_start=2026,
        fiscal_year_end=2027,
        architecture_id=architecture_id,
        investment_budget=investment_budget,
    )
    db_session.add(initiative)
    db_session.flush()
    return initiative


def _make_interface_element(db_session, org_id, name="Rollup Test Interface"):
    from app.services.archimate_backbone import create_backbone_element

    return create_backbone_element(
        element_type="ApplicationInterface",
        layer="Application",
        name=name,
        organization_id=org_id,
    )


def _raise_gap(initiative_id, element_id, gap_type="protocol_change"):
    from app.modules.interface_register.services import interface_gap_service

    return interface_gap_service.raise_interface_gap(element_id, initiative_id, gap_type)


def _setup(db_session, org, budget=3_000_000):
    from app.modules.interface_register.services import plateau_pair_service

    architecture = _make_architecture(db_session, org.id)
    initiative = _make_initiative(db_session, architecture.id, investment_budget=budget)
    plateau_pair_service.provision_plateau_pair(initiative.id)
    element = _make_interface_element(db_session, org.id)
    gap = _raise_gap(initiative.id, element.id)
    return initiative, gap


def test_rollup_with_no_work_packages_is_zero_not_missing(db_session, make_org, tenant_ctx):
    """An empty sum is a real zero (nothing is committed yet), not a
    fabricated one -- distinct from a WorkPackage carrying a NULL cost."""
    from app.modules.interface_register.services import programme_rollup_service

    org = make_org("rollup-a")
    with tenant_ctx(org.id):
        initiative, _gap = _setup(db_session, org)

        rollup = programme_rollup_service.interface_programme_rollup(initiative.id)

        assert rollup["committed_cost"] == 0.0
        assert rollup["work_packages_missing_cost"] == 0
        assert rollup["work_packages"] == []
        assert rollup["investment_budget"] == 3_000_000
        assert rollup["headroom"] == 3_000_000
        assert rollup["over_budget"] is False


def test_null_estimated_cost_excluded_from_sum_and_counted(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import programme_rollup_service, work_package_service

    org = make_org("rollup-b")
    with tenant_ctx(org.id):
        initiative, gap = _setup(db_session, org)

        work_package_service.attach_work_package_to_gap(
            gap.id, name="Costed WP", estimated_cost=100_000, estimated_effort_hours=50
        )
        work_package_service.attach_work_package_to_gap(
            gap.id, name="Uncosted WP"
        )

        rollup = programme_rollup_service.interface_programme_rollup(initiative.id)

        assert rollup["committed_cost"] == 100_000.0
        assert rollup["work_packages_missing_cost"] == 1
        assert len(rollup["work_packages"]) == 2


def test_null_investment_budget_yields_none_headroom_and_none_over_budget(
    db_session, make_org, tenant_ctx
):
    """investment_budget IS NULL must never be silently treated as 0/unlimited
    -- headroom and over_budget must both surface as None, not a fabricated
    False/0 (root CLAUDE.md null-display rule)."""
    from app.modules.interface_register.services import programme_rollup_service, work_package_service

    org = make_org("rollup-c")
    with tenant_ctx(org.id):
        initiative, gap = _setup(db_session, org, budget=None)

        work_package_service.attach_work_package_to_gap(
            gap.id, name="Costed WP", estimated_cost=50_000
        )

        rollup = programme_rollup_service.interface_programme_rollup(initiative.id)

        assert rollup["investment_budget"] is None
        assert rollup["headroom"] is None
        assert rollup["over_budget"] is None
        # Committed cost is still real and computed, even with no budget to compare to.
        assert rollup["committed_cost"] == 50_000.0


def test_over_budget_true_when_committed_exceeds_budget(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import programme_rollup_service, work_package_service

    org = make_org("rollup-d")
    with tenant_ctx(org.id):
        initiative, gap = _setup(db_session, org, budget=100_000)

        work_package_service.attach_work_package_to_gap(
            gap.id, name="Overrun WP", estimated_cost=250_000
        )

        rollup = programme_rollup_service.interface_programme_rollup(initiative.id)

        assert rollup["over_budget"] is True
        assert rollup["headroom"] == -150_000.0


def test_work_package_linked_to_two_gaps_is_not_double_counted(db_session, make_org, tenant_ctx):
    """WorkPackage<->Gap is many-to-many (gap_work_packages). A WorkPackage
    referenced by two of the initiative's gaps must contribute its cost once,
    not twice."""
    from app.modules.interface_register.services import programme_rollup_service, work_package_service

    org = make_org("rollup-e")
    with tenant_ctx(org.id):
        initiative, gap_a = _setup(db_session, org)
        element_b = _make_interface_element(db_session, org.id, name="Second Interface")
        gap_b = _raise_gap(initiative.id, element_b.id, gap_type="new_interface")

        shared_wp = work_package_service.attach_work_package_to_gap(
            gap_a.id, name="Shared WP", estimated_cost=60_000
        )
        gap_b.work_packages.append(shared_wp)
        db_session.commit()

        rollup = programme_rollup_service.interface_programme_rollup(initiative.id)

        assert rollup["committed_cost"] == 60_000.0
        assert len(rollup["work_packages"]) == 1


def test_cross_org_work_package_never_contributes(db_session, make_org, tenant_ctx):
    """A WorkPackage created under a different organization must never reach
    this initiative's rollup -- WorkPackage/Gap/Plateau are all TenantMixin,
    auto-scoped by do_orm_execute; this proves that scoping actually holds
    for the ORM-relationship traversal this service relies on."""
    from app.modules.interface_register.services import programme_rollup_service, work_package_service

    org_a = make_org("rollup-f-a")
    org_b = make_org("rollup-f-b")

    with tenant_ctx(org_a.id):
        initiative_a, gap_a = _setup(db_session, org_a)
        work_package_service.attach_work_package_to_gap(
            gap_a.id, name="Org A WP", estimated_cost=10_000
        )

    with tenant_ctx(org_b.id):
        initiative_b, gap_b = _setup(db_session, org_b)
        work_package_service.attach_work_package_to_gap(
            gap_b.id, name="Org B WP", estimated_cost=999_000
        )

    with tenant_ctx(org_a.id):
        rollup_a = programme_rollup_service.interface_programme_rollup(initiative_a.id)
        assert rollup_a["committed_cost"] == 10_000.0
        assert len(rollup_a["work_packages"]) == 1
        assert rollup_a["work_packages"][0].name == "Org A WP"

    with tenant_ctx(org_b.id):
        rollup_b = programme_rollup_service.interface_programme_rollup(initiative_b.id)
        assert rollup_b["committed_cost"] == 999_000.0
        assert len(rollup_b["work_packages"]) == 1
        assert rollup_b["work_packages"][0].name == "Org B WP"
