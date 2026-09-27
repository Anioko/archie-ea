"""GET /api/architecture-assistant/export-arb/<id> renders LLM-drafted ARB
content unescaped -- walked through as the owning architect would actually
use it (open the printable ARB submission document).

Found 11 Sep 2026 while triaging the debt the raw-html-escaping gate
surfaced. Worse than the digest-email bug fixed earlier the same day:
arb_draft's fields are LLM-generated (an AI-drafted ARB submission stored on
Solution.arb_snapshot), which makes this reachable via prompt injection
upstream of this route, not just a directly-attacker-controlled field. The
route returns `Response(html, mimetype="text/html")` built by hand with zero
escaping on arb_draft's text fields, solution.name/business_domain/
governance_status, and any linked ArchiMate element or roadmap plateau name.

Fixed with escape() (xml.sax.saxutils.escape, already imported in this file
for the OEF XML export helpers) at every interpolation site.
"""

import re
import uuid

import pytest
from playwright.sync_api import expect

from tests.smoke.conftest import PASSWORD

PAGE_TIMEOUT = 30000


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").click()
    page.wait_for_url(lambda u: "/account/login" not in u, timeout=PAGE_TIMEOUT)


@pytest.fixture()
def malicious_arb_solution(seeded):
    from app import create_app, db
    from app.models.solution_models import Solution

    app = create_app("testing")
    marker = "smoke-arb-xss-%s" % uuid.uuid4().hex[:8]
    payload = '<img src=x onerror=alert(1)> %s' % marker
    with app.app_context():
        org_id = seeded["ids"]["org"]
        user_id = seeded["ids"]["solution_architect_user"]
        solution = Solution(
            name="ARB Escaping Test %s" % marker, organization_id=org_id,
            created_by_id=user_id, governance_status="draft",
            arb_snapshot={
                "arb_draft": {
                    "business_justification": payload,
                    "technical_assessment": payload,
                    "risk_analysis": payload,
                },
                "options": [], "selected_option_id": None, "roadmap": {},
            },
        )
        db.session.add(solution)
        db.session.commit()
        result = {"id": solution.id, "marker": marker}
        db.session.remove()
        return result


@pytest.mark.smoke
def test_arb_export_escapes_llm_drafted_content(browser, live_server, seeded, malicious_arb_solution):
    architect_email = seeded["emails"]["solution_architect"]
    ctx = browser.new_context(ignore_https_errors=True)
    page = ctx.new_page()
    alerts = []
    page.on("dialog", lambda d: (alerts.append(d.message), d.dismiss()))
    _login(page, live_server, architect_email)

    page.goto(
        live_server + "/api/architecture-assistant/export-arb/%d" % malicious_arb_solution["id"],
        wait_until="load", timeout=PAGE_TIMEOUT,
    )
    page.wait_for_timeout(500)

    assert alerts == [], "the LLM-drafted ARB content executed as script: %s" % alerts

    body_text = page.locator("body").inner_text()
    assert malicious_arb_solution["marker"] in body_text, "ARB content should still be shown (as inert text)"
    expect(page.locator("img[src='x']")).to_have_count(0)
