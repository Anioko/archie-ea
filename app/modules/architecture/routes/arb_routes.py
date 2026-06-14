"""
DEPRECATED: This file is migrated to app/modules/architecture/.
Registration is now centralized via app.modules.architecture.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

Architecture Review Board (ARB) Routes

Flask routes for ARB web interface and API endpoints.
Integrates with existing platform workflows and provides TOGAF-aligned governance.
"""

from datetime import datetime, timedelta
from typing import List

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app import db
from app.models.architecture_review_board import (
    ARBBoardMember,
    ARBCapabilityImpact,
    ARBGovernanceStandard,
    ARBReviewComment,
    ARBReviewItem,
    ArchitectureReviewBoard,
    ReviewType,
    TOGAFPhase,
)
from app.decorators import audit_log, require_roles
from app.services.arb_analytics_service import ARBAnalyticsService
from app.services.rate_limiter import rate_limit
from app.services.arb_governance_service import ARBGovernanceService

arb_bp = Blueprint("arb", __name__, url_prefix="/arb")
arb_service = ARBGovernanceService()
arb_analytics = ARBAnalyticsService()


# =========================================================================
# ARB SESSION MANAGEMENT ROUTES
# =========================================================================


@arb_bp.route("/dashboard")
@login_required
def dashboard_redirect():
    """Redirect /arb/dashboard to canonical /arb/ URL."""
    return redirect(url_for("arb.dashboard"))


@arb_bp.route("/")
@login_required
def dashboard():
    """ARB Dashboard - Overview of all governance activities."""
    try:
        dashboard_data = arb_service.get_governance_dashboard()

        # Get user's specific items
        my_submitted = (
            ARBReviewItem.query.filter_by(submitter_id=current_user.id)
            .order_by(ARBReviewItem.created_at.desc())
            .limit(5)
            .all()
        )

        my_reviews = (
            ARBReviewItem.query.filter_by(reviewer_id=current_user.id)
            .order_by(ARBReviewItem.review_started_at.desc())
            .limit(5)
            .all()
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error loading ARB dashboard: {e}")
        dashboard_data = {
            "metrics": {
                "total_items": 0,
                "pending_items": 0,
                "approved_items": 0,
                "rejected_items": 0,
                "approval_rate": 0,
            },
            "recent_reviews": [],
            "upcoming_sessions": [],
            "review_types": [],
            "togaf_phases": [],
        }
        my_submitted = []
        my_reviews = []

    # Decision analytics data
    try:
        analytics_trends = arb_analytics.get_approval_trends(12)
        cycle_time = arb_analytics.get_cycle_time_analytics(90)
        standards_summary = arb_analytics.get_standard_compliance_summary()

        # Overdue items: submitted/under_review older than priority thresholds
        now = datetime.utcnow()
        overdue_thresholds = {"critical": 7, "high": 14, "medium": 21, "low": 30}
        overdue_items = []
        for priority_val, days_threshold in overdue_thresholds.items():
            cutoff = now - timedelta(days=days_threshold)
            items = (
                ARBReviewItem.query.filter(
                    ARBReviewItem.status.in_(["submitted", "under_review"]),
                    ARBReviewItem.priority == priority_val,
                    ARBReviewItem.submitted_at.isnot(None),
                    ARBReviewItem.submitted_at <= cutoff,
                )
                .order_by(ARBReviewItem.submitted_at.asc())
                .all()
            )
            for item in items:
                overdue_items.append(
                    {
                        "review": item,
                        "days_overdue": (now - item.submitted_at).days,
                        "threshold": days_threshold,
                    }
                )
        overdue_items.sort(
            key=lambda x: (
                {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
                    x["review"].priority, 4
                ),
                -x["days_overdue"],
            )
        )

        # Capability impact summary
        from sqlalchemy import func as sa_func

        capability_impacts_raw = (
            db.session.query(
                ARBCapabilityImpact.capability_id,
                sa_func.count(ARBCapabilityImpact.id).label("review_count"),
            )
            .group_by(ARBCapabilityImpact.capability_id)
            .order_by(sa_func.count(ARBCapabilityImpact.id).desc())
            .limit(20)
            .all()
        )
        capability_impacts = []
        for cap_id, review_count in capability_impacts_raw:
            cap_impact = ARBCapabilityImpact.query.filter_by(
                capability_id=cap_id
            ).first()
            cap_name = (
                cap_impact.capability.name
                if cap_impact and cap_impact.capability
                else f"Capability {cap_id}"
            )
            # Count by impact level
            high_count = ARBCapabilityImpact.query.filter_by(
                capability_id=cap_id, impact_level="high"
            ).count()
            medium_count = ARBCapabilityImpact.query.filter_by(
                capability_id=cap_id, impact_level="medium"
            ).count()
            low_count = ARBCapabilityImpact.query.filter_by(
                capability_id=cap_id, impact_level="low"
            ).count()
            capability_impacts.append(
                {
                    "capability_id": cap_id,
                    "name": cap_name,
                    "review_count": review_count,
                    "high": high_count,
                    "medium": medium_count,
                    "low": low_count,
                }
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error loading ARB analytics: {e}")
        analytics_trends = {"trends": []}
        cycle_time = {"avg_days": 0, "min_days": 0, "max_days": 0, "median_days": 0}
        standards_summary = {
            "total_standards": 0,
            "mandatory_count": 0,
            "standards": [],
        }
        overdue_items = []
        capability_impacts = []

    # Decisions list (recent decisions with recorded decisions) - WITH FILTERS
    try:
        # Get filter parameters
        search_query = request.args.get("search", "").strip()
        capability_id = request.args.get("capability_id", type=int)
        date_from = request.args.get("date_from")
        date_to = request.args.get("date_to")

        # Build query with filters
        query = ARBReviewItem.query.filter(ARBReviewItem.decision.isnot(None))

        # Apply search filter
        if search_query:
            query = query.filter(ARBReviewItem.title.ilike(f"%{search_query}%"))

        # Apply capability filter
        if capability_id:
            query = query.join(ARBReviewItem.capability_links).filter(
                ARBCapabilityImpact.capability_id == capability_id
            )

        # Apply date range filters
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
                query = query.filter(ARBReviewItem.decision_date >= date_from_obj)
            except ValueError:
                pass  # Ignore invalid date format

        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
                # Add 1 day to include the entire end date
                date_to_obj = date_to_obj + timedelta(days=1)
                query = query.filter(ARBReviewItem.decision_date < date_to_obj)
            except ValueError:
                pass  # Ignore invalid date format

        # Apply eager loading and ordering
        decisions = (
            query.options(
                joinedload(ARBReviewItem.capability_links).joinedload(
                    ARBCapabilityImpact.capability
                ),
                joinedload(ARBReviewItem.solution),
                joinedload(ARBReviewItem.architecture_model),
                joinedload(ARBReviewItem.decided_by),
            )
            .order_by(ARBReviewItem.decision_date.desc())
            .limit(200)
            .all()
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error loading decisions: {e}")
        decisions = []

    # Resolve application names from capability_impacts.application_ids for each decision
    application_names_by_review = {}
    if decisions:
        from app.models.application_portfolio import ApplicationComponent
        all_app_ids = set()
        for rev in decisions:
            cap = rev.capability_impacts if isinstance(rev.capability_impacts, dict) else {}
            ids = cap.get("application_ids") or []
            for aid in ids:
                all_app_ids.add(int(aid))
        if all_app_ids:
            apps = ApplicationComponent.query.filter(ApplicationComponent.id.in_(all_app_ids)).all()
            app_id_to_name = {a.id: a.name for a in apps if a.name}
            for rev in decisions:
                cap = rev.capability_impacts if isinstance(rev.capability_impacts, dict) else {}
                ids = cap.get("application_ids") or []
                names = [app_id_to_name[int(aid)] for aid in ids if int(aid) in app_id_to_name]
                if names:
                    application_names_by_review[rev.id] = names

    # Get recent ARB sessions for dashboard
    try:
        page = request.args.get("page", 1, type=int)
        recent_sessions = ArchitectureReviewBoard.query.order_by(
            ArchitectureReviewBoard.scheduled_date.desc()
        ).paginate(page=page, per_page=10, error_out=False)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error loading recent ARB sessions: {e}")

        # Create a mock pagination-like object with empty items
        class EmptyPagination:
            items = []
            pages = 0
            page = 1
            has_next = False
            has_prev = False

        recent_sessions = EmptyPagination()

    # Pending reviews queue for the dashboard table
    try:
        pending_status = request.args.get("pending_status", "all")
        pending_query = ARBReviewItem.query.filter(
            ARBReviewItem.status.in_(["submitted", "pending", "under_review", "draft"])
        )
        if pending_status != "all":
            pending_query = pending_query.filter(ARBReviewItem.status == pending_status)
        pending_reviews = (
            pending_query
            .options(joinedload(ARBReviewItem.solution))
            .order_by(ARBReviewItem.created_at.desc())
            .limit(15)
            .all()
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error loading pending reviews: {e}")
        pending_reviews = []
        pending_status = "all"

    # ARB-101: compute per-row SLA badge data for decisions table
    _SLA_THRESHOLDS = {"critical": 7, "high": 14, "medium": 21, "low": 30}
    sla_data_by_review = {}
    _now = datetime.utcnow()
    for _rev in decisions:
        if _rev.submitted_at and _rev.priority:
            _sla_days = _SLA_THRESHOLDS.get(_rev.priority, 30)
            _days_pending = (_now - _rev.submitted_at).days
            _days_left = _sla_days - _days_pending
            _pct = max(0.0, _days_left / _sla_days * 100) if _sla_days else 0.0
            if _pct > 50:
                _cls = "bg-emerald-100 text-emerald-800"
                _txt = f"{max(0, _days_left)}d remaining"
            elif _pct >= 25:
                _cls = "bg-amber-100 text-amber-800"
                _txt = f"{max(0, _days_left)}d remaining"
            else:
                _cls = "bg-red-100 text-red-800"
                _txt = f"{abs(_days_left)}d overdue" if _days_left < 0 else f"{_days_left}d remaining"
            sla_data_by_review[_rev.id] = {"cls": _cls, "txt": _txt}

    return render_template(
        "arb/dashboard.html",
        sessions=recent_sessions,
        status=request.args.get("status", "all"),
        pending_reviews=pending_reviews,
        pending_status=pending_status,
        dashboard_data=dashboard_data,
        my_submitted=my_submitted,
        my_reviews=my_reviews,
        analytics_trends=analytics_trends,
        cycle_time=cycle_time,
        standards_summary=standards_summary,
        overdue_items=overdue_items,
        capability_impacts=capability_impacts,
        decisions=decisions,
        application_names_by_review=application_names_by_review,
        sla_data_by_review=sla_data_by_review,
    )


def _chair_candidates():
    """Active users for the session chair/secretary pickers.

    arb/sessions.html iterates `users` to populate the Schedule-Session modal;
    without it the required Chair select is empty and no session can be created.
    """
    try:
        from app.models.user import User
        return (
            User.query.filter_by(confirmed=True)
            .order_by(User.first_name, User.last_name)
            .limit(200)
            .all()
        )
    except Exception as exc:
        current_app.logger.error("ARB chair candidates load failed: %s", exc)
        db.session.rollback()
        return []


@arb_bp.route("/sessions")
@login_required
def sessions():
    """List all ARB sessions."""
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "all")

    try:
        query = ArchitectureReviewBoard.query

        if status != "all":
            query = query.filter_by(status=status)

        sessions = query.order_by(
            ArchitectureReviewBoard.scheduled_date.desc()
        ).paginate(page=page, per_page=20, error_out=False)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error loading ARB sessions: {e}")

        # Create a mock pagination-like object with empty items
        class EmptyPagination:
            items = []
            pages = 0
            page = 1
            has_next = False
            has_prev = False

        sessions = EmptyPagination()

    return render_template(
        "arb/sessions.html", sessions=sessions, status=status, users=_chair_candidates()
    )


@arb_bp.route("/sessions/create", methods=["GET", "POST"])
@login_required
def create_session():
    """Create a new ARB session."""
    if request.method == "POST":
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        try:
            data = request.get_json() if request.is_json else request.form.to_dict()

            if not data.get("name"):
                if is_json:
                    return jsonify({"success": False, "errors": {"name": "Session name is required"}}), 400
                flash("Session name is required.", "error")
                return redirect(url_for("arb.create_session"))

            if not data.get("scheduled_date"):
                if is_json:
                    return jsonify({"success": False, "errors": {"scheduled_date": "Scheduled date is required"}}), 400
                flash("Scheduled date is required.", "error")
                return redirect(url_for("arb.create_session"))

            if not data.get("chair_id"):
                if is_json:
                    return jsonify({"success": False, "errors": {"chair_id": "Chair is required"}}), 400
                flash("Chair is required.", "error")
                return redirect(url_for("arb.create_session"))

            # Parse scheduled date — support both datetime-local (T separator) and space separator
            raw_date = data.get("scheduled_date", "").replace("T", " ")
            scheduled_date = datetime.strptime(raw_date, "%Y-%m-%d %H:%M")

            arb = arb_service.create_arb_session(
                name=data.get("name"),
                scheduled_date=scheduled_date,
                chair_id=int(data.get("chair_id")),
                description=data.get("description"),
                duration_minutes=int(data.get("duration_minutes") or 120),
                location=data.get("location"),
                meeting_link=data.get("meeting_link"),
                secretary_id=int(data.get("secretary_id"))
                if data.get("secretary_id")
                else None,
            )

            if is_json:
                return jsonify({"success": True, "id": arb.id, "board_number": arb.board_number}), 201

            flash(f"ARB session {arb.board_number} created successfully", "success")
            return redirect(url_for("arb.session_detail", id=arb.id))

        except Exception as e:
            current_app.logger.error(f"Error creating ARB session: {e}")
            if is_json:
                return jsonify({"success": False, "errors": {"general": str(e)}}), 500
            flash("Error creating session. Please try again.", "error")

    # GET — redirect to sessions list (modal handles creation inline)
    return redirect(url_for("arb.sessions"))


@arb_bp.route("/sessions/<int:id>")
@login_required
def session_detail(id):
    """View ARB session details."""
    session = ArchitectureReviewBoard.query.options(
        joinedload(ArchitectureReviewBoard.review_items),
        joinedload(ArchitectureReviewBoard.board_members).joinedload(
            ARBBoardMember.user
        ),
        joinedload(ArchitectureReviewBoard.chair),
        joinedload(ArchitectureReviewBoard.secretary),
    ).get_or_404(id)

    return render_template("arb/session_detail.html", session=session)


@arb_bp.route("/sessions/<int:id>/complete", methods=["POST"])
@login_required
@audit_log("arb_session_complete")
def complete_session(id):
    """Complete an ARB session."""
    try:
        # AUDIT-ARB-002: Quorum validation - require at least 3 board members
        arb_session = ArchitectureReviewBoard.query.get_or_404(id)
        member_count = (
            len(arb_session.board_members) if arb_session.board_members else 0
        )
        minimum_quorum = 3

        if member_count < minimum_quorum:
            flash(
                f"Cannot complete session: quorum not met. "
                f"At least {minimum_quorum} board members are required, "
                f"but only {member_count} member(s) are assigned.",
                "error",
            )
            return redirect(url_for("arb.session_detail", id=id))

        minutes = request.form.get("minutes")
        session = arb_service.complete_session(id, minutes)
        flash(f"ARB session {session.board_number} completed successfully", "success")
        return redirect(url_for("arb.session_detail", id=id))
    except Exception as e:
        current_app.logger.error(f"Error completing ARB session: {e}")
        flash("Error completing session. Please try again.", "error")
        return redirect(url_for("arb.session_detail", id=id))


@arb_bp.route("/sessions/<int:id>/cancel", methods=["POST"])
@login_required
@audit_log("arb_session_cancel")
def cancel_session(id):
    """Cancel a scheduled/draft ARB session.

    session_detail.html has rendered a Cancel button via
    url_for('arb.cancel_session') since PLT-era — the endpoint was never
    implemented, so every detail page for scheduled/draft sessions 500'd
    on the url_for BuildError.
    """
    try:
        arb_session = ArchitectureReviewBoard.query.get_or_404(id)
        if arb_session.status not in ("scheduled", "draft"):
            flash("Only scheduled or draft sessions can be cancelled.", "error")
            return redirect(url_for("arb.session_detail", id=id))
        arb_session.status = "cancelled"
        db.session.commit()
        flash(f"ARB session {arb_session.board_number} cancelled.", "success")
        return redirect(url_for("arb.sessions"))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cancelling ARB session: {e}")
        flash("Error cancelling session. Please try again.", "error")
        return redirect(url_for("arb.session_detail", id=id))


@arb_bp.route("/sessions/<int:session_id>/add_member", methods=["POST"])
@login_required
@require_roles("admin", "enterprise_architect")
@audit_log("arb_member_add")
def add_board_member(session_id):
    """Add a member to an ARB session."""
    try:
        data = request.form.to_dict()
        member = arb_service.add_board_member(
            arb_session_id=session_id,
            user_id=int(data.get("user_id")),
            role=data.get("role"),
            voting_member=data.get("voting_member") == "on",
        )
        flash("Board member added successfully", "success")
    except Exception as e:
        current_app.logger.error(f"Error adding board member: {e}")
        flash("Error adding member. Please try again.", "error")

    return redirect(url_for("arb.session_detail", id=session_id))


# =========================================================================
# REVIEW ITEM MANAGEMENT ROUTES
# =========================================================================


@arb_bp.route("/reviews")
@login_required
def reviews():
    """List all review items."""
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "all")
    review_type = request.args.get("review_type", "all")

    query = ARBReviewItem.query

    if status != "all":
        query = query.filter_by(status=status)

    if review_type != "all":
        query = query.filter_by(review_type=review_type)

    pagination = query.order_by(ARBReviewItem.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    # Pass is_reviews_view=True so the template renders review-specific
    # labels and links (review_detail instead of session_detail).
    return render_template(
        "arb/sessions.html",
        sessions=pagination,
        reviews=pagination.items,
        status=status,
        review_type=review_type,
        is_reviews_view=True,
        users=_chair_candidates(),
    )


@arb_bp.route("/review/new")
@login_required
def review_new_redirect():
    """Redirect legacy /arb/review/new to the canonical /arb/reviews/create."""
    return redirect(url_for("arb.create_review"))


@arb_bp.route("/reviews/create", methods=["GET", "POST"])
@login_required
@audit_log("arb_review_create")
@rate_limit(10, "1h")
def create_review():
    """Create a new review item."""
    if request.method == "POST":
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        try:
            data = request.get_json() if request.is_json else request.form.to_dict()

            review_type = data.get("review_type")
            capability_required_types = ["solution_design", "capability_implementation", "technology_selection"]

            # Validation: decision_sought is required
            decision_sought_val = (data.get("decision_sought") or "").strip()
            if not decision_sought_val:
                if is_json:
                    return (
                        jsonify({
                            "success": False,
                            "errors": {"decision_sought": "Decision sought is required."},
                        }),
                        400,
                    )
                flash("Decision sought is required.", "error")
                return redirect(url_for("arb.dashboard"))

            # Parse capability impacts (structured: capability_id, impact_type, impact_level)
            capability_impacts = []
            raw_impacts = data.get("capability_impacts")
            if raw_impacts and isinstance(raw_impacts, list):
                for imp in raw_impacts:
                    cap_id = imp.get("capability_id") if isinstance(imp, dict) else imp
                    if cap_id:
                        raw_impact = imp.get("impact_type", "modifies") if isinstance(imp, dict) else "modifies"
                        capability_impacts.append({
                            "capability_id": int(cap_id),
                            "impact_type": _normalize_impact_type(raw_impact),
                            "impact_level": imp.get("impact_level", "medium") if isinstance(imp, dict) else "medium",
                            "level": imp.get("level") if isinstance(imp, dict) else None,
                        })
            # Fallback: legacy capability_ids list
            if not capability_impacts and data.get("capability_ids"):
                raw = data.get("capability_ids")
                ids = [int(i) for i in raw] if isinstance(raw, list) else [int(i.strip()) for i in raw.split(",") if i.strip()]
                default_impact = data.get("capability_impact_type") or "modifies"
                for cap_id in ids:
                    capability_impacts.append({"capability_id": cap_id, "impact_type": _normalize_impact_type(default_impact), "impact_level": "medium"})

            # Validation: capability required for certain review types
            if review_type in capability_required_types and not capability_impacts:
                if is_json:
                    return (
                        jsonify({
                            "success": False,
                            "errors": {"capability_ids": f"At least one capability is required for {review_type.replace('_', ' ')} reviews."},
                        }),
                        400,
                    )
                flash(f"At least one capability is required for {review_type.replace('_', ' ')} reviews.", "error")
                return redirect(url_for("arb.dashboard"))

            # Parse application IDs
            application_ids = []
            if data.get("application_ids"):
                raw = data.get("application_ids")
                if isinstance(raw, list):
                    application_ids = [int(i) for i in raw]
                else:
                    application_ids = [int(i.strip()) for i in str(raw).split(",") if i.strip()]

            review_item = arb_service.submit_for_review(
                title=data.get("title"),
                description=data.get("description"),
                review_type=review_type,
                submitter_id=current_user.id,
                togaf_phase=data.get("togaf_phase") or None,
                archimate_layer=data.get("archimate_layer") or None,
                solution_id=int(data.get("solution_id")) if data.get("solution_id") else None,
                adr_id=int(data.get("adr_id")) if data.get("adr_id") else None,
                architecture_model_id=int(data.get("architecture_model_id")) if data.get("architecture_model_id") else None,
                priority=data.get("priority", "medium"),
                business_impact=data.get("business_impact", "medium"),
                estimated_effort=data.get("estimated_effort", "medium"),
                capability_ids=None,
                decision_sought=decision_sought_val or None,
                alternatives_considered=data.get("alternatives_considered") or None,
                application_ids=application_ids or None,
                capability_impacts=capability_impacts if capability_impacts else None,
            )

            if is_json:
                return jsonify({"success": True, "id": review_item.id, "review_number": review_item.review_number}), 201

            flash(
                f"Review item {review_item.review_number} created successfully",
                "success",
            )
            return redirect(url_for("arb.review_detail", id=review_item.id))

        except Exception as e:
            current_app.logger.error(f"Error creating review item: {e}")
            if is_json:
                return jsonify({"success": False, "errors": {"general": str(e)}}), 500
            flash("Error creating review. Please try again.", "error")

    # GET — redirect to dashboard (modal handles creation inline)
    return redirect(url_for("arb.dashboard"))


@arb_bp.route("/reviews/<int:id>")
@login_required
def review_detail(id):
    """View review item details."""
    review = ARBReviewItem.query.options(
        joinedload(ARBReviewItem.submitter),
        joinedload(ARBReviewItem.reviewer),
        joinedload(ARBReviewItem.decided_by),
        joinedload(ARBReviewItem.solution),
        joinedload(ARBReviewItem.adr),
        joinedload(ARBReviewItem.architecture_model),
        joinedload(ARBReviewItem.capability_links).joinedload(
            ARBCapabilityImpact.capability
        ),
        joinedload(ARBReviewItem.comments).joinedload(ARBReviewComment.user),
    ).get_or_404(id)

    # Resolve application names from capability_impacts.application_ids
    application_names = []
    cap_impacts = review.capability_impacts if isinstance(review.capability_impacts, dict) else {}
    app_ids = cap_impacts.get("application_ids") or []
    if app_ids:
        from app.models.application_portfolio import ApplicationComponent
        apps = ApplicationComponent.query.filter(ApplicationComponent.id.in_(app_ids)).all()
        application_names = [a.name for a in apps if a.name]

    # IA-012: enrich with canonical impact analysis for first app in scope
    canonical_impact = None
    if app_ids:
        try:
            from app.modules.ai_chat.services.ai_impact_analysis_service import AIImpactAnalysisService
            raw = AIImpactAnalysisService().analyze_application_impact(
                app_id=app_ids[0], scenario="modification"
            )
            if raw:
                ra = raw.get("risk_assessment") or {}
                canonical_impact = {
                    "risk_level": ra.get("risk_level") or raw.get("risk_level", "LOW"),
                    "total_score": ra.get("total_score", 0),
                    "breakdown": ra.get("breakdown") or {},
                    "app_count": len(app_ids),
                }
        except Exception:  # fabricated-values-ok: best-effort score enrichment, non-fatal
            logger.exception("Failed to operation")
            pass

    # ARB-101: compute SLA banner info for review detail
    _SLA_THRESHOLDS = {"critical": 7, "high": 14, "medium": 21, "low": 30}
    sla_info = None
    if review.submitted_at and review.status in ("submitted", "under_review", "pending_info"):
        _sla_days = _SLA_THRESHOLDS.get(review.priority or "low", 30)
        _days_pending = (datetime.utcnow() - review.submitted_at).days
        _days_left = _sla_days - _days_pending
        _pct = max(0.0, _days_left / _sla_days * 100) if _sla_days else 0.0
        if _pct > 50:
            _bg = "bg-emerald-50 border-emerald-200"
            _icon = "text-emerald-600"
            _txt = f"{max(0, _days_left)} days remaining"
        elif _pct >= 25:
            _bg = "bg-amber-50 border-amber-200"
            _icon = "text-amber-600"
            _txt = f"{max(0, _days_left)} days remaining"
        else:
            _bg = "bg-red-50 border-red-200"
            _icon = "text-red-600"
            _txt = f"{abs(_days_left)} days overdue" if _days_left < 0 else f"{_days_left} days remaining"
        sla_info = {
            "bg": _bg, "icon": _icon, "txt": _txt,
            "sla_days": _sla_days, "days_pending": _days_pending,
            "priority": review.priority or "low",
        }

    # ARB-102: build conditions_with_flags for approved_with_conditions tracker
    conditions_with_flags = []
    if review.decision == "approved_with_conditions" and review.conditions:
        today = datetime.utcnow().date().isoformat()
        for c in (review.conditions if isinstance(review.conditions, list) else []):
            entry = dict(c) if isinstance(c, dict) else {"condition": str(c)}
            due = entry.get("due_date")
            entry["overdue"] = bool(
                due and entry.get("status") != "done" and due < today
            )
            conditions_with_flags.append(entry)

    # Bug 2: fetch active architecture principles to display in review detail
    applicable_principles = []
    try:
        from app.models.models import Principle
        applicable_principles = (
            Principle.query
            .filter(Principle.status == "approved")
            .order_by(Principle.category, Principle.name)
            .limit(20)
            .all()
        )
    except Exception:
        pass  # principles table may not yet be populated — degrade gracefully

    return render_template(
        "arb/review_detail.html",
        review=review,
        application_names=application_names,
        canonical_impact=canonical_impact,
        sla_info=sla_info,
        conditions_with_flags=conditions_with_flags,
        applicable_principles=applicable_principles,
    )


@arb_bp.route("/reviews/<int:id>/submit", methods=["POST"])
@login_required
@audit_log("arb_review_submit")
@rate_limit(10, "1h")
def submit_review(id):
    """Submit a draft review item for ARB consideration."""
    try:
        review = arb_service.submit_item(id)
        flash(f"Review item {review.review_number} submitted successfully", "success")
        return redirect(url_for("arb.review_detail", id=id))
    except Exception as e:
        current_app.logger.error(f"Error submitting review: {e}")
        flash("Error submitting review. Please try again.", "error")
        return redirect(url_for("arb.review_detail", id=id))


@arb_bp.route("/reviews/<int:id>/assign", methods=["POST"])
@login_required
@audit_log("arb_review_assign")
def assign_to_session(id):
    """Assign review item to an ARB session."""
    try:
        data = request.form.to_dict()
        review = arb_service.assign_to_session(id, int(data.get("arb_session_id")))
        flash(f"Review item assigned to ARB session", "success")
        return redirect(url_for("arb.review_detail", id=id))
    except Exception as e:
        current_app.logger.error(f"Error assigning to session: {e}")
        flash("Error assigning to session. Please try again.", "error")
        return redirect(url_for("arb.review_detail", id=id))


@arb_bp.route("/reviews/<int:id>/decision", methods=["POST"])
@login_required
@audit_log("arb_decision_record")
def record_decision(id):
    """Record ARB decision for a review item."""
    try:
        data = request.form.to_dict()

        # Parse conditions if provided
        conditions = []
        if data.get("conditions"):
            for condition_line in data.get("conditions").strip().split("\n"):
                if condition_line.strip():
                    conditions.append(
                        {
                            "condition": condition_line.strip(),
                            "status": "pending",
                            "due_date": (
                                datetime.utcnow() + timedelta(days=30)
                            ).isoformat(),
                        }
                    )

        review = arb_service.record_decision(
            review_item_id=id,
            decision=data.get("decision"),
            rationale=data.get("rationale"),
            decided_by_id=current_user.id,
            conditions=conditions if conditions else None,
        )

        # Sync ARB decision to capability (if this is a capability review)
        try:
            from app.services.arb_integration_service import ARBIntegrationService

            integration_service = ARBIntegrationService()
            capability = integration_service.sync_arb_decision_to_capability(id)
            if capability:
                flash(f"ARB decision synced to capability: {capability.name}", "info")
        except Exception as sync_error:
            current_app.logger.warning(
                f"Failed to sync ARB decision to capability: {sync_error}"
            )
            # Don't fail the entire request if sync fails

        # Sync ARB decision back to linked solutions
        try:
            from app.models.truly_missing_models import Solution

            decision_value = data.get("decision")
            linked_solutions = Solution.query.filter_by(arb_review_item_id=id).all()
            for sol in linked_solutions:
                if decision_value == "approved":
                    sol.governance_status = "approved"
                    sol.arb_approval_date = datetime.utcnow()
                elif decision_value == "rejected":
                    sol.governance_status = "rejected"
                    sol.arb_rejection_reason = data.get("rationale", "")
                elif decision_value == "deferred":
                    sol.governance_status = "proposed"
                elif decision_value == "approved_with_conditions":
                    sol.governance_status = "approved"
                    sol.arb_approval_date = datetime.utcnow()
            if linked_solutions:
                db.session.commit()
                current_app.logger.info(
                    f"Synced ARB decision '{decision_value}' to {len(linked_solutions)} solution(s)"
                )
        except Exception as sol_sync_error:
            current_app.logger.warning(
                f"Failed to sync ARB decision to solutions: {sol_sync_error}"
            )

        flash(f"Decision recorded for review item {review.review_number}", "success")
        return redirect(url_for("arb.review_detail", id=id))

    except Exception as e:
        current_app.logger.error(f"Error recording decision: {e}")
        flash("Error recording decision. Please try again.", "error")
        return redirect(url_for("arb.review_detail", id=id))


@arb_bp.route("/reviews/<int:id>/reopen", methods=["POST"])
@login_required
@audit_log("arb_decision_reopen")
def reopen_decision(id):
    """Reopen a previously recorded ARB decision.

    Allows the original decision maker or an admin to revert a decision
    back to 'under_review' status. Creates an audit log entry recording
    who reopened the decision and why.
    """
    try:
        from app.models.architecture_review_board import ARBAuditAction, ARBAuditLog

        review = db.session.get(ARBReviewItem, id)
        if not review:
            flash("Review item not found.", "error")
            return redirect(url_for("arb.reviews"))

        # Only allow reopen if a decision has been recorded
        if not review.decision:
            flash("No decision has been recorded for this review item.", "warning")
            return redirect(url_for("arb.review_detail", id=id))

        # Authorization: only the original decision maker or admin can reopen
        is_decision_maker = review.decided_by_id == current_user.id
        is_admin = (
            getattr(current_user, "is_admin", False)
            or getattr(current_user, "role", "") == "admin"
        )

        if not is_decision_maker and not is_admin:
            flash(
                "Only the original decision maker or an admin can reopen a decision.",
                "error",
            )
            return redirect(url_for("arb.review_detail", id=id))

        reason = request.form.get("reopen_reason", "").strip()
        if not reason:
            flash("A reason for reopening the decision is required.", "warning")
            return redirect(url_for("arb.review_detail", id=id))

        # Capture previous state for audit trail
        previous_decision = review.decision
        previous_status = review.status
        previous_rationale = review.decision_rationale

        # Revert the review item to under_review status
        review.status = "under_review"
        review.decision = None
        review.decision_rationale = None
        review.decision_date = None
        review.decided_by_id = None
        review.conditions = None
        review.review_completed_at = None

        # Create audit log entry
        audit_entry = ARBAuditLog(
            entity_type="ARBReviewItem",
            entity_id=review.id,
            entity_reference=review.review_number,
            action=ARBAuditAction.DECISION_REOPEN.value,
            action_description=(
                f"Decision reopened by {current_user.email}. "
                f"Previous decision: {previous_decision} "
                f"(status: {previous_status}). Reason: {reason}"
            ),
            old_value={
                "decision": previous_decision,
                "status": previous_status,
                "rationale": previous_rationale,
            },
            new_value={
                "decision": None,
                "status": "under_review",
                "reopen_reason": reason,
            },
            changed_fields=[
                "decision",
                "status",
                "decision_rationale",
                "decision_date",
                "decided_by_id",
            ],
            user_id=current_user.id,
            user_email=getattr(current_user, "email", None),
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")[:500],
        )
        db.session.add(audit_entry)

        db.session.commit()
        flash(
            f"Decision for {review.review_number} has been reopened. "
            f"Previous decision ({previous_decision}) has been reverted.",
            "success",
        )
        return redirect(url_for("arb.review_detail", id=id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error reopening decision for review {id}: {e}")
        flash("Error reopening decision. Please try again.", "error")
        return redirect(url_for("arb.review_detail", id=id))


@arb_bp.route("/reviews/<int:id>/comment", methods=["POST"])
@login_required
@audit_log("arb_comment_add")
def add_comment(id):
    """Add comment to review item."""
    try:
        data = request.form.to_dict()

        comment = ARBReviewComment(
            review_item_id=id,
            user_id=current_user.id,
            comment_type=data.get("comment_type", "general"),
            content=data.get("content"),
        )

        db.session.add(comment)
        db.session.commit()

        flash("Comment added successfully", "success")

    except Exception as e:
        current_app.logger.error(f"Error adding comment: {e}")
        flash("Error adding comment. Please try again.", "error")

    return redirect(url_for("arb.review_detail", id=id))


# =========================================================================
# GOVERNANCE STANDARDS ROUTES
# =========================================================================


@arb_bp.route("/standards")
@login_required
def standards():
    """List governance standards."""
    category = request.args.get("category", "all")

    standards = arb_service.get_governance_standards(category)

    return render_template("arb/standards.html", standards=standards, category=category)


@arb_bp.route("/standards/<int:id>")
@login_required
def standard_detail(id):
    """View governance standard details."""
    standard = ARBGovernanceStandard.query.get_or_404(id)
    return render_template("arb/standard_detail.html", standard=standard)


@arb_bp.route("/decisions")
@login_required
def decision_register_page():
    """ARBU-001: Capability-based decision register page."""
    from app.models.architecture_decision import (
        ArchitectureDecision,
        VALID_HORIZONS, VALID_AUTHORITY_LEVELS,
        VALID_STATUSES, VALID_DECISION_TYPES
    )
    try:
        decisions = ArchitectureDecision.query.order_by(
            ArchitectureDecision.created_at.desc()
        ).limit(200).all()
    except Exception:
        decisions = []
    return render_template(
        'arb/decisions.html',
        decisions=decisions,
        valid_horizons=VALID_HORIZONS,
        valid_authority_levels=VALID_AUTHORITY_LEVELS,
        valid_statuses=VALID_STATUSES,
        valid_decision_types=VALID_DECISION_TYPES,
    )


@arb_bp.route("/change-requests")
@login_required
def change_request_list():
    """List Phase H change requests (wires arb/change_requests.html)."""
    from app.models.architecture_decision import ArchitectureChangeRequest
    change_requests = ArchitectureChangeRequest.query.order_by(
        ArchitectureChangeRequest.raised_at.desc()
    ).all()
    return render_template("arb/change_requests.html", change_requests=change_requests)


@arb_bp.route("/change-requests/<int:cr_id>")
@login_required
def change_request_detail(cr_id):
    """Detail view for a single change request (wires arb/change_request_detail.html)."""
    from app.models.architecture_decision import ArchitectureChangeRequest
    change_request = ArchitectureChangeRequest.query.get_or_404(cr_id)
    return render_template("arb/change_request_detail.html", change_request=change_request)


@arb_bp.route("/change-requests/new", methods=["GET", "POST"])
@login_required
def change_request_new():
    """New change request form (wires arb/change_request_form.html)."""
    from app.models.architecture_decision import (
        ArchitectureChangeRequest,
        VALID_TRIGGER_TYPES,
    )
    if request.method == "POST":
        data = request.form or request.get_json(silent=True) or {}
        title = data.get("title") or ""
        description = data.get("description") or ""
        trigger_type = data.get("trigger_type") or "reactive"
        if trigger_type not in VALID_TRIGGER_TYPES:
            trigger_type = "reactive"
        cr = ArchitectureChangeRequest(
            acr_reference=ArchitectureChangeRequest.next_acr_reference(),
            title=title,
            description=description,
            trigger_type=trigger_type,
            status="open",
        )
        db.session.add(cr)
        db.session.commit()
        return redirect(url_for("arb.change_request_detail", cr_id=cr.id))
    return render_template(
        "arb/change_request_form.html",
        change_request=None,
        valid_trigger_types=VALID_TRIGGER_TYPES,
    )


@arb_bp.route("/capabilities/<int:capability_id>/governance")
@login_required
def capability_governance_page(capability_id):
    """Governance panel page for a capability (wires arb/capability_governance.html)."""
    from app.models.unified_capability import UnifiedCapability
    cap = UnifiedCapability.query.get_or_404(capability_id)
    return render_template(
        "arb/capability_governance.html",
        capability_id=capability_id,
        capability_name=cap.name or "Capability",
        capability_description=getattr(cap, "description", None) or "",
    )


# =========================================================================
# API ENDPOINTS
# =========================================================================


@arb_bp.route("/api/reviews/<int:id>/assess")
@login_required
def api_assess_review(id):
    """API endpoint to assess review item scores."""
    try:
        compliance_score = arb_service.assess_compliance(id)
        risk_score = arb_service.assess_risk(id)
        quality_score = arb_service.assess_quality(id)
        overall_score = arb_service.calculate_overall_score(id)

        return jsonify(
            {
                "success": True,
                "compliance_score": compliance_score,
                "risk_score": risk_score,
                "quality_score": quality_score,
                "overall_score": overall_score,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error assessing review: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/reviews/<int:id>/checklist", methods=["POST"])
@login_required
@audit_log("arb_checklist_update")
def api_update_checklist(id):
    """API endpoint to update governance checklist."""
    try:
        data = request.get_json()
        checklist_items = data.get("checklist", {})

        review = db.session.get(ARBReviewItem, id)
        if not review:
            return jsonify({"success": False, "error": "Review not found"}), 404

        # Update checklist
        if not review.governance_checklist:
            review.governance_checklist = {}

        review.governance_checklist.update(checklist_items)
        db.session.commit()

        # Recalculate scores
        compliance_score = arb_service.assess_compliance(id)
        overall_score = arb_service.calculate_overall_score(id)

        return jsonify(
            {
                "success": True,
                "compliance_score": compliance_score,
                "overall_score": overall_score,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error updating checklist: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/capability/<int:capability_id>/reviews")
@login_required
def api_capability_reviews(capability_id):
    """API endpoint to get reviews affecting a capability."""
    try:
        reviews = arb_service.get_pending_reviews_by_capability(capability_id)
        return jsonify(
            {
                "success": True,
                "reviews": [
                    review.to_dict(include_details=False) for review in reviews
                ],
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error getting capability reviews: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/dashboard")
@login_required
def api_dashboard():
    """API endpoint for dashboard data."""
    try:
        dashboard_data = arb_service.get_governance_dashboard()
        return jsonify({"success": True, "data": dashboard_data})
    except Exception as e:
        current_app.logger.error(f"Error getting dashboard data: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/solution/<int:solution_id>/submit_review", methods=["POST"])
@login_required
@audit_log("arb_solution_review_submit")
def api_submit_solution_review(solution_id):
    """API endpoint to auto-submit solution for ARB review."""
    try:
        review = arb_service.auto_submit_solution_for_review(
            solution_id, current_user.id
        )
        if review:
            return jsonify(
                {
                    "success": True,
                    "review_id": review.id,
                    "review_number": review.review_number,
                }
            )
        else:
            return jsonify(
                {
                    "success": False,
                    "error": "Solution does not meet criteria for ARB review",
                }
            )
    except Exception as e:
        current_app.logger.error(f"Error submitting solution review: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/adr/<int:adr_id>/submit_review", methods=["POST"])
@login_required
@audit_log("arb_adr_review_submit")
def api_submit_adr_review(adr_id):
    """API endpoint to auto-submit ADR for ARB review."""
    try:
        review = arb_service.auto_submit_adr_for_review(adr_id, current_user.id)
        if review:
            return jsonify(
                {
                    "success": True,
                    "review_id": review.id,
                    "review_number": review.review_number,
                }
            )
        else:
            return jsonify(
                {"success": False, "error": "ADR does not require ARB review"}
            )
    except Exception as e:
        current_app.logger.error(f"Error submitting ADR review: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# =========================================================================
# JSON API FOR MODAL FORM
# =========================================================================


@arb_bp.route("/api/reviews", methods=["GET"])
@login_required
def api_list_reviews():
    """API endpoint to list review items with optional filtering."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 20, type=int), 100)
        status = request.args.get("status")
        review_type = request.args.get("review_type")

        query = ARBReviewItem.query

        if status and status != "all":
            query = query.filter_by(status=status)
        if review_type and review_type != "all":
            query = query.filter_by(review_type=review_type)

        pagination = query.order_by(ARBReviewItem.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify(
            {
                "success": True,
                "reviews": [r.to_dict() for r in pagination.items],
                "total": pagination.total,
                "page": page,
                "per_page": per_page,
                "pages": pagination.pages,
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error listing reviews via API: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/reviews", methods=["POST"])
@login_required
@audit_log("arb_review_create_api")
def api_create_review():
    """API endpoint to create a review via modal form."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        decision_sought_val = (data.get("decision_sought") or "").strip()
        if not decision_sought_val:
            return jsonify({
                "success": False,
                "errors": {"decision_sought": "Decision sought is required."},
            }), 400

        review_type = data.get("review_type")
        capability_required_types = ["solution_design", "capability_implementation", "technology_selection"]

        # Parse capability_impacts or fallback to capability_ids
        capability_impacts = []
        raw_impacts = data.get("capability_impacts")
        if raw_impacts and isinstance(raw_impacts, list):
            for imp in raw_impacts:
                cap_id = imp.get("capability_id") if isinstance(imp, dict) else imp
                if cap_id:
                    raw_impact = imp.get("impact_type", "modifies") if isinstance(imp, dict) else "modifies"
                    capability_impacts.append({
                        "capability_id": int(cap_id),
                        "impact_type": _normalize_impact_type(raw_impact),
                        "impact_level": imp.get("impact_level", "medium") if isinstance(imp, dict) else "medium",
                        "level": imp.get("level") if isinstance(imp, dict) else None,
                    })
        if not capability_impacts and data.get("capability_ids"):
            raw = data.get("capability_ids")
            ids = [int(i) for i in raw] if isinstance(raw, list) else [int(i.strip()) for i in str(raw).split(",") if str(i).strip()]
            default_impact = _normalize_impact_type(data.get("capability_impact_type") or "modifies")
            for cap_id in ids:
                capability_impacts.append({"capability_id": cap_id, "impact_type": default_impact, "impact_level": "medium"})

        if review_type in capability_required_types and not capability_impacts:
            return jsonify({
                "success": False,
                "errors": {"capability_ids": f"At least one capability is required for {review_type.replace('_', ' ')} reviews."},
            }), 400

        application_ids = []
        if data.get("application_ids"):
            raw = data.get("application_ids")
            application_ids = [int(i) for i in raw] if isinstance(raw, list) else [int(i.strip()) for i in str(raw).split(",") if str(i).strip()]

        review_item = arb_service.submit_for_review(
            title=data.get("title"),
            description=data.get("description"),
            review_type=review_type,
            submitter_id=current_user.id,
            togaf_phase=data.get("togaf_phase") or None,
            archimate_layer=data.get("archimate_layer") or None,
            solution_id=int(data.get("solution_id")) if data.get("solution_id") else None,
            adr_id=int(data.get("adr_id")) if data.get("adr_id") else None,
            architecture_model_id=int(data.get("architecture_model_id")) if data.get("architecture_model_id") else None,
            priority=data.get("priority", "medium"),
            business_impact=data.get("business_impact", "medium"),
            estimated_effort=data.get("estimated_effort", "medium"),
            capability_ids=None,
            decision_sought=decision_sought_val or None,
            alternatives_considered=data.get("alternatives_considered") or None,
            application_ids=application_ids or None,
            capability_impacts=capability_impacts if capability_impacts else None,
        )

        return jsonify(
            {
                "success": True,
                "review_id": review_item.id,
                "review_number": review_item.review_number,
                "redirect_url": url_for("arb.review_detail", id=review_item.id),
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error creating review via API: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# Decision types the ARB can be asked to approve (capability-based governance)
ARB_DECISION_TYPES = [
    {"value": "approve_vendor_selection", "label": "Approve Vendor/Product Selection"},
    {"value": "approve_new_application", "label": "Approve New Application/Capability"},
    {"value": "approve_enhancement", "label": "Approve Enhancement/Investment"},
    {"value": "approve_retirement", "label": "Approve Retirement/Consolidation"},
    {"value": "approve_exception", "label": "Approve Exception to Standard"},
    {"value": "approve_migration", "label": "Approve Migration Plan"},
    {"value": "approve_integration_pattern", "label": "Approve Integration Pattern"},
    {"value": "other", "label": "Other (describe in justification)"},
]

# Allowed impact_type values (validate and default to modifies if invalid)
ARB_IMPACT_TYPE_VALUES = {"enhances", "replaces", "deprecates", "new_implementation", "modifies"}


def _normalize_impact_type(val):
    """Return val if valid, else 'modifies'."""
    return val if val in ARB_IMPACT_TYPE_VALUES else "modifies"


# Capability impact types (ARBCapabilityImpact.impact_type)
ARB_IMPACT_TYPES = [
    {"value": "enhances", "label": "Enhances"},
    {"value": "replaces", "label": "Replaces"},
    {"value": "deprecates", "label": "Deprecates"},
    {"value": "new_implementation", "label": "New Implementation"},
    {"value": "modifies", "label": "Modifies"},
]


@arb_bp.route("/api/form-data")
@login_required
def api_form_data():
    """API endpoint to get form data for create review modal."""
    try:
        from app.models.adr import ArchitectureDecisionRecord
        from app.models.application_portfolio import ApplicationComponent
        from app.models.models import ArchitectureModel
        from app.models.truly_missing_models import Solution
        from app.models.unified_capability import UnifiedCapability

        solutions = Solution.query.order_by(Solution.name).limit(200).all()
        adrs = (
            ArchitectureDecisionRecord.query.order_by(
                ArchitectureDecisionRecord.created_at.desc()
            )
            .limit(50)
            .all()
        )
        architecture_models = (
            ArchitectureModel.query.order_by(ArchitectureModel.name).limit(200).all()
        )
        capabilities = (
            UnifiedCapability.query.order_by(UnifiedCapability.name).limit(500).all()
        )
        applications = (
            ApplicationComponent.query.order_by(ApplicationComponent.name)
            .limit(300)
            .all()
        )

        return jsonify(
            {
                "success": True,
                "solutions": [{"id": s.id, "name": s.name} for s in solutions],
                "adrs": [
                    {"id": a.id, "adr_number": a.adr_number, "title": a.title}
                    for a in adrs
                ],
                "architecture_models": [
                    {"id": m.id, "name": m.name} for m in architecture_models
                ],
                "capabilities": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "level": getattr(c, "level", None),
                        "specialization_type": getattr(c, "specialization_type", None),
                    }
                    for c in capabilities
                ],
                "applications": [
                    {"id": a.id, "name": a.name} for a in applications
                ],
                "review_types": [
                    {"value": t.value, "label": t.value.replace("_", " ").title()}
                    for t in ReviewType
                ],
                "togaf_phases": [
                    {"value": p.value, "label": p.value.replace("_", " ").title()}
                    for p in TOGAFPhase
                ],
                "decision_types": ARB_DECISION_TYPES,
                "impact_types": ARB_IMPACT_TYPES,
                "capability_required_review_types": [
                    "solution_design",
                    "capability_implementation",
                    "technology_selection",
                ],
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error getting form data: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# =========================================================================
# ANALYTICS API
# =========================================================================


@arb_bp.route("/api/decision-analytics")
@login_required
def api_decision_analytics():
    """API endpoint for comprehensive decision analytics data."""
    try:
        period = request.args.get("period", 90, type=int)
        report = arb_analytics.generate_comprehensive_report(period)
        return jsonify({"success": True, "data": report})
    except Exception as e:
        current_app.logger.error(f"Error getting decision analytics: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# =========================================================================
# ADM KANBAN API
# =========================================================================


@arb_bp.route("/api/adm-kanban")
@login_required
def api_adm_kanban():
    """API endpoint returning review items grouped by TOGAF ADM phase for Kanban board."""
    try:
        # Define ADM phases in order
        adm_phases = [
            {
                "code": "preliminary",
                "name": "Preliminary",
                "short": "Prelim",
                "order": 0,
            },
            {
                "code": "phase_a_vision",
                "name": "Phase A: Architecture Vision",
                "short": "A",
                "order": 1,
            },
            {
                "code": "phase_b_business",
                "name": "Phase B: Business Architecture",
                "short": "B",
                "order": 2,
            },
            {
                "code": "phase_c_information_systems",
                "name": "Phase C: Information Systems",
                "short": "C",
                "order": 3,
            },
            {
                "code": "phase_d_technology",
                "name": "Phase D: Technology Architecture",
                "short": "D",
                "order": 4,
            },
            {
                "code": "phase_e_opportunities",
                "name": "Phase E: Opportunities & Solutions",
                "short": "E",
                "order": 5,
            },
            {
                "code": "phase_f_migration",
                "name": "Phase F: Migration Planning",
                "short": "F",
                "order": 6,
            },
            {
                "code": "phase_g_implementation",
                "name": "Phase G: Implementation Governance",
                "short": "G",
                "order": 7,
            },
            {
                "code": "phase_h_change_management",
                "name": "Phase H: Change Management",
                "short": "H",
                "order": 8,
            },
            {
                "code": "requirements_management",
                "name": "Requirements Management",
                "short": "REQ",
                "order": 9,
            },
        ]

        # Build columns with review items
        columns = []
        for phase in adm_phases:
            items = (
                ARBReviewItem.query.filter_by(togaf_phase=phase["code"])
                .order_by(
                    db.case(
                        (ARBReviewItem.priority == "critical", 0),
                        (ARBReviewItem.priority == "high", 1),
                        (ARBReviewItem.priority == "medium", 2),
                        (ARBReviewItem.priority == "low", 3),
                        else_=4,
                    ),
                    ARBReviewItem.created_at.desc(),
                )
                .all()
            )

            total = len(items)
            completed = sum(
                1 for i in items if i.status in ("approved", "approved_with_conditions")
            )
            in_review = sum(1 for i in items if i.status == "under_review")

            cards = []
            for item in items:
                cards.append(
                    {
                        "id": item.id,
                        "review_number": item.review_number,
                        "title": item.title,
                        "status": item.status,
                        "priority": item.priority,
                        "review_type": item.review_type,
                        "submitter": (
                            f"{item.submitter.first_name} {item.submitter.last_name}"
                            if item.submitter
                            else "Unknown"
                        ),
                        "created_at": item.created_at.isoformat()
                        if item.created_at
                        else None,
                        "overall_score": item.overall_score,
                    }
                )

            columns.append(
                {
                    "phase_code": phase["code"],
                    "phase_name": phase["name"],
                    "phase_short": phase["short"],
                    "order": phase["order"],
                    "total": total,
                    "completed": completed,
                    "in_review": in_review,
                    "cards": cards,
                }
            )

        # Summary stats
        total_items = sum(c["total"] for c in columns)
        total_completed = sum(c["completed"] for c in columns)
        phases_with_items = sum(1 for c in columns if c["total"] > 0)

        return jsonify(
            {
                "success": True,
                "columns": columns,
                "summary": {
                    "total_items": total_items,
                    "total_completed": total_completed,
                    "phases_with_items": phases_with_items,
                    "completion_rate": round(total_completed / total_items * 100, 1)
                    if total_items > 0
                    else 0,
                },
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error loading ADM Kanban data: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/adm-kanban/move-card", methods=["POST"])
@login_required
@audit_log("adm_kanban_move_card")
def api_adm_kanban_move_card():
    """API endpoint to move a review item to a different TOGAF ADM phase (drag-and-drop)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        review_id = data.get("review_id")
        target_phase = data.get("target_phase")

        if not review_id or not target_phase:
            return jsonify(
                {"success": False, "error": "Missing review_id or target_phase"}
            ), 400

        # Validate phase code
        valid_phases = {p.value for p in TOGAFPhase}
        if target_phase not in valid_phases:
            return jsonify(
                {"success": False, "error": f"Invalid phase: {target_phase}"}
            ), 400

        review = db.session.get(ARBReviewItem, review_id)
        if not review:
            return jsonify({"success": False, "error": "Review item not found"}), 404

        old_phase = review.togaf_phase
        review.togaf_phase = target_phase
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "review_id": review.id,
                "old_phase": old_phase,
                "new_phase": target_phase,
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error moving Kanban card: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# =========================================================================
# DELETE ROUTES
# =========================================================================


@arb_bp.route("/sessions/<int:id>/delete", methods=["POST"])
@login_required
@audit_log("arb_session_delete")
def delete_session(id):
    """Delete an ARB session. Only draft/cancelled sessions can be deleted."""
    try:
        session = ArchitectureReviewBoard.query.get_or_404(id)

        # Only allow deletion of draft or cancelled sessions
        if session.status not in ("draft", "cancelled"):
            flash(
                "Only draft or cancelled sessions can be deleted. "
                "Complete or cancel the session first.",
                "error",
            )
            return redirect(url_for("arb.session_detail", id=id))

        # Check if session has review items assigned
        review_count = ARBReviewItem.query.filter_by(arb_session_id=id).count()
        if review_count > 0:
            flash(
                f"Cannot delete session with {review_count} review item(s) assigned. "
                "Remove review items first.",
                "error",
            )
            return redirect(url_for("arb.session_detail", id=id))

        # Remove board members first (cascade may not cover all cases)
        ARBBoardMember.query.filter_by(arb_session_id=id).delete()

        board_number = session.board_number
        db.session.delete(session)
        db.session.commit()

        current_app.logger.info(
            f"ARB session {board_number} (id={id}) deleted by user {current_user.id}"
        )
        flash(f"ARB session {board_number} deleted successfully", "success")
        return redirect(url_for("arb.sessions"))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting ARB session {id}: {e}")
        flash("Error deleting session. Please try again.", "error")
        return redirect(url_for("arb.session_detail", id=id))


@arb_bp.route("/reviews/<int:id>/delete", methods=["POST"])
@login_required
@audit_log("arb_review_delete")
def delete_review(id):
    """Delete an ARB review item. Only draft/withdrawn items can be deleted."""
    try:
        review = ARBReviewItem.query.get_or_404(id)

        # Only allow deletion of draft or withdrawn reviews
        if review.status not in ("draft", "withdrawn"):
            flash(
                "Only draft or withdrawn review items can be deleted. "
                "Withdraw the review first.",
                "error",
            )
            return redirect(url_for("arb.review_detail", id=id))

        # Only submitter can delete their own review
        if review.submitter_id != current_user.id:
            flash("Only the original submitter can delete a review item.", "error")
            return redirect(url_for("arb.review_detail", id=id))

        # Remove related records
        ARBCapabilityImpact.query.filter_by(review_item_id=id).delete()
        ARBReviewComment.query.filter_by(review_item_id=id).delete()

        review_number = review.review_number
        db.session.delete(review)
        db.session.commit()

        current_app.logger.info(
            f"ARB review {review_number} (id={id}) deleted by user {current_user.id}"
        )
        flash(f"Review item {review_number} deleted successfully", "success")
        return redirect(url_for("arb.reviews"))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting ARB review {id}: {e}")
        flash("Error deleting review. Please try again.", "error")
        return redirect(url_for("arb.review_detail", id=id))


# =========================================================================
# UTILITY ROUTES
# =========================================================================

# Import decision CRUD/register routes — adds them to arb_bp before registration (side-effect import)
from app.modules.architecture.routes import arb_decision_routes  # noqa: F401  # dead-code-ok
# Import document attachment routes — adds upload/download endpoints to arb_bp (side-effect import)
from app.modules.architecture.routes import arb_document_routes  # noqa: F401  # dead-code-ok
import logging
logger = logging.getLogger(__name__)


@arb_bp.route("/initialize_standards")
@login_required
def initialize_standards():
    """Initialize default governance standards."""
    try:
        arb_service.initialize_governance_standards()
        flash("Governance standards initialized successfully", "success")
    except Exception as e:
        current_app.logger.error(f"Error initializing standards: {e}")
        flash("Error initializing standards. Please try again.", "error")

    return redirect(url_for("arb.standards"))


# =========================================================================
# ENH-020: ARB Review Item API Lifecycle Endpoints
# POST /api/arb/<id>/review  - move to under_review
# POST /api/arb/<id>/approve - approve review item
# POST /api/arb/<id>/reject  - reject review item
# =========================================================================


@arb_bp.route("/api/arb/<int:item_id>/review", methods=["POST"])
@login_required
def api_arb_begin_review(item_id: int):
    """ENH-020: Transition ARBReviewItem to under_review status."""
    item = ARBReviewItem.query.get_or_404(item_id)
    current_status = item.status or "draft"
    if current_status not in ("submitted", "draft", "pending"):
        return jsonify({
            "success": False,
            "error": f"Cannot begin review from status '{current_status}'.",
        }), 409

    data = request.get_json() or {}
    try:
        item.status = "under_review"
        item.reviewer_id = current_user.id
        item.review_started_at = datetime.utcnow()
        db.session.commit()
        return jsonify({
            "success": True,
            "item_id": item.id,
            "status": item.status,
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("ENH-020: Error beginning ARB review %s: %s", item_id, exc)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/arb/<int:item_id>/approve", methods=["POST"])
@login_required
def api_arb_approve(item_id: int):
    """ENH-020: Approve an ARBReviewItem that is under_review."""
    item = ARBReviewItem.query.get_or_404(item_id)
    current_status = item.status or "draft"
    if current_status != "under_review":
        return jsonify({
            "success": False,
            "error": f"Cannot approve from status '{current_status}'. Item must be under_review.",
        }), 409

    data = request.get_json() or {}
    conditions = data.get("conditions")
    try:
        if conditions:
            item.status = "approved_with_conditions"
        else:
            item.status = "approved"
        item.decision_date = datetime.utcnow()
        item.decision_notes = data.get("notes", "")
        item.decided_by_id = current_user.id

        # Propagate approval to the linked solution
        if item.solution_id:
            from app.models.solution_models import Solution
            solution = Solution.query.get(item.solution_id)
            if solution:
                solution.governance_status = "approved"
                solution.arb_approval_date = datetime.utcnow()

        db.session.commit()
        return jsonify({
            "success": True,
            "item_id": item.id,
            "status": item.status,
            "conditions": conditions,
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("ENH-020: Error approving ARB item %s: %s", item_id, exc)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/arb/<int:item_id>/reject", methods=["POST"])
@login_required
def api_arb_reject(item_id: int):
    """ENH-020: Reject an ARBReviewItem that is under_review."""
    item = ARBReviewItem.query.get_or_404(item_id)
    current_status = item.status or "draft"
    if current_status != "under_review":
        return jsonify({
            "success": False,
            "error": f"Cannot reject from status '{current_status}'. Item must be under_review.",
        }), 409

    data = request.get_json() or {}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"success": False, "error": "reason is required to reject"}), 400

    try:
        item.status = "rejected"
        item.rejection_reason = reason
        item.decision_date = datetime.utcnow()
        item.decided_by_id = current_user.id

        # Propagate rejection to the linked solution
        if item.solution_id:
            from app.models.solution_models import Solution
            solution = Solution.query.get(item.solution_id)
            if solution:
                solution.governance_status = "rejected"
                solution.arb_rejection_reason = reason

        db.session.commit()
        return jsonify({
            "success": True,
            "item_id": item.id,
            "status": item.status,
            "rejection_reason": reason,
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("ENH-020: Error rejecting ARB item %s: %s", item_id, exc)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/arb/<int:item_id>/request-changes", methods=["POST"])
@login_required
def api_arb_request_changes(item_id: int):
    """ENH-020: Request changes on an ARBReviewItem under review.

    Sets status to approved_with_conditions and records conditions.

    Request Body:
        { "conditions": ["Fix security issue", ...], "notes": "Optional notes" }
    """
    item = ARBReviewItem.query.get_or_404(item_id)
    current_status = item.status or "draft"
    if current_status != "under_review":
        return jsonify({
            "success": False,
            "error": f"Cannot request changes from status '{current_status}'. "
                     "Item must be under_review.",
        }), 409

    data = request.get_json() or {}
    conditions = data.get("conditions")
    if not conditions or not isinstance(conditions, list) or len(conditions) == 0:
        return jsonify({"success": False, "error": "At least one condition is required"}), 400

    try:
        item.status = "approved_with_conditions"
        item.decision = "approved_with_conditions"
        item.conditions = [
            {"condition": c, "status": "pending", "due_date": None}
            for c in conditions
            if isinstance(c, str) and c.strip()
        ]
        item.decision_rationale = data.get("notes", "")
        item.decision_date = datetime.utcnow()
        item.decided_by_id = current_user.id
        db.session.commit()
        return jsonify({
            "success": True,
            "item_id": item.id,
            "status": item.status,
            "conditions": item.conditions,
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            "ENH-020: Error requesting changes for ARB item %s: %s", item_id, exc
        )
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@arb_bp.route("/api/arb/<int:item_id>/implementation-status", methods=["GET"])
@login_required
def api_arb_get_implementation_status(item_id: int):
    """ENH-020: Get implementation status for an approved ARB review item."""
    item = ARBReviewItem.query.get_or_404(item_id)
    return jsonify({
        "success": True,
        "item_id": item.id,
        "review_number": item.review_number,
        "status": item.status,
        "implementation_status": item.implementation_status or "not_started",
        "implementation_notes": item.implementation_notes,
        "implementation_started_at": item.implementation_started_at.isoformat()
        if item.implementation_started_at
        else None,
        "implementation_completed_at": item.implementation_completed_at.isoformat()
        if item.implementation_completed_at
        else None,
        "conditions": item.conditions,
        "conditions_response": item.conditions_response,
    })


@arb_bp.route("/api/arb/<int:item_id>/implementation-status", methods=["PATCH"])
@login_required
def api_arb_update_implementation_status(item_id: int):
    """ENH-020: Update implementation status for an approved ARB review item.

    Request Body:
        {
            "implementation_status": "in_progress|completed|blocked|deferred",
            "implementation_notes": "Optional notes",
            "conditions_response": {"0": "Evidence for condition 0", ...}
        }
    """
    item = ARBReviewItem.query.get_or_404(item_id)
    if item.status not in ("approved", "approved_with_conditions"):
        return jsonify({
            "success": False,
            "error": f"Cannot update implementation for status '{item.status}'. "
                     "Item must be approved.",
        }), 409

    data = request.get_json() or {}
    valid_impl_statuses = {
        "not_started", "in_progress", "completed", "blocked", "deferred",
    }
    new_status = data.get("implementation_status")
    if new_status and new_status not in valid_impl_statuses:
        return jsonify({
            "success": False,
            "error": "Invalid implementation_status. Must be one of: "
                     + ", ".join(sorted(valid_impl_statuses)),
        }), 400

    try:
        if new_status:
            item.implementation_status = new_status
            if new_status == "in_progress" and not item.implementation_started_at:
                item.implementation_started_at = datetime.utcnow()
            elif new_status == "completed":
                item.implementation_completed_at = datetime.utcnow()
        if "implementation_notes" in data:
            item.implementation_notes = data["implementation_notes"]
        if "conditions_response" in data:
            item.conditions_response = data["conditions_response"]
        db.session.commit()
        return jsonify({
            "success": True,
            "item_id": item.id,
            "implementation_status": item.implementation_status,
            "implementation_notes": item.implementation_notes,
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            "ENH-020: Error updating implementation status for ARB item %s: %s",
            item_id, exc,
        )
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# ===================================================================
# FRAG-037: ARB exception management routes
# ===================================================================

@arb_bp.route("/api/exceptions")
@login_required
def api_list_exceptions():
    """FRAG-037: List ARB exceptions."""
    try:
        from app.services.arb_exception_service import ARBExceptionService
        service = ARBExceptionService()
        exceptions = service.list_exceptions()
        return jsonify({"success": True, "exceptions": exceptions})
    except Exception as e:
        current_app.logger.error(f"List exceptions error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@arb_bp.route("/api/exceptions", methods=["POST"])
@login_required
def api_create_exception():
    """FRAG-037: Create ARB exception request."""
    try:
        from app.services.arb_exception_service import ARBExceptionService
        service = ARBExceptionService()
        data = request.get_json()
        result = service.create_exception_request(**data)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Create exception error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@arb_bp.route("/api/exceptions/<int:exception_id>/approve", methods=["PUT"])
@login_required
def api_approve_exception(exception_id):
    """FRAG-037: Approve ARB exception."""
    try:
        from app.services.arb_exception_service import ARBExceptionService
        service = ARBExceptionService()
        data = request.get_json() or {}
        result = service.approve_exception(exception_id, **data)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Approve exception error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
