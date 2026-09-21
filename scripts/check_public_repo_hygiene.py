#!/usr/bin/env python
r"""This repository is public; the orchestrator repository that plans its
work is not. A path reference to that repository's `docs/buckets/<slug>/`
folder structure, or a copy of that folder committed here, tells a public
reader exactly what to go looking for and where -- and once, 82 files and
17,550 lines of it were committed here directly (removed 21 Sep 2026).

This checker holds two things at ZERO:

1. No `docs/buckets/` directory tracked in this repository at all.
2. No tracked source file (app/, scripts/, tests/, templates) contains the
   literal string `docs/buckets/` -- a reference to that structure, even
   without the files themselves, still describes it.

Per-line escape hatch: `hygiene-ok: <reason>` on the same line, for a
reference that is itself the point (this file's own docstring, or a test
asserting the pattern is absent).

Proven-against: the first run against this repository's tracked tree, 21
Sep 2026, after docs/buckets/ (82 files) had been removed but before its
scattered path references elsewhere had been -- red at 7 (comments and
docstrings in app/utils/role_access.py and six others); green (0) once each
was reworded.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCAN_DIRS = ("app", "scripts", "tests", "templates")
PATTERN = "docs/buckets/"
SELF_NAME = os.path.basename(__file__)


def _tracked_bucket_paths(root: str) -> list[str]:
    bucket_dir = os.path.join(root, "docs", "buckets")
    if not os.path.isdir(bucket_dir):
        return []
    found = []
    for dirpath, _dirnames, filenames in os.walk(bucket_dir):
        for name in filenames:
            found.append(os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/"))
    return found


def _scan_for_references(root: str) -> list[str]:
    problems = []
    for scan_dir in SCAN_DIRS:
        base = os.path.join(root, scan_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "node_modules", ".git")]
            for name in filenames:
                if name == SELF_NAME:
                    continue
                if not name.endswith((".py", ".html", ".j2", ".md")):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    with open(path, encoding="utf-8", errors="ignore") as fh:
                        lines = fh.readlines()
                except OSError:
                    continue
                for lineno, line in enumerate(lines, start=1):
                    if PATTERN in line and "hygiene-ok:" not in line:
                        rel = os.path.relpath(path, root).replace(os.sep, "/")
                        problems.append(f"{rel}:{lineno}: references '{PATTERN}'")
    return problems


def scan(root: str) -> list[str]:
    problems = [f"tracked in docs/buckets/: {p}" for p in _tracked_bucket_paths(root)]
    problems += _scan_for_references(root)
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args()

    problems = scan(os.path.abspath(args.root))
    if not args.count:
        for line in problems:
            print("  " + line)
        if problems:
            print()
            print(
                "Remove the docs/buckets/ content or reference -- it belongs in the\n"
                "orchestrator repository, not here. Mark a genuinely necessary line\n"
                "with 'hygiene-ok: <reason>' (e.g. this checker's own docstring)."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
