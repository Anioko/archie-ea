"""DE-2: the derived-fact store (FR-3, FR-5) — ``archimate_derived_relationships``."""
# migration-exempt — new table created via db.create_all() (migration freeze)

# System of record for RULE-DERIVED ArchiMate relationships only (ADR-001).
# The adjacent ``architecture_inference_relationship`` table remains the
# authority for uncertain / agent-proposed edges — this store never holds
# one: ``confidence`` is pinned to ``1.00`` and ``provenance`` to
# ``'derivation'`` by CHECK constraint and column default, and the upsert
# path (``app/modules/intelligence/services/derivation_runner.py``) writes
# no other values for either column.
#
# Table shape and every constraint/index name are pinned by SDD v2 §DA-1 and
# are load-bearing for the refuter's acceptance-item-1 check, which reads
# ``pg_constraint`` / ``pg_indexes`` directly rather than the model's Python
# metadata:
#
#   uq_derived_rel        natural key (organization_id, source_element_id,
#                          target_element_id, derived_type, rule_id)
#   ck_derived_depth       depth BETWEEN 1 AND 5
#   ck_derived_conf        confidence > 0 AND confidence <= 1
#   ck_derived_stale       stale_since NULL iff stale = FALSE
#   ck_derived_chain_len   array_length(chain, 1) = depth
#   ix_dr_src              (source_element_id) WHERE stale = FALSE
#   ix_dr_tgt              (target_element_id) WHERE stale = FALSE
#   ix_dr_stale            (stale)  -- no partial predicate: this is the
#                          index the recompute job's stale-tenant selection
#                          and the invalidation listener's own read use.
#   ix_dr_chain            GIN(chain) array_ops WHERE stale = FALSE

from __future__ import annotations

import datetime as _dt

from app import db
from app.models.mixins.core import TenantMixin


class DerivedRelationship(TenantMixin, db.Model):
    """One rule-derived ArchiMate relationship, with its provenance chain."""

    __tablename__ = "archimate_derived_relationships"
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "source_element_id",
            "target_element_id",
            "derived_type",
            "rule_id",
            name="uq_derived_rel",
        ),
        db.CheckConstraint("depth BETWEEN 1 AND 5", name="ck_derived_depth"),
        db.CheckConstraint(
            "confidence > 0 AND confidence <= 1", name="ck_derived_conf"
        ),
        db.CheckConstraint(
            "(stale = FALSE AND stale_since IS NULL) OR "
            "(stale = TRUE AND stale_since IS NOT NULL)",
            name="ck_derived_stale",
        ),
        db.CheckConstraint(
            "array_length(chain, 1) = depth", name="ck_derived_chain_len"
        ),
        db.Index(
            "ix_dr_src",
            "source_element_id",
            postgresql_where=db.text("stale = FALSE"),
        ),
        db.Index(
            "ix_dr_tgt",
            "target_element_id",
            postgresql_where=db.text("stale = FALSE"),
        ),
        db.Index("ix_dr_stale", "stale"),
        db.Index(
            "ix_dr_chain",
            "chain",
            postgresql_using="gin",
            postgresql_ops={"chain": "array_ops"},
            postgresql_where=db.text("stale = FALSE"),
        ),
        # No extend_existing (round-1 refuter finding): this is a brand-new
        # table, not a pre-existing one being remapped by a second model
        # class, so extend_existing would only defeat the canonical-store
        # gate's ability to catch a future second mapped class on this
        # table -- exactly the failure mode that gate exists to catch.
    )

    id = db.Column(db.Integer, primary_key=True)

    # Deliberately no FK to archimate_elements.id: DA-1 does not specify one,
    # and an element that is the source/target of a derived row must remain
    # DELETE-able while the row survives (stale, reason="element_deleted")
    # until the next recompute prunes it -- a NOT NULL FK would block that
    # element delete outright, which the AA-4 invalidation predicate assumes
    # cannot happen. The store, not the FK, is the mechanism keeping these
    # ids meaningful.
    # No index=True here (round-1 refuter finding D10): ix_dr_src/ix_dr_tgt
    # above are the two DA-1-specified partial indexes on these columns.
    # Adding index=True as well creates a second, non-partial index on each
    # column -- 4 indexes total on this table instead of DA-1's 2, doubling
    # write amplification on what is meant to be the hottest table this
    # feature adds.
    source_element_id = db.Column(db.Integer, nullable=False)
    target_element_id = db.Column(db.Integer, nullable=False)
    derived_type = db.Column(db.String(50), nullable=False)
    rule_id = db.Column(db.String(64), nullable=False)

    # Ordered archimate_relationships.id values — FR-5's "why this row exists".
    chain = db.Column(db.ARRAY(db.Integer), nullable=False)
    # Ordered node path (element ids), retained for T-004's node highlighting.
    chain_element_ids = db.Column(db.ARRAY(db.Integer), nullable=False)
    depth = db.Column(db.Integer, nullable=False)

    # server_default, not just a Python-side default (round-1 refuter finding
    # D10): a Python-side default only applies when the ORM issues the
    # INSERT, so DDL created via create_all() previously had no real
    # DEFAULT 1.00 at the database level despite the earlier build report
    # claiming DDL parity with DA-1. The upsert path in derivation_runner.py
    # writes 1.00/'derivation' explicitly on every row regardless, so this
    # only matters for a row inserted by some other path -- but a DB-level
    # default is the correct expression of ADR-001's "confidence is always
    # 1.00, provenance is always 'derivation'" pin, and costs nothing here.
    confidence = db.Column(db.Numeric(3, 2), nullable=False, server_default="1.00")
    provenance = db.Column(db.String(20), nullable=False, server_default="derivation")
    engine_version = db.Column(db.String(20), nullable=False)

    computed_at = db.Column(db.DateTime, nullable=False, default=_dt.datetime.utcnow)

    stale = db.Column(db.Boolean, nullable=False, default=False)
    stale_since = db.Column(db.DateTime, nullable=True)
    stale_reason = db.Column(db.String(40), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return (
            f"<DerivedRelationship org={self.organization_id} "
            f"{self.source_element_id}->{self.target_element_id} "
            f"rule={self.rule_id} stale={self.stale}>"
        )


__all__ = ["DerivedRelationship"]
