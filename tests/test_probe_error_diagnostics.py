"""Exercise probe reporting without a server, browser, or database."""

import json
from functools import partial
from types import SimpleNamespace

import pytest
import requests
from werkzeug.routing import Map, Rule

from tests.smoke import test_adversarial_probes as probes


def _response(payload, status=503):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload).encode()
    return response


def _run_probe(monkeypatch, outcome, kind="persona"):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(probes, "_api_session", lambda *args: SimpleNamespace(get=get))
    monkeypatch.setattr(probes, "_load_baseline", lambda: {})
    route = "/api/archimate/relationships"
    if kind == "phantom":
        route += "/<int:id>"
    rules = Map([Rule(route, methods=["GET"])])
    monkeypatch.setattr(probes, "_rules", lambda: list(rules.iter_rules()))
    seeded = {"emails": {"enterprise_architect": "test@example.invalid",
                         "platform_admin": "admin@example.invalid"}}
    if kind == "persona":
        invoke = partial(probes.test_no_persona_can_reach_a_5xx_on_their_own_pages,
            "enterprise_architect", "http://test.invalid", seeded)
    elif kind == "pagination":
        invoke = partial(probes.test_hostile_pagination_never_reaches_a_500,
            "http://test.invalid", seeded)
    else:
        invoke = partial(probes.test_a_nonexistent_entity_is_never_rendered_as_a_real_one,
            "http://test.invalid", seeded)
    return invoke, calls


@pytest.mark.parametrize("kind", ["persona", "pagination", "phantom"])
def test_connection_failure_reports_cause_and_still_fails(monkeypatch, kind):
    invoke, calls = _run_probe(
        monkeypatch, requests.ConnectionError("RemoteDisconnected: peer closed\nconnection"), kind)
    with pytest.raises(AssertionError) as failure:
        invoke()
    assert "ConnectionError: RemoteDisconnected: peer closed connection" in str(failure.value)
    assert len(calls) == (len(probes.HOSTILE_PARAMS) if kind == "pagination" else 1)
    assert all(options["timeout"] == (25 if kind == "persona" else 20)
               and options["allow_redirects"] is False for _, options in calls)


@pytest.mark.parametrize("kind", ["persona", "pagination"])
def test_503_reports_json_reason_without_allowlisting_or_retry(monkeypatch, kind):
    invoke, calls = _run_probe(monkeypatch, _response({
        "error": "not_configured", "message": "Integration is unavailable",
        "headers": {"Authorization": "secret"}, "cookie": "secret",
    }), kind)
    with pytest.raises(AssertionError) as failure:
        invoke()
    report = str(failure.value)
    assert "503" in report
    assert "not_configured" in report
    assert "Integration is unavailable" in report
    assert "secret" not in report
    assert len(calls) == 1


@pytest.mark.parametrize("status", [200, 302, 403, 404, 501])
def test_persona_existing_nonfailure_statuses_remain_nonfailures(monkeypatch, status):
    invoke, _ = _run_probe(monkeypatch, _response({"error": "ignored"}, status))
    invoke()


@pytest.mark.parametrize("payload", [[], {"error": {"password": "secret"}}, None])
def test_unusable_json_does_not_mask_503(monkeypatch, payload):
    invoke, _ = _run_probe(monkeypatch, _response(payload))
    with pytest.raises(AssertionError, match="503") as failure:
        invoke()
    assert "secret" not in str(failure.value)


def test_html_error_is_not_dumped(monkeypatch):
    response = _response(None)
    response._content = b"<html>secret traceback</html>"
    invoke, _ = _run_probe(monkeypatch, response)
    with pytest.raises(AssertionError, match="503") as failure:
        invoke()
    assert "secret" not in str(failure.value)


def test_diagnostic_text_is_bounded_and_redacts_credentials():
    text = probes._diagnostic_text(
        "https://alice:secret@test.invalid/path?token=private "
        "password=hunter2 Authorization: Bearer hidden\nCookie: session=hidden\n"
        + "x" * 1000)
    assert len(text) <= 300
    assert "\n" not in text
    assert "test.invalid/path" in text
    for secret in ("alice", "secret", "private", "hunter2", "hidden"):
        assert secret not in text
    assert text.endswith("...")
