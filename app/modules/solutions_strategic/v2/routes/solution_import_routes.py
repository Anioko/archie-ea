"""ArchiMate OEF XML import routes (ENT-067).

Provides upload, preview, and execute endpoints for importing ArchiMate
Open Exchange Format XML files into the platform's element store.

Routes are attached to ``solution_design_bp`` (url_prefix=/solutions).
"""

import logging

from flask import jsonify, request
from flask_login import login_required

from .solution_design_routes import solution_design_bp

logger = logging.getLogger(__name__)

_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB limit for OEF XML files


@solution_design_bp.route("/import/archimate/preview", methods=["POST"])
@login_required
def import_archimate_preview():
    """Upload an OEF XML file and return a preview of elements to import.

    Accepts either:
    - multipart/form-data with a ``file`` field containing the .xml file
    - application/xml or text/xml with XML content in the request body

    Returns JSON with element classification (new/exists/conflict) and
    summary counts.
    """
    from app.services.archimate_import_service import ArchiMateImportService

    xml_content = _extract_xml_content(request)
    if xml_content is None:
        return jsonify({"error": "No XML content provided. Upload a .xml file or send XML in the request body."}), 400

    if len(xml_content) > _MAX_UPLOAD_SIZE:
        return jsonify({"error": f"File too large. Maximum size is {_MAX_UPLOAD_SIZE // (1024 * 1024)} MB."}), 413

    service = ArchiMateImportService()

    try:
        parsed = service.parse_oef_xml(xml_content)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    preview = service.preview_import(parsed)

    return jsonify({
        "model_name": parsed.get("model_name", ""),
        "elements": preview["elements"],
        "relationships": preview["relationships"],
        "summary": preview["summary"],
        "errors": preview["errors"],
    })


@solution_design_bp.route("/import/archimate/execute", methods=["POST"])
@login_required
def import_archimate_execute():
    """Execute an ArchiMate OEF XML import with the chosen strategy.

    Accepts JSON body::

        {
            "xml_content": "<model>...</model>",
            "strategy": "skip_duplicates" | "update_existing" | "create_all"
        }

    Or multipart/form-data with ``file`` and optional ``strategy`` field.

    Returns JSON with created/updated/skipped counts.
    """
    from app.services.archimate_import_service import ArchiMateImportService

    # Determine strategy
    strategy = "skip_duplicates"
    if request.is_json:
        strategy = request.json.get("strategy", "skip_duplicates")
    else:
        strategy = request.form.get("strategy", "skip_duplicates")

    if strategy not in ("skip_duplicates", "update_existing", "create_all"):
        return jsonify({"error": f"Invalid strategy: {strategy}. Must be one of: skip_duplicates, update_existing, create_all"}), 400

    xml_content = _extract_xml_content(request)
    if xml_content is None:
        return jsonify({"error": "No XML content provided."}), 400

    if len(xml_content) > _MAX_UPLOAD_SIZE:
        return jsonify({"error": f"File too large. Maximum size is {_MAX_UPLOAD_SIZE // (1024 * 1024)} MB."}), 413

    service = ArchiMateImportService()

    try:
        parsed = service.parse_oef_xml(xml_content)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not parsed["elements"]:
        return jsonify({"error": "No valid elements found in the XML file."}), 400

    result = service.execute_import(parsed, strategy=strategy)

    status_code = 200 if not result["errors"] else 207  # Multi-Status if partial errors
    return jsonify(result), status_code


def _extract_xml_content(req) -> str:
    """Extract XML content from a Flask request (file upload, JSON, or raw body)."""
    # 1. File upload (multipart/form-data)
    if req.files and "file" in req.files:
        uploaded = req.files["file"]
        if uploaded.filename:
            raw = uploaded.read()
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("latin-1")

    # 2. JSON body with xml_content field
    if req.is_json and req.json and "xml_content" in req.json:
        return req.json["xml_content"]

    # 3. Raw XML body
    content_type = req.content_type or ""
    if "xml" in content_type:
        raw = req.get_data(as_text=False)
        if raw:
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("latin-1")

    return None
