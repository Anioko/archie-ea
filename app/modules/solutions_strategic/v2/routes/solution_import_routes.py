"""ArchiMate OEF XML import routes (ENT-067).

The canonical model-import screen is ``architect_ui.import_oef`` at
``/architecture/import/oef`` (product decision, T-L1-IMPORT-OPS). This
route now only redirects the old ``/solutions/import/archimate`` URL there;
the preview/execute two-step panel that used to live here
(``solutions/import_archimate.html`` and its partial) had no other caller
and has been removed along with this route's redirect target.

Routes are attached to ``solution_design_bp`` (url_prefix=/solutions).
"""

from flask import redirect, request, url_for
from flask_login import login_required

from .solution_design_routes import solution_design_bp


@solution_design_bp.route("/import/archimate", methods=["GET"])
@login_required
def import_archimate_page():
    """Permanent redirect to the canonical OEF import screen."""
    target = url_for("architect_ui.import_oef")
    if request.query_string:
        target = f"{target}?{request.query_string.decode('utf-8')}"
    return redirect(target, code=301)
