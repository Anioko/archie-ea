"""
My Applications Routes (NS-012, NS-013)

Application manager persona dashboards for owned application management.
All queries scoped by current user's ownership records.

ADR Reference: docs/adr/0011-application-manager-persona.md
"""

from datetime import date

from flask import render_template
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.decorators import requires_application_owner
from app.extensions import db
from app.models.application_owner import ApplicationOwner
from app.models.solution_models import Solution

from . import my_applications_bp


def get_owned_apps():
    """Get applications owned by current user."""
    # Get app IDs where user is owner
    ownership = ApplicationOwner.query.filter_by(user_id=current_user.id).all()
    app_ids = [o.application_id for o in ownership]

    if not app_ids:
        return []

    # Get the actual applications
    apps = Solution.query.filter(Solution.id.in_(app_ids)).all()
    return apps


@my_applications_bp.route("/")
@login_required
@requires_application_owner
def dashboard():
    """Application manager dashboard - overview of owned applications."""
    apps = get_owned_apps()

    # Calculate stats
    total = len(apps)
    by_status = {}
    for app in apps:
        status = getattr(app, 'lifecycle_status', None) or getattr(app, 'status', 'unknown') or 'unknown'
        by_status[status] = by_status.get(status, 0) + 1

    # Health breakdown (using lifecycle or health status if available)
    healthy = sum(1 for a in apps if getattr(a, 'health_status', None) == 'healthy')
    at_risk = sum(1 for a in apps if getattr(a, 'health_status', None) == 'at_risk')
    critical = sum(1 for a in apps if getattr(a, 'health_status', None) == 'critical')

    return render_template(
        "my_applications/dashboard.html",
        apps=apps,
        total=total,
        by_status=by_status,
        healthy=healthy,
        at_risk=at_risk,
        critical=critical,
    )


@my_applications_bp.route("/list")
@login_required
@requires_application_owner
def app_list():
    """List applications owned by current user."""
    apps = get_owned_apps()

    return render_template(
        "my_applications/app_list.html",
        apps=apps,
    )


@my_applications_bp.route("/app/<int:app_id>")
@login_required
@requires_application_owner
def app_detail(app_id):
    """View details of an owned application."""
    # Verify ownership
    ownership = ApplicationOwner.query.filter_by(
        user_id=current_user.id,
        application_id=app_id
    ).first()

    if not ownership:
        from flask import abort
        abort(403, description="You do not own this application")

    app = Solution.query.get_or_404(app_id)

    return render_template(
        "my_applications/app_detail.html",
        app=app,
        ownership=ownership,
    )


@my_applications_bp.route("/health")
@login_required
@requires_application_owner
def health_overview():
    """Health overview of owned applications."""
    apps = get_owned_apps()

    # Group by health status
    by_health = {
        'healthy': [],
        'at_risk': [],
        'critical': [],
        'unknown': [],
    }

    for app in apps:
        health = getattr(app, 'health_status', None) or 'unknown'
        if health in by_health:
            by_health[health].append(app)
        else:
            by_health['unknown'].append(app)

    return render_template(
        "my_applications/health_overview.html",
        apps=apps,
        by_health=by_health,
    )


@my_applications_bp.route("/roadmap")
@login_required
@requires_application_owner
def roadmap_impact():
    """View roadmap items affecting owned applications."""
    apps = get_owned_apps()

    # Get apps with sunset dates or lifecycle changes
    upcoming_changes = []
    for app in apps:
        sunset = getattr(app, 'sunset_date', None)
        if sunset and sunset > date.today():
            upcoming_changes.append({
                'app': app,
                'date': sunset,
                'type': 'Sunset',
            })

    # Sort by date
    upcoming_changes.sort(key=lambda x: x['date'])

    return render_template(
        "my_applications/roadmap_impact.html",
        apps=apps,
        upcoming_changes=upcoming_changes,
        today=date.today(),
    )
