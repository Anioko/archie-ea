"""Real Alpine initialization must load a phase gate without cached ancestors."""

from pathlib import Path

from flask import Flask, render_template
from playwright.sync_api import expect, sync_playwright
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("nested", [False, True])
def test_phase_gate_cold_initial_load_and_refresh(nested):
    app = Flask(__name__, template_folder=str(ROOT / "app/templates"))
    app.add_url_rule("/solutions/<int:solution_id>", endpoint="solution_design.view_solution", view_func=lambda solution_id: "")
    with app.test_request_context():
        fragment = render_template("solutions/partials/_phase_gate_checklist.html",
                                   solution={"id": 32}, csrf_token=lambda: "cold-fixture-csrf")
    # A realistic parent reproduces the overshooting getter. The standalone
    # case ensures explicit configuration does not depend on Alpine internals.
    parent = '<main x-data="{apiBase: \'/solutions/32\', csrfToken: \'cold-fixture-csrf\'}"><section><div>' if nested else '<main>'
    close = '</div></section></main>' if nested else '</main>'
    alpine = (ROOT / "app/static/vendor/alpine.min.js").read_text(encoding="utf-8")
    html = ('<html><head><style>[x-cloak]{display:none!important}</style></head><body>'
            '<script>window.Platform={fetch:async function(url){const response=await fetch(url);'
            'if(!response.ok)throw new Error("HTTP "+response.status);return response.json();}};</script>'
            + parent + fragment + close + '<script>' + alpine + '</script></body></html>')
    calls = []
    def route_request(route):
        if route.request.url.endswith("/phase-gate"):
            calls.append(route.request.url)
            route.fulfill(json={"success": True, "can_advance": False, "phase": "C",
                                "phase_label": "Information Systems", "next_phase": "D",
                                "critical_failures": [], "warnings": [], "passed": [],
                                "summary": {"total": len(calls) + 1, "passed_count": 1}})
        else:
            route.fulfill(content_type="text/html", body=html)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.route("https://phase-gate.test/**", route_request)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto("https://phase-gate.test/solutions/32")
            panel = page.locator('[x-data="phaseGateChecklist()"]')
            # Do not click Refresh before proving initial request and content.
            expect(panel.locator('[x-text="gate.summary.total"]')).to_have_text("2")
            expect(panel.locator('[x-text="gate.phase"]')).to_have_text("C")
            expect(panel.locator('[x-show="error"]')).to_be_hidden()
            assert calls == ["https://phase-gate.test/solutions/32/phase-gate"]
            assert panel.evaluate("el => Alpine.$data(el).csrfToken") == "cold-fixture-csrf"
            panel.get_by_role("button", name="Refresh checklist", exact=True).click()
            expect(panel.locator('[x-text="gate.summary.total"]')).to_have_text("3")
            expect(panel.locator('[x-show="error"]')).to_be_hidden()
            assert calls == ["https://phase-gate.test/solutions/32/phase-gate"] * 2
            assert not errors
        finally:
            browser.close()
