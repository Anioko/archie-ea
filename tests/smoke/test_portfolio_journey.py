"""Create -> triage-decide -> persist journey for Portfolio Demand intake.

Wave 3. Prior recon: `app/modules/portfolio/routes/portfolio_write_routes.py`
is the only write surface on the portfolio blueprint (`/portfolio`) -- demand
intake, benefit/assumption POSTs -- and had zero smoke coverage. Demand intake
(`/portfolio/demands/new`, GET/POST) is the primary entity: a plain
server-rendered form (no JS/fetch involved, CSRF via a hidden field), listed at
`/portfolio/demands`. There is no dedicated "edit demand" route, but
`/portfolio/demands/<id>/decide` (POST) mutates the same row (status,
decision_rationale) and is the real second write in this journey -- triage
approving or declining a submitted demand -- so it stands in for "edit" per the
create -> edit -> persist pattern.

`portfolio_manager` is the persona role_access.py grants portfolio access to
(and is a seeded archetype in tests/smoke/conftest.py); `cto` also has read
access per role_access.py comments but portfolio_manager is the module owner.

Follows tests/smoke/test_business_case_journey.py's pattern: real login,
`expect_response` on the actual POST, and a page reload before the final
persistence assertion.
"""

import re
import time

import pytest
from playwright.sync_api import expect

from tests.smoke.conftest import PASSWORD

PAGE_TIMEOUT = 30000


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").click()
    page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)


@pytest.mark.smoke
@pytest.mark.journey
def test_portfolio_demand_create_decide_and_persist(browser, live_server, seeded):
    """A portfolio_manager submits a demand, confirms it lands in the open
    queue, approves it, then confirms the decision survived a reload into the
    Decided section."""
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    page.on("dialog", lambda d: d.accept())
    try:
        _login(page, live_server, seeded["emails"]["portfolio_manager"])

        title = "Smoke Demand %d" % int(time.time() * 1000)
        new_url = live_server + "/portfolio/demands/new"
        demands_url = live_server + "/portfolio/demands"

        # ---- CREATE (POST /portfolio/demands/new) ---------------------------
        page.goto(new_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.fill("#title", title)
        page.fill("#description", "Created by the smoke journey.")
        page.fill("#business_justification", "Proves the intake front door works end to end.")
        with page.expect_response(
            lambda r: "/portfolio/demands/new" in r.url and r.request.method == "POST",
            timeout=PAGE_TIMEOUT,
        ) as created:
            page.locator('button[type="submit"], input[type="submit"]').first.click()
        assert created.value.status < 400, f"create POST failed: {created.value.status}"
        page.wait_for_url(re.compile(r"/portfolio/demands$"), timeout=PAGE_TIMEOUT)

        # ---- Row appears in the open (undecided) queue -----------------------
        expect(page.get_by_text(title, exact=False)).to_be_visible(timeout=PAGE_TIMEOUT)

        # ---- PERSISTENCE (fresh GET) ------------------------------------------
        page.goto(demands_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        expect(page.get_by_text(title, exact=False)).to_be_visible(timeout=PAGE_TIMEOUT)

        # ---- DECIDE (POST /portfolio/demands/<id>/decide) --------------------
        # The queue renders one <form action=".../decide"> per row with three
        # submit buttons (name="status", value="approved"/"deferred"/"declined")
        # rather than a select -- click the Approve button for this row's form.
        card = page.locator("div").filter(has_text=title).filter(
            has=page.locator('form[action*="/decide"]')
        ).last
        approve_button = card.locator('button[name="status"][value="approved"]')
        expect(approve_button).to_be_visible(timeout=PAGE_TIMEOUT)
        with page.expect_response(
            lambda r: "/decide" in r.url and r.request.method == "POST",
            timeout=PAGE_TIMEOUT,
        ) as decided:
            approve_button.click()
        assert decided.value.status < 400, f"decide POST failed: {decided.value.status}"

        # ---- PERSISTENCE (reload -- the decision must survive a fresh GET) --
        page.goto(demands_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        decided_row = page.locator("tr, li, div").filter(has_text=title).first
        expect(decided_row.get_by_text("Approved", exact=False)).to_be_visible(
            timeout=PAGE_TIMEOUT
        )
    finally:
        context.close()
