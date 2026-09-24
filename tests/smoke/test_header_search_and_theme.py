"""Behavioural tests for the header search trigger and dark-theme toggle.

These drive a real browser against a live server because string-matching
the rendered HTML cannot prove the event object is not passed as the search
query, nor that the theme toggle actually applies the ``dark`` class.
"""

import pytest

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login, _visit, page  # noqa: F401

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def test_dark_theme_toggle_applies_and_removes_dark_class(page, live_server, seeded):
    """Clicking the Dark theme menuitemcheckbox once adds the ``dark`` class
    to ``<html>``; clicking it again removes it.  The switch must not
    double-toggle (D-1)."""
    _login(page, live_server, seeded["emails"]["enterprise_architect"])
    _visit(page, live_server, "/dashboard/overview")

    # Open the user menu
    user_btn = page.locator("#user-menu-btn")
    user_btn.click()
    page.wait_for_timeout(400)

    # The dark-theme item is a <button role="menuitemcheckbox">
    dark_item = page.locator('button[role="menuitemcheckbox"]')
    assert dark_item.count() == 1, "expected exactly one menuitemcheckbox in the user menu"

    # Click once — dark class must appear
    dark_item.click()
    page.wait_for_timeout(400)
    has_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
    assert has_dark is True, "expected <html> to have class 'dark' after one click"

    # Click again — dark class must be removed
    # Re-open the menu (it may have closed)
    if not page.locator('button[role="menuitemcheckbox"]').is_visible():
        page.locator("#user-menu-btn").click()
        page.wait_for_timeout(400)
    dark_item = page.locator('button[role="menuitemcheckbox"]')
    dark_item.click()
    page.wait_for_timeout(400)
    has_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
    assert has_dark is False, "expected <html> to NOT have class 'dark' after second click"


def test_search_trigger_does_not_pass_event_as_query(page, live_server, seeded):
    """Clicking the desktop search trigger must open the search modal with an
    empty input, not ``[object PointerEvent]``."""
    _login(page, live_server, seeded["emails"]["enterprise_architect"])
    _visit(page, live_server, "/dashboard/overview")

    # Click the desktop search trigger
    search_trigger = page.locator("#search-modal-trigger")
    search_trigger.click()
    page.wait_for_timeout(600)

    # The search modal should be visible and its input empty
    search_input = page.locator("#search-modal-input")
    assert search_input.is_visible(), "search modal input not visible after clicking trigger"
    value = search_input.input_value()
    assert value == "", (
        f"search input value must be empty after trigger click, got {value!r}"
    )


def test_dark_theme_toggle_via_enter_key_toggles_exactly_once(page, live_server, seeded):
    """Pressing Enter once on the focused Dark theme menuitemcheckbox must
    toggle the ``dark`` class exactly once.  A redundant @keydown handler
    would cause a double-toggle in some browsers (D-5)."""
    _login(page, live_server, seeded["emails"]["enterprise_architect"])
    _visit(page, live_server, "/dashboard/overview")

    # Open the user menu
    user_btn = page.locator("#user-menu-btn")
    user_btn.click()
    page.wait_for_timeout(400)

    # Focus the dark-theme menuitemcheckbox
    dark_item = page.locator('button[role="menuitemcheckbox"]')
    assert dark_item.count() == 1
    dark_item.focus()
    page.wait_for_timeout(100)

    # Press Enter once
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)

    # Verify dark class was applied exactly once
    has_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
    assert has_dark is True, (
        "expected <html> to have class 'dark' after pressing Enter on the "
        "dark theme menuitemcheckbox — the toggle may have double-fired and "
        "returned to the original state"
    )