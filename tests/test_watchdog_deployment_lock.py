"""Run the watchdog shell with isolated files and no real Docker/network access."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
if BASH is None and os.name == "nt" and shutil.which("git"):
    BASH = str(Path(shutil.which("git")).resolve().parents[1] / "bin/bash.exe")


@pytest.fixture
def watchdog(tmp_path):
    assert BASH and Path(BASH).is_file(), "watchdog tests require Bash"
    # Redirect only host file destinations; the executed decision/control flow
    # is the production script. Commands touching Docker/network are functions.
    source = (ROOT / "deploy/archie-watchdog.sh").read_text()
    for original, target in {
        '"/var/lib/archie-watchdog"': tmp_path / "watchdog",
        '"/var/log/archie-watchdog.log"': tmp_path / "watchdog.log",
        '/var/backups/archie/LAST_SUCCESS': tmp_path / "backup-success",
        '/etc/archie-alerts.env': tmp_path / "alerts.env",
    }.items():
        source = source.replace(original, shlex.quote(target.as_posix()))
    script = tmp_path / "watchdog.sh"
    script.write_text(source, newline="\n")
    state = tmp_path / "watchdog"
    state.mkdir()
    (state / "consecutive_failures").write_text("2\n")
    release = tmp_path / "releases"
    release.mkdir()

    def run(*, status="running", lock_status=0, real_lock=False, deployment_held=False,
            bad_lock_path=False):
        env = os.environ.copy()
        env.update(TEST_SCRIPT=script.as_posix(), TEST_LOG=(tmp_path / "commands").as_posix(),
                   TEST_STATUS=status, TEST_LOCK_STATUS=str(lock_status),
                   TEST_REAL_LOCK=str(int(real_lock)), TEST_DEPLOYMENT_HELD=str(int(deployment_held)),
                   ARCHIE_RELEASE_STATE=(release / "missing" / "directory").as_posix() if bad_lock_path else release.as_posix(),
                   ALERT_WEBHOOK="")
        harness = r'''
docker() {
    printf 'docker %s\n' "$*" >> "$TEST_LOG"
    case "$1:${3:-}" in
        inspect:*RestartCount*) echo 0 ;;
        inspect:*State.Status*) printf '%s\n' "$TEST_STATUS" ;;
        inspect:*State.StartedAt*) echo '2000-01-01T00:00:00Z' ;;
        restart:*)
            if [ "$TEST_REAL_LOCK" = 1 ]; then
                # A separately opened descriptor must not acquire the deploy
                # lock even at the final restart boundary (TOCTOU regression).
                ( exec 7>"$ARCHIE_RELEASE_STATE/deploy.lock"; command flock -n 7 ) && echo LOCK_NOT_HELD >> "$TEST_LOG"
            fi
            ;;
    esac
}
curl() { return 22; }
pgrep() { return 1; }
ss() { :; }
free() { :; }
flock() {
    if [ "$TEST_REAL_LOCK" = 1 ]; then command flock "$@"; else return "$TEST_LOCK_STATUS"; fi
}
if [ "$TEST_DEPLOYMENT_HELD" = 1 ]; then
    exec 6>"$ARCHIE_RELEASE_STATE/deploy.lock"
    command flock -n 6 || exit 90
fi
source "$TEST_SCRIPT"
'''
        result = subprocess.run([BASH, "-c", harness], env=env, capture_output=True,
                                text=True, timeout=15)
        commands = tmp_path / "commands"
        log = tmp_path / "watchdog.log"
        return result, commands.read_text() if commands.exists() else "", log.read_text() if log.exists() else ""

    return run


def test_locked_deployment_prevents_restart_and_failure_accumulation(watchdog, tmp_path):
    result, commands, log = watchdog(lock_status=1)
    assert result.returncode == 0, result.stderr
    assert "docker restart" not in commands
    assert (tmp_path / "watchdog/consecutive_failures").read_text().strip() == "2"
    assert "deploy" in log.lower()
    assert "backup" in log.lower(), "backup warnings must still run during deployments"


@pytest.mark.parametrize("status", ["created", "exited", "restarting", "", "dead"])
def test_nonrunning_container_is_never_forced_to_start(watchdog, status):
    result, commands, _ = watchdog(status=status)
    assert result.returncode == 0, result.stderr
    assert "docker restart" not in commands


def test_wedged_running_container_still_collects_forensics_and_restarts(watchdog, tmp_path):
    result, commands, log = watchdog()
    assert result.returncode == 0, result.stderr
    assert "docker restart archie-ea-server-1" in commands
    assert list((tmp_path / "watchdog").glob("wedge-*.txt"))
    assert "forensics written" in log


@pytest.mark.parametrize("options", [{"lock_status": 70}, {"bad_lock_path": True}])
def test_lock_errors_fail_closed(watchdog, options):
    result, commands, _ = watchdog(**options)
    assert result.returncode != 0
    assert "docker restart" not in commands


@pytest.mark.skipif(os.name == "nt", reason="Git Bash has no kernel flock; Linux CI verifies real locks")
@pytest.mark.parametrize("deployment_held", [True, False])
def test_real_deployment_lock_serializes_through_restart(watchdog, deployment_held):
    result, commands, _ = watchdog(real_lock=True, deployment_held=deployment_held)
    assert result.returncode == 0, result.stderr
    assert ("docker restart" in commands) is not deployment_held
    assert "LOCK_NOT_HELD" not in commands
