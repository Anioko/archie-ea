#!/usr/bin/env python
"""Every Jinja template must parse. Gated at ZERO.

A template that fails to parse is not a degraded page — it is a 500 on every
route that renders it, and on every route that renders a *macro* it defines.
Nothing else in the suite catches it: `compile` bytecode-compiles Python only,
and boot-health resolves url_for endpoints without rendering bodies.

Written after a one-line edit added `{# … #}` *inside* an existing `{# … #}`
documentation block in components/dropdown_menu.html. Jinja has no nested
comments, so the inner `#}` closed the outer block 17 lines early and the
remainder of the file became live template code. The macro is imported across
the app; every page using it would have 500'd. It surfaced only because an
unrelated air-gap test happened to render one of those pages.

Usage:
    python scripts/check_template_syntax.py            # list failures
    python scripts/check_template_syntax.py --count    # trailing line = count
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIRS = [
    os.path.join(ROOT, "app", "templates"),
]
# Module-local template folders (app/modules/<domain>/templates)
MODULES = os.path.join(ROOT, "app", "modules")

SKIP_DIRS = {"__pycache__", "node_modules", ".git"}


def template_files():
    seen = set()
    roots = list(TEMPLATE_DIRS)
    if os.path.isdir(MODULES):
        for dirpath, dirnames, _ in os.walk(MODULES):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            if os.path.basename(dirpath) == "templates":
                roots.append(dirpath)
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                # .j2 files under app/modules/solutions_product/templates are
                # code-generation scaffolds (Go, FastAPI, React Native) rendered
                # by deterministic_code_generator with its own environment, not
                # by Flask. They do not parse under default delimiters and are
                # not this gate's concern; only Flask render targets are.
                if fn.endswith(".j2"):
                    continue
                if fn.endswith((".html", ".jinja")):
                    full = os.path.join(dirpath, fn)
                    if full not in seen:
                        seen.add(full)
                        yield root, full


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", action="store_true", help="print only the count")
    args = ap.parse_args()

    try:
        from jinja2 import Environment
        from jinja2.exceptions import TemplateSyntaxError
    except ImportError:
        print("jinja2 not installed", file=sys.stderr)
        print(0)
        return 0

    # parse() only needs the source; no loader required, so an {% extends %} or
    # {% include %} of a template that lives elsewhere does not produce a false
    # positive. This checks syntax, not resolution.
    env = Environment()

    failures = []
    total = 0
    for _root, path in template_files():
        total += 1
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                env.parse(fh.read(), filename=rel)
        except TemplateSyntaxError as exc:
            failures.append((rel, exc.lineno, str(exc)))
        except Exception as exc:  # noqa: BLE001
            failures.append((rel, "?", f"{type(exc).__name__}: {exc}"))

    if not args.count:
        for rel, lineno, msg in failures:
            print(f"{rel}:{lineno}: {msg}")
        if failures:
            print()
            print(
                "Jinja does not nest comments: a `{#` inside a `{# … #}` block "
                "closes it early and the rest of the file becomes template code."
            )
        else:
            print(f"all {total} templates parse")
    print(len(failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
