"""
Procurement Services (NS-010, NS-011)

Business logic for procurement features including contract management
and renewal tracking.

ADR Reference: docs/adr/0010-procurement-persona.md
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app.extensions import db
from app.models.application_portfolio import VendorContract


def get_days_until_renewal(contract: VendorContract) -> Optional[int]:
    """Calculate days until contract renewal/expiration."""
    target_date = contract.renewal_date or contract.end_date
    if not target_date:
        return None
    return (target_date - date.today()).days


def get_renewal_urgency(contract: VendorContract) -> str:
    """
    Determine renewal urgency level based on days remaining.

    Returns: 'critical' (<30 days), 'warning' (<90 days),
             'upcoming' (<180 days), 'ok' (>180 days), 'expired', 'unknown'
    """
    days = get_days_until_renewal(contract)
    if days is None:
        return "unknown"
    if days < 0:
        return "expired"
    if days < 30:
        return "critical"
    if days < 90:
        return "warning"
    if days < 180:
        return "upcoming"
    return "ok"


def get_contracts_list(
    status: Optional[str] = None,
    vendor_id: Optional[int] = None,
    urgency: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[List[VendorContract], int]:
    """
    Get paginated list of contracts with optional filters.

    Returns: (contracts, total_count)
    """
    query = VendorContract.query

    # Apply filters
    if status:
        query = query.filter(VendorContract.status == status)
    if vendor_id:
        query = query.filter(VendorContract.vendor_id == vendor_id)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                VendorContract.contract_name.ilike(search_term),
                VendorContract.contract_number.ilike(search_term),
            )
        )

    # Order by renewal date (soonest first), then by name
    query = query.order_by(
        VendorContract.renewal_date.asc().nullslast(),
        VendorContract.contract_name.asc(),
    )

    total = query.count()
    contracts = query.offset((page - 1) * per_page).limit(per_page).all()

    # Filter by urgency if specified (post-query since it's calculated)
    if urgency:
        contracts = [c for c in contracts if get_renewal_urgency(c) == urgency]

    return contracts, total


def get_expiring_contracts(days: int = 90) -> List[VendorContract]:
    """Get contracts expiring within the specified number of days."""
    cutoff = date.today() + timedelta(days=days)

    return (
        VendorContract.query
        .filter(VendorContract.status == "active")
        .filter(
            or_(
                and_(
                    VendorContract.renewal_date.isnot(None),
                    VendorContract.renewal_date <= cutoff,
                ),
                and_(
                    VendorContract.renewal_date.is_(None),
                    VendorContract.end_date.isnot(None),
                    VendorContract.end_date <= cutoff,
                ),
            )
        )
        .order_by(
            func.coalesce(VendorContract.renewal_date, VendorContract.end_date).asc()
        )
        .all()
    )


def get_renewal_summary() -> Dict[str, int]:
    """Get summary counts by renewal urgency."""
    contracts = VendorContract.query.filter(VendorContract.status == "active").all()

    summary = {
        "critical": 0,  # <30 days
        "warning": 0,   # <90 days
        "upcoming": 0,  # <180 days
        "ok": 0,        # >180 days
        "expired": 0,
        "unknown": 0,
        "total": len(contracts),
    }

    for contract in contracts:
        urgency = get_renewal_urgency(contract)
        summary[urgency] = summary.get(urgency, 0) + 1

    return summary


def get_spend_summary() -> Dict[str, any]:
    """Get spend analytics summary."""
    contracts = VendorContract.query.filter(VendorContract.status == "active").all()

    total_value = sum(c.contract_value or 0 for c in contracts)
    total_annual = sum(c.annual_cost or 0 for c in contracts)

    # Group by contract type
    by_type = {}
    for c in contracts:
        ct = c.contract_type or "unknown"
        if ct not in by_type:
            by_type[ct] = {"count": 0, "annual_cost": 0}
        by_type[ct]["count"] += 1
        by_type[ct]["annual_cost"] += c.annual_cost or 0

    # Group by vendor
    by_vendor = {}
    for c in contracts:
        if c.vendor:
            vname = c.vendor.name
            if vname not in by_vendor:
                by_vendor[vname] = {"count": 0, "annual_cost": 0}
            by_vendor[vname]["count"] += 1
            by_vendor[vname]["annual_cost"] += c.annual_cost or 0

    # Sort by spend
    top_vendors = sorted(
        by_vendor.items(),
        key=lambda x: x[1]["annual_cost"],
        reverse=True
    )[:10]

    return {
        "total_contracts": len(contracts),
        "total_value": total_value,
        "total_annual_cost": total_annual,
        "by_type": by_type,
        "top_vendors": top_vendors,
    }
