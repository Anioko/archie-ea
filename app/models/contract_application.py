# migration-exempt
"""
Contract Application Junction Model (NS-005)

Links vendor contracts to applications for cost allocation.
Part of North Star Persona MVP implementation.

ADR Reference: docs/adr/0010-procurement-persona.md
"""

from datetime import datetime

from .. import db


class ContractApplication(db.Model):
    """
    Junction table linking vendor contracts to applications.

    Supports:
    - Cost allocation (which apps use which contracts)
    - Allocation percentage (for shared contracts)
    - Impact analysis (if contract ends, which apps affected)
    """
    __tablename__ = "contract_applications"
    __table_args__ = (
        db.UniqueConstraint(
            "contract_id", "application_id",
            name="uq_contract_application"
        ),
        {"extend_existing": True},
    )

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
        db.ForeignKey("application_components.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Allocation
    allocation_percentage = db.Column(
        db.Numeric(5, 2),
        default=100.00,
    )  # What % of contract cost is allocated to this app

    # Notes
    notes = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contract = db.relationship(
        "VendorContract",
        backref=db.backref("application_allocations", lazy="dynamic", cascade="all, delete-orphan"),
    )
    application = db.relationship(
        "ApplicationComponent",
        backref=db.backref("contract_allocations", lazy="dynamic"),
    )
    organization = db.relationship(
        "Organization",
        backref=db.backref("contract_applications", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<ContractApplication contract={self.contract_id} app={self.application_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "application_id": self.application_id,
            "allocation_percentage": float(self.allocation_percentage) if self.allocation_percentage else 100.0,
            "notes": self.notes,
            "organization_id": self.organization_id,
        }

    @property
    def allocated_cost(self):
        """Calculate allocated cost based on contract annual value."""
        if not self.contract or not self.contract.annual_value:
            return 0
        return float(self.contract.annual_value) * (float(self.allocation_percentage) / 100)

    @classmethod
    def get_applications_for_contract(cls, contract_id, organization_id):
        """Get all applications linked to a contract."""
        return cls.query.filter(
            cls.contract_id == contract_id,
            cls.organization_id == organization_id,
        ).all()

    @classmethod
    def get_contracts_for_application(cls, application_id, organization_id):
        """Get all contracts linked to an application."""
        return cls.query.filter(
            cls.application_id == application_id,
            cls.organization_id == organization_id,
        ).all()

    @classmethod
    def get_total_cost_for_application(cls, application_id, organization_id):
        """Calculate total contract cost allocated to an application."""
        allocations = cls.get_contracts_for_application(application_id, organization_id)
        return sum(a.allocated_cost for a in allocations)
