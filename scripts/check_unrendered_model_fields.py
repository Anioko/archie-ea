#!/usr/bin/env python
"""Find a detail-view template that never renders a text/JSON field its own
model declares.

Motivating case: `app/templates/architecture_decisions/detail.html` rendered
`context`, `decision`, `consequences` and `alternatives` from
`ArchitectureDecision`, but not `rationale`, `constraints`, or the GOV-02
approval trail (`decided_by`/`decided_at`/`approved_by`/`approved_at`/
`rejection_reason`) -- all real columns a real workflow writes
(`ADRService`/`adr_routes.py`'s approve/reject routes). The page looked
"empty" for approved and rejected decisions because their most important
content had nowhere to render. Found by hand; this makes it a measurement.

What is flagged
----------------
A Python route function that:

1. fetches a single row via `<Model>.query.get_or_404(...)` or
   `<Model>.query.get(...)`, assigned to a local variable, and
2. calls `render_template("<path>", ...)` in the same function

is a "detail view" of `<Model>` rendering `<path>`. For each such pairing,
this script resolves `<Model>`'s source file (a `class <Model>(...):` in
`app/models/**/*.py`), extracts its `Text` and `JSON` columns (the content
fields most likely to carry the "why"/"what" of a record -- Integer/Boolean/
DateTime columns are excluded: usually ids, flags or timestamps already
covered by other checks, and including them found nothing but noise in
practice), and checks whether each one appears anywhere in the rendered
template's own source text (a name match, not a full Jinja variable-flow
analysis) or in any partial that template `{% include %}`s (one level).

A field is flagged only when NONE of: the template, its includes, or a
`.gitignore`-parallel per-field escape all mention it.

Scope limitation (disclosed, not silent): this is a heuristic name match, not
type-aware Jinja analysis. It does not know which template variable holds the
`<Model>` instance versus something else, so a template that happens to
contain the field name in unrelated prose will read as covered (a false
negative, not a false positive -- this script undercounts, it does not cry
wolf). It does not follow `to_dict()`/JSON-API responses at all -- a field
exposed only through an API a JS component reads is invisible to it, so a
frontend gap of that shape needs a different check, not this one. It also
only looks one function deep for the `render_template` call: a route that
delegates rendering to a helper is not seen. These are the same trade-offs
`check_crosswalk_writer_gated.py` documents for its own one-level traversal
-- cheap and directionally reliable beats exhaustive and unmaintainable.

Escape hatch
------------
`unrendered-field-ok: <reason>` on the field's own `db.Column(...)` line (or
the line above it) suppresses that one field for that one model -- e.g. a
column that is genuinely write-only (an internal audit marker never meant for
display), or one rendered through a mechanism this script cannot see (an API
response, a PDF export). Bare `unrendered-field-ok` with no reason does not
suppress.

Usage
-----
    python scripts/check_unrendered_model_fields.py            # list findings
    python scripts/check_unrendered_model_fields.py --count    # trailing count

Proven-against: tests/test_unrendered_model_fields_gate.py, which caught a
real bug in its own first draft, not just the checker's: the escape-hatch's
"check the line above too" rule let a trailing `unrendered-field-ok:` marker
on one column's line suppress the very next column as well, because that
next column's "line above" was the marked line. The positive/negative/escape
controls (fake Widget model + template on disk) went red on the escape
control specifically, not a contrived failure -- fixed by only counting the
line above when it is not itself another column's own declaration.
"""
from __future__ import annotations

import argparse
import ast
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")

SKIP_DIRS = {"__pycache__", "node_modules", ".git", "vendor", "migrations"}

# Columns that are structural/bookkeeping rather than content a reader would
# expect to see spelled out on a detail page. Kept short and reviewed by
# hand -- a name landing here is a judgment call, not a mechanical rule.
EXCLUDED_FIELD_NAMES = {
    "id", "created_at", "updated_at", "organization_id",
    "source_table", "source_id", "decision_id",
}
EXCLUDED_SUFFIXES = ("_id",)  # foreign keys: usually surfaced via a relationship, not the raw id

ESCAPE_RE = re.compile(r"unrendered-field-ok:[ \t]*\S")

COLUMN_RE = re.compile(
    r"^\s*(\w+)\s*=\s*(?:db\.)?Column\(\s*(?:db\.)?(Text|JSON)\b", re.MULTILINE
)


def _iter_py_files(base: str):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def _model_content_fields(model_name: str) -> tuple[str, list[str]] | None:
    """Find `class <model_name>(...` and return (file, [text/json field names])."""
    pattern = re.compile(r"^class\s+" + re.escape(model_name) + r"\s*\(", re.MULTILINE)
    for path in _iter_py_files(os.path.join(APP, "models")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                src = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        m = pattern.search(src)
        if not m:
            continue
        # Class body: from the match to the next top-level `class ` or EOF.
        rest = src[m.end():]
        next_class = re.search(r"^class\s+\w+\s*\(", rest, re.MULTILINE)
        body = rest[: next_class.start()] if next_class else rest
        lines = body.splitlines()
        fields = []
        for i, line in enumerate(lines):
            col = COLUMN_RE.match(line)
            if not col:
                continue
            name = col.group(1)
            if name in EXCLUDED_FIELD_NAMES or name.endswith(EXCLUDED_SUFFIXES):
                continue
            candidates = [line]
            # The line above counts only when it is NOT itself another
            # column's own declaration -- otherwise a trailing marker on one
            # field's line reads as "the line above" for the very next field
            # and wrongly suppresses it too.
            if i > 0 and not COLUMN_RE.match(lines[i - 1]):
                candidates.append(lines[i - 1])
            if any(ESCAPE_RE.search(c) for c in candidates):
                continue
            fields.append(name)
        return path, fields
    return None


def _template_includes(template_path: str) -> list[str]:
    try:
        with open(template_path, "r", encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return []
    return re.findall(r"\{%-?\s*include\s+['\"]([^'\"]+)['\"]", src)


def _template_mentions(template_path: str, field: str, seen: set[str] | None = None) -> bool:
    seen = seen or set()
    if template_path in seen:
        return False
    seen.add(template_path)
    try:
        with open(template_path, "r", encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return False
    if re.search(r"\b" + re.escape(field) + r"\b", src):
        return True
    for inc in _template_includes(template_path):
        inc_path = os.path.join(APP, "templates", inc.lstrip("/"))
        if os.path.exists(inc_path) and _template_mentions(inc_path, field, seen):
            return True
    return False


def _find_get_or_404_model(func: ast.FunctionDef) -> str | None:
    """First `<Name>.query.get_or_404(...)` / `.get(...)` call's <Name>, if any."""
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr in ("get_or_404", "get")):
            continue
        # f.value should be <Name>.query
        query_attr = f.value
        if not (isinstance(query_attr, ast.Attribute) and query_attr.attr == "query"):
            continue
        model_expr = query_attr.value
        if isinstance(model_expr, ast.Name):
            return model_expr.id
    return None


def _find_render_template_path(func: ast.FunctionDef) -> str | None:
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "render_template"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            return node.args[0].value
    return None


def scan_route_file(path: str) -> list[tuple[str, str, str, list[str]]]:
    """Returns [(route_file, model_name, template_path, [unrendered fields])]."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        model_name = _find_get_or_404_model(node)
        if not model_name:
            continue
        template_rel = _find_render_template_path(node)
        if not template_rel:
            continue
        resolved = _model_content_fields(model_name)
        if not resolved:
            continue
        _model_file, fields = resolved
        if not fields:
            continue
        template_path = os.path.join(APP, "templates", template_rel)
        if not os.path.exists(template_path):
            continue
        missing = [f for f in fields if not _template_mentions(template_path, f)]
        if missing:
            findings.append((path, model_name, template_rel, missing))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", action="store_true", help="print only the total count")
    args = parser.parse_args()

    route_files = sorted(
        set(glob.glob(os.path.join(APP, "**", "routes*.py"), recursive=True))
        | set(glob.glob(os.path.join(APP, "**", "routes", "*.py"), recursive=True))
    )
    route_files = [p for p in route_files if not any(sd in p.split(os.sep) for sd in SKIP_DIRS)]

    total = 0
    report: list[str] = []
    for path in route_files:
        for route_file, model_name, template_rel, missing in scan_route_file(path):
            total += len(missing)
            rel = os.path.relpath(route_file, ROOT)
            report.append(
                f"{rel}: {model_name} -> templates/{template_rel} never renders: "
                f"{', '.join(sorted(missing))}"
            )

    if args.count:
        print(total)
        return 0

    if report:
        print("\n".join(sorted(set(report))))
        print(f"\n{total} model field(s) written but never rendered on their own detail view.")
        print("Render the field, or mark a deliberate exception with "
              "'unrendered-field-ok: <reason>' on the column's def line or the line above it.")
    else:
        print(f"No unrendered detail-view fields found across {len(route_files)} route file(s).")

    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
