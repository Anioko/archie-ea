"""EnterpriseExportService.export_archimate_xml interpolated elem.layer/
elem.type/rel.type unescaped into hand-built XML. Found 11 Sep 2026 while
triaging the raw-html-escaping gate. These are plain db.String columns with
no enforced fixed-vocabulary constraint, so treated as freeform for safety --
fixed by wrapping in the file's own existing _escape_xml() helper (already
used for elem.name/description/rel.custom_label).

Also fixed incidentally: the pre-existing code referenced
elem.element_type/rel.relationship_type/rel.name, none of which exist on
the actual models (ArchiMateElement.type, ArchiMateRelationship.type,
ArchiMateRelationship.custom_label) -- this export raised AttributeError on
every call before this fix, unrelated to escaping but necessary to fix so
the escaping fix is actually exercisable at all.
"""
import xml.etree.ElementTree as ET

from app.services.enterprise_export import EnterpriseExportService, _escape_xml

MALICIOUS = '<script>alert(1)</script> & "quoted"'
MALICIOUS_SHORT = '<b>&"</b>'  # fits VARCHAR(30) columns (layer/type)


def test_escape_xml_neutralises_special_characters():
    result = _escape_xml(MALICIOUS)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert "&amp;" in result
    assert "&quot;" in result


def test_export_archimate_xml_escapes_element_layer_and_type(app, db_session, make_org, tenant_ctx):
    from app.models.models import ArchiMateElement

    org = make_org("enterprise-export")
    with tenant_ctx(org.id):
        elem = ArchiMateElement(
            name="Test Element", layer=MALICIOUS_SHORT, type=MALICIOUS_SHORT,
            organization_id=org.id,
        )
        db_session.add(elem)
        db_session.flush()

        xml = EnterpriseExportService.export_archimate_xml(element_ids=[elem.id])

        assert MALICIOUS_SHORT not in xml
        assert "&lt;b&gt;&amp;&quot;&lt;/b&gt;" in xml
        # The output must still be well-formed XML around the escaped text.
        ET.fromstring(xml)
