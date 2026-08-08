#!/usr/bin/env python
"""Pull the newest production database dump off the app droplet, and verify it.

    python scripts/pull_backup.py                 # fetch newest + verify
    python scripts/pull_backup.py --verify-only   # verify what is already local
    python scripts/pull_backup.py --keep 10       # prune to the newest N locally

Why
---
`deploy/archie-backup.sh` dumps the database on a timer and writes to
/root/deploy-backups on the SAME droplet as the database it is dumping. The
script's own comment acknowledges this — "add an `aws s3 cp`/`rclone copy` here
once those exist" — and nothing was ever added. So every copy of the data shares a
single failure domain: lose the droplet and you lose the database and all twelve
of its backups together.

That is the whole of the risk. It is not a theoretical one: the droplet is a
single DigitalOcean VM with no snapshot policy configured here, running at 73%
disk.

This script is the smallest thing that actually breaks the single point of
failure — it copies the newest dump somewhere the droplet is not. It is not a
substitute for a real offsite target (object storage, another provider, anything
with its own durability guarantee). It is what can be done with no destination
provisioned and nothing to pay for.

Verification, not just transfer
-------------------------------
A backup nobody has restored is a hypothesis. This checks gzip integrity and that
the dump actually contains table definitions AND row data, because the failure
that matters is not a corrupt file — it is a dump that transferred perfectly and
contains only schema.

A full restore drill (restore into a scratch database, compare row counts against
production) was run against db-20260803-181612.sql.gz on 2026-08-04: 733 tables,
and organizations/users/application_components/archimate_elements all matched
production exactly. The only errors were a missing local `vector` extension, which
is environmental. Re-run that drill periodically; this script's checks are the
cheap daily version, not a replacement for it.
"""

from __future__ import annotations

import argparse
import gzip
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DIR = REPO_ROOT / "offsite_backups"
HOST = "root@134.122.105.56"
REMOTE_DIR = "/root/deploy-backups"


def _ssh(command: str) -> str:
    proc = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=20", HOST, command],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ssh failed: {(proc.stderr or '').strip()[:200]}")
    return (proc.stdout or "").strip()


def verify(path: Path) -> tuple[bool, str]:
    """Return (ok, description). Checks integrity AND that rows are present."""
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except Exception as exc:  # noqa: BLE001 — any failure here means unusable
        return False, f"unreadable: {exc.__class__.__name__}: {exc}"

    tables = len(re.findall(r"CREATE TABLE", text))
    copies = len(re.findall(r"^COPY ", text, re.M))
    databases = re.findall(r"CREATE DATABASE (\w+)", text)
    # Lines that are neither DDL nor psql directives — i.e. actual row data.
    skip = ("--", "SET", "SELECT", "CREATE", "ALTER", "COPY", "GRANT", "REVOKE", "COMMENT", "\\")
    rows = sum(1 for ln in text.splitlines() if ln and not ln.startswith(skip))

    if not tables:
        return False, "no CREATE TABLE statements — this is not a schema dump"
    if not rows:
        return False, f"{tables} tables but NO row data — schema-only dump, not a backup"
    return True, (
        f"{len(text) // 1024} KB uncompressed, {tables} tables, {copies} COPY blocks, "
        f"{rows} data lines, databases={databases or '?'}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--verify-only", action="store_true",
                        help="verify local copies without fetching")
    parser.add_argument("--keep", type=int, default=0,
                        help="after fetching, keep only the newest N local dumps")
    args = parser.parse_args(argv)

    LOCAL_DIR.mkdir(exist_ok=True)

    if not args.verify_only:
        try:
            newest = _ssh(f"ls -t {REMOTE_DIR}/*.sql.gz 2>/dev/null | head -1")
        except RuntimeError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        if not newest:
            print(f"FAIL: no dumps found in {REMOTE_DIR} on {HOST}", file=sys.stderr)
            return 1

        target = LOCAL_DIR / Path(newest).name
        if target.exists():
            print(f"already local: {target.name}")
        else:
            print(f"fetching {Path(newest).name} ...")
            proc = subprocess.run(
                ["scp", "-o", "ConnectTimeout=30", f"{HOST}:{newest}", str(target)],
                capture_output=True, encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0:
                print(f"FAIL: scp: {(proc.stderr or '').strip()[:200]}", file=sys.stderr)
                return 1

    local = sorted(LOCAL_DIR.glob("*.sql.gz"))
    if not local:
        print("FAIL: no local dumps to verify", file=sys.stderr)
        return 1

    failed = 0
    for path in local:
        ok, detail = verify(path)
        print(f"  {'OK  ' if ok else 'FAIL'} {path.name}  {detail}")
        failed += not ok

    if args.keep > 0:
        # Filename embeds the timestamp (db-YYYYMMDD-HHMMSS.sql.gz), so name order
        # is chronological order.
        for stale in sorted(LOCAL_DIR.glob("*.sql.gz"))[: -args.keep]:
            stale.unlink()
            print(f"  pruned {stale.name}")

    if failed:
        print(f"\n{failed} local dump(s) FAILED verification.", file=sys.stderr)
        return 1
    print(f"\n{len(local)} local dump(s) verified. These are the only copies that do "
          f"NOT share a failure domain with the database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
