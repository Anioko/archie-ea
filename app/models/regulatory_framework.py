"""
Framework adoption and tailoring models.

Extends the shared-reference pattern (HybridTenantMixin) so the platform
seeds a read-only catalogue of frameworks and controls, and each organisation
adopts them into its own tenant scope with optional tailoring.
"""

from datetime import datetime

from app import db
from app.models.mixins import HybridTenantMixin


class FrameworkAdoption(HybridTenantMixin, db.Model):
    """An organisation's adoption of a regulatory framework from the catalogue.

    Reference rows (organization_id IS NULL, scope='reference') represent the
    platform catalogue entry.  Tenant rows (organization_id = <org>, scope='tenant')
    represent an organisation's adoption with optional tailoring.
    """

    __tablename__ = "framework_adoptions"

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(16), nullable=True, index=True)

    framework_id = db.Column(
        db.Integer, db.ForeignKey("regulatory_frameworks.id"), nullable=False, index=True
    )
    reference_adoption_id = db.Column(
        db.Integer, db.ForeignKey("framework_adoptions.id", ondelete="SET NULL"), nullable=True
    )

    adopted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    adopted_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="active")  # active, inactive
    tailoring_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    framework = db.relationship("RegulatoryFramework", backref="adoptions")
    adopted_by = db.relationship("User", foreign_keys=[adopted_by_id])
    adopted_controls = db.relationship(
        "AdoptedControl", back_populates="adoption", lazy="dynamic", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "framework_id", name="uq_org_framework_adoption"
        ),
    )

    def __repr__(self):
        return f"<FrameworkAdoption {self.framework_id} org={self.organization_id}>"


class AdoptedControl(HybridTenantMixin, db.Model):
    """A control adopted by an organisation as part of a framework adoption.

    Tenant rows carry organisation-specific tailoring, implementation status,
    and evidence.  Reference rows are the platform catalogue.
    """

    __tablename__ = "adopted_controls"

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(16), nullable=True, index=True)

    adoption_id = db.Column(
        db.Integer, db.ForeignKey("framework_adoptions.id"), nullable=False, index=True
    )
    control_id = db.Column(
        db.Integer, db.ForeignKey("compliance_controls.id"), nullable=False, index=True
    )

    tailoring_notes = db.Column(db.Text)
    implementation_status = db.Column(db.String(20), default="planned")
    # planned, in_progress, implemented, verified, not_applicable, waived

    evidence_url = db.Column(db.String(500))
    verified_date = db.Column(db.DateTime)
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    adoption = db.relationship("FrameworkAdoption", back_populates="adopted_controls")
    control = db.relationship("ComplianceControl", backref="adopted_controls")
    verified_by = db.relationship("User", foreign_keys=[verified_by_id])

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "adoption_id", "control_id", name="uq_org_adoption_control"
        ),
    )

    def __repr__(self):
        return f"<AdoptedControl ctl={self.control_id} org={self.organization_id}>"