"""DOGFOOD-003 / DOGFOOD-004 — OEF relationship import + custom_properties.

Exercises ArchiMateImportService against the synthetic fixture
tests/fixtures/oef/archiet_shaped.xml (12 valid relationships, 1 invalid
composition, and a Constraint element carrying status/source/layer
properties shaped like the customer's M-CON-10G-FREE-PILOTS element).
"""

import os

import pytest

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "oef", "archiet_shaped.xml"
)


@pytest.fixture
def fixture_xml():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture
def org_ctx(app, db_session, make_org, tenant_ctx):
    org = make_org("dogfood-import")
    with tenant_ctx(org.id):
        yield org


def test_parse_oef_xml_reads_properties_and_relationships(fixture_xml):
    from app.services.archimate_import_service import ArchiMateImportService

    parsed = ArchiMateImportService().parse_oef_xml(fixture_xml)

    assert len(parsed["elements"]) == 15
    assert len(parsed["relationships"]) == 13

    con = next(e for e in parsed["elements"] if e["name"] == "M-CON-10G-FREE-PILOTS")
    assert con["type"] == "Constraint"
    assert con["properties"] == {
        "status": "RULED",
        "source": "founder ruling 2026-07-19 -- strategy/10G-ASSESSMENT-OFFER.md",
        "layer": "Motivation",
    }

    # Elements with no <properties> block parse to an empty dict, never None
    # or a fabricated value.
    other = next(e for e in parsed["elements"] if e["name"] == "Sales Team")
    assert other["properties"] == {}


def test_execute_import_writes_relationships_and_properties(app, org_ctx, fixture_xml):
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.services.archimate_import_service import ArchiMateImportService

    service = ArchiMateImportService()
    parsed = service.parse_oef_xml(fixture_xml)
    result = service.execute_import(parsed, strategy="skip_duplicates")

    assert result["created"] == 15
    assert result["relationships_created"] == 12
    assert result["relationships_skipped"] == 0
    assert len(result["relationships_failed"]) == 1

    failed = result["relationships_failed"][0]
    assert failed["identifier"] == "id-rel-13"
    assert failed["type"] == "composition"
    assert "reason" in failed
    assert "Traceback" not in failed["reason"]
    assert "Exception" not in failed["reason"]

    assert ArchiMateRelationship.query.count() == 12

    con = ArchiMateElement.query.filter_by(name="M-CON-10G-FREE-PILOTS").first()
    assert con is not None
    assert con.custom_properties["status"] == "RULED"
    assert con.custom_properties["source"] == (
        "founder ruling 2026-07-19 -- strategy/10G-ASSESSMENT-OFFER.md"
    )
    assert con.custom_properties["layer"] == "Motivation"
    # Provenance key present and namespaced so it never collides with a
    # customer property genuinely called "imported_at".
    assert "archie:imported_at" in con.custom_properties


def test_preview_and_execute_relationship_counts_agree(app, org_ctx, fixture_xml):
    from app.services.archimate_import_service import ArchiMateImportService

    service = ArchiMateImportService()
    parsed = service.parse_oef_xml(fixture_xml)

    preview = service.preview_import(parsed)
    assert preview["summary"]["relationships_valid"] == 12
    assert preview["summary"]["relationships_invalid"] == 1

    result = service.execute_import(parsed, strategy="skip_duplicates")
    assert result["relationships_created"] + result["relationships_skipped"] == (
        preview["summary"]["relationships_valid"]
    )
    assert len(result["relationships_failed"]) == preview["summary"]["relationships_invalid"]


def test_reimport_after_execute_reports_every_element_as_exists(app, org_ctx, fixture_xml):
    """Round-trip guard: re-running preview against the same XML after a
    successful execute must classify every element as 'exists', never
    'conflict' or 'new' — the acceptance criterion's shape (168 exists / 0
    new / 0 conflict), reproduced against the fixture's 15 elements."""
    from app.services.archimate_import_service import ArchiMateImportService

    service = ArchiMateImportService()
    parsed = service.parse_oef_xml(fixture_xml)
    service.execute_import(parsed, strategy="skip_duplicates")

    reparsed = service.parse_oef_xml(fixture_xml)
    preview_again = service.preview_import(reparsed)

    assert preview_again["summary"]["new"] == 0
    assert preview_again["summary"]["conflict"] == 0


def test_element_flush_failure_discards_whole_batch(app, org_ctx, monkeypatch):
    """D1 (round 4) — reproduces refuter's exact trace: elements [A, BAD, C]
    where BAD raises on flush. Before this fix, A's flush()/created-increment/
    id_map entry survived the rollback() triggered by BAD's failure, so the
    response reported a non-zero, confidently wrong created count (or a
    phantom-FK secondary failure) even though A no longer exists in the DB
    after rollback. The whole batch must be discarded and reported as such.
    """
    from app.extensions import db
    from app.models.archimate_core import ArchiMateElement
    from app.services.archimate_import_service import ArchiMateImportService

    parsed = {
        "elements": [
            {"name": "A", "type": "Application Component", "identifier": "id-a"},
            {"name": "BAD", "type": "Application Component", "identifier": "id-bad"},
            {"name": "C", "type": "Application Component", "identifier": "id-c"},
        ],
        "relationships": [],
        "errors": [],
    }

    real_flush = db.session.flush
    call_count = {"n": 0}

    def flaky_flush(*args, **kwargs):
        call_count["n"] += 1
        # First call is A's flush (succeeds); second call is BAD's — raise.
        if call_count["n"] == 2:
            raise RuntimeError("simulated DB constraint failure on BAD")
        return real_flush(*args, **kwargs)

    monkeypatch.setattr(db.session, "flush", flaky_flush)

    service = ArchiMateImportService()
    result = service.execute_import(parsed, strategy="skip_duplicates")

    assert result["created"] == 0
    assert result["updated"] == 0
    assert result["skipped"] == 0
    assert result["relationships_created"] == 0
    assert result["relationships_failed"] == []
    assert any("discarded" in e.lower() for e in result["errors"])

    monkeypatch.setattr(db.session, "flush", real_flush)
    assert ArchiMateElement.query.filter_by(name="A").first() is None
    assert ArchiMateElement.query.filter_by(name="BAD").first() is None
    assert ArchiMateElement.query.filter_by(name="C").first() is None


def test_export_then_reimport_preserves_custom_properties(app, org_ctx, fixture_xml):
    """DOGFOOD-004 round-trip: whole-model OEF export writes back
    custom_properties (minus the archie: namespace), and re-importing that
    export reports the element as 'exists' with the same property values."""
    from app.models.archimate_core import ArchiMateElement
    from app.services.archimate_import_service import ArchiMateImportService
    from app.services.archimate_oef_service import ArchiMateOEFService

    service = ArchiMateImportService()
    parsed = service.parse_oef_xml(fixture_xml)
    service.execute_import(parsed, strategy="skip_duplicates")

    exported_xml = ArchiMateOEFService().export_model()
    reparsed = service.parse_oef_xml(exported_xml)

    con = next(
        e for e in reparsed["elements"] if e["name"] == "M-CON-10G-FREE-PILOTS"
    )
    assert con["properties"]["status"] == "RULED"
    assert con["properties"]["source"] == (
        "founder ruling 2026-07-19 -- strategy/10G-ASSESSMENT-OFFER.md"
    )
    assert con["properties"]["layer"] == "Motivation"
    # The provenance key is never written back by export.
    assert "archie:imported_at" not in con["properties"]

    preview = service.preview_import(reparsed)
    # M5 (refuter): only asserting conflict==0 leaves "new"/"exists" free to
    # be anything, including a wrongly-classified full re-creation. Pin the
    # actual round-trip shape.
    assert preview["summary"]["conflict"] == 0
    assert preview["summary"]["new"] == 0
    assert preview["summary"]["exists"] == 15

    # M5: actually execute the reimport, not just preview it, and confirm the
    # relationship count survives the export/reimport round-trip too. Export
    # goes through ArchimateValidityService (a validity authority distinct
    # from RelationshipValidator, which import uses) and can reverse or drop
    # an edge on export -- exercising execute here is what would catch that,
    # not a preview-only assertion.
    from app.models.archimate_core import ArchiMateRelationship

    relationships_before = ArchiMateRelationship.query.count()
    result_reimport = service.execute_import(reparsed, strategy="skip_duplicates")
    assert result_reimport["created"] == 0
    assert result_reimport["skipped"] == 15
    # No new relationships should be created (all already exist from the
    # original import) and none of the 12 valid relationships should have
    # been dropped or reversed into a failure by the export path.
    assert result_reimport["relationships_created"] == 0
    assert ArchiMateRelationship.query.count() == relationships_before
