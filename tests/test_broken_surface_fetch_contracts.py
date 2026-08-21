"""Regression coverage for dashboard fetch contracts that previously broke live surfaces."""

from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]


def test_guardrail_dedupe_blueprint_exposes_dashboard_element_groups_url():
    """The guardrail-enabled app must serve the URL dashboard.js requests.

    Removing this route from the v2 blueprint makes the dashboard's live
    ArchiMate duplicate panel receive a 404 even though the legacy blueprint
    still has an implementation.
    """
    from app.modules.duplicate_detection.v2.routes.unified_duplicate_routes import (
        unified_duplicate_bp_v2,
    )

    app = Flask(__name__)
    app.register_blueprint(unified_duplicate_bp_v2)

    assert app.url_map.bind("localhost").test(
        "/duplicate-detection/simple/api/element-groups", "GET"
    )


def test_governance_bulk_delete_rejects_non_2xx_before_reading_json():
    """A 500 body must count as a deletion failure even if it contains JSON.

    Without the HTTP-status guard a gateway error payload could claim success
    and the dashboard would show a successful delete although nothing changed.
    """
    source = (
        ROOT / "app" / "static" / "js" / "governance" / "governance_dashboard.js"
    ).read_text(encoding="utf-8")
    bulk_delete = source.split("executeBulkDelete: function", 1)[1]
    normalized = " ".join(bulk_delete.split())

    assert (
        ".then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); "
        "return r.json(); })"
    ) in normalized


def test_value_stream_ai_capability_lookup_distinguishes_http_failure_from_no_match():
    """A failed lookup must reach applySuggestion's failure toast, not say missing.

    A null result is meaningful here: it tells the user that the named capability
    was not found. HTTP and network failures are different states and must be
    re-raised so the caller surfaces the actual failed apply operation.
    """
    source = (ROOT / "app" / "static" / "js" / "value_stream" / "grid.js").read_text(
        encoding="utf-8"
    )
    resolver = source.split("async resolveCapabilityByName(name)", 1)[1].split(
        "async applySuggestion(index)", 1
    )[0]

    assert "if (!resp.ok) {" in resolver
    assert "throw new Error('Capability lookup failed (HTTP ' + resp.status + ')');" in resolver
    assert "console.error('Failed to resolve suggested capability', err);" in resolver
    assert "throw err;" in resolver, "network and JSON failures must propagate to applySuggestion"
