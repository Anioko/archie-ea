"""
Run record routes — list and detail views for organisation administrators.

Every organisation administrator can view the agent run records for their
organisation. Records from other organisations are never returned.
"""
import logging

from flask import abort, render_template, request
from flask_login import current_user

from app.models.agent_charter import AgentCharter
from app.models.agent_run_record import AgentRunRecord

logger = logging.getLogger(__name__)


def _org_id():
    """Return the current user's organisation id, or None."""
    if not current_user or not current_user.is_authenticated:
        return None
    return getattr(current_user, "organization_id", None)


def _require_org_admin():
    """Abort 403 if the current user is not an organisation admin."""
    if not current_user or not current_user.is_authenticated:
        abort(401)
    if not getattr(current_user, "is_org_admin", False) and \
       not getattr(current_user, "is_platform_admin", False):
        abort(403)


def register_run_record_routes(bp):
    """Register run-record routes on a Flask Blueprint."""

    @bp.route("/run-records")
    def run_record_list():
        """List agent run records for this organisation."""
        _require_org_admin()
        org_id = _org_id()
        if org_id is None:
            abort(400)
        page = request.args.get("page", 1, type=int)
        per_page = 20
        query = AgentRunRecord.query.filter_by(organization_id=org_id).order_by(
            AgentRunRecord.created_at.desc()
        )
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        records = pagination.items
        return render_template(
            "ai_chat/run_records/list.html",
            records=records,
            pagination=pagination,
        )

    @bp.route("/run-records/<int:record_id>")
    def run_record_detail(record_id):
        """Show one agent run record with its tools called and records read."""
        _require_org_admin()
        org_id = _org_id()
        if org_id is None:
            abort(400)
        record = AgentRunRecord.query.filter_by(
            id=record_id, organization_id=org_id
        ).first_or_404()
        # Resolve the charter used for this run (if any)
        charter = None
        if record.persona and record.charter_version:
            charter = AgentCharter.query.filter_by(
                persona=record.persona,
                version=record.charter_version,
                organization_id=org_id,
            ).first()
        return render_template(
            "ai_chat/run_records/detail.html",
            record=record,
            charter=charter,
        )