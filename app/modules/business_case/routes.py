"""Routes for the Business Case module.

Blueprint: business_case_bp, url_prefix="/business-case".
Index endpoint (linked from the sidebar by the orchestrator post-merge):
    business_case.index
"""

import logging

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

# Destructive and mutating routes were guarded by @login_required only, so any
# authenticated user could delete another user's records. Matches the gating
# already used by app/modules/capabilities/routes/enterprise_crud_routes.py.
from app.decorators import require_roles

from app.models.business_case import BUSINESS_CASE_STATUSES
from app.models.business_capabilities import BusinessCapability
from app.models.solution_models import Solution
from app.models.strategic import StrategicInitiative
from app.utils.api_response import error_response, not_found_response, success_response

from . import service

logger = logging.getLogger(__name__)

business_case_bp = Blueprint("business_case", __name__, url_prefix="/business-case")


def _link_options():
    """Simple select-list options for the capability/initiative/solution link pickers."""
    capabilities = BusinessCapability.query.order_by(BusinessCapability.name).all()
    initiatives = StrategicInitiative.query.order_by(StrategicInitiative.name).all()
    solutions = Solution.query.order_by(Solution.name).all()
    return capabilities, initiatives, solutions


@business_case_bp.route("/")
@login_required
def index():
    """List all Business Cases for the current tenant."""
    business_cases = service.list_business_cases()
    return render_template(
        "business_case/index.html",
        business_cases=business_cases,
        statuses=BUSINESS_CASE_STATUSES,
    )


@business_case_bp.route("/create", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def create():
    """Create a new business case and redirect to its document view."""
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None

    try:
        business_case = service.create_business_case(
            title=title or "Untitled Business Case",
            description=description,
            created_by_id=getattr(current_user, "id", None),
        )
    except ValueError as exc:
        logger.warning("Invalid business case create payload: %s", exc)
        return redirect(url_for("business_case.index"))

    return redirect(url_for("business_case.detail", business_case_id=business_case.id))


@business_case_bp.route("/<int:business_case_id>")
@login_required
def detail(business_case_id):
    """The structured business-case document view."""
    business_case = service.get_business_case_or_none(business_case_id)
    if business_case is None:
        return render_template("business_case/not_found.html", business_case_id=business_case_id), 404

    capabilities, initiatives, solutions = _link_options()
    return render_template(
        "business_case/detail.html",
        business_case=business_case,
        statuses=BUSINESS_CASE_STATUSES,
        capabilities=capabilities,
        initiatives=initiatives,
        solutions=solutions,
    )


@business_case_bp.route("/<int:business_case_id>/report.<fmt>")
@login_required
def business_case_report(business_case_id, fmt):
    """One business case as a document: PDF, Word, Excel or a shareable page.

    The business case is the artefact that already *is* a document, and until
    now it existed only as a web form — so the version that reached an
    investment board was whatever somebody retyped into their own template.

    A format that cannot be produced on this deployment answers with the reason
    and a 503, not a 500 and not a zero-byte file: WeasyPrint is a binding over
    native libraries that are absent on Windows and on slim images, and the
    other three formats still work when it is missing.
    """
    from app.utils.report_export import (
        REPORT_FORMATS,
        current_organisation_name,
        normalise_format,
        report_response,
        safe_filename_stem,
        unsupported_format_response,
    )

    from .report_service import BusinessCaseReportError, BusinessCaseReportService

    fmt = normalise_format(fmt)
    if fmt not in REPORT_FORMATS:
        return unsupported_format_response(fmt)

    try:
        report = BusinessCaseReportService.build(
            business_case_id, organisation_name=current_organisation_name()
        )
        if report is None:
            return jsonify({"success": False, "error": "Business case not found."}), 404
        if fmt == "pdf":
            payload = BusinessCaseReportService.render_pdf(report)
        elif fmt == "docx":
            payload = BusinessCaseReportService.render_docx(report)
        elif fmt == "xlsx":
            payload = BusinessCaseReportService.render_xlsx(report)
        else:
            payload = BusinessCaseReportService.render_html(report)
    except BusinessCaseReportError as exc:
        current_app.logger.warning("business case report unavailable as %s: %s", fmt, exc)
        return jsonify({"success": False, "error": str(exc)}), 503
    except Exception:  # noqa: BLE001
        current_app.logger.exception(
            "business case %s report failed to render as %s", business_case_id, fmt
        )
        return (
            jsonify({
                "success": False,
                "error": "The business case report could not be generated. The "
                         "failure has been logged.",
            }),
            500,
        )

    stem = safe_filename_stem(report["case"]["title"], "business_case")
    return report_response(payload, fmt, f"business_case_{stem}")


@business_case_bp.route("/<int:business_case_id>/update", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def update(business_case_id):
    """Update business case meta fields (title/description/status/links) — JSON API."""
    business_case = service.get_business_case_or_none(business_case_id)
    if business_case is None:
        return not_found_response("Business Case")

    payload = request.get_json(silent=True) or request.form
    fields = {}
    for key in (
        "title",
        "description",
        "status",
        "capability_id",
        "strategic_initiative_id",
        "solution_id",
    ):
        if key in payload:
            fields[key] = payload.get(key)

    try:
        business_case = service.update_business_case(business_case, **fields)
    except ValueError as exc:
        return error_response(str(exc), code="VALIDATION_ERROR", status_code=400)

    return success_response(business_case.to_dict())


@business_case_bp.route("/<int:business_case_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete(business_case_id):
    """Delete a business case."""
    business_case = service.get_business_case_or_none(business_case_id)
    if business_case is None:
        return not_found_response("Business Case")

    service.delete_business_case(business_case)
    return redirect(url_for("business_case.index"))


@business_case_bp.route("/<int:business_case_id>/api/field", methods=["POST", "PUT"])
@login_required
@require_roles("admin", "architect", "business_architect")
def save_field(business_case_id):
    """Save a single business-case document section (inline save).

    Payload: {"field": "problem_statement", "value": "..."}
    """
    business_case = service.get_business_case_or_none(business_case_id)
    if business_case is None:
        return not_found_response("Business Case")

    payload = request.get_json(silent=True) or {}
    field_name = payload.get("field")
    value = payload.get("value")

    if not field_name:
        return error_response("Missing 'field' field", code="VALIDATION_ERROR", status_code=400)

    try:
        business_case = service.save_field(business_case, field_name, value)
    except ValueError as exc:
        return error_response(str(exc), code="VALIDATION_ERROR", status_code=400)

    return success_response(business_case.to_dict())


@business_case_bp.route("/<int:business_case_id>/pull-financials", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def pull_financials(business_case_id):
    """Re-run aggregate_financials() against the linked capability / initiative
    / solution and pre-populate any blank financial fields (JSON API)."""
    business_case = service.get_business_case_or_none(business_case_id)
    if business_case is None:
        return not_found_response("Business Case")

    report = service.refresh_financials_from_links(business_case)
    return success_response({"business_case": business_case.to_dict(), "aggregation": report})
