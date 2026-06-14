# migration-exempt
"""
License Entitlement Model (NS-004)

Tracks software license entitlements and usage for Procurement persona.
Part of North Star Persona MVP implementation.

ADR Reference: docs/adr/0010-procurement-persona.md
"""

from datetime import datetime
from decimal import Decimal

from .. import db


class LicenseEntitlement(db.Model):
    """
    License entitlement tracking for Procurement workflows.

    Tracks:
    - License type (named user, concurrent, device, etc.)
    - Quantities (entitled, deployed, used)
    - Compliance status (compliant, over-deployed, under-utilized)
    - Cost per unit

    Enables:
    - Shelfware detection (entitled but not used)
    - Compliance tracking (used > entitled)
    - True-up planning
    """
    __tablename__ = "license_entitlements"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Foreign keys
    contract_id = db.Column(
        db.Integer,
        db.ForeignKey("vendor_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id = db.Column(
        db.Integer,
        db.ForeignKey("application_components.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # License details
    license_type = db.Column(
        db.String(50),
        nullable=False,
    )  # 'named_user', 'concurrent', 'device', 'core', 'site'
    license_metric = db.Column(
        db.String(100),
        nullable=True,
    )  # 'per user', 'per core', 'per device', etc.

    # Quantities
    quantity_entitled = db.Column(db.Integer, nullable=False, default=0)
    quantity_deployed = db.Column(db.Integer, nullable=False, default=0)
    quantity_used = db.Column(db.Integer, nullable=False, default=0)

    # Cost
    unit_cost = db.Column(db.Numeric(10, 2), nullable=True)

    # Compliance
    compliance_status = db.Column(
        db.String(50),
        default="compliant",
    )  # 'compliant', 'over_deployed', 'under_utilized'

    # Sync tracking
    last_usage_sync = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contract = db.relationship(
        "VendorContract",
        backref=db.backref("license_entitlements", lazy="dynamic", cascade="all, delete-orphan"),
    )
    application = db.relationship(
        "ApplicationComponent",
        backref=db.backref("license_entitlements", lazy="dynamic"),
    )
    organization = db.relationship(
        "Organization",
        backref=db.backref("license_entitlements", lazy="dynamic"),
    )

    # Valid values
    LICENSE_TYPES = ["named_user", "concurrent", "device", "core", "site"]
    COMPLIANCE_STATUSES = ["compliant", "over_deployed", "under_utilized"]

    def __repr__(self):
        return f"<LicenseEntitlement {self.id}: {self.license_type} x{self.quantity_entitled}>"

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "application_id": self.application_id,
            "license_type": self.license_type,
            "license_metric": self.license_metric,
            "quantity_entitled": self.quantity_entitled,
            "quantity_deployed": self.quantity_deployed,
            "quantity_used": self.quantity_used,
            "unit_cost": float(self.unit_cost) if self.unit_cost else None,
            "compliance_status": self.compliance_status,
            "utilization_percent": self.utilization_percent,
            "organization_id": self.organization_id,
        }

    @property
    def utilization_percent(self):
        """Calculate utilization percentage."""
        if not self.quantity_entitled or self.quantity_entitled == 0:
            return 0
        return round((self.quantity_used / self.quantity_entitled) * 100, 1)

    @property
    def deployment_percent(self):
        """Calculate deployment percentage."""
        if not self.quantity_entitled or self.quantity_entitled == 0:
            return 0
        return round((self.quantity_deployed / self.quantity_entitled) * 100, 1)

    @property
    def total_cost(self):
        """Calculate total cost for entitled quantity."""
        if not self.unit_cost or not self.quantity_entitled:
            return Decimal("0.00")
        return self.unit_cost * self.quantity_entitled

    @property
    def unused_value(self):
        """Calculate value of unused licenses (shelfware)."""
        if not self.unit_cost:
            return Decimal("0.00")
        unused = max(0, self.quantity_entitled - self.quantity_used)
        return self.unit_cost * unused

    def update_compliance_status(self):
        """Update compliance status based on quantities."""
        if self.quantity_deployed > self.quantity_entitled:
            self.compliance_status = "over_deployed"
        elif self.utilization_percent < 50:
            self.compliance_status = "under_utilized"
        else:
            self.compliance_status = "compliant"

    @classmethod
    def get_compliance_summary(cls, organization_id):
        """Get compliance summary for organization."""
        entitlements = cls.query.filter(
            cls.organization_id == organization_id,
        ).all()

        summary = {
            "total": len(entitlements),
            "compliant": 0,
            "over_deployed": 0,
            "under_utilized": 0,
            "total_value": Decimal("0.00"),
            "unused_value": Decimal("0.00"),
        }

        for e in entitlements:
            summary[e.compliance_status] = summary.get(e.compliance_status, 0) + 1
            summary["total_value"] += e.total_cost
            summary["unused_value"] += e.unused_value

        return summary
