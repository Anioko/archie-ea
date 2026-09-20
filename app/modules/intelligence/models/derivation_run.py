"""T-005 (D7): the derivation run-record store — ``intelligence_derivation_runs``.

# migration-exempt — new table created via db.create_all() (migration freeze)

Answers exactly one question, which nothing else in this codebase can answer
after the request that produced it ends: did derivation run for this tenant,
when, and how long did it take (D5), and is a measured-zero result
distinguishable from "never ran" (D6). See
``docs/buckets/t005-us5-yield-report/tasks/00-verification-notes.md`` D5-D9
for the full reasoning; the decisions there are binding.

One row per tenant per COMPLETED ``DerivationRunner.run_and_persist`` call.
The sole producer is ``DerivationRunner.run_and_persist`` itself
(``app/modules/intelligence/services/derivation_runner.py``), which writes
this row atomically with the derived-fact upsert it already performs, inside
the same ``tenant_scope`` block, before the commit -- so no reader can ever
observe the facts without the run record that describes them, or vice versa.
A failed or lock-skipped run writes no row: absence means "no completed run",
which is exactly the fact the yield endpoint's not-computed branch reads.
Never a placeholder row.

Every non-key column is nullable, per CLAUDE.md "Schema management" --
``reconcile-schema`` only ever adds nullable columns to an existing database,
so this table (and any future column on it) must tolerate NULL.
"""

from __future__ import annotations

import datetime as _dt

from app import db
from app.models.mixins.core import TenantMixin


class DerivationRun(TenantMixin, db.Model):
    """One completed ``DerivationRunner.run_and_persist`` call, for one tenant."""

    __tablename__ = "intelligence_derivation_runs"
    __table_args__ = (
        db.Index("ix_idr_org_finished", "organization_id", "finished_at"),
        # No extend_existing: this is a brand-new table, not a pre-existing
        # one being remapped by a second model class -- extend_existing would
        # blind the canonical-store gate to a future second mapped class on
        # this table, exactly the failure mode it exists to catch.
    )

    id = db.Column(db.Integer, primary_key=True)

    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True, default=_dt.datetime.utcnow)

    duration_ms = db.Column(db.Integer, nullable=True)

    explicit_count = db.Column(db.Integer, nullable=True)
    derived_count = db.Column(db.Integer, nullable=True)
    # Never 0 when explicit_count is 0 -- a measured zero and "not computed"
    # must stay distinguishable (CLAUDE.md "never invent data").
    ratio = db.Column(db.Numeric(10, 4), nullable=True)

    engine_version = db.Column(db.String(20), nullable=True)

    # "scheduled" / "on_demand" -- whatever the caller passes, never guessed.
    trigger = db.Column(db.String(20), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return (
            f"<DerivationRun org={self.organization_id} "
            f"derived_count={self.derived_count} trigger={self.trigger}>"
        )


__all__ = ["DerivationRun"]
