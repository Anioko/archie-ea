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

CLOSED CYCLES ARE IMMUTABLE, AND THIS SCRIPT SUSPENDS THAT
----------------------------------------------------------
``trg_arb_cycle_history`` on ``arb_review_cycles`` rejects any UPDATE to a closed
cycle -- which is every row this script targets. That guard is correct and must
stay: it is what makes the governance record trustworthy. So the UPDATE is
performed with that ONE trigger disabled, on that ONE table, inside the same
transaction that re-enables it, and only after the prior state has been written
to disk.

This is deliberately narrow. It does not use ``session_replication_role =
replica``, which would silently suspend every trigger on every table including
the tenant and separation-of-duties guards. If the re-enable fails the whole
transaction rolls back, so the table cannot be left unguarded.

Disabling a trigger requires table ownership. If the operator running the
rollback is not the owner, the script fails loudly rather than reporting a
success it did not achieve.

USAGE
-----
    python scripts/rollback_typed_arb_cycle_projection.py            # report only
    python scripts/rollback_typed_arb_cycle_projection.py --apply    # rewrite

``--apply`` writes a JSON record of every row's prior state to
``arb_cycle_projection_rollback_<timestamp>.json`` before touching anything, so
the projection can be restored if the rollback is itself reverted.

That backup records the CYCLE rows only, and it is still sufficient to restore
both tables: each review item's prior ``status`` and ``decision`` always equalled
its cycle's prior ``status``, which is exactly the invariant
``archie_validate_arb_cycle_membership`` enforces. Stated here so that whoever
restores this during an incident does not have to re-derive it.
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
# Statuses the pre-release code accepts on a terminal cycle. Projecting status
# onto anything outside this set would swap one violated constraint for another.
_TERMINAL_STATUSES = frozenset(
    {
        "approved",
        "approved_with_conditions",
        "rejected",
        "deferred",
        "withdrawn",
        "returned_for_evidence",
        "returned_for_options",
    }
)

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
        # Say which database, always. This runs during a rollback, when the
        # operator is under pressure and may have several databases open; a
        # tool that reports "already installable" without naming what it looked
        # at invites acting on the wrong one.
        target = db.engine.url.render_as_string(hide_password=True)
        print(f"target database: {target}\n")

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

        # Refuse to project onto a value the older code would itself reject.
        # Without this the script could trade one uninstallable constraint for
        # another and still report success.
        illegal = [
            row["terminal_outcome"]
            for row in rows
            if row["terminal_outcome"] not in _TERMINAL_STATUSES
        ]
        if illegal:
            print(
                "\nABORTED: these terminal_outcome values are not legal cycle "
                "statuses, so projecting onto status would not help: "
                f"{sorted(set(illegal))}"
            )
            return 1

        try:
            db.session.execute(
                db.text(
                    "ALTER TABLE arb_review_cycles DISABLE TRIGGER trg_arb_cycle_history"
                )
            )
            # The cycle's status is PROJECTED onto its review item, and
            # archie_validate_arb_cycle_membership enforces that the two agree
            # (`AND review.status = NEW.status`). Moving the cycle alone leaves
            # the projection disagreeing and the membership guard rejects the
            # write -- so the projection moves in the same transaction, first.
            projected = db.session.execute(
                db.text(
                    "UPDATE arb_review_items r "
                    "SET status = c.terminal_outcome, decision = c.terminal_outcome "
                    "FROM arb_review_cycles c "
                    "WHERE r.review_cycle_id = c.id "
                    "AND r.organization_id = c.organization_id "
                    "AND c.closed_at IS NOT NULL "
                    "AND c.terminal_outcome IS NOT NULL "
                    "AND c.status IS DISTINCT FROM c.terminal_outcome"
                )
            ).rowcount
            updated = db.session.execute(
                db.text(
                    "UPDATE arb_review_cycles SET status = terminal_outcome "
                    f"WHERE {_MISMATCH}"
                )
            ).rowcount
            # trg_arb_cycle_membership is a DEFERRABLE constraint trigger, so
            # the UPDATEs above leave pending trigger events -- and PostgreSQL
            # refuses ALTER TABLE ... ENABLE TRIGGER on a table that has them.
            # Draining them here is also strictly safer than suspending that
            # trigger would have been: the membership guard still runs, and
            # still gets to reject this transaction, just immediately.
            db.session.execute(db.text("SET CONSTRAINTS ALL IMMEDIATE"))
        finally:
            # Same transaction as the UPDATE: if this fails, the rollback takes
            # the UPDATE with it and the table is never left unguarded.
            db.session.execute(
                db.text(
                    "ALTER TABLE arb_review_cycles ENABLE TRIGGER trg_arb_cycle_history"
                )
            )
        db.session.commit()

        remaining = db.session.execute(
            db.text(f"SELECT count(*) FROM arb_review_cycles WHERE {_MISMATCH}")
        ).scalar()
        print(
            f"{projected} review item projection(s) and {updated} cycle(s) "
            f"updated; {remaining} still mismatched."
        )
        # A non-zero remainder means the UPDATE did not cover the predicate it
        # was written against, which would leave the older guard uninstallable
        # while reporting success. Fail loudly rather than let boot discover it.
        return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
