"""
Governance Dashboard Routes
Provides central governance oversight, ARB reviews, ADRs, risk register, and enterprise roadmap.
"""
import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template
from flask_login import login_required

from app import db
from app.decorators import require_roles

logger = logging.getLogger(__name__)

governance_bp = Blueprint("governance", __name__, url_prefix="/governance")

# ArchiMate Principle carries an RFC-2119 enforcement level; the dashboard badges
# a "priority". Map the two rather than inventing a priority the model never held.
_ENFORCEMENT_TO_PRIORITY = {
    "MUST": "Critical",
    "SHOULD": "High",
    "MAY": "Medium",
}


@governance_bp.route("/dashboard")
@login_required
def dashboard():
    """Main governance dashboard."""
    return render_template("governance/dashboard.html")


@governance_bp.route("/api/metrics")
@login_required
def api_metrics():
    """API endpoint to get governance metrics."""
    try:
        from app.models.solution_governance import SolutionARBReview as SolutionGovernance
        
        # Count pending ARB reviews
        pending_reviews = db.session.query(SolutionGovernance).filter(
            SolutionGovernance.arb_decision.in_(['pending', 'in_review', 'arb_review'])
        ).count()
        
        # Count active risks (if risk model exists)
        active_risks = 0
        try:
            from app.models.risk import Risk, RiskStatus
            # 'severity' is not a column; risk level derives from likelihood*impact
            # (>=9 == high/critical). 'status' is a RiskStatus enum (OPEN == active),
            # not the string 'active'. The old filters raised AttributeError (swallowed
            # below), so this metric was always 0.
            active_risks = db.session.query(Risk).filter(
                Risk.status == RiskStatus.OPEN,
                (Risk.likelihood * Risk.impact) >= 9,
            ).count()
        except Exception:
            pass
        
        # Count recent ADRs (last 90 days)
        recent_adrs = 0
        try:
            from app.models.architecture_decision import ArchitectureDecision
            ninety_days_ago = datetime.utcnow() - timedelta(days=90)
            recent_adrs = db.session.query(ArchitectureDecision).filter(
                ArchitectureDecision.created_at >= ninety_days_ago
            ).count()
        except Exception:
            pass
        
        # Calculate compliance rate
        total_solutions = db.session.query(SolutionGovernance).count()
        approved_solutions = db.session.query(SolutionGovernance).filter(
            SolutionGovernance.arb_decision == 'approved'
        ).count()
        compliance_rate = round((approved_solutions / total_solutions * 100) if total_solutions > 0 else 0, 1)
        
        return jsonify({
            'pending_reviews': pending_reviews,
            'active_risks': active_risks,
            'recent_adrs': recent_adrs,
            'compliance_rate': compliance_rate
        })
    except Exception as e:
        # Previously returned all-zero metrics with HTTP 200, which the dashboard
        # rendered as fact — "Compliance Rate 0%" for a query that never ran.
        # Fail loudly so the client shows its "could not be loaded" state instead.
        logger.error(f"Error getting governance metrics: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load governance metrics'}), 500


@governance_bp.route("/api/principles")
@login_required
def api_principles():
    """Architecture principles for the governance dashboard.

    Reads the ArchiMate Principle element (app/models/models.py) — the backbone
    model per DESIGN.md — rather than a parallel governance-only table. This
    previously imported a non-existent `app.models.architecture_principle`, so
    the ImportError branch silently returned [] and the dashboard showed nothing.

    Tenant scoping is implicit: Principle carries TenantMixin, so do_orm_execute
    injects `WHERE organization_id = g.current_org_id`. Rows predating that change
    have a NULL organization_id and are excluded until
    `flask --app manage backfill-principle-org` has been run.
    """
    try:
        from app.models.models import Principle

        # Deprecated/superseded principles are not current governance.
        principles = (
            db.session.query(Principle)
            .filter(Principle.status.notin_(["deprecated", "superseded"]))
            .order_by(Principle.name)
            .all()
        )

        return jsonify([{
            'id': p.id,
            'name': p.name,
            'statement': p.statement,
            # The dashboard renders `priority` as a badge (Critical -> destructive).
            # RFC-2119 enforcement level is the closest real signal we hold.
            'priority': _ENFORCEMENT_TO_PRIORITY.get(
                (p.enforcement_level or "").upper(), p.enforcement_level or "—"
            ),
            'domain': p.category or "—",
        } for p in principles])
    except Exception as e:
        logger.error(f"Error getting principles: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load architecture principles'}), 500


@governance_bp.route("/api/standards")
@login_required
def api_standards():
    """Approved-technology register for the governance dashboard.

    The TechnologyStandard model did not exist when this route was written, so the
    ImportError branch silently returned [] — which is what drove the template's
    fabricated "Python 3.11+ / Approved" fallback. Tenant-scoped via TenantMixin.
    """
    try:
        from app.models.technology_standard import TechnologyStandard

        standards = (
            db.session.query(TechnologyStandard)
            .filter(TechnologyStandard.is_active.is_(True))
            .order_by(TechnologyStandard.category, TechnologyStandard.technology_name)
            .all()
        )
        return jsonify([s.to_dict() for s in standards])
    except Exception as e:
        logger.error(f"Error getting standards: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load technology standards'}), 500


@governance_bp.route("/api/reviews/recent")
@login_required
def api_recent_reviews():
    """API endpoint to get recent ARB reviews."""
    try:
        from app.models.solution_governance import SolutionARBReview as SolutionGovernance
        from app.models.solution_models import Solution
        
        reviews = db.session.query(
            SolutionGovernance, Solution
        ).join(
            Solution, SolutionGovernance.solution_id == Solution.id
        ).order_by(
            SolutionGovernance.submitted_at.desc()
        ).limit(10).all()
        
        return jsonify([{
            'id': gov.id,
            'solution_name': sol.name,
            'review_date': gov.submitted_at.strftime('%Y-%m-%d') if gov.submitted_at else 'N/A',
            'status': gov.arb_decision,
            'reviewer': gov.reviewer_name if hasattr(gov, 'reviewer_name') else 'ARB'
        } for gov, sol in reviews])
    except Exception as e:
        # Was: return [] with HTTP 200 — indistinguishable from "no reviews exist".
        logger.error(f"Error getting recent reviews: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load recent ARB reviews'}), 500


@governance_bp.route("/arb-reviews")
@login_required
def arb_reviews():
    """ARB Reviews page."""
    return render_template("governance/arb_reviews.html")


@governance_bp.route("/adr-list")
@login_required
def adr_list():
    """Architecture Decision Records list page."""
    return render_template("governance/adr_list.html")


@governance_bp.route("/risk-register")
@login_required
def risk_register():
    """Risk Register page."""
    return render_template("governance/risk_register.html")


@governance_bp.route("/principles")
@login_required
@require_roles("admin", "architect")
def principles():
    """Architecture Principles management page."""
    return render_template("governance/principles.html")


@governance_bp.route("/standards")
@login_required
@require_roles("admin", "architect")
def standards():
    """Technology Standards management page."""
    return render_template("governance/standards.html")


@governance_bp.route("/roadmap")
@login_required
def roadmap():
    """Enterprise Roadmap page."""
    return render_template("governance/roadmap.html")
