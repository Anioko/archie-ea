"""Outcome tests for controls the wiring-only census cannot validate."""

import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD


pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").dispatch_event("click")
    page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)


def test_solution_blueprint_modal_and_phase_gate_controls_have_observed_outcomes(
    browser, live_server, seeded
):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["solution_architect"])
        page.goto(
            live_server + "/solutions/" + str(seeded["ids"]["solution"]),
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        phase_gate = page.get_by_text("Phase Gate Checklist", exact=True)
        phase_gate.wait_for(state="visible", timeout=PAGE_TIMEOUT)
        page.get_by_text("Error loading gate:").wait_for(
            state="hidden", timeout=PAGE_TIMEOUT
        )

        # Blueprint sections intentionally start collapsed. Open a supported
        # section exactly as a user must, then exercise its visible toolbar;
        # the empty-state-only "Link Existing Elements" label is not guaranteed
        # when server data says the section is populated.
        section = page.locator("#deployment_view")
        section.locator(":scope > div").first.get_by_role("button").click()
        section.get_by_role("button", name="Link", exact=True).click()
        page.get_by_role("heading", name="Link Elements").wait_for(
            state="visible", timeout=PAGE_TIMEOUT
        )
        page.get_by_role("button", name="Done", exact=True).click()
        page.get_by_role("heading", name="Link Elements").wait_for(
            state="hidden", timeout=PAGE_TIMEOUT
        )

        section.get_by_role("button", name="Codegen", exact=True).click()
        page.get_by_role("heading", name="Code Generation").wait_for(
            state="visible", timeout=PAGE_TIMEOUT
        )
        page.get_by_role("button", name="Close", exact=True).click()
        page.get_by_role("heading", name="Code Generation").wait_for(
            state="hidden", timeout=PAGE_TIMEOUT
        )
    finally:
        page.close()


def test_platform_admin_can_open_foreign_solution_code_workbench(
    browser, live_server, seeded
):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["platform_admin"])
        page.goto(
            live_server + "/solutions/" + str(seeded["ids"]["solution"]),
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        page.get_by_role("button", name="More actions").click()
        page.get_by_role("menuitem", name="Code Workbench").click()
        page.wait_for_url(lambda url: url.endswith("/codegen"), timeout=PAGE_TIMEOUT)
        page.get_by_role("heading", name="Code Workbench").wait_for(
            state="visible", timeout=PAGE_TIMEOUT
        )
        assert page.title() != "403 — Forbidden"
    finally:
        page.close()
