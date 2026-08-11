#!/usr/bin/env python3
"""Find Jinja expressions that CALL a name nothing can provide at render time.

``{{ min(page * per_page, total_count) }}`` and
``{{ getCategoryExplanation(cap.category) }}`` both look ordinary. ``min`` is a
Python builtin, not a Jinja global; ``getCategoryExplanation`` is a JavaScript
function defined in a ``<script>`` block further down the same file. Jinja
resolves neither, so each raises ``UndefinedError`` *when the branch is reached*
— which means the page works on an empty result set and dies as soon as it has
something to show. Both were live on ``/capability-maturity/search``, one of
them behind ``{% if cap.category %}`` and the other behind a pagination guard,
so the page had never once returned a result.

``template-syntax`` cannot see this: the template parses perfectly. Only
resolution fails, and only at render.

What counts as resolvable:

* ``jinja_env.globals``, filters and tests
* everything the app's context processors inject
* names the template itself binds — ``{% macro %}``, ``{% set %}``, ``{% for %}``,
  ``{% import ... as x %}``, ``{% from ... import a, b %}``, and macro arguments
* names a base template binds, followed through ``{% extends %}`` and
  ``{% include %}`` when the target is a literal

Anything else is reported. A view *can* pass a callable into the context, which
this cannot see; that is what the baseline is for — the count ratchets down and
each new entry has to be justified.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = REPO / "app" / "templates"

# Names Jinja binds implicitly inside a rendering scope.
IMPLICIT = {"loop", "self", "super", "caller", "varargs", "kwargs"}


def _load_env_names():
    """Globals, filters, tests and context-processor keys from the real app."""
    sys.path.insert(0, str(REPO))
    os.environ.setdefault("FLASK_ENV", "development")

    from manage import app  # noqa: PLC0415 - importing the app is the point

    names = set(app.jinja_env.globals) | set(app.jinja_env.filters)
    names |= set(app.jinja_env.tests)

    for processors in app.template_context_processors.values():
        for func in processors:
            try:
                with app.test_request_context("/"):
                    names |= set(func().keys())
            except Exception:  # noqa: BLE001 - a processor that needs more than a bare
                continue      # request context still cannot hide a missing name here
    return names, app.jinja_env


def _bound_by(node, jinja_nodes) -> set:
    """Every name this node binds into its own scope."""
    bound = set()
    if isinstance(node, jinja_nodes.Macro):
        bound.add(node.name)
        bound |= {arg.name for arg in node.args}
    elif isinstance(node, jinja_nodes.Assign):
        target = node.target
        if isinstance(target, jinja_nodes.Name):
            bound.add(target.name)
        elif isinstance(target, jinja_nodes.Tuple):
            bound |= {n.name for n in target.items if isinstance(n, jinja_nodes.Name)}
    elif isinstance(node, jinja_nodes.AssignBlock):
        if isinstance(node.target, jinja_nodes.Name):
            bound.add(node.target.name)
    elif isinstance(node, jinja_nodes.For):
        if isinstance(node.target, jinja_nodes.Name):
            bound.add(node.target.name)
        elif isinstance(node.target, jinja_nodes.Tuple):
            bound |= {n.name for n in node.target.items if isinstance(n, jinja_nodes.Name)}
    elif isinstance(node, jinja_nodes.Import):
        if node.target:
            bound.add(node.target)
    elif isinstance(node, jinja_nodes.FromImport):
        for name in node.names:
            bound.add(name[1] if isinstance(name, tuple) else name)
    elif isinstance(node, jinja_nodes.With):
        bound |= {n.name for n in node.targets if isinstance(n, jinja_nodes.Name)}
    return bound


def _parents(source: str, jinja_env, jinja_nodes) -> list:
    """Literal {% extends %} / {% include %} targets, so inherited macros resolve."""
    out = []
    try:
        ast = jinja_env.parse(source)
    except Exception:  # noqa: BLE001 - template-syntax owns unparseable templates
        return out
    for node in ast.find_all((jinja_nodes.Extends, jinja_nodes.Include)):
        target = node.template
        if isinstance(target, jinja_nodes.Const) and isinstance(target.value, str):
            out.append(target.value)
    return out


def _names_bound_in(source: str, jinja_env, jinja_nodes) -> set:
    try:
        ast = jinja_env.parse(source)
    except Exception:  # noqa: BLE001
        return set()
    bound = set()
    for node in ast.find_all(
        (
            jinja_nodes.Macro,
            jinja_nodes.Assign,
            jinja_nodes.AssignBlock,
            jinja_nodes.For,
            jinja_nodes.Import,
            jinja_nodes.FromImport,
            jinja_nodes.With,
        )
    ):
        bound |= _bound_by(node, jinja_nodes)
    return bound


def scan():
    env_names, jinja_env = _load_env_names()
    from jinja2 import nodes as jinja_nodes  # noqa: PLC0415

    sources = {}
    for path in sorted(TEMPLATE_ROOT.rglob("*")):
        if path.suffix.lower() not in (".html", ".jinja", ".j2") or not path.is_file():
            continue
        rel = path.relative_to(TEMPLATE_ROOT).as_posix()
        sources[rel] = path.read_text(encoding="utf-8", errors="replace")

    bound_cache = {
        rel: _names_bound_in(src, jinja_env, jinja_nodes) for rel, src in sources.items()
    }

    # Parsing is the expensive step and admin_base.html is reachable from almost
    # every template, so both edge maps are built once rather than re-derived
    # while walking each template's closure.
    parents_cache = {
        rel: _parents(src, jinja_env, jinja_nodes) for rel, src in sources.items()
    }

    # An included partial renders inside its includer's context, so a macro the
    # includer imported is in scope there. The include edge has to be followed
    # in both directions: a partial does not name the page that includes it.
    included_by = {}
    for rel, targets in parents_cache.items():
        for target in targets:
            included_by.setdefault(target, set()).add(rel)

    findings = []
    for rel, src in sources.items():
        try:
            ast = jinja_env.parse(src)
        except Exception:  # noqa: BLE001 - template-syntax reports these
            continue

        available = set(env_names) | IMPLICIT | bound_cache[rel]
        # Macros defined in a base or included template are in scope here, and
        # so are those of any template that includes this one.
        seen = {rel}
        queue = list(parents_cache[rel]) + list(included_by.get(rel, ()))
        while queue:
            other = queue.pop()
            if other in seen or other not in sources:
                continue
            seen.add(other)
            available |= bound_cache[other]
            queue.extend(parents_cache[other])
            queue.extend(included_by.get(other, ()))

        for call in ast.find_all(jinja_nodes.Call):
            target = call.node
            if not isinstance(target, jinja_nodes.Name):
                continue  # a.b() resolves against a, which is a variable, not a call
            if target.name in available:
                continue
            findings.append(
                {
                    "template": rel,
                    "line": target.lineno,
                    "name": target.name,
                }
            )

    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--count", action="store_true", help="print only the count")
    args = parser.parse_args()

    findings = scan()

    if args.count:
        print(len(findings))
        return 0
    if args.json:
        print(json.dumps({"count": len(findings), "findings": findings}, indent=2))
    else:
        for f in findings:
            print(f"{f['template']}:{f['line']}  {f['name']}() is not resolvable")
        print(f"\n{len(findings)} uncallable name(s) in Jinja expressions")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
