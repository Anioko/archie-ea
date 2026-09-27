"""Authenticated real-browser downloads must contain populated architecture data.

Direct export navigation is tested here, not discovery of a UI export button.
"""
import csv
import json

import pytest
from playwright.sync_api import Error

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


@pytest.mark.parametrize("format_type", ["csv", "json"])
def test_populated_architecture_download(browser, live_server, seeded, tmp_path, format_type):
    page = browser.new_page(accept_downloads=True)
    try:
        _login(page, live_server, seeded["emails"]["platform_admin"])
        with page.expect_download(timeout=PAGE_TIMEOUT) as pending:
            try:
                response = page.goto(live_server + "/architecture/export?format=" + format_type,
                                     timeout=PAGE_TIMEOUT)
                if response is not None:
                    assert response.status == 200, "Export returned HTTP %s: %s" % (response.status, response.text())
                    assert "attachment" in response.headers.get("content-disposition", ""), "Export rendered a page instead of downloading a file"
            except Error as exc:
                # Chromium reports attachment navigation as aborted; only that
                # navigation outcome is allowed, and a completed file is mandatory.
                if "ERR_ABORTED" not in str(exc) and "Download is starting" not in str(exc):
                    raise
        download = pending.value
        assert download.failure() is None
        assert download.suggested_filename.endswith("." + format_type)
        path = tmp_path / ("architecture." + format_type)
        download.save_as(path)
        if format_type == "csv":
            with path.open(encoding="utf-8", newline="") as source:
                rows = list(csv.DictReader(source))
            assert rows, "Populated seeded architecture must not export only a header"
            assert all(row["id"] and row["name"] and row["element_type"] for row in rows)
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["elements"], "Populated seeded architecture must not export an empty list"
            assert isinstance(data["relationships"], list)
    finally:
        page.close()
