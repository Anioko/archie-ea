"""Raw backbone inserts must copy ownership from their tenant-scoped source."""

from importlib import import_module
from types import SimpleNamespace

import pytest


CASES = [
    ("application_layer", "ApplicationInterface", "create_interface_archimate_element"),
    ("application_layer", "ApplicationEvent", "create_event_archimate_element"),
    ("application_layer", "ApplicationFunction", "create_applicationfunction_archimate_element"),
    ("application_layer", "ApplicationProcess", "create_applicationprocess_archimate_element"),
    ("application_layer", "DataObject", "create_dataobject_archimate_element"),
    ("archimate_business", "BusinessCollaboration", "create_collaboration_archimate_element"),
    ("archimate_business", "BusinessInterface", "create_interface_archimate_element"),
    ("archimate_business", "Contract", "create_contract_archimate_element"),
    ("archimate_business", "Representation", "create_representation_archimate_element"),
    ("archimate_missing_elements", "MissingBusinessCollaboration", "create_collaboration_archimate"),
    ("archimate_missing_elements", "MissingBusinessInterface", "create_interface_archimate"),
    ("archimate_missing_elements", "MissingBusinessInteraction", "create_interaction_archimate"),
    ("archimate_missing_elements", "Product", "create_product_archimate"),
    ("archimate_technology", "TechnologyCollaborationFull", "create_collaboration_full_archimate_element"),
    ("archimate_technology", "TechnologyFunction", "create_function_archimate_element"),
    ("archimate_technology", "TechnologyProcess", "create_process_archimate_element"),
    ("archimate_technology", "TechnologyInteraction", "create_interaction_archimate_element"),
    ("archimate_technology", "TechnologyEvent", "create_event_archimate_element"),
    ("business_layer", "BusinessActor", "create_actor_archimate_element"),
    ("business_layer", "BusinessRole", "create_role_archimate_element"),
    ("business_layer", "BusinessService", "create_service_archimate_element"),
    ("business_layer", "BusinessObject", "create_object_archimate_element"),
    ("business_layer", "BusinessEvent", "create_event_archimate_element"),
    ("process_data", "BusinessProcess", "create_businessprocess_archimate_element"),
]


@pytest.mark.parametrize("module_name,model_name,hook_name", CASES)
@pytest.mark.parametrize("owner", [29, 41])
def test_backbone_insert_keeps_source_owner(module_name, model_name, hook_name, owner):
    module = import_module(f"app.models.{module_name}")
    model = getattr(module, model_name)
    # Inspect the real mapping: a fabricated target attribute must not hide a
    # source model that has no organisation ownership in the first place.
    assert "organization_id" in model.__table__.columns
    target = SimpleNamespace(name="Owned source", description="Fixture",
                             organization_id=owner, archimate_element_id=None)
    statements = []

    def execute(statement):
        statements.append(statement.compile().params)
        return SimpleNamespace(inserted_primary_key=[71])

    hook = getattr(module, hook_name)
    connection = SimpleNamespace(execute=execute)
    hook(None, connection, target)
    assert len(statements) == 1
    assert statements[0].get("organization_id") == owner
    assert target.archimate_element_id == 71
    hook(None, connection, target)
    assert len(statements) == 1, "Existing backbone link must not be replaced"


@pytest.mark.parametrize("model_name", [
    "PhysicalEquipment", "PhysicalFacility", "PhysicalDistributionNetwork", "PhysicalMaterial",
])
def test_physical_registered_insert_listener_keeps_source_owner(model_name):
    from app.models import physical_layer
    from sqlalchemy import inspect

    model = getattr(physical_layer, model_name)
    assert "organization_id" in model.__table__.columns
    target = SimpleNamespace(name="Owned physical source", description="Fixture",
                             organization_id=29, archimate_element_id=None)
    statements = []

    def execute(statement):
        statements.append(statement.compile().params)
        return SimpleNamespace(inserted_primary_key=[71])

    mapper = inspect(model)
    mapper.dispatch.before_insert(mapper, SimpleNamespace(execute=execute),
                                  SimpleNamespace(obj=lambda: target))
    assert len(statements) == 1
    assert statements[0].get("organization_id") == 29
    assert target.archimate_element_id == 71
