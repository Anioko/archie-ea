"""ArchiMateModelGenerator.export_to_archimate_exchange interpolated model/
element/relationship name, description, id and type into a hand-built XML
string with zero escaping. Found 11 Sep 2026 while triaging the
raw-html-escaping gate. These are architect-authored or LLM-generated
fields with no character restriction, so a payload there would inject
malformed/malicious markup into the exported ArchiMate Exchange Format file
-- opened by whatever tool imports it (Archi, other ArchiMate tooling, or
re-parsed by this same platform).
"""

from app.modules.architecture.services.archimate_model_generator import (
    ArchiMateModelGenerator,
)

MALICIOUS = '<script>alert(1)</script> & "quoted"'


def test_export_to_archimate_exchange_escapes_freeform_fields():
    gen = ArchiMateModelGenerator()
    model = {
        "id": "m1", "version": "1.0", "name": MALICIOUS, "description": MALICIOUS,
        "elements": [
            {"id": "e1", "type": "BusinessActor", "name": MALICIOUS, "description": MALICIOUS},
        ],
        "relationships": [
            {"id": "r1", "type": "Serving", "source": "e1", "target": "e1"},
        ],
    }
    xml = gen.export_to_archimate_exchange(model)

    assert "<script>" not in xml
    assert MALICIOUS not in xml
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in xml
    # The XML structure itself must still be well-formed around the escaped text.
    assert '<name xml:lang="en">' in xml
