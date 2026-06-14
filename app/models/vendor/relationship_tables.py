"""
Vendor Relationship Tables

This module defines the junction tables needed for vendor-capability
and vendor-compliance relationships in the enhanced vendor management system.
"""

from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer, String, Text

from .. import db

# Junction table for vendor capability risks
vendor_capability_risks = db.Table(
    "vendor_capability_risks",
    db.Column("id", db.Integer, primary_key=True),
    db.Column(
        "business_capability_id",
        db.Integer,
        db.ForeignKey("business_capability.id"),
        nullable=False,
    ),
    db.Column(
        "vendor_organization_id",
        db.Integer,
        db.ForeignKey("vendor_organizations.id"),
        nullable=False,
    ),
    db.Column("risk_level", db.String(20), default="medium"),  # low, medium, high, critical
    db.Column(
        "risk_type", db.String(50), default="operational"
    ),  # operational, financial, strategic, technical
    db.Column("risk_description", db.Text),
    db.Column("mitigation_strategy", db.Text),
    db.Column("likelihood", db.String(20), default="medium"),  # low, medium, high
    db.Column("impact", db.String(20), default="medium"),  # low, medium, high
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
    db.Column("updated_at", db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
    db.Column("assessed_by_id", db.Integer, db.ForeignKey("users.id")),
    extend_existing=True,
)


# Junction table for initiative capabilities
initiative_capabilities = db.Table(
    "initiative_capabilities",
    db.Column(
        "initiative_id",
        db.Integer,
        db.ForeignKey("enterprise_initiatives.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "capability_id",
        db.Integer,
        db.ForeignKey("business_capability.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "transformation_type", db.String(50)
    ),  # 'enhance', 'replace', 'consolidate', 'retire'
    db.Column("target_maturity", db.Integer),  # Target CMM level
    db.Column("priority", db.String(20)),  # 'critical', 'high', 'medium', 'low'
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
    extend_existing=True,
)


# Junction table for compliance vendor coverage
# NOTE: This table is defined in vendor_organization.py with composite primary key
# Importing from there to avoid redefinition
from .vendor_organization import compliance_vendor_coverage  # noqa

# Original definition kept for reference:
# compliance_vendor_coverage = db.Table(
#     "compliance_vendor_coverage",
#     db.Column("id", db.Integer, primary_key=True),
#     db.Column(
#         "compliance_requirement_id",
#         db.Integer,
#         db.ForeignKey("compliance_requirements.id"),
#         nullable=False,
#     ),
#     db.Column(
#         "vendor_product_capability_id",
#         db.Integer,
#         db.ForeignKey("vendor_product_capabilities.id"),
#         nullable=False,
#     ),
#     db.Column("coverage_level", db.String(20), default="partial"),
#     db.Column("evidence_notes", db.Text),
#     db.Column("last_verified", db.DateTime),
#     db.Column("created_at", db.DateTime, default=datetime.utcnow),
#     db.Column("updated_at", db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
# )
