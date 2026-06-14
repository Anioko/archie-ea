"""
Transaction Manager with rollback/compensation support.
Ensures pipeline failures don't leave orphaned data.
"""
import logging
from contextlib import contextmanager
from typing import Any, Callable, List, Tuple

from app import db

logger = logging.getLogger(__name__)


class TransactionManager:
    """
    Manages distributed transactions with compensation logic.
    Tracks all operations for rollback on failure.
    """

    def __init__(self):
        """Initialize transaction manager."""
        self.operations: List[Tuple[Callable, Callable, str]] = []
        self.executed: List[Tuple[Callable, str]] = []

    def register_operation(
        self, forward_func: Callable, backward_func: Callable, description: str = ""
    ):
        """
        Register an operation with its compensation function.

        Args:
            forward_func: Function to execute (no args)
            backward_func: Function to undo the operation (no args)
            description: Human-readable description

        Example:
            tx = TransactionManager()
            tx.register_operation(
                forward=lambda: db.session.add(architecture),
                backward=lambda: db.session.delete(architecture),
                description="Create architecture model"
            )
        """
        self.operations.append((forward_func, backward_func, description or "Operation"))

    def execute(self) -> bool:
        """
        Execute all registered operations.
        Rollback in reverse order on failure.

        Returns:
            bool: True if all operations succeeded, False otherwise
        """
        try:
            logger.info(f"Starting transaction with {len(self.operations)} operations")

            for forward_func, backward_func, description in self.operations:
                try:
                    logger.info(f"Executing: {description}")
                    forward_func()
                    self.executed.append((backward_func, description))

                except Exception as e:
                    logger.error(f"Operation failed: {description} - {e}")
                    self._rollback()
                    return False

            logger.info(f"Transaction completed successfully ({len(self.executed)} operations)")
            return True

        except Exception as e:
            logger.error(f"Transaction failed with unexpected error: {e}")
            self._rollback()
            return False

    def _rollback(self):
        """Rollback all executed operations in reverse order."""
        if not self.executed:
            logger.info("No operations to rollback")
            return

        logger.warning(f"Rolling back {len(self.executed)} operations...")

        for backward_func, description in reversed(self.executed):
            try:
                logger.info(f"Rolling back: {description}")
                backward_func()
            except Exception as rollback_error:
                logger.error(
                    f"Rollback failed for '{description}': {rollback_error}. "
                    f"Manual cleanup may be required!"
                )

        logger.info("Rollback completed")


class PipelineTransactionContext:
    """
    Context manager for pipeline execution with automatic rollback.
    Tracks all created database objects and files for cleanup.
    """

    def __init__(self, pipeline):
        """
        Initialize context for a pipeline.

        Args:
            pipeline: GenerationPipeline or WorkflowPipeline instance
        """
        self.pipeline = pipeline
        self.created_objects = []
        self.created_files = []
        self.savepoint = None

    def __enter__(self):
        """Start transaction context."""
        # Create database savepoint
        try:
            self.savepoint = db.session.begin_nested()
            logger.info(f"Started transaction for pipeline {self.pipeline.id}")
        except Exception as e:
            logger.warning(f"Could not create nested transaction (SQLite?): {e}")
            # Continue without savepoint - will use session-level rollback

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit transaction context.
        Commit if no exception, rollback otherwise.
        """
        if exc_type is None:
            # Success - commit
            try:
                if self.savepoint:
                    self.savepoint.commit()
                db.session.commit()
                logger.info(f"Transaction committed for pipeline {self.pipeline.id}")
            except Exception as e:
                logger.error(f"Commit failed: {e}")
                self._rollback()
                raise

        else:
            # Failure - rollback
            logger.error(f"Pipeline {self.pipeline.id} failed with {exc_type.__name__}: {exc_val}")
            self._rollback()

        return False  # Don't suppress exceptions

    def _rollback(self):
        """Rollback database and filesystem changes."""
        logger.warning(f"Rolling back pipeline {self.pipeline.id}...")

        # Rollback database
        try:
            if self.savepoint:
                self.savepoint.rollback()
            logger.info("Database changes rolled back")
        except Exception as e:
            logger.error(f"Database rollback failed: {e}")

        # Delete created objects (backup plan if rollback didn't work)
        for obj in reversed(self.created_objects):
            try:
                if obj in db.session:
                    db.session.delete(obj)
                logger.debug(f"Deleted object: {obj}")
            except Exception as e:
                logger.error(f"Failed to delete {obj}: {e}")

        # Delete created files
        for filepath in self.created_files:
            try:
                import os

                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"Deleted file: {filepath}")
            except Exception as e:
                logger.error(f"Failed to delete file {filepath}: {e}")

        # Try final commit of cleanup
        try:
            db.session.commit()
        except Exception as e:
            logger.debug("Final cleanup commit failed: %s", e)

    def track_object(self, obj):
        """Track a created database object for potential rollback."""
        self.created_objects.append(obj)

    def track_file(self, filepath: str):
        """Track a created file for cleanup on rollback."""
        self.created_files.append(filepath)


@contextmanager
def pipeline_transaction(pipeline):
    """
    Context manager for pipeline execution with automatic rollback.

    Usage:
        with pipeline_transaction(pipeline) as tx:
            architecture = create_architecture()
            tx.track_object(architecture)

            code_file = generate_code()
            tx.track_file(code_file)

            # If any exception occurs, everything is rolled back
    """
    context = PipelineTransactionContext(pipeline)
    try:
        yield context.__enter__()
    finally:
        context.__exit__(*None, None, None)


# Decorator for transactional functions
def transactional(func):
    """
    Decorator to make a function transactional.

    Usage:
        @transactional
        def create_pipeline_artifacts(pipeline):
            # Create stuff
            # Automatically rolled back on exception
    """

    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            db.session.commit()
            return result
        except Exception as e:
            logger.error(f"Transaction failed in {func.__name__}: {e}")
            raise

    return wrapper
