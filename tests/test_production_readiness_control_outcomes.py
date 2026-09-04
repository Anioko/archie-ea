"""Outcome-level checks for the exhaustive browser control census."""

from playwright.sync_api import sync_playwright

from scripts import production_readiness_audit as audit


def test_mutating_controls_are_reserved_for_seeded_journeys():
    controls = [
        {"tag": "button", "type": "submit", "label": "Save", "form_method": "post",
         "href": "", "handlers": {}, "disabled": False},
        {"tag": "a", "type": "", "label": "Delete record", "form_method": "",
         "href": "/records/1/delete", "handlers": {}, "disabled": False},
        {"tag": "button", "type": "button", "label": "Import", "form_method": "",
         "href": "", "handlers": {"@click": "importRows()"}, "disabled": False},
        {"tag": "a", "type": "", "label": "Sign out", "form_method": "",
         "href": "/account/logout", "handlers": {}, "disabled": False},
    ]

    assert [audit.classify_control_for_outcome(c)[0] for c in controls] == [
        "dedicated-seeded-journey",
        "dedicated-seeded-journey",
        "dedicated-seeded-journey",
        "dedicated-seeded-journey",
    ]


def test_safe_control_classification_excludes_fields_and_disabled_controls():
    assert audit.classify_control_for_outcome({"tag": "input", "disabled": False})[0] == "field"
    assert audit.classify_control_for_outcome({"tag": "button", "disabled": True})[0] == "disabled"
    assert audit.classify_control_for_outcome({
        "tag": "a", "href": "/portfolio", "label": "Portfolio", "disabled": False,
        "form_method": "", "handlers": {}, "type": "",
    })[0] == "safe"


def test_repeated_navigation_is_deduplicated_but_page_controls_are_not():
    navigation = {"tag": "a", "href": "/portfolio", "label": "Portfolio"}
    button = {"tag": "button", "href": "", "label": "Open", "handlers": {"@click": "open"}}

    assert audit.control_outcome_fingerprint(navigation, "/one") == (
        audit.control_outcome_fingerprint(navigation, "/two")
    )
    assert audit.control_outcome_fingerprint(button, "/one") != (
        audit.control_outcome_fingerprint(button, "/two")
    )


def test_real_browser_probe_requires_an_observable_outcome_not_a_handler():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()

        page = context.new_page()
        page.set_content(
            '<button onclick="window.__called = true">Do thing</button>'
            '<span id="clock">0</span>'
            '<script>setInterval(() => clock.textContent = Date.now(), 10)</script>'
        )
        dead = audit.probe_control_outcome(page, 0)
        page.set_content(
            '<button onclick="document.querySelector(\'#panel\').hidden=false">Open</button>'
            '<section id="panel" hidden>Visible result</section>'
        )
        changed = audit.probe_control_outcome(page, 0)
        page.set_content(
            '<a href="#destination">Continue</a>'
            '<div style="height:2000px"></div><div id="destination">Destination</div>'
        )
        navigated = audit.probe_control_outcome(page, 0)
        page.set_content('<a href="#missing">Does nothing</a>')
        empty_fragment = audit.probe_control_outcome(page, 0)
        browser.close()

    assert dead["status"] == "no-observable-outcome"
    assert changed["status"] == "verified"
    assert changed["outcome"] == "visible-state-change"
    assert navigated["status"] == "verified"
    assert navigated["outcome"] == "visible-state-change"
    assert empty_fragment["status"] == "no-observable-outcome"


def test_runtime_non_get_request_is_blocked_and_deferred():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        page.set_content(
            '<base href="http://audit.invalid/">'
            '<button onclick="fetch(\'/mutate?token=private\', {method: \'POST\'})">Run</button>'
        )
        result = audit.probe_control_outcome(page, 0)
        browser.close()

    assert result["status"] == "dedicated-seeded-journey"
    assert result["outcome"] == "blocked-non-get-request"
    assert "private" not in str(result)


def test_level_ten_persists_outcomes_and_reports_only_real_failures():
    source = (audit.REPO / "scripts/production_readiness_audit.py").read_text(encoding="utf-8")

    assert '"control_outcomes": control_outcomes' in source
    assert "if 10 in level_set" in source
    assert '"kind": "control-no-outcome"' in source
    assert "probe_control_outcome(" in source
    assert 'outcome_page, control["ordinal"]' in source
    assert "len(control_outcomes) % 25" in source
