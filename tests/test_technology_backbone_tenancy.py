"""Technology insert hooks must preserve ownership of their ArchiMate records."""

from types import SimpleNamespace

import pytest

HOOKS = [
    "create_node_archimate_element", "create_device_archimate_element",
    "create_systemsoftware_archimate_element", "create_technologyinterface_archimate_element",
    "create_path_archimate_element", "create_communicationnetwork_archimate_element",
    "create_technologyservice_archimate_element", "create_artifact_archimate_element",
    "create_collaboration_archimate_element",
]


@pytest.mark.parametrize("hook_name", HOOKS)
def test_backbone_insert_copies_technology_owner(hook_name):
    from app.models import technology_layer

    statements = []

    def execute(statement):
        statements.append(statement.compile().params)
        return SimpleNamespace(inserted_primary_key=[71])

    target = SimpleNamespace(
        name="Owned technology", description="Fixture", organization_id=29,
        archimate_element_id=None,
    )
    getattr(technology_layer, hook_name)(None, SimpleNamespace(execute=execute), target)
    assert statements[0].get("organization_id") == 29
    assert target.archimate_element_id == 71


def test_created_node_is_visible_in_own_radar_not_another_tenant(db_session, make_org, tenant_ctx):
    from app.models.technology_layer import Node
    from app.models.archimate_core import ArchiMateElement
    from app.modules.tech_radar.service import technology_candidates

    owner = make_org()
    other = make_org()
    node = Node(name="Owned radar node", organization_id=owner.id)
    db_session.add(node)
    db_session.flush()
    element_id = node.archimate_element_id
    element = db_session.get(ArchiMateElement, element_id)
    assert element.organization_id == owner.id
    with tenant_ctx(owner.id):
        assert element_id in {row.id for row in technology_candidates()}
    with tenant_ctx(other.id):
        assert element_id not in {row.id for row in technology_candidates()}
