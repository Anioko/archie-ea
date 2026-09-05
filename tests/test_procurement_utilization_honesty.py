"""Real summary function and template; shell/URL boundaries only are doubled."""
import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]


def summary(rows):
    source = ROOT / "app/modules/procurement/routes.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_compliance_summary")
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["_compliance_summary"]([
        SimpleNamespace(quantity_entitled=e, quantity_deployed=d, compliance_status="compliant") for e, d in rows
    ])


@pytest.mark.parametrize("rows,expected", [([], None), ([(0, 5)], None), ([(None, None)], None), ([(10, 0)], 0.0), ([(10, 15)], 150.0)])
def test_ratio_requires_positive_entitlement(rows, expected):
    assert summary(rows)["utilization"] == expected


def render_summary(rows):
    env = Environment(loader=ChoiceLoader([
        DictLoader({"layouts/admin_base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader([ROOT / "app/templates", ROOT / "app/modules/procurement/templates"]),
    ]), autoescape=True)
    env.globals["url_for"] = lambda endpoint, **kwargs: "/test/" + endpoint
    return env.get_template("procurement/compliance_dashboard.html").render(summary=summary(rows), licenses=[])


@pytest.mark.parametrize("rows,display", [([], "—"), ([(10, 0)], "0%")])
def test_rendered_unknown_is_distinct_from_measured_zero(rows, display):
    html = render_summary(rows)
    metric = re.search(r'Overall Utilization</div>\s*<div[^>]*>([^<]+)</div>', html)
    assert metric and metric.group(1).strip() == display
    if display == "—":
        assert "Utilization unavailable" in html
        assert 'style="width: 0%' not in html


@pytest.mark.parametrize("rows,display", [([], "—"), ([(10, 0)], "0%")])
def test_chromium_displays_unknown_and_real_zero_differently(rows, display):
    """Actual Chromium rendering of the template; not a full-app/auth/DB test."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(render_summary(rows))
            card = page.get_by_text("Overall Utilization", exact=True).locator("..")
            expect(card.get_by_text(display, exact=True)).to_be_visible()
            if display == "—":
                expect(page.get_by_text("Utilization unavailable", exact=False)).to_be_visible()
        finally:
            browser.close()
