"""
-> app.modules.import_batch.services.batch_service

Batch Processing Service with Progress & Recovery

Provides comprehensive batch processing capabilities with real-time progress tracking,
intelligent error recovery, checkpoint management, and transaction rollback for enterprise-scale operations.

Features:
- Multi-type batch job processing (AI import, capability mapping, etc.)
- Real-time progress tracking with performance metrics
- Intelligent error recovery with retry logic
- Checkpoint management for job resumption
- Transaction rollback and data consistency
- Performance monitoring and statistics
"""

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app import db

logger = logging.getLogger(__name__)


@dataclass
class BatchJobConfig:
    """Configuration for batch job execution."""

    job_name: str
    job_type: str
    items: List[Dict[str, Any]]
    confidence_threshold: float = 0.6
    auto_retry: bool = True
    max_retries: int = 3
    parallel_processing: bool = False
    batch_size: int = 100
    checkpoint_interval: int = 100  # Create checkpoint every N items
    timeout_per_item: int = 300  # seconds
    priority: int = 5  # 1 - 10, lower is higher priority
    user_id: Optional[int] = None

    def __post_init__(self):
        """Validate configuration parameters after initialization."""
        # Validate confidence_threshold
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be between 0.0 and 1.0, got {self.confidence_threshold}"
            )

        # Validate max_retries
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {self.max_retries}")

        # Validate batch_size
        if self.batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {self.batch_size}")

        # Validate checkpoint_interval
        if self.checkpoint_interval <= 0:
            raise ValueError(
                f"checkpoint_interval must be positive, got {self.checkpoint_interval}"
            )

        # Validate timeout_per_item
        if self.timeout_per_item <= 0:
            raise ValueError(f"timeout_per_item must be positive, got {self.timeout_per_item}")

        # Validate priority
        if not 1 <= self.priority <= 10:
            raise ValueError(f"priority must be between 1 and 10, got {self.priority}")

        # Validate items
        if not isinstance(self.items, list):
            raise ValueError(f"items must be a list, got {type(self.items)}")

        # Allow empty items for edge cases (but validate structure if not empty)
        if len(self.items) > 0:
            # Validate each item has required structure
            for i, item in enumerate(self.items):
                if not isinstance(item, dict):
                    raise ValueError(f"item at index {i} must be a dict, got {type(item)}")
                if "data" not in item:
                    raise ValueError(f"item at index {i} must have 'data' key")


@dataclass
class BatchJobProgress:
    """Real-time progress tracking for batch jobs."""

    job_id: int
    job_name: str
    status: str
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    skipped_items: int
    progress_percentage: float
    items_per_second: float
    estimated_completion_time: Optional[datetime]
    current_item_name: str
    error_count: int
    last_error_message: Optional[str]
    start_time: datetime
    elapsed_time: timedelta


@dataclass
class BatchJobResult:
    """Complete result of batch job execution."""

    job_id: int
    job_name: str
    status: str
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    skipped_items: int
    total_processing_time: float
    average_items_per_second: float
    success_rate: float
    error_count: int
    checkpoints_created: int
    recovery_attempts: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]


class BatchProcessingService:
    """
    Comprehensive batch processing service with progress tracking and recovery.

    Supports multiple job types with intelligent error handling, checkpoint management,
    and real-time progress monitoring for enterprise-scale operations.
    """

    def __init__(self):
        """Initialize the batch processing service."""
        self._init_job_processors()
        self._init_error_handlers()
        self._init_recovery_strategies()
        self._active_jobs = {}  # Thread-safe job tracking
        self._job_lock = threading.Lock()

    def _init_job_processors(self):
        """Initialize job type processors."""
        self.job_processors = {
            "ai_import": self._process_ai_import_item,
            "capability_mapping": self._process_capability_mapping_item,
            "apqc_classification": self._process_apqc_classification_item,
            "archimate_generation": self._process_archimate_generation_item,
            "vendor_analysis": self._process_vendor_analysis_item,
            "taxonomy_validation": self._process_taxonomy_validation_item,
            "bulk_update": self._process_bulk_update_item,
        }

    def _init_error_handlers(self):
        """Initialize error handling strategies."""
        self.error_handlers = {
            "validation_error": self._handle_validation_error,
            "processing_error": self._handle_processing_error,
            "system_error": self._handle_system_error,
            "timeout_error": self._handle_timeout_error,
            "data_error": self._handle_data_error,
            "resource_error": self._handle_resource_error,
        }

    def _init_recovery_strategies(self):
        """Initialize recovery strategies for different error types."""
        self.recovery_strategies = {
            "retry": self._retry_item_processing,
            "skip": self._skip_item_processing,
            "manual_intervention": self._request_manual_intervention,
            "abort": self._abort_job_processing,
            "recover_from_checkpoint": self._recover_from_checkpoint,
        }

    def create_batch_job(self, config: BatchJobConfig) -> Dict[str, Any]:
        """
        Create a new batch job with configuration.

        Args:
            config: Batch job configuration

        Returns:
            Dictionary with job creation result
        """
        try:
            from app.models.batch_processing import (
                BatchJob,
                BatchJobItem,
                BatchJobStatus,
                BatchJobType,
            )

            # Validate configuration
            if not config.items:
                return {"success": False, "error": "No items provided for batch processing"}

            # Create batch job
            job = BatchJob(
                job_name=config.job_name,
                job_type=BatchJobType(config.job_type),
                status=BatchJobStatus.PENDING,
                total_items=len(config.items),
                job_parameters=json.dumps(
                    {
                        "confidence_threshold": config.confidence_threshold,
                        "auto_retry": config.auto_retry,
                        "max_retries": config.max_retries,
                        "parallel_processing": config.parallel_processing,
                        "batch_size": config.batch_size,
                        "checkpoint_interval": config.checkpoint_interval,
                        "timeout_per_item": config.timeout_per_item,
                    }
                ),
                confidence_threshold=config.confidence_threshold,
                auto_retry=config.auto_retry,
                max_retries=config.max_retries,
                parallel_processing=config.parallel_processing,
                batch_size=config.batch_size,
                priority=config.priority,
                created_by_id=config.user_id,
            )

            db.session.add(job)
            db.session.flush()  # Get job ID

            # Create batch job items
            for i, item_data in enumerate(config.items):
                job_item = BatchJobItem(
                    batch_job_id=job.id,
                    item_sequence=i + 1,
                    item_type=item_data.get("type", "unknown"),
                    item_id=item_data.get("id"),
                    item_name=item_data.get("name", f"Item {i + 1}"),
                    item_data=json.dumps(item_data),
                    max_attempts=config.max_retries,
                )
                db.session.add(job_item)

            db.session.commit()

            # Create initial checkpoint
            self._create_checkpoint(
                job.id,
                "initial",
                "manual",
                {"total_items": len(config.items), "job_config": config.__dict__},
            )

            return {
                "success": True,
                "job_id": job.id,
                "job_name": job.job_name,
                "job_type": job.job_type.value,
                "total_items": job.total_items,
                "status": job.status.value,
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating batch job: {e}")
            return {"success": False, "error": str(e)}

    def start_batch_job(self, job_id: int) -> Dict[str, Any]:
        """
        Start execution of a batch job.

        Args:
            job_id: Batch job ID

        Returns:
            Dictionary with job start result
        """
        try:
            from app.models.batch_processing import BatchJob, BatchJobStatus

            job = BatchJob.query.get(job_id)
            if not job:
                return {"success": False, "error": "Batch job not found"}

            if job.status != BatchJobStatus.PENDING:
                return {
                    "success": False,
                    "error": f"Job cannot be started, current status: {job.status.value}",
                }

            # Update job status
            job.status = BatchJobStatus.RUNNING
            job.started_at = datetime.utcnow()
            db.session.commit()

            # Start job processing in background thread
            thread = threading.Thread(
                target=self._execute_batch_job, args=(job_id,), name=f"BatchJob-{job_id}"
            )
            thread.daemon = True
            thread.start()

            # Track active job
            with self._job_lock:
                self._active_jobs[job_id] = {
                    "thread": thread,
                    "start_time": datetime.utcnow(),
                    "status": "running",
                }

            return {
                "success": True,
                "job_id": job_id,
                "job_name": job.job_name,
                "status": job.status.value,
                "started_at": job.started_at.isoformat(),
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error starting batch job {job_id}: {e}")
            return {"success": False, "error": str(e)}

    def _execute_batch_job(self, job_id: int):
        """
        Execute batch job processing with progress tracking and recovery.

        Args:
            job_id: Batch job ID
        """
        try:
            from app.models.batch_processing import BatchJob, BatchJobItem, BatchJobStatus

            job = BatchJob.query.get(job_id)
            if not job:
                logger.error(f"Batch job {job_id} not found")
                return

            logger.info(f"Starting batch job execution: {job.job_name} ({job.job_type.value})")

            start_time = datetime.utcnow()
            processed_items = 0
            successful_items = 0
            failed_items = 0
            skipped_items = 0
            error_count = 0

            # Get job items ordered by sequence
            items = (
                BatchJobItem.query.filter_by(batch_job_id=job_id)
                .order_by(BatchJobItem.item_sequence)
                .all()
            )

            # Get job processor
            processor = self.job_processors.get(job.job_type.value)
            if not processor:
                raise ValueError(f"No processor found for job type: {job.job_type.value}")

            # Process items
            for i, item in enumerate(items):
                try:
                    # Check if job should continue
                    if self._should_pause_job(job_id):
                        job.status = BatchJobStatus.PAUSED
                        db.session.commit()
                        logger.info(f"Job {job_id} paused")
                        break

                    # Update current item status
                    item.status = "processing"
                    item.processing_start_time = datetime.utcnow()
                    db.session.commit()

                    # Process item
                    result = self._process_item_with_retry(job, item, processor)

                    # Update item status based on result
                    if result["success"]:
                        item.status = "completed"
                        item.processing_end_time = datetime.utcnow()
                        item.processing_duration = (
                            item.processing_end_time - item.processing_start_time
                        ).total_seconds()
                        item.result_data = json.dumps(result.get("result", {}))
                        item.confidence_score = result.get("confidence_score", 0.0)
                        successful_items += 1
                    else:
                        item.status = "failed"
                        item.error_message = result.get("error", "Unknown error")
                        item.error_type = result.get("error_type", "processing_error")
                        item.error_data = json.dumps(result.get("error_data", {}))
                        failed_items += 1
                        error_count += 1

                    processed_items += 1

                    # Update job progress
                    self._update_job_progress(
                        job, processed_items, successful_items, failed_items, skipped_items
                    )

                    # Create checkpoint at intervals
                    if (i + 1) % job.checkpoint_interval == 0:
                        self._create_checkpoint(
                            job_id,
                            f"progress_{i + 1}",
                            "progress",
                            {
                                "processed_items": processed_items,
                                "successful_items": successful_items,
                                "failed_items": failed_items,
                                "last_item_sequence": item.item_sequence,
                            },
                        )

                    db.session.commit()

                except Exception as e:
                    logger.error(f"Error processing item {item.id}: {e}")
                    item.status = "failed"
                    item.error_message = str(e)
                    item.error_type = "system_error"
                    failed_items += 1
                    error_count += 1
                    db.session.commit()

            # Finalize job
            end_time = datetime.utcnow()
            total_processing_time = (end_time - start_time).total_seconds()

            job.status = BatchJobStatus.COMPLETED
            job.completed_at = end_time
            job.actual_completion_time = end_time
            job.total_processing_time = total_processing_time
            job.processed_items = processed_items
            job.successful_items = successful_items
            job.failed_items = failed_items
            job.skipped_items = skipped_items
            job.error_count = error_count

            if processed_items > 0:
                job.items_per_second = processed_items / total_processing_time
                job.average_processing_time = total_processing_time / processed_items

            db.session.commit()

            # Create final checkpoint
            self._create_checkpoint(
                job_id,
                "final",
                "milestone",
                {
                    "total_processing_time": total_processing_time,
                    "final_status": "completed",
                    "items_processed": processed_items,
                },
            )

            logger.info(
                f"Batch job {job_id} completed: {successful_items}/{processed_items} successful"
            )

        except Exception as e:
            logger.error(f"Error executing batch job {job_id}: {e}")
            self._handle_job_failure(job_id, str(e))
        finally:
            # Clean up active job tracking
            with self._job_lock:
                self._active_jobs.pop(job_id, None)

    def _process_item_with_retry(self, job, item, processor: Callable) -> Dict[str, Any]:
        """
        Process a single item with retry logic.

        Args:
            job: Batch job instance
            item: Batch job item instance
            processor: Processing function

        Returns:
            Dictionary with processing result
        """
        max_attempts = item.max_attempts or job.max_retries or 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                # Load item data
                item_data = json.loads(item.item_data)

                # Process item
                result = processor(item_data, job.job_parameters)

                # Check confidence threshold
                confidence = result.get("confidence_score", 0.0)
                if confidence < job.confidence_threshold:
                    return {
                        "success": False,
                        "error": f"Confidence score {confidence} below threshold {job.confidence_threshold}",
                        "error_type": "validation_error",
                        "confidence_score": confidence,
                    }

                return {
                    "success": True,
                    "result": result,
                    "confidence_score": confidence,
                    "attempt": attempt + 1,
                }

            except Exception as e:
                last_error = e
                logger.warning(f"Item {item.id} processing attempt {attempt + 1} failed: {e}")

                if attempt < max_attempts - 1:
                    # Update retry count
                    item.processing_attempts = attempt + 1
                    item.retry_after = datetime.utcnow() + timedelta(seconds=60 * (attempt + 1))
                    db.session.commit()

                    # Wait before retry
                    time.sleep(60 * (attempt + 1))

        # All attempts failed
        return {
            "success": False,
            "error": str(last_error),
            "error_type": "processing_error",
            "attempts": max_attempts,
            "last_error": str(last_error),
        }

    def _update_job_progress(
        self,
        job,
        processed_items: int,
        successful_items: int,
        failed_items: int,
        skipped_items: int,
    ):
        """Update job progress metrics."""
        job.processed_items = processed_items
        job.successful_items = successful_items
        job.failed_items = failed_items
        job.skipped_items = skipped_items

        if job.total_items > 0:
            job.progress_percentage = (processed_items / job.total_items) * 100

            # Estimate completion time
            if processed_items > 0:
                elapsed_time = (datetime.utcnow() - job.started_at).total_seconds()
                items_per_second = processed_items / elapsed_time
                remaining_items = job.total_items - processed_items
                estimated_remaining_seconds = (
                    remaining_items / items_per_second if items_per_second > 0 else 0
                )
                job.estimated_completion_time = datetime.utcnow() + timedelta(
                    seconds=estimated_remaining_seconds
                )
                job.items_per_second = items_per_second

    def _create_checkpoint(
        self, job_id: int, checkpoint_name: str, checkpoint_type: str, data: Dict[str, Any]
    ):
        """Create a checkpoint for job recovery."""
        try:
            from app.models.batch_processing import BatchJob, BatchJobCheckpoint

            job = BatchJob.query.get(job_id)
            if not job:
                return

            checkpoint = BatchJobCheckpoint(
                batch_job_id=job_id,
                checkpoint_name=checkpoint_name,
                checkpoint_type=checkpoint_type,
                processed_items_count=job.processed_items,
                successful_items_count=job.successful_items,
                failed_items_count=job.failed_items,
                checkpoint_data=json.dumps(data),
                last_processed_item_id=data.get("last_item_id"),
                last_successful_item_sequence=data.get("last_item_sequence"),
                created_by="system",
            )

            db.session.add(checkpoint)
            db.session.commit()

            logger.info(f"Created checkpoint {checkpoint_name} for job {job_id}")

        except Exception as e:
            logger.error(f"Error creating checkpoint for job {job_id}: {e}")

    def _should_pause_job(self, job_id: int) -> bool:
        """Check if job should be paused based on system conditions."""
        # Check system resources
        # This could be enhanced with actual system monitoring
        return False

    def _handle_job_failure(self, job_id: int, error_message: str):
        """Handle job failure with recovery attempt."""
        try:
            from app.models.batch_processing import BatchJob, BatchJobError, BatchJobStatus

            job = BatchJob.query.get(job_id)
            if not job:
                return

            job.status = BatchJobStatus.FAILED
            job.last_error_message = error_message
            job.last_error_time = datetime.utcnow()
            job.recovery_attempts += 1

            # Create error record
            error = BatchJobError(
                batch_job_id=job_id,
                error_type="system_error",
                error_message=error_message,
                severity="high",
                category="system_error",
                can_retry=job.recovery_attempts < job.max_retries,
                recovery_action="retry"
                if job.recovery_attempts < job.max_retries
                else "manual_intervention",
            )

            db.session.add(error)
            db.session.commit()

            logger.error(f"Job {job_id} failed: {error_message}")

        except Exception as e:
            logger.error(f"Error handling job failure for {job_id}: {e}")

    def get_job_progress(self, job_id: int) -> Optional[BatchJobProgress]:
        """
        Get real-time progress for a batch job.

        Args:
            job_id: Batch job ID

        Returns:
            BatchJobProgress object or None if job not found
        """
        try:
            from app.models.batch_processing import BatchJob, BatchJobItem

            job = BatchJob.query.get(job_id)
            if not job:
                return None

            # Get current processing item
            current_item = BatchJobItem.query.filter_by(
                batch_job_id=job_id, status="processing"
            ).first()

            elapsed_time = datetime.utcnow() - job.started_at if job.started_at else timedelta(0)

            return BatchJobProgress(
                job_id=job.id,
                job_name=job.job_name,
                status=job.status.value,
                total_items=job.total_items,
                processed_items=job.processed_items,
                successful_items=job.successful_items,
                failed_items=job.failed_items,
                skipped_items=job.skipped_items,
                progress_percentage=float(job.progress_percentage),
                items_per_second=float(job.items_per_second) if job.items_per_second else 0.0,
                estimated_completion_time=job.estimated_completion_time,
                current_item_name=current_item.item_name if current_item else "None",
                error_count=job.error_count,
                last_error_message=job.last_error_message,
                start_time=job.started_at,
                elapsed_time=elapsed_time,
            )

        except Exception as e:
            logger.error(f"Error getting job progress for {job_id}: {e}")
            return None

    def pause_batch_job(self, job_id: int) -> Dict[str, Any]:
        """Pause a running batch job."""
        try:
            from app.models.batch_processing import BatchJob, BatchJobStatus

            job = BatchJob.query.get(job_id)
            if not job:
                return {"success": False, "error": "Batch job not found"}

            if job.status != BatchJobStatus.RUNNING:
                return {
                    "success": False,
                    "error": f"Job cannot be paused, current status: {job.status.value}",
                }

            job.status = BatchJobStatus.PAUSED
            db.session.commit()

            # Create checkpoint
            self._create_checkpoint(
                job_id,
                "paused",
                "manual",
                {
                    "paused_at": datetime.utcnow().isoformat(),
                    "processed_items": job.processed_items,
                },
            )

            return {"success": True, "job_id": job_id, "status": job.status.value}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error pausing batch job {job_id}: {e}")
            return {"success": False, "error": str(e)}

    def resume_batch_job(self, job_id: int) -> Dict[str, Any]:
        """Resume a paused batch job."""
        try:
            from app.models.batch_processing import BatchJob, BatchJobStatus

            job = BatchJob.query.get(job_id)
            if not job:
                return {"success": False, "error": "Batch job not found"}

            if job.status != BatchJobStatus.PAUSED:
                return {
                    "success": False,
                    "error": f"Job cannot be resumed, current status: {job.status.value}",
                }

            job.status = BatchJobStatus.RUNNING
            db.session.commit()

            # Resume processing in background thread
            thread = threading.Thread(
                target=self._execute_batch_job, args=(job_id,), name=f"BatchJob-{job_id}-Resume"
            )
            thread.daemon = True
            thread.start()

            return {"success": True, "job_id": job_id, "status": job.status.value}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error resuming batch job {job_id}: {e}")
            return {"success": False, "error": str(e)}

    def cancel_batch_job(self, job_id: int) -> Dict[str, Any]:
        """Cancel a batch job."""
        try:
            from app.models.batch_processing import BatchJob, BatchJobStatus

            job = BatchJob.query.get(job_id)
            if not job:
                return {"success": False, "error": "Batch job not found"}

            if job.status in [
                BatchJobStatus.COMPLETED,
                BatchJobStatus.FAILED,
                BatchJobStatus.CANCELLED,
            ]:
                return {
                    "success": False,
                    "error": f"Job cannot be cancelled, current status: {job.status.value}",
                }

            job.status = BatchJobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            db.session.commit()

            # Create checkpoint
            self._create_checkpoint(
                job_id,
                "cancelled",
                "manual",
                {
                    "cancelled_at": datetime.utcnow().isoformat(),
                    "processed_items": job.processed_items,
                },
            )

            return {"success": True, "job_id": job_id, "status": job.status.value}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error cancelling batch job {job_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_job_results(self, job_id: int) -> Optional[BatchJobResult]:
        """
        Get complete results for a batch job.

        Args:
            job_id: Batch job ID

        Returns:
            BatchJobResult object or None if job not found
        """
        try:
            from app.models.batch_processing import BatchJob, BatchJobError, BatchJobItem

            job = BatchJob.query.get(job_id)
            if not job:
                return None

            # Get items with results
            items = BatchJobItem.query.filter_by(batch_job_id=job_id).all()
            results = []
            errors = []

            for item in items:
                if item.result_data:
                    results.append(
                        {
                            "item_sequence": item.item_sequence,
                            "item_name": item.item_name,
                            "status": item.status,
                            "confidence_score": item.confidence_score,
                            "processing_duration": item.processing_duration,
                            "result": json.loads(item.result_data),
                        }
                    )

                if item.error_message:
                    errors.append(
                        {
                            "item_sequence": item.item_sequence,
                            "item_name": item.item_name,
                            "error_message": item.error_message,
                            "error_type": item.error_type,
                            "processing_attempts": item.processing_attempts,
                        }
                    )

            # Get job errors
            job_errors = BatchJobError.query.filter_by(batch_job_id=job_id).all()
            for error in job_errors:
                errors.append(
                    {
                        "error_id": error.id,
                        "error_type": error.error_type,
                        "error_message": error.error_message,
                        "severity": error.severity,
                        "recovery_action": error.recovery_action,
                        "occurred_at": error.occurred_at.isoformat(),
                    }
                )

            # Get checkpoints count
            from app.models.batch_processing import BatchJobCheckpoint

            checkpoints_count = BatchJobCheckpoint.query.filter_by(batch_job_id=job_id).count()

            success_rate = (
                (job.successful_items / job.processed_items * 100)
                if job.processed_items > 0
                else 0.0
            )

            return BatchJobResult(
                job_id=job.id,
                job_name=job.job_name,
                status=job.status.value,
                total_items=job.total_items,
                processed_items=job.processed_items,
                successful_items=job.successful_items,
                failed_items=job.failed_items,
                skipped_items=job.skipped_items,
                total_processing_time=float(job.total_processing_time)
                if job.total_processing_time
                else 0.0,
                average_items_per_second=float(job.items_per_second)
                if job.items_per_second
                else 0.0,
                success_rate=success_rate,
                error_count=job.error_count,
                checkpoints_created=checkpoints_count,
                recovery_attempts=job.recovery_attempts,
                results=results,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"Error getting job results for {job_id}: {e}")
            return None

    def get_job_statistics(
        self, job_type: str = None, date_from: datetime = None, date_to: datetime = None
    ) -> Dict[str, Any]:
        """
        Get batch job statistics with filtering options.

        Args:
            job_type: Optional job type filter
            date_from: Optional start date filter
            date_to: Optional end date filter

        Returns:
            Dictionary with job statistics
        """
        try:
            from app.models.batch_processing import BatchJob, BatchJobStatus, BatchJobType

            query = BatchJob.query

            if job_type:
                query = query.filter(BatchJob.job_type == BatchJobType(job_type))

            if date_from:
                query = query.filter(BatchJob.created_at >= date_from)

            if date_to:
                query = query.filter(BatchJob.created_at <= date_to)

            jobs = query.all()

            if not jobs:
                return {
                    "total_jobs": 0,
                    "completed_jobs": 0,
                    "failed_jobs": 0,
                    "cancelled_jobs": 0,
                    "running_jobs": 0,
                    "total_items": 0,
                    "processed_items": 0,
                    "successful_items": 0,
                    "failed_items": 0,
                    "average_items_per_second": 0.0,
                    "average_processing_time": 0.0,
                }

            # Calculate statistics
            total_jobs = len(jobs)
            completed_jobs = len([j for j in jobs if j.status == BatchJobStatus.COMPLETED])
            failed_jobs = len([j for j in jobs if j.status == BatchJobStatus.FAILED])
            cancelled_jobs = len([j for j in jobs if j.status == BatchJobStatus.CANCELLED])
            running_jobs = len([j for j in jobs if j.status == BatchJobStatus.RUNNING])

            total_items = sum(j.total_items for j in jobs)
            processed_items = sum(j.processed_items for j in jobs)
            successful_items = sum(j.successful_items for j in jobs)
            failed_items = sum(j.failed_items for j in jobs)

            # Calculate averages
            avg_items_per_second = (
                sum(j.items_per_second for j in jobs if j.items_per_second) / len(jobs)
                if jobs
                else 0.0
            )
            avg_processing_time = (
                sum(j.total_processing_time for j in jobs if j.total_processing_time) / len(jobs)
                if jobs
                else 0.0
            )

            return {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "cancelled_jobs": cancelled_jobs,
                "running_jobs": running_jobs,
                "total_items": total_items,
                "processed_items": processed_items,
                "successful_items": successful_items,
                "failed_items": failed_items,
                "average_items_per_second": float(avg_items_per_second),
                "average_processing_time": float(avg_processing_time),
                "success_rate": (successful_items / processed_items * 100)
                if processed_items > 0
                else 0.0,
            }

        except Exception as e:
            logger.error(f"Error getting job statistics: {e}")
            return {"error": str(e)}

    # Job processors (simplified implementations)
    def _process_ai_import_item(
        self, item_data: Dict[str, Any], job_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process AI import item."""
        try:
            from app.modules.import_batch.v2.services.ai_import_service_v2 import AIImportService
            from app.models.batch_import import BatchImportJob

            service = AIImportService()
            
            # Get job_id from job_params to track costs
            job_id = job_params.get("job_id")
            if job_id:
                # Get the job to track costs
                job = BatchImportJob.query.get(job_id)
                if job:
                    # Store initial cost to calculate delta
                    initial_cost = float(job.actual_cost_usd) if job.actual_cost_usd else 0.0
            
            # Perform AI analysis
            result = service.analyze_application_for_ai_mapping(item_data["id"])
            
            # Track cost if job exists
            if job_id and 'job' in locals():
                # Calculate cost incurred during this operation
                final_cost = float(job.actual_cost_usd) if job.actual_cost_usd else 0.0
                cost_incurred = final_cost - initial_cost
                
                # Add cost information to result
                return {
                    "result": result.__dict__, 
                    "confidence_score": result.avg_capability_confidence,
                    "cost_incurred": cost_incurred,
                    "total_cost": final_cost
                }
            
            return {"result": result.__dict__, "confidence_score": result.avg_capability_confidence}
        except Exception as e:
            raise Exception(f"AI import processing failed: {e}")

    def _process_capability_mapping_item(
        self, item_data: Dict[str, Any], job_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process capability mapping item."""
        return {"result": {"mapped_capabilities": []}, "confidence_score": 0.8}

    def _process_apqc_classification_item(
        self, item_data: Dict[str, Any], job_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process APQC classification item."""
        return {"result": {"apqc_processes": []}, "confidence_score": 0.7}

    def _process_archimate_generation_item(
        self, item_data: Dict[str, Any], job_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process ArchiMate generation item."""
        return {"result": {"archimate_elements": []}, "confidence_score": 0.6}

    def _process_vendor_analysis_item(
        self, item_data: Dict[str, Any], job_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process vendor analysis item."""
        return {"result": {"vendor_products": []}, "confidence_score": 0.7}

    def _process_taxonomy_validation_item(
        self, item_data: Dict[str, Any], job_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process taxonomy validation item."""
        return {"result": {"validation_results": []}, "confidence_score": 0.9}

    def _process_bulk_update_item(
        self, item_data: Dict[str, Any], job_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process bulk update item."""
        return {"result": {"updated_fields": []}, "confidence_score": 1.0}

    # Error handlers (simplified implementations)
    def _handle_validation_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle validation error."""
        return {
            "can_retry": False,
            "retry_delay": 0,
            "recovery_action": "manual_intervention",
            "recovery_suggestion": "Review and correct input data",
        }

    def _handle_processing_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle processing error."""
        return {
            "can_retry": True,
            "retry_delay": 60,
            "recovery_action": "retry",
            "recovery_suggestion": "Retry processing after delay",
        }

    def _handle_system_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle system error."""
        return {
            "can_retry": True,
            "retry_delay": 120,
            "recovery_action": "retry",
            "recovery_suggestion": "Retry after system recovery",
        }

    def _handle_timeout_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle timeout error."""
        return {
            "can_retry": True,
            "retry_delay": 300,
            "recovery_action": "retry",
            "recovery_suggestion": "Retry with increased timeout",
        }

    def _handle_data_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data error."""
        return {
            "can_retry": False,
            "retry_delay": 0,
            "recovery_action": "skip",
            "recovery_suggestion": "Skip item due to data issues",
        }

    def _handle_resource_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resource error."""
        return {
            "can_retry": True,
            "retry_delay": 180,
            "recovery_action": "retry",
            "recovery_suggestion": "Retry after resource recovery",
        }

    # Recovery strategies (simplified implementations)
    def _retry_item_processing(self, item: Any, context: Dict[str, Any]) -> bool:
        """Retry item processing."""
        return True

    def _skip_item_processing(self, item: Any, context: Dict[str, Any]) -> bool:
        """Skip item processing."""
        return True

    def _request_manual_intervention(self, item: Any, context: Dict[str, Any]) -> bool:
        """Request manual intervention."""
        return False

    def _abort_job_processing(self, item: Any, context: Dict[str, Any]) -> bool:
        """Abort job processing."""
        return False

    def _recover_from_checkpoint(self, item: Any, context: Dict[str, Any]) -> bool:
        """Recover from checkpoint."""
        return True
