"""
Workflow Audit

Provides comprehensive audit trail for workflow operations.
"""

import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading

from flask import current_app, g, request

logger = logging.getLogger(__name__)

class AuditEventType(Enum):
    """Workflow audit event types."""
    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"
    CHECKPOINT_CREATED = "checkpoint_created"
    ROLLBACK_EXECUTED = "rollback_executed"
    RECOVERY_ATTEMPTED = "recovery_attempted"
    INTERVENTION_CREATED = "intervention_created"
    INTERVENTION_UPDATED = "intervention_updated"
    VALIDATION_EXECUTED = "validation_executed"
    STATE_CHANGED = "state_changed"
    ERROR_OCCURRED = "error_occurred"

class AuditSeverity(Enum):
    """Audit event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class WorkflowAuditEvent:
    """Represents a workflow audit event."""
    id: str
    event_type: AuditEventType
    severity: AuditSeverity
    workflow_id: str
    step_id: Optional[str]
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: str
    user_agent: Optional[str]
    details: Dict[str, Any]
    timestamp: datetime
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        return data
    
    def to_json(self) -> str:
        """Convert audit event to JSON string."""
        return json.dumps(self.to_dict(), default=str)

class WorkflowAudit:
    """
    Manages audit trail for workflow operations and compliance.
    """
    
    def __init__(self):
        """Initialize the workflow audit system."""
        self._events = []  # In-memory storage (in production, use database)
        self._correlation_map = {}  # correlation_id -> event_ids
        self._lock = threading.Lock()
        
        # Initialize retention policies
        self._retention_days = current_app.config.get('WORKFLOW_AUDIT_RETENTION_DAYS', 90)
        self._max_events = current_app.config.get('WORKFLOW_AUDIT_MAX_EVENTS', 50000)
    
    def log_event(self, event_type: AuditEventType, severity: AuditSeverity = AuditSeverity.INFO,
                  workflow_id: str = "", step_id: Optional[str] = None,
                  details: Optional[Dict[str, Any]] = None,
                  correlation_id: Optional[str] = None):
        """
        Log a workflow audit event.
        
        Args:
            event_type: Type of audit event
            severity: Event severity level
            workflow_id: Workflow ID
            step_id: Optional step ID
            details: Additional event details
            correlation_id: Optional correlation ID for related events
        """
        # Get request context
        user_id = getattr(g, 'user_id', None) if hasattr(g, 'user_id') else None
        session_id = getattr(g, 'session_id', None) if hasattr(g, 'session_id') else None
        ip_address = getattr(request, 'remote_addr', 'unknown') if request else 'unknown'
        user_agent = getattr(request, 'user_agent', {}).get('string', 'unknown') if request and hasattr(request, 'user_agent') else 'unknown'
        
        # Generate correlation ID if not provided
        if not correlation_id:
            correlation_id = self._generate_correlation_id()
        
        # Create audit event
        event = WorkflowAuditEvent(
            id=self._generate_event_id(),
            event_type=event_type,
            severity=severity,
            workflow_id=workflow_id,
            step_id=step_id,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            timestamp=datetime.utcnow(),
            correlation_id=correlation_id
        )
        
        with self._lock:
            self._events.append(event)
            
            # Update correlation map
            if correlation_id not in self._correlation_map:
                self._correlation_map[correlation_id] = []
            self._correlation_map[correlation_id].append(event.id)
            
            # Cleanup old events
            self._cleanup_old_events()
        
        # Log to system logger for critical events
        if severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]:
            log_level = {
                AuditSeverity.INFO: logger.info,
                AuditSeverity.WARNING: logger.warning,
                AuditSeverity.ERROR: logger.error,
                AuditSeverity.CRITICAL: logger.critical
            }.get(severity, logger.info)
            
            log_level(f"Workflow Audit Event: {event_type.value} - {workflow_id} - {step_id} - {details}")
    
    def log_workflow_created(self, workflow_id: str, workflow_type: str,
                           user_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Log workflow creation event."""
        self.log_event(
            event_type=AuditEventType.WORKFLOW_CREATED,
            severity=AuditSeverity.INFO,
            workflow_id=workflow_id,
            details={
                'workflow_type': workflow_type,
                'user_id': user_id,
                'metadata': metadata or {}
            }
        )
    
    def log_workflow_started(self, workflow_id: str, trigger: str = "manual",
                           metadata: Optional[Dict[str, Any]] = None):
        """Log workflow start event."""
        self.log_event(
            event_type=AuditEventType.WORKFLOW_STARTED,
            severity=AuditSeverity.INFO,
            workflow_id=workflow_id,
            details={
                'trigger': trigger,
                'metadata': metadata or {}
            }
        )
    
    def log_workflow_completed(self, workflow_id: str, duration: Optional[float] = None,
                              result: Optional[Dict[str, Any]] = None):
        """Log workflow completion event."""
        self.log_event(
            event_type=AuditEventType.WORKFLOW_COMPLETED,
            severity=AuditSeverity.INFO,
            workflow_id=workflow_id,
            details={
                'duration_seconds': duration,
                'result': result or {}
            }
        )
    
    def log_workflow_failed(self, workflow_id: str, error: str, error_type: Optional[str] = None,
                           step_id: Optional[str] = None):
        """Log workflow failure event."""
        self.log_event(
            event_type=AuditEventType.WORKFLOW_FAILED,
            severity=AuditSeverity.ERROR,
            workflow_id=workflow_id,
            step_id=step_id,
            details={
                'error': error,
                'error_type': error_type
            }
        )
    
    def log_step_started(self, workflow_id: str, step_id: str, step_type: str,
                       metadata: Optional[Dict[str, Any]] = None):
        """Log step start event."""
        self.log_event(
            event_type=AuditEventType.STEP_STARTED,
            severity=AuditSeverity.INFO,
            workflow_id=workflow_id,
            step_id=step_id,
            details={
                'step_type': step_type,
                'metadata': metadata or {}
            }
        )
    
    def log_step_completed(self, workflow_id: str, step_id: str, duration: float,
                         result: Optional[Dict[str, Any]] = None):
        """Log step completion event."""
        self.log_event(
            event_type=AuditEventType.STEP_COMPLETED,
            severity=AuditSeverity.INFO,
            workflow_id=workflow_id,
            step_id=step_id,
            details={
                'duration_seconds': duration,
                'result': result or {}
            }
        )
    
    def log_step_failed(self, workflow_id: str, step_id: str, error: str,
                       error_type: Optional[str] = None, retry_count: int = 0):
        """Log step failure event."""
        self.log_event(
            event_type=AuditEventType.STEP_FAILED,
            severity=AuditSeverity.ERROR,
            workflow_id=workflow_id,
            step_id=step_id,
            details={
                'error': error,
                'error_type': error_type,
                'retry_count': retry_count
            }
        )
    
    def log_checkpoint_created(self, workflow_id: str, step_id: str, checkpoint_id: str,
                             state_size: int):
        """Log checkpoint creation event."""
        self.log_event(
            event_type=AuditEventType.CHECKPOINT_CREATED,
            severity=AuditSeverity.INFO,
            workflow_id=workflow_id,
            step_id=step_id,
            details={
                'checkpoint_id': checkpoint_id,
                'state_size_bytes': state_size
            }
        )
    
    def log_rollback_event(self, workflow_id: str, rollback_id: str, rollback_type: str,
                          target_checkpoint_id: str, reason: str):
        """Log rollback event."""
        self.log_event(
            event_type=AuditEventType.ROLLBACK_EXECUTED,
            severity=AuditSeverity.WARNING,
            workflow_id=workflow_id,
            details={
                'rollback_id': rollback_id,
                'rollback_type': rollback_type,
                'target_checkpoint_id': target_checkpoint_id,
                'reason': reason
            }
        )
    
    def log_recovery_event(self, workflow_id: str, error_id: str, action: str,
                         details: Optional[Dict[str, Any]] = None):
        """Log recovery event."""
        self.log_event(
            event_type=AuditEventType.RECOVERY_ATTEMPTED,
            severity=AuditSeverity.WARNING,
            workflow_id=workflow_id,
            details={
                'error_id': error_id,
                'action': action,
                'details': details or {}
            }
        )
    
    def log_intervention_event(self, workflow_id: str, intervention_id: str, action: str,
                             details: Optional[Dict[str, Any]] = None):
        """Log intervention event."""
        self.log_event(
            event_type=AuditEventType.INTERVENTION_CREATED if action == 'created' else AuditEventType.INTERVENTION_UPDATED,
            severity=AuditSeverity.WARNING,
            workflow_id=workflow_id,
            details={
                'intervention_id': intervention_id,
                'action': action,
                'details': details or {}
            }
        )
    
    def log_validation_event(self, workflow_id: str, validation_results: List[Dict[str, Any]],
                           step_id: Optional[str] = None):
        """Log validation event."""
        self.log_event(
            event_type=AuditEventType.VALIDATION_EXECUTED,
            severity=AuditSeverity.INFO,
            workflow_id=workflow_id,
            step_id=step_id,
            details={
                'validation_count': len(validation_results),
                'passed_count': len([r for r in validation_results if r.get('status') == 'passed']),
                'failed_count': len([r for r in validation_results if r.get('status') == 'failed']),
                'validation_results': validation_results
            }
        )
    
    def log_state_change(self, workflow_id: str, old_state: str, new_state: str,
                        reason: Optional[str] = None):
        """Log workflow state change."""
        try:
            from app.models.workflow_models import _WORKFLOW_TRANSITIONS

            allowed = _WORKFLOW_TRANSITIONS.get(old_state)
            if allowed is not None and new_state != old_state and new_state not in allowed:
                self.log_event(
                    event_type=AuditEventType.ERROR_OCCURRED,
                    severity=AuditSeverity.ERROR,
                    workflow_id=workflow_id,
                    details={
                        'error': 'Invalid workflow state transition',
                        'old_state': old_state,
                        'new_state': new_state,
                        'allowed_transitions': list(allowed),
                        'reason': reason,
                    }
                )
                return
        except Exception:
            # Audit should not fail closed if transition metadata is unavailable.
            pass

        self.log_event(
            event_type=AuditEventType.STATE_CHANGED,
            severity=AuditSeverity.INFO,
            workflow_id=workflow_id,
            details={
                'old_state': old_state,
                'new_state': new_state,
                'reason': reason
            }
        )
    
    def get_events(self, limit: int = 100, event_type: Optional[AuditEventType] = None,
                   severity: Optional[AuditSeverity] = None, workflow_id: Optional[str] = None,
                   step_id: Optional[str] = None, user_id: Optional[str] = None,
                   correlation_id: Optional[str] = None,
                   time_delta: Optional[timedelta] = None) -> List[Dict[str, Any]]:
        """
        Get audit events with filtering options.
        
        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type
            severity: Filter by severity
            workflow_id: Filter by workflow ID
            step_id: Filter by step ID
            user_id: Filter by user ID
            correlation_id: Filter by correlation ID
            time_delta: Filter by time range
            
        Returns:
            List of audit events
        """
        with self._lock:
            events = self._events.copy()
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        if workflow_id:
            events = [e for e in events if e.workflow_id == workflow_id]
        
        if step_id:
            events = [e for e in events if e.step_id == step_id]
        
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        
        if correlation_id:
            events = [e for e in events if e.correlation_id == correlation_id]
        
        if time_delta:
            cutoff_time = datetime.utcnow() - time_delta
            events = [e for e in events if e.timestamp > cutoff_time]
        
        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [event.to_dict() for event in events[:limit]]
    
    def get_correlation_events(self, correlation_id: str) -> List[Dict[str, Any]]:
        """
        Get all events for a specific correlation ID.
        
        Args:
            correlation_id: Correlation ID to retrieve
            
        Returns:
            List of related events
        """
        return self.get_events(correlation_id=correlation_id, limit=100)
    
    def get_workflow_timeline(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Get complete timeline for a workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Complete workflow timeline
        """
        events = self.get_events(workflow_id=workflow_id, limit=1000)
        
        # Sort by timestamp
        events.sort(key=lambda x: x['timestamp'])
        
        return events
    
    def get_audit_summary(self, time_delta: timedelta = timedelta(days=1)) -> Dict[str, Any]:
        """
        Get audit summary statistics.
        
        Args:
            time_delta: Time period to analyze
            
        Returns:
            Audit summary statistics
        """
        events = self.get_events(limit=10000, time_delta=time_delta)
        
        # Event counts by type
        event_counts = {}
        for event in events:
            event_type = event['event_type']
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Event counts by severity
        severity_counts = {}
        for event in events:
            severity = event['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Workflow activity
        workflow_counts = {}
        for event in events:
            workflow_id = event['workflow_id']
            workflow_counts[workflow_id] = workflow_counts.get(workflow_id, 0) + 1
        
        # User activity
        user_counts = {}
        for event in events:
            user_id = event.get('user_id')
            if user_id:
                user_counts[user_id] = user_counts.get(user_id, 0) + 1
        
        # Top users
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Error events
        error_events = [e for e in events if e['severity'] in ['error', 'critical']]
        
        return {
            'time_period': f"{time_delta.days} days",
            'total_events': len(events),
            'events_by_type': event_counts,
            'events_by_severity': severity_counts,
            'workflow_activity': workflow_counts,
            'user_activity': user_counts,
            'top_users': [{'user': user, 'events': count} for user, count in top_users],
            'error_events': len(error_events),
            'error_rate': len(error_events) / len(events) if events else 0,
            'unique_workflows': len(workflow_counts),
            'unique_users': len(user_counts),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_workflow_statistics(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get statistics for a specific workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Workflow statistics
        """
        events = self.get_events(workflow_id=workflow_id, limit=1000)
        
        if not events:
            return {
                'workflow_id': workflow_id,
                'total_events': 0,
                'duration_seconds': 0,
                'steps_completed': 0,
                'errors_count': 0,
                'interventions_count': 0
            }
        
        # Calculate duration
        start_time = events[0]['timestamp']
        end_time = events[-1]['timestamp']
        
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        duration = (end_dt - start_dt).total_seconds()
        
        # Count events by type
        step_completed = len([e for e in events if e['event_type'] == 'step_completed'])
        errors_count = len([e for e in events if e['severity'] in ['error', 'critical']])
        interventions_count = len([e for e in events if 'intervention' in e['event_type']])
        
        return {
            'workflow_id': workflow_id,
            'total_events': len(events),
            'duration_seconds': duration,
            'steps_completed': step_completed,
            'errors_count': errors_count,
            'interventions_count': interventions_count,
            'start_time': start_time,
            'end_time': end_time,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"audit_{timestamp}_{threading.get_ident()}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
    
    def _generate_correlation_id(self) -> str:
        """Generate unique correlation ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"corr_{timestamp}_{threading.get_ident()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]
    
    def _cleanup_old_events(self):
        """Clean up old audit events based on retention policy."""
        cutoff_time = datetime.utcnow() - timedelta(days=self._retention_days)
        
        # Remove events older than retention period
        original_length = len(self._events)
        self._events = [e for e in self._events if e.timestamp > cutoff_time]
        
        # Remove excess events if over limit
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]
        
        # Clean up correlation map for removed events
        event_ids = {e.id for e in self._events}
        self._correlation_map = {
            corr_id: [eid for eid in event_ids if eid in event_ids]
            for corr_id, event_ids in self._correlation_map.items()
            if any(eid in event_ids for eid in event_ids)
        }
        
        cleaned_count = original_length - len(self._events)
        if cleaned_count > 0:
            logger.debug(f"Cleaned up {cleaned_count} old audit events")

# Global workflow audit instance
workflow_audit = WorkflowAudit()
