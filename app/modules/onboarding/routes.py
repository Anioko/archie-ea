"""The five-screen onboarding flow.

Screen 1 Welcome -> Screen 2 Bring your company (P0, the only mandatory step)
-> Screen 3 First question -> Screen 4 Fill the gaps -> Screen 5 Your twin.

Replaces the old PLT-040 first-login modal (app/templates/layouts/admin_base.html)
as the onboarding UX, and calls the same completion endpoint
(dashboard.api_onboarding_complete) it did, so onboarding_completed_at stays the
one place "has this user finished onboarding" is recorded.

The website field on screen 2 is a real, honest stub: it saves the address and
answers, and says reading is not available yet -- the company-context reading
engine (the fetcher, the LLM clients, the run record) is a separate, not-yet-
landed piece of work. Nothing here fabricates a reading result.
"""
from __future__ import annotations

import datetime

from flask import Blueprint, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models.organization import Organization
from app.utils.api_response import success_response

from .services import capabilities as capability_capture
from .services import goals_changes
from .services import people as people_capture
from .services import profile, stage_gaps

onboarding_bp = Blueprint("onboarding", __name__, template_folder="templates")

_STAGES = ("pre_revenue", "early_revenue", "growing", "established")
_SIZE_BANDS = tuple(b["key"] for b in capability_capture.size_bands())
_STAGE_LABELS = {
    "pre_revenue": "Pre-revenue",
    "early_revenue": "Early revenue",
    "growing": "Growing",
    "established": "Established",
}


def _current_org() -> Organization:
    org_id = getattr(g, "current_org_id", None) or getattr(current_user, "organization_id", None)
    return db.session.get(Organization, int(org_id))


@onboarding_bp.route("/")
@login_required
def index():
    """Entry point: route each onboarding-time persona to the right screen.

    Someone who has already finished only lands here by choice (the All modules
    directory lists "Getting started"), so show their saved company answers,
    editable, instead of bouncing them to the dashboard."""
    if current_user.onboarding_completed_at:
        return company()

    org = _current_org()
    org_profile = profile.read(org)
    if org_profile.get("stage"):
        # The org's own P0 already exists (someone else completed it) -- an
        # invited team member enters at Screen 3, per onboarding-prd-v1 S3.
        return redirect(url_for("onboarding.capabilities"))
    return redirect(url_for("onboarding.welcome"))


@onboarding_bp.route("/welcome")
@login_required
def welcome():
    if current_user.onboarding_completed_at:
        return redirect(url_for("dashboard.overview"))
    return render_template("onboarding/screen1_welcome.html")


@onboarding_bp.route("/company", methods=["GET", "POST"])
@login_required
def company():
    org = _current_org()
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        stage = data.get("stage")
        if stage not in _STAGES:
            return jsonify({"success": False, "error": "invalid_stage"}), 400
        profile.write(
            org,
            stage=stage,
            company_size=(data.get("company_size") or "").strip()[:100] or None,
            size_band=data.get("size_band") if data.get("size_band") in _SIZE_BANDS else None,
            industry=(data.get("industry") or "").strip()[:200] or None,
            source_url=(data.get("source_url") or "").strip()[:500] or None,
            region_europe_or_eu_customers=bool(data.get("region_europe_or_eu_customers")),
            handles_card_data_directly=bool(data.get("handles_card_data_directly")),
        )
        if request.is_json:
            return success_response({"next": url_for("onboarding.capabilities")})
        return redirect(url_for("onboarding.capabilities"))

    return render_template(
        "onboarding/screen2_company.html",
        stages=[{"key": k, "label": v} for k, v in _STAGE_LABELS.items()],
        size_bands=capability_capture.size_bands(),
        current=profile.read(org),
    )


@onboarding_bp.route("/api/website", methods=["POST"])
@login_required
def api_website_read():
    """Screen 2's website field. Saves the address; the reading itself is a
    separate, not-yet-available capability -- this is an honest stub, not a
    fabricated result."""
    org = _current_org()
    data = request.get_json(silent=True) or {}
    source_url = (data.get("source_url") or "").strip()[:500]
    if not source_url:
        return jsonify({"success": False, "error": "no_address"}), 400
    profile.write(org, source_url=source_url)
    return success_response({
        "status": "not_available_yet",
        "message": "Reading your site isn't available yet -- we've saved the address "
                    "and will use it as soon as this is ready.",
    })


def _stage_and_band(org: Organization) -> tuple[str, str]:
    org_profile = profile.read(org)
    stage = org_profile.get("stage") or "pre_revenue"
    band = org_profile.get("size_band") or capability_capture.band_from_text(org_profile.get("company_size"))
    return stage, band


@onboarding_bp.route("/capabilities", methods=["GET", "POST"])
@login_required
def capabilities():
    """What the company can do and how mature each capability is.

    Answers are written to the real capability table (see services/capabilities.py);
    nothing is kept on the side."""
    org = _current_org()
    stage, band = _stage_and_band(org)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        result = capability_capture.save(data.get("items") or [], stage=stage, size_band=band)
        return success_response({"next": url_for("onboarding.people"), **result})
    return render_template(
        "onboarding/screen3_capabilities.html",
        rows=capability_capture.read(stage, band),
        levels=capability_capture.maturity_levels(),
        stage_label=_STAGE_LABELS.get(stage, stage),
        band_label=next((b["label"] for b in capability_capture.size_bands() if b["key"] == band), band),
    )


@onboarding_bp.route("/people", methods=["GET", "POST"])
@login_required
def people():
    """Who does what, and how well. How people are captured depends on company size.

    People and teams are written as business actors with capability assignments
    (see services/people.py); nothing is kept on the side."""
    org = _current_org()
    stage, band = _stage_and_band(org)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        result = people_capture.save(data.get("people") or [], stage=stage, size_band=band)
        return success_response({"next": url_for("onboarding.goals"), **result})
    return render_template(
        "onboarding/screen3b_people.html",
        state=people_capture.read(stage, band),
        proficiency=list(people_capture.PROFICIENCY),
        roles=list(people_capture.ROLES),
        band=band,
        band_label=next((b["label"] for b in capability_capture.size_bands() if b["key"] == band), band),
    )


@onboarding_bp.route("/goals", methods=["GET", "POST"])
@login_required
def goals():
    """What the company wants to achieve, and what is planned or under way.

    Goals become ArchiMate Goal elements and changes become work packages
    (see services/goals_changes.py); nothing is kept on the side."""
    org = _current_org()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        result = goals_changes.save(data.get("goals") or [], data.get("changes") or [], org_id=org.id)
        return success_response({"next": url_for("onboarding.gaps"), **result})
    return render_template("onboarding/screen3c_goals.html", state=goals_changes.read())


def _recorded_for_org(org: Organization) -> dict:
    """What the organisation actually has recorded, by category. Only an
    *assigned* gap counts as recorded (someone or "founder does this" now
    owns it) -- an *accepted* gap is deliberately deferred and must stay
    visible as a gap, per onboarding-redesign-v3 §4/§5: accepted items are
    "never counted as filled". Only the onboarding-answered facts exist yet
    (the derivation engine that would read real roles/functions/capabilities/
    systems off the estate is a separate, not-yet-landed piece of work) --
    so today this is deliberately small, and every remaining gap reads
    "expected at your stage", never a fabricated fact."""
    org_profile = profile.read(org)
    recorded = {"roles": [], "systems": [], "controls": []}
    assigned = org_profile.get("assigned_gaps", {})
    # assigned gap keys are stored as "<category>:<key>"
    for gap_id in assigned:
        if ":" in gap_id:
            cat, key = gap_id.split(":", 1)
            if cat in recorded:
                recorded[cat].append(key)
    return recorded


@onboarding_bp.route("/gaps", methods=["GET"])
@login_required
def gaps():
    org = _current_org()
    org_profile = profile.read(org)
    stage = org_profile.get("stage") or "pre_revenue"
    recorded = _recorded_for_org(org)
    all_gaps = stage_gaps.compute_gaps(
        stage,
        recorded,
        region_europe_or_eu_customers=bool(org_profile.get("region_europe_or_eu_customers")),
        handles_card_data_directly=bool(org_profile.get("handles_card_data_directly")),
    )
    accepted = org_profile.get("accepted_gaps", {})
    assigned = org_profile.get("assigned_gaps", {})
    for gap in all_gaps:
        gap_id = f"{gap['category']}:{gap['key']}"
        gap["gap_id"] = gap_id
        gap["accepted_reason"] = accepted.get(gap_id)
        gap["assigned_to"] = assigned.get(gap_id)
    return render_template(
        "onboarding/screen4_gaps.html",
        stage_label=_STAGE_LABELS.get(stage, stage),
        gaps=all_gaps,
    )


@onboarding_bp.route("/gaps/<gap_id>/action", methods=["POST"])
@login_required
def gap_action(gap_id: str):
    """Accept-for-now or assign a stage gap. Accepted gaps stay visible under
    Coverage as accepted, with the reason and date -- they are never counted
    as filled, per onboarding-redesign-v3 §4."""
    org = _current_org()
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    org_profile = profile.read(org)
    if action == "accept":
        reason = (data.get("reason") or "").strip()[:300]
        accepted = dict(org_profile.get("accepted_gaps", {}))
        accepted[gap_id] = {
            "reason": reason or "Not yet",
            "at": datetime.datetime.utcnow().isoformat(),
            "by_user_id": current_user.id,
        }
        profile.write(org, accepted_gaps=accepted)
    elif action == "assign":
        assignee = (data.get("assignee") or "").strip()[:200]
        if not assignee:
            return jsonify({"success": False, "error": "no_assignee"}), 400
        assigned = dict(org_profile.get("assigned_gaps", {}))
        assigned[gap_id] = {
            "assignee": assignee,
            "at": datetime.datetime.utcnow().isoformat(),
            "by_user_id": current_user.id,
        }
        profile.write(org, assigned_gaps=assigned)
    else:
        return jsonify({"success": False, "error": "invalid_action"}), 400
    return success_response({"gap_id": gap_id, "action": action})


@onboarding_bp.route("/twin")
@login_required
def twin():
    return render_template("onboarding/screen5_twin.html")


@onboarding_bp.route("/finish", methods=["POST"])
@login_required
def finish():
    """Record completion. Writes the same User.onboarding_completed_at (and
    optional enterprise_role) as dashboard.api_onboarding_complete -- one
    column, so no second "onboarding done" flag exists, but this route holds
    its own copy of that small write rather than calling the other endpoint."""
    data = request.get_json(silent=True) or {}
    new_role = data.get("enterprise_role")
    valid_roles = {
        "solution_architect", "enterprise_architect", "business_architect",
        "arb_member", "portfolio_manager", "platform_admin",
        "cto", "application_manager", "procurement",
    }
    if new_role and new_role in valid_roles:
        current_user.enterprise_role = new_role
    current_user.onboarding_completed_at = datetime.datetime.utcnow()
    db.session.commit()
    return success_response({"next": url_for("dashboard.overview")})
