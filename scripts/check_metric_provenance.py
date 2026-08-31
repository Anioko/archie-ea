#!/usr/bin/env python
"""A number the user can read must come from a query, not from the source.

The data / evidence analyst's question, per CLAUDE.md: can this number be
traced to the query that produced it. Distinct from the data architect, who
owns which store is the system of record -- this role owns whether what the
screen SAYS about that store is true. The 30 Aug 2026 QA audit's symptom was
/capability-map/ showing "Total Capabilities 191" directly above a table
reading "Showing 1-10 of 0 results", and traceability reporting 48% coverage
where the capability map reported 0%. Two surfaces, one question, two answers,
and no way for the user to tell which one to act on.

CLAUDE.md already forbids the class ("Never invent data ... a 0 that means 'not
computed' is indistinguishable from a measured zero"). The fabricated-data gate
holds part of it. This gate holds the part fabricated-data does not: a metric
whose VALUE is written in the source rather than measured.

DETECTED -- one shape, chosen because it has no innocent reading:

  A **proportion** emitted to a user surface with a hardcoded NON-ZERO value.
  A key or kwarg matching PROPORTION (percent, pct, coverage, score, maturity,
  health, readiness, confidence, completeness, utilisation) passed to
  render_template / jsonify / success_response with a numeric literal that is
  not 0. A proportion cannot be a structural constant the way "total_phases: 5"
  or a "out of 7 tests" denominator can: 100% completeness, or a 72 health
  score, is a claim about measured data. Zero is excluded because a zero
  literal is overwhelmingly an initialiser or an empty-result path, and the
  ambiguity CLAUDE.md describes is real but not separable statically.

SKIPPED, deliberately, each with its reason:

  * Integer counts and totals with literal values (53 in the tree). Most are
    honest -- `"created_count": 0` on a path where nothing was created, a
    `total: 7` denominator naming a fixed number of tests. Flagging them
    produced false positives on inspection, and a gate with false positives is
    worse than no gate (docs/DELIVERY_CONTRACT.md records a whole gate dropped
    for exactly that).
  * Accumulator variables (`count += 1`) passed to render_template. They look
    literal to a naive binding walk and are in fact computed. This was a
    measured false positive during construction, not a hypothetical.
  * The cross-store shape itself -- a total from store A captioning a list from
    store B. Deciding it statically means resolving which model each kwarg came
    from through service layers and, on /capability-map/ specifically, through
    a client-side fetch to a different endpoint. The structural half of that
    question is already gated by check_canonical_store.py (one table, one
    mapped class); the rendering half needs runtime and belongs to the
    walkthrough, not to a source reader.

Real measurement, 31 Aug 2026: 2, both in one early-return path of
solution_generate_routes.py, which reports ``completeness_before`` and
``completeness_after`` as 1.0 -- a fully-complete score -- on the branch taken
when there is nothing to score at all. The user is told the solution is 100%
complete precisely when nothing was measured.

Escape hatch: `metric-provenance-ok: <reason>` on the line, for a proportion
that genuinely is a constant of the design. Say what makes it fixed.

    python scripts/check_metric_provenance.py
    python scripts/check_metric_provenance.py --count
    python scripts/check_metric_provenance.py --root /path/to/tree

Proven-against: a synthetic route returning ``jsonify({"coverage_percent": 87})``
-- red at 1 naming the literal, green at 0 when the same key is computed from a
query. Pinned red-and-green on every run by tests/test_gates_actually_fail.py.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"metric-provenance-ok:[ \t]*\S")
PROPORTION = re.compile(
    r"(^|_)(percent|percentage|pct|coverage|score|maturity|health|readiness"
    r"|confidence|completeness|utilization|utilisation)(s?)($|_)",
    re.IGNORECASE,
)
SURFACES = frozenset({"render_template", "jsonify", "success_response"})


def _literal_value(node):
    """The numeric value of a plain numeric literal, else None."""
    if not isinstance(node, ast.Constant):
        return None
    if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
        return None
    return node.value


def _emitted_pairs(call: ast.Call):
    """(name, value node) for every named field this call hands to the user."""
    pairs = []
    for keyword in call.keywords:
        if keyword.arg:
            pairs.append((keyword.arg, keyword.value))
    containers = [a for a in call.args if isinstance(a, ast.Dict)]
    containers += [k.value for k in call.keywords if isinstance(k.value, ast.Dict)]
    for container in containers:
        for key, value in zip(container.keys, container.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                pairs.append((key.value, value))
    return pairs


def scan(root: str) -> list:
    problems = []
    base = os.path.join(root, "app")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    source = fh.read()
                tree = ast.parse(source)
            except (OSError, SyntaxError, ValueError):
                continue
            lines = source.split("\n")
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name not in SURFACES:
                    continue
                for field, value_node in _emitted_pairs(node):
                    if not PROPORTION.search(field):
                        continue
                    value = _literal_value(value_node)
                    if value is None or value == 0:
                        continue
                    lineno = getattr(value_node, "lineno", node.lineno)
                    line = lines[lineno - 1] if lineno <= len(lines) else ""
                    if ALLOW.search(line):
                        continue
                    problems.append(
                        "%s:%d [metric-provenance] %s() reports %r as the literal "
                        "%r -- a proportion written in the source, not measured "
                        "from a query, so the user cannot tell a fabricated "
                        "reading from a real one"
                        % (rel, lineno, name, field, value)
                    )
    return sorted(problems)


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
                "Compute the proportion from the query, or send None so the UI\n"
                "renders an em dash, or append 'metric-provenance-ok: <reason>'\n"
                "to the line saying what makes the value a fixed constant."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
