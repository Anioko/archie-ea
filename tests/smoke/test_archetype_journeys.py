"""One browser journey per archetype, against a real database.

Every archetype gets the same baseline - can it reach its own product, does the
page render, does the front end boot, is every control named, does anything
overflow - and the two archetypes with write paths additionally complete a real
piece of work through the forms.

The baseline is not filler. Each of its four checks corresponds to a defect this
suite was written after finding in production or on the way to it:

    renders           three my-applications pages 500'd on their first owned row
    front end boots   integrity hashes blocked Alpine, DOMPurify and every icon
    controls named    1,040 unlabelled inputs, the bulk of the accessibility debt
    no overflow       the mobile regression nothing else was watching for
"""

import pytest

from .conftest import ARCHETYPES, PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

# The pages each archetype exists to use. First entry is its signature screen -
# the one that, if broken, means the persona cannot do its job.
JOURNEY = {
    "solution_architect":   ["/solutions/"],
    "enterprise_architect": ["/value-streams/", "/enterprise/"],
    "business_architect":   ["/business-case/", "/capability-map/"],
    "arb_member":           ["/arb/", "/arb/reviews"],
    "portfolio_manager":    ["/applications/"],
    "cto":                  ["/dashboard/overview"],
    "procurement":          ["/procurement/", "/procurement/contracts",
                             "/procurement/licenses", "/procurement/compliance",
                             "/procurement/renewals", "/procurement/spend"],
    "application_manager":  ["/my-applications/", "/my-applications/list",
                             "/my-applications/health", "/my-applications/roadmap"],
    "platform_admin":       ["/admin/"],
}

PAGE_STATE = """() => {
  const controls = [...document.querySelectorAll('input,select,textarea')]
      .filter(e => !['hidden','submit','button','reset','image'].includes(e.type));
  const unnamed = controls.filter(e => {
      if (e.getAttribute('aria-label') || e.getAttribute('aria-labelledby')) return false;
      if (e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`)) return false;
      if (e.closest('label')) return false;
      return true;
  });
  return {
      alpine: typeof window.Alpine,
      overflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
      controls: controls.length,
      unnamed: unnamed.map(e => e.id || e.name || e.tagName.toLowerCase()),
  };
}"""


def _login(page, base, email):
    """Sign in the way a user does, and wait for the URL to change.

    The login form is Alpine-driven: @submit sets isSubmitting, which disables the
    button, so Playwright's actionability check blocks an ordinary click. And
    expect_navigation races the redirect. Force-clicking the real button and then
    waiting for the URL to stop being the login page is robust to both, and still
    exercises the actual control a user presses.
    """
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    # no_wait_after: the click causes a navigation, and without this Playwright
    # waits for the action to "settle" on a page that is being torn down.
    try:
        page.click("#submit", force=True, no_wait_after=True)
    except TypeError:                     # newer Playwright dropped the kwarg
        page.locator("#submit").dispatch_event("click")
    try:
        page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    page.wait_for_timeout(800)
    assert "/account/login" not in page.url, (
        "could not sign in as %s - still on the login page. Page said: %s"
        % (email, " ".join(page.inner_text("body").split())[:180]))


def _visit(page, base, path):
    """Load a page, dismiss the first-run overlay, return (response, state).

    Waits for domcontentloaded rather than load: `load` blocks on every image,
    font and analytics beacon, which is not what these journeys assert and made
    the suite hang on pages that render perfectly well.
    """
    response = page.goto(base + path, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(1200)
    try:
        # The onboarding modal covers the viewport on first login and would make
        # every subsequent interaction fail for reasons unrelated to the page.
        page.eval_on_selector_all("[x-show='showOnboarding']", "els => els.forEach(e => e.remove())")
    except Exception:
        pass
    return response, page.evaluate(PAGE_STATE)


@pytest.fixture
def page(browser, request):
    width = getattr(request, "param", 1440)
    ctx = browser.new_context(viewport={"width": width, "height": 900})
    ctx.set_default_timeout(PAGE_TIMEOUT)
    ctx.set_default_navigation_timeout(PAGE_TIMEOUT)
    pg = ctx.new_page()
    pg.console_errors = []
    pg.on("console", lambda m: pg.console_errors.append(m.text) if m.type == "error" else None)
    yield pg
    ctx.close()


@pytest.mark.parametrize("archetype", ARCHETYPES)
def test_archetype_can_use_its_product(archetype, page, live_server, seeded):
    """The baseline every archetype must clear."""
    _login(page, live_server, seeded["emails"][archetype])

    failures = []
    for path in JOURNEY[archetype]:
        response, state = _visit(page, live_server, path)
        status = response.status if response else 0

        if status >= 400:
            failures.append("%s -> HTTP %d" % (path, status))
            continue
        if state["alpine"] != "object":
            failures.append("%s -> front end did not boot (window.Alpine is %s)"
                            % (path, state["alpine"]))
        if state["unnamed"]:
            failures.append("%s -> %d control(s) with no accessible name: %s"
                            % (path, len(state["unnamed"]), state["unnamed"][:6]))
        if state["overflow"] > 0:
            failures.append("%s -> %dpx horizontal overflow" % (path, state["overflow"]))

    errors = [e for e in page.console_errors if "favicon" not in e.lower()]
    if errors:
        failures.append("%d console error(s): %s" % (len(errors), errors[:3]))

    assert not failures, "%s cannot use its product:\n  - %s" % (
        archetype, "\n  - ".join(failures))


@pytest.mark.parametrize("page", [390], indirect=True)
@pytest.mark.parametrize("archetype", ARCHETYPES)
def test_archetype_signature_screen_works_on_mobile(archetype, page, live_server, seeded):
    """Only the signature screen, to keep the mobile pass cheap."""
    _login(page, live_server, seeded["emails"][archetype])
    path = JOURNEY[archetype][0]
    response, state = _visit(page, live_server, path)
    assert response.status < 400, "%s -> HTTP %d at 390px" % (path, response.status)
    assert state["overflow"] == 0, "%s overflows by %dpx at 390px - the page scrolls sideways" % (
        path, state["overflow"])


# ── Write journeys: the two archetypes that gained one ──────────────────────

def test_procurement_completes_a_contract_and_licence(page, live_server, seeded):
    """Record a contract, put an over-deployed licence under it, see the breach.

    This is the persona's actual job. Until 2026-07-31 it exposed seven routes,
    all GET, and neither model was constructed anywhere in the codebase.
    """
    import uuid

    _login(page, live_server, seeded["emails"]["procurement"])
    ref = uuid.uuid4().hex[:6]

    _visit(page, live_server, "/procurement/contracts/new")
    page.fill("#contract_name", "Smoke Contract %s" % ref)
    page.fill("#contract_number", "SMK-%s" % ref)   # globally unique
    page.select_option("#contract_type", "subscription")
    page.select_option("#status", "active")
    page.fill("#contract_value", "250000")
    page.fill("#start_date", "2026-01-01")
    page.fill("#end_date", "2026-12-31")
    with page.expect_navigation(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT):
        page.eval_on_selector("form", "f => f.submit()")
    page.wait_for_timeout(1000)
    assert "Smoke Contract %s" % ref in page.inner_text("body"), \
        "contract was not created (still on %s)" % page.url

    _visit(page, live_server, "/procurement/contracts")
    assert "Smoke Contract %s" % ref in page.inner_text("body"), "contract missing from the list"

    _visit(page, live_server, "/procurement/licenses/new")
    page.select_option("#contract_id", label=[o for o in page.evaluate(
        "() => [...document.querySelectorAll('#contract_id option')].map(o => o.textContent.trim())")
        if ref in o][0])
    page.fill("#product_name", "Smoke Licence %s" % ref)
    page.fill("#quantity_entitled", "100")
    page.fill("#quantity_deployed", "150")          # deliberately over-deployed
    with page.expect_navigation(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT):
        page.eval_on_selector("form", "f => f.submit()")
    page.wait_for_timeout(1000)
    assert "Smoke Licence %s" % ref in page.inner_text("body"), "licence was not created"

    _visit(page, live_server, "/procurement/compliance")
    body = page.inner_text("body")
    assert "Smoke Licence %s" % ref in body, \
        "the over-deployed licence is not named on the compliance dashboard"
    # Quantities rendered blank until 2026-08-01: the templates read
    # consumed_quantity/entitled_quantity, which are not columns on the model.
    assert "150" in body and "100" in body, "licence quantities are not rendering"
    assert "Consumed: /" not in body, "quantity fields resolved to Undefined again"
    # The filter matched 'violation' while the model emits 'over_deployed', so the
    # panel stayed empty while the summary card counted the breach.
    assert "Violation" in body, "the breach is counted but not listed"


def test_application_manager_maintains_an_owned_application(page, live_server, seeded):
    """Set health on an owned application and see it reach the health overview."""
    _login(page, live_server, seeded["emails"]["application_manager"])
    app_id = seeded["ids"]["application"]

    _visit(page, live_server, "/my-applications/app/%d/edit" % app_id)
    assert page.locator("#health_status").count() == 1, "the edit form did not render"
    page.select_option("#health_status", "at_risk")
    page.select_option("#lifecycle_status", "operational")
    with page.expect_navigation(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT):
        page.eval_on_selector("form", "f => f.submit()")
    page.wait_for_timeout(1000)

    _visit(page, live_server, "/my-applications/health")
    # health_status did not exist as a column, so this page could only ever
    # report "unknown" for every application.
    assert "at risk" in page.inner_text("body").lower(), \
        "health assessment did not reach the health overview"


def test_an_archetype_cannot_reach_another_personas_section(page, live_server, seeded):
    """Authorisation is part of the journey, not a separate concern."""
    _login(page, live_server, seeded["emails"]["procurement"])
    response, _ = _visit(page, live_server, "/my-applications/")
    assert response.status in (403, 404), (
        "procurement reached the application manager's section (HTTP %d) - "
        "requires_application_owner is not holding" % response.status)
