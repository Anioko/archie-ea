"""Ask, Twin map and Value streams at risk: the pages of the intelligence
module's user interface.

Every route only renders a page shell. The data is fetched in the browser from
endpoints that already exist: element search from the ArchiMate picker
endpoint, the impact answer and the value-streams-at-risk answer from the
intelligence API, so the pages carry no query of their own and no way to read
another tenant's rows.

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


# The maturity threshold the value-streams-at-risk answer is asked for. The
# page shell opens on the same bounds and default as the API route that answers
# it; the browser then canonicalises the address bar to that same allowed
# threshold set.
VALUE_STREAMS_AT_RISK_THRESHOLDS = (1, 2, 3, 4, 5)
VALUE_STREAMS_AT_RISK_DEFAULT_THRESHOLD = 3


@intelligence_ui.route("/value-streams-at-risk", methods=["GET"])
@login_required
def value_streams_at_risk():
    """Show the organisation's value streams whose capabilities fall below a
    maturity threshold.

    The rows and counts are the intelligence API's own answer
    (``GET /api/v1/intelligence/value-streams-at-risk``), fetched in the
    browser; nothing is computed here. ``threshold`` (optional, 1 to 5,
    default 3) is the value the page opens on, so a reload or a shared link
    shows the same answer.
    """
    threshold = request.args.get("threshold", type=int)
    if threshold not in VALUE_STREAMS_AT_RISK_THRESHOLDS:
        threshold = VALUE_STREAMS_AT_RISK_DEFAULT_THRESHOLD
    return render_template(
        "intelligence/value_streams_at_risk.html",
        threshold=threshold,
        thresholds=VALUE_STREAMS_AT_RISK_THRESHOLDS,
    )


__all__ = ["intelligence_ui"]
