"""GanttExportService.export_to_svg interpolated task name/status/CSS-class
directly into a hand-built SVG string with zero escaping. Found 11 Sep 2026
while triaging the raw-html-escaping gate.
"""
import xml.etree.ElementTree as ET

from app.modules.solutions_strategic.v2.services.gantt_enhancement_service import (
    GanttExportService,
)

MALICIOUS = '<script>alert(1)</script>'


def test_export_to_svg_escapes_task_name_and_status():
    tasks = [
        {"name": MALICIOUS, "status": MALICIOUS, "is_critical": False},
    ]
    svg = GanttExportService.export_to_svg(tasks, {})

    assert MALICIOUS not in svg
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in svg
    # Well-formed XML around the escaped text.
    ET.fromstring(svg)
