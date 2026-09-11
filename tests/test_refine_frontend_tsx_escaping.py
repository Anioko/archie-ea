"""_generate_refine_frontend interpolated architect-defined field names
directly into generated TSX (React) source via .format(), with no character
restriction. Found 11 Sep 2026 while triaging the raw-html-escaping gate.

A field name containing '"' or '{'/'}' could break out of a JSX attribute or
open an arbitrary JS expression in the generated admin app's own source --
a code-generation-injection bug, not a runtime browser XSS, but the same
underlying failure: untrusted text landing unescaped in a markup/code
context. Fixed with a small _tsx_safe() helper stripping those characters.
"""
from app.modules.codegen.routes._helpers import _generate_refine_frontend

MALICIOUS = '"}} onClick={fetch("evil.com")'


def test_generate_refine_frontend_sanitizes_malicious_field_name():
    """The real injection vector here is a field name breaking out of a
    quoted JSX attribute (via '"') or opening an arbitrary JS expression
    (via '{'/'}') in the generated TSX source -- not arbitrary substrings
    like '<script>', which are inert as plain text inside a JS string
    literal. Assert the actual invariant: no unescaped '"' or brace from
    the field name survives in the generated pages for this resource."""
    uml_snapshot = {
        "class_diagram": {
            "classes": [
                {
                    "name": "Widget",
                    "table_name": "widgets",
                    "attributes": [{"name": MALICIOUS, "type": "str"}],
                }
            ]
        }
    }
    files = _generate_refine_frontend("Test Solution", uml_snapshot)

    widget_files = {p: c for p, c in files.items() if "widget" in p.lower()}
    assert widget_files, "expected generated files for the Widget resource"
    for path, content in widget_files.items():
        assert MALICIOUS not in content, "%s still contains the raw payload" % path
        assert 'onClick={fetch(' not in content, (
            "%s: the malicious field name broke out of its JSX attribute "
            "and injected a JS expression" % path
        )
