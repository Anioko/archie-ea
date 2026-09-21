"""Release browser tests must never silently target a fallback database."""

import pytest
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest.mock import Mock

from tests.smoke import conftest as harness
from tests.smoke.conftest import _require_explicit_test_database, _select_browser_engine


def test_smoke_database_contract_rejects_missing_explicit_url():
    with pytest.raises(pytest.UsageError, match="TEST_DATABASE_URL"):
        _require_explicit_test_database({})


def test_smoke_database_contract_mirrors_explicit_test_url_to_server():
    env = {"TEST_DATABASE_URL": "postgresql://qa@example/archie_candidate"}

    _require_explicit_test_database(env)

    assert env["DATABASE_URL"] == env["TEST_DATABASE_URL"]


def test_smoke_database_contract_rejects_conflicting_database_urls():
    env = {
        "TEST_DATABASE_URL": "postgresql://qa@example/archie_candidate",
        "DATABASE_URL": "postgresql://qa@example/archie_stale",
    }

    with pytest.raises(pytest.UsageError, match="same database"):
        _require_explicit_test_database(env)


class _PlaywrightEngines:
    chromium = object()
    firefox = object()
    webkit = object()


def test_smoke_browser_contract_selects_requested_engine():
    engines = _PlaywrightEngines()

    selected, name = _select_browser_engine(engines, {"SMOKE_BROWSER": "firefox"})

    assert selected is engines.firefox
    assert name == "firefox"


def test_smoke_browser_contract_rejects_unknown_engine():
    with pytest.raises(pytest.UsageError, match="SMOKE_BROWSER"):
        _select_browser_engine(_PlaywrightEngines(), {"SMOKE_BROWSER": "edge-ish"})


@pytest.fixture
def server_process(monkeypatch, tmp_path):
    """Exercise lifecycle failures without starting an application or connecting to a database."""
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://qa@example/archie_candidate")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(harness, "_free_port", lambda: 50123)
    monkeypatch.setattr(harness, "_has_gunicorn", lambda: True)
    monkeypatch.setattr(harness.tempfile, "gettempdir", lambda: str(tmp_path))
    proc = Mock()
    proc.poll.return_value = None
    started = {}

    def launch(cmd, **kwargs):
        started.update(cmd=cmd, **kwargs)
        kwargs["stdout"].write(b"server boot diagnostic\n")
        return proc

    popen = Mock(side_effect=launch)
    monkeypatch.setattr(harness.subprocess, "Popen", popen)
    response = Mock(status=200)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(urllib.request, "urlopen", Mock(return_value=response))
    finalizers = []
    request = SimpleNamespace(addfinalizer=finalizers.append, session=SimpleNamespace(testsfailed=0))

    def finish():
        while finalizers:
            finalizers.pop()()

    state = SimpleNamespace(proc=proc, started=started, popen=popen, request=request, finish=finish)
    yield state
    finish()


@pytest.mark.parametrize("workers", [None, 1])
def test_server_worker_variants_share_stub_environment_and_cleanup(server_process, workers):
    peer = Mock()
    peer.child_environment.side_effect = lambda env: dict(env, SMOKE_PROTOCOL_PEER="local")
    app = object()
    options = {} if workers is None else {"workers": workers}
    lifecycle = harness._serve_application(server_process.request, peer, app, **options)

    server = next(lifecycle)

    assert server.app is app
    cmd = server_process.started["cmd"]
    assert cmd[cmd.index("--workers") + 1] == str(workers or 2)
    assert server_process.started["env"]["SMOKE_PROTOCOL_PEER"] == "local"
    assert server_process.started["env"]["DATABASE_URL"] == "postgresql://qa@example/archie_candidate"
    peer.child_environment.assert_called_once()
    with pytest.raises(StopIteration):
        next(lifecycle)
    server_process.finish()
    server_process.proc.terminate.assert_called_once()
    server_process.proc.wait.assert_called_once_with(timeout=20)
    assert server_process.started["stdout"].closed


def test_server_refuses_missing_database_before_launch(server_process, monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL")
    lifecycle = harness._serve_application(server_process.request, None, None)

    with pytest.raises(pytest.UsageError, match="TEST_DATABASE_URL"):
        next(lifecycle)

    server_process.popen.assert_not_called()


def test_server_boot_exit_reports_file_log_and_reaps_process(server_process):
    server_process.proc.poll.return_value = 1
    lifecycle = harness._serve_application(server_process.request, None, None)

    with pytest.raises(pytest.fail.Exception, match="app exited during boot:.*\nserver boot diagnostic"):
        next(lifecycle)

    server_process.finish()
    server_process.proc.wait.assert_called_once_with(timeout=5)
    assert server_process.started["stdout"].closed


def test_server_boot_timeout_reports_log_and_kills_unresponsive_process(server_process, monkeypatch):
    clock = iter([0, harness.BOOT_TIMEOUT + 1])
    monkeypatch.setattr(harness.time, "time", lambda: next(clock))
    lifecycle = harness._serve_application(server_process.request, None, None)
    server_process.proc.wait.side_effect = [harness.subprocess.TimeoutExpired("server", 20), 0]

    with pytest.raises(pytest.fail.Exception, match="app did not bind.*\nserver boot diagnostic"):
        next(lifecycle)

    server_process.finish()
    server_process.proc.terminate.assert_called_once()
    server_process.proc.kill.assert_called_once()
    assert server_process.proc.wait.call_count == 2
    assert server_process.started["stdout"].closed


def test_server_launch_failure_closes_log(server_process):
    def fail_launch(cmd, **kwargs):
        server_process.started.update(kwargs)
        raise OSError("process launch failed")

    server_process.popen.side_effect = fail_launch
    lifecycle = harness._serve_application(server_process.request, None, None)

    with pytest.raises(OSError, match="process launch failed"):
        next(lifecycle)

    assert server_process.started["stdout"].closed


def test_server_without_gunicorn_accepts_degraded_health_and_reports_journey_failure(
    server_process, monkeypatch, capsys
):
    monkeypatch.setattr(harness, "_has_gunicorn", lambda: False)
    original_urlopen = urllib.request.urlopen

    def degraded_health(url, **kwargs):
        if url.endswith("/health"):
            raise urllib.error.HTTPError(url, 503, "cache unavailable", {}, None)
        return original_urlopen(url, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", degraded_health)
    lifecycle = harness._serve_application(server_process.request, None, None, workers=1)

    next(lifecycle)
    assert server_process.started["cmd"][1:4] == ["-m", "flask", "--app"]
    assert "--no-reload" in server_process.started["cmd"]
    server_process.started["stdout"].flush()
    server_process.request.session.testsfailed = 1
    with pytest.raises(StopIteration):
        next(lifecycle)
    assert "server boot diagnostic" in capsys.readouterr().out
