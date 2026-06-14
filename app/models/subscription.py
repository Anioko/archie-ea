"""
Subscription model — billing record for each organization.

Stores Stripe customer/subscription IDs and plan metadata.
One subscription per organization; the org FK is the tenant boundary.
"""

import enum

from app import db


class SubscriptionPlan(enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class SubscriptionStatus(enum.Enum):
    active = "active"
    past_due = "past_due"
    cancelled = "cancelled"
    trialing = "trialing"


class Subscription(db.Model):  # migration-exempt
    """Billing record for an organization. One row per org."""

    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    stripe_customer_id = db.Column(db.String(255), nullable=True, index=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True, index=True)
    plan = db.Column(
        db.Enum(SubscriptionPlan),
        nullable=False,
        default=SubscriptionPlan.free,
    )
    status = db.Column(
        db.Enum(SubscriptionStatus),
        nullable=False,
        default=SubscriptionStatus.active,
    )
    current_period_end = db.Column(db.DateTime, nullable=True)
    seats_purchased = db.Column(db.Integer, nullable=False, default=5)
    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    organization = db.relationship(
        "Organization",
        backref=db.backref("subscription", uselist=False, lazy="select"),
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Subscription org={self.organization_id} "
            f"plan={self.plan.value} status={self.status.value}>"
        )
