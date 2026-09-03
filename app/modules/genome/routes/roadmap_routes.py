"""Transformation Roadmap page — deterministic genome slice, org-scoped read.

One read route + one page. The presenter clicks "Generate roadmap"; the server
builds the implementation-layer genome slice for the current tenant (zero LLM),
the deterministic emitter renders it to a gantt-style HTML fragment, and the
page shows it with element-level provenance on every plateau lane and work
package bar.

No write path — pure read + deterministic render. This is ADR 0010's
IMPLEMENTATION domain, modelled exactly on the proven business-layer coverage
slice alongside it.
"""
from __future__ import annotations

import logging

from flask import Blueprint, g, render_template
from flask_login import current_user, login_required
from markupsafe import Markup

from app.modules.genome.emit.roadmap_gantt import emit_roadmap_gantt_html
from app.modules.genome.services.roadmap_slice import (
    SliceProvenanceError,
    build_roadmap_slice,
)

logger = logging.getLogger(__name__)

genome_roadmap_bp = Blueprint(
    "genome_roadmap",
    __name__,
    url_prefix="/genome/roadmap",
    template_folder="../templates",
)


def _active_org_id():
    """The current tenant's organization_id (g first, then the user)."""
    org_id = getattr(g, "current_org_id", None)
    if org_id is None:
        org_id = getattr(current_user, "organization_id", None)
    return org_id


@genome_roadmap_bp.route("/", methods=["GET"])
@login_required
def index():
    """Landing page with the 'Generate roadmap' button (no roadmap yet)."""
    return render_template(
        "genome/roadmap.html",
        roadmap_html=None,
        error=None,
        org_id=_active_org_id(),
    )


@genome_roadmap_bp.route("/generate", methods=["POST"])
@login_required
def generate():
    """Build the slice for the current tenant and render the gantt inline."""
    org_id = _active_org_id()
    roadmap_html = None
    error = None
    if org_id is None:
        error = "No active organization for the current user."
    else:
        try:
            slice_dict = build_roadmap_slice(org_id)
            # The deterministic emitter escapes every database-derived text field.
            roadmap_html = Markup(  # nosec B704
                emit_roadmap_gantt_html(slice_dict)
            )
        except SliceProvenanceError as exc:
            # Provenance is structural and non-optional — surface the failure,
            # never render a fabricated or half-provenanced roadmap.
            logger.warning("Roadmap slice provenance error for org %s: %s", org_id, exc)
            error = f"Roadmap could not be built: {exc}"
    return render_template(
        "genome/roadmap.html",
        roadmap_html=roadmap_html,
        error=error,
        org_id=org_id,
    )


def register(app):
    """Register the Transformation Roadmap blueprint on the app."""
    app.register_blueprint(genome_roadmap_bp)
    app.logger.info(
        "[BLUEPRINT] Transformation Roadmap registered at /genome/roadmap"
    )
