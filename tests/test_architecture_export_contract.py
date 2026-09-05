"""Exports must contain real model data, not just return a redirect or filename."""
import csv
import io
import json
import pytest
from pathlib import Path
from types import SimpleNamespace


@pytest.mark.parametrize("has_timestamp", [False, True])
def test_csv_export_serializes_canonical_archimate_type(monkeypatch, has_timestamp):
    from app.modules.architecture.services import architecture_import_export_service as module
    assert "type" in module.ArchitectureElement.__table__.columns
    assert hasattr(module.ArchitectureElement, "type")
    # Canonical-field row double: this tests serialization, not DB isolation.
    element = SimpleNamespace(id=71, name="QA export application",
                              type="application_component", layer="application",
                              description=None)
    if has_timestamp:
        from datetime import datetime
        element.created_at = datetime(2026, 9, 5, 12, 0)
    monkeypatch.setattr(module, "ArchitectureElement", SimpleNamespace(
        query=SimpleNamespace(all=lambda: [element])))
    path, filename = module.ArchitectureImportExportService.export_to_csv()
    try:
        with Path(path).open(encoding="utf-8", newline="") as source:
            rows = list(csv.DictReader(source))
        assert filename.endswith(".csv")
        assert len(rows) == 1
        assert rows[0]["id"] == "71"
        assert rows[0]["name"] == "QA export application"
        assert rows[0]["element_type"] == "application_component"
        assert rows[0]["created_at"] == ("2026-09-05T12:00:00" if has_timestamp else "")
    finally:
        Path(path).unlink(missing_ok=True)


@pytest.mark.parametrize("format_type", ["csv", "json"])
@pytest.mark.parametrize("types,valid", [
    ({"element_type": "application_component"}, True),
    ({"type": "application_component"}, True),
    ({"archimate_type": "application_component"}, True),
    ({"element_type": "application_component", "archimate_type": "application_component"}, True),
    ({"element_type": "business_actor", "archimate_type": "application_component"}, False),
    ({"type": "business_actor", "element_type": "application_component"}, False),
    ({}, False),
    ({"element_type": "   "}, False),
])
def test_import_type_contract(monkeypatch, format_type, types, valid):
    from app.modules.architecture.services import architecture_import_export_service as module

    added = []
    class Model:
        name = "name"
        query = SimpleNamespace(with_entities=lambda *args: SimpleNamespace(all=lambda: []))

        def __init__(self, *, name, type, layer, description):
            self.name, self.type = name, type

    monkeypatch.setattr(module, "ArchitectureElement", Model)
    monkeypatch.setattr(module, "db", SimpleNamespace(session=SimpleNamespace(
        add=added.append, commit=lambda: None)))
    row = {"name": "QA import", **types}
    if format_type == "json":
        source = io.StringIO(json.dumps({"elements": [row]}))
    else:
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
        source = SimpleNamespace(stream=io.BytesIO(text.getvalue().encode()))
    result = module.ArchitectureImportExportService.import_data(source, format_type)
    assert result["imported"] == int(valid)
    assert len(added) == int(valid)
    assert bool(result["errors"]) is not valid
    if valid:
        assert added[0].type == "application_component"
