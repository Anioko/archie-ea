"""
-> app.modules.import_batch.services.batch_service

Batch Processor Service

Handles processing of individual batches and applications.
Integrates with AI services to generate elements with checkpointing.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

from flask import current_app

from app import db
from app.models.batch_import import (
    AppProcessingStatus,
    BatchImportApplication,
    BatchImportBatch,
    BatchImportCheckpoint,
    BatchImportElement,
    BatchImportJob,
    BatchJobStatus,
    BatchStatus,
    CheckpointType,
    ElementApprovalStatus,
)

logger = logging.getLogger(__name__)


class BatchProcessorService:
    """
    Service for processing individual batches.

    Handles:
    - Processing batches with checkpointing
    - Generating AI elements for applications
    - Recovery from failures
    - Cost tracking
    """

    def __init__(self):
        self._ai_service = None

    @property
    def ai_service(self):
        """Lazy load AI service to avoid circular imports."""
        if self._ai_service is None:
            try:
                from app.modules.import_batch.v2.services.ai_import_service_v2 import AIImportService

                self._ai_service = AIImportService()
            except ImportError:
                logger.warning("AIImportService not available")
                self._ai_service = None
        return self._ai_service

    def process_batch(self, batch_id: int) -> BatchImportBatch:
        """
        Process a single batch of applications.

        This is the main entry point for batch processing.
        Creates checkpoints after each application for recovery.

        Args:
            batch_id: ID of the batch to process

        Returns:
            Updated batch instance
        """
        batch = BatchImportBatch.query.get_or_404(batch_id)
        job = batch.job

        # Verify batch can be processed
        if batch.status not in [BatchStatus.QUEUED, BatchStatus.FAILED]:
            logger.warning(f"Batch {batch_id} is not in a processable state: {batch.status}")
            return batch

        # Verify job is in processing state
        if job.status != BatchJobStatus.PROCESSING:
            logger.warning(f"Job {job.id} is not in processing state: {job.status}")
            return batch

        # Update batch status
        batch.status = BatchStatus.PROCESSING
        batch.started_at = batch.started_at or datetime.utcnow()
        db.session.commit()

        # Create batch started checkpoint
        self._create_checkpoint(batch, CheckpointType.BATCH_STARTED)

        try:
            # Get applications to process
            applications = self._get_applications_to_process(batch)

            for app in applications:
                # Check if job was paused
                db.session.refresh(job)
                if job.status == BatchJobStatus.PAUSED:
                    logger.info(f"Job {job.id} paused, stopping batch {batch_id} processing")
                    batch.status = BatchStatus.QUEUED
                    db.session.commit()
                    return batch

                # Check budget
                if job.budget_limit_usd and job.actual_cost_usd >= job.budget_limit_usd:
                    logger.warning(f"Budget exhausted for job {job.id}")
                    batch.status = BatchStatus.READY_FOR_REVIEW
                    batch.completed_at = datetime.utcnow()
                    job.status = BatchJobStatus.PAUSED
                    job.error_message = "Budget limit reached"
                    db.session.commit()
                    return batch

                # Process the application
                self._process_application(app, batch, job)

                # Update batch progress
                batch.processed_applications += 1
                batch.current_application_name = None
                db.session.commit()

            # Batch completed
            batch.status = BatchStatus.READY_FOR_REVIEW
            batch.completed_at = datetime.utcnow()
            self._create_checkpoint(batch, CheckpointType.BATCH_COMPLETED)

            # Update job progress
            job.batches_completed = sum(
                1
                for b in job.batches
                if b.status
                in [BatchStatus.READY_FOR_REVIEW, BatchStatus.APPROVED, BatchStatus.COMMITTED]
            )

            db.session.commit()

            logger.info(
                f"Batch {batch_id} processing complete: "
                f"{batch.successful_applications}/{batch.total_applications} successful, "
                f"{batch.total_elements_generated} elements generated"
            )

        except Exception as e:
            logger.error(f"Error processing batch {batch_id}: {e}", exc_info=True)
            batch.status = BatchStatus.FAILED
            batch.error_message = str(e)
            batch.retry_count += 1
            db.session.commit()
            raise

        return batch

    def _get_applications_to_process(self, batch: BatchImportBatch) -> List[BatchImportApplication]:
        """Get applications that need processing (for recovery support)."""
        return (
            BatchImportApplication.query.filter(
                BatchImportApplication.batch_id == batch.id,
                BatchImportApplication.status.in_(
                    [
                        AppProcessingStatus.PENDING,
                        AppProcessingStatus.FAILED,
                    ]
                ),
            )
            .order_by(BatchImportApplication.row_number)
            .all()
        )

    def _process_application(
        self,
        app: BatchImportApplication,
        batch: BatchImportBatch,
        job: BatchImportJob,
    ) -> None:
        """
        Process a single application within a batch.

        Generates AI elements and creates checkpoints.
        """
        start_time = time.time()

        # Update status
        app.status = AppProcessingStatus.PROCESSING
        batch.current_application_name = app.application_name
        db.session.commit()

        # Create checkpoint
        self._create_checkpoint(batch, CheckpointType.APP_STARTED, app.id)

        try:
            elements = []

            if job.enable_ai_generation:
                # Generate AI elements
                elements = self._generate_elements_for_application(app, job)

                # Create checkpoint after generation
                self._create_checkpoint(
                    batch,
                    CheckpointType.APP_ELEMENTS_GENERATED,
                    app.id,
                    {"elements_count": len(elements)},
                )

            # Update application stats
            app.status = AppProcessingStatus.COMPLETED
            app.elements_generated = len(elements)
            app.processing_time_seconds = time.time() - start_time

            if elements:
                confidence_scores = [e.confidence_score for e in elements if e.confidence_score]
                if confidence_scores:
                    app.average_confidence_score = sum(confidence_scores) / len(confidence_scores)

            # Update batch stats
            batch.successful_applications += 1
            batch.total_elements_generated += len(elements)

            # Create completion checkpoint
            self._create_checkpoint(batch, CheckpointType.APP_COMPLETED, app.id)

            app.processed_at = datetime.utcnow()
            db.session.commit()

            logger.debug(
                f"Processed application {app.id}: {app.application_name} - {len(elements)} elements"
            )

        except Exception as e:
            logger.error(f"Error processing application {app.id}: {e}", exc_info=True)
            app.status = AppProcessingStatus.FAILED
            app.error_message = str(e)
            batch.failed_applications += 1
            db.session.commit()

    def _generate_elements_for_application(
        self,
        app: BatchImportApplication,
        job: BatchImportJob,
    ) -> List[BatchImportElement]:
        """
        Generate AI elements for an application.

        Integrates with real AI services via AIElementGenerator adapter.
        Tracks actual costs and metrics from AI generation.
        """
        elements = []

        # Build application context for AI
        app_context = {
            "name": app.application_name,
            "description": app.application_description,
            "type": app.application_type,
            "vendor": app.vendor_name,
            "source_data": app.source_data,
        }

        try:
            # Generate ArchiMate elements based on mode (now returns tuple with metrics)
            archimate_elements, metrics = self._generate_archimate_elements(
                app_context,
                job.archimate_mode,
                use_real_ai=job.enable_ai_generation,
            )

            for elem_data in archimate_elements:
                element = BatchImportElement(
                    batch_id=app.batch_id,
                    application_id=app.id,
                    element_uuid=str(uuid.uuid4()),
                    element_type="archimate_element",
                    element_subtype=elem_data.get("type"),
                    element_name=elem_data.get("name", "Unnamed Element"),
                    element_description=elem_data.get("description"),
                    element_data=elem_data,
                    archimate_layer=elem_data.get("layer"),
                    generated_by_model=elem_data.get("model", metrics.model_used),
                    confidence_score=elem_data.get("confidence", 0.8),
                    approval_status=ElementApprovalStatus.PENDING,
                )
                db.session.add(element)
                elements.append(element)

            # Track ACTUAL costs from metrics (not estimates)
            app.tokens_used = metrics.tokens_used
            app.llm_calls = metrics.llm_calls
            app.cost_usd = metrics.cost_usd
            app.processing_time_seconds = metrics.processing_time_seconds

            app.batch.batch_tokens_used += metrics.tokens_used
            app.batch.batch_llm_calls += metrics.llm_calls
            app.batch.batch_cost_usd += metrics.cost_usd

            job.total_tokens_used += metrics.tokens_used
            job.total_llm_calls += metrics.llm_calls
            job.actual_cost_usd += metrics.cost_usd

            db.session.flush()

        except Exception as e:
            logger.error(f"Error generating elements for {app.application_name}: {e}")
            raise

        return elements

    def _generate_archimate_elements(
        self,
        app_context: Dict[str, Any],
        mode: str,
        use_real_ai: bool = True,
    ) -> tuple:
        """
        Generate ArchiMate elements for an application.

        Uses AIElementGenerator adapter to call real AI services when available,
        with fallback to mock generation for testing or when AI is unavailable.

        Args:
            app_context: Application data dictionary
            mode: Generation mode (quick/standard/comprehensive)
            use_real_ai: If True, attempt to use real AI; if False, use mock only

        Returns:
            Tuple of (elements_list, generation_metrics)
        """
        from app.modules.import_batch.v2.services.unified_import.ai_element_generator_v2 import AIElementGenerator

        generator = AIElementGenerator()

        # Check if we should use real AI based on configuration
        use_ai = use_real_ai and current_app.config.get("ENABLE_AI_IMPORT", True)

        elements, metrics = generator.generate_elements_for_batch_app(
            app_context=app_context,
            mode=mode,
            use_real_ai=use_ai,
        )

        logger.info(
            f"Generated {metrics.elements_generated} elements for '{app_context.get('name')}' "
            f"using {metrics.model_used} (tokens: {metrics.tokens_used}, "
            f"cost: ${float(metrics.cost_usd):.4f})"
        )

        return elements, metrics

    def _create_checkpoint(
        self,
        batch: BatchImportBatch,
        checkpoint_type: CheckpointType,
        application_id: int = None,
        data: Dict = None,
    ) -> BatchImportCheckpoint:
        """Create a recovery checkpoint."""
        checkpoint = BatchImportCheckpoint(
            batch_id=batch.id,
            checkpoint_type=checkpoint_type,
            checkpoint_name=f"{checkpoint_type.value}_{datetime.utcnow().strftime('%H%M%S')}",
            application_id=application_id,
            checkpoint_data=data or {},
            elements_staged=batch.total_elements_generated,
        )
        db.session.add(checkpoint)
        db.session.flush()
        return checkpoint

    def recover_batch(self, batch_id: int) -> BatchImportBatch:
        """
        Recover a failed batch from its last checkpoint.

        Resumes processing from where it left off.
        """
        batch = BatchImportBatch.query.get_or_404(batch_id)

        if batch.status != BatchStatus.FAILED:
            raise ValueError(f"Batch {batch_id} is not in failed state")

        if not batch.can_retry:
            raise ValueError(f"Batch {batch_id} has exceeded retry limit")

        # Get last checkpoint
        last_checkpoint = (
            BatchImportCheckpoint.query.filter_by(batch_id=batch_id)
            .order_by(BatchImportCheckpoint.created_at.desc())
            .first()
        )

        if last_checkpoint:
            logger.info(
                f"Recovering batch {batch_id} from checkpoint: "
                f"{last_checkpoint.checkpoint_type.value}"
            )

        # Reset batch status for reprocessing
        batch.status = BatchStatus.QUEUED
        batch.error_message = None
        db.session.commit()

        # Process the batch (will skip already completed applications)
        return self.process_batch(batch_id)
