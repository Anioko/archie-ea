"""
Import History API Routes - Frontend-Backend Integration

Provides API endpoints for the import history and audit trail interface.
"""

import csv
import io
import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user, login_required

from app.decorators import audit_log
from app.models.application_import_history import ApplicationImportHistory
from app.models.batch_processing import BatchJob
from app.services.batch_processing_service import BatchProcessingService
from app.services.rate_limiter import rate_limit

logger = logging.getLogger(__name__)

# Create blueprint
import_history_bp = Blueprint("import_history", __name__, url_prefix="/api/import-history")


@import_history_bp.route("", methods=["GET"])
@login_required
def get_import_history():
    """Get user's import history with batch job details."""
    try:
        # Get pagination parameters
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        status = request.args.get("status")
        date_from = request.args.get("date_from")
        date_to = request.args.get("date_to")

        service = BatchProcessingService()

        # Query batch jobs for current user with optional filters
        query = BatchJob.query.filter_by(created_by_id=current_user.id)
        if status:
            query = query.filter_by(status=status)
        query = query.order_by(BatchJob.created_at.desc())
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        # Convert to dict format
        job_dicts = []
        for job in paginated.items:
            job_dict = {
                "id": job.id,
                "job_name": job.job_name,
                "job_type": job.job_type,
                "status": job.status,
                "total_items": job.total_items,
                "processed_items": job.processed_items,
                "successful_items": job.successful_items,
                "failed_items": job.failed_items,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "progress": getattr(job, "progress_percentage", 0) or 0,
            }
            job_dicts.append(job_dict)

        return jsonify(
            {
                "success": True,
                "jobs": job_dicts,
                "total": len(job_dicts),
                "page": page,
                "per_page": per_page,
            }
        )

    except Exception as e:
        logger.error(f"Error getting import history: {e}")
        return jsonify({"success": False, "error": "Failed to get import history"}), 500


@import_history_bp.route("/<int:job_id>", methods=["GET"])
@login_required
def get_job_details(job_id):
    """Get detailed information about a specific batch job."""
    try:
        service = BatchProcessingService()
        job = service.get_job(job_id)

        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404

        # Check if user owns this job
        if job.created_by != current_user.id and not current_user.is_admin:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Get detailed job information
        job_dict = job.to_dict()

        # Get progress information
        progress = service.get_job_progress(job_id)
        job_dict["progress"] = progress.get("progress_percentage", 0)
        job_dict["status_details"] = progress.get("status_details", {})

        # Get job items
        items = service.get_job_items(job_id)
        job_dict["items"] = [item.to_dict() for item in items]

        # Get import history details if available
        if job.config_data and "import_history_id" in job.config_data:
            import_history = ApplicationImportHistory.query.get(
                job.config_data["import_history_id"]
            )
            if import_history:
                job_dict["import_history"] = import_history.to_dict()

        return jsonify({"success": True, "job": job_dict})

    except Exception as e:
        logger.error(f"Error getting job details for {job_id}: {e}")
        return jsonify({"success": False, "error": "Failed to get job details"}), 500


@import_history_bp.route("/<int:job_id>/progress", methods=["GET"])
@login_required
def get_job_progress(job_id):
    """Get real-time progress for batch job."""
    try:
        service = BatchProcessingService()
        job = service.get_job(job_id)

        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404

        # Check if user owns this job
        if job.created_by != current_user.id and not current_user.is_admin:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Get progress information
        progress = service.get_job_progress(job_id)

        return jsonify(
            {
                "success": True,
                "progress": progress.get("progress_percentage", 0),
                "status": progress.get("status", "unknown"),
                "status_details": progress.get("status_details", {}),
                "processed_items": progress.get("processed_items", 0),
                "total_items": progress.get("total_items", 0),
                "failed_items": progress.get("failed_items", 0),
                "estimated_completion": progress.get("estimated_completion"),
            }
        )

    except Exception as e:
        logger.error(f"Error getting job progress for {job_id}: {e}")
        return jsonify({"success": False, "error": "Failed to get job progress"}), 500


@import_history_bp.route("/<int:job_id>/export", methods=["POST"])
@login_required
@rate_limit(10, "1m")
@audit_log("import_job_export")
def export_job_data(job_id):
    """Export job data as CSV."""
    try:
        service = BatchProcessingService()
        job = service.get_job(job_id)

        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404

        # Check if user owns this job
        if job.created_by != current_user.id and not current_user.is_admin:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Get export format
        data = request.get_json() or {}
        export_format = data.get("format", "csv")

        if export_format != "csv":
            return jsonify({"success": False, "error": "Only CSV export is supported"}), 400

        # Get job items
        items = service.get_job_items(job_id)

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "Item ID",
                "Type",
                "Status",
                "Created At",
                "Started At",
                "Completed At",
                "Error Message",
                "Processing Time",
                "Result Data",
            ]
        )

        # Write items
        for item in items:
            writer.writerow(
                [
                    item.id,
                    item.item_type,
                    item.status,
                    item.created_at,
                    item.started_at,
                    item.completed_at,
                    item.error_message,
                    item.processing_time_seconds,
                    str(item.result_data) if item.result_data else "",
                ]
            )

        # Create file
        output.seek(0)
        csv_data = output.getvalue()

        # Create file for download
        csv_file = io.BytesIO()
        csv_file.write(csv_data.encode("utf-8"))
        csv_file.seek(0)

        filename = f"job_{job_id}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return send_file(csv_file, mimetype="text/csv", as_attachment=True, download_name=filename)

    except Exception as e:
        logger.error(f"Error exporting job data for {job_id}: {e}")
        return jsonify({"success": False, "error": "Failed to export job data"}), 500


@import_history_bp.route("/<int:job_id>/rollback", methods=["POST"])
@login_required
@rate_limit(10, "1m")
@audit_log("import_job_rollback")
def rollback_job(job_id):
    """Rollback a completed import job."""
    try:
        service = BatchProcessingService()
        job = service.get_job(job_id)

        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404

        # Check if user owns this job
        if job.created_by != current_user.id and not current_user.is_admin:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Check if job can be rolled back (within 7 days)
        if job.created_at < datetime.utcnow() - timedelta(days=7):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Rollback is only available within 7 days of import",
                    }
                ),
                400,
            )

        # Perform rollback
        result = service.rollback_job(job_id, current_user.id)

        if result["success"]:
            logger.info(f"Job {job_id} rolled back by user {current_user.id}")
            return jsonify(result)
        else:
            return jsonify({"success": False, "error": result.get("error", "Rollback failed")}), 400

    except Exception as e:
        logger.error(f"Error rolling back job {job_id}: {e}")
        return jsonify({"success": False, "error": "Failed to rollback job"}), 500


@import_history_bp.route("/<int:job_id>/retry-failed", methods=["POST"])
@login_required
@rate_limit(10, "1m")
@audit_log("import_job_retry")
def retry_failed_items(job_id):
    """Retry failed items in a batch job."""
    try:
        service = BatchProcessingService()
        job = service.get_job(job_id)

        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404

        # Check if user owns this job
        if job.created_by != current_user.id and not current_user.is_admin:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Retry failed items
        result = service.retry_failed_items(job_id, current_user.id)

        if result["success"]:
            logger.info(f"Retrying failed items for job {job_id} by user {current_user.id}")
            return jsonify(result)
        else:
            return jsonify({"success": False, "error": result.get("error", "Retry failed")}), 400

    except Exception as e:
        logger.error(f"Error retrying failed items for job {job_id}: {e}")
        return jsonify({"success": False, "error": "Failed to retry items"}), 500


@import_history_bp.route("/statistics", methods=["GET"])
@login_required
def get_import_statistics():
    """Get import statistics for the current user."""
    try:
        service = BatchProcessingService()
        stats = service.get_user_statistics(current_user.id)

        return jsonify({"success": True, "statistics": stats})

    except Exception as e:
        logger.error(f"Error getting import statistics: {e}")
        return jsonify({"success": False, "error": "Failed to get statistics"}), 500


def register_import_history_routes(app):
    """Register import history blueprint with Flask app."""
    app.register_blueprint(import_history_bp)
    logger.info("Import history API routes registered")
