from types import SimpleNamespace

from scripts import verify


def test_test_gate_applies_release_timeout_to_each_suite(monkeypatch):
    calls = []

    def fake_run(command, *, timeout=None, **_kwargs):
        calls.append((command, timeout))
        return SimpleNamespace(returncode=0, stdout="1 passed", stderr="")

    monkeypatch.setattr(verify, "_run", fake_run)

    result = verify.gate_tests()

    assert result.status == verify.PASS
    assert len(calls) == 2
    assert all(timeout == 3600 for _command, timeout in calls)

