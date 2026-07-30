"""Fail CI on NEW bandit findings only.

Why not `bandit -b baseline.json`? Its baseline matching keys on file path and
line number, so it breaks two ways that both happened here:

  * Paths differ by platform. A baseline generated on Windows records
    "app\\models\\x.py"; bandit on the Linux CI runner reports "./app/models/x.py",
    so nothing matches and every pre-existing finding is reported as new.
  * Line numbers drift. Any edit above a finding shifts it, and bandit then
    emits "-- Candidate Issues --" and exits non-zero even though nothing new
    was introduced.

This gate fingerprints a finding by (test_id, normalised path, stripped source
line) and ignores line numbers entirely, so it is stable across platforms and
survives unrelated edits to the same file.

Usage:
    python scripts/ci/bandit_gate.py --update   # regenerate the accepted set
    python scripts/ci/bandit_gate.py            # fail if anything new appeared
"""

import argparse
import json
import os
import subprocess
import sys

BASELINE = ".bandit-baseline.json"
TARGETS = ["app", "config.py", "manage.py"]
EXCLUDE = "./app/static/vendor,./app/modules/solutions_product/templates,./tests"


def normalise(path):
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def fingerprint(result):
    """Identity of a finding, independent of platform and line number."""
    code = " ".join(result.get("code", "").split())
    return "%s|%s|%s" % (result["test_id"], normalise(result["filename"]), code)


def run_bandit():
    cmd = [
        sys.executable, "-m", "bandit", "-r", *TARGETS,
        "-x", EXCLUDE, "-ll", "-f", "json", "-q",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not proc.stdout.strip():
        sys.stderr.write(proc.stderr)
        raise SystemExit("bandit produced no output")
    return json.loads(proc.stdout).get("results", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="write the accepted set")
    args = ap.parse_args()

    results = run_bandit()
    current = {fingerprint(r): r for r in results}

    if args.update:
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(sorted(current), fh, indent=1)
        print("baseline updated: %d accepted finding(s)" % len(current))
        return 0

    if not os.path.exists(BASELINE):
        raise SystemExit("%s missing - run with --update" % BASELINE)
    with open(BASELINE, encoding="utf-8") as fh:
        accepted = set(json.load(fh))

    new = [current[k] for k in current if k not in accepted]
    if not new:
        fixed = len(accepted) - len(set(current) & accepted)
        print("bandit: no new findings (%d accepted, %d of them now fixed)"
              % (len(accepted), fixed))
        return 0

    print("bandit: %d NEW finding(s):\n" % len(new))
    for r in sorted(new, key=lambda x: (x["issue_severity"], x["filename"])):
        print("  [%s/%s] %s" % (r["issue_severity"], r["issue_confidence"], r["test_id"]))
        print("    %s:%s" % (normalise(r["filename"]), r["line_number"]))
        print("    %s" % r["issue_text"][:100])
        snippet = " ".join(r.get("code", "").split())[:100]
        if snippet:
            print("    > %s" % snippet)
        print()
    print("If a finding is genuinely acceptable, justify it in the commit message")
    print("and run: python scripts/ci/bandit_gate.py --update")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
