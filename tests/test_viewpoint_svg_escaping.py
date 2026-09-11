"""ViewpointBuilder.export_to_svg interpolated elem.name and element_type
into a hand-built SVG string with zero escaping. Found 11 Sep 2026 while
triaging the raw-html-escaping gate. elem.name is architect-authored
freeform text with no character restriction, reachable in an SVG a browser
renders directly.
"""
import xml.etree.ElementTree as ET

from app.modules.architecture.services.viewpoint_builder import (
    Viewpoint, ViewpointBuilder, ViewpointElement,
)

MALICIOUS = '<script>alert(1)</script>'


def test_export_to_svg_escapes_element_name():
    builder = ViewpointBuilder()
    elem = ViewpointElement(
        id=1, name=MALICIOUS, element_type=MALICIOUS, description=None,
        layer="business", x=0, y=0, width=150, height=60,
    )
    viewpoint = Viewpoint(
        code="APC", name="Test", purpose="Test", elements=[elem],
        relationships=[], metadata={}, warnings=[],
    )
    svg = builder.export_to_svg(viewpoint)

    assert "<script>" not in svg
    assert MALICIOUS not in svg
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in svg
    # The output must still be well-formed XML around the escaped text.
    ET.fromstring(svg)
