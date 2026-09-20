"""Journey: the sidebar's scrolling list has more room, the search box stays visible while it scrolls,
a no-match search says so, and long labels wrap instead of being cut (T-236).

Reported measurements: at 1440x900 #sidebar-nav's client height was 693px by the footer's position (652px by
the audit's own script), against a target of at least 730px. The duplicated "Collapse sidebar (Ctrl+B)" row
inside the sidebar (the header already carries the same toggle, with the same Ctrl+B hint in its title) and
the search box living inside the scrolling <nav> both ate into that height for no reason.

The no-match message and its two exits ("Search everywhere (Ctrl+K)", "Browse all modules") already exist
from T-302 (docs/buckets/archie-ea-four-intelligences-extension/tasks/T-103... superseded, see PR 63); this
file only re-confirms criterion 2 still holds after the layout change, it does not re-implement it.
"""
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey

STATIC = Path(__file__).resolve().parents[2] / "app" / "static"
MIN_NAV_HEIGHT = 730


def _persona(app, enterprise_role):
    from app import db

    with app.app_context():
        org_id = make_org(db, "SidebarVisibleArea")
        return make_user(db, org_id, "u", enterprise_role, role_name="Architect")


@pytest.fixture(scope="module")
def browser():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


def _open(browser, client, document, path, width=1440, height=900):
    pg = browser.new_page(viewport={"width": width, "height": height})

    def handle(route):
        url = urlparse(route.request.url)
        if url.path.startswith("/static/"):
            f = STATIC / url.path[len("/static/"):]
            return route.fulfill(path=str(f)) if f.is_file() else route.fulfill(status=404, body="")
        if url.path == "/api/sidebar/search":
            r = client.get(url.path, query_string=dict(parse_qsl(url.query)))
            return route.fulfill(status=r.status_code, content_type="application/json", body=r.get_data())
        if url.path == path:
            return route.fulfill(status=200, content_type="text/html", body=document)
        return route.fulfill(status=204, body="")

    pg.route("http://app.test/**", handle)
    pg.goto("http://app.test" + path)
    pg.wait_for_selector("#sidebar-nav")
    return pg


def test_the_scrolling_list_is_at_least_730px_tall_at_1440(app, client, browser):
    login(client, _persona(app, "solution_architect"))
    path = "/dashboard/overview"
    document = client.get(path).get_data(as_text=True)
    pg = _open(browser, client, document, path)
    try:
        height = pg.eval_on_selector("#sidebar-nav", "el => el.clientHeight")
        assert height >= MIN_NAV_HEIGHT, "sidebar-nav is %dpx tall, expected at least %dpx" % (height, MIN_NAV_HEIGHT)
    finally:
        pg.close()


def test_the_search_box_stays_on_screen_when_the_list_is_scrolled(app, client, browser):
    # platform_admin has the longest zone list, most likely to overflow the nav.
    login(client, _persona(app, "platform_admin"))
    path = "/dashboard/overview"
    document = client.get(path).get_data(as_text=True)
    pg = _open(browser, client, document, path)
    try:
        pg.eval_on_selector("#sidebar-nav", "el => { el.scrollTop = el.scrollHeight; }")
        pg.wait_for_timeout(150)
        visible = pg.eval_on_selector(
            'input[x-ref="searchInput"]',
            "el => { const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight && r.width > 0; }",
        )
        assert visible, "the search box scrolled out of view"
    finally:
        pg.close()


def test_a_no_match_search_still_says_so_after_the_layout_change(app, client, browser):
    login(client, _persona(app, "solution_architect"))
    path = "/dashboard/overview"
    document = client.get(path).get_data(as_text=True)
    pg = _open(browser, client, document, path)
    try:
        pg.fill('input[x-ref="searchInput"]', "zzzznomatch")
        results = pg.locator('[data-testid="sidebar-search-results"]')
        results.wait_for(state="visible", timeout=10000)
        pg.wait_for_timeout(300)
        assert 'No pages match "zzzznomatch"' in results.inner_text()
        assert results.get_by_role("button", name="Search everywhere (Ctrl+K)").is_visible()

        pg.click('button[title="Clear search"]')
        pg.wait_for_timeout(150)
        assert not results.is_visible()
    finally:
        pg.close()


def test_a_long_label_wraps_instead_of_being_cut(app, client, browser):
    login(client, _persona(app, "enterprise_architect"))
    path = "/dashboard/overview"
    document = client.get(path).get_data(as_text=True)
    pg = _open(browser, client, document, path)
    try:
        link = pg.locator('#sidebar-nav a[title="Transformation programmes"] span.flex-1')
        link.wait_for(state="visible", timeout=10000)
        info = link.evaluate("""el => ({
            wraps: getComputedStyle(el).whiteSpace !== 'nowrap',
            fullText: el.textContent.trim(),
            clipped: el.scrollWidth > el.clientWidth && getComputedStyle(el).textOverflow === 'ellipsis',
        })""")
        assert info["wraps"], "the label still forces a single line (white-space: nowrap)"
        assert info["fullText"] == "Transformation programmes"
        assert not info["clipped"], "the label still ellipsis-clips instead of wrapping"
    finally:
        pg.close()


def test_the_footer_name_and_email_carry_a_title_with_the_full_text(app, client, browser):
    import uuid

    from app import db
    from app.models.user import User

    suffix = uuid.uuid4().hex[:8]
    long_email = "a-name-long-enough-to-need-a-title.%s@example.com" % suffix
    with app.app_context():
        org_id = make_org(db, "SidebarVisibleArea")
        user_id = make_user(db, org_id, "long", "solution_architect", role_name="Architect")
        user = db.session.get(User, user_id)
        user.first_name, user.last_name = "Aniekannneemeka", "Longernamewouldneverfit"
        user.email = long_email
        db.session.commit()
    login(client, user_id)
    path = "/dashboard/overview"
    document = client.get(path).get_data(as_text=True)
    pg = _open(browser, client, document, path)
    try:
        name_title = pg.eval_on_selector(".sidebar-footer-text p.font-medium", "el => el.title")
        email_title = pg.eval_on_selector(".sidebar-footer-text p.text-muted-foreground", "el => el.title")
        assert name_title == "Aniekannneemeka Longernamewouldneverfit"
        assert email_title == long_email
    finally:
        pg.close()


def test_collapse_still_works_from_the_header_toggle_and_ctrl_b(app, client, browser):
    login(client, _persona(app, "solution_architect"))
    path = "/dashboard/overview"
    document = client.get(path).get_data(as_text=True)
    pg = _open(browser, client, document, path)
    try:
        assert "sidebar-collapsed" not in pg.eval_on_selector('[data-testid="sidebar"]', "el => el.className")
        pg.click('button[title*="Collapse sidebar (Ctrl+B)"]')
        pg.wait_for_timeout(200)
        assert "sidebar-collapsed" in pg.eval_on_selector('[data-testid="sidebar"]', "el => el.className")

        pg.keyboard.press("Control+b")
        pg.wait_for_timeout(200)
        assert "sidebar-collapsed" not in pg.eval_on_selector('[data-testid="sidebar"]', "el => el.className")
    finally:
        pg.close()


def test_the_duplicated_collapse_row_is_gone(app, client, browser):
    """The sidebar's own "Collapse sidebar (Ctrl+B)" row duplicated the header toggle; removed to reclaim
    height. Exactly one occurrence of the hint text remains, in the header's own `:title` binding
    (`'Collapse sidebar (Ctrl+B)'`, present as raw source even though the value is applied by Alpine)."""
    login(client, _persona(app, "solution_architect"))
    document = client.get("/dashboard/overview").get_data(as_text=True)
    assert document.count("Collapse sidebar (Ctrl+B)") == 1
    assert "sidebar-show-all-btn" not in document
