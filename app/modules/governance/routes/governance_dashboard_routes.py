"""
Governance Dashboard Routes
Provides central governance oversight, ARB reviews, ADRs, risk register, and enterprise roadmap.
"""
import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user

from app import db
from app.decorators import audit_log, require_roles

logger = logging.getLogger(__name__)

governance_bp = Blueprint("governance", __name__, url_prefix="/governance")


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
        from app.models.solution_governance import SolutionGovernance
        from app.models.governance_gates import GovernanceGate
        
        # Count pending ARB reviews
        pending_reviews = db.session.query(SolutionGovernance).filter(
            SolutionGovernance.status.in_(['pending', 'in_review', 'arb_review'])
        ).count()
        
        # Count active risks (if risk model exists)
        active_risks = 0
        try:
            from app.models.risk import Risk
            active_risks = db.session.query(Risk).filter(
                Risk.status == 'active',
                Risk.severity.in_(['high', 'critical'])
            ).count()
        except ImportError:
            pass
        
        # Count recent ADRs (last 90 days)
        recent_adrs = 0
        try:
            from app.models.architecture_decision import ArchitectureDecision
            ninety_days_ago = datetime.utcnow() - timedelta(days=90)
            recent_adrs = db.session.query(ArchitectureDecision).filter(
                ArchitectureDecision.created_at >= ninety_days_ago
            ).count()
        except ImportError:
            pass
        
        # Calculate compliance rate
        total_solutions = db.session.query(SolutionGovernance).count()
        approved_solutions = db.session.query(SolutionGovernance).filter(
            SolutionGovernance.status == 'approved'
        ).count()
        compliance_rate = round((approved_solutions / total_solutions * 100) if total_solutions > 0 else 0, 1)
        
        return jsonify({
            'pending_reviews': pending_reviews,
            'active_risks': active_risks,
            'recent_adrs': recent_adrs,
            'compliance_rate': compliance_rate
        })
    except Exception as e:
        logger.error(f"Error getting governance metrics: {e}")
        return jsonify({
            'pending_reviews': 0,
            'active_risks': 0,
            'recent_adrs': 0,
            'compliance_rate': 0
        }), 200


@governance_bp.route("/api/principles")
@login_required
def api_principles():
    """API endpoint to get architecture principles."""
    try:
        from app.models.architecture_principle import ArchitecturePrinciple
        
        principles = db.session.query(ArchitecturePrinciple).filter(
            ArchitecturePrinciple.is_active == True
        ).all()
        
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'statement': p.statement,
            'priority': p.priority,
            'domain': p.domain
        } for p in principles])
    except ImportError:
        logger.warning("ArchitecturePrinciple model not found")
        return jsonify([])
    except Exception as e:
        logger.error(f"Error getting principles: {e}")
        return jsonify([]), 500


@governance_bp.route("/api/standards")
@login_required
def api_standards():
    """API endpoint to get technology standards."""
    try:
        from app.models.technology_standard import TechnologyStandard
        
        standards = db.session.query(TechnologyStandard).filter(
            TechnologyStandard.is_active == True
        ).all()
        
        return jsonify([{
            'id': s.id,
            'technology': s.technology_name,
            'category': s.category,
            'status': s.status,
            'version': s.approved_version
        } for s in standards])
    except ImportError:
        logger.warning("TechnologyStandard model not found")
        return jsonify([])
    except Exception as e:
        logger.error(f"Error getting standards: {e}")
        return jsonify([]), 500


@governance_bp.route("/api/reviews/recent")
@login_required
def api_recent_reviews():
    """API endpoint to get recent ARB reviews."""
    try:
        from app.models.solution_governance import SolutionGovernance
        from app.models.solution import Solution
        
        reviews = db.session.query(
            SolutionGovernance, Solution
        ).join(
            Solution, SolutionGovernance.solution_id == Solution.id
        ).order_by(
            SolutionGovernance.review_date.desc()
        ).limit(10).all()
        
        return jsonify([{
            'id': gov.id,
            'solution_name': sol.name,
            'review_date': gov.review_date.strftime('%Y-%m-%d') if gov.review_date else 'N/A',
            'status': gov.status,
            'reviewer': gov.reviewer_name if hasattr(gov, 'reviewer_name') else 'ARB'
        } for gov, sol in reviews])
    except Exception as e:
        logger.error(f"Error getting recent reviews: {e}")
        return jsonify([]), 200


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
