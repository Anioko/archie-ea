#!/usr/bin/env python
"""The AI write path has one choke point. This proves it is still the only one.

ToolExecutor.execute is where every agent write is authorised. Its own
docstring states the invariant the design rests on:

    "There is no other path from an agent tool name to a `_tool_*` handler, so
     a permission check placed here -- before the handler dispatch, not inside
     any individual `_tool_*` method -- covers every mutating tool without
     per-tool ad hoc checks, including tools added in future that forget to add
     their own."

That is a good design, and it is exactly the kind of claim that quietly stops
being true. One `self._tool_create_application(args)` called from a route or a
service -- for a perfectly reasonable-looking reason -- and 27 write tools lose
their permission check with nothing going red. The docstring would still say it.

Three invariants, all statically checkable:

1. CHOKE POINT. No `_tool_*` handler is called anywhere except through
   execute()'s dispatch. Any direct call bypasses the permission check.

2. NO WRITE DECLARED READ-ONLY. A handler that reaches the database
   (db.session.add / delete / commit, or a bulk .update()/.delete()) must not
   be registered with "mutates": False -- that flag is what decides whether the
   permission check runs at all, and whether AgentRunner queues the call for
   approval.

3. EXPLICIT CLASSIFICATION. Every registered tool declares "mutates". The
   executor defaults to True (fail closed, correctly), so an omission is safe
   today -- but it means a reader cannot tell a read-only tool from an
   unclassified one, and the next person to "tidy" the default has no signal.
   Counted as debt, ratcheting down.

Escape hatch: `ai-tool-guard-ok: <reason>` on the offending line.

    python scripts/check_ai_tool_guard.py
    python scripts/check_ai_tool_guard.py --count

Proven-against: a direct `self._tool_create_application({})` call added to
agent_runner.py -- red at 1 naming the bypass, green when removed.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXECUTOR = "app/modules/ai_chat/tools/executor.py"
REGISTRY = "app/modules/ai_chat/tools/registry.py"
ALLOW = re.compile(r"ai-tool-guard-ok:[ \t]*\S")

WRITES = ("db.session.add", "db.session.delete", "db.session.commit",
          "db.session.bulk_save", "session.add(", ".delete()", ".update(")


def _tool_schemas(root: str) -> dict:
    """{tool name: declared mutates, or None when unclassified}."""
    path = os.path.join(root, *REGISTRY.split("/"))
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError):
        return {}
    out = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
        if "name" not in keys:
            continue
        name = mutates = None
        for k, v in zip(node.keys, node.values):
            if not isinstance(k, ast.Constant):
                continue
            if k.value == "name" and isinstance(v, ast.Constant):
                name = v.value
            elif k.value == "mutates" and isinstance(v, ast.Constant):
                mutates = v.value
        if name:
            out[name] = mutates
    return out


def scan(root: str) -> list[str]:
    problems = []
    schemas = _tool_schemas(root)

    # 1. choke point -- a direct call to any _tool_* handler outside execute()
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "app")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            # A test calling a handler directly is testing the handler, which is
            # the point of a unit test -- not a production path that skips the
            # permission check. Excluded, or the gate reports six findings nobody
            # can act on, and a gate that cries wolf gets ignored
            # (TESTING_STANDARD.md rule 8).
            if "/tests/" in rel or filename.startswith("test_"):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    lines = fh.read().split("\n")
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(lines, 1):
                if ALLOW.search(line) or "def _tool_" in line:
                    continue
                # A comment naming a handler is documentation, not a call. The
                # registry documents _tool_run_inference_engine's write path in a
                # comment, which the first version of this gate called a bypass.
                code = line.split("#", 1)[0]
                if re.search(r"\b_tool_[a-z_]+\s*\(", code):
                    problems.append(
                        "%s:%d [ai-tool-guard] calls a _tool_* handler directly, "
                        "bypassing ToolExecutor.execute's permission check" % (rel, number)
                    )

    # 2 and 3. classification of every registered tool
    exec_path = os.path.join(root, *EXECUTOR.split("/"))
    try:
        with open(exec_path, encoding="utf-8") as fh:
            exec_src = fh.read()
        exec_tree = ast.parse(exec_src)
    except (OSError, SyntaxError):
        return problems

    handlers = {}
    for node in ast.walk(exec_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("_tool_"):
            handlers[node.name[len("_tool_"):]] = ast.get_source_segment(exec_src, node) or ""

    for name, declared in sorted(schemas.items()):
        body = handlers.get(name, "")
        writes = any(w in body for w in WRITES)
        if declared is False and writes:
            problems.append(
                "%s: [ai-tool-guard] tool %r is registered \"mutates\": False but its "
                "handler writes to the database -- the permission check and the "
                "approval queue are both skipped for it" % (REGISTRY, name)
            )
        elif declared is None:
            problems.append(
                "%s: [ai-tool-guard] tool %r does not declare \"mutates\"; the executor "
                "fails closed so it is safe today, but nothing records whether it is "
                "read-only or merely unclassified" % (REGISTRY, name)
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
                "Route the call through ToolExecutor.execute, declare the tool's\n"
                "\"mutates\" flag honestly, or append 'ai-tool-guard-ok: <reason>'."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
