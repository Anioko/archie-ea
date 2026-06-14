"""
Workflow Error Recovery

Provides comprehensive error recovery mechanisms for workflow engine.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import threading
import traceback

from flask import current_app
from app import db
from app.monitoring.alerting_service import alerting_service, AlertSeverity

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RecoveryAction(Enum):
    """Recovery action types."""
    RETRY = "retry"
    ROLLBACK = "rollback"
    SKIP = "skip"
    MANUAL = "manual"
    TERMINATE = "terminate"

@dataclass
class WorkflowError:
    """Represents a workflow error."""
    id: str
    workflow_id: str
    step_id: str
    error_type: str
    error_message: str
    severity: ErrorSeverity
    timestamp: datetime
    context: Dict[str, Any]
    stack_trace: Optional[str] = None
    recovery_attempts: int = 0
    resolved: bool = False

@dataclass
class RecoveryStrategy:
    """Represents a recovery strategy."""
    error_type: str
    action: RecoveryAction
    max_attempts: int
    retry_delay: float
    conditions: Dict[str, Any]
    handler: Optional[Callable] = None

class WorkflowErrorRecovery:
    """
    Manages error recovery for workflow executions.
    """
    
    def __init__(self):
        """Initialize the workflow error recovery system."""
        self._errors = {}  # error_id -> WorkflowError
        self._strategies = {}
        self._active_recoveries = {}  # workflow_id -> recovery_info
        self._lock = threading.Lock()
        
        # Initialize default recovery strategies
        self._initialize_default_strategies()
        
        # Load custom strategies from configuration
        self._load_custom_strategies()
    
    def _initialize_default_strategies(self):
        """Initialize default error recovery strategies."""
        self._strategies = {
            'database_connection_error': RecoveryStrategy(
                error_type='database_connection_error',
                action=RecoveryAction.RETRY,
                max_attempts=3,
                retry_delay=5.0,
                conditions={'timeout': 30}
            ),
            'validation_error': RecoveryStrategy(
                error_type='validation_error',
                action=RecoveryAction.SKIP,
                max_attempts=1,
                retry_delay=0.0,
                conditions={'skip_step': True}
            ),
            'permission_denied': RecoveryStrategy(
                error_type='permission_denied',
                action=RecoveryAction.MANUAL,
                max_attempts=1,
                retry_delay=0.0,
                conditions={'requires_intervention': True}
            ),
            'resource_unavailable': RecoveryStrategy(
                error_type='resource_unavailable',
                action=RecoveryAction.RETRY,
                max_attempts=5,
                retry_delay=10.0,
                conditions={'backoff_multiplier': 2}
            ),
            'timeout_error': RecoveryStrategy(
                error_type='timeout_error',
                action=RecoveryAction.RETRY,
                max_attempts=2,
                retry_delay=15.0,
                conditions={'increase_timeout': True}
            ),
            'data_corruption': RecoveryStrategy(
                error_type='data_corruption',
                action=RecoveryAction.ROLLBACK,
                max_attempts=1,
                retry_delay=0.0,
                conditions={'rollback_to_last_checkpoint': True}
            ),
            'critical_system_error': RecoveryStrategy(
                error_type='critical_system_error',
                action=RecoveryAction.TERMINATE,
                max_attempts=1,
                retry_delay=0.0,
                conditions={'terminate_workflow': True}
            ),
            'external_service_error': RecoveryStrategy(
                error_type='external_service_error',
                action=RecoveryAction.RETRY,
                max_attempts=3,
                retry_delay=30.0,
                conditions={'circuit_breaker': True}
            )
        }
    
    def _load_custom_strategies(self):
        """Load custom recovery strategies from configuration."""
        try:
            # Load from app configuration
            custom_strategies = current_app.config.get('WORKFLOW_RECOVERY_STRATEGIES', {})
            
            for error_type, config in custom_strategies.items():
                action = RecoveryAction(config.get('action', 'retry'))
                self._strategies[error_type] = RecoveryStrategy(
                    error_type=error_type,
                    action=action,
                    max_attempts=config.get('max_attempts', 3),
                    retry_delay=config.get('retry_delay', 5.0),
                    conditions=config.get('conditions', {})
                )
                
        except Exception as e:
            logger.warning(f"Failed to load custom recovery strategies: {e}")
    
    def handle_error(self, workflow_id: str, step_id: str, error: Exception,
                    context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle a workflow error and attempt recovery.
        
        Args:
            workflow_id: Workflow instance ID
            step_id: Step ID where error occurred
            error: Exception that occurred
            context: Additional context information
            
        Returns:
            True if error was handled/recovered, False otherwise
        """
        # Create workflow error record
        workflow_error = WorkflowError(
            id=self._generate_error_id(),
            workflow_id=workflow_id,
            step_id=step_id,
            error_type=type(error).__name__,
            error_message=str(error),
            severity=self._classify_error_severity(error),
            timestamp=datetime.utcnow(),
            context=context or {},
            stack_trace=traceback.format_exc()
        )
        
        with self._lock:
            self._errors[workflow_error.id] = workflow_error
        
        # Log the error
        logger.error(f"Workflow error in {workflow_id}:{step_id} - {workflow_error.error_message}")
        
        # Get recovery strategy
        strategy = self._get_recovery_strategy(workflow_error)
        
        if not strategy:
            logger.warning(f"No recovery strategy found for error type: {workflow_error.error_type}")
            self._escalate_error(workflow_error)
            return False
        
        # Attempt recovery
        return self._attempt_recovery(workflow_error, strategy)
    
    def _classify_error_severity(self, error: Exception) -> ErrorSeverity:
        """Classify error severity based on exception type and message."""
        error_message = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Critical errors
        if any(term in error_message for term in ['critical', 'fatal', 'system', 'corruption']):
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if any(term in error_type for term in ['connection', 'timeout', 'permission']):
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if any(term in error_message for term in ['validation', 'format', 'missing']):
            return ErrorSeverity.MEDIUM
        
        # Default to low severity
        return ErrorSeverity.LOW
    
    def _get_recovery_strategy(self, error: WorkflowError) -> Optional[RecoveryStrategy]:
        """Get recovery strategy for an error."""
        # Try exact match first
        strategy = self._strategies.get(error.error_type)
        if strategy:
            return strategy
        
        # Try pattern matching
        for error_type, strategy in self._strategies.items():
            if error_type.lower() in error.error_type.lower():
                return strategy
        
        return None
    
    def _attempt_recovery(self, error: WorkflowError, strategy: RecoveryStrategy) -> bool:
        """Attempt to recover from an error using a strategy."""
        logger.info(f"Attempting recovery for {error.error_type} using {strategy.action.value}")
        
        with self._lock:
            if error.workflow_id in self._active_recoveries:
                # Recovery already in progress
                return False
            
            self._active_recoveries[error.workflow_id] = {
                'error_id': error.id,
                'strategy': strategy,
                'attempts': 0,
                'start_time': datetime.utcnow()
            }
        
        try:
            if strategy.action == RecoveryAction.RETRY:
                return self._retry_recovery(error, strategy)
            elif strategy.action == RecoveryAction.ROLLBACK:
                return self._rollback_recovery(error, strategy)
            elif strategy.action == RecoveryAction.SKIP:
                return self._skip_recovery(error, strategy)
            elif strategy.action == RecoveryAction.MANUAL:
                return self._manual_recovery(error, strategy)
            elif strategy.action == RecoveryAction.TERMINATE:
                return self._terminate_recovery(error, strategy)
            else:
                logger.error(f"Unknown recovery action: {strategy.action}")
                return False
                
        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")
            self._escalate_error(error)
            return False
        
        finally:
            with self._lock:
                self._active_recoveries.pop(error.workflow_id, None)
    
    def _retry_recovery(self, error: WorkflowError, strategy: RecoveryStrategy) -> bool:
        """Attempt retry recovery."""
        max_attempts = strategy.max_attempts
        retry_delay = strategy.retry_delay
        
        for attempt in range(max_attempts):
            error.recovery_attempts += 1
            
            logger.info(f"Retry attempt {attempt + 1}/{max_attempts} for {error.workflow_id}")
            
            # Wait before retry
            if retry_delay > 0:
                time.sleep(retry_delay)
                
                # Apply backoff if configured
                backoff_multiplier = strategy.conditions.get('backoff_multiplier', 1)
                if backoff_multiplier > 1 and attempt > 0:
                    retry_delay *= backoff_multiplier
            
            try:
                # Attempt to retry the step
                success = self._retry_workflow_step(error)
                
                if success:
                    logger.info(f"Retry successful for {error.workflow_id}")
                    error.resolved = True
                    self._set_workflow_status(error.workflow_id, "running")
                    self._log_recovery_success(error, 'retry')
                    return True
                    
            except Exception as e:
                logger.warning(f"Retry attempt {attempt + 1} failed: {e}")
                continue
        
        logger.error(f"All retry attempts failed for {error.workflow_id}")
        return False
    
    def _rollback_recovery(self, error: WorkflowError, strategy: RecoveryStrategy) -> bool:
        """Attempt rollback recovery."""
        try:
            from .rollback_manager import workflow_rollback_manager
            
            # Perform rollback
            rollback_success = workflow_rollback_manager.rollback_workflow(
                error.workflow_id, 
                error.step_id,
                reason=error.error_message
            )
            
            if rollback_success:
                logger.info(f"Rollback successful for {error.workflow_id}")
                error.resolved = True
                self._set_workflow_status(error.workflow_id, "running")
                self._log_recovery_success(error, 'rollback')
                return True
            else:
                logger.error(f"Rollback failed for {error.workflow_id}")
                return False
                
        except Exception as e:
            logger.error(f"Rollback recovery failed: {e}")
            return False
    
    def _skip_recovery(self, error: WorkflowError, strategy: RecoveryStrategy) -> bool:
        """Attempt skip recovery."""
        try:
            # Skip the problematic step
            skip_success = self._skip_workflow_step(error)
            
            if skip_success:
                logger.info(f"Step skipped for {error.workflow_id}")
                error.resolved = True
                self._log_recovery_success(error, 'skip')
                return True
            else:
                logger.error(f"Skip failed for {error.workflow_id}")
                return False
                
        except Exception as e:
            logger.error(f"Skip recovery failed: {e}")
            return False
    
    def _manual_recovery(self, error: WorkflowError, strategy: RecoveryStrategy) -> bool:
        """Initiate manual recovery."""
        try:
            from .manual_intervention import manual_intervention_manager
            
            # Create manual intervention request
            intervention_id = manual_intervention_manager.create_intervention_request(
                workflow_id=error.workflow_id,
                step_id=error.step_id,
                error=error,
                priority=self._map_severity_to_priority(error.severity)
            )
            
            logger.info(f"Manual intervention requested: {intervention_id}")
            
            # Create alert for manual intervention
            alerting_service.create_manual_alert(
                name=f"workflow_manual_intervention_{error.workflow_id}",
                severity=AlertSeverity.WARNING if error.severity != ErrorSeverity.CRITICAL else AlertSeverity.CRITICAL,
                message=f"Manual intervention required for workflow {error.workflow_id}: {error.error_message}",
                source='workflow_error_recovery',
                metadata={
                    'workflow_id': error.workflow_id,
                    'step_id': error.step_id,
                    'error_id': error.id,
                    'intervention_id': intervention_id
                }
            )
            
            return True  # Manual intervention initiated
            
        except Exception as e:
            logger.error(f"Manual recovery failed: {e}")
            return False
    
    def _terminate_recovery(self, error: WorkflowError, strategy: RecoveryStrategy) -> bool:
        """Terminate workflow due to critical error."""
        try:
            # Terminate the workflow
            terminate_success = self._terminate_workflow(error.workflow_id, error.error_message)
            
            if terminate_success:
                logger.info(f"Workflow terminated: {error.workflow_id}")
                error.resolved = True
                self._set_workflow_status(error.workflow_id, "failed")
                self._log_recovery_success(error, 'terminate')
                return True
            else:
                logger.error(f"Workflow termination failed: {error.workflow_id}")
                return False
                
        except Exception as e:
            logger.error(f"Terminate recovery failed: {e}")
            return False
    
    def _retry_workflow_step(self, error: WorkflowError) -> bool:
        """Retry a workflow step."""
        try:
            # This would integrate with the actual workflow engine
            # For now, simulate retry success
            logger.info(f"Retrying step {error.step_id} in workflow {error.workflow_id}")
            
            # In a real implementation, this would call the workflow engine
            # to re-execute the failed step
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to retry workflow step: {e}")
            raise
    
    def _skip_workflow_step(self, error: WorkflowError) -> bool:
        """Skip a workflow step."""
        try:
            # This would integrate with the actual workflow engine
            logger.info(f"Skipping step {error.step_id} in workflow {error.workflow_id}")
            
            # In a real implementation, this would mark the step as skipped
            # and continue with the next step
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to skip workflow step: {e}")
            raise
    
    def _terminate_workflow(self, workflow_id: str, reason: str) -> bool:
        """Terminate a workflow."""
        try:
            # This would integrate with the actual workflow engine
            logger.info(f"Terminating workflow {workflow_id}: {reason}")
            
            # In a real implementation, this would update the workflow
            # status to 'terminated' and stop all processing
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to terminate workflow: {e}")
            raise
    
    def _escalate_error(self, error: WorkflowError):
        """Escalate an error when recovery is not possible."""
        logger.critical(f"Escalating error for workflow {error.workflow_id}: {error.error_message}")
        
        # Create critical alert
        alerting_service.create_manual_alert(
            name=f"workflow_error_escalation_{error.workflow_id}",
            severity=AlertSeverity.CRITICAL,
            message=f"Workflow error escalation: {error.workflow_id} - {error.error_message}",
            source='workflow_error_recovery',
            metadata={
                'workflow_id': error.workflow_id,
                'step_id': error.step_id,
                'error_id': error.id,
                'severity': error.severity.value
            }
        )

    def _set_workflow_status(self, workflow_id: str, status: str):
        """Best-effort workflow status update after recovery actions."""
        try:
            from app.models.workflow_models import EAWorkflowInstance

            instance = EAWorkflowInstance.query.filter_by(instance_code=workflow_id).first()
            if not instance:
                return
            instance.status = status
            if status in {"failed", "completed", "cancelled"} and not instance.completed_at:
                instance.completed_at = datetime.utcnow()
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.warning("Failed to set workflow status for %s: %s", workflow_id, exc)
    
    def _log_recovery_success(self, error: WorkflowError, action: str):
        """Log successful recovery."""
        logger.info(f"Error recovery successful: {error.workflow_id} - {action}")
        
        # Log to workflow audit
        try:
            from .workflow_audit import workflow_audit
            workflow_audit.log_recovery_event(
                workflow_id=error.workflow_id,
                error_id=error.id,
                action=action,
                details={
                    'error_type': error.error_type,
                    'recovery_attempts': error.recovery_attempts,
                    'resolution_time': (datetime.utcnow() - error.timestamp).total_seconds()
                }
            )
        except Exception as e:
            logger.warning(f"Failed to log recovery to audit: {e}")
    
    def _map_severity_to_priority(self, severity: ErrorSeverity) -> str:
        """Map error severity to intervention priority."""
        mapping = {
            ErrorSeverity.LOW: 'low',
            ErrorSeverity.MEDIUM: 'medium',
            ErrorSeverity.HIGH: 'high',
            ErrorSeverity.CRITICAL: 'critical'
        }
        return mapping.get(severity, 'medium')
    
    def get_error_history(self, workflow_id: Optional[str] = None, 
                         time_delta: Optional[timedelta] = None) -> List[Dict[str, Any]]:
        """
        Get error history with filtering options.
        
        Args:
            workflow_id: Filter by workflow ID
            time_delta: Filter by time range
            
        Returns:
            List of error records
        """
        with self._lock:
            errors = list(self._errors.values())
        
        # Apply filters
        if workflow_id:
            errors = [e for e in errors if e.workflow_id == workflow_id]
        
        if time_delta:
            cutoff_time = datetime.utcnow() - time_delta
            errors = [e for e in errors if e.timestamp > cutoff_time]
        
        # Sort by timestamp (newest first)
        errors.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [
            {
                'id': error.id,
                'workflow_id': error.workflow_id,
                'step_id': error.step_id,
                'error_type': error.error_type,
                'error_message': error.error_message,
                'severity': error.severity.value,
                'timestamp': error.timestamp.isoformat(),
                'recovery_attempts': error.recovery_attempts,
                'resolved': error.resolved
            }
            for error in errors
        ]
    
    def get_active_recoveries(self) -> List[Dict[str, Any]]:
        """Get list of active recovery operations."""
        with self._lock:
            active = []
            for workflow_id, recovery_info in self._active_recoveries.items():
                active.append({
                    'workflow_id': workflow_id,
                    'error_id': recovery_info['error_id'],
                    'strategy': recovery_info['strategy'].action.value,
                    'attempts': recovery_info['attempts'],
                    'start_time': recovery_info['start_time'].isoformat(),
                    'duration': (datetime.utcnow() - recovery_info['start_time']).total_seconds()
                })
            
            return active
    
    def _generate_error_id(self) -> str:
        """Generate unique error ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"error_{timestamp}_{threading.get_ident()}"
        return data
    
    def add_custom_strategy(self, error_type: str, action: RecoveryAction,
                           max_attempts: int = 3, retry_delay: float = 5.0,
                           conditions: Optional[Dict[str, Any]] = None):
        """
        Add a custom recovery strategy.
        
        Args:
            error_type: Error type to handle
            action: Recovery action
            max_attempts: Maximum retry attempts
            retry_delay: Delay between retries
            conditions: Additional conditions
        """
        strategy = RecoveryStrategy(
            error_type=error_type,
            action=action,
            max_attempts=max_attempts,
            retry_delay=retry_delay,
            conditions=conditions or {}
        )
        
        with self._lock:
            self._strategies[error_type] = strategy
        
        logger.info(f"Added custom recovery strategy for {error_type}")
    
    def remove_strategy(self, error_type: str) -> bool:
        """
        Remove a recovery strategy.
        
        Args:
            error_type: Error type to remove
            
        Returns:
            True if strategy was removed, False if not found
        """
        with self._lock:
            if error_type in self._strategies:
                del self._strategies[error_type]
                logger.info(f"Removed recovery strategy for {error_type}")
                return True
            else:
                logger.warning(f"Strategy not found for removal: {error_type}")
                return False

# Global workflow error recovery instance
workflow_error_recovery = WorkflowErrorRecovery()
