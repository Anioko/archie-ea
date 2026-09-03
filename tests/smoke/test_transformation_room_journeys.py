"""End-to-end Transformation Room creation, deep-link and honesty proof."""

import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD
from .test_accessibility_audit import TAGS

axe_module = pytest.importorskip("axe_playwright_python.sync_playwright")

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").dispatch_event("click")
    try:
        page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    assert "/account/login" not in page.url


def _visit(page, base, path):
    response = page.goto(base + path, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(800)
    try:
        page.eval_on_selector_all(
            "[x-show='showOnboarding']", "els => els.forEach(e => e.remove())"
        )
    except Exception:
        pass
    return response


def _assert_no_blocking_axe_violations(page):
    report = axe_module.Axe().run(
        page, options={"runOnly": {"type": "tag", "values": TAGS}}
    )
    data = report.response if hasattr(report, "response") else report
    blocking = [
        item
        for item in data.get("violations", [])
        if item.get("impact") in {"critical", "serious"}
    ]
    assert not blocking, repr([
        (item["id"], [node.get("target") for node in item.get("nodes", [])])
        for item in blocking
    ])


@pytest.mark.parametrize("viewport_width", [390, 1024])
def test_transformation_create_to_objective_deep_link_is_accessible_and_honest(
    viewport_width, browser, live_server, seeded
):
    context = browser.new_context(viewport={"width": viewport_width, "height": 900})
    page = context.new_page()
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
        _login(page, live_server, seeded["emails"]["enterprise_architect"])
        response = _visit(page, live_server, "/solutions/new-programme")

        assert response.status < 400

        # The intake is a six-step wizard. Each step only reveals its own fields,
        # and Continue stays disabled until that step's required fields are
        # filled -- so walking it is also the assertion that the gating works.
        advance = page.get_by_test_id("wizard-next")

        def _advance(from_step, to_step):
            """Advance one step, waiting for the destination to actually show.

            Clicking blind and asserting only at the end tells you a step was
            missed but not which one, and races Alpine at narrow viewports where
            the step nav reflows.
            """
            page.get_by_test_id(f"step-{from_step}").wait_for(
                state="visible", timeout=PAGE_TIMEOUT
            )
            advance.click()
            page.get_by_test_id(f"step-{to_step}").wait_for(
                state="visible", timeout=PAGE_TIMEOUT
            )

        # Step 1: intent
        page.locator('input[name="name"]').fill(f"Smoke transformation {viewport_width}")
        page.locator('textarea[name="objective"]').fill("Reduce avoidable hand-offs")
        _advance("intent", "ownership")

        # Step 2: ownership -- the owner picker keeps its full combobox keyboard
        # contract (arrow key moves aria-activedescendant, Enter selects).
        owner = page.get_by_role("combobox", name="Programme owner")
        owner.fill("Smoke")
        page.wait_for_selector('#owner-results [role="option"]', timeout=PAGE_TIMEOUT)
        owner.press("ArrowDown")
        assert owner.get_attribute("aria-activedescendant")
        owner.press("Enter")
        assert page.locator('input[name="owner_id"]').input_value()
        page.locator('input[name="target_date"]').fill("2027-12-31")
        _advance("ownership", "workstream")

        # Step 3: workstream
        page.locator('select[name="workstream_type"]').select_option("process")
        page.locator('input[name="scope_expression"]').fill("Operations")
        _advance("workstream", "outcome")

        # Step 4: outcome
        page.locator('input[name="outcome"]').fill("Fewer customer hand-offs")
        _advance("outcome", "measure")

        # Step 5: measure -- no baseline, so the reason carries it rather than a
        # zero that would read as a measured value.
        page.locator('input[name="metric_name"]').fill("Hand-offs")
        page.locator('input[name="unit"]').fill("count")
        page.locator('input[name="unavailable_reason"]').fill("Baseline requested")
        page.locator('input[name="target_value"]').fill("10")
        _advance("measure", "review")

        # Step 6: review reads back what will actually be sent.
        assert page.get_by_test_id("step-review").is_visible()
        assert (
            page.get_by_test_id("review-name").inner_text().strip()
            == f"Smoke transformation {viewport_width}"
        )
        # An absent baseline shows its reason, never 0.
        assert page.get_by_test_id("review-baseline").inner_text().strip() == "Baseline requested"
        with page.expect_response(
            lambda item: item.url.endswith("/solutions/create-programme")
        ) as creation:
            page.get_by_test_id("wizard-submit").click()
        creation_response = creation.value
        assert creation_response.status < 400, creation_response.text()
        page.wait_for_url("**/workstreams/*/objective", timeout=PAGE_TIMEOUT)

        objective_url = page.url
        assert page.get_by_role("heading", name="Objective and scope").count() == 1
        page.reload(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        assert page.url == objective_url
        _assert_no_blocking_axe_violations(page)

        page.get_by_role("link", name="Outcomes", exact=True).last.click()
        page.wait_for_url("**/outcomes", timeout=PAGE_TIMEOUT)
        assert page.get_by_text("Not available in this release", exact=True).count() >= 1
        assert page.get_by_text("Ready to advance", exact=True).count() == 0

        page.goto(objective_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        assert console_errors == []
        assert page_errors == []
        page.get_by_test_id("objective-form").locator(
            'input[name="expected_revision"]'
        ).evaluate(
            "element => element.value = '999999'"
        )
        with page.expect_response(lambda item: item.url == objective_url) as submitted:
            page.get_by_role("button", name="Save objective").click()
        assert submitted.value.status >= 400
        page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        page.locator('[role="alert"]:visible').first.wait_for(timeout=PAGE_TIMEOUT)
        assert page.locator('[role="alert"]:visible').count() >= 1
        assert page_errors == []
    finally:
        context.close()
