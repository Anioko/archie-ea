#!/usr/bin/env python3
"""Run every quality gate that can run here. The executable form of the protocol.

CLAUDE.md tells contributors to run this before claiming work is complete, and
documents its flags and its gate table. The file did not exist, so the project's
documented primary gate could not be run at all - which is worse than not having
one, because everyone believes it is being enforced.

    python scripts/verify.py                  # every gate that can run here
    python scripts/verify.py --json           # machine-readable
    python scripts/verify.py --gate lint-core # one gate
    python scripts/verify.py --tag static     # fast static gates only
    python scripts/verify.py --require-db     # fail instead of skipping DB gates (CI)
    python scripts/verify.py --update-baseline

Three outcomes, and the difference matters:

    PASS  the gate ran and was satisfied
    FAIL  the gate ran and was not
    SKIP  the gate could not run (no database, no Node toolchain, tool absent)

A SKIP is never a pass. It is printed in the summary and counted separately so
it cannot be mistaken for one - a gate that quietly skips is how a project ends
up believing it is covered.

Several gates are RATCHETS: they compare a measurement against
verification_baseline.json and fail only when it gets worse. The tree carries
known debt, so the honest gate is "no worse", not "clean". Lowering a baseline
after a cleanup is routine; raising one is a regression that needs justifying.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_PATH = os.path.join(ROOT, "verification_baseline.json")

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


class Result:
    def __init__(self, status, detail="", measured=None, baseline=None):
        self.status = status
        self.detail = detail
        self.measured = measured
        self.baseline = baseline


def _run(cmd, timeout=600):
    """Run a command, returning (returncode, stdout+stderr)."""
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return None, "tool not installed"
    except subprocess.TimeoutExpired:
        return None, "timed out after %ss" % timeout


def _ruff_count(select):
    """How many findings ruff reports for a rule selection."""
    code, out = _run([sys.executable, "-m", "ruff", "check", ".",
                      "--select", select, "--output-format", "concise",
                      "--exclude", "migrations,node_modules,.git"])
    if code is None:
        return None, out
    findings = [ln for ln in out.splitlines() if re.match(r"^[^\s].*:\d+:\d+:", ln)]
    return len(findings), out


def _load_baseline():
    if not os.path.exists(BASELINE_PATH):
        return {}
    with open(BASELINE_PATH, encoding="utf-8") as handle:
        return json.load(handle).get("gates", {})


def _ratchet(name, measured, baseline, unit, output=""):
    """Fail only when a measurement gets worse than its recorded baseline."""
    if measured is None:
        return Result(SKIP, output.strip()[:120] or "could not measure")
    allowed = baseline.get(name)
    if allowed is None:
        return Result(PASS, "%d %s (no baseline recorded yet)" % (measured, unit),
                      measured, None)
    if measured > allowed:
        return Result(FAIL,
                      "%d %s, baseline allows %d — %d new" %
                      (measured, unit, allowed, measured - allowed), measured, allowed)
    note = "%d %s (baseline %d)" % (measured, unit, allowed)
    if measured < allowed:
        note += " — improved, run --update-baseline to lock it in"
    return Result(PASS, note, measured, allowed)


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def gate_compile(baseline):
    """Every module must at least parse. A syntax error is not a style opinion.

    Compiles in memory rather than via compileall. compileall writes a .pyc,
    and on Windows that raises FileNotFoundError for deep paths - reported
    identically to a syntax error. The first version of this gate failed 8
    modules that ast.parse accepts perfectly well, which is precisely the
    false positive CLAUDE.md warns about. Syntax is a property of the source,
    not of whether the filesystem would accept a bytecode file next to it.
    """
    failures = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "app")):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "node_modules")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                source = open(path, encoding="utf-8", errors="replace").read()
                compile(source, path, "exec")
            except SyntaxError as exc:
                failures.append("%s:%s" % (os.path.relpath(path, ROOT), exc.lineno))
    if failures:
        return Result(FAIL, "%d module(s) have syntax errors: %s"
                      % (len(failures), ", ".join(failures[:5])))
    return Result(PASS, "all modules compile")


def gate_undefined_names(baseline):
    """ruff F821 — the closest thing to a compiler catching a NameError."""
    count, out = _ruff_count("F821")
    return _ratchet("undefined-names", count, baseline, "undefined name(s)", out)


def gate_redefinitions(baseline):
    """ruff F811 — a shadowed definition silently discards the earlier one."""
    count, out = _ruff_count("F811")
    return _ratchet("redefinitions", count, baseline, "redefinition(s)", out)


def gate_lint_core(baseline):
    """ruff F,E4,E7,E9 — correctness lint, not style."""
    count, out = _ruff_count("F,E4,E7,E9")
    return _ratchet("lint-core", count, baseline, "finding(s)", out)


def gate_undefined_exports(baseline):
    """__all__ naming a symbol the module does not define.

    An import * then fails at runtime, far from the cause.
    """
    import ast

    offenders = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "app")):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "node_modules")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
            except SyntaxError:
                continue  # gate_compile owns that
            exported, defined = [], set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    defined.add(node.name)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    defined.add(node.id)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        defined.add(alias.asname or alias.name.split(".")[0])
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, (ast.List, ast.Tuple)):
                                exported = [e.value for e in node.value.elts
                                            if isinstance(e, ast.Constant)
                                            and isinstance(e.value, str)]
            missing = [name for name in exported if name not in defined]
            if missing:
                offenders.append("%s: %s" % (os.path.relpath(path, ROOT),
                                             ", ".join(missing[:4])))
    if offenders:
        return Result(FAIL, "%d module(s) export undefined names: %s"
                      % (len(offenders), "; ".join(offenders[:3])))
    return Result(PASS, "no __all__ names a missing symbol")


def gate_design_tokens(baseline):
    """Raw Tailwind colour classes, which DESIGN.md replaces with tokens.

    bg-blue-500 hard-codes a colour that cannot follow the theme; bg-primary
    does. This is the tree's largest known debt, so it is a ratchet.
    """
    pattern = re.compile(
        r"\b(?:bg|text|border|ring|from|to|via)-"
        r"(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|"
        r"emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-"
        r"\d{2,3}\b")
    count = 0
    templates = os.path.join(ROOT, "app", "templates")
    for dirpath, _dirnames, filenames in os.walk(templates):
        for filename in filenames:
            if not filename.endswith(".html"):
                continue
            text = open(os.path.join(dirpath, filename),
                        encoding="utf-8", errors="replace").read()
            count += len(pattern.findall(text))
    return _ratchet("design-tokens", count, baseline, "raw colour use(s)")


def gate_native_dialogs(baseline):
    """alert()/confirm() in templates. Absolute: the count is zero."""
    code, out = _run([sys.executable, "-m", "pytest",
                      "tests/test_no_native_dialogs.py", "-q", "--no-header"], timeout=300)
    if code is None:
        return Result(SKIP, out.strip()[:120])
    return Result(PASS if code == 0 else FAIL,
                  "no native browser dialogs" if code == 0
                  else out.strip().splitlines()[-1][:160])


def gate_sri(baseline):
    """integrity= hashes must match the files they guard.

    A stale hash means the browser silently refuses the script and a feature
    disappears with nothing in the server log.
    """
    test = os.path.join(ROOT, "tests", "test_subresource_integrity.py")
    if not os.path.exists(test):
        return Result(SKIP, "tests/test_subresource_integrity.py not present")
    code, out = _run([sys.executable, "-m", "pytest", test, "-q", "--no-header"], timeout=300)
    if code is None:
        return Result(SKIP, out.strip()[:120])
    return Result(PASS if code == 0 else FAIL,
                  "every integrity hash matches" if code == 0
                  else out.strip().splitlines()[-1][:160])


def gate_boot_health(baseline):
    """The app must build and every url_for target must exist.

    Blueprints register non-fatally, so a broken import silently removes a
    feature - and any template linking to it then 500s every page that renders
    the sidebar.
    """
    if not os.environ.get("TEST_DATABASE_URL") and not os.environ.get("DATABASE_URL"):
        return Result(SKIP, "no TEST_DATABASE_URL/DATABASE_URL — cannot build the app")
    code, out = _run([sys.executable, "-c", (
        "import os;os.environ.setdefault('SECRET_KEY','x'*32);"
        "from app import create_app;a=create_app('testing');"
        "n=len(list(a.url_map.iter_rules()));"
        "print('ROUTES',n);"
        "print('BLUEPRINTS',len(a.blueprints))"
    )], timeout=600)
    if code is None:
        return Result(SKIP, out.strip()[:120])
    if code != 0:
        tail = [ln for ln in out.strip().splitlines() if ln.strip()][-1:] or ["failed"]
        return Result(FAIL, "app did not build: %s" % tail[0][:150])
    routes = re.search(r"ROUTES (\d+)", out)
    blueprints = re.search(r"BLUEPRINTS (\d+)", out)
    measured = int(routes.group(1)) if routes else 0
    allowed = baseline.get("boot-health")
    if allowed and measured < allowed * 0.95:
        return Result(FAIL, "%d routes registered, baseline %d — a blueprint "
                            "failed to import" % (measured, allowed), measured, allowed)
    return Result(PASS, "app builds; %s routes, %s blueprints"
                  % (measured, blueprints.group(1) if blueprints else "?"),
                  measured, allowed)


def gate_schema_drift(baseline):
    """Models versus the live database. Needs a database."""
    if not os.environ.get("TEST_DATABASE_URL") and not os.environ.get("DATABASE_URL"):
        return Result(SKIP, "no database configured")
    code, out = _run([sys.executable, "-m", "flask", "--app", "manage",
                      "reconcile-schema", "--dry-run"], timeout=600)
    if code is None:
        return Result(SKIP, out.strip()[:120])
    if code != 0:
        return Result(FAIL, "reconcile-schema --dry-run failed")
    match = re.search(r"(\d+) column\(s\)", out)
    drift = int(match.group(1)) if match else 0
    if drift:
        return Result(FAIL, "%d column(s) declared by models and missing from the "
                            "database — run flask reconcile-schema" % drift, drift)
    return Result(PASS, "models and database agree", 0)


def gate_tests(baseline):
    """The behavioural suite. Needs a database."""
    if not os.environ.get("TEST_DATABASE_URL"):
        return Result(SKIP, "no TEST_DATABASE_URL — pytest reads that, not DATABASE_URL")
    code, out = _run([sys.executable, "-m", "pytest", "tests/", "-q", "--no-header",
                      "--ignore=tests/smoke", "-p", "no:randomly"], timeout=1800)
    if code is None:
        return Result(SKIP, out.strip()[:120])
    summary = [ln for ln in out.strip().splitlines() if "passed" in ln or "failed" in ln]
    detail = summary[-1].strip()[:150] if summary else "no summary"
    return Result(PASS if code == 0 else FAIL, detail)


GATES = [
    # (name, function, tags)
    ("compile", gate_compile, {"static", "fast"}),
    ("undefined-exports", gate_undefined_exports, {"static", "fast"}),
    ("undefined-names", gate_undefined_names, {"static", "fast"}),
    ("redefinitions", gate_redefinitions, {"static", "fast"}),
    ("lint-core", gate_lint_core, {"static", "fast"}),
    ("design-tokens", gate_design_tokens, {"static", "fast"}),
    ("native-dialogs", gate_native_dialogs, {"static"}),
    ("sri", gate_sri, {"static"}),
    ("boot-health", gate_boot_health, {"runtime"}),
    ("schema-drift", gate_schema_drift, {"runtime", "db"}),
    ("tests", gate_tests, {"runtime", "db"}),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--gate", help="run a single gate by name")
    parser.add_argument("--tag", help="run only gates with this tag (static, fast, runtime, db)")
    parser.add_argument("--require-db", action="store_true",
                        help="treat a skipped database gate as a failure (what CI does)")
    parser.add_argument("--update-baseline", action="store_true",
                        help="record current measurements as the accepted baseline")
    args = parser.parse_args()

    baseline = _load_baseline()
    selected = [g for g in GATES
                if (not args.gate or g[0] == args.gate)
                and (not args.tag or args.tag in g[2])]
    if args.gate and not selected:
        print("No such gate: %s\nAvailable: %s"
              % (args.gate, ", ".join(g[0] for g in GATES)), file=sys.stderr)
        return 2

    results, started = {}, time.time()
    if not args.json:
        print()
    for name, function, _tags in selected:
        if not args.json:
            print("  %-20s running..." % name, end="\r", flush=True)
        try:
            result = function(baseline)
        except Exception as exc:  # noqa: BLE001 — a broken gate must not hide the rest
            result = Result(FAIL, "gate raised %s: %s" % (type(exc).__name__, str(exc)[:100]))
        if result.status == SKIP and args.require_db:
            result = Result(FAIL, "skipped, and --require-db was set: " + result.detail)
        results[name] = result
        if not args.json:
            mark = {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}[result.status]
            print("  %-20s %-4s  %s" % (name, mark, result.detail))

    failed = [n for n, r in results.items() if r.status == FAIL]
    skipped = [n for n, r in results.items() if r.status == SKIP]
    elapsed = round(time.time() - started, 1)

    if args.update_baseline:
        recorded = {n: r.measured for n, r in results.items() if r.measured is not None}
        existing = _load_baseline()
        existing.update(recorded)
        with open(BASELINE_PATH, "w", encoding="utf-8") as handle:
            json.dump({
                "_comment": "Accepted measurements for the ratchet gates in "
                            "scripts/verify.py. Every number here is real debt that "
                            "has not been paid off, not a statement that the tree is "
                            "clean. Lowering one after a cleanup is routine; raising "
                            "one is a regression that needs justifying in review.",
                "gates": existing,
            }, handle, indent=1, sort_keys=True)
            handle.write("\n")
        if not args.json:
            print("\n  baseline written: %d measurement(s)" % len(recorded))

    if args.json:
        print(json.dumps({
            "ok": not failed,
            "elapsed_seconds": elapsed,
            "failed": failed,
            "skipped": skipped,
            "gates": {n: {"status": r.status, "detail": r.detail,
                          "measured": r.measured, "baseline": r.baseline}
                      for n, r in results.items()},
        }, indent=2))
    else:
        print()
        if skipped:
            print("  %d gate(s) SKIPPED and therefore unverified: %s"
                  % (len(skipped), ", ".join(skipped)))
            print("  A skip is not a pass. CI runs with --require-db so these fail there.")
        if failed:
            print("  FAILED: %s  (%ss)" % (", ".join(failed), elapsed))
        else:
            print("  All %d gate(s) that could run passed (%ss)."
                  % (len(results) - len(skipped), elapsed))
        print()

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
