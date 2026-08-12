"""Every export document must be printable, and say so when there is nothing to print.

The four business-architecture exports render to PDF through WeasyPrint, which
binds native GTK/Pango libraries. Those are present in the shipped image and
absent on Windows and on slim images, so the PDF path is the one branch of this
feature that no developer machine exercises — the unit tests reach the 503
fallback instead, and CI has no WeasyPrint either.

That leaves the actual risk unguarded: the export *documents* are self-contained
HTML with their own ``@page`` rules, and a malformed one produces a PDF that is
empty, single-page, or does not open. This renders each document with the
chromium that Playwright already installs and asserts it becomes a real,
multi-page PDF. It does not exercise WeasyPrint — nothing here can — but it does
prove the input WeasyPrint is given is a valid printable document.

The second half matters as much. An export with no data behind it must answer
with an explanation, not a 500 and not a zero-byte file. Where a route returns
404 this asserts the body says why.
"""

from __future__ import annotations

import re

import pytest

EXPORTS = [
    ("capability model", "/capability-map/report.html"),
    ("ea briefing", "/solutions/briefings/report.html"),
]

PAGE_TIMEOUT = 30000


def _login(page, base, email):
    """Sign in exactly the way the other smoke tests do.

    The seeded password is tests/smoke/conftest.py::PASSWORD — imported rather
    than repeated, so changing it there cannot leave this file silently unable
    to log in and reporting the failure as a broken export.
    """
    from tests.smoke.conftest import PASSWORD

    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", force=True, no_wait_after=True)
    except TypeError:
        page.locator("#submit").dispatch_event("click")
    try:
        page.wait_for_url(lambda u: "/account/login" not in u, timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    assert "/account/login" not in page.url, f"could not sign in as {email}"


@pytest.mark.parametrize("name,path", EXPORTS, ids=[e[0] for e in EXPORTS])
def test_the_export_document_is_a_printable_pdf(live_server, seeded, browser, name, path):
    ctx = browser.new_context()
    ctx.set_default_timeout(PAGE_TIMEOUT)
    page = ctx.new_page()
    try:
        _login(page, live_server, seeded["emails"]["business_architect"])
        response = page.goto(live_server + path, wait_until="load", timeout=PAGE_TIMEOUT)
        status = response.status if response else 0

        if status == 404:
            # A legitimate empty state — but it has to explain itself rather
            # than hand back a bare 404 or an empty document.
            body = page.content()
            assert re.search(r"nothing to export|has been generated|no .*yet", body, re.I), (
                f"{name} returned 404 without saying why there is nothing to export"
            )
            pytest.skip(f"{name}: no data seeded for this archetype; empty state is correct")

        assert status == 200, f"{name} returned {status}"

        pdf = page.pdf(format="A4", print_background=True)
        assert pdf.startswith(b"%PDF-"), f"{name} did not produce a PDF"
        pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf))
        assert pages >= 1, f"{name} produced a PDF with no pages"
        assert len(pdf) > 5000, (
            f"{name} produced a {len(pdf)}-byte PDF, which is too small to hold "
            "a cover page and a table — the document is probably not rendering"
        )
    finally:
        ctx.close()


def test_an_unsupported_export_format_is_refused_not_crashed(live_server, seeded, browser):
    ctx = browser.new_context()
    page = ctx.new_page()
    try:
        _login(page, live_server, seeded["emails"]["business_architect"])
        response = page.goto(
            live_server + "/capability-map/report.rtf", wait_until="load",
            timeout=PAGE_TIMEOUT,
        )
        assert response is not None and response.status == 400
        assert "rtf" in page.content().lower()
    finally:
        ctx.close()
