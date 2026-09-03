"""Model Health / Drift page — deterministic detector + governed remediation.

Two routes, one page:

  GET  /genome/model-health            — run the deterministic drift detector for
                                          the current tenant and render the report
                                          (zero LLM), provenance on every finding.
  POST /genome/model-health/remediate  — for ONE selected fixable finding, build a
                                          genome patch and route it through the
                                          EXISTING governed approval gate
                                          (`propose_genome_patch`): validate →
                                          ground → QUEUE for human approval. Nothing
                                          is applied here; approval + apply happen
                                          through the existing AI approval flow.

The detector is read-only and org-scoped. The remediation POST never edits the
model — it only queues a proposal, so a change to the system of record still
carries a human decision (ADR 0009: propose-and-govern, never silent auto-edit).
"""
from __future__ import annotations

import logging

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from markupsafe import Markup

from app.modules.genome.emit.drift_report import (
    DRIFT_CSRF_PLACEHOLDER,
    emit_drift_report_html,
)
from app.modules.genome.patch.schema import (
    ARCHIMATE_TYPE_LAYER,
    ARCHIMATE_TYPES,
    GENOME_DOMAINS,
)
from app.modules.genome.services.drift_detector import (
    FINDING_DECOMM_MAPPED,
    FINDING_ORPHANED,
    detect_model_drift,
)

logger = logging.getLogger(__name__)

genome_drift_bp = Blueprint(
    "genome_drift",
    __name__,
    url_prefix="/genome/model-health",
    template_folder="../templates",
)

# Finding types this page can propose a single-element governed fix for. Other
# findings (coverage gaps, duplicate merges, missing realizations) need a
# multi-element decision and are surfaced read-only, not offered a one-click fix.
_FIXABLE = {FINDING_ORPHANED, FINDING_DECOMM_MAPPED}

# Layer -> genome domain (all values are in GENOME_DOMAINS). Used to target the
# remediation patch at the right genome domain.
_LAYER_DOMAIN = {
    "motivation": "motivation",
    "strategy": "business",
    "business": "business",
    "application": "application",
    "technology": "technology",
    "implementation": "implementation",
    "physical": "technology",
}


def _active_org_id():
    """The current tenant's organization_id (g first, then the user)."""
    org_id = getattr(g, "current_org_id", None)
    if org_id is None:
        org_id = getattr(current_user, "organization_id", None)
    return org_id


def _csrf_input() -> str:
    """A real CSRF hidden input, substituted into the emitter's placeholder."""
    try:
        from flask_wtf.csrf import generate_csrf

        token = generate_csrf()
    except Exception:  # pragma: no cover - CSRF disabled in some test configs
        return ""
    return f'<input type="hidden" name="csrf_token" value="{token}">'


@genome_drift_bp.route("/", methods=["GET"])
@login_required
def index():
    """Run the detector for the current tenant and render the drift dashboard."""
    org_id = _active_org_id()
    report_html = None
    error = None
    summary = None
    if org_id is None:
        error = "No active organization for the current user."
    else:
        try:
            report = detect_model_drift(org_id)
            summary = report.get("summary")
            html = emit_drift_report_html(report)
            # Substitute the CSRF placeholder AFTER the deterministic emit.
            html = html.replace(DRIFT_CSRF_PLACEHOLDER, _csrf_input())
            # The emitter escapes model data; the only substitution is a
            # server-generated CSRF input, never request-controlled HTML.
            report_html = Markup(html)  # nosec B704
        except Exception as exc:  # surface, never render a fabricated report
            logger.warning("Drift detection failed for org %s: %s", org_id, exc)
            error = f"Model-health report could not be built: {exc}"
    return render_template(
        "genome/model_health.html",
        report_html=report_html,
        summary=summary,
        error=error,
        org_id=org_id,
    )


@genome_drift_bp.route("/remediate", methods=["POST"])
@login_required
def remediate():
    """Queue a GOVERNED remediation for one selected finding. Applies nothing."""
    org_id = _active_org_id()
    finding_type = (request.form.get("finding_type") or "").strip()
    element_id_raw = (request.form.get("element_id") or "").strip()

    if org_id is None:
        flash("No active organization for the current user.", "error")
        return redirect(url_for("genome_drift.index"))

    if finding_type not in _FIXABLE:
        flash(
            "That finding needs a multi-element decision and cannot be fixed with "
            "a single governed patch.",
            "error",
        )
        return redirect(url_for("genome_drift.index"))

    try:
        element_id = int(element_id_raw)
    except (TypeError, ValueError):
        flash("Invalid element reference for remediation.", "error")
        return redirect(url_for("genome_drift.index"))

    patch = _build_remediation_patch(org_id, finding_type, element_id)
    if patch is None:
        flash(
            "The selected element cannot be expressed as a governed patch "
            "(unknown ArchiMate type); no proposal was queued.",
            "error",
        )
        return redirect(url_for("genome_drift.index"))

    # Route through the EXISTING governed gate: validate -> ground -> QUEUE.
    from app.modules.genome.patch.proposer import propose_genome_patch

    result = propose_genome_patch(
        request_text=f"Remediate drift finding '{finding_type}' on element #{element_id}",
        user_id=getattr(current_user, "id", None),
        patch_source=lambda _text, _ctx: patch,
        context={"organization_id": org_id},
    )

    if result.get("success"):
        flash(
            f"Governed remediation queued for approval (approval #{result.get('approval_id')}). "
            f"Nothing has been applied — a human must approve it.",
            "success",
        )
    elif result.get("status") == "rejected":
        flash(
            "The proposed fix did not validate/ground and was not queued: "
            + "; ".join(result.get("errors", []) or ["unknown reason"]),
            "error",
        )
    else:
        flash(
            "Could not queue the remediation: " + str(result.get("error", "unknown error")),
            "error",
        )
    return redirect(url_for("genome_drift.index"))


def _build_remediation_patch(org_id: int, finding_type: str, element_id: int):
    """Build a schema-valid `modify` genome patch for a fixable finding.

    Returns the patch dict, or None if the element's ArchiMate type is not one the
    genome-patch schema knows (in which case no fabricated patch is produced —
    CLAUDE.md: never invent data). The patch is NOT applied here; it is handed to
    `propose_genome_patch`, which validates, grounds and queues it for approval.
    """
    from app.extensions import db
    from app.models.archimate_core import ArchiMateElement

    element = (
        db.session.query(ArchiMateElement)
        .filter(ArchiMateElement.id == element_id)
        .filter(ArchiMateElement.organization_id == org_id)
        .first()
    )
    if element is None:
        return None

    a_type = element.type
    if a_type not in ARCHIMATE_TYPES:
        return None  # cannot express as a governed patch without inventing a type

    layer = ARCHIMATE_TYPE_LAYER.get(a_type)
    if layer is None:
        return None
    domain = _LAYER_DOMAIN.get(layer, "business")
    if domain not in GENOME_DOMAINS:
        domain = "business"

    if finding_type == FINDING_ORPHANED:
        rationale = (
            f"Drift detector: element #{element_id} ('{element.name}') is orphaned — "
            f"wired to no relationship and linked from no capability/application. "
            f"Proposing it be flagged for architecture review/retirement."
        )
        fields = {"status": "Flagged-Drift", "drift_signal": FINDING_ORPHANED}
    else:  # FINDING_DECOMM_MAPPED
        rationale = (
            f"Drift detector: application element #{element_id} ('{element.name}') is "
            f"in a retiring lifecycle yet still mapped as active capability support. "
            f"Proposing its retiring lifecycle be recorded on the genome element so "
            f"the model matches reality."
        )
        fields = {
            "status": "Flagged-Drift",
            "drift_signal": FINDING_DECOMM_MAPPED,
            "lifecycle_status": (element.status or "retiring"),
        }

    return {
        "target": {"organization_id": org_id, "domain": domain},
        "operation": "modify",
        "element": {
            "archimate_type": a_type,
            "layer": layer,
            "name": element.name,
            "element_id": element_id,
            "fields": fields,
        },
        "provenance": {
            "proposed_by": f"drift_detector:user_{getattr(current_user, 'id', 'unknown')}",
            "rationale": rationale,
            "archimate_anchor": a_type,  # a known ArchiMate type — resolves in grounding
            "source": "genome_drift_detector",
        },
    }


def register(app):
    """Register the Model Health / Drift blueprint on the app (non-fatal caller)."""
    app.register_blueprint(genome_drift_bp)
    app.logger.info(
        "[BLUEPRINT] Genome model-health / drift registered at /genome/model-health"
    )


__all__ = ["genome_drift_bp", "register", "_build_remediation_patch"]
