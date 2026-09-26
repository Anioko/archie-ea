"""Buying a plan: the pricing page's buy button and the administrator's billing page.

The smoke server carries no payment-provider keys, so this is the journey a
visitor and an administrator take on an installation where online payment is
not set up: every buy control must lead somewhere real and say plainly that
payment is not available, never fire nothing or pretend to have worked. The
paths with keys present (checkout, change, cancel, signed events) are driven
against recorded provider responses in tests/test_billing_plans_and_checkout.py.
"""
import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def test_pricing_buy_button_leads_a_visitor_to_that_plans_checkout(browser, live_server, seeded):
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(live_server + "/pricing", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        buy = page.get_by_test_id("buy-startup")
        expect(buy).to_be_visible(timeout=PAGE_TIMEOUT)
        expect(page.get_by_test_id("buy-enterprise")).to_have_attribute("href", "/contact")

        buy.click()
        # Not signed in yet: the button asks for a sign-in and keeps the plan.
        page.wait_for_url(lambda url: "/account/login" in url, timeout=PAGE_TIMEOUT)
        page.fill("#email", seeded["emails"]["platform_admin"])
        page.fill("#password", PASSWORD)
        page.locator("#submit").click()
        page.wait_for_url(lambda url: "/admin/billing" in url and "plan=startup" in url,
                          timeout=PAGE_TIMEOUT)

        checkout = page.locator("#checkout")
        expect(checkout.get_by_role("heading", name="Buy Startup")).to_be_visible(timeout=PAGE_TIMEOUT)
        expect(page.get_by_test_id("plan-card-startup")).to_be_visible()
        # No keys on this server: say so, and offer no payment button that cannot work.
        expect(page.get_by_test_id("checkout-unavailable")).to_contain_text(
            "Online payment is not set up on this installation")
        expect(page.get_by_test_id("checkout-submit")).to_have_count(0)
    finally:
        context.close()


def test_administrator_sees_plan_limits_and_can_choose_a_plan(browser, live_server, seeded):
    from .test_archetype_journeys import _login

    context = browser.new_context()
    page = context.new_page()
    try:
        _login(page, live_server, seeded["emails"]["platform_admin"])
        response = page.goto(live_server + "/admin/billing/", wait_until="domcontentloaded",
                             timeout=PAGE_TIMEOUT)
        assert response.status == 200

        expect(page.get_by_role("heading", name="Billing & plan", level=1)).to_be_visible(timeout=PAGE_TIMEOUT)
        expect(page.get_by_test_id("billing-not-configured")).to_be_visible()
        plan_name = page.get_by_test_id("billing-current-plan").inner_text().strip()
        assert plan_name in {"Community", "Startup", "Team", "Enterprise"}
        # The people figure is "<used> of <limit>" from the plan, never blank.
        people = page.get_by_test_id("billing-people-limit").inner_text().strip()
        assert " of " in people, people

        page.get_by_test_id("plan-card-team").get_by_role("link", name="Choose Team").click()
        page.wait_for_url(lambda url: "plan=team" in url, timeout=PAGE_TIMEOUT)
        expect(page.locator("#checkout").get_by_role("heading", name="Buy Team")).to_be_visible(
            timeout=PAGE_TIMEOUT)
        expect(page.get_by_test_id("checkout-unavailable")).to_be_visible()

        # The state survives a reload: the chosen plan is in the address.
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#checkout").get_by_role("heading", name="Buy Team")).to_be_visible(
            timeout=PAGE_TIMEOUT)

        # Invoices and billing details say why they are empty instead of showing zeros.
        expect(page.get_by_text("Invoices are not available")).to_be_visible()
    finally:
        context.close()
