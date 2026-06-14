"""
Vendor Population API Routes

Provides endpoints for managing vendor data population and enrichment.
"""

import logging

from flask import Blueprint, jsonify
from flask_login import login_required

logger = logging.getLogger(__name__)

# Create blueprint
vendor_population_bp = Blueprint("vendor_population", __name__, url_prefix="/api/vendor-population")


@vendor_population_bp.route("/status", methods=["GET"])
@login_required
def get_population_status():
    """Get the current status of vendor population processes."""
    return jsonify(
        {"success": True, "status": "ready", "message": "Vendor population service is available"}
    )
