#!/usr/bin/env python
"""Find a fact-bearing model column with no row in the intelligence wiring register.

What is flagged
----------------
A `ClassDef` under `app/models/**/*.py` or `app/modules/*/models/**/*.py` (top-level, or nested inside a
function -- this tree defines several of its models that way) that either assigns `__tablename__` in its own
body or has a base class named `Model` / `db.Model`, and whose body assigns a `Column`, `db.Column` or
`mapped_column` call to a plain attribute -- `name = db.Column(...)` -- where the attribute name matches
`FAMILY_RE` (a maturity, cost, budget, tco, licence, contract, renewal, lifecycle, end-of-life, risk,
compliance, sla, owner, raci, plateau, gap, score or one of the other families named in
`docs/intelligence-wiring-register.yml`'s `pipeline_rule.statement`) is a fact-bearing column. A first
positional string argument -- `db.Column("plateau", ...)` -- is recorded as the database column name and
tested as well as the attribute name.

A fact-bearing column is covered, and not flagged, when:

  1. a `rows[]` entry in the register names the class (comma-split, case-sensitive, exact) in `model` and
     names the column in `fields` -- bare (`health_status`), as `Class.column` (`Plateau.target_date`, for a
     row whose `model` lists more than one class), or as a path expression matched on its last identifier
     (`elements[].archimate_element_id` matches `archimate_element_id`) -- or the database column name; or
  2. a `not_intelligence[]` entry's `where` text names the class or the file's basename, and later in the same
     text names the attribute or database column name; or
  3. the column's own `db.Column(...)` line, or the line directly above it (when that line is not itself
     another column's own declaration -- the same rule `check_unrendered_model_fields.py` uses), carries
     `wiring-ok: IW-nn <reason>` where `IW-nn` is a real id in the register and `<reason>` is at least two
     words. A marker whose id is not in the register does not suppress the finding -- it is reported, with a
     note that the marker has no effect, so a typo'd id cannot silently defeat the ratchet.

Scope and disclosed limits
---------------------------
Any path segment `tests` is excluded. Association tables built with `db.Table(...)` are not classes and are
out of scope -- disclosed, not silent. A column named outside the families above is not seen at all; adding a
new family is a register change (`pipeline_rule.statement`), not a checker change. Coverage is by name, not by
semantics: a row naming `status` on a class covers every `status` column that class has, however different
their meaning. A missing or unparseable register is a hard failure (exit 2), never a count of 0 -- silence here
must never look like "no debt".

Usage
-----
    python scripts/check_wiring_rows.py                 # list findings
    python scripts/check_wiring_rows.py --count          # trailing count only
    python scripts/check_wiring_rows.py --list            # list findings explicitly
    python scripts/check_wiring_rows.py --root <tree>      # scan a different tree (tests)
    python scripts/check_wiring_rows.py --register <path>  # read a different register (tests)

Proven-against: tests/test_wiring_rows_gate.py -- a positive control (an unregistered fact-bearing column is
flagged), a negative control (a register row, and separately a not_intelligence entry, suppresses it), the
escape hatch on the column's own line and the line above (and its refusal to honour a marker whose id is not
registered), the family boundary (`user_count`/`description` never flagged; `eol_date`/`is_baseline`/
`rto_hours`/`owner_id` flagged), a class nested inside a function, a database-column-name match, and a missing
register exiting 2.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parent.parent

FAMILY_RE = re.compile(
    r"(^|_)(maturity|assessment|health|cost|budget|tco|spend|licen[cs]e|renewal|contract|vendor|lifecycle|"
    r"eol|eos|retire(?:ment)?|decommission|risk|compliance|control|sla|availability|rto|rpo|criticality|"
    r"owner|raci|usage|plateau|gap|roadmap|milestone|baseline|drift|score)(_|$)"
)

_COLUMN_CALL_NAMES = {"Column", "mapped_column"}
_ESCAPE_RE = re.compile(r"wiring-ok:\s*(IW-[0-9]{2,})(?:\s+(\S.*?))?\s*$")
_DOTTED_FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass
class Finding:
    path: str
    lineno: int
    cls: str
    attr: str
    note: str = ""

    def render(self) -> str:
        base = f"{self.path}:{self.lineno} {self.cls}.{self.attr}"
        return f"{base} ({self.note})" if self.note else base


@dataclass
class Register:
    rows: list = field(default_factory=list)
    not_intelligence: list = field(default_factory=list)
    wiring_ids: set = field(default_factory=set)


def _load_register(path: Path) -> tuple[Register | None, str | None]:
    if yaml is None:
        return None, "PyYAML is not available; cannot read the intelligence wiring register"
    if not path.exists():
        return None, f"register file not found at {path}"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, f"register file at {path} did not parse: {exc}"
    if not isinstance(data, dict) or "rows" not in data or "not_intelligence" not in data:
        return None, f"register file at {path} did not parse into rows/not_intelligence"
    rows = data.get("rows") or []
    not_intelligence = data.get("not_intelligence") or []
    ids = {r["id"] for r in rows if isinstance(r, dict) and "id" in r}
    ids |= {r["id"] for r in not_intelligence if isinstance(r, dict) and "id" in r}
    return Register(rows=rows, not_intelligence=not_intelligence, wiring_ids=ids), None


def _iter_model_files(root: Path):
    seen: set[Path] = set()
    bases = [root / "app" / "models"]
    modules_dir = root / "app" / "modules"
    if modules_dir.is_dir():
        for module_dir in sorted(modules_dir.iterdir()):
            models_dir = module_dir / "models"
            if models_dir.is_dir():
                bases.append(models_dir)
    for base in bases:
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if "tests" in p.relative_to(root).parts:
                continue
            if p not in seen:
                seen.add(p)
                yield p


def _is_column_call(node) -> bool:
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    if isinstance(f, ast.Name):
        return f.id in _COLUMN_CALL_NAMES
    if isinstance(f, ast.Attribute):
        return f.attr in _COLUMN_CALL_NAMES
    return False


def _first_positional_string(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


def _class_qualifies(cdef: ast.ClassDef) -> bool:
    for base in cdef.bases:
        name = None
        if isinstance(base, ast.Name):
            name = base.id
        elif isinstance(base, ast.Attribute):
            name = base.attr
        if name == "Model":
            return True
    for stmt in cdef.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == "__tablename__":
                    return True
    return False


def _column_assigns(cdef: ast.ClassDef):
    """[(attr_name, db_col_name_or_None, lineno)] for each column declared directly in cdef's own body."""
    out = []
    for stmt in cdef.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            continue
        if not _is_column_call(stmt.value):
            continue
        out.append((stmt.targets[0].id, _first_positional_string(stmt.value), stmt.lineno))
    return out


def _last_identifier(s: str) -> str:
    idents = _IDENT_RE.findall(s)
    return idents[-1] if idents else s


def _row_covers(row: dict, cls: str, names: set[str]) -> bool:
    model_field = row.get("model") or ""
    classes = [c.strip() for c in str(model_field).split(",") if c.strip()]
    if cls not in classes:
        return False
    for f in row.get("fields") or []:
        f = str(f)
        m = _DOTTED_FIELD_RE.match(f)
        if m:
            fcls, fcol = m.group(1), m.group(2)
            if fcls == cls and fcol in names:
                return True
            continue
        if _last_identifier(f) in names:
            return True
    return False


def _not_intelligence_covers(entry: dict, cls: str, names: set[str], basename: str) -> bool:
    where = entry.get("where") or []
    text = " ".join(str(w) for w in where)
    markers = [m for m in (cls, basename) if m and m in text]
    if not markers:
        return False
    pos = min(text.index(m) for m in markers)
    rest = text[pos:]
    return any(re.search(rf"\b{re.escape(n)}\b", rest) for n in names)


def _is_covered(cls: str, attr: str, dbcol: str | None, basename: str, register: Register) -> bool:
    names = {attr}
    if dbcol:
        names.add(dbcol)
    for row in register.rows:
        if _row_covers(row, cls, names):
            return True
    for entry in register.not_intelligence:
        if _not_intelligence_covers(entry, cls, names, basename):
            return True
    return False


def _escape_marker(lines: list[str], lineno: int, column_lines: set[int]):
    candidates = []
    if 1 <= lineno <= len(lines):
        candidates.append(lines[lineno - 1])
    above = lineno - 1
    if above >= 1 and above not in column_lines:
        candidates.append(lines[above - 1])
    for c in candidates:
        m = _ESCAPE_RE.search(c)
        if m:
            return m.group(1), (m.group(2) or "").strip()
    return None


def _scan_file(path: Path, root: Path, register: Register) -> list[Finding]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    lines = src.splitlines()
    rel = str(path.relative_to(root)).replace(os.sep, "/")
    basename = path.name

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _class_qualifies(node):
            continue
        assigns = _column_assigns(node)
        column_lines = {lineno for _a, _d, lineno in assigns}
        for attr, dbcol, lineno in assigns:
            if not FAMILY_RE.search(attr):
                continue
            if _is_covered(node.name, attr, dbcol, basename, register):
                continue
            marker = _escape_marker(lines, lineno, column_lines)
            if marker is not None:
                marker_id, reason = marker
                if marker_id in register.wiring_ids and len(reason.split()) >= 2:
                    continue  # suppressed
                if marker_id not in register.wiring_ids:
                    findings.append(Finding(rel, lineno, node.name, attr,
                                             note=f"wiring-ok marker {marker_id} is not in the register; has no effect"))
                    continue
            findings.append(Finding(rel, lineno, node.name, attr))
    return findings


def scan(root: Path, register: Register) -> list[Finding]:
    findings: list[Finding] = []
    for path in _iter_model_files(root):
        findings.extend(_scan_file(path, root, register))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", action="store_true", help="print only the trailing count")
    parser.add_argument("--list", action="store_true", help="print each finding (default when --count is absent)")
    parser.add_argument("--root", default=str(ROOT), help="scan a different tree (tests)")
    parser.add_argument("--register", default=None, help="read a different register file (tests)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    register_path = Path(args.register) if args.register else root / "docs" / "intelligence-wiring-register.yml"
    register, err = _load_register(register_path)
    if register is None:
        print(err, file=sys.stderr)
        return 2

    findings = scan(root, register)

    if args.count:
        print(len(findings))
        return 0

    if findings:
        for finding in findings:
            print(finding.render())
        print(f"\n{len(findings)} fact-bearing model column(s) with no row in the intelligence wiring register.")
        print("Add a row (wired, or not_intelligence with a reason) to docs/intelligence-wiring-register.yml, "
              "or mark 'wiring-ok: IW-nn <reason>' on the column line.")
    else:
        print("No fact-bearing model columns found with no row in the intelligence wiring register.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
