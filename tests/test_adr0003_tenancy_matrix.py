"""ADR-0003 completion: every layer model is tenant-scoped, and stays that way.

The business, data, technology and physical layers shipped without
organization_id — not "unfiltered outside a request context" but structurally
impossible to filter. Every table was verified empty in production, which is
why the adoption could be a same-day change: there were no rows to migrate,
only columns to add and harden (`flask backfill-layer-tenancy`).

The matrix below is the specification. A model added here without TenantMixin
fails test 1; a model whose table somehow lacks the column fails test 2; and
test 3 proves the filter actually bites for one representative model per layer,
which is the part a subclass check alone cannot prove.
"""

import importlib

import pytest

# (module, class name) — the ADR-0003 adoption set, by layer.
ADOPTED = [
    # Business
    ("app.models.business_layer", "BusinessRole"),
    ("app.models.business_layer", "BusinessEvent"),
    ("app.models.process_data", "BusinessProcess"),
    ("app.models.archimate_missing_elements", "MissingBusinessCollaboration"),
    ("app.models.archimate_missing_elements", "MissingBusinessInterface"),
    ("app.models.archimate_missing_elements", "MissingBusinessInteraction"),
    ("app.models.archimate_missing_elements", "Product"),
    ("app.models.representation", "Representation"),
    # Data
    ("app.models.process_data", "DataEntity"),
    ("app.models.process_data", "DataDomain"),
    ("app.models.models", "DataStore"),
    ("app.models.application_layer", "DataObject"),
    ("app.models.all_missing_models", "ConceptualDataModel"),
    ("app.models.all_missing_models", "LogicalDataModel"),
    ("app.models.all_missing_models", "PhysicalDataModel"),
    ("app.models.all_missing_models", "DataLineage"),
    ("app.models.all_missing_models", "DataTransformation"),
    ("app.models.relationship_tables", "ProcessDataCrud"),
    ("app.models.relationship_tables", "DataObjectStorage"),
    ("app.models.data_governance", "DataCatalog"),
    ("app.models.data_governance", "DataQualityMetrics"),
    ("app.models.data_governance", "DataGovernanceWorkflow"),
    ("app.models.data_governance", "DataAccessControl"),
    ("app.models.data_governance", "DataRetentionPolicy"),
    # Technology
    ("app.models.technology_layer", "Node"),
    ("app.models.technology_layer", "Device"),
    ("app.models.technology_layer", "SystemSoftware"),
    ("app.models.technology_layer", "TechnologyInterface"),
    ("app.models.technology_layer", "Path"),
    ("app.models.technology_layer", "CommunicationNetwork"),
    ("app.models.technology_layer", "TechnologyService"),
    ("app.models.technology_layer", "TechnologyArtifact"),
    ("app.models.technology_layer", "TechnologyCollaboration"),
    ("app.models.archimate_technology", "TechnologyCollaborationFull"),
    ("app.models.archimate_technology", "TechnologyFunction"),
    ("app.models.archimate_technology", "TechnologyProcess"),
    ("app.models.archimate_technology", "TechnologyInteraction"),
    ("app.models.archimate_technology", "TechnologyEvent"),
    # Physical
    ("app.models.physical_layer", "PhysicalEquipment"),
    ("app.models.physical_layer", "PhysicalFacility"),
    ("app.models.physical_layer", "PhysicalDistributionNetwork"),
    ("app.models.physical_layer", "PhysicalMaterial"),
]

_IDS = [f"{m.rsplit('.', 1)[-1]}.{c}" for m, c in ADOPTED]


def _load(module_name, class_name):
    return getattr(importlib.import_module(module_name), class_name)


@pytest.mark.parametrize(("module_name", "class_name"), ADOPTED, ids=_IDS)
def test_model_is_tenant_scoped(app, module_name, class_name):
    from app.models.mixins import TenantMixin

    model = _load(module_name, class_name)
    assert issubclass(model, TenantMixin), (
        f"{class_name} maps tenant business data but is not TenantMixin — "
        "its rows are visible to every organisation (ADR-0003)"
    )


@pytest.mark.parametrize(("module_name", "class_name"), ADOPTED, ids=_IDS)
def test_table_carries_the_tenant_column(app, db_session, module_name, class_name):
    """The live test schema (built by create_all) must carry organization_id."""
    from sqlalchemy import inspect

    model = _load(module_name, class_name)
    columns = {c["name"] for c in inspect(db_session.get_bind()).get_columns(model.__tablename__)}
    assert "organization_id" in columns, (
        f"{model.__tablename__} has no organization_id column — the model and "
        "schema disagree, which is the drift ADR-0002 exists to prevent"
    )


# One representative per layer: the behavioural proof a subclass check can't give.
_REPRESENTATIVES = [
    ("app.models.business_layer", "BusinessRole", {"name": "Credit Controller"}),
    # DataDomain, not DataEntity: DataEntity.domain_id is NOT NULL, so it cannot
    # be built standalone; DataDomain carries the same tenancy semantics.
    ("app.models.process_data", "DataDomain", {"name": "Sales Data"}),
    ("app.models.technology_layer", "Node", {"name": "HANA Node"}),
    ("app.models.physical_layer", "PhysicalEquipment", {"name": "Kiln 3"}),
]


@pytest.mark.parametrize(
    ("module_name", "class_name", "kwargs"),
    _REPRESENTATIVES,
    ids=[c for _, c, _ in _REPRESENTATIVES],
)
def test_rows_are_invisible_across_tenants(
    app, db_session, make_org, tenant_ctx, module_name, class_name, kwargs
):
    import uuid

    model = _load(module_name, class_name)
    org_a = make_org(f"adr3-{class_name}-a")
    org_b = make_org(f"adr3-{class_name}-b")
    # Unique per run: some target tables carry UNIQUE(name), and commits under
    # the shared test database persist across runs.
    kwargs = {**kwargs, "name": f"{kwargs['name']} {uuid.uuid4().hex[:8]}"}

    with tenant_ctx(org_a.id):
        row = model(**kwargs)
        db_session.add(row)
        db_session.commit()
        assert db_session.query(model).filter_by(name=kwargs["name"]).count() == 1

    with tenant_ctx(org_b.id):
        assert db_session.query(model).filter_by(name=kwargs["name"]).count() == 0, (
            f"{class_name} row created in org {org_a.id} is visible to org "
            f"{org_b.id} — the tenant filter is not applying"
        )
