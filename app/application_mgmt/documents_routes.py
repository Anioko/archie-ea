"""
Document download/delete routes for Application Management.
"""
# mass-deletion-ok — BE-179 removes 16 manual CSRF blocks replaced by global CSRFProtect

import os

from flask import current_app, flash, redirect, send_file, url_for
from flask_login import login_required

from .. import db
from ..models.miscellaneous import ApplicationDocument
from . import application_mgmt


@application_mgmt.route("/documents/<int:doc_id>/download")
@login_required
def download_document_file(doc_id):
    """Download a document file"""
    document = ApplicationDocument.query.get_or_404(doc_id)

    # Tenant isolation: verify parent app belongs to current org
    from app.middleware.tenant_files import verify_file_access
    from app.models.application_portfolio import ApplicationComponent
    parent_app = ApplicationComponent.query.get(document.application_component_id)
    if parent_app and not verify_file_access(getattr(parent_app, "organization_id", None)):
        flash("Access denied.", "danger")
        return redirect(url_for("unified_applications.application_list"))

    # Check if file exists
    if not document.file_path or not os.path.exists(document.file_path):
        flash("Document file not found on server", "danger")
        return redirect(
            url_for(
                "unified_applications.application_detail",
                id=document.application_component_id,
            )
        )

    try:
        return send_file(
            document.file_path,
            as_attachment=True,
            download_name=document.file_name,
            mimetype="application/octet-stream",
        )
    except Exception as e:
        current_app.logger.error(f"Error downloading document {doc_id}: {str(e)}")
        flash("Error downloading document. Please try again.", "danger")
        return redirect(
            url_for(
                "unified_applications.application_detail",
                id=document.application_component_id,
            )
        )


@application_mgmt.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document_file(doc_id):
    """Delete a document file"""
    document = ApplicationDocument.query.get_or_404(doc_id)
    app_id = document.application_component_id

    # csrf-ok: global CSRFProtect active

    try:
        # Delete physical file if it exists
        if document.file_path and os.path.exists(document.file_path):
            os.remove(document.file_path)
            current_app.logger.info(f"Deleted file: {document.file_path}")

        # Delete database record
        document_title = document.title
        db.session.delete(document)
        db.session.commit()

        flash(f'Document "{document_title}" deleted successfully', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting document {doc_id}: {str(e)}")
        flash("Error deleting document. Please try again.", "danger")

    return redirect(url_for("unified_applications.application_detail", id=app_id, edit="1"))
