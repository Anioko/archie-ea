"""ARB Document Attachment Routes.

Provides file upload and retrieval for ARB governance documents:
  - POST /arb/api/change-requests/<id>/documents  — attach file to change request
  - GET  /arb/api/change-requests/<id>/documents  — list attached files
  - POST /arb/api/review-items/<id>/documents     — attach file to review item
  - GET  /arb/api/review-items/<id>/documents     — list attached files
  - GET  /arb/api/documents/<id>/download         — download a file

Registering on the existing arb_bp (url_prefix=/arb) via bottom-import in arb_routes.py.
"""

import os
import uuid
from datetime import datetime

from flask import current_app, jsonify, request, send_file
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from app.modules.architecture.routes.arb_routes import arb_bp

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "ppt", "pptx",
    "xls", "xlsx", "csv",
    "txt", "md",
    "png", "jpg", "jpeg", "gif", "svg",
    "zip",
}
MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB
UPLOAD_SUBDIR = os.path.join("uploads", "arb_documents")
VALID_DOC_TYPES = {"supporting", "evidence", "decision", "minutes"}


def _upload_dir():
    base = current_app.root_path
    path = os.path.join(base, UPLOAD_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_file(file_storage):
    """Validate, save, and return metadata dict. Raises ValueError on bad input."""
    if not file_storage or not file_storage.filename:
        raise ValueError("No file provided")
    if not _allowed(file_storage.filename):
        raise ValueError(f"File type not allowed: {file_storage.filename}")

    # Read content to check size
    content = file_storage.read()
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(f"File exceeds 50 MB limit")
    file_storage.seek(0)

    original_name = file_storage.filename
    ext = original_name.rsplit(".", 1)[1].lower() if "." in original_name else ""
    stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    dest = os.path.join(_upload_dir(), stored_name)

    file_storage.save(dest)

    return {
        "original_name": original_name,
        "stored_name": stored_name,
        "file_path": os.path.join(UPLOAD_SUBDIR, stored_name),
        "file_size": len(content),
        "mime_type": file_storage.content_type or "application/octet-stream",
    }


def _create_document_record(file_meta, doc_type, change_request_id=None, review_item_id=None):
    from app.models.architecture_review_board import ARBDocument
    doc = ARBDocument(
        change_request_id=change_request_id,
        review_item_id=review_item_id,
        original_name=file_meta["original_name"],
        stored_name=file_meta["stored_name"],
        file_path=file_meta["file_path"],
        file_size=file_meta["file_size"],
        mime_type=file_meta["mime_type"],
        document_type=doc_type if doc_type in VALID_DOC_TYPES else "supporting",
        uploaded_by_id=current_user.id if current_user.is_authenticated else None,
        uploaded_at=datetime.utcnow(),
    )
    db.session.add(doc)
    db.session.commit()
    return doc


# ---------------------------------------------------------------------------
# Change Request document endpoints
# ---------------------------------------------------------------------------

@arb_bp.route("/api/change-requests/<int:cr_id>/documents", methods=["POST"])
@login_required
def upload_change_request_document(cr_id):
    """Attach a file to an ARB change request (ArchitectureChangeRequest)."""
    from app.models.architecture_decision import ArchitectureChangeRequest
    ArchitectureChangeRequest.query.get_or_404(cr_id)

    file_storage = request.files.get("file")
    doc_type = request.form.get("document_type", "supporting")

    try:
        file_meta = _save_file(file_storage)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    doc = _create_document_record(file_meta, doc_type, change_request_id=cr_id)
    return jsonify({"success": True, "document": doc.to_dict()}), 201


@arb_bp.route("/api/change-requests/<int:cr_id>/documents", methods=["GET"])
@login_required
def list_change_request_documents(cr_id):
    """List documents attached to an ARB change request."""
    from app.models.architecture_decision import ArchitectureChangeRequest
    from app.models.architecture_review_board import ARBDocument
    ArchitectureChangeRequest.query.get_or_404(cr_id)
    docs = ARBDocument.query.filter_by(change_request_id=cr_id)\
        .order_by(ARBDocument.uploaded_at.desc()).all()
    return jsonify({"success": True, "documents": [d.to_dict() for d in docs]})


# ---------------------------------------------------------------------------
# Review Item document endpoints
# ---------------------------------------------------------------------------

@arb_bp.route("/api/review-items/<int:ri_id>/documents", methods=["POST"])
@login_required
def upload_review_item_document(ri_id):
    """Attach a file to an ARB review item."""
    from app.models.architecture_review_board import ARBReviewItem
    ARBReviewItem.query.get_or_404(ri_id)

    file_storage = request.files.get("file")
    doc_type = request.form.get("document_type", "supporting")

    try:
        file_meta = _save_file(file_storage)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    doc = _create_document_record(file_meta, doc_type, review_item_id=ri_id)
    return jsonify({"success": True, "document": doc.to_dict()}), 201


@arb_bp.route("/api/review-items/<int:ri_id>/documents", methods=["GET"])
@login_required
def list_review_item_documents(ri_id):
    """List documents attached to an ARB review item."""
    from app.models.architecture_review_board import ARBReviewItem, ARBDocument
    ARBReviewItem.query.get_or_404(ri_id)
    docs = ARBDocument.query.filter_by(review_item_id=ri_id)\
        .order_by(ARBDocument.uploaded_at.desc()).all()
    return jsonify({"success": True, "documents": [d.to_dict() for d in docs]})


# ---------------------------------------------------------------------------
# Download endpoint (shared)
# ---------------------------------------------------------------------------

@arb_bp.route("/api/documents/<int:doc_id>/download", methods=["GET"])
@login_required
def download_arb_document(doc_id):
    """Download an ARB document by ID."""
    from app.models.architecture_review_board import ARBDocument
    doc = ARBDocument.query.get_or_404(doc_id)
    full_path = os.path.join(current_app.root_path, doc.file_path)
    if not os.path.exists(full_path):
        return jsonify({"error": "File not found on disk"}), 404
    return send_file(full_path, download_name=doc.original_name, as_attachment=True)
