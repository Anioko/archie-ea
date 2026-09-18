"""Fast, non-browser regression coverage for GET /architecture/export?format=json.

tests/smoke/test_architecture_download.py::test_populated_architecture_download[json]
already exercises this end-to-end through a real browser, but that smoke run
takes ~47 minutes to catch a defect this test catches in well under a second:
ArchitectureImportExportService.export_to_json() called a .to_dict() method
that neither ArchiMateElement nor ArchiMateRelationship defines, so every JSON
export raised AttributeError and returned HTTP 400 to every caller, in every
environment. The fix reuses the existing, already-correct
_element_to_dict/_relationship_to_dict helpers from
app.modules.architecture.routes.architecture_crud_routes instead of adding a
third serialization implementation.
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
        )
        db_session.add(element)
        db_session.flush()

        relationship = ArchiMateRelationship(
            type="realization",
            source_id=element.id,
            target_id=element.id,
            organization_id=org.id,
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

        exported_relationships = {r["id"]: r for r in data["relationships"]}
        assert relationship.id in exported_relationships, (
            "seeded relationship missing from JSON export"
        )
        exported_relationship = exported_relationships[relationship.id]
        assert exported_relationship["type"] == "realization"
        assert exported_relationship["source_id"] == element.id
        assert exported_relationship["target_id"] == element.id
    finally:
        if os.path.exists(file_path):
            os.unlink(file_path)
