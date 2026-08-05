"""Roll logged effort up into initiative spend.

The chain, now that every hop exists:

    KanbanCard.time_spent_seconds        (Jira worklog sync)
      -> KanbanCard.implementation_work_package_id
        -> WorkPackage.enterprise_initiative_id
          -> EnterpriseInitiative

Every one of those links was missing until this change set, which is why
`spent_to_date` was a column nothing ever wrote.

Design rule: this returns None, never 0, when it cannot compute. An initiative
with no logged effort and an initiative whose effort nobody has recorded are
different facts, and rendering both as "£0 spent" is the class of lie the
fabricated-data gate exists to prevent. The result also carries `is_estimate`
and `basis`, so a rate-card-derived figure is never mistaken for booked cost.
"""
import logging
from decimal import Decimal

from app import db

logger = logging.getLogger(__name__)


def _default_rate():
    """The organisation's blended hourly rate, or None if none is configured.

    Tenant-scoped implicitly: RateCard carries TenantMixin.
    """
    from app.models.rate_card import RateCard

    row = (
        db.session.query(RateCard)
        .filter(RateCard.is_default.is_(True))
        .order_by(RateCard.effective_from.desc().nullslast())
        .first()
    )
    if row is None:
        row = db.session.query(RateCard).order_by(RateCard.id).first()
    if row is None or not row.is_current:
        return None
    return row


def logged_seconds_for_initiative(initiative_id: int) -> int | None:
    """Total effort logged against an initiative's work packages.

    None means "no card carried a worklog", which is different from 0.
    """
    from app.models.adm_kanban import KanbanCard
    from app.models.implementation_migration import WorkPackage

    rows = (
        db.session.query(KanbanCard.time_spent_seconds)
        .join(WorkPackage, KanbanCard.implementation_work_package_id == WorkPackage.id)
        .filter(
            WorkPackage.enterprise_initiative_id == initiative_id,
            KanbanCard.time_spent_seconds.isnot(None),
        )
        .all()
    )
    if not rows:
        return None
    return sum(r[0] for r in rows)


def compute_initiative_spend(initiative_id: int) -> dict:
    """Estimated spend for one initiative.

    Returns a dict rather than a bare number so the caller can tell an estimate
    from a measurement, and can show *why* a figure is unavailable instead of
    printing a zero.
    """
    result = {
        "initiative_id": initiative_id,
        "amount": None,
        "currency": None,
        "hours": None,
        "is_estimate": True,
        "basis": None,
        "reason_unavailable": None,
    }

    seconds = logged_seconds_for_initiative(initiative_id)
    if seconds is None:
        result["reason_unavailable"] = "No effort has been logged against this initiative's work."
        return result

    hours = round(seconds / 3600.0, 2)
    result["hours"] = hours

    rate = _default_rate()
    if rate is None:
        result["reason_unavailable"] = (
            f"{hours} hours logged, but no current rate card is configured, "
            "so the hours cannot be costed."
        )
        return result

    result["amount"] = float(Decimal(str(hours)) * rate.hourly_rate)
    result["currency"] = rate.currency
    result["basis"] = f"{hours}h at {rate.hourly_rate}{rate.currency}/h ({rate.role})"
    return result


def refresh_initiative_spend(initiative_id: int, commit: bool = True) -> dict:
    """Write the computed estimate onto EnterpriseInitiative.spent_to_date.

    Only writes when a figure could actually be computed — an initiative whose
    effort is unknown keeps a NULL spend rather than being stamped with 0.
    """
    from app.models.vendor.vendor_organization import EnterpriseInitiative

    spend = compute_initiative_spend(initiative_id)
    if spend["amount"] is None:
        return spend

    initiative = db.session.get(EnterpriseInitiative, initiative_id)
    if initiative is None:
        spend["reason_unavailable"] = "Initiative not found."
        spend["amount"] = None
        return spend

    initiative.spent_to_date = spend["amount"]
    if initiative.approved_budget:
        initiative.budget_variance_percentage = round(
            (float(spend["amount"]) - float(initiative.approved_budget))
            / float(initiative.approved_budget) * 100,
            1,
        )
    if commit:
        db.session.commit()
    return spend
