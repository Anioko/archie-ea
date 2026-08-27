"""Make a database written by the typed ARB release installable on pre-release code.

WHY THIS EXISTS
---------------
The typed ARB release loosened ``ck_arb_review_cycle_shape`` so that a
conditionally-approved cycle whose conditions were later resolved can carry
``status='approved'`` while its recorded decision stays
``terminal_outcome='approved_with_conditions'``. That is the normal end state of
the governance flow, not an edge case.

The constraint that shipped BEFORE the release requires ``terminal_outcome =
status``. So rolling the application back is a one-way door: on any database that
has completed even one conditional approval, ``ensure_arb_cycle_constraints``
fails during boot, reconcile-schema reports the guard as malformed, and the
schema never converges.

This script closes that door from the inside. Run it AFTER checking out the
older code and BEFORE booting it. It rewrites ``status`` to match the recorded
decision, which is precisely what the older code means by those columns.

It does NOT delete anything. ``terminal_outcome`` -- the record of what the board
actually decided -- is never modified; only the projection column moves, and it
moves onto the value already stored beside it, so no information is invented and
none is lost.

USAGE
-----
    python scripts/rollback_typed_arb_cycle_projection.py            # report only
    python scripts/rollback_typed_arb_cycle_projection.py --apply    # rewrite

``--apply`` writes a JSON record of every row's prior state to
``arb_cycle_projection_rollback_<timestamp>.json`` before touching anything, so
the projection can be restored if the rollback is itself reverted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The exact predicate the pre-release constraint enforces on a terminal cycle.
# Rows failing it are the ones that make the older guard uninstallable.
_MISMATCH = (
    "closed_at IS NOT NULL "
    "AND terminal_outcome IS NOT NULL "
    "AND status IS DISTINCT FROM terminal_outcome"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="rewrite status to match terminal_outcome (default: report only)",
    )
    args = parser.parse_args()

    from app import create_app, db

    app = create_app()
    with app.app_context():
        rows = (
            db.session.execute(
                db.text(
                    "SELECT id, organization_id, subject_type, subject_id, "
                    "status, terminal_outcome, closed_at "
                    f"FROM arb_review_cycles WHERE {_MISMATCH} ORDER BY id"
                )
            )
            .mappings()
            .all()
        )

        if not rows:
            print(
                "0 cycles need normalising -- this database is already "
                "installable on pre-release code."
            )
            return 0

        orgs = {row["organization_id"] for row in rows}
        print(f"{len(rows)} cycle(s) across {len(orgs)} organisation(s) would be normalised:")
        for row in rows[:20]:
            print(
                f"  cycle {row['id']} (org {row['organization_id']}, "
                f"{row['subject_type']} {row['subject_id']}): "
                f"status {row['status']!r} -> {row['terminal_outcome']!r}"
            )
        if len(rows) > 20:
            print(f"  ... and {len(rows) - 20} more")

        if not args.apply:
            print("\nReport only. Re-run with --apply to rewrite.")
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = f"arb_cycle_projection_rollback_{stamp}.json"
        with open(backup, "w", encoding="utf-8") as handle:
            json.dump(
                [
                    {key: (value.isoformat() if hasattr(value, "isoformat") else value)
                     for key, value in row.items()}
                    for row in rows
                ],
                handle,
                indent=2,
            )
        print(f"\nPrior state written to {backup}")

        updated = db.session.execute(
            db.text(
                "UPDATE arb_review_cycles SET status = terminal_outcome "
                f"WHERE {_MISMATCH}"
            )
        ).rowcount
        db.session.commit()

        remaining = db.session.execute(
            db.text(f"SELECT count(*) FROM arb_review_cycles WHERE {_MISMATCH}")
        ).scalar()
        print(f"{updated} row(s) updated; {remaining} still mismatched.")
        # A non-zero remainder means the UPDATE did not cover the predicate it
        # was written against, which would leave the older guard uninstallable
        # while reporting success. Fail loudly rather than let boot discover it.
        return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
