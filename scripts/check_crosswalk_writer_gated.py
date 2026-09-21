#!/usr/bin/env python
"""Catch a write to the external identity crosswalk table with no allowlist gate.

`external_identity_crosswalk` is where an external connector's identifier
gets resolved to an internal element. There is deliberately no writer to
this table yet in this codebase -- the write path (and the table itself)
ships later -- but the gate that must sit in front of that write
(`assert_connector_permitted` in
`app/modules/intelligence/services/connector_allowlist.py`) ships now, and
this script is what keeps it load-bearing: the day a writer is added, this
check either finds `assert_connector_permitted` on its call path or fails
the build.

What is flagged
----------------
Any Python function that issues a write (INSERT/UPDATE/session.add/.merge/
a raw SQL statement, etc.) against a table/model literally named
`external_identity_crosswalk` (case-insensitive, matching either the raw
table name or a model class name containing `ExternalIdentityCrosswalk`),
where none of the following holds:

1. the function itself contains a real AST call to `assert_connector_permitted`
   (a bare-name call, or an attribute call such as `module.assert_connector_
   permitted(...)` / `self.assert_connector_permitted(...)`);
2. the function calls another function in the same module (by bare name)
   whose own body contains such a call; or
3. every same-file caller of this function calls the gate before calling it
   (a public method gates, then delegates the actual
   write to a private helper method).

Call detection is real AST traversal (`ast.Call` nodes), never a source-text
substring match -- a comment or docstring mentioning the gate's name does not
satisfy it.

Scope limitation (disclosed, not silent): this is a same-file, one-level
static call-graph check in both directions -- one level of callee traversal
(item 2) and one level of caller traversal (item 3). It will NOT catch
gating done two or more calls up or down the chain, and it will NOT see
gating done in a different file. That is an acceptable trade here because
the thing being guarded against is "a writer exists with the gate call site
nowhere in its own function, its direct callees, or its direct callers",
which this script can see; anything requiring more indirection than that
would also, in practice, be visible on a `grep -rn assert_connector_permitted`
review of that PR.

Escape hatch
------------
A finding is suppressed only when the specific line defining the flagged
function (or the line immediately above it) carries a reviewable marker:
`crosswalk-gate-ok: <reason>`. The marker must carry a non-empty reason and
only suppresses the one finding it is attached to -- it is not a file-wide
switch.

Usage
-----
    python scripts/check_crosswalk_writer_gated.py                  # scan the app/ tree
    python scripts/check_crosswalk_writer_gated.py --count          # print violation count only
    python scripts/check_crosswalk_writer_gated.py FILE [FILE ...]  # scan specific files

Proven-against: tests/test_crosswalk_writer_gated_gate.py, which exercises
this scanner directly against fake files on disk covering an ungated write
(flagged), a gate name appearing only in a docstring/comment (still flagged
-- not a substring match), a directly gated write (not flagged), the
gate-then-delegate-to-private-helper shape (not flagged), a private helper
with one ungated caller among several (still flagged), the per-line
escape hatch requiring a reason (bare marker still flagged, reasoned marker
suppresses only its own finding), and the zero-files-found hard failure.
"""

from __future__ import annotations

import argparse
import ast
import collections
import glob
import re
import sys

TABLE_MARKER = "external_identity_crosswalk"
MODEL_MARKER = "externalidentitycrosswalk"
GATE_NAME = "assert_connector_permitted"

# Call/attribute shapes that constitute a "write" once we've established the
# table/model marker is present somewhere in the same function body.
WRITE_CALL_NAMES = {
    "add", "add_all", "merge", "bulk_save_objects", "bulk_insert_mappings",
    "bulk_update_mappings", "execute", "insert", "update",
}

# Per-line escape hatch, matching this repo's established `<name>-ok: <reason>`
# convention (see check_fetch_guards.py / check_error_signalling.py). A bare
# `crosswalk-gate-ok` with no reason does not match and does not suppress.
ESCAPE_RE = re.compile(r"crosswalk-gate-ok:[ \t]*\S")


def default_paths() -> list[str]:
    return sorted(glob.glob("app/**/*.py", recursive=True))


def _source_mentions_marker(node: ast.AST, src_lines: list[str]) -> bool:
    """True when the function's own source text names the crosswalk table
    or model, as a raw string, an f-string fragment, or an identifier."""
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno)
    text = "\n".join(src_lines[start:end]).lower()
    return TABLE_MARKER in text or MODEL_MARKER in text


def _calls_write_operation(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            name = None
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name in WRITE_CALL_NAMES:
                return True
    return False


def _call_target_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _node_calls_gate(node: ast.AST) -> bool:
    """True when this AST subtree contains a genuine call to the gate --
    a bare-name call or an attribute call (module.foo(...), self.foo(...))
    -- never a source-text substring match."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and _call_target_name(sub) == GATE_NAME:
            return True
    return False


def _build_reverse_call_graph(
    tree: ast.AST,
) -> tuple[
    dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]],
    list[ast.FunctionDef | ast.AsyncFunctionDef],
]:
    """Map a callee name to every same-file function whose body calls it
    (bare-name or attribute call, e.g. `self.callee(...)`)."""
    all_funcs = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    callers_of: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = collections.defaultdict(list)
    for func in all_funcs:
        called_names = set()
        for sub in ast.walk(func):
            if isinstance(sub, ast.Call):
                name = _call_target_name(sub)
                if name:
                    called_names.add(name)
        for name in called_names:
            callers_of[name].append(func)
    return callers_of, all_funcs


def _caller_gates_before_calling(caller: ast.AST, callee_name: str) -> bool:
    """True when `caller` calls the gate at least once, and that gate call
    occurs before every call it makes to `callee_name`."""
    gate_lines: list[int] = []
    call_lines: list[int] = []
    for sub in ast.walk(caller):
        if isinstance(sub, ast.Call):
            name = _call_target_name(sub)
            if name == GATE_NAME:
                gate_lines.append(sub.lineno)
            elif name == callee_name:
                call_lines.append(sub.lineno)
    if not gate_lines or not call_lines:
        return False
    earliest_gate = min(gate_lines)
    return all(earliest_gate < call_line for call_line in call_lines)


def _all_callers_gate_before_calling(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    callers_of: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]],
) -> bool:
    callers = callers_of.get(node.name, [])
    if not callers:
        return False
    return all(_caller_gates_before_calling(caller, node.name) for caller in callers)


def _calls_gate(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_funcs: list[ast.FunctionDef | ast.AsyncFunctionDef],
    callers_of: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]],
) -> bool:
    """True when the function itself calls the gate, calls a same-module
    function that does, or is called exclusively by same-file callers that
    all gate before calling it (see module docstring for the disclosed
    scope of this check)."""
    if _node_calls_gate(node):
        return True

    # One level of same-module callee traversal: does this function call
    # another function (by name) whose own body calls the gate?
    called_names = {
        _call_target_name(sub)
        for sub in ast.walk(node)
        if isinstance(sub, ast.Call) and _call_target_name(sub)
    }
    for other in all_funcs:
        if other.name in called_names and _node_calls_gate(other):
            return True

    # One level of same-file caller traversal: a private writer helper
    # whose only same-file caller(s) already gated before calling it.
    if _all_callers_gate_before_calling(node, callers_of):
        return True

    return False


def _escape_marker_present(lines: list[str], lineno: int) -> bool:
    idx = lineno - 1
    candidates = []
    if 0 <= idx < len(lines):
        candidates.append(lines[idx])
    if 0 <= idx - 1 < len(lines):
        candidates.append(lines[idx - 1])
    return any(ESCAPE_RE.search(line) for line in candidates)


def scan_file(path: str) -> list[tuple[int, str]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return []

    if TABLE_MARKER not in src.lower() and MODEL_MARKER not in src.lower():
        return []

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    lines = src.splitlines()
    callers_of, all_funcs = _build_reverse_call_graph(tree)
    findings: list[tuple[int, str]] = []

    for node in all_funcs:
        if not _source_mentions_marker(node, lines):
            continue
        if not _calls_write_operation(node):
            continue
        if _calls_gate(node, all_funcs, callers_of):
            continue
        if _escape_marker_present(lines, node.lineno):
            continue
        findings.append((node.lineno, node.name))

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="files to scan (default: whole app/ tree)")
    parser.add_argument("--count", action="store_true", help="print only the total count")
    args = parser.parse_args(argv)

    paths = args.paths or default_paths()
    paths = [p for p in paths if p.endswith(".py")]

    if not paths:
        print(
            "ERROR: no Python files found to scan. This scanner globs "
            "'app/**/*.py' relative to the current working directory -- run "
            "it from the repo root, or pass explicit file paths. A scan "
            "that finds nothing to check must not be reported as a clean "
            "pass.",
            file=sys.stderr,
        )
        return 2

    total = 0
    report: list[str] = []
    for path in paths:
        findings = scan_file(path)
        total += len(findings)
        for lineno, funcname in findings:
            report.append(
                f"{path}:{lineno}: function '{funcname}' writes to "
                f"{TABLE_MARKER} with no {GATE_NAME}() call on its path"
            )

    if args.count:
        print(total)
        return 0

    if report:
        print("\n".join(report))
        print(f"\n{total} crosswalk writer(s) with no allowlist gate on their call path.")
        print(f"Call {GATE_NAME}() before the write, or mark a deliberate "
              "exception with 'crosswalk-gate-ok: <reason>' on the "
              "function's def line or the line above it.")
    else:
        print(f"No unguarded {TABLE_MARKER} writers found in {len(paths)} file(s).")

    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
