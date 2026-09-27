"""Interface Register service tests (SAP S/4HANA Interface Register, Task 02).

Against the shared fixtures in tests/conftest.py (db_session, make_org,
tenant_ctx) per root CLAUDE.md — not the hand-rolled module-scoped pattern.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_architecture(db_session, org_id, name="Test Architecture"):
    from app.models.archimate_core import ArchitectureModel

    arch = ArchitectureModel(name=name, organization_id=org_id)
    db_session.add(arch)
    db_session.flush()
    return arch


def _make_initiative(db_session, architecture_id, name="Test Initiative"):
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


def _make_component(db_session, org_id, name):
    from app.models.application_portfolio import ApplicationComponent
    from app.services.archimate_backbone import create_backbone_element

    element = create_backbone_element(
        element_type="ApplicationComponent",
        layer="Application",
        name=name,
        organization_id=org_id,
    )
    component = ApplicationComponent(
        name=name, organization_id=org_id, archimate_element_id=element.id
    )
    db_session.add(component)
    db_session.flush()
    return component


def test_create_interface_writes_one_of_each(db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.models.integration_metadata import ApplicationInterfaceMetadata, SystemDependency
    from app.modules.interface_register.services import interface_register_service as service

    org = make_org("a")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)
        provider = _make_component(db_session, org.id, "SAP S/4HANA")
        consumer = _make_component(db_session, org.id, "Salesforce CRM")

        form = {
            "name": "Customer Master Replication",
            "interface_type": "REST",
            "protocol": "HTTPS",
            "business_criticality": "High",
            "provider_component_id": str(provider.id),
            "consumer_component_id": str(consumer.id),
        }

        element = service.create_interface(initiative.id, form, org.id)

        assert element.type == "ApplicationInterface"
        assert element.layer == "Application"
        assert element.custom_properties["source_model"] == "InterfaceRegister"
        assert element.custom_properties["initiative_id"] == initiative.id

        metadata_count = ApplicationInterfaceMetadata.query.filter_by(
            archimate_element_id=element.id
        ).count()
        assert metadata_count == 1

        dependency_count = SystemDependency.query.filter_by(interface_id=element.id).count()
        assert dependency_count == 2

        relationship_count = (
            ArchiMateRelationship.query.filter(
                ArchiMateRelationship.source_id == element.id
            ).count()
            + ArchiMateRelationship.query.filter(
                ArchiMateRelationship.target_id == element.id
            ).count()
        )
        assert relationship_count == 2


def test_create_interface_bad_component_rolls_back_leaving_no_orphan(
    db_session, make_org, tenant_ctx
):
    from app.models.archimate_core import ArchiMateElement
    from app.modules.interface_register.services import interface_register_service as service

    org = make_org("a")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)

        before_count = ArchiMateElement.query.filter_by(
            type="ApplicationInterface"
        ).count()

        form = {
            "name": "Bad Interface",
            "interface_type": "REST",
            "protocol": "HTTPS",
            "provider_component_id": "999999",
        }

        with pytest.raises(service.InterfaceRegisterError):
            service.create_interface(initiative.id, form, org.id)

        after_count = ArchiMateElement.query.filter_by(
            type="ApplicationInterface"
        ).count()
        assert after_count == before_count


def test_cross_org_read_returns_zero_rows(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import interface_register_service as service

    org_a, org_b = make_org("a"), make_org("b")

    with tenant_ctx(org_a.id):
        architecture = _make_architecture(db_session, org_a.id)
        initiative = _make_initiative(db_session, architecture.id)
        form = {
            "name": "Org A Interface",
            "interface_type": "REST",
            "protocol": "HTTPS",
        }
        service.create_interface(initiative.id, form, org_a.id)

    with tenant_ctx(org_b.id):
        with pytest.raises(service.InterfaceRegisterError):
            service.list_interfaces(initiative.id, org_b.id)


def test_update_interface_replaces_not_accumulates_relationships(
    db_session, make_org, tenant_ctx
):
    from app.models.archimate_core import ArchiMateRelationship
    from app.models.integration_metadata import SystemDependency
    from app.modules.interface_register.services import interface_register_service as service

    org = make_org("a")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)
        provider_1 = _make_component(db_session, org.id, "Provider One")
        provider_2 = _make_component(db_session, org.id, "Provider Two")

        form = {
            "name": "Interface",
            "interface_type": "REST",
            "protocol": "HTTPS",
            "provider_component_id": str(provider_1.id),
        }
        element = service.create_interface(initiative.id, form, org.id)

        update_form = {
            "name": "Interface",
            "interface_type": "REST",
            "protocol": "HTTPS",
            "provider_component_id": str(provider_2.id),
        }
        service.update_interface(element.id, update_form, org.id)

        composition_rels = ArchiMateRelationship.query.filter_by(
            target_id=element.id, type="composition"
        ).all()
        assert len(composition_rels) == 1
        assert composition_rels[0].source_id == provider_2.archimate_element_id

        # D4 fix: SystemDependency must move with ArchiMateRelationship, not
        # be left disagreeing with it (store-agreement).
        dependencies = SystemDependency.query.filter_by(
            interface_id=element.id, dependency_type="service"
        ).all()
        assert len(dependencies) == 1
        assert dependencies[0].source_system_id == provider_2.archimate_element_id
        assert dependencies[0].target_system_id == element.id


def test_update_interface_unchanged_provider_leaves_relationship_untouched(
    db_session, make_org, tenant_ctx
):
    """N1 regression: re-saving an interface with the SAME provider/consumer
    (e.g. only editing the name — the edit form now always posts the
    current provider/consumer per D5) must not delete-and-recreate the
    composition/serving ArchiMateRelationship rows. Doing so would silently
    wipe connection_spec/custom_label/description on the relationship and
    mint a new id/created_at even though nothing about the link changed."""
    from app.models.archimate_core import ArchiMateRelationship
    from app.models.integration_metadata import SystemDependency
    from app.modules.interface_register.services import interface_register_service as service

    org = make_org("a")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)
        provider = _make_component(db_session, org.id, "Provider One")
        consumer = _make_component(db_session, org.id, "Consumer One")

        form = {
            "name": "Interface",
            "interface_type": "REST",
            "protocol": "HTTPS",
            "provider_component_id": str(provider.id),
            "consumer_component_id": str(consumer.id),
        }
        element = service.create_interface(initiative.id, form, org.id)

        composition_rel = ArchiMateRelationship.query.filter_by(
            target_id=element.id, type="composition"
        ).first()
        serving_rel = ArchiMateRelationship.query.filter_by(
            source_id=element.id, type="serving"
        ).first()

        # Simulate an architect having set connection_spec/custom_label on
        # the relationship rows via the Composer.
        composition_rel.connection_spec = {"note": "set via Composer"}
        composition_rel.custom_label = "Nightly batch"
        db_session.flush()

        composition_id_before = composition_rel.id
        composition_created_at_before = composition_rel.created_at
        serving_id_before = serving_rel.id
        serving_created_at_before = serving_rel.created_at
        dependency_count_before = SystemDependency.query.filter_by(
            interface_id=element.id
        ).count()

        # Edit form D5-rehydrates the SAME provider/consumer, only the name
        # actually changes.
        update_form = {
            "name": "Interface (renamed)",
            "interface_type": "REST",
            "protocol": "HTTPS",
            "provider_component_id": str(provider.id),
            "consumer_component_id": str(consumer.id),
        }
        service.update_interface(element.id, update_form, org.id)

        composition_rel_after = ArchiMateRelationship.query.filter_by(
            target_id=element.id, type="composition"
        ).first()
        serving_rel_after = ArchiMateRelationship.query.filter_by(
            source_id=element.id, type="serving"
        ).first()

        assert composition_rel_after.id == composition_id_before
        assert composition_rel_after.created_at == composition_created_at_before
        assert composition_rel_after.connection_spec == {"note": "set via Composer"}
        assert composition_rel_after.custom_label == "Nightly batch"

        assert serving_rel_after.id == serving_id_before
        assert serving_rel_after.created_at == serving_created_at_before

        dependency_count_after = SystemDependency.query.filter_by(
            interface_id=element.id
        ).count()
        assert dependency_count_after == dependency_count_before


def test_update_interface_does_not_delete_unowned_relationship(
    db_session, make_org, tenant_ctx
):
    """N1 regression (round 5): the CURRENT-provider lookup itself, not just
    the delete predicate, must be narrowed to a relationship this module
    actually created -- an unqualified
    ArchiMateRelationship.query.filter_by(target_id=..., type='composition').first()
    can return an unrelated row when more than one composition relationship
    touches the same element, and the module then deletes "the current one"
    it just resolved to the wrong row.

    Regression-proofs both failure modes by inserting the UNOWNED
    relationship BEFORE this module's own (so an insertion-order-based
    .first() would pick the unowned row first, not last) and asserting the
    OWNED row -- not merely "a row" -- is the one actually replaced."""
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.models.integration_metadata import SystemDependency
    from app.modules.interface_register.services import interface_register_service as service
    from app.services.archimate_backbone import create_backbone_element

    org = make_org("a")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)
        provider_1 = _make_component(db_session, org.id, "Provider One")
        provider_2 = _make_component(db_session, org.id, "Provider Two")

        # Create the interface with NO provider yet, so this module has not
        # written any composition relationship for it.
        form = {
            "name": "Interface",
            "interface_type": "REST",
            "protocol": "HTTPS",
        }
        element = service.create_interface(initiative.id, form, org.id)

        # A composition relationship drawn some other way (e.g. the
        # Composer), not owned by this module, inserted BEFORE this
        # module's own -- so it holds the lower id / earlier insertion
        # order, and would be what an unordered .first() returns.
        other_source = create_backbone_element(
            element_type="ApplicationComponent",
            layer="Application",
            name="Composer-drawn component",
            organization_id=org.id,
        )
        unowned_rel = ArchiMateRelationship(
            type="composition", source_id=other_source.id, target_id=element.id
        )
        db_session.add(unowned_rel)
        db_session.flush()
        unowned_rel_id = unowned_rel.id

        # This module now records its OWN provider relationship (provider_1),
        # inserted AFTER the unowned one.
        service.update_interface(
            element.id,
            {
                "name": "Interface",
                "interface_type": "REST",
                "protocol": "HTTPS",
                "provider_component_id": str(provider_1.id),
            },
            org.id,
        )
        owned_rel_before = ArchiMateRelationship.query.filter_by(
            type="composition", source_id=provider_1.archimate_element_id, target_id=element.id
        ).first()
        assert owned_rel_before is not None
        owned_rel_before_id = owned_rel_before.id

        # Now replace the provider. Only the OWNED (provider_1) relationship
        # should be deleted and replaced by a new one for provider_2; the
        # unowned Composer-drawn relationship must be untouched.
        update_form = {
            "name": "Interface",
            "interface_type": "REST",
            "protocol": "HTTPS",
            "provider_component_id": str(provider_2.id),
        }
        service.update_interface(element.id, update_form, org.id)

        # The unowned row is unchanged -- same id, still present.
        still_present_unowned = ArchiMateRelationship.query.filter_by(
            id=unowned_rel_id
        ).first()
        assert still_present_unowned is not None
        assert still_present_unowned.source_id == other_source.id

        # The OWNED row (provider_1's) was deleted, not merely "a" row.
        assert (
            ArchiMateRelationship.query.filter_by(id=owned_rel_before_id).first()
            is None
        )

        # Exactly one composition relationship now points at the NEW
        # provider (provider_2), and exactly two composition relationships
        # touch the element in total: the untouched unowned one plus the
        # new owned one -- never a duplicate, never zero.
        composition_rels = ArchiMateRelationship.query.filter_by(
            type="composition", target_id=element.id
        ).all()
        assert len(composition_rels) == 2
        new_owned = [
            r for r in composition_rels if r.source_id == provider_2.archimate_element_id
        ]
        assert len(new_owned) == 1
        assert {r.id for r in composition_rels} == {unowned_rel_id, new_owned[0].id}

        # SystemDependency mirrors the same story: exactly one provider-side
        # row, and it points at provider_2, not provider_1.
        provider_side_deps = SystemDependency.query.filter_by(
            target_system_id=element.id, interface_id=element.id, dependency_type="service"
        ).all()
        assert len(provider_side_deps) == 1
        assert provider_side_deps[0].source_system_id == provider_2.archimate_element_id
