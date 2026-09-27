#!/usr/bin/env python
"""Two response shapes on one API means every caller must guess which it got.

The integration architect's question, per CLAUDE.md's role list: "what does this
call, and what does it do when that is slow, absent or lying?"

Archie's own convention, from CLAUDE.md's Conventions section:

    "Responses may be wrapped by success_response() -- unwrap with
     json.data ?? json."

That sentence documents the defect rather than a design. Every front-end caller
carries a conditional unwrap because the API does not commit to one envelope,
and `json.data ?? json` silently produces the WRONG object whenever a bare
payload happens to have a `data` key of its own.

Measured 31 Aug 2026: 2,668 route handlers return jsonify, and 853 of them
neither call success_response() nor include a "success" key. So a third of the
surface answers in a different shape from the rest, and the client cannot tell
which without inspecting the body.

This is the failure the convention makes invisible: `fetch` does not reject on
404, so a caller that unwraps the wrong shape reads `undefined` and renders it
as a plausible blank rather than an error -- the exact fabricated-data problem
the `fabricated-data` gate exists to stop, arriving through the front door.

A RATCHET at the measured number, and deliberately not a wall. Choosing the
canonical envelope and migrating 853 handlers is a breaking API change that
needs its callers moved in step; that is a scheduled migration, not a lint fix.
What the gate buys is that the inconsistency cannot grow while that work is
outstanding -- which the sentence in CLAUDE.md was not doing.

Legitimate exceptions exist and should say so rather than being silently
excluded: a health probe, a raw export, a third-party webhook whose response
shape is dictated by the other side.

Escape hatch: `envelope-ok: <reason>` in the handler.

    python scripts/check_api_envelope.py
    python scripts/check_api_envelope.py --count

Proven-against: success_response() replaced by a bare jsonify({...}) in a route
handler -- the count rises by one naming that handler, and returns when
restored. Pinned red-and-green on a synthetic tree by
tests/test_gates_actually_fail.py.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"envelope-ok:[ \t]*\S")

# Any of these means the handler has committed to the envelope.
ENVELOPE_MARKERS = ("success_response", "error_response", '"success"', "'success'")


def scan(root: str) -> list:
    problems = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "app")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue

            for func in ast.walk(tree):
                if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                decorators = " ".join(
                    ast.get_source_segment(source, d) or "" for d in func.decorator_list
                )
                if ".route(" not in decorators:
                    continue
                body = ast.get_source_segment(source, func) or ""
                if "jsonify(" not in body:
                    continue
                if any(marker in body for marker in ENVELOPE_MARKERS):
                    continue
                if ALLOW.search(body):
                    continue
                problems.append(
                    "%s:%d [api-envelope] %s() returns jsonify with no envelope "
                    "-- callers must guess between the wrapped and bare shape, "
                    "and `json.data ?? json` picks wrong when the payload has "
                    "its own data key" % (rel, func.lineno, func.name)
                )
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
                "Return through success_response()/error_response(), or append\n"
                "'envelope-ok: <reason>' naming why this handler's shape is\n"
                "dictated from outside (a health probe, a raw export, a webhook)."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
