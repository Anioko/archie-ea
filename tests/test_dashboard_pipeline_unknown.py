"""Execute the real aggregation/card with controlled database result rows.

The database boundary is replaced; these are not full-app/tenant isolation tests.
"""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def pipeline(rows, monkeypatch):
    import app.models.solution_models as models

    monkeypatch.setattr(models, "Solution", SimpleNamespace(adm_phase="phase", id="id"))

    class Query:
        def group_by(self, *args):
            return self

        def all(self):
            if isinstance(rows, Exception):
                raise rows
            return rows

    tree = ast.parse((ROOT / "app/modules/dashboard/v2/routes/dashboard_views.py").read_text(encoding="utf-8"))
    body = next(node.body for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "overview")
    start = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "solution_pipeline" for t in node.targets))
    namespace = {
        "db": SimpleNamespace(session=SimpleNamespace(query=lambda *a: Query(), rollback=lambda: None), func=SimpleNamespace(count=lambda x: x)),
        "logger": logging.getLogger(__name__),
    }
    exec(compile(ast.Module(body=body[start:start + 2], type_ignores=[]), "pipeline-production", "exec"), namespace)
    return namespace["solution_pipeline"]


def render_card(rows):
    source = (ROOT / "app/templates/dashboards/overview.html").read_text(encoding="utf-8")
    fragment = source.split("{# solution_pipeline", 1)[1].split("{% endcall %}", 1)[0]
    env = Environment(loader=FileSystemLoader(ROOT / "app/templates"), autoescape=True)
    env.globals["url_for"] = lambda *a: "/solutions/"
    return env.from_string("{% from 'macros/page_shell.html' import empty_state %}{# solution_pipeline" + fragment).render(solution_pipeline=rows, current_user=SimpleNamespace(enterprise_role="platform_admin"))


@pytest.mark.parametrize("rows", [[(None, 4)], [("", 4)], [("obsolete", 4)]])
def test_existing_unclassified_solutions_are_not_an_empty_pipeline(rows, monkeypatch):
    result = pipeline(rows, monkeypatch)
    assert sum(item["count"] for item in result) == 4
    html = render_card(result)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html)
            assert "4 solutions" in page.inner_text("body")
            assert "No solutions yet" not in page.inner_text("body")
            assert "phase A" not in page.inner_text("body")
            assert page.get_by_role("link", name="Open the pipeline").count() == 1
        finally:
            browser.close()


def test_mixed_phase_counts_preserve_unknown_and_known(monkeypatch):
    result = pipeline([("A", 2), (None, 3), ("", 1), ("C", 1)], monkeypatch)
    assert sum(item["count"] for item in result) == 7
    assert next(item["count"] for item in result if item["phase"] == "A") == 2


def test_normalized_phase_groups_sum_collisions_without_losing_solutions(monkeypatch):
    result = pipeline([("C", 2), (" c ", 3), (None, 1), ("", 1), ("obsolete", 1)], monkeypatch)
    assert sum(item["count"] for item in result) == 8
    assert next(item["count"] for item in result if item["phase"] == "C") == 5
    assert next(item["count"] for item in result if item["phase"] is None) == 3


def test_query_failure_is_unavailable_not_no_solutions(monkeypatch):
    result = pipeline(RuntimeError("database unavailable"), monkeypatch)
    html = render_card(result)
    assert "Pipeline unavailable" in html
    assert "No solutions yet" not in html


def test_genuine_empty_pipeline_remains_empty(monkeypatch):
    assert "No solutions yet" in render_card(pipeline([], monkeypatch))
