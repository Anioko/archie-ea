"""Impact API pagination, owner, and health columns: a CTO asks what breaks
if a platform fails, pages to the second page, and sees owner and health on
every row."""

import json

import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


@pytest.fixture(scope="module")
def pagination_graph(seeded, live_server):
    """A chain of 7 connected elements in the seeded organisation so that
    page_size=3 produces three pages."""
    from app import create_app, db
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship

    app = create_app("testing")
    org_id = seeded["ids"]["org"]
    out = {}
    with app.app_context():
        elements = []
        for i in range(7):
            el = ArchiMateElement(
                name="Impact Page %d" % i,
                type="ApplicationComponent",
                layer="application",
                organization_id=org_id,
            )
            db.session.add(el)
            db.session.flush()
            elements.append(el)
        # Chain: 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6
        for i in range(6):
            rel = ArchiMateRelationship(
                source_id=elements[i].id,
                target_id=elements[i + 1].id,
                type="Serving",
                organization_id=org_id,
            )
            db.session.add(rel)
        db.session.commit()
        out["root_id"] = elements[0].id
        out["all_ids"] = [el.id for el in elements[1:]]  # dependencies only
    return out


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.set_default_timeout(PAGE_TIMEOUT)
    ctx.set_default_navigation_timeout(PAGE_TIMEOUT)
    pg = ctx.new_page()
    yield pg
    ctx.close()


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", no_wait_after=True)
    except TypeError:
        page.locator("#submit").dispatch_event("click")
    page.wait_for_url(lambda u: "/account/login" not in u, timeout=PAGE_TIMEOUT)
    assert "/account/login" not in page.url, "could not sign in as %s" % email


def test_impact_api_pagination_owner_health(page, live_server, seeded, pagination_graph):
    """CTO asks what breaks: the impact API returns paginated results with
    total, next_cursor, and every row carries owner and health fields."""
    _login(page, live_server, seeded["emails"]["cto"])

    root_id = pagination_graph["root_id"]
    all_dep_ids = set(pagination_graph["all_ids"])
    seen_ids = set()
    cursor = None
    pages = 0

    while True:
        url = live_server + "/api/v1/intelligence/impact/%d?page_size=3&max_depth=6" % root_id
        if cursor is not None:
            url += "&cursor=%d" % cursor

        response = page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        assert response is not None
        assert response.status == 200, "impact API returned %d" % response.status

        body = response.json()
        assert body.get("success"), "impact API response not successful"
        data = body["data"]

        # Every response carries total and next_cursor.
        assert "total" in data, "response missing total"
        assert "next_cursor" in data, "response missing next_cursor"
        assert data["total"] == 6, "expected 6 dependencies, got %d" % data["total"]

        rows = data.get("rows") or []
        assert len(rows) > 0, "page %d returned no rows" % (pages + 1)

        for row in rows:
            assert "element_id" in row, "row missing element_id"
            assert "health" in row, "row missing health field"
            assert "owner" in row, "row missing owner field"
            seen_ids.add(row["element_id"])

        pages += 1
        cursor = data["next_cursor"]
        if cursor is None:
            break

    # All dependency elements must appear across pages.
    assert seen_ids == all_dep_ids, (
        "paginated walk missed elements: expected %s, got %s" % (all_dep_ids, seen_ids)
    )
    assert pages == 2, "expected 2 pages with page_size=3 and 6 rows, got %d" % pages