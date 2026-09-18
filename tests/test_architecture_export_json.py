"""Fast, non-browser regression coverage for GET /architecture/export?format=json.

tests/smoke/test_architecture_download.py::test_populated_architecture_download[json]
already exercises this end-to-end through a real browser, but that smoke run
takes ~47 minutes to catch a defect this test catches in well under a second:
ArchitectureImportExportService.export_to_json() called a .to_dict() method
that ArchiMateRelationship did not define (ArchiMateElement's has always
existed), so exporting an architecture with at least one relationship raised
AttributeError. The fix adds ArchiMateRelationship.to_dict() and calls both
models' own to_dict() directly - not the compact 8/5-key
_element_to_dict/_relationship_to_dict helpers from
architecture_crud_routes.py, which exist for the list APIs and would silently
narrow this export to a fraction of its declared columns.

This test pins full-fidelity export two ways: (1) representative
non-trivial fields - including custom_properties and building_block_type,
the kind of TOGAF/tagged-value data that a narrow projection drops first -
round-trip with their real values, and (2) the exported key *set* for both
an element and a relationship equals every column the model declares, not
just a fixed handful. Either assertion alone would have caught the original
8-field/5-field regression; both are kept because they fail for different
reasons and pin different parts of the contract.

Deliberately not asserted: the `plateau` key (ArchiMateElement's
togaf_plateau column, mapped explicitly to DB column name "plateau"). A
same-named relationship backref (Plateau.archimate_element, backref="plateau")
shadows it on the model instance, so to_dict()'s generic
getattr(self, col.name) loop reads the relationship, not the column, for
that one field. That collision predates this task, is not part of its scope,
and is called out in the build report rather than asserted on here as if it
round-tripped correctly.
"""
from __future__ import annotations

import json
import os
import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def test_export_to_json_serializes_seeded_element_and_relationship(db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.modules.architecture.services.architecture_import_export_service import (
        ArchitectureImportExportService,
    )

    org = make_org("export-json")
    with tenant_ctx(org.id):
        element = ArchiMateElement(
            name=f"Export Element {uuid.uuid4().hex[:6]}",
            type="BusinessService",
            layer="business",
            description="Seeded for the JSON export regression test.",
            organization_id=org.id,
            building_block_type="ABB",
            custom_properties={"tagged_value": "CMP-043"},
        )
        db_session.add(element)
        db_session.flush()

        relationship = ArchiMateRelationship(
            type="realization",
            source_id=element.id,
            target_id=element.id,
            organization_id=org.id,
            description="Seeded relationship for the JSON export regression test.",
            connection_spec={"multiplicity": "1..*"},
        )
        db_session.add(relationship)
        db_session.flush()

        file_path, filename = ArchitectureImportExportService.export_to_json()

    try:
        assert filename.startswith("architecture_export_")
        assert filename.endswith(".json")

        with open(file_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert "exported_at" in data

        exported_elements = {e["id"]: e for e in data["elements"]}
        assert element.id in exported_elements, (
            "seeded element missing from JSON export - export_to_json did not "
            "run (or did not serialize real rows)"
        )
        exported_element = exported_elements[element.id]
        assert exported_element["name"] == element.name
        assert exported_element["type"] == "BusinessService"
        assert exported_element["layer"] == "business"
        assert exported_element["description"] == element.description
        assert exported_element["organization_id"] == org.id
        assert exported_element["building_block_type"] == "ABB", (
            "TOGAF building-block classification did not round-trip through "
            "the export - the narrow 8-field projection drops this field"
        )
        assert exported_element["custom_properties"] == {"tagged_value": "CMP-043"}, (
            "custom tagged-value properties did not round-trip through the "
            "export - the narrow 8-field projection drops this field"
        )

        expected_element_keys = {col.name for col in ArchiMateElement.__table__.columns}
        assert set(exported_element.keys()) == expected_element_keys, (
            "export_to_json() no longer serializes every declared "
            "ArchiMateElement column - the export contract narrowed"
        )

        exported_relationships = {r["id"]: r for r in data["relationships"]}
        assert relationship.id in exported_relationships, (
            "seeded relationship missing from JSON export"
        )
        exported_relationship = exported_relationships[relationship.id]
        assert exported_relationship["type"] == "realization"
        assert exported_relationship["source_id"] == element.id
        assert exported_relationship["target_id"] == element.id
        assert exported_relationship["organization_id"] == org.id
        assert exported_relationship["description"] == relationship.description
        assert exported_relationship["connection_spec"] == {"multiplicity": "1..*"}, (
            "structured connection_spec did not round-trip through the export"
        )

        expected_relationship_keys = {col.name for col in ArchiMateRelationship.__table__.columns}
        assert set(exported_relationship.keys()) == expected_relationship_keys, (
            "export_to_json() no longer serializes every declared "
            "ArchiMateRelationship column - the export contract narrowed"
        )
    finally:
        if os.path.exists(file_path):
            os.unlink(file_path)
