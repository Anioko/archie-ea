"""Run the real scripts/deploy_verified.sh against a fake droplet.

deploy_verified.sh SSHes to the droplet for every step. Here `ssh` is replaced by
a shim that runs the same remote script locally, `docker`/`curl` are stand-ins
that behave like a container which is healthy or not, and git is real (a bare
"origin" plus a checkout that plays the droplet's /root/archie-ea).

This exists to pin down how rollback state behaves when the script is run from a
machine that has never run it before, which is what a fresh CI runner is. The
script keeps its last-verified commit in a file on the machine it runs from
(DEPLOY_STATE_FILE); on a fresh runner that file does not exist, so an
automatic rollback has nothing to roll back to unless something seeds it. The
production deploy workflow seeds it by running `--skip-deploy` first, because a
passing verify-only run records the droplet's current commit there.

The fake droplet is only as faithful as its stand-ins: it proves the script's
control flow and the workflow's use of it, not Docker or the real host.
"""

from __future__ import annotations

import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy_verified.sh"
HELPERS = ROOT / "scripts" / "deploy_workflow.py"

spec = importlib.util.spec_from_file_location("deploy_workflow_fake_droplet", HELPERS)
dw = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = dw
spec.loader.exec_module(dw)

BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None or shutil.which("git") is None, reason="needs bash and git")

FAKE_SSH = """#!/bin/bash
# ssh [-o opt]... host bash -s -- args...   (remote script arrives on stdin)
while [ "$1" = "-o" ]; do shift 2; done
shift                                   # host
[ "$1" = bash ] || { echo "fake ssh: unsupported remote command: $*" >&2; exit 255; }
shift
exec bash "$@"
"""

FAKE_DOCKER = """#!/bin/bash
S="$FAKE_STATE"
echo "docker $*" >> "$S/docker.log"
if [ "$1" = compose ]; then
    case "$2" in
        rm) exit 0 ;;
        up)
            if [[ " $* " == *" --force-recreate "* ]]; then
                git rev-parse HEAD > "$S/running"
                exit 0
            fi
            echo "database-acl-1  | postgres://app:hunter2-SECRET@db:5432/archie"
            exit "${FAKE_ACL_EXIT:-0}" ;;
    esac
    exit 0
fi
if [ "$1" = inspect ]; then
    running=$(cat "$S/running" 2>/dev/null) || { echo missing; exit 0; }
    if [ "$2" = "--format" ]; then                  # health
        if grep -qx "$running" "$S/bad" 2>/dev/null; then echo unhealthy; else echo healthy; fi
    else                                            # mounts
        echo "$APP_DIR -> /app"
    fi
    exit 0
fi
exit 1
"""

FAKE_CURL = """#!/bin/bash
running=$(cat "$FAKE_STATE/running" 2>/dev/null) || exit 7
printf '{"build_id": "%s"}' "${running:0:8}"
"""

FAKE_SLEEP = "#!/bin/bash\nexit 0\n"


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.test"}
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout.strip()


class FakeDroplet:
    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.state = tmp_path / "fake-state"
        self.state.mkdir()
        self.app = tmp_path / "root-archie-ea"
        self.runner_state = tmp_path / "runner" / "last-verified-sha"
        _write(self.bin / "ssh", FAKE_SSH)
        _write(self.bin / "docker", FAKE_DOCKER)
        _write(self.bin / "curl", FAKE_CURL)
        _write(self.bin / "sleep", FAKE_SLEEP)
        _write(self.bin / "python3", "#!/bin/bash\nexec %s \"$@\"\n" % shlex.quote(Path(sys.executable).as_posix()))
        # deploy_verified.sh as committed uses LF; a Windows checkout may hold CRLF.
        self.script = tmp_path / "scripts" / "deploy_verified.sh"
        self.script.parent.mkdir()
        self.script.write_bytes(SCRIPT.read_bytes().replace(b"\r\n", b"\n"))

        work = tmp_path / "work"
        origin = tmp_path / "origin.git"
        work.mkdir()
        _git(work, "init", "-q", "-b", "main")
        self.commits = {}
        for name in ("A", "B", "C"):
            (work / "f.txt").write_text(name)
            _git(work, "add", "f.txt")
            _git(work, "commit", "-q", "-m", name)
            self.commits[name] = _git(work, "rev-parse", "HEAD")
        subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
        _git(work, "push", "-q", str(origin), "main")
        subprocess.run(["git", "clone", "-q", str(origin), str(self.app)], check=True, capture_output=True)
        # Production starts on A, running and healthy.
        _git(self.app, "checkout", "-q", "--detach", self.commits["A"])
        (self.state / "running").write_text(self.commits["A"] + "\n")

    def mark_bad(self, *names: str) -> None:
        (self.state / "bad").write_text("".join(self.commits[n] + "\n" for n in names))

    def running(self) -> str:
        return (self.state / "running").read_text().strip()

    def run(self, ref: str, *extra: str, state_file: bool = True, **env_overrides):
        env = {
            **os.environ,
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "DROPLET": "root@fake-droplet",
            "APP_DIR": self.app.as_posix(),
            "FAKE_STATE": self.state.as_posix(),
            "HEALTH_TIMEOUT_SECONDS": "1",
            "DEPLOY_STATE_FILE": self.runner_state.as_posix(),
            "DEPLOY_VERIFY_EMAIL": "",
            "DEPLOY_VERIFY_PASSWORD": "",
        }
        env.update(env_overrides)
        result = subprocess.run(
            [BASH, self.script.as_posix(), ref, *extra],
            env=env, capture_output=True, text=True, timeout=120,
        )
        return result.returncode, result.stdout + result.stderr

    def recorded(self) -> str | None:
        return self.runner_state.read_text().strip() if self.runner_state.exists() else None

    def docker_calls(self) -> list[str]:
        path = self.state / "docker.log"
        return path.read_text().splitlines() if path.exists() else []


@pytest.fixture()
def droplet(tmp_path):
    return FakeDroplet(tmp_path)


def sha(droplet, name):
    return droplet.commits[name]


def test_a_healthy_deploy_verifies_and_records_the_commit(droplet):
    rc, out = droplet.run(sha(droplet, "B"))

    assert rc == 0, out
    assert "DEPLOY VERIFIED: commit %s is running" % sha(droplet, "B") in out
    assert droplet.running() == sha(droplet, "B")
    assert droplet.recorded() == sha(droplet, "B")
    assert dw.classify_log(out, rc, sha(droplet, "B")) == ("verified", "not-attempted")


def test_the_trap_a_fresh_runner_has_nothing_to_roll_back_to(droplet):
    """No state file, as on a fresh CI runner: the failed deploy stays deployed."""
    droplet.mark_bad("B")
    rc, out = droplet.run(sha(droplet, "B"))

    assert rc == 1
    assert "no different known-good commit on record" in out
    assert "ROLLED BACK" not in out
    assert droplet.running() == sha(droplet, "B")          # production left on the bad commit
    assert dw.classify_log(out, rc, sha(droplet, "B")) == ("failed", "no-known-good")


def test_seeding_the_state_with_a_passing_verify_only_run_makes_rollback_real(droplet):
    """The workflow's baseline step: verify what is running, then deploy."""
    rc, out = droplet.run(sha(droplet, "B"), "--skip-deploy")
    assert rc == 0, out
    assert droplet.recorded() == sha(droplet, "A")          # the running commit became the rollback target

    droplet.mark_bad("B")
    rc, out = droplet.run(sha(droplet, "B"))

    assert rc == 1
    assert "redeploying last known-good commit %s" % sha(droplet, "A") in out
    assert "DEPLOY FAILED, ROLLED BACK SUCCESSFULLY" in out
    assert droplet.running() == sha(droplet, "A")          # production is back on A, verified
    assert _git(droplet.app, "rev-parse", "HEAD") == sha(droplet, "A")
    assert dw.classify_log(out, rc, sha(droplet, "B")) == ("rolled_back", "succeeded")


def test_a_failed_rollback_is_reported_as_critical(droplet):
    assert droplet.run(sha(droplet, "B"), "--skip-deploy")[0] == 0
    droplet.mark_bad("A", "B")                                # the known-good commit stops being healthy too
    rc, out = droplet.run(sha(droplet, "B"))

    assert rc == 1 and "CRITICAL" in out
    assert dw.classify_log(out, rc, sha(droplet, "B")) == ("rollback_failed", "failed")


def test_when_production_is_unhealthy_before_the_deploy_there_is_no_baseline(droplet):
    droplet.mark_bad("A")
    rc, _ = droplet.run(sha(droplet, "B"), "--skip-deploy")

    assert rc == 1 and droplet.recorded() is None             # the workflow reports "no known-good baseline"


def test_verify_only_never_touches_the_droplet(droplet):
    before = droplet.running()
    rc, out = droplet.run(sha(droplet, "C"), "--skip-deploy")

    assert rc == 0, out
    assert droplet.running() == before
    assert _git(droplet.app, "rev-parse", "HEAD") == sha(droplet, "A")
    assert not any(call.startswith("docker compose") for call in droplet.docker_calls())


def test_verify_only_checks_what_is_running_not_the_requested_commit(droplet):
    """--skip-deploy ignores its <ref> argument: a dry run proves the running
    deployment, not the requested commit."""
    rc, out = droplet.run(sha(droplet, "C"), "--skip-deploy")

    assert rc == 0
    assert "DEPLOY VERIFIED: commit %s is running" % sha(droplet, "A") in out
    assert sha(droplet, "C") not in out.replace("DEPLOY VERIFIED", "")


def test_a_branch_named_like_the_sha_would_win_over_the_sha(droplet):
    """Why the pre-flight refuses such a branch: the script resolves origin/<ref>
    before the bare ref, so it would deploy the branch tip, not the checked commit."""
    work = droplet.tmp / "work"
    victim = sha(droplet, "B")
    _git(work, "push", "-q", str(droplet.tmp / "origin.git"), "%s:refs/heads/%s" % (sha(droplet, "C"), victim))

    rc, out = droplet.run(victim)

    assert rc == 0
    assert droplet.running() == sha(droplet, "C")
    assert dw.classify_log(out, rc, victim)[0] == "contradiction"   # the workflow still fails the run


def test_droplet_output_never_survives_the_log_filter(droplet):
    rc, out = droplet.run(sha(droplet, "B"))

    assert rc == 0
    assert "hunter2-SECRET" in out                            # the raw output does contain compose's line
    shown = []
    dw.filter_stream(out.splitlines(), shown.append)
    assert not any("hunter2-SECRET" in line for line in shown)
    assert any(line.startswith("DEPLOY VERIFIED") for line in shown)
    assert any(line.startswith("OK: ") for line in shown)


def test_the_deploy_script_itself_is_the_committed_one():
    """The wrapper must not change verification logic: these markers are what
    the workflow's classifier and the runbook depend on."""
    text = SCRIPT.read_text(encoding="utf-8")
    for marker in ("docker compose up -d --force-recreate server", "docker compose rm -f database-bootstrap schema-deploy database-acl",
                   "DEPLOY VERIFIED: commit", "ROLLED BACK SUCCESSFULLY", "nothing to roll back to"):
        assert marker in text
