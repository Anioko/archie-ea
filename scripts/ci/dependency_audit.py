"""Fail when a dependency brings in a NEW known vulnerability.

    python scripts/ci/dependency_audit.py                 # gate against the baseline
    python scripts/ci/dependency_audit.py --update-baseline

A ratchet, not a clean-tree gate, for the same reason the bandit and
undefined-names gates are ratchets: the tree carries known debt, and a check that
fails on day one gets disabled on day two. This fails only on advisories that are
not already recorded, so the number can go down but never up.

The baseline is a record of accepted risk, not of safety. Everything in it is a
real vulnerability that has not been remediated yet, and an enterprise security
review will ask about each entry. Shrinking it is the point.
"""
import argparse
import json
import os
import subprocess
import sys

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dependency_baseline.json")
REQUIREMENTS = "requirements.txt"


def audit():
    """Run pip-audit and return {package: {advisory_id, ...}} plus fix versions."""
    proc = subprocess.run(
        [sys.executable, "-m", "pip_audit", "-r", REQUIREMENTS,
         "--progress-spinner", "off", "-f", "json"],
        capture_output=True, text=True,
    )
    if not proc.stdout.strip():
        print("pip-audit produced no output:\n%s" % proc.stderr[-2000:], file=sys.stderr)
        raise SystemExit(2)
    data = json.loads(proc.stdout)
    deps = data.get("dependencies", data if isinstance(data, list) else [])

    found, meta = {}, {}
    for dep in deps:
        vulns = dep.get("vulns") or []
        if not vulns:
            continue
        name = dep["name"]
        found[name] = sorted(v["id"] for v in vulns)
        fixes = [f for v in vulns for f in (v.get("fix_versions") or [])]
        meta[name] = {"installed": dep.get("version"),
                      "fix_available": max(fixes) if fixes else None}
    return found, meta


def load_baseline():
    if not os.path.exists(BASELINE):
        return {}
    with open(BASELINE, encoding="utf-8") as fh:
        return json.load(fh).get("accepted", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args()

    found, meta = audit()
    total = sum(len(v) for v in found.values())

    if args.update_baseline:
        with open(BASELINE, "w", encoding="utf-8") as fh:
            json.dump({
                "_comment": "Accepted dependency vulnerabilities. Each entry is real, "
                            "unremediated risk that a security review will ask about. "
                            "Regenerate with: python scripts/ci/dependency_audit.py "
                            "--update-baseline",
                "accepted": found,
                "context": meta,
            }, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("baseline updated: %d package(s), %d advisories" % (len(found), total))
        return 0

    baseline = load_baseline()
    new = {}
    for pkg, ids in found.items():
        unseen = sorted(set(ids) - set(baseline.get(pkg, [])))
        if unseen:
            new[pkg] = unseen

    print("dependency audit: %d package(s), %d advisories total" % (len(found), total))
    for pkg in sorted(found):
        info = meta.get(pkg, {})
        print("  %-22s %-10s -> %-10s %d" % (
            pkg, info.get("installed") or "?", info.get("fix_available") or "no fix",
            len(found[pkg])))

    if new:
        print("\nNEW advisories not in the baseline:")
        for pkg, ids in sorted(new.items()):
            fix = (meta.get(pkg) or {}).get("fix_available") or "none published"
            print("  %s: %s   (fix: %s)" % (pkg, ", ".join(ids), fix))
        print("\nUpgrade the package, or accept it deliberately with "
              "--update-baseline and say why in the pull request.")
        return 1

    resolved = sum(len(set(ids) - set(found.get(pkg, [])))
                   for pkg, ids in baseline.items())
    if resolved:
        print("\n%d baselined advisor%s no longer present - re-run with "
              "--update-baseline to lock the improvement in."
              % (resolved, "y is" if resolved == 1 else "ies are"))
    print("\nno new vulnerabilities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
