#!/usr/bin/env python
"""Every `{% include %}` / `{% extends %}` target must exist on disk.

`template-syntax` proves a template *parses*. It says nothing about whether the
files that template pulls in are actually there, because Jinja resolves
`include`/`extends` at render time — so a missing partial is invisible until a
user opens the page, and then it is a TemplateNotFound 500, not a gap in the
layout.

Found three of these in one sweep:

  * `auth/register.html` and `admin/security.html` both did
    `{% extends 'base.html' %}`. The base template lives at
    `layouts/base.html`; there is no `base.html` at the template root. Both
    survive today only because the blueprints that render them are not
    currently registered — the moment either is wired up, the page 500s.
  * `applications/detail.html` includes nine `application_mgmt/partials/_*_tab`
    partials, of which one exists. That file is rendered by no route at all,
    which is the only reason it has not been noticed; it also means the entire
    per-application ArchiMate layer UI it contains has never worked.

Dynamic targets (`{% include some_var %}`, or a name built with `{{ }}`) cannot
be resolved statically and are skipped rather than guessed at — this reports
what it can prove, and stays silent about the rest.

Usage:
    python scripts/check_template_references.py            # list broken references
    python scripts/check_template_references.py --count    # trailing line = count
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_ROOTS = [os.path.join(ROOT, "app", "templates")]

# Module-local template folders (app/modules/<domain>/templates), same
# convention scripts/check_template_syntax.py follows.
#
# `solutions_product` is excluded deliberately. Its trees (go_chi/,
# python_fastapi/, …) are code-generation scaffolds consumed by
# app/modules/codegen and written out as files — nothing renders them through
# Flask. Their `{% include %}` targets resolve inside the *generated* project,
# so checking them here reports 14 failures that are not failures.
CODEGEN_MODULES = {"solutions_product"}

_MODULES = os.path.join(ROOT, "app", "modules")
if os.path.isdir(_MODULES):
    for _entry in sorted(os.listdir(_MODULES)):
        if _entry in CODEGEN_MODULES:
            continue
        _candidate = os.path.join(_MODULES, _entry, "templates")
        if os.path.isdir(_candidate):
            TEMPLATE_ROOTS.append(_candidate)

# Flask renders .html/.jinja here; .j2 is the codegen convention in this repo.
SUFFIXES = (".html", ".jinja")

# {% include "x.html" %} / {% extends 'x.html' %} / {% import %} / {% from %}
REFERENCE = re.compile(
    r"{%-?\s*(?:include|extends|import|from)\s+['\"]([^'\"]+)['\"]"
)


def _is_dynamic(target: str) -> bool:
    """A target built at render time cannot be checked from here."""
    return "{" in target or "%" in target


def _resolve(target: str) -> bool:
    return any(os.path.isfile(os.path.join(root, target)) for root in TEMPLATE_ROOTS)


def find_broken_references():
    """Yield (template_path, missing_target), sorted and de-duplicated."""
    seen = set()
    for root in TEMPLATE_ROOTS:
        for dirpath, _dirs, files in os.walk(root):
            for filename in sorted(files):
                if not filename.endswith(SUFFIXES):
                    continue
                path = os.path.join(dirpath, filename)
                try:
                    with open(path, encoding="utf-8", errors="replace") as handle:
                        source = handle.read()
                except OSError:
                    continue
                for target in REFERENCE.findall(source):
                    if _is_dynamic(target) or _resolve(target):
                        continue
                    rel = os.path.relpath(path, ROOT).replace("\\", "/")
                    if (rel, target) not in seen:
                        seen.add((rel, target))
                        yield rel, target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", action="store_true",
                        help="print only the count, as the trailing line")
    args = parser.parse_args()

    broken = sorted(find_broken_references())

    if not args.count:
        if not broken:
            print("No broken template references.")
        else:
            current = None
            for template, target in broken:
                if template != current:
                    current = template
                    print(template)
                print(f"    -> {target}")
            print(f"\n{len(broken)} broken reference(s).")
    else:
        print(len(broken))
    return 0


if __name__ == "__main__":
    sys.exit(main())
