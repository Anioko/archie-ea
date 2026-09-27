"""/admin/export-portfolio-pdf renders solution names unescaped -- walked
through as a platform admin would actually use it (print/save as PDF).

Found 11 Sep 2026 while triaging the debt the raw-html-escaping gate
surfaced (see app/_bootstrap/_digest_emails.py's own incident the same
day): this route builds an HTML page by hand (`"".join(html_parts)`
returned directly from the Flask view, not a Jinja template), and
interpolated solution names -- architect-authored freeform text -- into
table cells with zero escaping. Any solution named with an HTML/script
payload would have it execute for every admin who opens this report.

Fixed with html.escape() at every interpolation site in both the v1 and
v2 admin_routes.py copies (v2 is live by default per the module-layout
guardrail flags). This test proves it the way the earlier count-only
digest tests failed to: create a solution with a malicious name, hit
the real route as a real platform admin, and confirm the browser never
executes the payload.
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
def malicious_solution(seeded):
    from app import create_app, db
    from app.models.solution_models import Solution

    app = create_app("testing")
    marker = "smoke-xss-%s" % uuid.uuid4().hex[:8]
    malicious_name = '<img src=x onerror=alert(1)> %s' % marker
    with app.app_context():
        org_id = seeded["ids"]["org"]
        user_id = seeded["ids"]["solution_architect_user"]
        solution = Solution(
            name=malicious_name, organization_id=org_id,
            created_by_id=user_id, governance_status="draft",
        )
        db.session.add(solution)
        db.session.commit()
        result = {"id": solution.id, "marker": marker}
        db.session.remove()
        return result


@pytest.mark.smoke
def test_portfolio_pdf_export_escapes_malicious_solution_name(browser, live_server, seeded, malicious_solution):
    admin_email = seeded["emails"]["platform_admin"]
    ctx = browser.new_context(ignore_https_errors=True)
    page = ctx.new_page()
    alerts = []
    page.on("dialog", lambda d: (alerts.append(d.message), d.dismiss()))
    _login(page, live_server, admin_email)

    page.goto(live_server + "/admin/export-portfolio-pdf", wait_until="load", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(500)

    assert alerts == [], "the malicious solution name executed as script: %s" % alerts

    body_text = page.locator("body").inner_text()
    assert malicious_solution["marker"] in body_text, "the solution should still be listed (as inert text)"
    # The payload must render as literal text, not a live <img> element.
    expect(page.locator("img[src='x']")).to_have_count(0)
