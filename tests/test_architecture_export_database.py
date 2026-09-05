"""Real mapped-model export, tenant isolation and element round trips.

Relationship round-trip support remains a separate outstanding contract.
"""
import csv
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("format_type", ["csv", "json"])
def test_export_and_import_real_tenant_elements(db_session, make_org, tenant_ctx, format_type):
    from app.models.archimate_core import ArchiMateElement
    from app.modules.architecture.services.architecture_import_export_service import ArchitectureImportExportService

    source_org, other_org, target_org = make_org("export-source"), make_org("export-other"), make_org("export-target")
    for org, name in [(source_org, "Visible export application"), (other_org, "Private other application")]:
        with tenant_ctx(org.id):
            db_session.add(ArchiMateElement(name=name, type="ApplicationComponent", layer="application"))
            db_session.flush()
    with tenant_ctx(source_org.id):
        path, _ = ArchitectureImportExportService.export_data(format_type)
    try:
        payload = Path(path).read_text(encoding="utf-8")
    finally:
        Path(path).unlink(missing_ok=True)
    if format_type == "csv":
        rows = list(csv.DictReader(io.StringIO(payload)))
        assert [(row["name"], row["element_type"]) for row in rows] == [("Visible export application", "ApplicationComponent")]
        upload = SimpleNamespace(stream=io.BytesIO(payload.encode("utf-8")))
    else:
        rows = json.loads(payload)["elements"]
        assert [(row["name"], row["type"]) for row in rows] == [("Visible export application", "ApplicationComponent")]
        upload = io.StringIO(payload)
    with tenant_ctx(target_org.id):
        result = ArchitectureImportExportService.import_data(upload, format_type)
        assert result == {"imported": 1, "skipped": 0, "errors": []}
        imported = ArchiMateElement.query.one()
        assert imported.name == "Visible export application"
        assert imported.type == "ApplicationComponent"
        assert imported.organization_id == target_org.id
