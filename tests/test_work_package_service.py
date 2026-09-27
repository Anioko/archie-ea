"""Task 04: work_package_service.attach_work_package_to_gap -- the write path
for the S/4HANA programme costing rollup.

Against the shared fixtures in tests/conftest.py per root CLAUDE.md.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_architecture(db_session, org_id, name="WP Service Test Architecture"):
    from app.models.archimate_core import ArchitectureModel

    arch = ArchitectureModel(name=name, organization_id=org_id)
    db_session.add(arch)
    db_session.flush()
    return arch


def _make_initiative(db_session, architecture_id, name="WP Service Test Initiative"):
    from app.models.implementation_migration import TechnologyRoadmapInitiative

    initiative = TechnologyRoadmapInitiative(
        name=name,
        fiscal_year_start=2026,
        fiscal_year_end=2027,
        architecture_id=architecture_id,
        investment_budget=3_000_000,
    )
    db_session.add(initiative)
    db_session.flush()
    return initiative


def _make_interface_element(db_session, org_id, name="WP Service Test Interface"):
    from app.services.archimate_backbone import create_backbone_element

    return create_backbone_element(
        element_type="ApplicationInterface",
        layer="Application",
        name=name,
        organization_id=org_id,
    )


def _setup_gap_with_initiative(db_session, org):
    from app.modules.interface_register.services import interface_gap_service, plateau_pair_service

    architecture = _make_architecture(db_session, org.id)
    initiative = _make_initiative(db_session, architecture.id)
    plateau_pair_service.provision_plateau_pair(initiative.id)
    element = _make_interface_element(db_session, org.id)
    gap = interface_gap_service.raise_interface_gap(element.id, initiative.id, "protocol_change")
    return gap, initiative


def _setup_gap(db_session, org):
    gap, _initiative = _setup_gap_with_initiative(db_session, org)
    return gap


def test_attach_work_package_sets_cost_and_effort(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import work_package_service

    org = make_org("wpservice-a")
    with tenant_ctx(org.id):
        gap = _setup_gap(db_session, org)

        wp = work_package_service.attach_work_package_to_gap(
            gap.id, name="Costed WP", estimated_cost="125000.50", estimated_effort_hours="80"
        )

        assert wp.id is not None
        assert wp.estimated_cost == 125000.50
        assert wp.estimated_effort_hours == 80
        assert wp in gap.work_packages


def test_attach_work_package_with_no_cost_or_effort_leaves_them_null(db_session, make_org, tenant_ctx):
    """Blank form fields must persist as NULL, never a fabricated 0 --
    the rollup service depends on this to distinguish 'not estimated' from
    'measured at zero'."""
    from app.modules.interface_register.services import work_package_service

    org = make_org("wpservice-b")
    with tenant_ctx(org.id):
        gap = _setup_gap(db_session, org)

        wp = work_package_service.attach_work_package_to_gap(gap.id, name="Bare WP")

        assert wp.estimated_cost is None
        assert wp.estimated_effort_hours is None


def test_attach_work_package_defaults_name_when_blank(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import work_package_service

    org = make_org("wpservice-c")
    with tenant_ctx(org.id):
        gap = _setup_gap(db_session, org)

        wp = work_package_service.attach_work_package_to_gap(gap.id, name="   ")

        assert wp.name.strip() != ""
        assert gap.name in wp.name


def test_attach_work_package_rejects_non_numeric_cost(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import work_package_service
    from app.modules.interface_register.services.interface_register_service import (
        InterfaceRegisterError,
    )

    org = make_org("wpservice-d")
    with tenant_ctx(org.id):
        gap = _setup_gap(db_session, org)

        with pytest.raises(InterfaceRegisterError, match="numeric"):
            work_package_service.attach_work_package_to_gap(
                gap.id, name="Bad WP", estimated_cost="not-a-number"
            )


def test_attach_work_package_rejects_unknown_gap(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import work_package_service
    from app.modules.interface_register.services.interface_register_service import (
        InterfaceRegisterError,
    )

    org = make_org("wpservice-e")
    with tenant_ctx(org.id):
        with pytest.raises(InterfaceRegisterError, match="not found"):
            work_package_service.attach_work_package_to_gap(999999999, name="Orphan WP")


def test_attach_work_package_rejects_nan_cost(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import work_package_service
    from app.modules.interface_register.services.interface_register_service import (
        InterfaceRegisterError,
    )

    org = make_org("wpservice-nan")
    with tenant_ctx(org.id):
        gap = _setup_gap(db_session, org)

        with pytest.raises(InterfaceRegisterError, match="finite"):
            work_package_service.attach_work_package_to_gap(
                gap.id, name="NaN WP", estimated_cost="nan"
            )


def test_attach_work_package_rejects_infinite_effort(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import work_package_service
    from app.modules.interface_register.services.interface_register_service import (
        InterfaceRegisterError,
    )

    org = make_org("wpservice-inf")
    with tenant_ctx(org.id):
        gap = _setup_gap(db_session, org)

        with pytest.raises(InterfaceRegisterError, match="finite"):
            work_package_service.attach_work_package_to_gap(
                gap.id, name="Infinite WP", estimated_effort_hours="inf"
            )


def test_attach_work_package_rejects_negative_cost(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import work_package_service
    from app.modules.interface_register.services.interface_register_service import (
        InterfaceRegisterError,
    )

    org = make_org("wpservice-neg")
    with tenant_ctx(org.id):
        gap = _setup_gap(db_session, org)

        with pytest.raises(InterfaceRegisterError, match="negative"):
            work_package_service.attach_work_package_to_gap(
                gap.id, name="Negative WP", estimated_cost="-500000"
            )


def test_attach_work_package_rejects_negative_effort(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import work_package_service
    from app.modules.interface_register.services.interface_register_service import (
        InterfaceRegisterError,
    )

    org = make_org("wpservice-neg2")
    with tenant_ctx(org.id):
        gap = _setup_gap(db_session, org)

        with pytest.raises(InterfaceRegisterError, match="negative"):
            work_package_service.attach_work_package_to_gap(
                gap.id, name="Negative Hours WP", estimated_effort_hours="-5"
            )


def test_attach_work_package_rejects_gap_from_different_initiative(db_session, make_org, tenant_ctx):
    """D3: posting a foreign initiative_id must not let the wrong programme's
    budget absorb the cost."""
    from app.modules.interface_register.services import work_package_service
    from app.modules.interface_register.services.interface_register_service import (
        InterfaceRegisterError,
    )

    org = make_org("wpservice-cross")
    with tenant_ctx(org.id):
        gap_a, initiative_a = _setup_gap_with_initiative(db_session, org)
        gap_b, initiative_b = _setup_gap_with_initiative(db_session, org)

        with pytest.raises(InterfaceRegisterError, match="does not belong"):
            work_package_service.attach_work_package_to_gap(
                gap_b.id, initiative_id=initiative_a.id, name="Cross-initiative WP"
            )

        # Same initiative id as the gap's own initiative must still succeed.
        wp = work_package_service.attach_work_package_to_gap(
            gap_a.id, initiative_id=initiative_a.id, name="Same-initiative WP"
        )
        assert wp.id is not None


def test_attach_work_package_rejects_effort_hours_above_int4_ceiling(db_session, make_org, tenant_ctx):
    """D7: estimated_effort_hours is a Postgres db.Integer (int4, max
    2,147,483,647). Without a ceiling check, a value above that raises
    psycopg2.errors.NumericValueOutOfRange at commit time -- a DataError,
    not an InterfaceRegisterError -- which comparison_routes.py's
    `except InterfaceRegisterError` does not catch, producing an
    unhandled 500 instead of a clean validation flash."""
    from app.modules.interface_register.services import work_package_service
    from app.modules.interface_register.services.interface_register_service import (
        InterfaceRegisterError,
    )

    org = make_org("wpservice-ceiling")
    with tenant_ctx(org.id):
        gap = _setup_gap(db_session, org)

        with pytest.raises(InterfaceRegisterError, match="2,147,483,647"):
            work_package_service.attach_work_package_to_gap(
                gap.id, name="Overflow WP", estimated_effort_hours="3000000000"
            )


def test_attach_work_package_rejects_capability_shortfall_gap(db_session, make_org, tenant_ctx):
    """A plain capability-shortfall Gap (default gap_kind) must never accept
    a work package through this path -- this is the interface register's own
    vocabulary boundary (see the gap_kind isolation work in Task 03)."""
    from app.models.implementation_migration import Gap
    from app.modules.interface_register.services import work_package_service
    from app.modules.interface_register.services.interface_register_service import (
        InterfaceRegisterError,
    )

    org = make_org("wpservice-f")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        capability_gap = Gap(name="A capability shortfall", architecture_id=architecture.id)
        db_session.add(capability_gap)
        db_session.flush()

        with pytest.raises(InterfaceRegisterError, match="not found"):
            work_package_service.attach_work_package_to_gap(
                capability_gap.id, name="Should not attach"
            )
