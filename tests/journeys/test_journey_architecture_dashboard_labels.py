"""Journey: layer tabs and element names on the architecture dashboard must be readable.

UX_IA_REVIEW.md finding 10 (Low): at 1440px the "Implementation" layer tab read "Implementa..." and a long element
name read "QA-E2E Critical Risk: Order cutov..." with no way to read the rest. That breaks the "truncation still
says what the thing is" bar the repo already holds sidebar labels to (CLAUDE.md, 31 Aug 2026 sidebar incident).

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
        user = make_user(db, org, "sa", "solution_architect", role_name="Architect")
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


@pytest.fixture
def measured(browser, client, document):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
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
    try:
        pg.goto("http://app.test/architecture/dashboard")
        try:
            pg.wait_for_selector('[data-field="element-name"] button', timeout=20000)
        except Exception as exc:  # report what the page saw, not just that it timed out
            pytest.fail("the element table never rendered; page requests: %s; %s" % (seen, str(exc)[:200]))
        pg.wait_for_timeout(400)
        yield pg.evaluate(MEASURE)
    finally:
        pg.close()


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
