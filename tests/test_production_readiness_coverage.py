"""Discovery evidence must not become an intended-success/completeness claim."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace

import pytest
from playwright.sync_api import sync_playwright

from scripts import production_readiness_audit as audit


@pytest.mark.parametrize("feedback_request", [False, True])
def test_visible_failure_feedback_is_not_verified_success(feedback_request):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            action = "document.querySelector('[role=alert]').hidden=false"
            if feedback_request:
                action = "fetch('/feedback').then(() => {" + action + "})"
            body = (f'<button onclick="{action}">Inspect fixture</button>'
                    '<p role="alert" hidden>Fixture operation failed</p>').encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                result = audit.probe_control_outcome(page, 0)
                assert page.get_by_role("alert").is_visible()
                assert result["status"] == "observed-unqualified"
                assert result["intended_outcome_confirmed"] is False
                assert result["outcome"] == (
                    "request-with-feedback" if feedback_request else "visible-state-change"
                )
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def manifest(*, processed=(), inventory=(), outcomes=(), state="completed", routes=None):
    return audit.build_coverage_manifest(
        routes=[{"path": "/one?secret=private#fragment", "endpoint": "one"},
                {"path": "/two", "endpoint": "two", "parameterised": True}]
        if routes is None else routes,
        personas=["business_architect"], viewports=["desktop"], levels=[10],
        processed=processed, inventory=inventory, outcomes=outcomes,
        execution_state=state,
    )


def test_manifest_reports_missing_slot_without_leaking_query_or_claiming_completion():
    result = manifest(processed=[{"slot_id": 0, "result": "html-inventoried"}])
    assert result["loads"]["expected"] == 2
    assert result["loads"]["processed"] == 1
    assert result["loads"]["missing"] == [
        {"slot_id": 1, "route": "/two", "endpoint": "two",
         "persona": "business_architect", "viewport": "desktop", "parameterised": True}
    ]
    assert result["traversal_completed"] is False
    assert result["comprehensive_qualification"] is False
    assert "private" not in json.dumps(result)
    assert "fragment" not in json.dumps(result)


def test_manifest_separates_discovery_fresh_probes_reuse_and_intended_outcomes():
    result = manifest(
        processed=[{"slot_id": 0, "result": "html-inventoried"},
                   {"slot_id": 1, "result": "parameterised-denial"}],
        inventory=[{"controls": [{}, {}, {}, {}, {}, {}]}],
        outcomes=[
            {"classification": "safe", "status": "verified", "outcome": "navigation",
             "probe_attempted": True},
            {"classification": "safe", "status": "verified", "outcome": "navigation",
             "evidence_reused": True, "probe_attempted": False},
            {"classification": "safe", "status": "observed-unqualified",
             "probe_attempted": True},
            {"classification": "dedicated-seeded-journey"},
            {"classification": "field"},
        ],
    )
    assert result["traversal_completed"] is True
    assert result["comprehensive_qualification"] is False
    controls = result["controls"]
    assert controls["discovered"] == 6
    assert controls["outcome_records"] == 5
    assert controls["fresh_probes"] == 2
    assert controls["reused_evidence"] == 1
    assert controls["primitive_events_confirmed"] == 1
    assert controls["intended_outcomes_confirmed"] == 0
    assert controls["unqualified"] == 6
    assert controls["without_outcome_record"] == 1
    assert controls["classifications"] == {"safe": 3, "dedicated-seeded-journey": 1, "field": 1}
    assert "recursive-interactions-not-covered" in result["coverage_gaps"]
    assert "seeded-route-mappings-not-covered" in result["coverage_gaps"]


@pytest.mark.parametrize("state", ["running", "interrupted"])
def test_checkpoint_never_claims_traversal_completed(state):
    result = manifest(state=state, processed=[{"slot_id": 0, "result": "non-html"},
                                              {"slot_id": 1, "result": "navigation-failed"}])
    assert result["traversal_completed"] is False
    assert result["execution_state"] == state
    assert result["loads"]["results"] == {"non-html": 1, "navigation-failed": 1}


def test_empty_route_selection_is_not_a_completed_audit():
    assert manifest(routes=[])["traversal_completed"] is False


@pytest.mark.parametrize("stage", ["boot", "seed"])
def test_setup_failure_retains_interrupted_manifest(tmp_path, monkeypatch, stage):
    monkeypatch.setattr(audit, "seed_personas", lambda: {})
    monkeypatch.setattr(audit, "collect_routes", lambda: [{"path": "/fixture", "endpoint": "fixture"}])

    def fail_boot(*args):
        raise RuntimeError("fixture boot unavailable")

    monkeypatch.setattr(audit, "boot", fail_boot)
    if stage == "seed":
        monkeypatch.setattr(audit, "seed_personas", fail_boot)
    report = tmp_path / "interrupted.json"
    args = SimpleNamespace(level=[10], route=[], persona=["business_architect"],
                           desktop_only=True, report=str(report), settle=0)
    with pytest.raises(RuntimeError, match="fixture boot unavailable"):
        audit.run(args)
    coverage = json.loads(report.read_text())["coverage_manifest"]
    assert coverage["execution_state"] == "interrupted"
    assert coverage["traversal_completed"] is False
    assert coverage["loads"]["processed"] == 0
    assert coverage["loads"]["missing"][0]["route"] == "/fixture"


def test_real_browser_run_reports_reuse_and_preserves_dead_control_exit(tmp_path, monkeypatch):
    """Only DB seeding/discovery and child boot are replaced by loopback fixtures.

    The real driver, browser, inventory, click probe, findings and JSON writer run.
    This is not authenticated full-application or persistence qualification.
    """
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, content_type = 200, "text/html"
            if self.path.startswith("/account/login"):
                body = ('<form action="/signed-in"><input id="email"><input id="password">'
                        '<button id="submit">Sign in</button></form>')
            elif self.path == "/fixture":
                body = ('<button onclick="document.querySelector(\'p\').hidden=false">Inspect</button>'
                        '<button onclick="void 0">Dead fixture</button>'
                        '<input aria-label="Fixture field">'
                        '<p role="alert" hidden>Operation failed</p>')
            elif self.path == "/record/1":
                status, body = 404, "No fixture record"
            elif self.path == "/data":
                content_type, body = "application/json", "{}"
            else:
                body = "<h1>Signed in fixture</h1>"
            encoded = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(audit, "seed_personas", lambda: {"business_architect": "fixture@example.invalid"})
    monkeypatch.setattr(audit, "collect_routes", lambda: [
        {"path": "/fixture", "endpoint": "fixture"},
        {"path": "/fixture", "endpoint": "fixture_alias"},
        {"path": "/record/1", "endpoint": "record", "parameterised": True},
        {"path": "/data", "endpoint": "data"},
    ])
    process = SimpleNamespace(terminate=lambda: None, wait=lambda timeout: None)
    monkeypatch.setattr(audit, "boot", lambda *args: (process, f"http://127.0.0.1:{server.server_port}"))
    report = tmp_path / "loopback.json"
    args = SimpleNamespace(level=[10], route=[], persona=["business_architect"],
                           desktop_only=True, report=str(report), settle=0)
    try:
        result = audit.run(args)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    retained = json.loads(report.read_text())
    coverage = retained["coverage_manifest"]
    assert result == 1
    assert [item["kind"] for item in retained["findings"]] == ["control-no-outcome"]
    assert coverage["traversal_completed"] is True
    assert coverage["comprehensive_qualification"] is False
    assert coverage["loads"]["expected"] == retained["routes_audited"] == 4
    assert coverage["loads"]["results"] == {
        "html-inventoried": 2, "parameterised-denial": 1, "non-html": 1,
    }
    assert coverage["controls"]["discovered"] == 6
    assert coverage["controls"]["fresh_probes"] == 2
    assert coverage["controls"]["reused_evidence"] == 2
    assert coverage["controls"]["outcome_records"] == 6
    assert coverage["controls"]["intended_outcomes_confirmed"] == 0
    assert coverage["controls"]["unqualified"] == 6
