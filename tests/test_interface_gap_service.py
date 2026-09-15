"""Task 03: interface_gap_service.raise_interface_gap — gap_type allow-list,
"set up the comparison first" rejection, and the explicit validate_gap_kind()
call surfacing as InterfaceRegisterError (route's inline 4xx path).

Against the shared fixtures in tests/conftest.py per root CLAUDE.md.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_architecture(db_session, org_id, name="Interface Gap Test Architecture"):
    from app.models.archimate_core import ArchitectureModel

    arch = ArchitectureModel(name=name, organization_id=org_id)
    db_session.add(arch)
    db_session.flush()
    return arch


def _make_initiative(db_session, architecture_id, name="Interface Gap Test Initiative"):
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


def _make_interface_element(db_session, org_id, name="Smoke Interface"):
    from app.services.archimate_backbone import create_backbone_element

    return create_backbone_element(
        element_type="ApplicationInterface",
        layer="Application",
        name=name,
        organization_id=org_id,
    )


def test_raise_interface_gap_without_comparison_set_up_rejects(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import interface_gap_service as service

    org = make_org("gapservice-a")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)
        element = _make_interface_element(db_session, org.id)

        with pytest.raises(service.InterfaceRegisterError, match="Set up the As-is/To-be"):
            service.raise_interface_gap(element.id, initiative.id, "protocol_change")


def test_raise_interface_gap_invalid_gap_type_rejects(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import interface_gap_service as service
    from app.modules.interface_register.services import plateau_pair_service

    org = make_org("gapservice-b")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)
        element = _make_interface_element(db_session, org.id)
        plateau_pair_service.provision_plateau_pair(initiative.id)

        with pytest.raises(service.InterfaceRegisterError, match="Invalid gap type"):
            service.raise_interface_gap(element.id, initiative.id, "not_a_real_type")


def test_raise_interface_gap_unknown_element_rejects(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import interface_gap_service as service

    org = make_org("gapservice-c")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)

        with pytest.raises(service.InterfaceRegisterError, match="not found"):
            service.raise_interface_gap(999999999, initiative.id, "protocol_change")


def test_raise_interface_gap_writes_a_valid_plateau_transition_gap(db_session, make_org, tenant_ctx):
    from app.models.implementation_migration import GAP_KIND_PLATEAU_TRANSITION
    from app.modules.interface_register.services import interface_gap_service as service
    from app.modules.interface_register.services import plateau_pair_service

    org = make_org("gapservice-d")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)
        element = _make_interface_element(db_session, org.id)
        as_is, to_be = plateau_pair_service.provision_plateau_pair(initiative.id)

        gap = service.raise_interface_gap(element.id, initiative.id, "new_interface")

        assert gap.id is not None
        assert gap.gap_kind == GAP_KIND_PLATEAU_TRANSITION
        assert gap.gap_type == "new_interface"
        assert gap.archimate_element_id == element.id
        assert gap.originating_plateau_id == as_is.id
        assert gap.target_plateau_id == to_be.id
