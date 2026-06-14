"""
My Applications Services (NS-012, NS-013)

Business logic for application manager features including
filtered application lists and ownership management.

ADR Reference: docs/adr/0011-application-manager-persona.md
"""

from typing import Dict, List, Optional, Tuple

from flask_login import current_user
from sqlalchemy import and_, or_

from app.extensions import db
from app.models.application_owner import ApplicationOwner
from app.models.application_portfolio import ApplicationComponent


def get_user_applications(
    user_id: int,
    ownership_type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[List[dict], int]:
    """
    Get applications owned by a specific user.

    Returns: (applications with ownership info, total_count)
    """
    # Get ownership records for user
    query = ApplicationOwner.query.filter(ApplicationOwner.user_id == user_id)

    if ownership_type:
        query = query.filter(ApplicationOwner.ownership_type == ownership_type)

    ownership_records = query.all()
    app_ids = [o.application_id for o in ownership_records]

    if not app_ids:
        return [], 0

    # Get applications
    app_query = ApplicationComponent.query.filter(ApplicationComponent.id.in_(app_ids))

    if search:
        search_term = f"%{search}%"
        app_query = app_query.filter(
            or_(
                ApplicationComponent.name.ilike(search_term),
                ApplicationComponent.description.ilike(search_term),
            )
        )

    app_query = app_query.order_by(ApplicationComponent.name.asc())

    total = app_query.count()
    apps = app_query.offset((page - 1) * per_page).limit(per_page).all()

    # Build ownership lookup
    ownership_map = {o.application_id: o for o in ownership_records}

    # Combine app data with ownership info
    result = []
    for app in apps:
        ownership = ownership_map.get(app.id)
        result.append({
            "application": app,
            "ownership_type": ownership.ownership_type if ownership else None,
            "is_primary": ownership.is_primary if ownership else False,
        })

    return result, total


def get_ownership_summary(user_id: int) -> Dict[str, int]:
    """Get summary of ownership by type for a user."""
    records = ApplicationOwner.query.filter(ApplicationOwner.user_id == user_id).all()

    summary = {
        "primary": 0,
        "backup": 0,
        "technical": 0,
        "business": 0,
        "total": len(records),
    }

    for r in records:
        if r.ownership_type in summary:
            summary[r.ownership_type] += 1
        if r.is_primary:
            summary["primary"] += 1

    return summary


def get_application_health_summary(user_id: int) -> Dict[str, any]:
    """Get health summary for user's applications."""
    ownership_records = ApplicationOwner.query.filter(
        ApplicationOwner.user_id == user_id
    ).all()

    app_ids = [o.application_id for o in ownership_records]
    if not app_ids:
        return {
            "total": 0,
            "healthy": 0,
            "at_risk": 0,
            "critical": 0,
            "unknown": 0,
        }

    apps = ApplicationComponent.query.filter(ApplicationComponent.id.in_(app_ids)).all()

    summary = {
        "total": len(apps),
        "healthy": 0,
        "at_risk": 0,
        "critical": 0,
        "unknown": 0,
    }

    for app in apps:
        # Determine health based on available fields
        # This is a simplified health check - real implementation would use more factors
        lifecycle = getattr(app, 'lifecycle_status', None)
        if lifecycle in ['active', 'production']:
            summary["healthy"] += 1
        elif lifecycle in ['sunset', 'retiring']:
            summary["at_risk"] += 1
        elif lifecycle in ['decommissioned', 'retired']:
            summary["critical"] += 1
        else:
            summary["unknown"] += 1

    return summary


def get_roadmap_impacts(user_id: int) -> List[dict]:
    """Get roadmap items affecting user's applications."""
    # Get user's application IDs
    ownership_records = ApplicationOwner.query.filter(
        ApplicationOwner.user_id == user_id
    ).all()

    app_ids = [o.application_id for o in ownership_records]
    if not app_ids:
        return []

    # Get applications with roadmap-relevant fields
    apps = ApplicationComponent.query.filter(ApplicationComponent.id.in_(app_ids)).all()

    impacts = []
    for app in apps:
        # Check for sunset/retirement dates
        sunset_date = getattr(app, 'sunset_date', None)
        if sunset_date:
            impacts.append({
                "application": app,
                "impact_type": "sunset",
                "date": sunset_date,
                "description": f"{app.name} is scheduled for sunset",
            })

        # Check lifecycle status
        lifecycle = getattr(app, 'lifecycle_status', None)
        if lifecycle in ['sunset', 'retiring']:
            impacts.append({
                "application": app,
                "impact_type": "lifecycle_change",
                "date": None,
                "description": f"{app.name} is in {lifecycle} phase",
            })

    # Sort by date (None dates last)
    impacts.sort(key=lambda x: (x["date"] is None, x["date"]))

    return impacts[:20]  # Limit to 20 most relevant
