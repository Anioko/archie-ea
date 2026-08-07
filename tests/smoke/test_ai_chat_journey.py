"""Browser journey for /ai-chat.

The page had no browser coverage at all — no smoke journey, no authorisation row,
no entry in the a11y baseline — while carrying roughly 2,500 lines of inline
JavaScript. That is how a dead stop button, a composer handoff writing a key
nobody reads, and a sidebar tab that never hid its own panel all shipped
unnoticed: nothing ever loaded the page in a browser and looked.

This file is the instrument the client rebuild is verified against, so its
assertions are deliberately about **transport and DOM**, never about what the
model says. The LLM provider is unconfigured in CI — `/ai-chat/models` returns an
empty list there — and a test that needs a working provider is a test that fails
for reasons unrelated to the code under change, which is how browser suites get
switched off.

Concretely, each assertion is a defect class the rebuild can reintroduce silently:

    page boots          2,500 lines move into modules; one dangling reference
                        and the whole front end stops at the first exception
    console clean       an Alpine expression error is a warning in the console
                        and nothing at all in an HTTP 200
    panels toggle       'history' was missing from switchSidebarTab's list, so
                        picking another tab left the Chats panel on screen
    composer sends      Enter was bound to nothing for a long time; the only way
                        to send was the button, which is also a keyboard trap
    request is issued   the point of the composer is that a request leaves the
                        browser — assert that, not the answer that comes back
"""

import uuid

import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

# The four sidebar panels. Contractual ids: the rebuild moves the code that
# drives them out of the template, but these are what the markup promises.
TABS = ("context", "query", "alerts", "history")

# Console noise that is not the page's doing. Kept deliberately short — every
# entry added here is a class of error this test stops seeing.
IGNORED_CONSOLE = ("favicon",)


def _login(page, base, email):
    """Sign in the way a user does. Mirrors test_accessibility_audit.py.

    The login form is Alpine-driven: @submit disables the button, so Playwright's
    actionability check blocks an ordinary click. Force-clicking the real control
    and then waiting for the URL to stop being the login page is robust to that
    and to the navigation race, while still exercising the button a user presses.
    """
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", force=True, no_wait_after=True)
    except TypeError:                     # newer Playwright dropped the kwarg
        page.locator("#submit").dispatch_event("click")
    try:
        page.wait_for_url(lambda u: "/account/login" not in u, timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    assert "/account/login" not in page.url, "could not sign in as %s" % email


@pytest.fixture
def page(browser):
    """A page whose JavaScript errors are recorded from the first navigation.

    The listeners are attached before any goto, which is the whole point: an
    exception thrown while the inline scripts are still evaluating happens long
    before any assertion could run, and is invisible afterwards.

    Both channels are collected because they carry different failures.
    `console` gets explicit console.error calls and Alpine's expression errors;
    `pageerror` gets uncaught exceptions — the ReferenceError a half-extracted
    module produces — which Playwright does not deliver as a console event.
    """
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.set_default_timeout(PAGE_TIMEOUT)
    ctx.set_default_navigation_timeout(PAGE_TIMEOUT)
    pg = ctx.new_page()
    pg.console_errors = []
    pg.page_errors = []
    pg.on("console", lambda m: pg.console_errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: pg.page_errors.append(str(e)))
    yield pg
    ctx.close()


def _js_errors(page):
    """Every JavaScript error the page has produced so far, filtered for noise."""
    return [
        err for err in (page.console_errors + page.page_errors)
        if not any(ignored in err.lower() for ignored in IGNORED_CONSOLE)
    ]


def _open_chat(page, live_server, seeded):
    """Sign in as the enterprise architect and land on a settled /ai-chat."""
    _login(page, live_server, seeded["emails"]["enterprise_architect"])
    response = page.goto(live_server + "/ai-chat", wait_until="domcontentloaded",
                         timeout=PAGE_TIMEOUT)
    status = response.status if response else 0
    assert status < 400, "/ai-chat -> HTTP %d\n%s" % (status, live_server.tail())
    # The inline scripts wire everything on DOMContentLoaded and then fetch the
    # model list and the context panel; give those a moment to fail if they mean to.
    page.wait_for_timeout(1500)
    try:
        # The first-run overlay covers the viewport and would make every
        # subsequent interaction fail for reasons unrelated to this page.
        page.eval_on_selector_all(
            "[x-show='showOnboarding']", "els => els.forEach(e => e.remove())")
    except Exception:
        pass
    return response


def _visible_panels(page):
    return [t for t in TABS if page.locator("#panel-%s" % t).is_visible()]


def test_ai_chat_renders_and_the_front_end_boots(page, live_server, seeded):
    """The page loads, Alpine is alive, and the composer is on screen.

    `window.Alpine` being an object is the cheapest proof the front end got
    further than its first script tag — an integrity-blocked or exception-halted
    bundle leaves it undefined while the server still happily returns 200.
    """
    _open_chat(page, live_server, seeded)

    assert page.evaluate("() => typeof window.Alpine") == "object", \
        "the front end did not boot — window.Alpine is not an object"
    assert page.locator("#chat-form").count() == 1, "the composer form is not in the page"
    assert page.locator("#user-input").is_visible(), "the composer textarea is not visible"
    assert page.locator("#messages-container").count() == 1, "there is no transcript container"

    errors = _js_errors(page)
    assert not errors, (
        "%d JavaScript error(s) on /ai-chat:\n  - %s\n\n"
        "The page renders regardless, which is why this went unnoticed: an "
        "exception during boot stops every listener registered after it, and "
        "the server still returns 200."
        % (len(errors), "\n  - ".join(errors[:8])))


def test_exactly_one_sidebar_panel_is_visible_at_a_time(page, live_server, seeded):
    """Each tab shows its own panel and hides the other three.

    Not a tautology: 'history' was absent from the list switchSidebarTab hides,
    so choosing Context or Query left the Chats panel stacked on top of it. The
    assertion is on the whole set, not on the chosen panel, because that is the
    half a per-tab check misses.
    """
    _open_chat(page, live_server, seeded)

    assert _visible_panels(page) == ["context"], (
        "the sidebar does not open on Context alone, it shows %s" % _visible_panels(page))

    for tab in TABS:
        page.click("#tab-%s" % tab)
        page.wait_for_timeout(300)
        visible = _visible_panels(page)
        assert visible == [tab], (
            "clicked #tab-%s and the visible panels were %s — a panel that does "
            "not hide overlays the one the user asked for" % (tab, visible))

    errors = _js_errors(page)
    assert not errors, "%d JavaScript error(s) while switching tabs:\n  - %s" % (
        len(errors), "\n  - ".join(errors[:8]))


def test_pressing_enter_sends_the_message_to_the_server(page, live_server, seeded):
    """Enter submits, the turn appears in the transcript, and a request leaves.

    Three separate things, all of which have been broken here at some point and
    none of which needs the model to answer:

      * Enter is bound. There were zero keydown listeners in this file for most
        of its life, so the composer could not be submitted from the keyboard at
        all — a WCAG failure as much as a usability one.
      * The user's own turn is rendered locally, before any response. That is
        DOM, not model output, so it holds with no provider configured.
      * A POST actually reaches /ai-chat/message or /ai-chat/message/stream.
        expect_request resolves when the request is issued, so this says nothing
        about whether an LLM was reachable — which is exactly what we want.
    """
    _open_chat(page, live_server, seeded)

    probe = "Smoke journey probe %s" % uuid.uuid4().hex[:8]
    page.fill("#user-input", probe)

    with page.expect_request(
        lambda r: "/ai-chat/message" in r.url and r.method == "POST",
        timeout=PAGE_TIMEOUT,
    ) as request_info:
        page.press("#user-input", "Enter")

    assert request_info.value, "no POST to /ai-chat/message* was issued"

    # The composer clears on send; leaving the text behind duplicates the turn
    # on the next Enter.
    assert page.input_value("#user-input") == "", "the composer did not clear on send"

    transcript = page.locator("#messages-container")
    transcript.locator(".message-content", has_text=probe).first.wait_for(
        state="visible", timeout=PAGE_TIMEOUT)

    errors = _js_errors(page)
    assert not errors, (
        "%d JavaScript error(s) while sending a message:\n  - %s\n\n"
        "A failing provider must render an error in the transcript, not throw."
        % (len(errors), "\n  - ".join(errors[:8])))
