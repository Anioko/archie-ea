#!/usr/bin/env python
"""No unevidenced claim ships, and no gate is trusted until it has failed.

Written 30 Aug 2026 after a session in which the model running this repository
announced three conclusions it had not measured -- that the audit harness was
broken (it had just measured 1,700 page loads), that the Health Scorecard was
hanging with a scalability defect (0.04s), and that the product lacked personas
it has. Each was corrected within minutes and none reached production, because
the artifacts were measured even when the narration was not. That asymmetry is
the whole point of this file: make the MEASUREMENT the deliverable, so an
assertion without one cannot be committed by anyone -- human or model.

Two rules, both mechanical, both binding on any agent.

RULE 1 -- evidence for a behavioural change.
A commit that changes behaviour under app/ must carry either a test change in
the same commit, or an `Evidence:` trailer naming the command that was run and
what it returned. "I checked it" is not evidence; a command and its output is.

    Evidence: pytest tests/journeys/test_journey_cto.py -q -> 4 passed
    Evidence: curl -s -o /dev/null -w '%{http_code}' .../dashboard/health -> 200 in 0.45s

Docs, comments, templates-only styling and test-only commits are exempt: they
change no behaviour to measure.

RULE 2 -- provenance for a gate.
TESTING_STANDARD.md rule 7 already requires that every gate be proven against
known-bad input -- "reintroduce the defect, watch the gate go red, restore,
watch it go green. A checker nobody has seen fail is just a number." Nothing
enforced it, which is exactly the hole a model can walk through: write a
checker that has never once gone red, register it at 0, and report coverage.

So every checker registered in verify.py must carry a `Proven-against:` line in
its module docstring, naming the concrete input it was observed to fail on.

This is a ratchet, not a wall: the existing checkers predate the rule and are
counted as debt, so the number can only go down. Every NEW gate must carry its
proof on the day it lands.

    python scripts/check_evidence_contract.py                 # HEAD
    python scripts/check_evidence_contract.py --staged        # pre-commit
    python scripts/check_evidence_contract.py --range A..B    # a range
    python scripts/check_evidence_contract.py --count         # trailing = count

Proven-against: a commit touching app/ with neither a test nor an Evidence:
trailer, and a checker registered in verify.py whose docstring carries no
Proven-against line -- both observed red, then green once supplied.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EVIDENCE = re.compile(r"^\s*Evidence:\s*\S", re.M)
PROVEN = re.compile(r"^\s*Proven-against:\s*\S", re.M)

# Changing one of these changes what the product DOES, so it needs a measurement.
BEHAVIOURAL = (".py", ".js", ".html", ".jinja", ".jinja2")

# These change nothing a user can observe, so requiring a measurement would be
# noise -- and a noisy gate gets ignored (TESTING_STANDARD.md, rule 8).
EXEMPT_PREFIXES = ("docs/", "tests/", "scripts/", "migrations/", ".github/")
EXEMPT_SUFFIXES = (".md", ".txt", ".json", ".css", ".cfg", ".toml", ".ini")


def _git(*args: str) -> str:
    proc = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else ""


def _behavioural(paths: list[str]) -> list[str]:
    out = []
    for path in paths:
        p = path.replace("\\", "/").strip()
        if not p or p.startswith(EXEMPT_PREFIXES) or p.endswith(EXEMPT_SUFFIXES):
            continue
        if p.startswith("app/") and p.endswith(BEHAVIOURAL):
            out.append(p)
    return out


def check_evidence(staged: bool, rev_range: str | None) -> list[str]:
    problems = []
    if staged:
        files = _git("diff", "--cached", "--name-only").splitlines()
        message = ""  # no message yet at pre-commit time; a test change must carry it
        touched_tests = any(f.startswith("tests/") for f in files)
        if _behavioural(files) and not touched_tests:
            problems.append(
                "staged change: [evidence] %d behavioural file(s) under app/ with no "
                "test change staged -- stage the test, or put an 'Evidence: <command> "
                "-> <result>' trailer in the commit message"
                % len(_behavioural(files))
            )
        return problems

    commits = (_git("rev-list", rev_range) if rev_range else _git("rev-list", "-1", "HEAD")).split()
    for sha in commits:
        files = _git("show", "--pretty=", "--name-only", sha).splitlines()
        behavioural = _behavioural(files)
        if not behavioural:
            continue
        if any(f.startswith("tests/") for f in files):
            continue
        message = _git("show", "-s", "--format=%B", sha)
        if EVIDENCE.search(message):
            continue
        problems.append(
            "%s: [evidence] changes %d behavioural file(s) under app/ with no test "
            "change and no 'Evidence:' trailer (e.g. %s)"
            % (sha[:8], len(behavioural), behavioural[0])
        )
    return problems


def check_provenance() -> list[str]:
    problems = []
    verify = os.path.join(ROOT, "scripts", "verify.py")
    try:
        with open(verify, encoding="utf-8") as fh:
            source = fh.read()
    except OSError:
        return ["scripts/verify.py: [provenance] unreadable"]

    referenced = sorted(set(re.findall(r'"(scripts/check_[a-z0-9_]+\.py)"', source)))
    for relpath in referenced:
        path = os.path.join(ROOT, *relpath.split("/"))
        if not os.path.exists(path):
            problems.append(
                "%s: [provenance] registered in verify.py but not on disk -- the gate "
                "enforces nothing and a fresh clone cannot run it" % relpath
            )
            continue
        with open(path, encoding="utf-8") as fh:
            head = fh.read(6000)
        if not PROVEN.search(head):
            problems.append(
                "%s: [provenance] no 'Proven-against:' line -- a checker nobody has "
                "watched fail is just a number (TESTING_STANDARD.md rule 7)" % relpath
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--range", dest="rev_range", default=None)
    parser.add_argument("--rule", choices=["evidence", "provenance"], action="append")
    args = parser.parse_args()

    rules = args.rule or ["evidence", "provenance"]
    problems = []
    if "evidence" in rules:
        problems += check_evidence(args.staged, args.rev_range)
    if "provenance" in rules:
        problems += check_provenance()

    if not args.count:
        for line in problems:
            print("  " + line)
        if problems:
            print()
            print(
                "A claim is not a measurement. Supply the test, the Evidence: trailer,\n"
                "or the Proven-against: line -- see docs/DELIVERY_CONTRACT.md."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
