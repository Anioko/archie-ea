"""
DEPRECATED: This file is migrated to app/modules/import_batch/.
Registration is now centralized via app.modules.import_batch.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

Batch Processing API Routes

Provides REST API endpoints for batch processing with progress tracking,
job management, and recovery operations for enterprise-scale operations.
"""

import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services.batch_processing_service import BatchJobConfig, BatchProcessingService

logger = logging.getLogger(__name__)

# Create blueprint
batch_processing_bp = Blueprint("batch_processing", __name__, url_prefix="/api/batch")

# Initialize service
batch_service = BatchProcessingService()


@batch_processing_bp.route("/jobs", methods=["POST"])
@login_required
def create_batch_job():
    """
    Create a new batch job.

    Request Body:
        {
            "job_name": "AI Import Batch Job",
            "job_type": "ai_import",
            "items": [
                {
                    "id": 123,
                    "name": "Customer Management System",
                    "type": "application",
                    "description": "Customer relationship management system"
                }
            ],
            "confidence_threshold": 0.6,
            "auto_retry": true,
            "max_retries": 3,
            "parallel_processing": false,
            "batch_size": 100,
            "checkpoint_interval": 100,
            "timeout_per_item": 300,
            "priority": 5,
            "user_id": 789
        }

    Returns:
        JSON with job creation result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        # Validate required fields
        required_fields = ["job_name", "job_type", "items"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"success": False, "error": f"Required field missing: {field}"}), 400

        # Create job configuration
        config = BatchJobConfig(
            job_name=data["job_name"],
            job_type=data["job_type"],
            items=data["items"],
            confidence_threshold=data.get("confidence_threshold", 0.6),
            auto_retry=data.get("auto_retry", True),
            max_retries=data.get("max_retries", 3),
            parallel_processing=data.get("parallel_processing", False),
            batch_size=data.get("batch_size", 100),
            checkpoint_interval=data.get("checkpoint_interval", 100),
            timeout_per_item=data.get("timeout_per_item", 300),
            priority=data.get("priority", 5),
            user_id=data.get("user_id"),
        )

        # Create batch job
        result = batch_service.create_batch_job(config)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error creating batch job: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/jobs/<int:job_id>/start", methods=["POST"])
@login_required
def start_batch_job(job_id: int):
    """
    Start execution of a batch job.

    Path Parameters:
        job_id: Batch job ID

    Returns:
        JSON with job start result
    """
    try:
        result = batch_service.start_batch_job(job_id)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error starting batch job {job_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/jobs/<int:job_id>/progress", methods=["GET"])
@login_required
def get_job_progress(job_id: int):
    """
    Get real-time progress for a batch job.

    Path Parameters:
        job_id: Batch job ID

    Returns:
        JSON with job progress information
    """
    try:
        progress = batch_service.get_job_progress(job_id)

        if not progress:
            return jsonify({"success": False, "error": "Job not found"}), 404

        return jsonify(
            {
                "success": True,
                "progress": {
                    "job_id": progress.job_id,
                    "job_name": progress.job_name,
                    "status": progress.status,
                    "total_items": progress.total_items,
                    "processed_items": progress.processed_items,
                    "successful_items": progress.successful_items,
                    "failed_items": progress.failed_items,
                    "skipped_items": progress.skipped_items,
                    "progress_percentage": progress.progress_percentage,
                    "items_per_second": progress.items_per_second,
                    "estimated_completion_time": progress.estimated_completion_time.isoformat()
                    if progress.estimated_completion_time
                    else None,
                    "current_item_name": progress.current_item_name,
                    "error_count": progress.error_count,
                    "last_error_message": progress.last_error_message,
                    "start_time": progress.start_time.isoformat(),
                    "elapsed_time": str(progress.elapsed_time),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting job progress {job_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/jobs/<int:job_id>/pause", methods=["POST"])
@login_required
def pause_batch_job(job_id: int):
    """
    Pause a running batch job.

    Path Parameters:
        job_id: Batch job ID

    Returns:
        JSON with pause result
    """
    try:
        result = batch_service.pause_batch_job(job_id)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error pausing batch job {job_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/jobs/<int:job_id>/resume", methods=["POST"])
@login_required
def resume_batch_job(job_id: int):
    """
    Resume a paused batch job.

    Path Parameters:
        job_id: Batch job ID

    Returns:
        JSON with resume result
    """
    try:
        result = batch_service.resume_batch_job(job_id)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error resuming batch job {job_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/jobs/<int:job_id>/cancel", methods=["POST"])
@login_required
def cancel_batch_job(job_id: int):
    """
    Cancel a batch job.

    Path Parameters:
        job_id: Batch job ID

    Returns:
        JSON with cancel result
    """
    try:
        result = batch_service.cancel_batch_job(job_id)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error cancelling batch job {job_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/jobs/<int:job_id>/results", methods=["GET"])
@login_required
def get_job_results(job_id: int):
    """
    Get complete results for a batch job.

    Path Parameters:
        job_id: Batch job ID

    Returns:
        JSON with job results
    """
    try:
        results = batch_service.get_job_results(job_id)

        if not results:
            return jsonify({"success": False, "error": "Job not found"}), 404

        return jsonify(
            {
                "success": True,
                "results": {
                    "job_id": results.job_id,
                    "job_name": results.job_name,
                    "status": results.status,
                    "total_items": results.total_items,
                    "processed_items": results.processed_items,
                    "successful_items": results.successful_items,
                    "failed_items": results.failed_items,
                    "skipped_items": results.skipped_items,
                    "total_processing_time": results.total_processing_time,
                    "average_items_per_second": results.average_items_per_second,
                    "success_rate": results.success_rate,
                    "error_count": results.error_count,
                    "checkpoints_created": results.checkpoints_created,
                    "recovery_attempts": results.recovery_attempts,
                    "results": results.results,
                    "errors": results.errors,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting job results {job_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/jobs", methods=["GET"])
@login_required
def list_batch_jobs():
    """
    List batch jobs with optional filtering.

    Query Parameters:
        job_type (str): Optional job type filter
        status (str): Optional status filter
        user_id (int): Optional user ID filter
        limit (int): Maximum results (default: 50)

    Returns:
        JSON with job list
    """
    try:
        from app.models.batch_processing import BatchJob, BatchJobStatus, BatchJobType

        job_type = request.args.get("job_type")
        status = request.args.get("status")
        user_id = request.args.get("user_id", type=int)
        limit = min(request.args.get("limit", 50, type=int), 100)

        query = BatchJob.query

        if job_type:
            query = query.filter(BatchJob.job_type == BatchJobType(job_type))

        if status:
            query = query.filter(BatchJob.status == BatchJobStatus(status))

        if user_id:
            query = query.filter(BatchJob.created_by_id == user_id)

        jobs = query.order_by(BatchJob.created_at.desc()).limit(limit).all()

        return jsonify(
            {"success": True, "jobs": [job.to_dict() for job in jobs], "total_jobs": len(jobs)}
        )

    except Exception as e:
        logger.error(f"Error listing batch jobs: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/statistics", methods=["GET"])
@login_required
def get_batch_statistics():
    """
    Get batch processing statistics with filtering options.

    Query Parameters:
        job_type (str): Optional job type filter
        date_from (str): Optional start date filter (YYYY-MM-DD)
        date_to (str): Optional end date filter (YYYY-MM-DD)

    Returns:
        JSON with statistics
    """
    try:
        job_type = request.args.get("job_type")
        date_from_str = request.args.get("date_from")
        date_to_str = request.args.get("date_to")

        date_from = None
        date_to = None

        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
            except ValueError:
                return (
                    jsonify(
                        {"success": False, "error": "Invalid date_from format, use YYYY-MM-DD"}
                    ),
                    400,
                )

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, "%Y-%m-%d")
            except ValueError:
                return (
                    jsonify({"success": False, "error": "Invalid date_to format, use YYYY-MM-DD"}),
                    400,
                )

        statistics = batch_service.get_job_statistics(job_type, date_from, date_to)

        if "error" in statistics:
            return jsonify({"success": False, "error": statistics["error"]}), 500

        return jsonify({"success": True, "statistics": statistics})

    except Exception as e:
        logger.error(f"Error getting batch statistics: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/job-types", methods=["GET"])
@login_required
def get_job_types():
    """
    Get available job types.

    Returns:
        JSON with job types
    """
    try:
        from app.models.batch_processing import BatchJobType

        job_types = [
            {
                "value": job_type.value,
                "name": job_type.value.replace("_", " ").title(),
                "description": f'{job_type.value.replace("_", " ").title()} batch processing',
            }
            for job_type in BatchJobType
        ]

        return jsonify({"success": True, "job_types": job_types})

    except Exception as e:
        logger.error(f"Error getting job types: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/jobs/<int:job_id>/checkpoints", methods=["GET"])
@login_required
def get_job_checkpoints(job_id: int):
    """
    Get checkpoints for a batch job.

    Path Parameters:
        job_id: Batch job ID

    Returns:
        JSON with checkpoints
    """
    try:
        from app.models.batch_processing import BatchJobCheckpoint

        checkpoints = (
            BatchJobCheckpoint.query.filter_by(batch_job_id=job_id)
            .order_by(BatchJobCheckpoint.created_at.desc())
            .all()
        )

        return jsonify(
            {
                "success": True,
                "checkpoints": [checkpoint.to_dict() for checkpoint in checkpoints],
                "total_checkpoints": len(checkpoints),
            }
        )

    except Exception as e:
        logger.error(f"Error getting job checkpoints {job_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/jobs/<int:job_id>/errors", methods=["GET"])
@login_required
def get_job_errors(job_id: int):
    """
    Get errors for a batch job.

    Path Parameters:
        job_id: Batch job ID

    Query Parameters:
        severity (str): Optional severity filter
        category (str): Optional category filter

    Returns:
        JSON with errors
    """
    try:
        from app.models.batch_processing import BatchJobError

        severity = request.args.get("severity")
        category = request.args.get("category")

        query = BatchJobError.query.filter_by(batch_job_id=job_id)

        if severity:
            query = query.filter(BatchJobError.severity == severity)

        if category:
            query = query.filter(BatchJobError.category == category)

        errors = query.order_by(BatchJobError.occurred_at.desc()).all()

        return jsonify(
            {
                "success": True,
                "errors": [error.to_dict() for error in errors],
                "total_errors": len(errors),
            }
        )

    except Exception as e:
        logger.error(f"Error getting job errors {job_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@batch_processing_bp.route("/jobs/<int:job_id>/items", methods=["GET"])
@login_required
def get_job_items(job_id: int):
    """
    Get items for a batch job.

    Path Parameters:
        job_id: Batch job ID

    Query Parameters:
        status (str): Optional status filter
        limit (int): Maximum results (default: 100)

    Returns:
        JSON with job items
    """
    try:
        from app.models.batch_processing import BatchJobItem

        status = request.args.get("status")
        limit = min(request.args.get("limit", 100, type=int), 500)

        query = BatchJobItem.query.filter_by(batch_job_id=job_id)

        if status:
            query = query.filter(BatchJobItem.status == status)

        items = query.order_by(BatchJobItem.item_sequence).limit(limit).all()

        return jsonify(
            {
                "success": True,
                "items": [item.to_dict() for item in items],
                "total_items": len(items),
            }
        )

    except Exception as e:
        logger.error(f"Error getting job items {job_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


def register_batch_processing_routes(app):
    """Register batch processing blueprint with Flask app."""
    app.register_blueprint(batch_processing_bp)
    logger.info("Batch processing API routes registered")
