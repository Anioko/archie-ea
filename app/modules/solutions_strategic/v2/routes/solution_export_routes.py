"""COM-022 — Solution blueprint export routes.

Routes:
    GET /solutions/<id>/export/pptx  — Download blueprint as PowerPoint
"""

import logging

from flask import Blueprint, make_response
from flask_login import login_required

logger = logging.getLogger(__name__)

solution_export_bp = Blueprint("solution_export", __name__, url_prefix="/solutions")


@solution_export_bp.route("/<int:solution_id>/export/pptx", methods=["GET"])
@login_required
def export_solution_pptx(solution_id: int):
    """Download solution architecture blueprint as a .pptx file.

    Also uploads the file to SharePoint if M365 integration is configured
    for this deployment. The SharePoint URL is returned in the
    X-SharePoint-URL response header when upload succeeds.

    Returns:
        200 + PPTX bytes on success.
        404 if solution not found.
    """
    from app.models.solution_models import Solution
    from app.services.powerpoint_export_service import PowerPointExportService

    solution = Solution.query.get_or_404(solution_id)

    pptx_bytes = PowerPointExportService.generate(solution_id)

    safe_name = (solution.name or "blueprint").replace(" ", "_").replace("/", "-")[:80]
    filename = f"{safe_name}_blueprint.pptx"

    response = make_response(pptx_bytes)
    response.headers["Content-Type"] = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Content-Length"] = len(pptx_bytes)

    # COM-017: upload to SharePoint if M365 is configured
    try:
        from app.services.m365_service import M365Service

        svc = M365Service()
        m365_cfg = svc._get_config()
        if m365_cfg:
            cfg_data = m365_cfg.config or {}
            site_id = cfg_data.get("site_id", "")
            folder_path = cfg_data.get("folder_path", "Architecture Blueprints")
            if site_id:
                org_id = getattr(solution, "org_id", None)
                sharepoint_url = svc.upload_to_sharepoint(
                    org_id=org_id,
                    file_content=pptx_bytes,
                    filename=filename,
                    site_id=site_id,
                    folder_path=folder_path,
                )
                if sharepoint_url:
                    response.headers["X-SharePoint-URL"] = sharepoint_url
    except Exception:
        logger.exception("COM-017: SharePoint upload hook failed for solution %s", solution_id)

    # COM-013: Journey 5 — Architecture exported
    try:
        from app.services.analytics_service import AnalyticsService
        from flask import g
        from flask_login import current_user
        _org_id = getattr(g, "current_org_id", None)
        _uid = getattr(current_user, "id", None)
        AnalyticsService().capture(
            f"{_org_id}:{_uid}",
            "architecture_exported",
            {
                "format": "pptx",
                "solution_id": solution_id,
                "org_id": _org_id,
            },
        )
    except Exception:
        logger.debug("COM-013: architecture_exported event failed (non-blocking)")

    return response
