"""Task 03, Round 2 (D3): interface-register plateau-transition gaps must not
leak into capability-gap surfaces -- the enterprise Gap Analysis screen/
counters, the AI roadmap generator, and the capability-roadmap gap listing.

Against the shared fixtures in tests/conftest.py per root CLAUDE.md.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_architecture(db_session, org_id, name="Isolation Test Architecture"):
    from app.models.archimate_core import ArchitectureModel

    arch = ArchitectureModel(name=name, organization_id=org_id)
    db_session.add(arch)
    db_session.flush()
    return arch


def _make_initiative(db_session, architecture_id, name="Isolation Test Initiative"):
    from app.models.implementation_migration import TechnologyRoadmapInitiative

    initiative = TechnologyRoadmapInitiative(
        name=name,
        fiscal_year_start=2026,
        fiscal_year_end=2027,
        architecture_id=architecture_id,
    )
    db_session.add(initiative)
    db_session.flush()
    return initiative


def _make_interface_element(db_session, org_id, name="Isolation Test Interface"):
    from app.services.archimate_backbone import create_backbone_element

    return create_backbone_element(
        element_type="ApplicationInterface",
        layer="Application",
        name=name,
        organization_id=org_id,
    )


def _raise_one_interface_gap(db_session, make_org, tenant_ctx, org_suffix):
    """Provision a plateau pair and raise one real interface gap, returning
    (org, interface_gap, capability_gap) -- the capability_gap is a plain Gap
    with the default gap_kind, seeded in the same org so both are visible to
    the same tenant-scoped query."""
    from app import db
    from app.models.implementation_migration import Gap
    from app.modules.interface_register.services import interface_gap_service as service
    from app.modules.interface_register.services import plateau_pair_service

    org = make_org(f"isolation-{org_suffix}")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)
        element = _make_interface_element(db_session, org.id)
        plateau_pair_service.provision_plateau_pair(initiative.id)

        interface_gap = service.raise_interface_gap(element.id, initiative.id, "new_interface")

        capability_gap = Gap(
            name="Isolation capability gap",
            resolution_status="identified",
            severity="critical",
            architecture_id=architecture.id,
        )
        db_session.add(capability_gap)
        db_session.commit()

        return org, interface_gap, capability_gap, architecture


def test_unified_gap_register_does_not_double_count_retirement_type_collision(
    db_session, make_org, tenant_ctx
):
    """Refuter round-2 finding: interface-register's GAP_TYPES and
    gap_register_service._ROADMAP_GAP_TYPES both use the string
    "retirement" for unrelated concepts (an interface being decommissioned
    vs. an application/technology being retired). An interface gap raised
    with gap_type="retirement" must not appear in the unified capability
    gap register at all -- it is not a capability shortfall and it is not
    a roadmap/opportunities gap in the Phase E sense, it is a
    plateau-transition row from the interface register.

    Before the D3 fix in this round, this gap leaked in TWICE: once
    unfiltered via the Phase D "implementation" source query, and again
    via the Phase E "roadmap" source query matching gap_type="retirement".
    """
    from app import db
    from app.modules.interface_register.services import interface_gap_service as service
    from app.modules.interface_register.services import plateau_pair_service
    from app.services.gap_register_service import get_unified_gap_register

    org = make_org("isolation-retirement-collision")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)
        element = _make_interface_element(db_session, org.id)
        plateau_pair_service.provision_plateau_pair(initiative.id)

        interface_gap = service.raise_interface_gap(element.id, initiative.id, "retirement")
        db.session.commit()

        results = get_unified_gap_register()
        matches = [r for r in results if r.get("gap_id") == interface_gap.id]
        assert matches == [], (
            "an interface-register plateau-transition gap with "
            "gap_type='retirement' must not appear in the unified "
            f"capability gap register at all; found: {matches}"
        )


def test_gap_analysis_query_excludes_plateau_transition_gaps(db_session, make_org, tenant_ctx):
    """The exact filter added to unified_enterprise_routes.gap_analysis."""
    from app.models.implementation_migration import Gap

    org, interface_gap, capability_gap, _arch = _raise_one_interface_gap(
        db_session, make_org, tenant_ctx, "a"
    )
    with tenant_ctx(org.id):
        gaps = Gap.query.filter(Gap.gap_kind != "plateau_transition").all()
        gap_ids = {g.id for g in gaps}
        assert capability_gap.id in gap_ids
        assert interface_gap.id not in gap_ids


def test_roadmap_generator_excludes_plateau_transition_gaps(db_session, make_org, tenant_ctx):
    """RoadmapGenerator._get_gaps_to_process must not sweep interface gaps
    into an AI-generated capability roadmap, even though both share
    resolution_status='identified' and the same architecture_id."""
    from app.modules.architecture.services.roadmap_generator import RoadmapGenerator

    org, interface_gap, capability_gap, architecture = _raise_one_interface_gap(
        db_session, make_org, tenant_ctx, "b"
    )
    with tenant_ctx(org.id):
        generator = RoadmapGenerator()
        gaps = generator._get_gaps_to_process(
            gap_ids=None, architecture_id=architecture.id, priority_filter=None
        )
        gap_ids = {g.id for g in gaps}
        assert capability_gap.id in gap_ids
        assert interface_gap.id not in gap_ids


def test_gap_archimate_service_roadmap_listing_excludes_plateau_transition_gaps(
    db_session, make_org, tenant_ctx
):
    from app.modules.architecture.services.gap_archimate_service import GapArchiMateService

    org, interface_gap, capability_gap, _arch = _raise_one_interface_gap(
        db_session, make_org, tenant_ctx, "c"
    )
    with tenant_ctx(org.id):
        service = GapArchiMateService()
        gaps = service.get_gaps_for_roadmap()
        gap_ids = {g.id for g in gaps}
        assert capability_gap.id in gap_ids
        assert interface_gap.id not in gap_ids
