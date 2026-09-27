"""
Enterprise Genome — SECURITY slice route.

One org-scoped page with a "Generate control matrix" button. Clicking it
(re)builds the SECURITY genome slice for the current organisation and renders
the deterministic control-to-requirement matrix inline. Server-rendered, no
inline JS — the button is a plain GET form, so it is CSP-safe.
"""
from __future__ import annotations

from flask import Blueprint, g, render_template, request
from flask_login import current_user, login_required

from app.modules.enterprise_genome.services.security_matrix_emitter import (
    render_control_matrix,
)
from app.modules.enterprise_genome.services.security_slice import build_security_slice

enterprise_genome_bp = Blueprint(
    "enterprise_genome",
    __name__,
    url_prefix="/enterprise-genome",
)


def _current_org_id() -> int | None:
    """Resolve the acting tenant: explicit ?org_id for a demo, else the session org."""
    raw = request.args.get("org_id")
    if raw and raw.isdigit():
        return int(raw)
    org_id = getattr(g, "current_org_id", None)
    if org_id is None:
        org_id = getattr(current_user, "organization_id", None)
    return org_id


@enterprise_genome_bp.route("/security/matrix", methods=["GET"])
@login_required
def security_matrix():
    """Render the SECURITY control-to-requirement matrix page.

    Without ``?generate=1`` the page shows the intro and the Generate button.
    With it, the slice is built and the matrix is rendered inline.
    """
    org_id = _current_org_id()
    generate = request.args.get("generate") == "1"

    rendered_matrix = None
    slice_meta = None
    if generate and org_id is not None:
        genome_slice = build_security_slice(org_id)
        rendered_matrix = render_control_matrix(genome_slice)
        slice_meta = {
            "spec_hash": genome_slice["spec_hash"],
            "store": genome_slice["store"],
            "count": len(genome_slice["controls"]),
            "version": genome_slice["genome_version"],
        }

    return render_template(
        "enterprise_genome/security_matrix.html",
        org_id=org_id,
        rendered_matrix=rendered_matrix,
        slice_meta=slice_meta,
    )
