"""
Import Audit

Provides comprehensive audit trail for import operations.
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

class ImportAuditEventType(Enum):
    """Import audit event types."""
    IMPORT_STARTED = "import_started"
    IMPORT_COMPLETED = "import_completed"
    IMPORT_FAILED = "import_failed"
    IMPORT_CANCELLED = "import_cancelled"
    IMPORT_ROLLBACK = "import_rollback"
    ROW_PROCESSED = "row_processed"
    ROW_FAILED = "row_failed"
    ROW_SKIPPED = "row_skipped"
    VALIDATION_FAILED = "validation_failed"
    DUPLICATE_FOUND = "duplicate_found"
    ERROR_OCCURRED = "error_occurred"
    ROLLBACK_EXECUTED = "rollback_executed"
    MANUAL_INTERVENTION = "manual_intervention"

class ImportAuditSeverity(Enum):
    """Import audit severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ImportAuditEvent:
    """Represents an import audit event."""
    id: str
    event_type: ImportAuditEventType
    severity: ImportAuditSeverity
    import_id: str
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
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert audit event to JSON string."""
        return json.dumps(self.to_dict(), default=str)

class ImportAudit:
    """
    Manages audit trail for import operations and compliance.
    """
    
    def __init__(self):
        """Initialize the import audit system."""
        self._events = []  # In-memory storage (in production, use database)
        self._correlation_map = {}  # correlation_id -> event_ids
        self._lock = threading.Lock()
        
        # Initialize retention policies
        self._retention_days = current_app.config.get('IMPORT_AUDIT_RETENTION_DAYS', 90)
        self._max_events = current_app.config.get('IMPORT_AUDIT_MAX_EVENTS', 50000)
        
        # Start cleanup
        self._start_cleanup()
    
    def log_event(self, event_type: ImportAuditEventType, import_id: str,
                  severity: ImportAuditSeverity = ImportAuditSeverity.INFO,
                  user_id: Optional[str] = None,
                  details: Optional[Dict[str, Any]] = None,
                  correlation_id: Optional[str] = None):
        """
        Log an import audit event.
        
        Args:
            event_type: Type of audit event
            severity: Event severity level
            import_id: Import session ID
            user_id: Optional user ID
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
        event = ImportAuditEvent(
            id=self._generate_event_id(),
            event_type=event_type,
            severity=severity,
            import_id=import_id,
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
        if severity in [ImportAuditSeverity.ERROR, ImportAuditSeverity.CRITICAL]:
            log_level = {
                ImportAuditSeverity.INFO: logger.info,
                ImportAuditSeverity.WARNING: logger.warning,
                ImportAuditSeverity.ERROR: logger.error,
                ImportAuditSeverity.CRITICAL: logger.critical
            }.get(severity, logger.info)
            
            log_level(f"Import Audit Event: {event_type.value} - {import_id} - {details}")
        
        # Check for compliance alerts
        self._check_compliance_alerts(event)
    
    def log_import_started(self, import_id: str, import_type: str, file_count: int,
                           user_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Log import start event."""
        self.log_event(
            event_type=ImportAuditEventType.IMPORT_STARTED,
            severity=ImportAuditSeverity.INFO,
            import_id=import_id,
            user_id=user_id,
            details={
                'import_type': import_type,
                'file_count': file_count,
                'metadata': metadata or {}
            }
        )
    
    def log_import_completed(self, import_id: str, duration: float, records_processed: int,
                            records_failed: int, records_skipped: int,
                            user_id: Optional[str] = None,
                            metadata: Optional[Dict[str, Any]] = None):
        """Log import completion event."""
        self.log_event(
            event_type=ImportAuditEventType.IMPORT_COMPLETED,
            severity=ImportAuditSeverity.INFO,
            import_id=import_id,
            user_id=user_id,
            details={
                'duration_seconds': duration,
                'records_processed': records_processed,
                'records_failed': records_failed,
                'records_skipped': records_skipped,
                'success_rate': (records_processed - records_failed - records_skipped) / records_processed if records_processed > 0 else 0,
                'metadata': metadata or {}
            }
        )
    
    def log_import_failed(self, import_id: str, error: str, records_processed: int,
                          error_type: Optional[str] = None,
                          user_id: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None):
        """Log import failure event."""
        self.log_event(
            event_type=ImportAuditEventType.IMPORT_FAILED,
            severity=ImportAuditSeverity.ERROR,
            import_id=import_id,
            user_id=user_id,
            details={
                'error': error,
                'error_type': error_type,
                'records_processed': records_processed,
                'metadata': metadata or {}
            }
        )
    
    def log_import_cancelled(self, import_id: str, reason: str, records_processed: int,
                            user_id: Optional[str] = None,
                            metadata: Optional[Dict[str, Any]] = None):
        """Log import cancellation event."""
        self.log_event(
            event_type=ImportAuditEventType.IMPORT_CANCELLED,
            severity=ImportAuditSeverity.WARNING,
            import_id=import_id,
            user_id=user_id,
            details={
                'reason': reason,
                'records_processed': records_processed,
                'metadata': metadata or {}
            }
        )
    
    def log_import_rollback(self, import_id: str, rollback_type: str, reason: str,
                           records_affected: int, user_id: Optional[str] = None,
                           metadata: Optional[Dict[str, Any]] = None):
        """Log import rollback event."""
        self.log_event(
            event_type=ImportAuditEventType.IMPORT_ROLLBACK,
            severity=ImportAuditSeverity.WARNING,
            import_id=import_id,
            user_id=user_id,
            details={
                'rollback_type': rollback_type,
                'reason': reason,
                'records_affected': records_affected,
                'metadata': metadata or {}
            }
        )
    
    def log_row_processed(self, import_id: str, row_number: int, row_data: Dict[str, Any],
                         user_id: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None):
        """Log row processed event."""
        self.log_event(
            event_type=ImportAuditEventType.ROW_PROCESSED,
            severity=ImportAuditSeverity.INFO,
            import_id=import_id,
            user_id=user_id,
            details={
                'row_number': row_number,
                'row_data': row_data,
                'metadata': metadata or {}
            }
        )
    
    def log_row_failed(self, import_id: str, row_number: int, error: str,
                       error_type: Optional[str] = None, row_data: Optional[Dict[str, Any]] = None,
                       user_id: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None):
        """Log row failure event."""
        self.log_event(
            event_type=ImportAuditEventType.ROW_FAILED,
            severity=ImportAuditSeverity.ERROR,
            import_id=import_id,
            user_id=user_id,
            details={
                'row_number': row_number,
                'error': error,
                'error_type': error_type,
                'row_data': row_data,
                'metadata': metadata or {}
            }
        )
    
    def log_row_skipped(self, import_id: str, row_number: int, reason: str,
                       row_data: Optional[Dict[str, Any]] = None,
                       user_id: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None):
        """Log row skipped event."""
        self.log_event(
            event_type=ImportAuditEventType.ROW_SKIPPED,
            severity=ImportAuditSeverity.WARNING,
            import_id=import_id,
            user_id=user_id,
            details={
                'row_number': row_number,
                'reason': reason,
                'row_data': row_data,
                'metadata': metadata or {}
            }
        )
    
    def log_validation_failed(self, import_id: str, validation_errors: List[Dict[str, Any]],
                            user_id: Optional[str] = None):
        """Log validation failure event."""
        self.log_event(
            event_type=ImportAuditEventType.VALIDATION_FAILED,
            severity=ImportAuditSeverity.ERROR,
            import_id=import_id,
            user_id=user_id,
            details={
                'validation_errors': validation_errors,
                'error_count': len(validation_errors)
            }
        )
    
    def log_duplicate_found(self, import_id: str, duplicate_info: Dict[str, Any],
                           user_id: Optional[str] = None):
        """Log duplicate found event."""
        self.log_event(
            event_type=ImportAuditEventType.DUPLICATE_FOUND,
            severity=ImportAuditEventType.WARNING,
            import_id=import_id,
            user_id=user_id,
            details={
                'duplicate_info': duplicate_info
            }
        )
    
    def log_error_occurred(self, import_id: str, error: str, context: Optional[Dict[str, Any]] = None,
                        user_id: Optional[str] = None):
        """Log error occurred event."""
        self.log_event(
            event_type=ImportAuditEventType.ERROR_OCCURRED,
            severity=ImportAuditSeverity.ERROR,
            import_id=import_id,
            user_id=user_id,
            details={
                'error': error,
                'context': context or {}
            }
        )
    
    def log_rollback_executed(self, import_id: str, rollback_type: str, reason: str,
                             records_affected: int, user_id: Optional[str] = None):
        """Log rollback executed event."""
        self.log_event(
            event_type=ImportAuditEventType.ROLLBACK_EXECUTED,
            severity=ImportAuditEventType.WARNING,
            import_id=import_id,
            user_id=user_id,
            details={
                'rollback_type': rollback_type,
                'reason': reason,
                'records_affected': records_affected
            }
        )
    
    def log_manual_intervention(self, import_id: str, intervention_type: str, reason: str,
                                user_id: Optional[str] = None):
        """Log manual intervention event."""
        self.log_event(
            event_type=ImportAuditEventType.MANUAL_INTERVENTION,
            severity=ImportAuditEventType.WARNING,
            import_id=import_id,
            user_id=user_id,
            details={
                'intervention_type': intervention_type,
                'reason': reason
            }
        )
    
    def get_events(self, limit: int = 100, event_type: Optional[ImportAuditEventType] = None,
                   severity: Optional[ImportAuditSeverity] = None, import_id: Optional[str] = None,
                   user_id: Optional[str] = None, correlation_id: Optional[str] = None,
                   time_delta: Optional[timedelta] = None) -> List[Dict[str, Any]]:
        """
        Get import audit events with filtering options.
        
        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type
            severity: Filter by severity
            import_id: Filter by import ID
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
        
        if import_id:
            events = [e for e in events if e.import_id == import_id]
        
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
    
    def get_import_timeline(self, import_id: str) -> List[Dict[str, Any]]:
        """
        Get complete timeline for an import.
        
        Args:
            import_id: Import ID
            
        Returns:
            Complete import timeline
        """
        events = self.get_events(import_id=import_id, limit=1000)
        
        # Sort by timestamp
        events.sort(key=lambda x: x['timestamp'])
        
        return events
    
    def get_import_summary(self, import_id: str) -> Dict[str, Any]:
        """
        Get summary for a specific import.
        
        Args:
            import_id: Import ID
            
        Returns:
            Import summary statistics
        """
        events = self.get_events(import_id=import_id, limit=1000)
        
        if not events:
            return {
                'import_id': import_id,
                'total_events': 0,
                'duration_seconds': 0,
                'rows_processed': 0,
                'rows_failed': 0,
                'rows_skipped': 0,
                'validation_errors': 0,
                'duplicates_found': 0,
                'manual_interventions': 0,
                'rollbacks_executed': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Calculate statistics
        total_events = len(events)
        
        # Get import duration
        start_event = next((e for e in events if e['event_type'] == 'import_started'), None)
        end_event = next((e for e in events if e['event_type'] == 'import_completed'), None)
        
        duration_seconds = 0
        if start_event and end_event:
            start_time = datetime.fromisoformat(start_event['timestamp'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_event['timestamp'].replace('event_type', '+00:00'))
            duration_seconds = (end_time - start_time).total_seconds()
        
        # Count event types
        event_counts = {}
        for event in events:
            event_type = event['event_type']
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Count row events
        row_processed = len([e for e in events if e['event_type'] == 'row_processed'])
        row_failed = len([e for e in events if e['event_type'] == 'row_failed'])
        row_skipped = len([e for e in events if e['event_type'] == 'row_skipped'])
        
        # Count validation errors
        validation_errors = len([e for e in events if e['event_type'] == 'validation_failed'])
        
        # Count duplicates
        duplicates_found = len([e for e in events if e['event_type'] == 'duplicate_found'])
        
        # Count manual interventions
        manual_interventions = len([e for e in events if e['event_type'] == 'manual_intervention'])
        
        # Count rollbacks
        rollbacks_executed = len([e for e in events if e['event_type'] == 'rollback_executed'])
        
        return {
            'import_id': import_id,
            'total_events': total_events,
            'duration_seconds': duration_seconds,
            'rows_processed': row_processed,
            'rows_failed': row_failed,
            'rows_skipped': row_skipped,
            'validation_errors': validation_errors,
            'duplicates_found': duplicates_found,
            'manual_interventions': manual_interventions,
            'rollbacks_executed': rollbacks_executed,
            'event_counts': event_counts,
            'start_time': start_event['timestamp'] if start_event else None,
            'end_time': end_event['timestamp'] if end_event else None,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_audit_summary(self, time_delta: timedelta = timedelta(days=1)) -> Dict[str, Any]:
        """
        Get import audit summary statistics.
        
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
        
        # Import activity
        import_counts = {}
        for event in events:
            import_id = event['import_id']
            import_counts[import_id] = import_counts.get(import_id, 0) + 1
        
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
        
        # Manual interventions
        intervention_events = [e for e in events if e['event_type'] == 'manual_intervention']
        
        # Rollback events
        rollback_events = [e for e in events if e['event_type'] == 'rollback_executed']
        
        return {
            'time_period': f"{time_delta.days} days",
            'total_events': len(events),
            'events_by_type': event_counts,
            'events_by_severity': severity_counts,
            'import_activity': import_counts,
            'user_activity': user_counts,
            'top_users': [{'user': user, 'events': count} for user, count in top_users],
            'error_events': len(error_events),
            'error_rate': len(error_events) / len(events) if events else 0,
            'manual_interventions': len(intervention_events),
            'rollback_events': len(rollback_events),
            'unique_imports': len(import_counts),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _check_compliance_alerts(self, event: ImportAuditEvent):
        """Check for compliance alerts and send notifications."""
        try:
            # Check for critical errors that require immediate attention
            if event.severity == ImportAuditSeverity.CRITICAL:
                from app.monitoring.alerting_service import alerting_service, AlertSeverity
                
                alerting_service.create_manual_alert(
                    name=f"import_critical_{event.import_id}_{event.id}",
                    severity=AlertSeverity.CRITICAL,
                    message=f"Critical import error: {event.import_id} - {event.details}",
                    source='import_audit',
                    metadata={
                        'event_id': event.id,
                        'import_id': event.import_id,
                        'event_type': event.event_type.value,
                        'user_id': event.user_id,
                        'severity': event.severity.value
                    }
                )
            
            # Check for high error rates
            if event.event_type == ImportAuditEventType.IMPORT_FAILED:
                # Check if this is part of a pattern of failures
                recent_failures = self._get_recent_import_failures(event.import_id, timedelta(hours=1))
                
                if len(recent_failures) >= 5:
                    alerting_service.create_manual_alert(
                        name=f"import_failure_pattern_{event.import_id}",
                        severity=AlertSeverity.WARNING,
                        message=f"High failure rate detected for import {event.import_id}: {len(recent_failures)} failures in 1 hour",
                        source='import_audit',
                        metadata={
                            'import_id': event.import_id,
                            'failure_count': len(recent_failures),
                            'time_window': '1 hour'
                        }
                    )
            
            # Check for frequent manual interventions
            if event.event_type == ImportAuditEventType.MANUAL_INTERVENTION:
                recent_interventions = self._get_recent_interventions(event.import_id, timedelta(hours=6))
                
                if len(recent_interventions) >= 3:
                    alerting_service.create_manual_alert(
                        name=f"import_intervention_pattern_{event.import_id}",
                        severity=AlertSeverity.WARNING,
                        message=f"Frequent manual interventions for import {event.import_id}: {len(recent_interventions)} interventions in 6 hours",
                        source='import_audit',
                        metadata={
                            'import_id': event.import_id,
                            'intervention_count': len(recent_interventions),
                            'time_window': '6 hours'
                        }
                    )
            
        except Exception as e:
            logger.error(f"Failed to check compliance alerts: {e}")
    
    def _get_recent_import_failures(self, import_id: str, time_delta: timedelta) -> List[Dict[str, Any]]:
        """Get recent import failures for an import."""
        cutoff_time = datetime.utcnow() - time_delta
        
        with self._lock:
            recent_failures = [
                e for e in self._events
                if e.import_id == import_id and 
                   e.event_type == ImportAuditEventType.IMPORT_FAILED and 
                   e.timestamp > cutoff_time
            ]
        
        return [event.to_dict() for event in recent_failures]
    
    def _get_recent_interventions(self, import_id: str, time_delta: timedelta) -> List[Dict[str, Any]]:
        """Get recent manual interventions for an import."""
        cutoff_time = datetime.utcnow() - time_delta
        
        with self._lock:
            recent_interventions = [
                e for e in self._events
                if e.import_id == import_id and 
                   e.event_type == ImportAuditEventType.MANUAL_INTERVENTION and 
                   e.timestamp > cutoff_time
            ]
        
        return [event.to_dict() for event in recent_interventions]
    
    def _start_cleanup(self):
        """Start background cleanup task."""
        # In a real implementation, this would use a proper background task scheduler
        logger.info("Import audit cleanup task started")
    
    def _cleanup_old_events(self):
        """Clean up old audit events based on retention policy."""
        cutoff_time = datetime.utcnow() - timedelta(days=self._retention_days)
        
        with self._lock:
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
                logger.debug(f"Cleaned up {cleaned_count} old import audit events")
    
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

# Global import audit instance
import_audit = ImportAudit()
