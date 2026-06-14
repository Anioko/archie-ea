"""
Integration Pattern catalogue model.

Stores the 18 ARB-approved/conditional/blocked integration patterns for
the Integration Architecture Governance feature (INTARCH-001).

Usage:
    from app.models.integration_pattern import IntegrationPattern
    approved = IntegrationPattern.query.filter_by(approval_status='approved').all()
"""

from datetime import datetime

from app import db


class IntegrationPattern(db.Model):
    __tablename__ = "integration_patterns"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    vendor_key = db.Column(db.String(50), nullable=False)    # SAP_BTP | MICROSOFT | CROSS_VENDOR | GENERIC
    pattern_type = db.Column(db.String(50), nullable=False)  # middleware | event_driven | api | file | batch | rpa
    middleware = db.Column(db.String(100))
    source_system_hint = db.Column(db.String(100))
    target_system_hint = db.Column(db.String(100))
    protocol = db.Column(db.String(30))                      # odata | rest | soap | idoc | event | file
    data_format = db.Column(db.String(30))                   # json | xml | idoc | avro | csv
    approval_status = db.Column(db.String(20), default='approved')  # approved | conditional | blocked
    approval_notes = db.Column(db.Text)
    arb_conditions = db.Column(db.JSON)
    codegen_target = db.Column(db.String(50))                # sap-btp-integration | azure-logic-app | null
    description = db.Column(db.Text)
    documentation_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<IntegrationPattern id={self.id} name={self.name!r} status={self.approval_status}>"
