#!/usr/bin/env python
"""A Jinja expression opened inside another one renders as literal text.

From the 30 Aug 2026 QA audit, High #15:

    "The page's <h1> literally renders the unescaped template expression
     {{ framework.industry_name }} instead of interpolating the value, even
     though the breadcrumb one line above correctly shows the resolved name --
     a template-binding bug, not a data problem."

The line was:

    {{ page_header(title='{{ framework.industry_name }}') }}

The inner expression sits inside a STRING LITERAL, so Jinja passes the seven
words through untouched and the page title reads, to a customer, as a broken
template. It is a plausible thing to write -- the surrounding markup is full of
`{{ ... }}`, and quoting a macro argument is normally right.

Nothing else sees it. The template parses (it is valid Jinja), the route returns
200, no console error is raised, and every other gate is happy. Only a person
reading the rendered heading, or this, can tell.

Detection is exact rather than heuristic: scan the raw text tracking `{{` /
`}}` depth, and report any `{{` that opens while depth is already above zero.
That is unambiguous -- Jinja does not nest expressions -- so a finding is a
fact. An earlier regex attempt matched any `{{ ... 'string' ... }}` and
returned 204 findings, nearly all of them ordinary macro calls; it was
discarded rather than baselined.

Note what this deliberately does NOT flag: `{{ ... }}` inside a quoted HTML
attribute, e.g. `x-show='matches({{ x | tojson }})'`. That is the correct way to
render a value into an attribute, and it is not nested, because the outer quote
is HTML rather than Jinja.

Escape hatch: `nested-jinja-ok: <reason>` on the line.

    python scripts/check_nested_jinja.py
    python scripts/check_nested_jinja.py --count

Proven-against: `{{ page_header(title='{{ framework.industry_name }}') }}`
restored in industry_apqc/framework_detail.html -- red at 1 naming that line,
green at 0 when the argument was unquoted again.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"nested-jinja-ok:[ \t]*\S")
SUFFIXES = (".html", ".jinja", ".jinja2")


def _template_dirs(root: str):
    yield os.path.join(root, "app", "templates")
    modules = os.path.join(root, "app", "modules")
    if os.path.isdir(modules):
        for name in sorted(os.listdir(modules)):
            candidate = os.path.join(modules, name, "templates")
            if os.path.isdir(candidate):
                yield candidate


def nested_offsets(source: str) -> list[int]:
    """Offsets of every ``{{`` that opens while another is still open."""
    offsets: list[int] = []
    depth = 0
    index = 0
    end = len(source) - 1
    while index < end:
        pair = source[index:index + 2]
        if pair == "{{":
            if depth > 0:
                offsets.append(index)
            depth += 1
            index += 2
            continue
        if pair == "}}":
            depth = max(0, depth - 1)
            index += 2
            continue
        index += 1
    return offsets


def scan(root: str) -> list[str]:
    problems = []
    for base in _template_dirs(root):
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in sorted(filenames):
                if not filename.endswith(SUFFIXES):
                    continue
                path = os.path.join(dirpath, filename)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                try:
                    with open(path, encoding="utf-8") as fh:
                        source = fh.read()
                except (OSError, UnicodeDecodeError):
                    continue
                lines = source.split("\n")
                for offset in nested_offsets(source):
                    number = source[:offset].count("\n") + 1
                    line = lines[number - 1] if number <= len(lines) else ""
                    if ALLOW.search(line):
                        continue
                    problems.append(
                        "%s:%d [nested-jinja] a {{ expression opens inside another "
                        "one -- Jinja renders the inner one as literal text on the "
                        "page" % (rel, number)
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
                "Pass the value itself rather than a quoted placeholder:\n"
                "  {{ page_header(title=framework.industry_name) }}\n"
                "not\n"
                "  {{ page_header(title='{{ framework.industry_name }}') }}\n"
                "Or append 'nested-jinja-ok: <reason>' if the literal text is intended."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
