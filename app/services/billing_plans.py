"""
Plan catalogue and plan limits.

The organisation's plan lives on its ``subscriptions`` row (written by
BillingService from checkout and from the payment provider's signed events).
This module is the only place that turns that row into limits, so the billing
page, the add-user screens and the seat counter all give the same answer.

Price ids are never in code: each purchasable plan names the environment
variables that hold its monthly and annual price ids.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

INTERVALS = ("year", "month")


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    summary: str
    # True when the plan can be bought online; Enterprise is sold by contract.
    purchasable: bool
    # Fixed number of people the plan admits; None with per_seat=True means
    # the number of seats bought, None with per_seat=False means no limit.
    user_limit: Optional[int]
    per_seat: bool = False
    default_seats: int = 1
    # "people" counts every member; "editors" leaves read-only members free.
    counts: str = "people"
    price_env: Dict[str, str] = field(default_factory=dict)


PLANS: Tuple[Plan, ...] = (
    Plan(
        key="free",
        name="Community",
        summary="One organisation, three people. Every question, every canvas, the twin map.",
        purchasable=False,
        user_limit=3,
    ),
    Plan(
        key="startup",
        name="Startup",
        summary="Ten people. Adds the webhook feed, export and share, and email support.",
        purchasable=True,
        user_limit=10,
        price_env={"month": "STRIPE_PRICE_STARTUP_MONTHLY", "year": "STRIPE_PRICE_STARTUP_ANNUAL"},
    ),
    Plan(
        key="team",
        name="Team",
        summary="Priced per editor; people who only ask questions are free. Single sign-on and the review-board workflow.",
        purchasable=True,
        user_limit=None,
        per_seat=True,
        default_seats=15,
        counts="editors",
        price_env={"month": "STRIPE_PRICE_TEAM_MONTHLY", "year": "STRIPE_PRICE_TEAM_ANNUAL"},
    ),
    Plan(
        key="enterprise",
        name="Enterprise",
        summary="Annual contract. Unlimited editors, SAML, audit export, supported self-hosting.",
        purchasable=False,
        user_limit=None,
    ),
)

_BY_KEY = {p.key: p for p in PLANS}
# Rows written before this catalogue carry "pro"; it bought seats like Team.
_LEGACY_KEYS = {"pro": "team"}

CONTACT_SALES_URL = "/contact"


def get_plan(key: Optional[str]) -> Plan:
    """Return the plan for a stored key; an unknown or empty key is Community."""
    key = _LEGACY_KEYS.get(key or "", key or "")
    return _BY_KEY.get(key, _BY_KEY["free"])


def purchasable_plans() -> Tuple[Plan, ...]:
    return tuple(p for p in PLANS if p.purchasable)


def price_id_for(plan_key: str, interval: str) -> Optional[str]:
    plan = _BY_KEY.get(plan_key)
    if plan is None or interval not in plan.price_env:
        return None
    return os.environ.get(plan.price_env[interval]) or None


def plan_for_price(price_id: Optional[str]) -> Optional[Tuple[Plan, str]]:
    """Return (plan, interval) for a configured price id, or None when unknown."""
    if not price_id:
        return None
    for plan in PLANS:
        for interval, env_name in plan.price_env.items():
            if os.environ.get(env_name) == price_id:
                return plan, interval
    return None


def configuration_status() -> Dict:
    """Which billing settings are present. Never returns the values."""
    missing = [
        name
        for name in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET")
        if not os.environ.get(name)
    ]
    try:
        import stripe  # noqa: F401
    except ImportError:
        missing.insert(0, "stripe (Python package)")
    prices = {
        (p.key, interval): bool(os.environ.get(env))
        for p in purchasable_plans()
        for interval, env in p.price_env.items()
    }
    if not any(prices.values()):
        missing.extend(env for p in purchasable_plans() for env in p.price_env.values())
    return {"ready": not missing, "missing": missing, "prices": prices}


# --------------------------------------------------------------------------- #
# Plan limits                                                                  #
# --------------------------------------------------------------------------- #


def _subscription_row(org_id: int):
    from app.models.subscription import Subscription

    return Subscription.query.filter_by(organization_id=org_id).first()


def effective_plan(sub) -> Plan:
    """The plan whose limits apply now.

    A deleted subscription (status cancelled) is back on Community; a
    subscription whose payment failed keeps its plan while the provider
    retries. A cancellation scheduled for the period end keeps the plan until
    the provider sends the deletion.
    """
    if sub is None:
        return _BY_KEY["free"]
    from app.models.subscription import SubscriptionStatus

    if sub.status == SubscriptionStatus.cancelled:
        return _BY_KEY["free"]
    return get_plan(sub.plan.value if sub.plan is not None else None)


def _contract_plan(org):
    """(SubscriptionPlan, seats) for the plan a platform administrator set on
    the organisation form (``organizations.plan`` / ``max_users``)."""
    from app.models.subscription import SubscriptionPlan

    legacy = (getattr(org, "plan", None) or "").lower()
    if legacy == "enterprise":
        return SubscriptionPlan.enterprise, org.max_users or 0
    if legacy in ("pro", "team"):
        return SubscriptionPlan.team, org.max_users or _BY_KEY["team"].default_seats
    if legacy == "startup":
        return SubscriptionPlan.startup, _BY_KEY["startup"].user_limit
    return SubscriptionPlan.free, _BY_KEY["free"].user_limit


def ensure_subscription(org):
    """Return the organisation's subscriptions row, creating it when absent.

    An organisation created before billing existed carries its plan only on
    ``organizations.plan`` (set by a platform administrator). The first time
    its limits are read, that value is copied onto the subscriptions row once;
    from then on the subscriptions row is the only answer.
    """
    from sqlalchemy.exc import IntegrityError

    from app import db
    from app.models.subscription import Subscription, SubscriptionStatus

    sub = _subscription_row(org.id)
    if sub is not None:
        return sub

    plan, seats = _contract_plan(org)
    sub = Subscription(
        organization_id=org.id,
        plan=plan,
        status=SubscriptionStatus.active,
        seats_purchased=seats,
    )
    db.session.add(sub)
    try:
        db.session.commit()
    except IntegrityError:
        # Another request created it first.
        db.session.rollback()
        sub = _subscription_row(org.id)
    return sub


def apply_contract_plan(org) -> bool:
    """Copy a plan a platform administrator set on the organisation form onto
    the subscriptions row. Returns False, changing nothing, while the
    organisation pays online: the payment provider owns that plan.
    """
    from app import db
    from app.models.subscription import SubscriptionStatus

    sub = ensure_subscription(org)
    if sub.stripe_subscription_id and sub.status != SubscriptionStatus.cancelled:
        return False
    sub.plan, sub.seats_purchased = _contract_plan(org)
    sub.status = SubscriptionStatus.active
    db.session.commit()
    return True


def _count_members(org_id: int, counts: str) -> int:
    from app import db
    from app.models.org_role import OrgRole
    from app.models.user import User

    query = db.session.query(User.id).filter(User.organization_id == org_id)
    if counts == "editors":
        readers = db.session.query(OrgRole.user_id).filter(
            OrgRole.organization_id == org_id, OrgRole.role == "viewer"
        )
        query = query.filter(~User.id.in_(readers))
    return query.count()


def user_limit_status(org_id: int) -> Dict:
    """The people limit that applies to *org_id* and how much of it is used.

    ``limit`` is None when the plan has no limit on people.
    """
    from app import db
    from app.models.organization import Organization

    org = db.session.get(Organization, org_id)
    sub = ensure_subscription(org) if org is not None else None
    plan = effective_plan(sub)
    if plan.per_seat:
        limit = sub.seats_purchased if sub is not None else None
    else:
        limit = plan.user_limit
    used = _count_members(org_id, plan.counts)
    return {
        "plan_key": plan.key,
        "plan_name": plan.name,
        "counts": plan.counts,
        "limit": limit,
        "used": used,
        "remaining": None if limit is None else max(limit - used, 0),
        "limit_reached": limit is not None and used >= limit,
    }


class PlanLimitReached(Exception):
    """Raised when adding someone would take an organisation past its plan."""

    def __init__(self, status: Dict):
        self.status = status
        super().__init__(
            f"The {status['plan_name']} plan admits {status['limit']} "
            f"{'editors' if status['counts'] == 'editors' else 'people'}; "
            f"{status['used']} are already in use."
        )


def enforce_user_limit(org_id: int) -> Dict:
    """Raise PlanLimitReached when *org_id* cannot add one more person."""
    status = user_limit_status(org_id)
    if status["limit_reached"]:
        raise PlanLimitReached(status)
    return status
