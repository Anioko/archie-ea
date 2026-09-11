"""VisualGenerationService interpolated AI-chat-reachable freeform text
(element name/type, heatmap title/item labels) into hand-built Mermaid and
HTML strings with zero or insufficient escaping. Found 11 Sep 2026 while
triaging the raw-html-escaping gate.

Mermaid renders HTML inside node labels by default (this file already uses
<br/>/<small> tags deliberately), so an unescaped element name is a real
client-side injection vector wherever the diagram is rendered. The heat map
HTML fragment is even more direct: it's raw HTML a browser renders.
"""

from app.services.ai_chat_extensions.visual_generation_service import (
    VisualGenerationService,
)

MALICIOUS = '<img src=x onerror=alert(1)>'


def test_mermaid_diagram_escapes_element_name():
    svc = VisualGenerationService()
    elements = [{"id": 1, "name": MALICIOUS, "type": MALICIOUS, "layer": "Business"}]
    mermaid = svc._elements_to_mermaid(elements, [], "Test Diagram")

    assert MALICIOUS not in mermaid
    assert "&lt;img src=x onerror=alert(1)&gt;" in mermaid


def test_heatmap_html_escapes_labels():
    svc = VisualGenerationService()
    data = [{"color": "#22c55e", "value": MALICIOUS, "name": MALICIOUS, "level": MALICIOUS}]
    html = svc._generate_heatmap_html(data, MALICIOUS, MALICIOUS)

    assert MALICIOUS not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    # color is a fixed hex value and must pass through untouched.
    assert "#22c55e" in html
