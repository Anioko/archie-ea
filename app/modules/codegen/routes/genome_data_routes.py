"""
Enterprise Genome — DATA slice route.

One org-scoped page with a "Generate RoPA" button. Deterministic, 0-LLM: the
button builds the DATA genome slice for the current organization and renders the
GDPR Article 30 Record of Processing Activities table from it.
"""
import logging

from flask import Blueprint, g, render_template
from flask_login import current_user, login_required

logger = logging.getLogger(__name__)

genome_data_bp = Blueprint("genome_data", __name__, url_prefix="/genome/data")


def _current_org_id():
    """Resolve the acting organization, preferring the request tenant context."""
    org_id = getattr(g, "current_org_id", None)
    if org_id is None and current_user.is_authenticated:
        org_id = getattr(current_user, "organization_id", None)
    return org_id


@genome_data_bp.route("/ropa", methods=["GET"])
@login_required
def ropa_index():
    """Landing page — shows the Generate RoPA button, no table yet."""
    return render_template(
        "genome/data_ropa.html",
        ropa_html=None,
        activity_count=0,
        spec_hash=None,
    )


@genome_data_bp.route("/ropa/generate", methods=["POST"])
@login_required
def generate_ropa():
    """Build the DATA slice for the current org and render the Article 30 table."""
    from app.modules.codegen.services.genome_data_ropa_emitter import render_ropa_table
    from app.modules.codegen.services.genome_data_slice import build_data_genome_slice

    org_id = _current_org_id()
    slice_dict = build_data_genome_slice(org_id)
    ropa_html = render_ropa_table(slice_dict)
    return render_template(
        "genome/data_ropa.html",
        ropa_html=ropa_html,
        activity_count=len(slice_dict["processing_activities"]),
        spec_hash=slice_dict["spec_hash"],
    )
