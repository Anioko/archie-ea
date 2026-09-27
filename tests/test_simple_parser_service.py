"""Regression tests for the restored no-LLM SimpleParserService.

The module backing the "Simple Parsing" upload toggle had been dropped from this
extract, so `document_routes.upload_document` raised ImportError (a 500) whenever a
user flipped the toggle. These tests pin the two things that matter: the contract
the upload pipeline consumes ({elements, relationships, metadata}), and the
no-fabrication invariant — a row with no name never becomes a placeholder element.
"""

import csv

import pytest

from app.services.archimate.simple_parser_service import SimpleParserService


def _write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return str(path)


def test_maps_named_rows_and_skips_nameless(tmp_path):
    csv_path = _write_csv(tmp_path / "apps.csv", [
        ["Application Name", "Type", "Description", "Vendor"],
        ["Payroll System", "ApplicationComponent", "Runs payroll", "SAP"],
        ["CRM", "", "Customer records", "Salesforce"],
        ["", "", "orphan row with no name", ""],      # no name → must be skipped
        ["Data Lake", "DataObject", "Central store", ""],
    ])
    out = SimpleParserService().parse_document(csv_path, analysis_context="application")

    # contract the upload pipeline relies on
    assert set(out) == {"elements", "relationships", "metadata"}
    assert out["relationships"] == []                      # never inferred without an LLM
    assert out["metadata"]["mapped_count"] == 3
    assert out["metadata"]["skipped_count"] == 1           # the nameless row
    assert out["metadata"]["row_count"] == 4

    names = {e["name"] for e in out["elements"]}
    assert names == {"Payroll System", "CRM", "Data Lake"}


def test_no_fabrication_invariants(tmp_path):
    csv_path = _write_csv(tmp_path / "apps.csv", [
        ["Name", "Type", "Owner"],
        ["Portal", "DataObject", "Team A"],
        ["Gateway", "", "Team B"],
    ])
    elements = SimpleParserService().parse_document(csv_path)["elements"]
    by_name = {e["name"]: e for e in elements}

    # explicit type honoured; absent type defaults to ApplicationComponent
    assert by_name["Portal"]["type"] == "DataObject"
    assert by_name["Gateway"]["type"] == "ApplicationComponent"
    # extra columns preserved verbatim, name column not duplicated into them
    assert by_name["Portal"]["properties"] == {"Owner": "Team A"}
    assert "Name" not in by_name["Portal"]["properties"]


def test_non_spreadsheet_degrades_without_raising(tmp_path):
    txt = tmp_path / "notes.pdf"
    txt.write_text("free text, not a spreadsheet", encoding="utf-8")
    out = SimpleParserService().parse_document(str(txt))
    # honest empty result with a note, NOT an exception and NOT invented elements
    assert out["elements"] == []
    assert out["metadata"]["mapped_count"] == 0
    assert "error" in out["metadata"] or "note" in out["metadata"]
