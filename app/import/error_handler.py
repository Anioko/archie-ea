"""
Import Error Handler

Provides comprehensive error handling and recovery for import workflows.
"""

import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import threading

from flask import current_app
from app.monitoring.alerting_service import alerting_service, AlertSeverity

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories."""
    VALIDATION_ERROR = "validation_error"
    DATA_FORMAT_ERROR = "data_format_error"
    REFERENTIAL_ERROR = "referential_error"
    BUSINESS_RULE_ERROR = "business_rule_error"
    SYSTEM_ERROR = "system_error"
    NETWORK_ERROR = "network_error"
    PERMISSION_ERROR = "permission_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"

class RecoveryAction(Enum):
    """Recovery action types."""
    RETRY = "retry"
    SKIP_ROW = "skip_row"
    USE_DEFAULT = "use_default"
    MANUAL_INTERVENTION = "manual_intervention"
    ABORT_IMPORT = "abort_import"
    LOG_AND_CONTINUE = "log_and_continue"

@dataclass
class ImportError:
    """Represents an import error."""
    id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    row_number: Optional[int]
    column_name: Optional[str]
    field_value: Optional[str]
    original_exception: Optional[str]
    stack_trace: Optional[str]
    timestamp: datetime
    context: Dict[str, Any]
    recovery_attempts: int
    resolved: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        data = asdict(self)
        data['category'] = self.category.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class RecoveryStrategy:
    """Represents a recovery strategy for an error."""
    category: ErrorCategory
    severity: ErrorSeverity
    action: RecoveryAction
    max_attempts: int
    retry_delay: float
    conditions: Dict[str, Any]
    handler: Optional[Callable]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert strategy to dictionary."""
        return {
            'category': self.category.value,
            'severity': self.severity.value,
            'action': self.action.value,
            'max_attempts': self.max_attempts,
            'retry_delay': self.retry_delay,
            'conditions': self.conditions,
            'has_handler': self.handler is not None
        }

class ImportErrorHandler:
    """
    Handles errors during import workflows with recovery strategies.
    """
    
    def __init__(self):
        """Initialize the import error handler."""
        self._errors = []  # error_id -> ImportError
        self._strategies = {}
        self._error_counts = {}  # category -> count
        self._recovery_history = {}  # error_id -> recovery attempts
        self._lock = threading.Lock()
        
        # Initialize default recovery strategies
        self._initialize_default_strategies()
        
        # Load custom strategies from configuration
        self._load_custom_strategies()
        
        # Start error cleanup
        self._start_error_cleanup()
    
    def _initialize_default_strategies(self):
        """Initialize default recovery strategies."""
        self._strategies = {
            # Validation errors
            (ErrorCategory.VALIDATION_ERROR, ErrorSeverity.LOW): RecoveryStrategy(
                category=ErrorCategory.VALIDATION_ERROR,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.USE_DEFAULT,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.VALIDATION_ERROR, ErrorSeverity.MEDIUM): RecoveryStrategy(
                category=ErrorCategory.VALIDATION_ERROR,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.SKIP_ROW,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.VALIDATION_ERROR, ErrorSeverity.HIGH): RecoveryStrategy(
                category=ErrorCategory.VALIDATION_ERROR,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.MANUAL_INTERVENTION,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            
            # Data format errors
            (ErrorCategory.DATA_FORMAT_ERROR, ErrorSeverity.LOW): RecoveryStrategy(
                category=ErrorCategory.DATA_FORMAT_ERROR,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.USE_DEFAULT,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.DATA_FORMAT_ERROR, ErrorSeverity.MEDIUM): RecoveryStrategy(
                category=ErrorCategory.DATA_FORMAT_ERROR,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.SKIP_ROW,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.DATA_FORMAT_ERROR, ErrorSeverity.HIGH): RecoveryStrategy(
                category=ErrorCategory.DATA_FORMAT_ERROR,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.MANUAL_INTERVENTION,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            
            # Referential errors
            (ErrorCategory.REFERENTIAL_ERROR, ErrorSeverity.LOW): RecoveryStrategy(
                category=ErrorCategory.REFERENTIAL_ERROR,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.USE_DEFAULT,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.REFERENTIAL_ERROR, ErrorSeverity.MEDIUM): RecoveryStrategy(
                category=ErrorCategory.REFERENTIAL_ERROR,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.SKIP_ROW,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.REFERENTIAL_ERROR, ErrorSeverity.HIGH): RecoveryStrategy(
                category=ErrorCategory.REFERENTIAL_ERROR,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.MANUAL_INTERVENTION,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            
            # Business rule errors
            (ErrorCategory.BUSINESS_RULE_ERROR, ErrorSeverity.LOW): RecoveryStrategy(
                category=ErrorCategory.BUSINESS_RULE_ERROR,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.USE_DEFAULT,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.BUSINESS_RULE_ERROR, ErrorSeverity.MEDIUM): RecoveryStrategy(
                category=ErrorCategory.BUSINESS_RULE_ERROR,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.SKIP_ROW,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.BUSINESS_RULE_ERROR, ErrorSeverity.HIGH): RecoveryStrategy(
                category=ErrorCategory.BUSINESS_RULE_ERROR,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.MANUAL_INTERVENTION,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            
            # System errors
            (ErrorCategory.SYSTEM_ERROR, ErrorSeverity.LOW): RecoveryStrategy(
                category=ErrorCategory.SYSTEM_ERROR,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.LOG_AND_CONTINUE,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.SYSTEM_ERROR, ErrorSeverity.MEDIUM): RecoveryStrategy(
                category=ErrorCategory.SYSTEM_ERROR,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.RETRY,
                max_attempts=3,
                retry_delay=5.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.SYSTEM_ERROR, ErrorSeverity.HIGH): RecoveryStrategy(
                category=ErrorCategory.SYSTEM_ERROR,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.ABORT_IMPORT,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            
            # Network errors
            (ErrorCategory.NETWORK_ERROR, ErrorSeverity.LOW): RecoveryStrategy(
                category=ErrorCategory.NETWORK_ERROR,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.RETRY,
                max_attempts=5,
                retry_delay=10.0,
                conditions={'backoff_multiplier': 2},
                handler=None
            ),
            (ErrorCategory.NETWORK_ERROR, ErrorSeverity.MEDIUM): RecoveryStrategy(
                category=ErrorCategory.NETWORK_ERROR,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.RETRY,
                max_attempts=3,
                retry_delay=15.0,
                conditions={'backoff_multiplier': 2},
                handler=None
            ),
            (ErrorCategory.NETWORK_ERROR, ErrorSeverity.HIGH): RecoveryStrategy(
                category=ErrorCategory.NETWORK_ERROR,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.ABORT_IMPORT,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            
            # Timeout errors
            (ErrorCategory.TIMEOUT_ERROR, ErrorSeverity.LOW): RecoveryStrategy(
                category=ErrorCategory.TIMEOUT_ERROR,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.RETRY,
                max_attempts=3,
                retry_delay=5.0,
                conditions={'increase_timeout': True},
                handler=None
            ),
            (ErrorCategory.TIMEOUT_ERROR, ErrorSeverity.MEDIUM): RecoveryStrategy(
                category=ErrorCategory.TIMEOUT_ERROR,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.RETRY,
                max_attempts=2,
                retry_delay=10.0,
                conditions={'increase_timeout': True},
                handler=None
            ),
            (ErrorCategory.TIMEOUT_ERROR, ErrorSeverity.HIGH): RecoveryStrategy(
                category=ErrorCategory.TIMEOUT_ERROR,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.ABORT_IMPORT,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            
            # Permission errors
            (ErrorCategory.PERMISSION_ERROR, ErrorSeverity.LOW): RecoveryStrategy(
                category=ErrorCategory.PERMISSION_ERROR,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.SKIP_ROW,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.PERMISSION_ERROR, ErrorSeverity.MEDIUM): RecoveryStrategy(
                category=ErrorCategory.PERMISSION_ERROR,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.MANANUAL_INTERVENTION,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.PERMISSION_ERROR, ErrorSeverity.HIGH): RecoveryStrategy(
                category=ErrorCategory.PERMISSION_ERROR,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.ABORT_IMPORT,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            
            # Unknown errors
            (ErrorCategory.UNKNOWN_ERROR, ErrorSeverity.LOW): RecoveryStrategy(
                category=ErrorCategory.UNKNOWN_ERROR,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.LOG_AND_CONTINUE,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.UNKNOWN_ERROR, ErrorSeverity.MEDIUM): RecoveryStrategy(
                category=ErrorCategory.UNKNOWN_ERROR,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.SKIP_ROW,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            ),
            (ErrorCategory.UNKNOWN_ERROR, ErrorSeverity.HIGH): RecoveryStrategy(
                category=ErrorCategory.UNKNOWN_ERROR,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.MANUAL_INTERVENTION,
                max_attempts=1,
                retry_delay=0.0,
                conditions={},
                handler=None
            )
        }
    
    def _load_custom_strategies(self):
        """Load custom recovery strategies from configuration."""
        try:
            custom_strategies = current_app.config.get('IMPORT_ERROR_STRATEGIES', {})
            
            for strategy_config in custom_strategies:
                try:
                    category = ErrorCategory(strategy_config['category'])
                    severity = ErrorSeverity(strategy_config['severity'])
                    action = RecoveryAction(strategy_config['action'])
                    
                    strategy = RecoveryStrategy(
                        category=category,
                        severity=severity,
                        action=action,
                        max_attempts=strategy_config.get('max_attempts', 3),
                        retry_delay=strategy_config.get('retry_delay', 5.0),
                        conditions=strategy_config.get('conditions', {}),
                        handler=None  # Custom handlers would be implemented separately
                    )
                    
                    self._strategies[(category, severity)] = strategy
                    logger.info(f"Added custom error strategy: {category.value} - {severity.value}")
                    
                except Exception as e:
                    logger.warning(f"Failed to load custom strategy: {e}")
                    
        except Exception as e:
            logger.warning(f"Failed to load custom strategies: {e}")
    
    def handle_error(self, exception: Exception, row_number: Optional[int] = None,
                    column_name: Optional[str] = None, field_value: Optional[str] = None,
                    context: Optional[Dict[str, Any]] = None) -> ImportError:
        """
        Handle an import error and determine recovery action.
        
        Args:
            exception: The exception that occurred
            row_number: Row number where error occurred
            column_name: Column name where error occurred
            field_value: Field value that caused the error
            context: Additional context information
            
        Returns:
            ImportError object
        """
        # Categorize the error
        category = self._categorize_error(exception)
        severity = self._determine_severity(exception, category)
        
        # Create error object
        error = ImportError(
            id=self._generate_error_id(),
            category=category,
            severity=severity,
            message=str(exception),
            row_number=row_number,
            column_name=column_name,
            field_value=field_value,
            original_exception=type(exception).__name__,
            stack_trace=traceback.format_exc(),
            timestamp=datetime.utcnow(),
            context=context or {},
            recovery_attempts=0,
            resolved=False
        )
        
        with self._lock:
            self._errors[error.id] = error
            self._error_counts[category] = self._error_counts.get(category, 0) + 1
        
        # Log the error
        log_level = {
            ErrorSeverity.LOW: logger.info,
            ErrorSeverity.MEDIUM: logger.warning,
            ErrorSeverity.HIGH: logger.error,
            ErrorSeverity.CRITICAL: logger.critical
        }.get(severity, logger.info)
        
        log_level(f"Import error: {category.value} - {severity.value} - {str(exception)}")
        
        # Send alert for critical errors
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self._send_error_alert(error)
        
        return error
    
    def attempt_recovery(self, error: ImportError, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Attempt to recover from an error using the appropriate strategy.
        
        Args:
            error: The import error to recover from
            context: Additional context for recovery
            
        Returns:
            Recovery result
        """
        strategy = self._get_recovery_strategy(error.category, error.severity)
        
        if not strategy:
            return {
                'success': False,
                'action': 'no_strategy',
                'message': 'No recovery strategy available',
                'error_id': error.id
            }
        
        # Check if max attempts exceeded
        if error.recovery_attempts >= strategy.max_attempts:
            return {
                'success': False,
                'action': 'max_attempts_exceeded',
                'message': f"Maximum recovery attempts ({strategy.max_attempts}) exceeded",
                'error_id': error.id
            }
        
        # Increment recovery attempts
        with self._lock:
            error.recovery_attempts += 1
            self._recovery_history[error.id] = self._recovery_history.get(error.id, [])
            self._recovery_history[error.id].append({
                'attempt': error.recovery_attempts,
                'action': strategy.action.value,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Execute recovery action
        try:
            if strategy.action == RecoveryAction.RETRY:
                return self._retry_recovery(error, strategy, context)
            elif strategy.action == RecoveryAction.SKIP_ROW:
                return self._skip_row_recovery(error, strategy, context)
            elif strategy.action == RecoveryAction.USE_DEFAULT:
                return self._use_default_recovery(error, strategy, context)
            elif strategy.action == RecoveryAction.MANUAL_INTERVENTION:
                return self._manual_intervention_recovery(error, strategy, context)
            elif strategy.action == RecoveryAction.ABORT_IMPORT:
                return self._abort_import_recovery(error, strategy, context)
            elif strategy.action == RecoveryAction.LOG_AND_CONTINUE:
                return self._log_and_continue_recovery(error, strategy, context)
            else:
                return {
                    'success': False,
                    'action': 'unknown_action',
                    'message': f"Unknown recovery action: {strategy.action.value}",
                    'error_id': error.id
                }
                
        except Exception as e:
            logger.error(f"Recovery action {strategy.action.value} failed: {e}")
            return {
                'success': False,
                'action': 'recovery_failed',
                'message': f"Recovery failed: {str(e)}",
                'error_id': error.id
            }
    
    def _get_recovery_strategy(self, category: ErrorCategory, severity: ErrorSeverity) -> Optional[RecoveryStrategy]:
        """Get recovery strategy for error category and severity."""
        return self._strategies.get((category, severity))
    
    def _categorize_error(self, exception: Exception) -> ErrorCategory:
        """Categorize an exception."""
        exception_type = type(exception).__name__
        exception_message = str(exception).lower()
        
        # Check for specific error types
        if 'validation' in exception_type.lower() or 'value' in exception_type.lower():
            return ErrorCategory.VALIDATION_ERROR
        elif 'format' in exception_type.lower() or 'parse' in exception_type.lower():
            return ErrorCategory.DATA_FORMAT_ERROR
        elif 'reference' in exception_type.lower() or 'foreign' in exception_type.lower():
            return ErrorCategory.REFERENTIAL_ERROR
        elif 'permission' in exception_type.lower() or 'access' in exception_type.lower():
            return ErrorCategory.PERMISSION_ERROR
        elif 'timeout' in exception_type.lower() or 'timed out' in exception_message:
            return ErrorCategory.TIMEOUT_ERROR
        elif 'network' in exception_type.lower() or 'connection' in exception_type.lower():
            return ErrorCategory.NETWORK_ERROR
        elif 'database' in exception_type.lower() or 'db' in exception_type.lower():
            return ErrorCategory.SYSTEM_ERROR
        
        return ErrorCategory.UNKNOWN_ERROR
    
    def _determine_severity(self, exception: Exception, category: ErrorCategory) -> ErrorSeverity:
        """Determine error severity."""
        exception_type = type(exception).__name__
        
        # Critical errors
        if any(keyword in exception_type.lower() for keyword in ['critical', 'fatal', 'security']):
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if category in [ErrorCategory.PERMISSION_ERROR, ErrorCategory.SYSTEM_ERROR]:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if category in [ErrorCategory.REFERENTIAL_ERROR, ErrorCategory.BUSINESS_RULE_ERROR]:
            return ErrorSeverity.MEDIUM
        
        # Low severity errors
        if category in [ErrorCategory.VALIDATION_ERROR, ErrorCategory.DATA_FORMAT_ERROR]:
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM
    
    def _retry_recovery(self, error: ImportError, strategy: RecoveryStrategy, 
                        context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Attempt retry recovery."""
        retry_delay = strategy.retry_delay
        
        # Apply backoff if configured
        if strategy.conditions.get('backoff_multiplier'):
            retry_delay *= (strategy.conditions['backoff_multiplier'] ** (error.recovery_attempts - 1))
        
        return {
            'success': True,
            'action': 'retry',
            'message': f"Retry recommended after {retry_delay}s",
            'error_id': error.id,
            'retry_delay': retry_delay,
            'attempt': error.recovery_attempts
        }
    
    def _skip_row_recovery(self, error: ImportError, strategy: RecoveryStrategy, 
                          context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Skip row recovery."""
        return {
            'success': True,
            'action': 'skip_row',
            'message': f"Row {error.row_number} skipped due to error",
            'error_id': error.id,
            'skipped_row': error.row_number
        }
    
    def _use_default_recovery(self, error: ImportError, strategy: RecoveryStrategy, 
                             context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Use default value recovery."""
        default_value = self._get_default_value(error.column_name, context)
        
        return {
            'success': True,
            'action': 'use_default',
            'message': f"Using default value for {error.column_name}: {default_value}",
            'error_id': error.id,
            'default_value': default_value,
            'column': error.column_name
        }
    
    def _manual_intervention_recovery(self, error: ImportError, strategy: RecoveryStrategy, 
                                    context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Manual intervention recovery."""
        # Create manual intervention request
        intervention_id = self._create_intervention_request(error)
        
        return {
            'success': True,
            'action': 'manual_intervention',
            'message': f"Manual intervention required: {intervention_id}",
            'error_id': error.id,
            'intervention_id': intervention_id
        }
    
    def _abort_import_recovery(self, error: ImportError, strategy: RecoveryStrategy, 
                             context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Abort import recovery."""
        return {
            'success': True,
            'action': 'abort_import',
            'message': f"Import aborted due to {error.category.value} error",
            'error_id': error.id
        }
    
    def _log_and_continue_recovery(self, error: ImportError, strategy: RecoveryStrategy, 
                                  context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Log and continue recovery."""
        return {
            'success': True,
            'action': 'log_and_continue',
            'message': f"Error logged, continuing with import",
            'error_id': error.id
        }
    
    def _get_default_value(self, column_name: str, context: Optional[Dict[str, Any]]) -> str:
        """Get default value for a column."""
        # This would be implemented based on business rules
        defaults = {
            'status': 'pending',
            'priority': 'medium',
            'active': 'true',
            'created_date': datetime.utcnow().strftime('%Y-%m-%d')
        }
        
        return defaults.get(column_name, '')
    
    def _create_intervention_request(self, error: ImportError) -> str:
        """Create a manual intervention request."""
        # This would integrate with the workflow manual intervention system
        intervention_id = f"intervention_{error.id}"
        
        # Log intervention request
        logger.warning(f"Manual intervention requested: {intervention_id} for error {error.id}")
        
        return intervention_id
    
    def _send_error_alert(self, error: ImportError):
        """Send alert for critical errors."""
        try:
            alerting_service.create_manual_alert(
                name=f"import_error_{error.id}",
                severity=AlertSeverity.CRITICAL if error.severity == ErrorSeverity.CRITICAL else AlertSeverity.WARNING,
                message=f"Critical import error: {error.message}",
                source='import_error_handler',
                metadata={
                    'error_id': error.id,
                    'category': error.category.value,
                    'severity': error.severity.value,
                    'row_number': error.row_number,
                    'column_name': error.column_name
                }
            )
        except Exception as e:
            logger.error(f"Failed to send error alert: {e}")
    
    def get_error_history(self, limit: int = 100, category: Optional[ErrorCategory] = None,
                         severity: Optional[ErrorSeverity] = None,
                         time_delta: Optional[timedelta] = None) -> List[Dict[str, Any]]:
        """
        Get error history with filtering options.
        
        Args:
            limit: Maximum number of errors to return
            category: Filter by error category
            severity: Filter by error severity
            time_delta: Filter by time range
            
        Returns:
            List of error records
        """
        with self._lock:
            errors = list(self._errors.values())
        
        # Apply filters
        if category:
            errors = [e for e in errors if e.category == category]
        
        if severity:
            errors = [e for e in errors if e.severity == severity]
        
        if time_delta:
            cutoff_time = datetime.utcnow() - time_delta
            errors = [e for e in errors if e.timestamp > cutoff_time]
        
        # Sort by timestamp (newest first) and limit
        errors.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [error.to_dict() for error in errors[:limit]]
    
    def get_error_statistics(self, time_delta: timedelta = timedelta(days=7)) -> Dict[str, Any]:
        """
        Get error statistics.
        
        Args:
            time_delta: Time period to analyze
            
        Returns:
            Error statistics
        """
        cutoff_time = datetime.utcnow() - time_delta
        
        with self._lock:
            recent_errors = [e for e in self._errors.values() if e.timestamp > cutoff_time]
        
        if not recent_errors:
            return {
                'time_period': f"{time_delta.days} days",
                'total_errors': 0,
                'error_counts': {},
                'severity_distribution': {},
                'category_distribution': {},
                'recovery_success_rate': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Calculate statistics
        total_errors = len(recent_errors)
        
        # Error counts by category
        category_counts = {}
        for error in recent_errors:
            category = error.category.value
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Severity distribution
        severity_counts = {}
        for error in recent_errors:
            severity = error.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Recovery success rate
        recovered_errors = len([e for e in recent_errors if e.resolved])
        recovery_success_rate = recovered_errors / total_errors if total_errors > 0 else 0
        
        return {
            'time_period': f"{time_delta.days} days",
            'total_errors': total_errors,
            'error_counts': category_counts,
            'severity_distribution': severity_counts,
            'recovery_success_rate': recovery_success_rate,
            'recovered_errors': recovered_errors,
            'unresolved_errors': total_errors - recovered_errors,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _start_error_cleanup(self):
        """Start background task to clean up old errors."""
        # In a real implementation, this would use a proper background task scheduler
        logger.info("Error cleanup task started")
    
    def _cleanup_old_errors(self):
        """Clean up old error records."""
        retention_days = current_app.config.get('IMPORT_ERROR_RETENTION_DAYS', 30)
        cutoff_time = datetime.utcnow() - timedelta(days=retention_days)
        
        with self._lock:
            original_count = len(self._errors)
            self._errors = {eid: error for eid, error in self._errors.items() if error.timestamp > cutoff_time}
            
            # Clean up recovery history
            self._recovery_history = {
                eid: history for eid, history in self._recovery_history.items()
                if any(datetime.fromisoformat(attempt['timestamp']) > cutoff_time for attempt in history)
            }
            
            cleaned_count = original_count - len(self._errors)
            
            if cleaned_count > 0:
                logger.debug(f"Cleaned up {cleaned_count} old import errors")
    
    def _generate_error_id(self) -> str:
        """Generate unique error ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"error_{timestamp}_{threading.get_ident()}"
        return data
    
    def add_custom_strategy(self, category: ErrorCategory, severity: ErrorSeverity,
                           action: RecoveryAction, max_attempts: int = 3,
                           retry_delay: float = 5.0, conditions: Optional[Dict[str, Any]] = None):
        """Add a custom recovery strategy."""
        strategy = RecoveryStrategy(
            category=category,
            severity=severity,
            action=action,
            max_attempts=max_attempts,
            retry_delay=retry_delay,
            conditions=conditions or {},
            handler=None
        )
        
        with self._lock:
            self._strategies[(category, severity)] = strategy
        
        logger.info(f"Added custom recovery strategy: {category.value} - {severity.value} - {action.value}")
    
    def remove_strategy(self, category: ErrorCategory, severity: ErrorSeverity) -> bool:
        """Remove a recovery strategy."""
        with self._lock:
            if (category, severity) in self._strategies:
                del self._strategies[(category, severity)]
                logger.info(f"Removed recovery strategy: {category.value} - {severity.value}")
                return True
            return False

# Global import error handler instance
import_error_handler = ImportErrorHandler()
