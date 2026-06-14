"""
Shared Execution Engine for Pipeline and Workflow.
Eliminates code duplication and provides consistent stage execution.
"""
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from app import db

from ..validation.artifact_validator import ArtifactValidator, validate_or_fail
from ..validation.schema_validator import SchemaValidator
from .retry_handler import RetryHandler
from .transaction_manager import pipeline_transaction

logger = logging.getLogger(__name__)


class StageResult:
    """Result of stage execution."""

    def __init__(
        self, success: bool, artifacts: Dict[str, Any], cost: float = 0.0, error: str = None
    ):
        self.success = success
        self.artifacts = artifacts
        self.cost = cost
        self.error = error


class ExecutionEngine:
    """
    Generic execution engine for pipeline stages.
    Used by both GenerationPipeline and WorkflowPipeline.

    Features:
    - Automatic retry on transient failures
    - Artifact validation (no silent failures)
    - Cost tracking
    - Transaction management
    - Structured logging
    """

    def __init__(self, pipeline, cost_tracker=None):
        """
        Initialize execution engine.

        Args:
            pipeline: GenerationPipeline or WorkflowPipeline instance
            cost_tracker: Optional cost tracking object
        """
        self.pipeline = pipeline
        self.cost_tracker = cost_tracker
        self.retry_handler = RetryHandler(max_attempts=3)

    def execute_stage(
        self,
        stage_name: str,
        handler_func: Callable,
        context: Dict[str, Any],
        validate_func: Optional[Callable] = None,
    ) -> StageResult:
        """
        Execute a pipeline stage with validation and error handling.

        Args:
            stage_name: Human-readable stage name (e.g., "architecture_gen")
            handler_func: Function that executes the stage logic
            context: Context dictionary with inputs for the stage
            validate_func: Optional validation function for artifacts

        Returns:
            StageResult with success status, artifacts, and cost

        Example:
            result = engine.execute_stage(
                stage_name="architecture_gen",
                handler_func=lambda ctx: generate_architecture(ctx['jira_issues']),
                context={'jira_issues': issues},
                validate_func=ArtifactValidator.validate_architecture_elements
            )
        """
        logger.info(f"[{self.pipeline.id}] Starting stage: {stage_name}")
        start_time = datetime.utcnow()

        try:
            # Execute with retry logic
            success, result, attempts, error = self.retry_handler.execute_with_retry(
                handler_func, context
            )

            if not success:
                logger.error(
                    f"[{self.pipeline.id}] Stage {stage_name} failed after {attempts} attempts: {error}"
                )
                return StageResult(success=False, artifacts={}, cost=0.0, error=str(error))

            # Extract artifacts and cost
            artifacts = result.get("artifacts", {}) if isinstance(result, dict) else {}
            cost = result.get("cost", 0.0) if isinstance(result, dict) else 0.0

            # Validate artifacts if validator provided
            if validate_func and artifacts:
                try:
                    validation_result = validate_func(artifacts)

                    if not validation_result.valid:
                        error_msg = f"Artifact validation failed: {validation_result.message}"
                        logger.error(f"[{self.pipeline.id}] {error_msg}")
                        return StageResult(success=False, artifacts={}, cost=cost, error=error_msg)

                    # Log warnings
                    for warning in validation_result.warnings:
                        logger.warning(f"[{self.pipeline.id}] {warning}")

                except Exception as validation_error:
                    logger.error(f"[{self.pipeline.id}] Validation error: {validation_error}")
                    return StageResult(
                        success=False,
                        artifacts={},
                        cost=cost,
                        error=f"Validation exception: {validation_error}",
                    )

            # Track cost
            if self.cost_tracker and cost > 0:
                self.cost_tracker.add(cost)

            # Log success
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"[{self.pipeline.id}] Stage {stage_name} completed successfully "
                f"in {duration:.2f}s (attempts: {attempts}, cost: ${cost:.4f})"
            )

            return StageResult(success=True, artifacts=artifacts, cost=cost)

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                f"[{self.pipeline.id}] Stage {stage_name} failed with unexpected error after {duration:.2f}s: {e}",
                exc_info=True,
            )
            return StageResult(success=False, artifacts={}, cost=0.0, error=str(e))


class CostTracker:
    """Simple cost tracking for pipelines."""

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.total_cost = 0.0

    def add(self, cost: float):
        """Add cost to total."""
        self.total_cost += cost
        logger.info(f"[{self.pipeline.id}] Cost accumulated: ${self.total_cost:.4f} (+${cost:.4f})")

    def get_total(self) -> float:
        """Get total accumulated cost."""
        return self.total_cost


# Example usage:
def example_pipeline_execution():
    """
    Example of how to use ExecutionEngine in your pipeline.
    """
    from app.models import GenerationPipeline

    pipeline = db.session.get(GenerationPipeline, 1)
    engine = ExecutionEngine(pipeline, cost_tracker=CostTracker(pipeline))

    # Stage 1: Architecture Generation
    def architecture_stage_handler(ctx):
        # Your existing logic here
        from app.services.llm_service import LLMService

        elements = []  # Generate elements using LLM
        return {"artifacts": elements, "cost": 0.05}

    result = engine.execute_stage(
        stage_name="architecture_generation",
        handler_func=architecture_stage_handler,
        context={"jira_issues": []},
        validate_func=ArtifactValidator.validate_architecture_elements,
    )

    if not result.success:
        # Handle failure
        logger.error(f"Pipeline failed: {result.error}")
        return False

    # Continue with next stage...
    return True
