"""Journey: layer tabs and element names on the architecture dashboard must be readable.

Reported problem: at 1440px the "Implementation" layer tab read "Implementa..." and a long element
name read "QA-E2E Critical Risk: Order cutov..." with no way to read the rest. That breaks the "truncation still
says what the thing is" bar the repo already holds sidebar labels to.

Asserted on the real /architecture/dashboard page in a browser, as a logged-in architect, with an element whose
name is long enough to be truncated. Two rules: a label that CAN fit at 1440px must fit, and a label that is
truncated at all must expose its full text on hover (title).
"""
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey

STATIC = Path(__file__).resolve().parents[2] / "app" / "static"
LONG_NAME = "QA-E2E Critical Risk: Order cutover data loss during the regional migration window"

MEASURE = r"""() => {
  const tabs = [...document.querySelectorAll('nav[data-testid="layer-spine"] a')].map(a => {
    const label = a.querySelector('span.truncate');
    return {text: (label.innerText || '').trim(), clipped: label.scrollWidth > label.clientWidth + 1,
            title: a.getAttribute('title') || ''};
  });
  const names = [...document.querySelectorAll('[data-field="element-name"] button')].map(b => ({
    text: (b.innerText || '').trim(), clipped: b.scrollWidth > b.clientWidth + 1,
    title: b.getAttribute('title') || ''}));
  return {tabs: tabs, names: names};
}"""


@pytest.fixture
def document(app, client):
    from app import db
    from app.models.archimate_core import ArchiMateElement

    name = LONG_NAME + " " + uuid.uuid4().hex[:4]
    with app.app_context():
        org = make_org(db, "ArchLabels")
        user = make_user(db, org, "ea", "enterprise_architect", role_name="Architect")
        element = ArchiMateElement(name=name, type="Goal", layer="Motivation")
        if hasattr(element, "organization_id"):
            element.organization_id = org
        db.session.add(element)
        db.session.commit()
        stored_org = element.organization_id
    login(client, user)
    # Pre-flight: ask the API the page will call. If the seeded element is not in its answer, the problem is
    # the fixture or tenancy, not the layout, and the failure should say so instead of timing out in a browser.
    api = client.get("/architecture/api/layer/motivation/elements")
    if name not in api.get_data(as_text=True):
        pytest.fail(
            "seeded element is not in the elements API answer (status %s, user org %s, element org %s): %s"
            % (api.status_code, org, stored_org, api.get_data(as_text=True)[:300])
        )
    return client.get("/architecture/dashboard").get_data(as_text=True)


@pytest.fixture(scope="module")
def browser():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


def _open(browser, client, document, width=1440, height=900):
    """Open the real dashboard page in a browser and wait for the element table to render."""
    pg = browser.new_page(viewport={"width": width, "height": height})
    seen = []

    def handle(route):
        url = urlparse(route.request.url)
        if url.path.startswith("/static/"):
            f = STATIC / url.path[len("/static/"):]
            return route.fulfill(path=str(f)) if f.is_file() else route.fulfill(status=404, body="")
        if url.path == "/architecture/dashboard":
            return route.fulfill(status=200, content_type="text/html", body=document)
        if url.path.startswith(("/api/", "/architecture/", "/archimate")):
            r = client.get(url.path, query_string=dict(parse_qsl(url.query)))
            seen.append((url.path, r.status_code, len(r.get_data())))
            return route.fulfill(status=r.status_code, content_type=r.content_type or "application/json", body=r.get_data())
        return route.fulfill(status=204, body="")

    pg.route("http://app.test/**", handle)
    pg.goto("http://app.test/architecture/dashboard")
    try:
        pg.wait_for_function(
            "() => [...document.querySelectorAll('[data-field=\"element-name\"]')].some(e => e.offsetParent !== null)",
            timeout=20000,
        )
    except Exception as exc:  # report what the page saw, not just that it timed out
        pg.close()
        pytest.fail("the element table never rendered; page requests: %s; %s" % (seen, str(exc)[:200]))
    pg.wait_for_timeout(800)
    return pg


@pytest.fixture
def measured(browser, client, document):
    pg = _open(browser, client, document)
    try:
        yield pg.evaluate(MEASURE)
    finally:
        pg.close()


STRIP = 'nav[data-testid="layer-spine"] > div'


def test_every_layer_tab_shows_its_full_label_at_1440(measured):
    clipped = [t["text"] for t in measured["tabs"] if t["clipped"]]
    assert clipped == [], f"layer tab labels cut off at 1440px: {clipped}"


def test_every_layer_tab_has_a_hover_title(measured):
    assert [t["text"] for t in measured["tabs"] if not t["title"]] == []


def test_a_truncated_element_name_exposes_its_full_text(measured):
    long_ones = [n for n in measured["names"] if n["text"].startswith("QA-E2E Critical Risk")]
    assert long_ones, "the seeded element did not render in the table"
    for n in long_ones:
        assert n["clipped"], "the fixture name is no longer long enough to be truncated; lengthen it"
        assert n["title"] == n["text"] or n["title"].startswith("QA-E2E Critical Risk: Order cutover"), n


def test_every_truncated_name_cell_carries_its_full_text_as_a_title(measured):
    truncated = [n for n in measured["names"] if n["clipped"]]
    assert truncated, "no name is truncated in this fixture, so the check proves nothing"
    assert [n["text"] for n in truncated if n["title"] != n["text"]] == []


def test_at_1280_every_label_fits_or_the_strip_scrolls_with_an_edge_fade(browser, client, document):
    pg = _open(browser, client, document, width=1280, height=800)
    try:
        info = pg.evaluate("""() => {
            const strip = document.querySelector('%s');
            const clipped = [...strip.querySelectorAll('a')].map(a => a.querySelector('span.truncate'))
                .filter(l => l.scrollWidth > l.clientWidth + 1).map(l => l.innerText.trim());
            return {clipped: clipped, scrolls: strip.scrollWidth > strip.clientWidth + 1,
                    fadeClass: strip.classList.contains('workbench-table-scroll'),
                    atEnd: strip.classList.contains('at-scroll-end-x')};
        }""" % STRIP)
        assert info["clipped"] == [], "labels cut off at 1280px: %s" % info["clipped"]
        if info["scrolls"]:
            assert info["fadeClass"] and not info["atEnd"], "the strip scrolls but shows no edge cue: %s" % info
            pg.evaluate("() => { const s = document.querySelector('%s'); s.scrollLeft = s.scrollWidth; }" % STRIP)
            pg.wait_for_timeout(300)
            assert pg.evaluate("() => document.querySelector('%s').classList.contains('at-scroll-end-x')" % STRIP),                 "the fade does not drop once the strip is scrolled to its end"
        reachable = pg.evaluate("""() => {
            const s = document.querySelector('%s'); const box = s.getBoundingClientRect();
            return [...s.querySelectorAll('a')].map(a => { a.scrollIntoView({inline: 'nearest', block: 'nearest'});
                const r = a.getBoundingClientRect(); return r.left >= box.left - 1 && r.right <= box.right + 1; });
        }""" % STRIP)
        assert all(reachable), "a tab cannot be brought into view: %s" % reachable
    finally:
        pg.close()


def test_the_strip_actually_scrolls_and_the_fade_behaves_when_it_is_narrow(browser, client, document):
    """The 1280px test above passes without ever exercising the fade path: seven tabs with this
    fixture's real (single-digit) counts fit at 1280px, so `info["scrolls"]` is false there and the
    scrolling/fade assertions never run. A narrow width forces genuine overflow so the mechanism this
    PR adds is actually exercised at least once, not just at a width where it happens not to be needed."""
    pg = _open(browser, client, document, width=480, height=800)
    try:
        info = pg.evaluate("""() => {
            const strip = document.querySelector('%s');
            return {scrolls: strip.scrollWidth > strip.clientWidth + 1,
                    fadeClass: strip.classList.contains('workbench-table-scroll'),
                    atEnd: strip.classList.contains('at-scroll-end-x')};
        }""" % STRIP)
        assert info["scrolls"], "expected the strip to overflow at 480px width: %s" % info
        assert info["fadeClass"] and not info["atEnd"], "the strip scrolls but shows no edge cue: %s" % info
        pg.evaluate("() => { const s = document.querySelector('%s'); s.scrollLeft = s.scrollWidth; }" % STRIP)
        pg.wait_for_timeout(300)
        assert pg.evaluate("() => document.querySelector('%s').classList.contains('at-scroll-end-x')" % STRIP), \
            "the fade does not drop once the strip is scrolled to its end"
        pg.evaluate("() => { const s = document.querySelector('%s'); s.scrollLeft = 0; }" % STRIP)
        pg.wait_for_timeout(300)
        assert not pg.evaluate("() => document.querySelector('%s').classList.contains('at-scroll-end-x')" % STRIP), \
            "the fade does not come back once the strip is scrolled away from its end"
    finally:
        pg.close()


def test_no_tab_shows_a_dash_where_a_count_is_unknown(browser, client, document):
    pg = _open(browser, client, document)
    try:
        pg.wait_for_function(
            """(sel) => [...document.querySelectorAll(sel + ' a')]
                .map(a => a.querySelector('span:last-child'))
                .filter(b => b && b.offsetParent !== null).length === 7""",
            arg=STRIP, timeout=5000,
        )
        counts = pg.evaluate("""() => [...document.querySelectorAll('%s a')]
            .map(a => a.querySelector('span:last-child'))
            .filter(b => b && b.offsetParent !== null).map(b => b.innerText.trim())""" % STRIP)
        # A count that never becomes visible (the badge silently staying display:none once its
        # count is known) is exactly the regression this fix is for; the wait_for_function above
        # fails loudly on that instead of letting an empty list pass this assertion vacuously.
        assert len(counts) == 7, "not every tab's count badge became visible: %s" % counts
        assert [c for c in counts if not c.isdigit()] == [], "tabs showing a placeholder instead of a count: %s" % counts
    finally:
        pg.close()


@pytest.mark.parametrize("width,height", [(1024, 768), (390, 844)])
def test_the_strip_causes_no_horizontal_page_overflow(browser, client, document, width, height):
    pg = _open(browser, client, document, width=width, height=height)
    try:
        overflow = pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 0, "the page overflows sideways by %dpx at %dpx wide" % (overflow, width)
    finally:
        pg.close()


@pytest.mark.parametrize("persona", ["enterprise_architect", "business_architect", "data_architect"])
def test_the_active_tab_and_test_ids_are_present_for_each_persona(app, client, persona):
    from app import db

    with app.app_context():
        org = make_org(db, "ArchLabels")
        user = make_user(db, org, "p", persona, role_name="Architect")
    login(client, user)
    response = client.get("/architecture/dashboard")
    assert response.status_code == 200, "%s cannot open the dashboard" % persona
    html = response.get_data(as_text=True)
    assert 'data-testid="layer-spine"' in html and 'data-testid="architecture-data-card"' in html
    nav = html[html.index('data-testid="layer-spine"'):]
    nav = nav[:nav.index("</nav>")]
    assert nav.count('aria-current="page"') == 1, "expected exactly one active tab for %s" % persona
