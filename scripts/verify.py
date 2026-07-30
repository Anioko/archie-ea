#!/usr/bin/env python
"""Archie verification runner — one command, every gate.

    python scripts/verify.py                # run every gate that can run here
    python scripts/verify.py --json         # machine-readable result
    python scripts/verify.py --gate compile # run one gate
    python scripts/verify.py --require-db   # turn DB-dependent SKIPs into failures (CI)
    python scripts/verify.py --update-baseline   # re-measure ratchets (see below)

Why this exists
---------------
``app/templates/macros/ZERO_TOLERANCE_PROTOCOL.md`` asks every agent to verify its
work against a mandatory protocol. A protocol document cannot enforce itself: at
the time this runner was written the repository had 8 test files and a CI lint step
reading ``ruff check . || true`` inside ``continue-on-error: true``. This script is
the executable form of that protocol — the thing you can actually run, and that CI
can actually fail on.

Gate kinds
----------
``zero``     the measurement must be exactly 0. Used only where the tree is
             already clean, so the gate can never be satisfied by regression.
``ratchet``  the measurement must not exceed a recorded baseline. This is how a
             tree with 4482 known lint findings and 1255 known token violations
             gets a meaningful gate today instead of after a multi-month cleanup:
             the number is allowed to fall, never to rise.
``command``  a subprocess that must exit 0.

Ratchets are stored in ``verification_baseline.json``. Lowering a baseline is
routine — run ``--update-baseline`` after a cleanup. *Raising* one is a deliberate
act that shows up in review as a changed number, which is the point.

Skips are loud
--------------
A gate that cannot run reports SKIP with a reason and is listed in the summary. It
never counts as a pass. CI passes ``--require-db`` so that a missing database
fails the build rather than quietly shrinking the gate set.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / "verification_baseline.json"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


@dataclass
class Result:
    name: str
    status: str
    detail: str = ""
    measured: int | None = None
    baseline: int | None = None
    duration_s: float = 0.0
    remediation: str = ""


@dataclass
class Gate:
    name: str
    description: str
    kind: str                      # zero | ratchet | command
    runner: object
    needs_db: bool = False
    remediation: str = ""
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- helpers


def _run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    """Run *cmd* capturing output, decoding defensively.

    ``text=True`` alone decodes the child's output with the *parent's* locale
    encoding — cp1252 on a default Windows console — regardless of the child's
    PYTHONIOENCODING. Several commands here print non-cp1252 characters (the check
    marks in ``manage.py init_db``, for one), which raised UnicodeDecodeError inside
    subprocess's reader thread and left ``proc.stdout`` as None. Pinning utf-8 with
    errors="replace" makes a gate's *output* incapable of breaking the gate.
    """
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    # Normalise so callers can concatenate without a None check.
    proc.stdout = proc.stdout or ""
    proc.stderr = proc.stderr or ""
    return proc


def _ruff_count(select: str | None = None) -> tuple[int, str]:
    """Count ruff findings under the repo's pinned ruff.toml."""
    cmd = [sys.executable, "-m", "ruff", "check", ".", "--output-format", "concise"]
    if select:
        cmd += ["--select", select]
    proc = _run(cmd)
    if "error:" in proc.stderr.lower() and "Rule" in proc.stderr:
        raise RuntimeError(f"ruff rejected the selection: {proc.stderr.strip()[:200]}")
    lines = [ln for ln in proc.stdout.splitlines() if re.search(r":\d+:\d+:", ln)]
    sample = "\n".join(f"    {ln}" for ln in lines[:5])
    return len(lines), sample


def database_available() -> tuple[bool, str]:
    """TCP-probe the configured database. Cheap and dependency-free."""
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if not url:
        return False, "neither TEST_DATABASE_URL nor DATABASE_URL is set"
    try:
        parsed = urlparse(url)
        host, port = parsed.hostname or "127.0.0.1", parsed.port or 5432
    except Exception as exc:  # noqa: BLE001
        return False, f"could not parse database URL: {exc}"
    sock = socket.socket()
    sock.settimeout(2.0)
    try:
        sock.connect((host, port))
        return True, f"{host}:{port} reachable"
    except OSError as exc:
        return False, f"{host}:{port} unreachable ({exc.__class__.__name__})"
    finally:
        sock.close()


# ---------------------------------------------------------------- gate runners


def gate_compile() -> Result:
    """The honest Python equivalent of a compile step: bytecode-compile everything.

    This is the strongest *ahead-of-time* guarantee the language offers. It proves
    every module is syntactically valid; it cannot prove a name exists (see the
    undefined-names gate) or that a template endpoint resolves (see boot-health).
    """
    proc = _run([sys.executable, "-m", "compileall", "-q", "app", "config.py", "manage.py", "create_admin.py"])
    if proc.returncode == 0:
        return Result("compile", PASS, "all modules compile")
    return Result("compile", FAIL, (proc.stdout + proc.stderr).strip()[:2000])


def gate_undefined_names(baseline: int) -> Result:
    """Ruff F821 — compiler-grade name resolution.

    This is the closest thing to a compiler's symbol check available for Python,
    and it finds real defects: at the time of writing, 296 findings across 68
    files, including a module using ``datetime`` it never imports (a guaranteed
    NameError when that endpoint is called).
    """
    count, sample = _ruff_count("F821")
    return Result("undefined-names", PASS if count <= baseline else FAIL, sample, count, baseline)


def gate_redefinitions(baseline: int) -> Result:
    count, sample = _ruff_count("F811")
    return Result("redefinitions", PASS if count <= baseline else FAIL, sample, count, baseline)


def gate_undefined_exports() -> Result:
    """F822 — names in __all__ that do not exist. Already 0; locked at 0."""
    count, sample = _ruff_count("F822")
    return Result("undefined-exports", PASS if count == 0 else FAIL, sample, count, 0)


def gate_lint_core(baseline: int) -> Result:
    """Full pinned correctness set (F, E4, E7, E9) — ratcheted."""
    count, sample = _ruff_count(None)
    return Result("lint-core", PASS if count <= baseline else FAIL, sample, count, baseline)


def gate_design_tokens(baseline: int) -> Result:
    """DESIGN.md's colour-token rule, which nothing enforced before this."""
    proc = _run([sys.executable, "scripts/check_design_tokens.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("design-tokens", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    return Result("design-tokens", PASS if count <= baseline else FAIL, "", count, baseline)


def gate_air_gap(baseline: int) -> Result:
    """No UI assets loaded from the public internet.

    Archie is being prepared for deployment inside an enterprise network, where
    public CDNs are blocked or proxied. Every external script is a page that breaks
    on a managed workstation. Also a privacy control: each request leaks the
    referring URL and client IP to a third party.
    """
    proc = _run([sys.executable, "scripts/check_external_origins.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("air-gap", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    return Result("air-gap", PASS if count <= baseline else FAIL, "", count, baseline)


def gate_dependency_cves() -> Result:
    """No known CVEs in the production dependency set.

    This is the scan an enterprise security review runs before granting network
    admission, so it is better to run it ourselves first. Scoped to
    requirements.txt deliberately: test tooling is not shipped, so a CVE in pytest
    is not part of the deployed attack surface.
    """
    proc = _run([sys.executable, "-m", "pip_audit", "-r", "requirements.txt",
                 "--progress-spinner", "off"], timeout=600)
    output = (proc.stdout + proc.stderr).strip()
    if "No known vulnerabilities found" in output:
        return Result("dependency-cves", PASS, "no known vulnerabilities", 0, 0)
    if proc.returncode != 0 and ("Failed to install" in output or "internal pip failure" in output):
        # A resolution failure is a real problem, not a scanner hiccup: it means
        # requirements.txt cannot be installed as written.
        return Result("dependency-cves", FAIL,
                      "requirements.txt does not resolve:\n" + output[-1200:],
                      remediation="fix the conflicting pins")
    if "urlopen error" in output or "Temporary failure in name resolution" in output:
        return Result("dependency-cves", SKIP, "no network access to the advisory database")
    rows = [ln for ln in output.splitlines() if re.match(r"^\S+\s+\S+\s+(PYSEC|CVE|GHSA)", ln)]
    return Result("dependency-cves", FAIL if rows else PASS,
                  "\n".join(rows[:15]), len(rows), 0,
                  remediation="bump the affected package; check for a blocking upper bound")


def gate_boot_health() -> Result:
    """Boot + wiring. Database-free by design — see tests/test_boot_health.py."""
    proc = _run([sys.executable, "-m", "pytest", "tests/test_boot_health.py", "-q", "-p", "no:cacheprovider"])
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-15:]
    return Result("boot-health", PASS if proc.returncode == 0 else FAIL, "\n".join(tail))


def gate_schema_drift() -> Result:
    """No column or table drift between the ORM models and the live database.

    ``reconcile-schema`` reports drift in its output, not its exit code, and always
    prints the summary line ``reconcile-schema: N column(s) would add.`` — so the
    count has to be parsed. Matching the phrase alone is a false positive, because
    the summary contains it even when N is 0.
    """
    proc = _run([sys.executable, "-m", "flask", "--app", "manage", "reconcile-schema", "--dry-run"])
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        return Result("schema-drift", FAIL, output[-2000:])

    summary = re.search(r"reconcile-schema:\s+(\d+)\s+column\(s\)", output)
    if not summary:
        # No parseable summary means the check did not actually run to completion.
        # Report that rather than inferring success from the absence of bad news.
        return Result("schema-drift", FAIL,
                      "could not find the 'reconcile-schema: N column(s)' summary line:\n"
                      + output[-1500:])

    drifted_columns = int(summary.group(1))
    absent_tables = 0
    tables = re.search(r"(\d+)\s+table\(s\)\s+absent", output)
    if tables:
        absent_tables = int(tables.group(1))

    if drifted_columns or absent_tables:
        detail_lines = [
            ln for ln in output.splitlines()
            if ln.startswith("  + ") or "table(s) absent" in ln
        ][:20]
        return Result(
            "schema-drift", FAIL,
            f"{drifted_columns} drifted column(s), {absent_tables} absent table(s):\n"
            + "\n".join(detail_lines),
            measured=drifted_columns + absent_tables, baseline=0,
            remediation="run: flask --app manage init-db && flask --app manage reconcile-schema",
        )
    return Result("schema-drift", PASS, "no drift detected", measured=0, baseline=0)


def gate_tests() -> Result:
    proc = _run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                 "--ignore=tests/test_boot_health.py"])
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-20:]
    return Result("tests", PASS if proc.returncode == 0 else FAIL, "\n".join(tail))


# ---------------------------------------------------------------- registry


def build_gates(baseline: dict) -> list[Gate]:
    return [
        Gate("compile", "Every module bytecode-compiles", "command", gate_compile,
             remediation="fix the reported SyntaxError", tags=["static", "fast"]),
        Gate("undefined-exports", "No __all__ entry names a missing symbol", "zero",
             gate_undefined_exports, remediation="remove the stale __all__ entry",
             tags=["static", "fast"]),
        Gate("undefined-names", "No new undefined names (ruff F821)", "ratchet",
             lambda: gate_undefined_names(baseline["undefined_names"]),
             remediation="add the missing import, or fix the typo", tags=["static", "fast"]),
        Gate("redefinitions", "No new redefinitions (ruff F811)", "ratchet",
             lambda: gate_redefinitions(baseline["redefinitions"]),
             remediation="delete the shadowed definition", tags=["static", "fast"]),
        Gate("lint-core", "No new correctness lint findings", "ratchet",
             lambda: gate_lint_core(baseline["lint_core"]),
             remediation="run: python -m ruff check . --fix", tags=["static", "fast"]),
        Gate("design-tokens", "No new raw Tailwind colours (DESIGN.md)", "ratchet",
             lambda: gate_design_tokens(baseline["design_tokens"]),
             remediation="use semantic tokens; see the table in DESIGN.md",
             tags=["static", "ui"]),
        Gate("air-gap", "No UI assets loaded from public CDNs", "ratchet",
             lambda: gate_air_gap(baseline["air_gap"]),
             remediation="vendor the asset into app/static/ and use url_for('static', ...)",
             tags=["static", "ui", "airgap"]),
        Gate("dependency-cves", "No known CVEs in shipped dependencies", "zero",
             gate_dependency_cves,
             remediation="bump the affected package (watch for blocking upper bounds)",
             tags=["deps", "security"]),
        Gate("boot-health", "App boots; every url_for endpoint resolves", "command",
             gate_boot_health,
             remediation="see the failure message in tests/test_boot_health.py",
             tags=["runtime"]),
        Gate("schema-drift", "Live DB matches the ORM models", "command",
             gate_schema_drift, needs_db=True,
             remediation="run: flask --app manage reconcile-schema", tags=["runtime", "db"]),
        Gate("tests", "Test suite passes", "command", gate_tests, needs_db=True,
             remediation="fix the failing test", tags=["runtime", "db"]),
    ]


DEFAULT_BASELINE = {
    "undefined_names": 296,
    "redefinitions": 73,
    "lint_core": 4482,
    "design_tokens": 1255,
    "air_gap": 78,
}


def load_baseline() -> dict:
    if BASELINE_PATH.exists():
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        return {**DEFAULT_BASELINE, **data.get("ratchets", {})}
    return dict(DEFAULT_BASELINE)


def save_baseline(ratchets: dict, note: str) -> None:
    BASELINE_PATH.write_text(
        json.dumps(
            {
                "_comment": (
                    "Ratchet baselines for scripts/verify.py. Lowering a number is routine "
                    "(run --update-baseline after a cleanup). Raising one is a deliberate "
                    "regression and must be justified in review."
                ),
                "_note": note,
                "ratchets": ratchets,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--gate", action="append", help="run only this gate (repeatable)")
    parser.add_argument("--tag", action="append", help="run only gates with this tag")
    parser.add_argument("--require-db", action="store_true",
                        help="fail DB-dependent gates instead of skipping (use in CI)")
    parser.add_argument("--update-baseline", action="store_true",
                        help="re-measure ratchets and write verification_baseline.json")
    args = parser.parse_args(argv)

    os.chdir(REPO_ROOT)
    baseline = load_baseline()
    gates = build_gates(baseline)

    if args.gate:
        wanted = set(args.gate)
        unknown = wanted - {g.name for g in gates}
        if unknown:
            parser.error(f"unknown gate(s): {', '.join(sorted(unknown))}")
        gates = [g for g in gates if g.name in wanted]
    if args.tag:
        gates = [g for g in gates if set(args.tag) & set(g.tags)]

    db_ok, db_reason = database_available()
    results: list[Result] = []

    for gate in gates:
        if gate.needs_db and not db_ok:
            if args.require_db:
                results.append(Result(gate.name, FAIL,
                                      f"database required but unavailable: {db_reason}",
                                      remediation="start PostgreSQL and set TEST_DATABASE_URL"))
            else:
                results.append(Result(gate.name, SKIP, f"no database: {db_reason}",
                                      remediation="start PostgreSQL and set TEST_DATABASE_URL"))
            continue
        started = time.time()
        try:
            result = gate.runner()
        except subprocess.TimeoutExpired:
            result = Result(gate.name, FAIL, "timed out")
        except Exception as exc:  # noqa: BLE001 — a broken gate must report, not crash the run
            result = Result(gate.name, FAIL, f"{exc.__class__.__name__}: {exc}")
        result.duration_s = round(time.time() - started, 1)
        if result.status == FAIL and not result.remediation:
            result.remediation = gate.remediation
        results.append(result)

    if args.update_baseline:
        measured = {r.name.replace("-", "_"): r.measured for r in results if r.measured is not None}
        new = {**baseline, **{k: v for k, v in measured.items() if k in baseline}}
        lowered = {k: (baseline[k], new[k]) for k in new if new[k] < baseline.get(k, new[k])}
        save_baseline(new, f"updated {time.strftime('%Y-%m-%d')}")
        print(f"baseline written to {BASELINE_PATH.name}")
        for key, (old, cur) in lowered.items():
            print(f"  lowered {key}: {old} -> {cur}")
        return 0

    failed = [r for r in results if r.status == FAIL]
    skipped = [r for r in results if r.status == SKIP]

    if args.json:
        print(json.dumps({
            "ok": not failed,
            "database_available": db_ok,
            "database_detail": db_reason,
            "summary": {"pass": len(results) - len(failed) - len(skipped),
                        "fail": len(failed), "skip": len(skipped)},
            "gates": [r.__dict__ for r in results],
        }, indent=2))
        return 1 if failed else 0

    width = max(len(r.name) for r in results) if results else 10
    print("\nArchie verification")
    print("-" * (width + 46))
    for r in results:
        mark = {PASS: "ok  ", FAIL: "FAIL", SKIP: "skip"}[r.status]
        measure = ""
        if r.measured is not None:
            arrow = "<=" if r.status == PASS else ">"
            measure = f"  [{r.measured} {arrow} {r.baseline}]"
        print(f"  {mark}  {r.name:<{width}}  {r.duration_s:>5.1f}s{measure}")
    print("-" * (width + 46))

    for r in failed:
        print(f"\nFAIL: {r.name}")
        if r.detail:
            print("\n".join(f"    {ln}" for ln in r.detail.splitlines()[:20]))
        if r.remediation:
            print(f"    -> {r.remediation}")

    if skipped:
        print(f"\n{len(skipped)} gate(s) skipped and therefore NOT verified:")
        for r in skipped:
            print(f"    {r.name}: {r.detail}")
        print("    CI runs with --require-db so these cannot be silently skipped there.")

    print(f"\n{len(results) - len(failed) - len(skipped)} passed, {len(failed)} failed, {len(skipped)} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
