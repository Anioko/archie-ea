#!/usr/bin/env python
"""Count findings still open in the 17 Aug 2026 QA remediation register.

The register (97 active findings, compiled in ARCHIE-MASTER-Remediation-Register.md
from three source documents) is the outstanding remediation backlog. Its own most
useful observation about this repository is that a defect written down and left is a
defect PLUS a note, and the note gets read later as a decision someone made on
purpose. CLAUDE.md draws the conclusion: prefer a gate that COUNTS the outstanding
work over prose that merely describes it.

So this is that gate. `qa_findings_status.json` is the ledger, and the `qa-register`
gate in verify.py fails while any finding is open — which means verify.py cannot go
green, and therefore nothing can legitimately deploy, until the register is closed.

The point is that finishing stops being a promise and becomes something the build
asserts. Two things follow, and both are deliberate:

  * A finding is marked closed only when its fix is COMMITTED and its tests pass.
    Partially-fixed findings stay open with a note saying what remains — "mostly
    done" is open.
  * Lowering the threshold to make a deploy possible defeats the entire mechanism.
    If the work is genuinely descoped, remove the finding from the ledger with a
    recorded reason; do not quietly reclassify it as closed.

Usage:
    python scripts/check_qa_register.py            # list what is still open
    python scripts/check_qa_register.py --count    # print the open count only
"""

import argparse
import json
import pathlib
import sys

LEDGER = pathlib.Path(__file__).resolve().parents[1] / "qa_findings_status.json"

# Order used when listing, so the most serious open work is read first.
SEVERITY_ORDER = {"S1": 0, "S2": 1, "S3": 2, "S4": 3, "S5": 4}


def load():
    if not LEDGER.exists():
        print(f"ledger not found: {LEDGER}", file=sys.stderr)
        sys.exit(2)
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ledger is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", action="store_true",
                        help="print only the number of open findings")
    args = parser.parse_args()

    data = load()
    findings = data.get("findings", [])
    open_rows = [f for f in findings if f.get("status") != "closed"]

    if args.count:
        print(len(open_rows))
        return

    if not open_rows:
        print(f"QA register closed: {len(findings)}/{len(findings)} findings done.")
        return

    open_rows.sort(key=lambda f: (SEVERITY_ORDER.get(f.get("severity"), 9), f["id"]))
    closed = len(findings) - len(open_rows)
    print(f"{len(open_rows)} of {len(findings)} QA register findings still open "
          f"({closed} closed):")
    for f in open_rows:
        note = f.get("note")
        suffix = f"  [partial: {note}]" if note else ""
        print(f"  {f.get('severity', '??'):3} {f['id']:10} {f.get('title', '')}{suffix}")


if __name__ == "__main__":
    main()
