"""Cost visibility Playwright journey.

As the platform admin, set a finance-capable role for a user, reload,
and see cost shown to that user and hidden from a non-finance role.
"""
import uuid

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT, PASSWORD, type_and_wait

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def _seed_cost_graph(org_id):
    """Seed an ArchiMate element with a PortfolioInitiative carrying budget
    figures, so the Ask strategy lens has something to show or redact."""
    from app import create_app, db
    from app.models.archimate_core import ArchiMateElement
    from app.models.enterprise_intelligence import PortfolioInitiative

    app = create_app("testing")
    suffix = uuid.uuid4().hex[:6]
    noun = f"CostTest {suffix}"
    out = {"noun": noun, "org": org_id}
    with app.app_context():
        element = ArchiMateElement(
            name=f"{noun} Service", type="ApplicationComponent",
            layer="application", organization_id=org_id,
        )
        db.session.add(element)
        db.session.commit()

        initiative = PortfolioInitiative(
            name=f"{noun} modernisation",
            archimate_element_id=element.id,
            status="Active",
            completion_percentage=45,
            total_budget=200000.0,
            spent_to_date=180000.0,
        )
        db.session.add(initiative)
        db.session.commit()
        out["element_id"] = element.id
    return out


@pytest.fixture(scope="module")
def cost_graph(seeded, live_server):
    return _seed_cost_graph(seeded["ids"]["org"])


def _login(page, base, email):
    page.goto(base + "/account/logout", wait_until="domcontentloaded",
              timeout=PAGE_TIMEOUT)
    page.context.clear_cookies()
    page.goto(base + "/account/login", wait_until="domcontentloaded",
              timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", no_wait_after=True)
    except TypeError:
        page.locator("#submit").click()
    try:
        page.wait_for_url(lambda url: "/account/login" not in url,
                          timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    assert "/account/login" not in page.url, f"could not sign in as {email}"


def _ready(page, factory):
    page.wait_for_function(
        "(f) => { const el = document.querySelector('[x-data=\"' + f + '()\"]');"
        " return !!(el && el._x_dataStack); }",
        arg=factory,
    )


def test_platform_admin_sets_finance_role_and_cost_visibility_follows(
    page, live_server, seeded, cost_graph
):
    """Platform admin changes a user's enterprise_role to CTO (finance-capable),
    then to solution_architect (not finance-capable), and the Ask strategy lens
    shows or hides cost accordingly."""
    admin_email = seeded["emails"]["platform_admin"]
    target_email = seeded["emails"]["solution_architect"]

    # ── Step 1: sign in as platform admin and find the target user's id ──
    _login(page, live_server, admin_email)
    page.goto(live_server + "/admin/users", wait_until="domcontentloaded",
              timeout=PAGE_TIMEOUT)

    # Find the target user's row and navigate to their role edit page.
    # The admin user list renders each user with a link to their info page.
    body = page.content()
    # The user list page renders user emails; find the target.
    page.wait_for_selector("table", timeout=PAGE_TIMEOUT)
    # Click through to the user's detail page via the registered users list.
    # We need the user id — extract it from the page or use a known route.
    # The smoke fixture creates users with known emails; we can find the id
    # by looking at the admin users page.
    from app import create_app, db
    from app.models.user import User

    app = create_app("testing")
    with app.app_context():
        target_user = User.query.filter_by(email=target_email).first()
        assert target_user is not None, f"target user {target_email} not found"
        target_id = target_user.id

    # ── Step 2: set the target user's role to CTO ──
    page.goto(
        live_server + f"/admin/user/{target_id}/role",
        wait_until="domcontentloaded", timeout=PAGE_TIMEOUT,
    )
    page.wait_for_selector("form", timeout=PAGE_TIMEOUT)
    page.click("input[name='enterprise_role'][value='cto']")
    page.click("button[type='submit']")
    page.wait_for_url(live_server + f"/admin/user/{target_id}/info",
                      timeout=PAGE_TIMEOUT)

    # ── Step 3: sign in as the target user (now CTO) and verify cost shown ──
    _login(page, live_server, target_email)
    page.goto(live_server + "/intelligence/ask", wait_until="domcontentloaded",
              timeout=PAGE_TIMEOUT)
    _ready(page, "askSurface")

    page.locator("#ask-question-strategy").click()
    expect(page.locator("#ask-picker-input")).to_be_focused()
    type_and_wait(page, "ask", cost_graph["noun"])
    page.locator("#ask-picker-listbox [role=option]", has_text="Service").click()

    page.wait_for_selector("[data-ask-strategy-row]", timeout=PAGE_TIMEOUT)
    row = page.locator("[data-ask-strategy-row]")
    expect(row).to_contain_text("modernisation")
    # CTO has budget authority — cost figures must be visible.
    expect(row).to_contain_text("Budget variance")
    expect(row).not_to_contain_text("Restricted to roles with budget authority")

    # ── Step 4: sign back in as platform admin, set role to solution_architect ──
    _login(page, live_server, admin_email)
    page.goto(
        live_server + f"/admin/user/{target_id}/role",
        wait_until="domcontentloaded", timeout=PAGE_TIMEOUT,
    )
    page.wait_for_selector("form", timeout=PAGE_TIMEOUT)
    page.click("input[name='enterprise_role'][value='solution_architect']")
    page.click("button[type='submit']")
    page.wait_for_url(live_server + f"/admin/user/{target_id}/info",
                      timeout=PAGE_TIMEOUT)

    # ── Step 5: sign in as target user (now solution_architect) and verify cost hidden ──
    _login(page, live_server, target_email)
    page.goto(live_server + "/intelligence/ask", wait_until="domcontentloaded",
              timeout=PAGE_TIMEOUT)
    _ready(page, "askSurface")

    page.locator("#ask-question-strategy").click()
    expect(page.locator("#ask-picker-input")).to_be_focused()
    type_and_wait(page, "ask", cost_graph["noun"])
    page.locator("#ask-picker-listbox [role=option]", has_text="Service").click()

    page.wait_for_selector("[data-ask-strategy-row]", timeout=PAGE_TIMEOUT)
    row = page.locator("[data-ask-strategy-row]")
    expect(row).to_contain_text("modernisation")
    # Solution architect has no budget authority — cost must be redacted.
    expect(row).to_contain_text("Restricted to roles with budget authority")
    expect(row).not_to_contain_text("Budget variance")