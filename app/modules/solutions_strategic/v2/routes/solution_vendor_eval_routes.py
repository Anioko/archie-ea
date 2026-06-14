"""Vendor evaluation workflow routes — shortlist, search, manage.

Registers on ``solution_design_bp`` (url_prefix="/solutions").
Provides:
  GET  /<solution_id>/vendor-evaluation           — shortlist data
  GET  /vendor-products/search?q=&category=&limit= — search vendor products
  POST /<solution_id>/vendor-evaluation/shortlist  — add to shortlist
  DELETE /<solution_id>/vendor-evaluation/shortlist/<product_id> — remove
"""

import logging

from flask import jsonify, request
from flask_login import login_required

from app import db
from app.modules.solutions_strategic.v2.services.solution_vendor_eval_service import (
    SolutionVendorEvalService,
)

from .solution_design_routes import solution_design_bp

logger = logging.getLogger(__name__)

_svc = SolutionVendorEvalService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_solution_or_404(solution_id):
    """Return (solution, None) or (None, error_response)."""
    from app.models.solution_models import Solution

    solution = db.session.get(Solution, solution_id)
    if not solution:
        return None, (jsonify({"success": False, "error": "Solution not found"}), 404)
    return solution, None


# ---------------------------------------------------------------------------
# Shortlist endpoints
# ---------------------------------------------------------------------------


@solution_design_bp.route(
    "/<int:solution_id>/vendor-evaluation", methods=["GET"],
    endpoint="vendor_evaluation_get",
)
@login_required
def get_vendor_evaluation(solution_id):
    """Return the current vendor evaluation shortlist for a solution."""
    solution, err = _get_solution_or_404(solution_id)
    if err:
        return err

    shortlist = _svc.get_shortlist(solution_id)
    categories = _svc.get_product_categories()
    return jsonify({
        "success": True,
        "shortlist": shortlist,
        "categories": categories,
        "shortlist_count": len(shortlist),
    })


@solution_design_bp.route(
    "/vendor-products/search", methods=["GET"],
    endpoint="vendor_products_search",
)
@login_required
def search_vendor_products():
    """Search vendor products by name and optional category filter."""
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip() or None
    limit = request.args.get("limit", 20, type=int)

    results = _svc.search_vendor_products(query=query, category=category, limit=limit)
    return jsonify({"success": True, "results": results, "count": len(results)})


@solution_design_bp.route(
    "/<int:solution_id>/vendor-evaluation/shortlist", methods=["POST"],
    endpoint="vendor_evaluation_add",
)
@login_required
def add_to_vendor_shortlist(solution_id):
    """Add a vendor product to the evaluation shortlist."""
    solution, err = _get_solution_or_404(solution_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")
    if not product_id:
        return jsonify({"success": False, "error": "product_id is required"}), 400

    try:
        product_id = int(product_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "product_id must be an integer"}), 400

    notes = data.get("notes", "")

    try:
        item, warning = _svc.add_to_shortlist(solution_id, product_id, notes=notes)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409

    response = {"success": True, "item": item}
    if warning:
        response["warning"] = warning
    return jsonify(response), 201


@solution_design_bp.route(
    "/<int:solution_id>/vendor-evaluation/shortlist/<int:product_id>",
    methods=["DELETE"],
    endpoint="vendor_evaluation_remove",
)
@login_required
def remove_from_vendor_shortlist(solution_id, product_id):
    """Remove a vendor product from the evaluation shortlist."""
    solution, err = _get_solution_or_404(solution_id)
    if err:
        return err

    deleted = _svc.remove_from_shortlist(solution_id, product_id)
    if deleted == 0:
        return jsonify({"success": False, "error": "Product not on shortlist"}), 404

    return jsonify({"success": True, "removed_product_id": product_id})


# ---------------------------------------------------------------------------
# Comparison matrix
# ---------------------------------------------------------------------------


@solution_design_bp.route(
    "/<int:solution_id>/vendor-evaluation/comparison",
    methods=["GET"],
    endpoint="vendor_evaluation_comparison",
)
@login_required
def get_vendor_comparison(solution_id):
    """Return side-by-side comparison data for shortlisted products."""
    solution, err = _get_solution_or_404(solution_id)
    if err:
        return err

    try:
        matrix = _svc.get_comparison_matrix(solution_id)
    except Exception:
        logger.exception("Error building comparison matrix for solution %s", solution_id)
        return jsonify({"success": False, "error": "Failed to build comparison matrix"}), 500

    return jsonify({"success": True, **matrix})


# ---------------------------------------------------------------------------
# Decision recording
# ---------------------------------------------------------------------------


@solution_design_bp.route(
    "/<int:solution_id>/vendor-evaluation/decision",
    methods=["POST"],
    endpoint="vendor_evaluation_decision",
)
@login_required
def record_vendor_decision(solution_id):
    """Record the vendor selection decision for a solution."""
    solution, err = _get_solution_or_404(solution_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}

    product_id = data.get("product_id")
    if not product_id:
        return jsonify({"success": False, "error": "product_id is required"}), 400

    try:
        product_id = int(product_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "product_id must be an integer"}), 400

    rationale = data.get("rationale", "").strip()
    if not rationale:
        return jsonify({"success": False, "error": "rationale is required"}), 400

    criteria_weights = data.get("criteria_weights", {})

    try:
        decision = _svc.record_decision(
            solution_id=solution_id,
            product_id=product_id,
            rationale=rationale,
            criteria_weights=criteria_weights,
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    return jsonify({"success": True, "decision": decision})
