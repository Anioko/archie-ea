#!/usr/bin/env python
"""Every AI persona charter must carry the no-fabrication rules.

Archie is a system of record. Its AI personas speak with the platform's voice
about applications, spend, risk and governance posture, so a persona that
invents a number is worse than one that says nothing: the architect cannot tell
the difference and acts on it. That is the same rule the `fabricated-data`
gates enforce on server-rendered pages, applied to the surface most able to
produce a confident wrong figure.

The product already has the right mechanism. `_EVIDENCE_RULES` in
architect_persona_charters.py is a shared constant carrying six hard rules --
evidence, no fabrication, propose-don't-dispose, cite your source, governance
wins, and live-data precedence over stale RAG documents -- and every charter
interpolates it. What was missing is anything that NOTICES when one does not.

A charter is a large f-string. Adding a persona means copying one, and a copy
that drops the `{_EVIDENCE_RULES}` interpolation still produces a working,
plausible, entirely ungoverned persona. Nothing else in the tree would fail:
the module imports, the prompt builds, the chat answers.

This gate also holds the second half of the contract -- that
build_architect_prompt still labels the live block as the ONLY source for
numbers -- because a charter that demands sourcing is worthless if the prompt
stops saying where the source is.

Escape hatch: `evidence-rules-ok: <reason>` on the charter's key line, for a
persona that deliberately carries different governance.

    python scripts/check_ai_evidence_rules.py
    python scripts/check_ai_evidence_rules.py --count

Proven-against: the `{_EVIDENCE_RULES}` interpolation deleted from the cto
charter -- red at 1 naming 'cto', green at 0 when restored.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARTERS_PATH = "app/modules/ai_chat/services/architect_persona_charters.py"
ALLOW = re.compile(r"evidence-rules-ok:[ \t]*\S")

# The sentence that tells the model where its numbers may come from. If the
# prompt builder stops saying this, the charters' "cite your source" rule
# points at nothing.
LIVE_BLOCK_CLAIM = "your ONLY source for numbers"


def scan(root: str) -> list[str]:
    path = os.path.join(root, *CHARTERS_PATH.split("/"))
    try:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
    except OSError:
        return ["%s: [ai-evidence] unreadable" % CHARTERS_PATH]

    problems = []
    marker = "CHARTERS: Dict[str, str] = {"
    if marker not in source:
        return ["%s: [ai-evidence] CHARTERS mapping not found" % CHARTERS_PATH]

    body = source[source.index(marker):]
    for key, text in re.findall(r'"([a-z_]+)":\s*f?"""(.*?)"""', body, re.S):
        if "_EVIDENCE_RULES" in text:
            continue
        line = next(
            (ln for ln in source.split("\n") if '"%s":' % key in ln), ""
        )
        if ALLOW.search(line):
            continue
        problems.append(
            "%s: [ai-evidence] charter %r does not interpolate _EVIDENCE_RULES -- "
            "this persona may state numbers it was never given"
            % (CHARTERS_PATH, key)
        )

    if LIVE_BLOCK_CLAIM not in source:
        problems.append(
            "%s: [ai-evidence] build_architect_prompt no longer labels the live block "
            "as the only source for numbers -- the charters' 'cite your source' rule "
            "now points at nothing" % CHARTERS_PATH
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
                "Interpolate {_EVIDENCE_RULES} into the charter, or append\n"
                "'evidence-rules-ok: <reason>' to its key line if the persona\n"
                "deliberately carries different governance."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
