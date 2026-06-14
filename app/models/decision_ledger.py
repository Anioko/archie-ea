from datetime import datetime

from sqlalchemy.orm import relationship

from app import db


class DecisionLedger(db.Model):
    """Append-only decision ledger for Capability Governance.

    Each row represents one decision event related to a capability. Snapshot
    fields store minimal capability metadata to avoid joins for historical
    reporting. Use `(capability_id, decision_sequence)` or `decision_date`
    to retrieve latest decision per capability.
    """

    __tablename__ = "decision_ledger"

    id = db.Column(db.Integer, primary_key=True)
    capability_id = db.Column(db.String(64), nullable=False, index=True)
    # Snapshot fields (minimal): copy the capability name and owner at time
    capability_name_snapshot = db.Column(db.String(255), nullable=False)
    business_owner_snapshot = db.Column(db.String(128), nullable=True)

    # Decision-specific fields
    decision_id = db.Column(db.String(64), nullable=False)
    decision_sequence = db.Column(db.Integer, nullable=False, default=1)
    decision_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    decision_summary = db.Column(db.Text, nullable=True)
    decision_owner = db.Column(db.String(128), nullable=True)
    decision_type = db.Column(db.String(64), nullable=True)
    rationale = db.Column(db.Text, nullable=True)
    impact_estimate = db.Column(db.Text, nullable=True)
    approval_status = db.Column(db.String(32), nullable=True, index=True)

    # Additional metadata and extensible payload
    related_docs = db.Column(db.JSON, nullable=True)  # list of doc references
    tags = db.Column(db.JSON, nullable=True)  # list of tag strings

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Note: additional composite indexes are created via migrations
