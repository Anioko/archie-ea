"""End-to-end Transformation Room creation, deep-link and honesty proof."""

import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD
from .test_accessibility_audit import TAGS

async_playwright = pytest.importorskip("playwright.async_api").async_playwright
Axe = pytest.importorskip("axe_playwright_python.async_playwright").Axe

pytestmark = [pytest.mark.smoke, pytest.mark.journey, pytest.mark.asyncio]


async def _login(page, base, email):
    await page.goto(
        base + "/account/login",
        wait_until="domcontentloaded",
        timeout=PAGE_TIMEOUT,
    )
    await page.fill("#email", email)
    await page.fill("#password", PASSWORD)
    await page.locator("#submit").dispatch_event("click")
    try:
        await page.wait_for_url(
            lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT
        )
    except Exception:
        pass
    assert "/account/login" not in page.url


async def _visit(page, base, path):
    response = await page.goto(
        base + path, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT
    )
    await page.wait_for_timeout(800)
    try:
        await page.eval_on_selector_all(
            "[x-show='showOnboarding']", "els => els.forEach(e => e.remove())"
        )
    except Exception:
        pass
    return response


async def _assert_no_blocking_axe_violations(page):
    report = await Axe().run(
        page, options={"runOnly": {"type": "tag", "values": TAGS}}
    )
    data = report.response if hasattr(report, "response") else report
    blocking = [
        item
        for item in data.get("violations", [])
        if item.get("impact") in {"critical", "serious"}
    ]
    assert blocking == []


@pytest.mark.parametrize("viewport_width", [390, 1024])
async def test_transformation_create_to_objective_deep_link_is_accessible_and_honest(
    viewport_width, live_server, seeded
):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": viewport_width, "height": 900}
        )
        page = await context.new_page()
        console_errors = []
        page_errors = []
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        try:
            await _login(
                page,
                live_server,
                seeded["emails"]["enterprise_architect"],
            )
            response = await _visit(page, live_server, "/solutions/new-programme")

            assert response.status < 400
            owner = page.get_by_role("combobox", name="Programme owner")
            await owner.fill("Smoke")
            await page.wait_for_selector(
                '#owner-results [role="option"]', timeout=PAGE_TIMEOUT
            )
            await owner.press("ArrowDown")
            active = await owner.get_attribute("aria-activedescendant")
            assert active
            await owner.press("Enter")
            assert await page.locator('input[name="owner_id"]').input_value()

            await page.locator('input[name="name"]').fill(
                f"Smoke transformation {viewport_width}"
            )
            await page.locator('textarea[name="objective"]').fill(
                "Reduce avoidable hand-offs"
            )
            await page.locator('select[name="workstream_type"]').select_option(
                "process"
            )
            await page.locator('input[name="target_date"]').fill("2027-12-31")
            await page.locator('input[name="scope_expression"]').fill("Operations")
            await page.locator('input[name="outcome"]').fill(
                "Fewer customer hand-offs"
            )
            await page.locator('input[name="metric_name"]').fill("Hand-offs")
            await page.locator('input[name="unit"]').fill("count")
            await page.locator('input[name="unavailable_reason"]').fill(
                "Baseline requested"
            )
            await page.locator('input[name="target_value"]').fill("10")
            async with page.expect_response(
                lambda item: item.url.endswith("/solutions/create-programme")
            ) as creation:
                await page.get_by_role("button", name="Create programme").click()
            creation_response = await creation.value
            assert creation_response.status < 400, await creation_response.text()
            await page.wait_for_url("**/workstreams/*/objective", timeout=PAGE_TIMEOUT)

            objective_url = page.url
            assert (
                await page.get_by_role("heading", name="Objective and scope").count()
                == 1
            )
            await page.reload(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            assert page.url == objective_url
            await _assert_no_blocking_axe_violations(page)

            await page.get_by_role("link", name="Outcomes", exact=True).last.click()
            await page.wait_for_url("**/outcomes", timeout=PAGE_TIMEOUT)
            assert (
                await page.get_by_text(
                    "Not available in this release", exact=True
                ).count()
                >= 1
            )
            assert await page.get_by_text("Ready to advance", exact=True).count() == 0

            await page.goto(
                objective_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT
            )
            await page.locator('input[name="expected_revision"]').evaluate(
                "element => element.value = '999999'"
            )
            async with page.expect_response(
                lambda item: item.url == objective_url
            ) as submitted:
                await page.get_by_role("button", name="Save objective").click()
            assert (await submitted.value).status >= 400
            assert await page.get_by_role("alert").count() == 1
            assert console_errors == []
            assert page_errors == []
        finally:
            await context.close()
            await browser.close()
