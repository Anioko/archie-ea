#!/usr/bin/env python
"""The agent's queue decision must honour the operator's approval control.

Found 31 Aug 2026 by an AI-architecture audit, and it is the shape of defect
this repository has no other way to catch: a governance control that reads as
enforced, is documented as enforced, and is not enforced.

config.py said REQUIRE_AI_APPROVAL gated "the LLM-agent mutating-tool queue",
and that setting it false "restores the pre-Aug-2026 direct-write behaviour for
the LLM-agent paths". Both statements were false for the agent path. The tool
loop never read the key. Its queue decision came from `agent_auto_execute`, a
per-session USER PREFERENCE, flipped by POST /session/toggle-auto-execute behind
@login_required alone.

So an operator who set REQUIRE_AI_APPROVAL=true believed AI-proposed writes went
to a human queue. Any authenticated user could turn that off for themselves in
one request, after which every tier:"auto" mutating tool -- create_solution,
create_archimate_element, create_driver/goal/constraint/requirement/risk, the
whole link_* family -- executed immediately against the system of record with no
approval row and no second pair of eyes.

The /ai-chat/data/* routes were correctly gated the entire time (approval_gate.py
reads the key properly), which is exactly why nobody noticed: the control worked
on the path people tested and did nothing on the path that matters most.

Nothing else catches this. check_ai_tool_guard verifies the permission choke
point and the `mutates` flags -- both were correct throughout -- and says nothing
about WHO decides to queue. test_ai_write_approval exercises queue_ai_write on
the HTTP routes, a different code path entirely. The config comment asserted the
coupling in prose, and prose is not a gate.

Two invariants:

1. Every `AgentRunner(...)` construction passes an `auto_execute` expression that
   reaches REQUIRE_AI_APPROVAL -- directly, or through a resolver whose body
   does.
2. The resolver fails CLOSED: an absent config key means approval required.

Escape hatch: `ai-approval-ok: <reason>` on the construction line, for a caller
that genuinely has no operator control to honour (a CLI backfill, say). Say why.

    python scripts/check_ai_approval_honoured.py
    python scripts/check_ai_approval_honoured.py --count

Proven-against: `auto_execute=_agent_auto_execute_allowed()` reverted to
`auto_execute=flask_session.get("agent_auto_execute", False)` at either chat_core
call site -- red naming that construction, green when restored.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"ai-approval-ok:[ \t]*\S")
CONTROL = "REQUIRE_AI_APPROVAL"
SEARCH_ROOT = os.path.join("app", "modules", "ai_chat")


def _resolvers_reaching_the_control(tree: ast.Module, source: str) -> set:
    """Functions in this module whose body consults REQUIRE_AI_APPROVAL."""
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = ast.get_source_segment(source, node) or ""
        if CONTROL in body:
            names.add(node.name)
    return names


def scan(root: str) -> list[str]:
    problems = []
    base = os.path.join(root, SEARCH_ROOT)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue

            resolvers = _resolvers_reaching_the_control(tree, source)
            lines = source.split("\n")

            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and getattr(node.func, "id", getattr(node.func, "attr", ""))
                        == "AgentRunner"):
                    continue
                keyword = next(
                    (k for k in node.keywords if k.arg == "auto_execute"), None
                )
                line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                segment = ast.get_source_segment(source, node) or ""
                if ALLOW.search(line) or ALLOW.search(segment):
                    continue

                if keyword is None:
                    # No auto_execute at all defaults to queueing, which is safe.
                    continue

                expression = ast.get_source_segment(source, keyword.value) or ""
                if CONTROL in expression:
                    continue
                # Or it calls a resolver in this module that consults the control.
                called = {
                    getattr(n.func, "id", getattr(n.func, "attr", ""))
                    for n in ast.walk(keyword.value)
                    if isinstance(n, ast.Call)
                }
                if called & resolvers:
                    continue
                # Or it is a plain name assigned from such a resolver nearby.
                if isinstance(keyword.value, ast.Name):
                    window = "\n".join(lines[max(0, node.lineno - 40):node.lineno])
                    assignment = re.search(
                        r"^\s*%s\s*=\s*(.+)$" % re.escape(keyword.value.id),
                        window, re.M,
                    )
                    if assignment and (
                        CONTROL in assignment.group(1)
                        or any(name in assignment.group(1) for name in resolvers)
                    ):
                        continue

                problems.append(
                    "%s:%d [ai-approval] AgentRunner(auto_execute=%s) never reaches "
                    "%s -- a user preference is deciding whether AI writes need "
                    "approval" % (rel, node.lineno, expression.strip()[:60], CONTROL)
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
                "Resolve auto_execute through a helper that returns False whenever\n"
                "REQUIRE_AI_APPROVAL is set, and treats an absent key as 'approval\n"
                "required'. Or append 'ai-approval-ok: <reason>' saying why this\n"
                "caller has no operator control to honour."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
