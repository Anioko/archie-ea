"""RateCard — what an hour of effort costs, so effort can become spend.

`EnterpriseInitiative.spent_to_date` was a column nothing ever wrote, because
nothing in the platform knew either how much effort had been consumed or what an
hour was worth. Jira worklog sync supplies the first half; this supplies the
second.

Deliberately small. A full finance integration (actuals from the GL, capitalised
vs expensed, currency conversion at transaction date) is a different project. A
role-and-rate table is the least that makes a spend figure defensible, and it is
honest about being an estimate: the rollup reports `is_estimate=True` and names
the basis, so nobody mistakes it for booked cost.
"""
from datetime import datetime

from app import db
from app.models.mixins import TenantMixin


class RateCard(TenantMixin, db.Model):
    """Hourly cost for a role, optionally time-bounded."""

    __tablename__ = "rate_cards"

    id = db.Column(db.Integer, primary_key=True)

    role = db.Column(db.String(120), nullable=False, index=True)
    hourly_rate = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default="GBP", nullable=False)

    # A blended default is what most organisations actually have on day one.
    # Exactly one row per organisation should carry this.
    is_default = db.Column(db.Boolean, default=False, nullable=False, index=True)

    effective_from = db.Column(db.Date)
    effective_to = db.Column(db.Date)
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    @property
    def is_current(self) -> bool:
        today = datetime.utcnow().date()
        if self.effective_from and self.effective_from > today:
            return False
        if self.effective_to and self.effective_to < today:
            return False
        return True

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "hourly_rate": float(self.hourly_rate) if self.hourly_rate is not None else None,
            "currency": self.currency,
            "is_default": self.is_default,
            "is_current": self.is_current,
        }

    def __repr__(self):
        return f"<RateCard {self.role} {self.hourly_rate}{self.currency}>"
