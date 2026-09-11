"""POST /ai-chat/architect/export-brief built an HTML document from every
solution field (name, description, scope, domain, type, business value,
status) with zero escaping. Found 11 Sep 2026 while triaging the
raw-html-escaping gate: only the <title> line was originally flagged by the
static checker, but every field in both the ARB and full-brief branches had
the identical bug -- an architect naming a solution with an HTML/script
payload would have it execute for anyone who exported this brief.
"""
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
def malicious_solution(seeded):
    from app import create_app, db
    from app.models.solution_models import Solution

    app = create_app("testing")
    marker = "smoke-export-brief-xss-%s" % uuid.uuid4().hex[:8]
    payload = '<img src=x onerror=alert(1)> %s' % marker
    # solution_type is VARCHAR(50) -- the marker-bearing payload overflows it,
    # so it gets the bare payload (29 chars) with no marker suffix; the
    # marker assertion is still covered by name/description/business_domain.
    short_payload = '<img src=x onerror=alert(1)>'
    with app.app_context():
        org_id = seeded["ids"]["org"]
        user_id = seeded["ids"]["solution_architect_user"]
        solution = Solution(
            name=payload, organization_id=org_id, created_by_id=user_id,
            governance_status="draft", description=payload,
            business_domain=payload, solution_type=short_payload,
        )
        db.session.add(solution)
        db.session.commit()
        result = {"id": solution.id, "marker": marker}
        db.session.remove()
        return result


@pytest.mark.smoke
def test_export_brief_escapes_malicious_solution_fields(browser, live_server, seeded, malicious_solution):
    architect_email = seeded["emails"]["solution_architect"]
    ctx = browser.new_context(ignore_https_errors=True)
    page = ctx.new_page()
    alerts = []
    page.on("dialog", lambda d: (alerts.append(d.message), d.dismiss()))
    _login(page, live_server, architect_email)

    response = page.request.post(
        live_server + "/ai-chat/architect/export-brief",
        data={"solution_id": malicious_solution["id"], "format": "pdf"},
    )
    assert response.status == 200
    html = response.text()

    assert '<img src=x onerror=alert(1)>' not in html
    assert malicious_solution["marker"] in html, "the solution's own content should still appear (as inert text)"
    assert "&lt;img src=x onerror=alert(1)&gt;" in html

    # Load the returned HTML directly in the browser to prove it's inert,
    # not just string-match the escaped entities.
    page.set_content(html)
    page.wait_for_timeout(300)
    assert alerts == [], "the malicious solution field executed as script: %s" % alerts
