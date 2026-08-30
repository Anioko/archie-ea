#!/usr/bin/env python
"""Fail when an `x-data` names an Alpine component the CSP evaluator cannot resolve.

Archie evaluates every Alpine expression through the hand-written interpreter in
``app/static/js/csp/csp-evaluator.js`` so ``script-src`` can drop
``'unsafe-eval'``. That interpreter resolves a bare identifier against the
component scope and then against ``window`` (``readId``); it never consults
Alpine's ``Alpine.data()`` registry. So::

    Alpine.data('impactAnalysis', () => ({ ... }))   <div x-data="impactAnalysis">

registers a component that is never mounted. Alpine treats the undefined
expression as an empty component, and the page silently degrades in the worst
possible way: controls do nothing, and every expression in the subtree falls
through to a *global* of the same name. The measured case that motivated this
gate is Impact Analysis, where ``x-show="history.length > 0"`` and
``x-text="'(' + history.length + ')'"`` resolved to ``window.history`` and the
page displayed the browser's navigation-entry count in a badge labelled
"Recent Analyses", above an empty table. Nothing went red: no console error, no
failed request, no 5xx. Only a person reading the number could tell.

The supported form -- used by ~156 templates -- is a top-level (window) factory
invoked in the attribute::

    function impactAnalysis() { return { ... }; }     <div x-data="impactAnalysis()">

This gate flags an ``x-data`` whose value is a bare identifier (no call, no
object literal). Object literals (``x-data="{ open: false }"``) and calls
(``x-data="foo()"``) are fine, as are the Alpine magics.

Usage:
    python scripts/check_alpine_data_binding.py
    python scripts/check_alpine_data_binding.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIRS = [REPO_ROOT / "app" / "templates", REPO_ROOT / "app" / "modules"]

# x-data="..." / x-data='...' as an ATTRIBUTE — the leading whitespace or "<"
# keeps prose in a comment ("the bare x-data=\"foo\" form") from matching.
_X_DATA = re.compile(r"""(?<=[\s"'])x-data\s*=\s*(?P<q>["'])(?P<val>[^"']*)(?P=q)""")

# A bare identifier or dotted path with no call, no operators, no braces.
_BARE_IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*$")

# Values that are legitimately bare: Alpine reads these itself.
_ALLOWED_BARE = {"", "true", "false", "null"}


def scan() -> list[dict]:
    findings: list[dict] = []
    for root in TEMPLATE_DIRS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.html")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for m in _X_DATA.finditer(line):
                    val = m.group("val").strip()
                    if val in _ALLOWED_BARE or val.startswith(("{", "[", "(")):
                        continue
                    if not _BARE_IDENT.match(val):
                        continue
                    findings.append(
                        {
                            "file": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                            "line": lineno,
                            "expression": val,
                        }
                    )
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    findings = scan()
    if args.json:
        print(json.dumps({"count": len(findings), "findings": findings}, indent=2))
    elif findings:
        print(
            f"{len(findings)} x-data binding(s) the CSP evaluator cannot resolve.\n"
            'Use x-data="componentName()" with a top-level `function componentName()`\n'
            "that returns the object, and assign it to window. Alpine.data() plus a\n"
            "bare name mounts an EMPTY component and every expression in the subtree\n"
            "silently falls through to a global of the same name.\n"
        )
        for f in findings:
            print(f"  {f['file']}:{f['line']}: x-data=\"{f['expression']}\"")
    else:
        print("all x-data bindings resolve under the CSP evaluator")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
