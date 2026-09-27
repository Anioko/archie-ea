#!/usr/bin/env python
"""ARCH-070 measurement: classify Alpine.js expressions in templates by
compatibility with Alpine's CSP-compatible build.

The CSP build (`alpinejs-csp`) removes `new Function(...)` expression
evaluation. It only accepts expressions that are:
  - a bare identifier / property access chain (`count`, `foo.bar`)
  - a single function/method call with simple argument expressions
    (`increment()`, `save(item.id)`)

Anything containing JS operators, literals beyond simple call args,
ternaries, arithmetic, logical/comparison operators, assignment,
increment/decrement, template literals, or multiple statements is NOT
supported by the CSP build without rewriting the markup to call a
method that does the work in the Alpine component's `data()`/methods.

This script is a heuristic static scanner, not a JS parser. It errs
toward flagging anything with a JS operator as "unsafe" (i.e. requires
rewrite), which is the safe direction for this measurement: it will not
undercount the blast radius.

Usage:
    python scripts/check_alpine_csp_compat.py            # summary report
    python scripts/check_alpine_csp_compat.py --json      # machine-readable
    python scripts/check_alpine_csp_compat.py --examples N  # show N unsafe examples per attribute type
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIRS = [REPO_ROOT / "app" / "templates", REPO_ROOT / "app" / "modules"]

# Alpine directive attribute names we scan. Covers x-data, x-on:/@,
# x-bind:/: (skipped for :style/:class which are CSSOM/attr writes, still
# JS-evaluated though, so included), x-show, x-if, x-text, x-html,
# x-model, x-init, x-effect.
ATTR_RE = re.compile(
    r"""
    (?P<name>
        x-data
        | x-init
        | x-show
        | x-if
        | x-text
        | x-html
        | x-model(?:\.[a-zA-Z.]+)?
        | x-effect
        | x-on:[a-zA-Z0-9\-_.]+
        | @[a-zA-Z0-9\-_.:]+
        | x-bind:[a-zA-Z0-9\-_:]+
        | :[a-zA-Z0-9\-_:]+
    )
    \s*=\s*
    (?P<quote>["'])
    (?P<expr>.*?)
    (?P=quote)
    """,
    re.VERBOSE,
)

# A bare "safe" expression: optional leading '!', identifier / dotted /
# bracket-indexed chain, optionally followed by a single call with
# argument list containing only identifiers/dotted chains/literals
# separated by commas (no operators between them at top level).
SAFE_RE = re.compile(
    r"""^\s*
    !?
    [A-Za-z_$][\w$]*
    (?:\.[A-Za-z_$][\w$]*|\[\d+\]|\(\))*
    (?:\(\s*
        (?:
            [^()]*
        )?
    \s*\))?
    \s*$
    """,
    re.VERBOSE,
)

# Jinja templating inside the expression ({{ }} / {% %}) makes this
# unclassifiable by the static heuristic; treat as "dynamic" bucket,
# reported separately since it's a template-authoring pattern, not a
# hand-written Alpine expression.
JINJA_RE = re.compile(r"\{\{|\{%")

OPERATOR_HINTS = re.compile(
    r"""
    &&|\|\||===|!==|==|!=|<=|>=|\+\+|--|=>|
    [+\-*/%<>=?:,]|
    \btrue\b|\bfalse\b|\bnull\b|\bnew\b|
    `
    """,
    re.VERBOSE,
)


def classify(expr: str) -> str:
    e = expr.strip()
    if not e:
        return "empty"
    if JINJA_RE.search(e):
        return "jinja"
    if SAFE_RE.match(e) and not OPERATOR_HINTS.search(e):
        return "safe"
    return "unsafe"


def scan():
    results = {"safe": [], "unsafe": [], "jinja": [], "empty": []}
    files_scanned = 0
    for base in TEMPLATE_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*.html"):
            files_scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(path.relative_to(REPO_ROOT))
            for m in ATTR_RE.finditer(text):
                name = m.group("name")
                expr = m.group("expr")
                bucket = classify(expr)
                results[bucket].append((rel, name, expr))
    return results, files_scanned


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--examples", type=int, default=0)
    args = ap.parse_args()

    results, files_scanned = scan()
    counts = {k: len(v) for k, v in results.items()}
    total = sum(counts.values())

    if args.json:
        out = {"files_scanned": files_scanned, "total": total, "counts": counts}
        if args.examples:
            out["unsafe_examples"] = [
                {"file": f, "attr": a, "expr": e}
                for f, a, e in results["unsafe"][: args.examples]
            ]
        print(json.dumps(out, indent=2))
        return 0

    print(f"Files scanned: {files_scanned}")
    print(f"Total Alpine directive expressions found: {total}")
    for bucket in ("safe", "unsafe", "jinja", "empty"):
        print(f"  {bucket:8s}: {counts[bucket]}")

    if args.examples:
        print(f"\nFirst {args.examples} unsafe examples:")
        for f, a, e in results["unsafe"][: args.examples]:
            print(f"  {f}: {a}=\"{e}\"")

    return 0


if __name__ == "__main__":
    sys.exit(main())
