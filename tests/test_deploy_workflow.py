"""The production deploy workflow and its pre-flight helpers.

Nothing here talks to production, to GitHub or to a droplet. The workflow file
is checked statically, the pre-flight logic is exercised with a fake GitHub API
and a real throwaway git repository, and the ssh material is written into a
temporary directory.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
MODULE_PATH = ROOT / "scripts" / "deploy_workflow.py"

spec = importlib.util.spec_from_file_location("deploy_workflow_under_test", MODULE_PATH)
dw = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = dw
spec.loader.exec_module(dw)

GOOD_SHA = "a" * 40
OTHER_SHA = "b" * 40


def load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def all_steps(workflow: dict):
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            yield job_name, step


# ---------------------------------------------------------------------------
# The workflow file
# ---------------------------------------------------------------------------
def test_triggers_only_on_manual_dispatch_with_the_two_inputs():
    workflow = load_workflow()
    triggers = workflow.get(True, workflow.get("on"))  # PyYAML reads a bare `on` as True

    assert list(triggers) == ["workflow_dispatch"]
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"ref", "dry_run"}
    assert inputs["ref"]["required"] is True
    assert inputs["ref"]["type"] == "string"
    assert inputs["dry_run"]["type"] == "boolean"
    assert inputs["dry_run"]["default"] is True


def test_no_expression_reaches_a_shell_body():
    """Untrusted input must be passed through env:, never interpolated."""
    offenders = [
        (job, step.get("name"))
        for job, step in all_steps(load_workflow())
        if "${{" in step.get("run", "")
    ]
    assert offenders == []
    assert not re.search(r"\$\{\{\s*(github\.event\.)?inputs\.", "\n".join(
        step.get("run", "") for _, step in all_steps(load_workflow())
    ))


def test_secrets_are_referenced_only_by_the_one_step_in_the_deploy_job():
    workflow = load_workflow()
    text = WORKFLOW.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))

    assert re.findall(r"secrets\.([A-Za-z0-9_]+)", code) == ["DROPLET_DEPLOY_KEY", "DROPLET_KNOWN_HOSTS"]
    assert "secrets." not in json.dumps({k: v for k, v in workflow.items() if k != "jobs"})
    assert "secrets." not in json.dumps(workflow["jobs"]["preflight"])
    assert "secrets." not in json.dumps(workflow["jobs"]["deploy"].get("env", {}))
    holders = [s.get("id") for job, s in all_steps(workflow) if "secrets." in json.dumps(s)]
    assert holders == ["ssh_setup"]
    assert "DROPLET_SSH_KEY" not in text  # the read-only log-scan key is never reused


def test_only_the_deploy_job_uses_the_protected_environment():
    jobs = load_workflow()["jobs"]

    assert jobs["deploy"]["environment"]["name"] == "production"
    assert "environment" not in jobs["preflight"]
    assert jobs["deploy"]["needs"] == "preflight"


def test_concurrency_timeouts_and_least_privilege_permissions():
    workflow = load_workflow()

    assert workflow["concurrency"] == {"group": "production-deploy", "cancel-in-progress": False}
    assert workflow["permissions"] == {"contents": "read"}
    for name, job in workflow["jobs"].items():
        assert isinstance(job["timeout-minutes"], int) and 0 < job["timeout-minutes"] <= 90, name
        assert set(job["permissions"].values()) == {"read"}, name
        assert set(job["permissions"]) <= {"contents", "checks", "actions"}, name


def test_ssh_is_strict_pinned_and_never_traced():
    text = WORKFLOW.read_text(encoding="utf-8")
    script = MODULE_PATH.read_text(encoding="utf-8")

    for source in (text, script):
        assert "StrictHostKeyChecking no" not in source
        assert "StrictHostKeyChecking=no" not in source
        assert "ssh-keyscan" not in re.sub(r"#.*", "", source)
        assert "set -x" not in source
        assert "xtrace" not in source
    assert "StrictHostKeyChecking yes" in dw.render_ssh_config("/tmp/x")
    assert "UserKnownHostsFile" in dw.render_ssh_config("/tmp/x")
    assert "--logs" not in text  # post_deploy_verify --logs uses StrictHostKeyChecking=no


def test_the_key_is_removed_by_an_always_step():
    steps = list(load_workflow()["jobs"]["deploy"]["steps"])
    last = steps[-1]

    assert last["if"] == "always()"
    assert "deploy-ssh" in last["run"] and "rm -rf" in last["run"]


def test_deploy_verified_is_wrapped_with_skip_deploy_only_in_dry_run():
    steps = {s.get("id"): s for _, s in all_steps(load_workflow())}
    dry, baseline, deploy = steps["dry"], steps["baseline"], steps["deploy"]

    assert dry["if"] == "steps.gate.outputs.mode == 'dry-run'"
    assert "scripts/deploy_verified.sh" in dry["run"] and "--skip-deploy" in dry["run"]
    assert baseline["if"] == "steps.gate.outputs.mode == 'deploy'"
    assert "--skip-deploy" in baseline["run"]
    assert deploy["if"] == "steps.gate.outputs.mode == 'deploy'"
    assert "--skip-deploy" not in deploy["run"]
    assert deploy["env"]["AUTO_ROLLBACK"] == "1"
    assert "steps.gate.outputs.sha" in deploy["env"]["DEPLOY_SHA"]
    assert steps["post"]["run"] == "python3 scripts/post_deploy_verify.py --json"
    assert steps["post"]["if"] == "steps.gate.outputs.mode == 'deploy'"


def test_actions_are_pinned_to_a_full_commit_sha():
    for _, step in all_steps(load_workflow()):
        if "uses" in step:
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", step["uses"]), step["uses"]


def test_both_jobs_run_the_preflight_and_only_from_main():
    workflow = load_workflow()
    runs = [s["run"] for _, s in all_steps(workflow) if "preflight" in s.get("run", "")]

    assert len(runs) == 2
    for run in runs:
        assert "--require-branch main" in run and "--check-environment production" in run


def test_required_checks_match_ci_yml_job_for_job():
    ci = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    names = set()
    for job in ci["jobs"].values():
        template = job["name"]
        matrix = job.get("strategy", {}).get("matrix", {})
        if "${{ matrix." in template:
            key = re.search(r"\$\{\{\s*matrix\.(\w+)\s*\}\}", template).group(1)
            for value in matrix[key]:
                names.add(re.sub(r"\$\{\{[^}]*\}\}", value, template))
        else:
            names.add(template)
    assert names == set(dw.REQUIRED_CHECKS)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    ["", "main", "origin/main", "v1.0.0", "abc1234", "A" * 40, "a" * 39, "a" * 41,
     "g" * 40, GOOD_SHA + "\n", " " + GOOD_SHA, GOOD_SHA + " ", GOOD_SHA + ";id", "$(id)" + "a" * 35],
)
def test_ref_that_is_not_a_full_lowercase_sha_is_refused(value):
    assert dw.validate_ref(value)


def test_a_full_lowercase_sha_is_accepted():
    assert dw.validate_ref(GOOD_SHA) is None
    assert dw.validate_ref("0123456789abcdef" * 2 + "01234567") is None


@pytest.mark.parametrize("value,expected", [("true", True), ("false", False), ("", None), ("True", None), ("1", None), ("yes", None)])
def test_dry_run_is_exactly_true_or_false(value, expected):
    assert dw.parse_dry_run(value) is expected


# ---------------------------------------------------------------------------
# CI evidence
# ---------------------------------------------------------------------------
def run(name, conclusion="success", status="completed", run_id=1, app="github-actions"):
    return {"id": run_id, "name": name, "status": status, "conclusion": conclusion, "app": {"slug": app}}


def all_green():
    return [run(name, run_id=i + 1) for i, name in enumerate(dw.REQUIRED_CHECKS)]


def test_all_required_checks_green_passes():
    assert dw.evaluate_checks(all_green()) == []


def test_a_missing_required_check_is_refused():
    runs = [r for r in all_green() if r["name"] != "SAST (bandit)"]
    problems = dw.evaluate_checks(runs)
    assert len(problems) == 1 and "SAST (bandit)" in problems[0]


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "skipped", "neutral", "timed_out", None])
def test_a_check_that_did_not_succeed_is_refused(conclusion):
    runs = all_green()
    runs[3] = run(dw.REQUIRED_CHECKS[3], conclusion=conclusion, run_id=99)
    assert dw.evaluate_checks(runs)


def test_a_check_that_is_still_running_is_refused():
    runs = all_green()
    runs[0] = run(dw.REQUIRED_CHECKS[0], status="in_progress", conclusion=None, run_id=99)
    problems = dw.evaluate_checks(runs)
    assert problems and "not finished" in problems[0]


def test_the_newest_run_of_a_check_decides():
    name = dw.REQUIRED_CHECKS[1]
    reran_green = [r for r in all_green() if r["name"] != name] + [
        run(name, "failure", run_id=5), run(name, "success", run_id=50)]
    reran_red = [r for r in all_green() if r["name"] != name] + [
        run(name, "success", run_id=5), run(name, "failure", run_id=50)]

    assert dw.evaluate_checks(reran_green) == []
    assert dw.evaluate_checks(reran_red)


def test_a_check_published_by_another_app_does_not_count():
    runs = [run(n, app="some-other-app", run_id=i + 1) for i, n in enumerate(dw.REQUIRED_CHECKS)]
    assert len(dw.evaluate_checks(runs)) == len(dw.REQUIRED_CHECKS)


# ---------------------------------------------------------------------------
# Fake GitHub API
# ---------------------------------------------------------------------------
class FakeResponse(io.BytesIO):
    def __init__(self, payload, status=200):
        super().__init__(json.dumps(payload).encode())
        self.status = status
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(url, code, message="nope", headers=None):
    body = io.BytesIO(json.dumps({"message": message}).encode())
    return urllib.error.HTTPError(url, code, message, headers or {}, body)


class FakeGitHub:
    """Answers the three endpoints the pre-flight uses."""

    def __init__(self, runs=None, shadow=None, environment=None, checks_error=None):
        self.runs = all_green() if runs is None else runs
        self.shadow = shadow or []
        self.environment = environment
        self.checks_error = checks_error
        self.requests = []

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.requests.append(url)
        assert request.headers["Authorization"] == "Bearer test-token"
        if "/check-runs" in url:
            if self.checks_error:
                raise http_error(url, self.checks_error)
            page = int(re.search(r"[?&]page=(\d+)", url).group(1))
            chunk = self.runs[(page - 1) * 100: page * 100]
            return FakeResponse({"total_count": len(self.runs), "check_runs": chunk})
        if "/git/matching-refs/heads/" in url:
            return FakeResponse(self.shadow)
        if "/environments/" in url:
            if isinstance(self.environment, int):
                raise http_error(url, self.environment)
            return FakeResponse(self.environment)
        raise AssertionError("unexpected request " + url)


def protected_environment(reviewers=1, branch_policy=True):
    rules = [{"type": "branch_policy"}]
    if reviewers is not None:
        rules.append({"type": "required_reviewers", "reviewers": [{"type": "User"}] * reviewers})
    return {
        "name": "production",
        "protection_rules": rules,
        "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True} if branch_policy else None,
    }


def test_pagination_collects_every_page():
    runs = [run("n%d" % i, run_id=i + 1) for i in range(230)]
    fetched, problem = dw.fetch_check_runs("o/r", GOOD_SHA, "test-token", "https://api.example.test", FakeGitHub(runs=runs))
    assert problem == "" and len(fetched) == 230


def test_a_checks_api_error_is_a_refusal_not_a_pass():
    fetched, problem = dw.fetch_check_runs("o/r", GOOD_SHA, "test-token", "https://api.example.test", FakeGitHub(checks_error=403))
    assert fetched is None and "403" in problem


def test_a_non_https_api_url_is_refused():
    assert dw.api_get("http://api.example.test/x", "t").status == 0


def test_a_transport_failure_never_raises():
    def boom(request, timeout=None):
        raise TimeoutError("timed out")
    assert dw.api_get("https://api.example.test/x", "t", boom).status == 0


# ---------------------------------------------------------------------------
# Ancestry, against a real throwaway repository
# ---------------------------------------------------------------------------
def git_in(path, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.test"}
    result = subprocess.run(["git", *args], cwd=path, env=env, capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture()
def repo(tmp_path):
    """main = A -> B (origin/main points at B); side = A -> C, not on main."""
    path = tmp_path / "repo"
    path.mkdir()
    git_in(path, "init", "-q", "-b", "main")
    commits = {}
    for name in ("A", "B"):
        (path / "f.txt").write_text(name)
        git_in(path, "add", "f.txt")
        git_in(path, "commit", "-q", "-m", name)
        commits[name] = git_in(path, "rev-parse", "HEAD")
    git_in(path, "update-ref", "refs/remotes/origin/main", commits["B"])
    git_in(path, "checkout", "-q", "-b", "side", commits["A"])
    (path / "f.txt").write_text("C")
    git_in(path, "commit", "-q", "-am", "C")
    commits["C"] = git_in(path, "rev-parse", "HEAD")
    git_in(path, "checkout", "-q", "main")
    return path, commits


def test_a_commit_on_main_is_an_ancestor(repo):
    path, commits = repo
    for name in ("A", "B"):
        assert dw.check_ancestry(commits[name], "origin/main", runner=lambda a, **k: subprocess.run(a, cwd=path, **k)) == []


def test_a_commit_off_main_is_refused(repo):
    path, commits = repo
    problems = dw.check_ancestry(commits["C"], "origin/main", runner=lambda a, **k: subprocess.run(a, cwd=path, **k))
    assert problems and "not an ancestor" in problems[0]


def test_a_commit_that_does_not_exist_is_refused(repo):
    path, _ = repo
    problems = dw.check_ancestry("f" * 40, "origin/main", runner=lambda a, **k: subprocess.run(a, cwd=path, **k))
    assert problems and "not present" in problems[0]


def test_a_missing_origin_main_is_refused_not_assumed(repo):
    path, commits = repo
    git_in(path, "update-ref", "-d", "refs/remotes/origin/main")
    problems = dw.check_ancestry(commits["A"], "origin/main", runner=lambda a, **k: subprocess.run(a, cwd=path, **k))
    assert problems and "cannot resolve" in problems[0]


# ---------------------------------------------------------------------------
# The whole pre-flight
# ---------------------------------------------------------------------------
@pytest.fixture()
def preflight_env(repo, tmp_path, monkeypatch):
    path, commits = repo
    monkeypatch.chdir(path)
    out = tmp_path / "github_output"
    summary = tmp_path / "github_summary"
    env = {
        "DEPLOY_REF": commits["A"],
        "DEPLOY_DRY_RUN": "true",
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_TOKEN": "test-token",
        "GITHUB_API_URL": "https://api.example.test",
        "GITHUB_OUTPUT": str(out),
        "GITHUB_STEP_SUMMARY": str(summary),
    }
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    return env, commits, out


def preflight(env, api, **flags):
    args = SimpleNamespace(check_environment=flags.get("environment", ""), require_branch=flags.get("branch", "main"))
    lines = []
    code = dw.run_preflight(env, args, opener=api, out=lines.append)
    return code, "\n".join(lines)


def test_a_valid_request_passes_and_publishes_the_sha_and_mode(preflight_env):
    env, commits, out = preflight_env
    code, text = preflight(env, FakeGitHub())

    assert code == 0 and "PRE-FLIGHT OK" in text
    assert out.read_text().splitlines() == ["sha=%s" % commits["A"], "mode=dry-run"]


def test_a_real_deploy_request_publishes_deploy_mode(preflight_env):
    env, commits, out = preflight_env
    env["DEPLOY_DRY_RUN"] = "false"
    code, _ = preflight(env, FakeGitHub())

    assert code == 0 and out.read_text().splitlines()[1] == "mode=deploy"


@pytest.mark.parametrize("bad", ["main", "abc123", "A" * 40, "a" * 41, "$(id)"])
def test_a_ref_that_is_not_a_full_sha_is_refused_and_nothing_is_published(preflight_env, bad):
    env, _, out = preflight_env
    env["DEPLOY_REF"] = bad
    api = FakeGitHub()
    code, text = preflight(env, api)

    assert code == 1 and "PRE-FLIGHT REFUSED" in text
    assert not out.exists() and api.requests == []  # refused before any API call


def test_a_commit_not_on_main_is_refused(preflight_env):
    env, commits, out = preflight_env
    env["DEPLOY_REF"] = commits["C"]
    code, text = preflight(env, FakeGitHub())

    assert code == 1 and "not an ancestor" in text and not out.exists()


def test_a_commit_without_a_green_required_ci_run_is_refused(preflight_env):
    env, _, out = preflight_env
    runs = all_green()
    runs[2] = run(dw.REQUIRED_CHECKS[2], "failure", run_id=77)
    code, text = preflight(env, FakeGitHub(runs=runs))

    assert code == 1 and dw.REQUIRED_CHECKS[2] in text and "11 of 12" in open(env["GITHUB_STEP_SUMMARY"]).read()
    assert not out.exists()


def test_a_commit_with_no_ci_at_all_is_refused(preflight_env):
    env, _, _ = preflight_env
    code, text = preflight(env, FakeGitHub(runs=[]))
    assert code == 1 and text.count("no CI check named") == len(dw.REQUIRED_CHECKS)


def test_dispatch_from_a_branch_other_than_main_is_refused(preflight_env):
    env, _, _ = preflight_env
    env["GITHUB_REF"] = "refs/heads/feature"
    code, text = preflight(env, FakeGitHub())
    assert code == 1 and "must be dispatched from main" in text


def test_an_ambiguous_dry_run_value_is_refused(preflight_env):
    env, _, _ = preflight_env
    env["DEPLOY_DRY_RUN"] = ""
    code, text = preflight(env, FakeGitHub())
    assert code == 1 and "dry_run must be exactly" in text


def test_a_branch_named_like_the_sha_is_refused(preflight_env):
    env, commits, _ = preflight_env
    code, text = preflight(env, FakeGitHub(shadow=[{"ref": "refs/heads/" + commits["A"]}]))
    assert code == 1 and "branch whose name starts with the SHA" in text


def test_the_checks_api_failing_is_a_refusal(preflight_env):
    env, _, _ = preflight_env
    code, text = preflight(env, FakeGitHub(checks_error=500))
    assert code == 1 and "checks API returned HTTP 500" in text


def test_the_token_never_appears_in_output_or_summary(preflight_env):
    env, _, _ = preflight_env
    env["DEPLOY_REF"] = "main"
    _, text = preflight(env, FakeGitHub())
    assert "test-token" not in text and "test-token" not in open(env["GITHUB_STEP_SUMMARY"]).read()


# --- environment protection --------------------------------------------------
def test_an_environment_with_reviewers_and_a_branch_policy_passes(preflight_env):
    env, _, out = preflight_env
    code, text = preflight(env, FakeGitHub(environment=protected_environment()), environment="production")
    assert code == 0 and "environment: verified" in text and out.exists()


def test_an_environment_without_required_reviewers_is_refused(preflight_env):
    env, _, out = preflight_env
    code, text = preflight(env, FakeGitHub(environment=protected_environment(reviewers=None)), environment="production")
    assert code == 1 and "no required reviewers" in text and not out.exists()


def test_an_environment_with_an_empty_reviewer_list_is_refused(preflight_env):
    env, _, _ = preflight_env
    code, text = preflight(env, FakeGitHub(environment=protected_environment(reviewers=0)), environment="production")
    assert code == 1 and "no required reviewers" in text


def test_an_environment_open_to_every_branch_is_refused(preflight_env):
    env, _, _ = preflight_env
    code, text = preflight(env, FakeGitHub(environment=protected_environment(branch_policy=False)), environment="production")
    assert code == 1 and "any branch" in text


def test_a_missing_environment_is_refused(preflight_env):
    env, _, _ = preflight_env
    code, text = preflight(env, FakeGitHub(environment=404), environment="production")
    assert code == 1 and "does not exist" in text


def test_an_unreadable_environment_warns_and_relies_on_the_setup_step(preflight_env):
    """If the token cannot read environment settings the check cannot be made;
    the run continues and says so in an annotation and in the summary."""
    env, _, out = preflight_env
    code, text = preflight(env, FakeGitHub(environment=403), environment="production")

    assert code == 0 and out.exists()
    assert "::warning" in text and "NOT CHECKED" in open(env["GITHUB_STEP_SUMMARY"]).read()


def test_evaluate_environment_reports_reviewer_count():
    state, detail = dw.evaluate_environment(dw.ApiResponse(200, protected_environment(reviewers=2), {}), "production")
    assert state == "ok" and "required reviewers: 2" in detail


# ---------------------------------------------------------------------------
# SSH material
# ---------------------------------------------------------------------------
SECRET_MARKER = "DO-NOT-PRINT-THIS-KEY-BODY"
# Built from parts so that no source line looks like a committed private key to
# the repository's secret scanner.
PEM_BEGIN = "-----BEGIN OPENSSH" + " PRIVATE KEY-----"
PEM_END = "-----END OPENSSH" + " PRIVATE KEY-----"
FAKE_KEY = "\n".join([PEM_BEGIN, SECRET_MARKER, PEM_END])
HOST = "134.122.105.56"
KNOWN = "%s ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleExampleExampleExampleExampleExample1" % HOST


def keygen_ok(*a, **k):
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def keygen_bad(*a, **k):
    return SimpleNamespace(returncode=1, stdout="", stderr="invalid format")


def test_ssh_material_is_written_pinned_and_private(tmp_path):
    target = tmp_path / "ssh"
    problems = dw.setup_ssh(str(target), HOST, "root", FAKE_KEY, KNOWN, real_ssh="/usr/bin/ssh", keygen=keygen_ok)

    assert problems == []
    config = (target / "config").read_text()
    assert "StrictHostKeyChecking yes" in config and "IdentitiesOnly yes" in config
    assert str(target) in config and "UpdateHostKeys no" in config and "ForwardAgent no" in config
    assert (target / "known_hosts").read_text().strip() == KNOWN
    assert (target / "id_deploy").read_text().endswith("KEY-----\n")
    wrapper = (target / "bin" / "ssh").read_text()
    assert wrapper.startswith("#!/bin/sh") and "/usr/bin/ssh" in wrapper and "-F" in wrapper
    if os.name == "posix":
        assert (target / "id_deploy").stat().st_mode & 0o777 == 0o600
        assert (target / "known_hosts").stat().st_mode & 0o777 == 0o600
        assert target.stat().st_mode & 0o777 == 0o700


def test_crlf_and_missing_trailing_newline_in_the_secret_are_normalised(tmp_path):
    key = FAKE_KEY.replace("\n", "\r\n")
    assert dw.setup_ssh(str(tmp_path / "s"), HOST, "root", key, KNOWN, real_ssh="/usr/bin/ssh", keygen=keygen_ok) == []
    text = (tmp_path / "s" / "id_deploy").read_bytes()
    assert b"\r" not in text and text.endswith(b"\n")


@pytest.mark.parametrize(
    "key",
    ["", "   \n", "not a key", "\n".join([PEM_BEGIN, "ENCRYPTED", PEM_END])],
)
def test_a_missing_or_unusable_key_is_refused(tmp_path, key):
    problems = dw.setup_ssh(str(tmp_path / "s"), HOST, "root", key, KNOWN, real_ssh="/usr/bin/ssh", keygen=keygen_ok)
    assert problems and not (tmp_path / "s").exists()


def test_a_key_that_ssh_keygen_cannot_parse_is_refused_and_removed(tmp_path):
    if not shutil.which("ssh-keygen"):
        pytest.skip("ssh-keygen not installed")
    problems = dw.setup_ssh(str(tmp_path / "s"), HOST, "root", FAKE_KEY, KNOWN, real_ssh="/usr/bin/ssh")
    assert problems and "could not be parsed" in problems[0] and not (tmp_path / "s").exists()


@pytest.mark.parametrize(
    "known",
    [
        "",
        "# only a comment",
        "1.2.3.4 ssh-ed25519 AAAAexample",                              # a different host
        "|1|abcd=|efgh= ssh-ed25519 AAAAexample",                       # hashed entry
        "@cert-authority %s ssh-ed25519 AAAAexample" % HOST,             # CA marker
        "%s ssh-ed25519" % HOST,                                         # no key
        "%s not-a-key-type AAAAexample" % HOST,
        KNOWN + "\n1.2.3.4 ssh-ed25519 AAAAexample",                    # one good, one foreign
    ],
)
def test_the_pinned_host_key_must_be_plain_and_for_this_host_only(tmp_path, known):
    problems = dw.setup_ssh(str(tmp_path / "s"), HOST, "root", FAKE_KEY, known, real_ssh="/usr/bin/ssh", keygen=keygen_ok)
    assert problems and not (tmp_path / "s").exists()


def test_secrets_are_never_printed_by_the_setup_command(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DROPLET_DEPLOY_KEY", FAKE_KEY)
    monkeypatch.setenv("DROPLET_KNOWN_HOSTS", KNOWN)
    monkeypatch.setattr(dw.shutil, "which", lambda name: "/usr/bin/" + name if name != "ssh-keygen" else None)
    code = dw.main(["setup-ssh", "--dir", str(tmp_path / "s"), "--host", HOST])
    captured = capsys.readouterr()

    assert code == 0
    assert SECRET_MARKER not in captured.out + captured.err


def test_a_refused_setup_never_echoes_the_secret(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DROPLET_DEPLOY_KEY", "BEGIN-but-broken " + SECRET_MARKER)
    monkeypatch.setenv("DROPLET_KNOWN_HOSTS", KNOWN)
    code = dw.main(["setup-ssh", "--dir", str(tmp_path / "s"), "--host", HOST])
    captured = capsys.readouterr()

    assert code == 1 and SECRET_MARKER not in captured.out + captured.err


@pytest.mark.skipif(shutil.which("ssh") is None or shutil.which("ssh-keygen") is None, reason="needs an OpenSSH client")
def test_openssh_resolves_the_generated_config_to_strict_pinned_identity_only(tmp_path):
    """`ssh -G` prints the effective configuration without connecting anywhere."""
    key_file = tmp_path / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "test", "-f", str(key_file)], check=True)
    target = tmp_path / "ssh"
    problems = dw.setup_ssh(str(target), HOST, "root", key_file.read_text(), KNOWN)
    assert problems == []

    resolved = subprocess.run(
        ["ssh", "-F", str(target / "config"), "-G", "root@" + HOST], capture_output=True, text=True, check=True
    ).stdout.lower().splitlines()
    settings = {}
    for line in resolved:
        key, _, value = line.partition(" ")
        settings.setdefault(key, []).append(value)

    assert settings["stricthostkeychecking"] == ["true"]
    assert settings["identitiesonly"] == ["yes"] or settings["identitiesonly"] == ["true"]
    assert settings["batchmode"] == ["yes"] or settings["batchmode"] == ["true"]
    assert settings["passwordauthentication"] == ["no"] or settings["passwordauthentication"] == ["false"]
    assert settings["forwardagent"] == ["no"] or settings["forwardagent"] == ["false"]
    assert settings["updatehostkeys"] == ["no"] or settings["updatehostkeys"] == ["false"]
    assert len(settings["identityfile"]) == 1 and settings["identityfile"][0].endswith("id_deploy")
    assert len(settings["userknownhostsfile"]) == 1 and settings["userknownhostsfile"][0].endswith("known_hosts")


# ---------------------------------------------------------------------------
# Log handling
# ---------------------------------------------------------------------------
def filtered(lines):
    shown = []
    withheld = dw.filter_stream(lines, shown.append)
    return shown, withheld


def test_only_the_scripts_own_status_lines_pass_the_filter():
    lines = [
        "== deploying %s to root@134.122.105.56:/root/archie-ea" % GOOD_SHA,
        "RESOLVED_COMMIT=" + GOOD_SHA,
        "OK: container reports healthy",
        "/root/archie-ea -> /app",
        "/root/archie-ea -> /appOK: bind mount is present and correct",  # the script omits the newline before OK
        'version endpoint: {"build_id": "aaaaaaaa"}',
        "DEPLOY VERIFIED: commit %s is running, mounted and reachable." % GOOD_SHA,
        "DEPLOY-VERIFY FAIL: container did not report healthy within 900s (last status: unhealthy)",
        "Host key verification failed.",
    ]
    shown, withheld = filtered(lines)
    assert shown == lines and withheld == 0


def test_everything_else_the_droplet_prints_is_withheld():
    lines = [
        "database-acl-1  | postgres://app:hunter2@db:5432/archie",
        "Traceback (most recent call last):",
        "SECRET_KEY=abcdef",
        "::error::injected workflow command",
        "::add-mask::x",
        "   OK: indented lines are not the script's own",
        "",
        "OK: real status line",
    ]
    shown, withheld = filtered(lines)

    assert shown == ["OK: real status line"]
    assert withheld == 6  # the blank line is not counted
    assert not any(line.startswith("::") for line in shown)


def test_the_filter_survives_binary_junk_and_never_raises():
    shown, _ = filtered(["\x00\x01\xff", "OK: fine", None])  # None forces the exception path
    assert shown == ["OK: fine"]


def test_the_filter_drains_its_input_even_if_stdout_is_gone(monkeypatch):
    class Closed:
        def write(self, _):
            raise BrokenPipeError

        def flush(self):
            raise BrokenPipeError

    monkeypatch.setattr(dw.sys, "stdout", Closed())
    monkeypatch.setattr(dw.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"OK: a\nOK: b\nnoise\n")))
    assert dw.cmd_filter_log(None) == 0


VERIFIED_OUT = "== summary\nDEPLOY VERIFIED: commit %s is running, mounted and reachable.\n" % GOOD_SHA


@pytest.mark.parametrize(
    "text,rc,expected",
    [
        (VERIFIED_OUT, 0, ("verified", "not-attempted")),
        (VERIFIED_OUT, 1, ("contradiction", "unknown")),
        ("nothing useful\n", 0, ("contradiction", "unknown")),
        (VERIFIED_OUT.replace(GOOD_SHA, OTHER_SHA), 0, ("contradiction", "unknown")),
        ("== AUTO-ROLLBACK: no different known-good commit on record (x) -- nothing to roll back to\n"
         "DEPLOY NOT VERIFIED — see FAIL lines above.\n", 1, ("failed", "no-known-good")),
        ("== AUTO-ROLLBACK: r (resolved x) failed verification -- redeploying last known-good commit y\n"
         "DEPLOY FAILED, ROLLED BACK SUCCESSFULLY: r did not verify\n", 1, ("rolled_back", "succeeded")),
        ("== AUTO-ROLLBACK: r (resolved x) failed verification -- redeploying last known-good commit y\n"
         "CRITICAL: r did not verify, AND the automatic rollback to y ALSO failed to verify.\n", 1, ("rollback_failed", "failed")),
        ("DEPLOY NOT VERIFIED — see FAIL lines above.\n", 1, ("failed", "not-attempted")),
        ("", 255, ("failed", "not-attempted")),
    ],
)
def test_classification_of_the_scripts_outcome(text, rc, expected):
    assert dw.classify_log(text, rc, GOOD_SHA) == expected


def test_a_droplet_line_cannot_fake_a_verified_result():
    """The success line must start the line; text echoed inside other output does not count."""
    text = "noise: DEPLOY VERIFIED: commit %s is running\n" % GOOD_SHA
    assert dw.classify_log(text, 0, GOOD_SHA)[0] == "contradiction"


# ---------------------------------------------------------------------------
# Job summary
# ---------------------------------------------------------------------------
def summary_env(**overrides):
    base = {
        "SUMMARY_SHA": GOOD_SHA, "SUMMARY_MODE": "deploy", "SUMMARY_BEFORE_SHA": OTHER_SHA,
        "SUMMARY_AFTER_SHA": GOOD_SHA, "SUMMARY_GATE_OUTCOME": "success", "SUMMARY_SSH_OUTCOME": "success",
        "SUMMARY_DRY_OUTCOME": "skipped", "SUMMARY_BASELINE": "passed", "SUMMARY_DEPLOY_OUTCOME": "success",
        "SUMMARY_DEPLOY_RESULT": "verified", "SUMMARY_ROLLBACK": "not-attempted", "SUMMARY_POST_OUTCOME": "success",
        "SUMMARY_RUN_URL": "https://github.com/o/r/actions/runs/1",
    }
    base.update(overrides)
    return base


def test_summary_states_every_required_fact():
    text = dw.render_summary(summary_env())
    for fragment in (GOOD_SHA, OTHER_SHA, "real deploy", "Rollback", "https://github.com/o/r/actions/runs/1",
                     "Deployed and verified"):
        assert fragment in text


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"SUMMARY_MODE": "dry-run", "SUMMARY_DRY_OUTCOME": "success", "SUMMARY_DEPLOY_OUTCOME": "skipped",
          "SUMMARY_DEPLOY_RESULT": "", "SUMMARY_POST_OUTCOME": "skipped", "SUMMARY_BASELINE": ""},
         "Dry run passed"),
        ({"SUMMARY_MODE": "dry-run", "SUMMARY_DRY_OUTCOME": "failure", "SUMMARY_DEPLOY_OUTCOME": "skipped",
          "SUMMARY_DEPLOY_RESULT": ""}, "Dry run failed"),
        ({"SUMMARY_POST_OUTCOME": "failure"}, "public-page check failed. Not reported as success"),
        ({"SUMMARY_DEPLOY_OUTCOME": "failure", "SUMMARY_DEPLOY_RESULT": "rolled_back", "SUMMARY_ROLLBACK": "succeeded",
          "SUMMARY_POST_OUTCOME": "skipped"}, "rolled back"),
        ({"SUMMARY_DEPLOY_OUTCOME": "failure", "SUMMARY_DEPLOY_RESULT": "rollback_failed", "SUMMARY_ROLLBACK": "failed"},
         "CRITICAL"),
        ({"SUMMARY_DEPLOY_OUTCOME": "failure", "SUMMARY_DEPLOY_RESULT": "failed", "SUMMARY_ROLLBACK": "no-known-good",
          "SUMMARY_BASELINE": "failed"}, "No rollback was possible"),
        ({"SUMMARY_GATE_OUTCOME": "failure", "SUMMARY_MODE": ""}, "Refused before any change"),
        ({"SUMMARY_SSH_OUTCOME": "failure", "SUMMARY_DEPLOY_OUTCOME": "skipped"}, "SSH setup or the connection to the droplet failed"),
    ],
)
def test_summary_verdicts(overrides, expected):
    assert expected in dw.render_summary(summary_env(**overrides))


def test_summary_never_renders_unvalidated_text():
    text = dw.render_summary(summary_env(SUMMARY_SHA="<script>x</script>", SUMMARY_BEFORE_SHA="; rm -rf /",
                                          SUMMARY_RUN_URL="javascript:alert(1)"))
    assert "<script>" not in text and "rm -rf" not in text and "javascript:" not in text
