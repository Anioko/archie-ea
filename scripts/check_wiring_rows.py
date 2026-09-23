#!/usr/bin/env python
"""Find a fact-bearing model column with no row in the intelligence wiring register.

What is flagged
----------------
A `ClassDef` under `app/models/**/*.py` or `app/modules/*/models/**/*.py` (top-level, or nested inside a
function -- this tree defines several of its models that way) that either assigns `__tablename__` in its own
body or has a base class named `Model` / `db.Model`, and whose body assigns a `Column`, `db.Column` or
`mapped_column` call to a plain attribute -- `name = db.Column(...)` or the SQLAlchemy 2.0 `name: Mapped[str]
= mapped_column(...)` shape -- where the attribute name matches `FAMILY_RE` (a maturity, cost, budget, tco,
licence, contract, renewal, lifecycle, end-of-life, risk, compliance, sla, owner, raci, plateau, gap, score or
one of the other families named in `docs/intelligence-wiring-register.yml`'s `pipeline_rule.statement`) is a
fact-bearing column. A first positional string argument -- `db.Column("plateau", ...)` -- is recorded as the
database column name and tested as well as the attribute name. Each family is matched in every spelling the
tree uses for it -- singular, plural, past tense, agent and gerund forms, plus `ownership`, `critical`,
`compliant`, `end_of_life`, `eos`, `retired`, `licensing` -- so `end_of_life_date`, `last_assessed`,
`key_risks`, `other_costs` and `assessor` are fact-bearing; `controller`, `discount`, `scorecard` and
`healthy` are not.

A fact-bearing column is covered, and not flagged, when:

  1. a `rows[]` entry in the register names the class (comma-split, case-sensitive, exact) in `model` and
     names the column in `fields` -- bare (`health_status`), as `Class.column` (`Plateau.target_date`, for a
     row whose `model` lists more than one class), or as a path expression matched on its last identifier
     (`elements[].archimate_element_id` matches `archimate_element_id`) -- or the database column name; or
  2. a `not_intelligence[]` entry's `where` text names the class or the file's basename as a whole word (not
     merely a substring -- a `where` naming `RiskEntityLink` does not name `Risk`), and later in the same text
     names the attribute or database column name, also as a whole word; or
  3. any line of the column's own declaration (its first line through the last, so a multi-line
     `db.Column(...)` call is covered by a marker on any of its lines, including a closing-paren line), or
     the line directly above the declaration's first line (when that line is not itself part of another
     column's own declaration -- the same rule `check_unrendered_model_fields.py` uses), carries
     `wiring-ok: IW-nn <reason>` where `IW-nn` is a real id in the register and `<reason>` is at least two
     words. A marker whose id is not in the register does not suppress the finding -- it is reported, with a
     note that the marker has no effect, so a typo'd id cannot silently defeat the ratchet.

Scope and disclosed limits
---------------------------
Any path segment `tests` is excluded. Association tables built with `db.Table(...)` are not classes and are
out of scope -- disclosed, not silent. A column named outside the families above is not seen at all; adding a
new family is a register change (`pipeline_rule.statement`), not a checker change. Coverage is by name, not by
semantics: a row naming `status` on a class covers every `status` column that class has, however different
their meaning. A column declared on a mixin (a class with no `Model` base and no `__tablename__`) is not seen;
the model that inherits it is not scanned for inherited columns. A missing or unparseable register is a hard
failure (exit 2), never a count of 0 -- silence here must never look like "no debt".

Base diff
---------
`--base [ref]` scans the base tree at `ref` (its `app/models` and, where present, `app/modules`, exported with
`git archive` into a temporary directory) with the same, branch-side register, and lists the findings present
on the working tree and absent at the base -- keyed on `(path, class, attribute)`, so a line moving within an
unchanged declaration is not counted as added. With no explicit ref, `ref` resolves through the same
merge-base-with-`origin/main` fallback chain `check_smoke_coverage_on_change.py` uses. Exit codes: 0 nothing
added, 1 one or more findings added, 2 the register did not parse (as above), 3 the base ref could not be
resolved -- nothing is printed to stdout in that case, so a shallow clone or an offline sandbox cannot be read
as "nothing added".

Usage
-----
    python scripts/check_wiring_rows.py                 # list findings
    python scripts/check_wiring_rows.py --count          # trailing count only
    python scripts/check_wiring_rows.py --list            # list findings explicitly
    python scripts/check_wiring_rows.py --root <tree>      # scan a different tree (tests)
    python scripts/check_wiring_rows.py --register <path>  # read a different register (tests)
    python scripts/check_wiring_rows.py --base [ref]  # list findings added since ref (default: merge-base with origin/main)

Proven-against: tests/test_wiring_rows_gate.py -- a positive control (an unregistered fact-bearing column is
flagged), a negative control (a register row, and separately a not_intelligence entry, suppresses it; a row or
a not_intelligence entry naming a different, merely similarly-spelled class does not), the escape hatch on the
column's own line, a closing-paren line of a multi-line declaration, and the line above (and its refusal to
honour a marker whose id is not registered, and its refusal to leak onto the next column), the family boundary,
a class nested inside a function, a database-column-name match, the `AnnAssign` (`Mapped[...]`) column shape, a
mixin column staying unseen, a missing register exiting 2, and the base-diff mode's positive, negative and
unresolvable-ref controls.
"""
from __future__ import annotations

import argparse
import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parent.parent

FAMILY_RE = re.compile(
    r"(^|_)(maturit(?:y|ies)|assess(?:ment|ments|ed|or|ors)?|health|costs?|costing|budgets?|budgeted|tco|spend(?:ing)?|"
    r"licen[cs](?:e|es|ed|ing)|renewals?|renewed|contracts?|contracted|contracting|vendors?|lifecycle|end_of_life|eol|eos|"
    r"retire(?:ment|d|s)?|decommission(?:ed|ing)?|risks?|risky|complian(?:ce|t)|controls?|slas?|availability|rto|rpo|"
    r"criticality|critical|owner(?:s|ship)?|owned|raci|usage|plateaus?|gaps?|roadmaps?|milestones?|baselines?|baselined|"
    r"drifts?|drifted|scores?|scored|scoring)(_|$)"
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
    """[(attr_name, db_col_name_or_None, lineno, end_lineno)] for each column declared directly in cdef's own
    body -- a plain `Assign` (`name = db.Column(...)`) or an annotated `AnnAssign`
    (`name: Mapped[str] = mapped_column(...)`)."""
    out = []
    for stmt in cdef.body:
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                continue
            target = stmt.targets[0]
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            if not isinstance(stmt.target, ast.Name) or stmt.value is None:
                continue
            target = stmt.target
            value = stmt.value
        else:
            continue
        if not _is_column_call(value):
            continue
        end_lineno = getattr(stmt, "end_lineno", None) or stmt.lineno
        out.append((target.id, _first_positional_string(value), stmt.lineno, end_lineno))
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
    positions = []
    for m in (cls, basename):
        if not m:
            continue
        found = re.search(rf"\b{re.escape(m)}\b", text)
        if found:
            positions.append(found.start())
    if not positions:
        return False
    pos = min(positions)
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


def _escape_marker(lines: list[str], lineno: int, end_lineno: int, column_lines: set[int]):
    candidates = []
    for ln in range(lineno, end_lineno + 1):
        if 1 <= ln <= len(lines):
            candidates.append(lines[ln - 1])
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
        column_lines: set[int] = set()
        for _a, _d, lineno, end_lineno in assigns:
            column_lines.update(range(lineno, end_lineno + 1))
        for attr, dbcol, lineno, end_lineno in assigns:
            if not FAMILY_RE.search(attr):
                continue
            if _is_covered(node.name, attr, dbcol, basename, register):
                continue
            marker = _escape_marker(lines, lineno, end_lineno, column_lines)
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


# ---------------------------------------------------------------- base diff


def _resolve_base_ref(ref: str) -> str:
    if ref != "auto":
        return ref
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_smoke_coverage_on_change import _base_ref  # real reuse, not a copy
    return _base_ref()


def _verify_ref(ref: str, root: Path) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd=root, capture_output=True, text=True,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def _base_tree_paths(ref: str, root: Path) -> list[str]:
    paths = ["app/models"]
    proc = subprocess.run(["git", "cat-file", "-e", f"{ref}:app/modules"], cwd=root, capture_output=True)
    if proc.returncode == 0:
        paths.append("app/modules")
    return paths


def _export_base_tree(ref: str, root: Path) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="wiring-rows-base-"))
    paths = _base_tree_paths(ref, root)
    proc = subprocess.run(["git", "archive", ref, *paths], cwd=root, capture_output=True)
    if proc.returncode == 0 and proc.stdout:
        with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tf:
            tf.extractall(dest)
    return dest


def _run_base_diff(base_arg: str, root: Path, register: Register, findings: list[Finding], count_only: bool) -> int:
    ref = _resolve_base_ref(base_arg)
    if not _verify_ref(ref, root):
        print(f"base ref {ref} cannot be resolved; added-findings check not run", file=sys.stderr)
        return 3

    base_root = _export_base_tree(ref, root)
    try:
        base_findings = scan(base_root, register)
    finally:
        shutil.rmtree(base_root, ignore_errors=True)

    base_keys = {(f.path, f.cls, f.attr) for f in base_findings}
    added = [f for f in findings if (f.path, f.cls, f.attr) not in base_keys]

    if count_only:
        print(len(added))
        return 1 if added else 0

    for f in added:
        print(f.render())
    if added:
        print(f"\n{len(added)} fact-bearing column(s) added since {ref} with no row in the intelligence wiring register.")
        print("Add a row (wired, or not_intelligence with a reason) to docs/intelligence-wiring-register.yml, "
              "or mark 'wiring-ok: IW-nn <reason>' on the column line.")
    else:
        print(f"No fact-bearing model columns added since {ref} with no row in the intelligence wiring register.")
    return 1 if added else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", action="store_true", help="print only the trailing count")
    parser.add_argument("--list", action="store_true", help="print each finding (default when --count is absent)")
    parser.add_argument("--root", default=str(ROOT), help="scan a different tree (tests)")
    parser.add_argument("--register", default=None, help="read a different register file (tests)")
    parser.add_argument("--base", nargs="?", const="auto", default=None,
                         help="list findings added since ref (default: merge-base with origin/main)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    register_path = Path(args.register) if args.register else root / "docs" / "intelligence-wiring-register.yml"
    register, err = _load_register(register_path)
    if register is None:
        print(err, file=sys.stderr)
        return 2

    findings = scan(root, register)

    if args.base is not None:
        return _run_base_diff(args.base, root, register, findings, args.count)

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
