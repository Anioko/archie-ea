"""Journey: typing a module's name into the sidebar's "Search navigation..." must find it.

UX_IA_REVIEW.md finding 3 (High): typing "impact" returned "Searching for: impact" and nothing else, although
Impact Analysis is a working page. The sidebar box was a client-side filter over the ~16 links already rendered
in the persona's own zones; the other ~65 modules that /modules/ lists were invisible to it.

The server already had the right index: /api/sidebar/search returns `type: "module"` hits built from
visible_module_links() (the same list /modules/ renders, minus anything the user is barred from). The Ctrl-K
modal called it; the sidebar box never did. The fix reuses that endpoint rather than adding a second index.

Four layers:
  * the behaviour of app/static/js/sidebar/module_search.js, in a real browser, against canned responses;
  * the endpoint contract the box now depends on (found by name; nothing the persona cannot open);
  * the rendered sidebar actually contains the results region and loads that module;
  * the real rendered sidebar in a browser with real Alpine: typing "impact" shows the link.
"""

import json
from pathlib import Path

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey

STATIC = Path(__file__).resolve().parents[2] / "app" / "static"
MODULE = STATIC / "js" / "sidebar" / "module_search.js"

HARNESS = """<!doctype html><html><body>
<script src="%s"></script>
<script>
window.log = {fetches: [], states: []};
window.pending = [];
window.finder = SidebarModuleSearch.create({
  delay: 20,
  fetchJson: function (q) {
    window.log.fetches.push(q);
    return new Promise(function (resolve, reject) { window.pending.push({q: q, resolve: resolve, reject: reject}); });
  },
  onChange: function (s) { window.log.states.push(JSON.parse(JSON.stringify(s))); }
});
</script></body></html>"""

CANNED = {
    "results": [
        {"type": "application", "id": 1, "name": "Impact Portal", "url": "/applications/1"},
        {"type": "module", "id": "strategic.impact_analysis", "name": "Impact Analysis", "url": "/strategic/impact-analysis"},
    ],
    "total_count": 2,
}


@pytest.fixture(scope="module")
def browser():
    """One Chromium for the whole module. Playwright's sync API cannot be started twice at once
    ("Sync API inside the asyncio loop"), so every browser test here shares this instance."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


@pytest.fixture(scope="module")
def page(browser, tmp_path_factory):
    html = tmp_path_factory.mktemp("sidebar_search") / "harness.html"
    html.write_text(HARNESS % MODULE.as_uri(), encoding="utf-8")
    pg = browser.new_page()
    pg.goto(html.as_uri())
    yield pg
    pg.close()


def _reset(page):
    page.evaluate("() => { window.log.fetches.length = 0; window.log.states.length = 0; window.pending.length = 0; }")


def _last(page):
    return page.evaluate("() => window.log.states[window.log.states.length - 1]")


def test_a_one_character_query_never_calls_the_server(page):
    _reset(page)
    page.evaluate("() => window.finder.search('i')")
    page.wait_for_timeout(120)
    assert page.evaluate("() => window.log.fetches") == []
    assert _last(page)["results"] == []


def test_only_module_hits_are_returned_as_name_and_url(page):
    _reset(page)
    page.evaluate("() => window.finder.search('impact')")
    page.wait_for_function("() => window.pending.length === 1")
    page.evaluate("(body) => window.pending[0].resolve(body)", CANNED)
    page.wait_for_function("() => window.log.states.length && !window.log.states[window.log.states.length - 1].loading")
    assert _last(page)["results"] == [{"name": "Impact Analysis", "url": "/strategic/impact-analysis"}]


def test_rapid_typing_makes_one_request_for_the_final_query(page):
    _reset(page)
    page.evaluate("() => { window.finder.search('im'); window.finder.search('imp'); window.finder.search('impact'); }")
    page.wait_for_timeout(150)
    assert page.evaluate("() => window.log.fetches") == ["impact"]


def test_a_slow_earlier_response_cannot_overwrite_a_newer_one(page):
    _reset(page)
    page.evaluate("() => window.finder.search('capab')")
    page.wait_for_function("() => window.pending.length === 1")
    page.evaluate("() => window.finder.search('impact')")
    page.wait_for_function("() => window.pending.length === 2")
    newer = {"results": [{"type": "module", "id": "x", "name": "Impact Analysis", "url": "/strategic/impact-analysis"}]}
    older = {"results": [{"type": "module", "id": "y", "name": "Capability Map", "url": "/capability-map/"}]}
    page.evaluate("(b) => window.pending[1].resolve(b)", newer)
    page.wait_for_function("() => window.log.states.some(s => s.results.length === 1 && s.results[0].name === 'Impact Analysis')")
    page.evaluate("(b) => window.pending[0].resolve(b)", older)
    page.wait_for_timeout(100)
    assert _last(page)["results"] == [{"name": "Impact Analysis", "url": "/strategic/impact-analysis"}]


def test_a_failed_request_is_reported_as_an_error_not_as_no_results(page):
    _reset(page)
    page.evaluate("() => window.finder.search('impact')")
    page.wait_for_function("() => window.pending.length === 1")
    page.evaluate("() => window.pending[0].reject(new Error('boom'))")
    page.wait_for_function("() => window.log.states[window.log.states.length - 1].error === true")
    state = _last(page)
    assert state["results"] == [] and state["loading"] is False


# ---- the endpoint contract the sidebar box now depends on --------------------------------------------

def _persona(app, enterprise_role):
    from app import db

    with app.app_context():
        org_id = make_org(db, "SidebarSearch")
        return make_user(db, org_id, "nav", enterprise_role, role_name="Architect")


def _modules(client, q):
    response = client.get("/api/sidebar/search", query_string={"q": q})
    assert response.status_code == 200, response.data[:200]
    return [r for r in json.loads(response.data)["results"] if r["type"] == "module"]


def test_solution_architect_finds_impact_analysis_by_name(app, client):
    login(client, _persona(app, "solution_architect"))
    hits = _modules(client, "impact")
    assert any(h["name"] == "Impact Analysis" and h["url"] == "/strategic/impact-analysis" for h in hits), hits


def test_a_module_the_persona_cannot_open_is_never_offered(app, client):
    """Organisations is guarded by platform_admin_required; it must not be a search hit for an architect."""
    login(client, _persona(app, "solution_architect"))
    assert not [h for h in _modules(client, "organizations") if "/admin/" in h["url"]]


# ---- the rendered sidebar ----------------------------------------------------------------------------

def test_sidebar_renders_the_results_region_and_loads_the_module(app, client):
    login(client, _persona(app, "solution_architect"))
    page = client.get("/solutions/")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'data-testid="sidebar-module-results"' in body
    assert "js/sidebar/module_search.js" in body


# ---- the real sidebar, real Alpine, real endpoint -----------------------------------------------------

def _serve_app_in_browser(pg, client, document, path):
    """Serve `document` at `path`, static files from disk, and /api/sidebar/search from the Flask app,
    so the sidebar's Alpine wiring is exercised against the real markup and the real endpoint."""
    from urllib.parse import parse_qsl, urlparse

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


def test_typing_in_the_real_sidebar_finds_impact_analysis(app, client, browser):
    # The CTO's own zones do not contain Impact Analysis (only the architect personas' do), so a hit
    # here can only have come from the search, not from a link already in the sidebar.
    login(client, _persona(app, "cto"))
    page_path = "/dashboard/overview"
    document = client.get(page_path).get_data(as_text=True)
    assert 'href="/strategic/impact-analysis"' not in document.split('data-testid="sidebar-module-results"')[0]

    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        _serve_app_in_browser(pg, client, document, page_path)
        pg.goto("http://app.test" + page_path)
        pg.fill('#sidebar-nav input[x-ref="searchInput"]', "impact")
        hit = pg.locator('[data-testid="sidebar-module-results"] a[href="/strategic/impact-analysis"]')
        hit.wait_for(state="visible", timeout=10000)
        assert hit.inner_text().strip() == "Impact Analysis"

        pg.fill('#sidebar-nav input[x-ref="searchInput"]', "zzzznomatch")
        empty = pg.locator('[data-testid="sidebar-module-results"]', has_text="No module matches")
        empty.wait_for(state="visible", timeout=10000)
    finally:
        pg.close()
