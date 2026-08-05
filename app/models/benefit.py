"""Benefit — the measurable outcome an initiative exists to deliver.

Benefits were previously `EnterpriseInitiative.expected_benefits`, a Text column
holding a JSON array. That makes them declarable but not measurable: you cannot
baseline one, track it, roll it up across a portfolio, or ask whether the thing
you funded actually paid. CLAUDE.md states the principle for motivation entities
— "A plain textarea is not an acceptable substitute — the field *is* the element"
— and a benefit is exactly that kind of entity.

Modelled as baseline -> target -> actual, because "benefit realised" is only
meaningful as a delta from where you started, measured after go-live. A benefit
with a target and no baseline is a wish.

New table, so `flask init-db` (create_all) provisions it; no reconcile-schema
step is needed for a new table.
"""
from datetime import datetime
from decimal import Decimal

from app import db
from app.models.mixins import TenantMixin

# Financial benefits roll up into a portfolio total; non-financial ones must not
# be summed with them, so the type drives whether `value_*` is money or a unit.
BENEFIT_TYPES = (
    "cost_saving",       # opex/capex reduction — money
    "cost_avoidance",    # spend not incurred — money
    "revenue",           # incremental revenue — money
    "productivity",      # hours released — convertible, but not cash
    "risk_reduction",    # non-financial
    "compliance",        # non-financial
    "customer",          # CSAT/NPS etc — non-financial
    "capability",        # maturity uplift — non-financial
)

FINANCIAL_BENEFIT_TYPES = {"cost_saving", "cost_avoidance", "revenue"}

BENEFIT_STATUSES = (
    "identified",    # claimed in the business case
    "planned",       # baselined, owner assigned, measurement agreed
    "in_delivery",   # initiative underway
    "realising",     # partially measured post go-live
    "realised",      # target met
    "not_realised",  # measured and missed — kept, not deleted
    "cancelled",
)


class Benefit(TenantMixin, db.Model):
    """A single measurable benefit claimed by an initiative."""

    __tablename__ = "benefits"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    benefit_type = db.Column(db.String(40), default="cost_saving", index=True)
    status = db.Column(db.String(30), default="identified", index=True)

    # ── What is being measured ──────────────────────────────────────────────
    measure = db.Column(db.String(255))      # "Annual licence spend", "Order cycle time"
    unit = db.Column(db.String(40))          # "GBP", "hours/month", "%", "days"

    baseline_value = db.Column(db.Numeric(18, 2))
    baseline_date = db.Column(db.Date)
    target_value = db.Column(db.Numeric(18, 2))
    target_date = db.Column(db.Date)
    actual_value = db.Column(db.Numeric(18, 2))
    actual_date = db.Column(db.Date)

    # ── Accountability ──────────────────────────────────────────────────────
    # A benefit with no owner is never measured. Kept nullable so a benefit can
    # be captured during intake before an owner is agreed.
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    measurement_method = db.Column(db.Text)   # how it will be evidenced
    measurement_frequency = db.Column(db.String(30))  # monthly, quarterly, annual

    # ── Traceability ────────────────────────────────────────────────────────
    # A benefit must attach to what delivers it and what it improves, or it
    # cannot be rolled up or chased.
    initiative_id = db.Column(
        db.Integer, db.ForeignKey("enterprise_initiatives.id", ondelete="CASCADE"), index=True
    )
    capability_id = db.Column(
        db.Integer, db.ForeignKey("unified_capabilities.id", ondelete="SET NULL"), index=True
    )
    work_package_id = db.Column(
        db.Integer, db.ForeignKey("work_packages.id", ondelete="SET NULL"), index=True
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    owner = db.relationship("User", foreign_keys=[owner_id])
    initiative = db.relationship(
        "EnterpriseInitiative", foreign_keys=[initiative_id], backref="benefits"
    )
    capability = db.relationship("UnifiedCapability", foreign_keys=[capability_id], backref="benefits")
    work_package = db.relationship("WorkPackage", foreign_keys=[work_package_id], backref="benefits")

    # ── Derived ─────────────────────────────────────────────────────────────
    @property
    def is_financial(self) -> bool:
        return self.benefit_type in FINANCIAL_BENEFIT_TYPES

    @staticmethod
    def _dec(value):
        """Coerce to Decimal so DB values and form values can be compared.

        Numeric columns come back as Decimal, but a value just assigned from a
        form is a float, and `float - Decimal` raises TypeError. Mixing the two
        is the normal case — measure a benefit and the freshly-set actual_value
        is a float while baseline_value is still a Decimal from the database —
        so this must not be left to chance. str() first: Decimal(0.1) carries
        the binary float error, Decimal("0.1") does not, and these are money.
        """
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @property
    def target_delta(self):
        """Improvement sought: target - baseline. None when either is unset."""
        target, baseline = self._dec(self.target_value), self._dec(self.baseline_value)
        if target is None or baseline is None:
            return None
        return target - baseline

    @property
    def actual_delta(self):
        """Improvement achieved so far. None when either is unset."""
        actual, baseline = self._dec(self.actual_value), self._dec(self.baseline_value)
        if actual is None or baseline is None:
            return None
        return actual - baseline

    @property
    def realisation_percentage(self):
        """Percent of the sought improvement achieved.

        Returns None — never 0 — when it cannot be computed, so the UI shows an
        em dash instead of asserting "0% realised" about something never
        measured. A measured zero and an absent measurement are different facts.
        """
        target, actual = self.target_delta, self.actual_delta
        if target is None or actual is None or target == 0:
            return None
        return round(float(actual) / float(target) * 100, 1)

    @property
    def is_overdue(self) -> bool:
        """Past its target date without a measured actual."""
        if not self.target_date or self.actual_value is not None:
            return False
        if self.status in ("realised", "not_realised", "cancelled"):
            return False
        return self.target_date < datetime.utcnow().date()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "benefit_type": self.benefit_type,
            "status": self.status,
            "measure": self.measure,
            "unit": self.unit,
            "baseline_value": float(self.baseline_value) if self.baseline_value is not None else None,
            "target_value": float(self.target_value) if self.target_value is not None else None,
            "actual_value": float(self.actual_value) if self.actual_value is not None else None,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "actual_date": self.actual_date.isoformat() if self.actual_date else None,
            "realisation_percentage": self.realisation_percentage,
            "is_financial": self.is_financial,
            "is_overdue": self.is_overdue,
            "owner": self.owner.email if self.owner else None,
            "initiative_id": self.initiative_id,
            "capability_id": self.capability_id,
        }

    def __repr__(self):
        return f"<Benefit {self.name} [{self.status}]>"
