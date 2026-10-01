"""Ask, Twin map and Traceability: the pages of the intelligence module's user interface.

Ask and Twin map only render a page shell. Their data is fetched in the browser from
endpoints that already exist: element search from the ArchiMate picker
endpoint and the impact answer from the intelligence API, so the pages carry no
query of their own and no way to read another tenant's rows. Traceability
renders its answer on the server from the traceability check service, which
reads the same tenant-fenced walk as the impact answer.

The provenance drawer is not a route. It opens over either page.
"""

from __future__ import annotations

from flask import Blueprint, current_app, g, render_template, request
from flask_login import login_required

intelligence_ui = Blueprint(
    "intelligence_ui",
    __name__,
    url_prefix="/intelligence",
    template_folder="../templates",
)


def _workspace_counts_available() -> bool:
    """Whether the shell's per-tenant counts can be read right now.

    Both pages show a "nothing is modelled yet" state only when those counts say
    the workspace is empty. The shell's own context processor answers a failed
    read with counts of zero, which is indistinguishable from an empty
    workspace, so this asks the same cached function directly and reports
    whether it worked. An unreadable count is never treated as an empty
    workspace.
    """
    try:
        from app._bootstrap.context_processors import compute_nav_counts

        compute_nav_counts(getattr(g, "current_org_id", None))
        return True
    except Exception:
        current_app.logger.warning("[MODULE] intelligence: workspace counts unavailable")
        return False


@intelligence_ui.route("/ask", methods=["GET"])
@login_required
def ask():
    """Ask a plain business question about what depends on a chosen element."""
    return render_template(
        "intelligence/ask.html",
        workspace_counts_available=_workspace_counts_available(),
    )


@intelligence_ui.route("/twin-map", methods=["GET"])
@login_required
def twin_map():
    """Show what a chosen element connects to, banded by architecture layer.

    ``element`` (optional) is the id of the element to centre the map on, so a
    row on the Ask page can hand its element straight across. A value that is
    not a whole number is ignored and the page opens on its picker.
    """
    initial_element_id = request.args.get("element", type=int)
    return render_template(
        "intelligence/twin_map.html",
        initial_element_id=initial_element_id,
        workspace_counts_available=_workspace_counts_available(),
    )


@intelligence_ui.route("/traceability", methods=["GET"])
@login_required
def traceability():
    """Check one element's chains up to a capability and down to technology.

    ``element`` (optional) is the id of the element to check. The answer is
    rendered on the server from ``TraceabilityCheckService.check``, which
    reads the same tenant-fenced walk as the impact answer; an id outside the
    caller's organisation renders the same "not found" state as a missing one.
    Candidate relationships are added through the existing relationship
    writer from the browser, then the page reloads and checks again.
    """
    element_id = request.args.get("element", type=int)
    result = None
    if element_id is not None:
        from app.modules.intelligence.services.traceability_check_service import TraceabilityCheckService

        org_id = getattr(g, "current_org_id", None)
        if org_id is None:
            from flask_login import current_user

            org_id = getattr(current_user, "organization_id", None)
        result = TraceabilityCheckService.check(element_id, org_id)
    return render_template(
        "intelligence/traceability.html",
        element_id=element_id,
        result=result,
        workspace_counts_available=_workspace_counts_available(),
    )


__all__ = ["intelligence_ui"]
