#!/usr/bin/env python
"""Find a raw Python object repr, or an un-filtered container value, reaching
a rendered page.

Found in production on the ArchiMate element detail page (fixed in
e30ad429): `_get_display_fields()` in
`app/modules/architecture/routes/archimate_crud/routes.py` called
`str(value)` on every column value unconditionally, so a JSON/dict column
rendered Python's literal repr -- `{'source_model': 'Risk'}` -- as page
content instead of readable text. That is a reusable anti-pattern (a generic
"introspect a model's columns, stringify each value" helper), and duplicate
breadcrumbs were independently found on at least three other pages this
session, so a single instance fixed by hand is not evidence the class is
closed -- this gate makes the class itself impossible to reintroduce
silently.

Two shapes are flagged.

  py-unchecked-str      a Python function that reads a value via
                         `getattr(obj, col, None)` (the shape of every
                         model-introspection "build display fields" helper in
                         this codebase) and later calls `str(<that value>)`
                         with no `isinstance(<value>, (dict` / `isinstance(
                         <value>, dict)` / `isinstance(<value>, (list` /
                         `isinstance(<value>, list)` guard anywhere in the
                         same function. A dict or list column sails through
                         `str()` as Python's repr, not prose.

  template-raw-container a Jinja `{{ expr }}` interpolation whose expression
                         ends in a container-shaped attribute name (a
                         `properties`/`metadata`/`config`/`attributes`
                         column -- the exact shape of the columns that broke
                         in production) with no filter (`|tojson`, `|join`,
                         `|dictsort`, a custom filter, etc.) applied. Rendering
                         a dict/list straight through Jinja's default
                         `str()` reproduces the same repr.

Escape hatch: append `raw-repr-ok: <reason>` on the flagged line (or the line
immediately above it).

Usage:
    python scripts/check_raw_repr_in_template.py            # list findings
    python scripts/check_raw_repr_in_template.py --count    # trailing = count

Proven-against: app/modules/architecture/routes/archimate_crud/routes.py
before e30ad429 -- `value = getattr(element, column.name, None)` followed by
unconditional `fields.append({"label": label, "value": str(value)})` with no
`isinstance(value, (dict, list))` guard in the function -- flagged by
py-unchecked-str; restoring the guard (as landed) clears it.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")

SKIP_DIRS = {"__pycache__", "node_modules", ".git", "vendor", "migrations", "tests"}
ALLOW = re.compile(r"raw-repr-ok:")

# Deliberately narrow to the exact shape of the bug: `value = getattr(obj,
# <non-literal column expression>, None)` inside a model-introspection loop.
# Requiring the variable be named `value` and the attribute argument be a
# name/expression (not a string literal) keeps this from matching the dozens
# of unrelated `str(name)` / `str(val)` one-offs elsewhere in the tree that a
# looser name match flagged as noise during development of this checker.
GETATTR_ASSIGN = re.compile(
    r"^\s*value\s*=\s*getattr\(\s*\w+\s*,\s*([A-Za-z_][\w.]*)\s*,\s*None\s*\)",
    re.M,
)
DEF_LINE = re.compile(r"^(\s*)def\s+\w+\s*\(")
# Signals this is a "walk the model's columns/attributes" loop, the shape
# that produced the production bug, rather than an unrelated one-off getattr.
INTROSPECTION_LOOP = re.compile(
    r"for\s+\w+\s+in\b.*(?:\.columns\b|__table__|mapper\(|inspect\()"
    r"|\.columns\b|__table__\.columns"
)
ISINSTANCE_DICT_OR_LIST_TEMPLATE = (
    r"isinstance\(\s*{var}\s*,\s*(?:\(?\s*dict|\(?\s*list|\([^)]*\b(?:dict|list)\b)"
)

CONTAINER_ATTR_SUFFIXES = (
    "properties", "metadata", "config", "attributes", "custom_fields",
    "extra_data", "custom_props", "acm_properties", "params", "settings",
)
# {{ expr }} with no `|` filter chain, where expr's last dotted/bracket
# segment is one of the container-shaped names above.
TEMPLATE_RAW = re.compile(
    r"\{\{\s*([A-Za-z_][\w.\[\]'\"]*(?:\.(?:"
    + "|".join(CONTAINER_ATTR_SUFFIXES)
    + r")))\s*\}\}"
)


def _iter_functions(lines: list[str]):
    """Yield (start_idx, end_idx_exclusive) for each top-level-or-nested `def`.

    Boundary is the next line at the same-or-lower indentation that is not
    blank and not a comment -- good enough for this codebase's formatting
    (ruff-enforced 4-space indent) without a full parse.
    """
    n = len(lines)
    for i, line in enumerate(lines):
        m = DEF_LINE.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        j = i + 1
        while j < n:
            stripped = lines[j].strip()
            if stripped and not stripped.startswith("#"):
                cur_indent = len(lines[j]) - len(lines[j].lstrip(" "))
                if cur_indent <= indent:
                    break
            j += 1
        yield i, j


def _excused(lines: list[str], idx: int) -> bool:
    if idx < len(lines) and ALLOW.search(lines[idx]):
        return True
    return idx > 0 and ALLOW.search(lines[idx - 1])


def _walk(app_dir: str, exts: tuple[str, ...]):
    for dirpath, dirnames, filenames in os.walk(app_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1] in exts:
                yield os.path.join(dirpath, fn)


def _check_python(path: str, root: str) -> list[tuple[str, int, str, str]]:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
    except OSError:
        return []
    lines = src.split("\n")
    hits = []
    seen: set[int] = set()  # line indices already reported (avoid nested-def dupes)
    for start, end in _iter_functions(lines):
        body = lines[start:end]
        body_text = "\n".join(body)
        if not GETATTR_ASSIGN.search(body_text):
            continue
        if not INTROSPECTION_LOOP.search(body_text):
            continue  # not a "walk the model's columns" loop
        var = "value"
        guard = ISINSTANCE_DICT_OR_LIST_TEMPLATE.format(var=var)
        if re.search(guard, body_text):
            continue  # the function already type-checks before stringifying
        str_call = re.compile(rf"\bstr\(\s*{var}\s*\)")
        for offset, line in enumerate(body):
            m = str_call.search(line)
            if not m:
                continue
            idx = start + offset
            if idx in seen or _excused(lines, idx):
                continue
            seen.add(idx)
            rel = os.path.relpath(path, root).replace("\\", "/")
            hits.append((rel, idx + 1, "py-unchecked-str", line.strip()[:120]))
    return hits


def _check_templates(path: str, root: str) -> list[tuple[str, int, str, str]]:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
    except OSError:
        return []
    lines = src.split("\n")
    hits = []
    for m in TEMPLATE_RAW.finditer(src):
        idx = src.count("\n", 0, m.start())
        if _excused(lines, idx):
            continue
        rel = os.path.relpath(path, root).replace("\\", "/")
        hits.append((rel, idx + 1, "template-raw-container", lines[idx].strip()[:120]))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    app_dir = os.path.join(root, "app")

    findings: list[tuple[str, int, str, str]] = []
    for path in sorted(_walk(app_dir, (".py",))):
        findings.extend(_check_python(path, root))
    for path in sorted(_walk(app_dir, (".html", ".jinja", ".j2"))):
        findings.extend(_check_templates(path, root))
    findings.sort()

    if not args.count:
        for rel, line, name, text in findings:
            print(f"{rel}:{line}: [{name}] {text}")
        if findings:
            print()
            print(
                "A dict/list value reaching str() or a bare {{ }} renders Python's\n"
                "repr as page content. Format it explicitly (e.g. '; '.join(f'{k}: {v}'\n"
                "for k, v in value.items())) or apply a template filter (|tojson,\n"
                "|join, a custom filter). If genuinely fine, append\n"
                "'raw-repr-ok: <reason>' on or above the flagged line."
            )
    print(len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
