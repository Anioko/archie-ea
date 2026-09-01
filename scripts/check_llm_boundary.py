#!/usr/bin/env python
"""Enforce the deterministic-emitter / LLM boundary in the codegen pipeline.

    python scripts/check_llm_boundary.py            # report
    python scripts/check_llm_boundary.py --count    # count only (last line)
    python scripts/check_llm_boundary.py --json

Why
---
`docs/adr/0010-enterprise-genome.md` and the integration design
(`03_integration.md`, §2) draw a hard trust boundary: the deterministic emitters
turn a validated genome into artifacts with **zero LLM calls**. The LLM may only
propose schema-validated genome edits (an RFC-6902 patch or an extraction
partial); it may never emit a final artifact, an element id, or any value that
reaches a file un-validated.

That boundary is currently a *convention* — nothing stops a future edit from
reaching into `LLMService._call_llm` from inside `genome_to_bundle` to "fill in"
a field. The moment that happens the emitter stops being reproducible and
testable, and provenance stops being trustworthy, silently.

What it does and does not catch
-------------------------------
It scans the **emitter files** — `genome_to_bundle.py`, any
`genome_to_<domain>_bundle*.py`, and any `emit_*.py` under the codegen services
tree — and counts direct references to the LLM boundary:

    _call_llm            the one method that actually calls a provider
    LLMService           the class that owns it

A clean result (0) means no emitter reaches the LLM directly. It does NOT prove
the *rest* of the pipeline is LLM-free — only that the deterministic core is.

This is a **ratchet at 0**: the emitters are LLM-free today, and any new call
into them is a regression the gate fails on. Registered in `scripts/verify.py`
as the ``llm-boundary`` gate.

Exemption
---------
Append ``llm-boundary-ok: <reason>`` on the line to record a deliberate,
reviewed exception (there should essentially never be one — the whole point of
the emitter is that it does not call the LLM).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The deterministic emitter tree. Everything here MUST be 0-LLM.
_EMITTER_DIR = REPO_ROOT / "app" / "modules" / "codegen" / "services"

# Tokens that mean "this file talks to the LLM provider directly".
_LLM_TOKENS = re.compile(r"\b_call_llm\b|\bLLMService\b")

_EXEMPT = "llm-boundary-ok"


def _emitter_files() -> list[Path]:
    """The emitter files whose determinism the boundary protects.

    genome_to_bundle.py (the shared core), any genome_to_<domain>_bundle*.py,
    and any emit_*.py under the codegen services tree.
    """
    if not _EMITTER_DIR.is_dir():
        return []
    seen: dict[Path, None] = {}
    for pattern in ("genome_to_bundle.py", "genome_to_*_bundle*.py", "emit_*.py"):
        for path in _EMITTER_DIR.glob(pattern):
            if path.is_file():
                seen[path] = None
    return sorted(seen)


def find_violations() -> list[tuple[str, int, str]]:
    """Return (relative_path, lineno, line) for each LLM reference in an emitter."""
    violations: list[tuple[str, int, str]] = []
    for path in _emitter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _EXEMPT in line:
                continue
            if _LLM_TOKENS.search(line):
                rel = path.relative_to(REPO_ROOT).as_posix()
                violations.append((rel, lineno, line.strip()))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", action="store_true", help="print only the count")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    violations = find_violations()
    count = len(violations)

    if args.json:
        print(json.dumps({
            "count": count,
            "files_scanned": [p.relative_to(REPO_ROOT).as_posix() for p in _emitter_files()],
            "violations": [
                {"file": f, "line": ln, "text": txt} for f, ln, txt in violations
            ],
        }, indent=2))
        return 0

    if args.count:
        print(count)
        return 0

    if not violations:
        n = len(_emitter_files())
        print(f"OK — {n} emitter file(s) scanned, 0 direct LLM references.")
        return 0

    print("LLM references inside deterministic emitter paths (must be 0):\n")
    for f, ln, txt in violations:
        print(f"  {f}:{ln}: {txt}")
    print(f"\n{count} violation(s). Emitters must be deterministic — the LLM may only")
    print("propose schema-validated genome edits, never emit artifacts (03_integration.md §2).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
