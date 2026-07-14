#!/usr/bin/env python3
"""no-dark-features guardrail.

FAILS a commit / CI run when a NEW product-feature flag is introduced that
defaults OFF. Product features MUST ship ON and wired into a real path — never
behind a switch someone has to discover and flip.

Only OPERATIONAL config may be flag-gated (external secrets, deploy-env
selectors, infra/perf/observability toggles). Those are auto-exempt if their
name looks like a secret, or must be listed in config/allowed_config.txt.

Usage:
  no_dark_features.py                # scan staged diff  (pre-commit)
  no_dark_features.py --base <ref>   # scan diff vs <ref> (CI)
  no_dark_features.py --all          # scan the whole tree (audit)
Exit code 1 on any violation.
"""
import re, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOW = ROOT / "config" / "allowed_config.txt"

# default-OFF feature-flag shapes
PATTERNS = [
    re.compile(r"""_env_bool\(\s*['"]([A-Z0-9_]+)['"]\s*,\s*False\b"""),
    re.compile(r"""(?:os\.)?(?:environ\.get|getenv)\(\s*['"]([A-Z0-9_]+)['"]\s*,\s*['"](?:false|0|no|off)['"]"""),
    # default empty-string, opt-IN to true -- dark by omission: get("X","").lower()=="true"
    re.compile(r"""(?:os\.)?(?:environ\.get|getenv)\(\s*['"]([A-Z0-9_]+)['"]\s*,\s*['"]['"]\s*\)\s*\.lower\(\)\s*==\s*['"]true['"]"""),
    re.compile(r"""FeatureFlag\([^)]*\benabled\s*=\s*False\b"""),
    re.compile(r"""enabled\s*=\s*db\.Column\([^)]*default\s*=\s*False"""),
]
SECRET_SUFFIXES = ("_API_KEY", "_SECRET", "_TOKEN", "_PASSWORD", "_URL", "_KEY",
                   "_DSN", "_ENDPOINT", "_CLIENT_ID", "_CLIENT_SECRET", "_WEBHOOK")


def load_allow():
    names = set()
    if ALLOW.exists():
        for ln in ALLOW.read_text(encoding="utf-8").splitlines():
            ln = ln.split("#")[0].strip()
            if ln:
                names.add(ln.upper())
    return names


def scan_lines(mode, base):
    if mode == "all":
        files = subprocess.check_output(["git", "ls-files", "*.py", "*.yml", "*.yaml"],
                                        cwd=ROOT).decode().split()
        for f in files:
            p = ROOT / f
            try:
                for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    yield f, ln
            except Exception:
                continue
        return
    args = (["git", "diff", "--unified=0", base + "...", "--"] if base
            else ["git", "diff", "--cached", "--unified=0"])
    diff = subprocess.check_output(args, cwd=ROOT).decode("utf-8", "replace")
    cur = None
    for ln in diff.splitlines():
        if ln.startswith("+++ b/"):
            cur = ln[6:]
        elif ln.startswith("+") and not ln.startswith("+++"):
            yield cur, ln[1:]


def main():
    mode = "all" if "--all" in sys.argv else "diff"
    base = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else None
    allow = load_allow()
    violations = []
    for path, line in scan_lines(mode, base):
        for pat in PATTERNS:
            m = pat.search(line)
            if not m:
                continue
            name = (m.group(1) if m.groups() else "FeatureFlag(default off)")
            u = name.upper()
            if u in allow or any(u.endswith(s) for s in SECRET_SUFFIXES):
                continue
            violations.append((path, line.strip(), name))
            break
    if violations:
        print("\n❌ NO-DARK-FEATURES: a product feature is gated OFF by default.\n")
        print("   Product features MUST ship ON and wired into a real path.")
        print("   If this is genuine OPERATIONAL config (secret / deploy-selector / infra),")
        print("   add its name to config/allowed_config.txt WITH A ONE-LINE REASON.\n")
        for path, line, name in violations:
            print(f"   • {name}   ({path})")
            print(f"       {line}")
        print("")
        return 1
    print("✅ no-dark-features: no default-off product flags introduced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
