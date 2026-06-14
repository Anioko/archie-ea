"""
Upload Monitoring Service

Provides comprehensive monitoring and logging for document uploads.
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading

from flask import current_app, g, request
from app.monitoring.alerting_service import alerting_service, AlertSeverity

logger = logging.getLogger(__name__)

class UploadStatus(Enum):
    """Upload status levels."""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    QUARANTINED = "quarantined"

class ThreatLevel(Enum):
    """Threat level for uploads."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class UploadEvent:
    """Represents an upload event."""
    id: str
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: str
    user_agent: Optional[str]
    filename: str
    file_size: int
    mime_type: str
    file_hash: str
    status: UploadStatus
    threat_level: ThreatLevel
    validation_result: Optional[Dict[str, Any]]
    scan_result: Optional[Dict[str, Any]]
    sanitization_result: Optional[Dict[str, Any]]
    timestamp: datetime
    duration_ms: Optional[int]
    error_message: Optional[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert upload event to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        data['threat_level'] = self.threat_level.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

class UploadMonitoringService:
    """
    Monitors and logs document upload activities for security and compliance.
    """
    
    def __init__(self):
        """Initialize the upload monitoring service."""
        self._events = []  # In-memory storage (in production, use database)
        self._user_stats = {}  # user_id -> statistics
        self._ip_stats = {}  # ip_address -> statistics
        self._threat_patterns = {}  # threat patterns detection
        self._lock = threading.Lock()
        
        # Initialize monitoring configuration
        self._max_events = current_app.config.get('UPLOAD_MONITORING_MAX_EVENTS', 10000)
        self._retention_days = current_app.config.get('UPLOAD_MONITORING_RETENTION_DAYS', 90)
        self._alert_thresholds = current_app.config.get('UPLOAD_ALERT_THRESHOLDS', {
            'failed_uploads_per_hour': 10,
            'blocked_uploads_per_hour': 5,
            'critical_threats_per_hour': 1,
            'large_file_uploads_per_hour': 20
        })
        
        # Start background monitoring
        self._start_background_monitoring()
    
    def log_upload_start(self, filename: str, file_size: int, mime_type: str) -> str:
        """
        Log the start of an upload.
        
        Args:
            filename: Original filename
            file_size: File size in bytes
            mime_type: MIME type
            
        Returns:
            Upload event ID
        """
        # Get request context
        user_id = getattr(g, 'user_id', None) if hasattr(g, 'user_id') else None
        session_id = getattr(g, 'session_id', None) if hasattr(g, 'session_id') else None
        ip_address = getattr(request, 'remote_addr', 'unknown') if request else 'unknown'
        user_agent = getattr(request, 'user_agent', {}).get('string', 'unknown') if request and hasattr(request, 'user_agent') else 'unknown'
        
        # Generate file hash (will be updated when file is available)
        file_hash = hashlib.sha256(f"{filename}_{file_size}_{datetime.utcnow().isoformat()}".encode()).hexdigest()
        
        # Create upload event
        event = UploadEvent(
            id=self._generate_event_id(),
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            status=UploadStatus.UPLOADING,
            threat_level=ThreatLevel.NONE,
            validation_result=None,
            scan_result=None,
            sanitization_result=None,
            timestamp=datetime.utcnow(),
            duration_ms=None,
            error_message=None,
            metadata={}
        )
        
        with self._lock:
            self._events.append(event)
            self._cleanup_old_events()
        
        logger.info(f"Upload started: {filename} ({file_size} bytes) from {ip_address}")
        
        return event.id
    
    def log_upload_progress(self, event_id: str, progress: float):
        """
        Log upload progress.
        
        Args:
            event_id: Upload event ID
            progress: Progress percentage (0-100)
        """
        with self._lock:
            event = self._events.get(event_id)
            if event:
                event.metadata['progress'] = progress
                event.metadata['last_update'] = datetime.utcnow().isoformat()
    
    def log_upload_completion(self, event_id: str, file_hash: str, duration_ms: int,
                           validation_result: Optional[Dict[str, Any]] = None,
                           scan_result: Optional[Dict[str, Any]] = None,
                           sanitization_result: Optional[Dict[str, Any]] = None):
        """
        Log successful upload completion.
        
        Args:
            event_id: Upload event ID
            file_hash: SHA-256 hash of the file
            duration_ms: Upload duration in milliseconds
            validation_result: Content validation result
            scan_result: Virus scan result
            sanitization_result: File sanitization result
        """
        with self._lock:
            event = self._events.get(event_id)
            if not event:
                logger.warning(f"Upload event not found: {event_id}")
                return
            
            # Update event
            event.file_hash = file_hash
            event.duration_ms = duration_ms
            event.validation_result = validation_result
            event.scan_result = scan_result
            event.sanitization_result = sanitization_result
            event.status = UploadStatus.COMPLETED
            event.metadata['completed_at'] = datetime.utcnow().isoformat()
            
            # Determine threat level
            event.threat_level = self._calculate_threat_level(event)
            
            # Update statistics
            self._update_statistics(event)
        
        logger.info(f"Upload completed: {event.filename} ({event.file_size} bytes) in {duration_ms}ms")
        
        # Check for suspicious patterns
        self._check_suspicious_patterns(event)
        
        # Send alerts if needed
        self._check_alert_conditions(event)
    
    def log_upload_failure(self, event_id: str, error_message: str, duration_ms: Optional[int] = None):
        """
        Log upload failure.
        
        Args:
            event_id: Upload event ID
            error_message: Error message
            duration_ms: Upload duration in milliseconds
        """
        with self._lock:
            event = self._events.get(event_id)
            if not event:
                logger.warning(f"Upload event not found: {event_id}")
                return
            
            # Update event
            event.status = UploadStatus.FAILED
            event.error_message = error_message
            event.duration_ms = duration_ms
            event.metadata['failed_at'] = datetime.utcnow().isoformat()
            
            # Update statistics
            self._update_statistics(event)
        
        logger.error(f"Upload failed: {event.filename} - {error_message}")
        
        # Check for suspicious failure patterns
        self._check_failure_patterns(event)
    
    def log_upload_blocked(self, event_id: str, reason: str, threat_level: ThreatLevel):
        """
        Log blocked upload.
        
        Args:
            event_id: Upload event ID
            reason: Reason for blocking
            threat_level: Detected threat level
        """
        with self._lock:
            event = self._events.get(event_id)
            if not event:
                logger.warning(f"Upload event not found: {event_id}")
                return
            
            # Update event
            event.status = UploadStatus.BLOCKED
            event.threat_level = threat_level
            event.error_message = reason
            event.metadata['blocked_at'] = datetime.utcnow().isoformat()
            
            # Update statistics
            self._update_statistics(event)
        
        logger.warning(f"Upload blocked: {event.filename} - {reason} (threat: {threat_level.value})")
        
        # Send critical alert
        alerting_service.create_manual_alert(
            name=f"upload_blocked_{event_id}",
            severity=AlertSeverity.WARNING if threat_level != ThreatLevel.CRITICAL else AlertSeverity.CRITICAL,
            message=f"Upload blocked due to {reason}: {event.filename}",
            source='upload_monitoring',
            metadata={
                'event_id': event_id,
                'filename': event.filename,
                'threat_level': threat_level.value,
                'user_id': event.user_id,
                'ip_address': event.ip_address
            }
        )
    
    def log_upload_quarantined(self, event_id: str, reason: str, threats: List[str]):
        """
        Log quarantined upload.
        
        Args:
            event_id: Upload event ID
            reason: Reason for quarantine
            threats: List of threats found
        """
        with self._lock:
            event = self._events.get(event_id)
            if not event:
                logger.warning(f"Upload event not found: {event_id}")
                return
            
            # Update event
            event.status = UploadStatus.QUARANTINED
            event.threat_level = ThreatLevel.HIGH
            event.error_message = reason
            event.metadata['quarantined_at'] = datetime.utcnow().isoformat()
            event.metadata['threats'] = threats
            
            # Update statistics
            self._update_statistics(event)
        
        logger.critical(f"Upload quarantined: {event.filename} - {reason}")
        
        # Send critical alert
        alerting_service.create_manual_alert(
            name=f"upload_quarantined_{event_id}",
            severity=AlertSeverity.CRITICAL,
            message=f"Upload quarantined due to security threats: {event.filename}",
            source='upload_monitoring',
            metadata={
                'event_id': event_id,
                'filename': event.filename,
                'threats': threats,
                'user_id': event.user_id,
                'ip_address': event.ip_address
            }
        )
    
    def _calculate_threat_level(self, event: UploadEvent) -> ThreatLevel:
        """Calculate threat level based on validation, scan, and sanitization results."""
        threat_level = ThreatLevel.NONE
        
        # Check validation result
        if event.validation_result:
            validation_status = event.validation_result.get('status', 'valid')
            if validation_status == 'blocked':
                threat_level = ThreatLevel.CRITICAL
            elif validation_status == 'invalid':
                threat_level = max(threat_level, ThreatLevel.HIGH)
            elif validation_status == 'suspicious':
                threat_level = max(threat_level, ThreatLevel.MEDIUM)
        
        # Check scan result
        if event.scan_result:
            scan_status = event.scan_result.get('status', 'clean')
            if scan_status == 'infected':
                threat_level = ThreatLevel.CRITICAL
            elif scan_status == 'suspicious':
                threat_level = max(threat_level, ThreatLevel.HIGH)
            elif scan_status == 'error':
                threat_level = max(threat_level, ThreatLevel.MEDIUM)
        
        # Check sanitization result
        if event.sanitization_result:
            sanitization_status = event.sanitization_result.get('status', 'success')
            if sanitization_status == 'partial':
                threat_level = max(threat_level, ThreatLevel.MEDIUM)
            elif sanitization_status == 'failed':
                threat_level = max(threat_level, ThreatLevel.LOW)
        
        return threat_level
    
    def _update_statistics(self, event: UploadEvent):
        """Update user and IP statistics."""
        # Update user statistics
        if event.user_id:
            if event.user_id not in self._user_stats:
                self._user_stats[event.user_id] = {
                    'total_uploads': 0,
                    'completed_uploads': 0,
                    'failed_uploads': 0,
                    'blocked_uploads': 0,
                    'quarantined_uploads': 0,
                    'total_bytes': 0,
                    'last_upload': None,
                    'threat_levels': {level.value: 0 for level in ThreatLevel}
                }
            
            stats = self._user_stats[event.user_id]
            stats['total_uploads'] += 1
            stats['total_bytes'] += event.file_size
            stats['last_upload'] = event.timestamp.isoformat()
            stats['threat_levels'][event.threat_level.value] += 1
            
            if event.status == UploadStatus.COMPLETED:
                stats['completed_uploads'] += 1
            elif event.status == UploadStatus.FAILED:
                stats['failed_uploads'] += 1
            elif event.status == UploadStatus.BLOCKED:
                stats['blocked_uploads'] += 1
            elif event.status == UploadStatus.QUARANTINED:
                stats['quarantined_uploads'] += 1
        
        # Update IP statistics
        if event.ip_address not in self._ip_stats:
            self._ip_stats[event.ip_address] = {
                'total_uploads': 0,
                'completed_uploads': 0,
                'failed_uploads': 0,
                'blocked_uploads': 0,
                'quarantined_uploads': 0,
                'total_bytes': 0,
                'last_upload': None,
                'user_ids': set(),
                'threat_levels': {level.value: 0 for level in ThreatLevel}
            }
        
        stats = self._ip_stats[event.ip_address]
        stats['total_uploads'] += 1
        stats['total_bytes'] += event.file_size
        stats['last_upload'] = event.timestamp.isoformat()
        stats['threat_levels'][event.threat_level.value] += 1
        
        if event.user_id:
            stats['user_ids'].add(event.user_id)
        
        if event.status == UploadStatus.COMPLETED:
            stats['completed_uploads'] += 1
        elif event.status == UploadStatus.FAILED:
            stats['failed_uploads'] += 1
        elif event.status == UploadStatus.BLOCKED:
            stats['blocked_uploads'] += 1
        elif event.status == UploadStatus.QUARANTINED:
            stats['quarantined_uploads'] += 1
    
    def _check_suspicious_patterns(self, event: UploadEvent):
        """Check for suspicious upload patterns."""
        # Check for rapid uploads from same IP
        recent_uploads = self._get_recent_uploads_from_ip(event.ip_address, timedelta(minutes=5))
        
        if len(recent_uploads) > 10:
            logger.warning(f"Rapid uploads detected from {event.ip_address}: {len(recent_uploads)} uploads in 5 minutes")
            
            alerting_service.create_manual_alert(
                name=f"rapid_uploads_{event.ip_address}",
                severity=AlertSeverity.WARNING,
                message=f"Rapid uploads detected from IP {event.ip_address}",
                source='upload_monitoring',
                metadata={
                    'ip_address': event.ip_address,
                    'upload_count': len(recent_uploads),
                    'time_window': '5 minutes'
                }
            )
        
        # Check for large file uploads
        if event.file_size > 100 * 1024 * 1024:  # 100MB
            logger.info(f"Large file upload: {event.filename} ({event.file_size} bytes)")
        
        # Check for unusual file types
        unusual_mime_types = ['application/octet-stream', 'application/x-executable']
        if event.mime_type in unusual_mime_types:
            logger.warning(f"Unusual file type uploaded: {event.mime_type} - {event.filename}")
    
    def _check_failure_patterns(self, event: UploadEvent):
        """Check for suspicious failure patterns."""
        # Check for repeated failures from same user
        if event.user_id:
            recent_failures = self._get_recent_failures_from_user(event.user_id, timedelta(hours=1))
            
            if len(recent_failures) > 5:
                logger.warning(f"Repeated upload failures from user {event.user_id}: {len(recent_failures)} failures in 1 hour")
                
                alerting_service.create_manual_alert(
                    name=f"repeated_failures_{event.user_id}",
                    severity=AlertSeverity.WARNING,
                    message=f"Repeated upload failures from user {event.user_id}",
                    source='upload_monitoring',
                    metadata={
                        'user_id': event.user_id,
                        'failure_count': len(recent_failures),
                        'time_window': '1 hour'
                    }
                )
    
    def _check_alert_conditions(self, event: UploadEvent):
        """Check if alert conditions are met."""
        # Check for high threat levels
        if event.threat_level == ThreatLevel.CRITICAL:
            alerting_service.create_manual_alert(
                name=f"critical_threat_upload_{event.id}",
                severity=AlertSeverity.CRITICAL,
                message=f"Critical threat detected in upload: {event.filename}",
                source='upload_monitoring',
                metadata={
                    'event_id': event.id,
                    'filename': event.filename,
                    'threat_level': event.threat_level.value,
                    'user_id': event.user_id,
                    'ip_address': event.ip_address
                }
            )
        
        # Check for blocked uploads
        if event.status == UploadStatus.BLOCKED:
            blocked_uploads = self._get_recent_blocked_uploads(event.ip_address, timedelta(hours=1))
            
            if len(blocked_uploads) >= self._alert_thresholds['blocked_uploads_per_hour']:
                alerting_service.create_manual_alert(
                    name=f"blocked_uploads_threshold_{event.ip_address}",
                    severity=AlertSeverity.WARNING,
                    message=f"Blocked uploads threshold exceeded: {len(blocked_uploads)} blocked uploads in 1 hour",
                    source='upload_monitoring',
                    metadata={
                        'ip_address': event.ip_address,
                        'blocked_count': len(blocked_uploads),
                        'threshold': self._alert_thresholds['blocked_uploads_per_hour']
                    }
                )
    
    def _get_recent_uploads_from_ip(self, ip_address: str, time_delta: timedelta) -> List[UploadEvent]:
        """Get recent uploads from specific IP."""
        cutoff_time = datetime.utcnow() - time_delta
        
        with self._lock:
            return [
                event for event in self._events
                if event.ip_address == ip_address and event.timestamp > cutoff_time
            ]
    
    def _get_recent_failures_from_user(self, user_id: str, time_delta: timedelta) -> List[UploadEvent]:
        """Get recent failures from specific user."""
        cutoff_time = datetime.utcnow() - time_delta
        
        with self._lock:
            return [
                event for event in self._events
                if event.user_id == user_id and event.status == UploadStatus.FAILED and event.timestamp > cutoff_time
            ]
    
    def _get_recent_blocked_uploads(self, ip_address: str, time_delta: timedelta) -> List[UploadEvent]:
        """Get recent blocked uploads from specific IP."""
        cutoff_time = datetime.utcnow() - time_delta
        
        with self._lock:
            return [
                event for event in self._events
                if event.ip_address == ip_address and event.status == UploadStatus.BLOCKED and event.timestamp > cutoff_time
            ]
    
    def get_upload_events(self, limit: int = 100, user_id: Optional[str] = None,
                        status: Optional[UploadStatus] = None, threat_level: Optional[ThreatLevel] = None,
                        time_delta: Optional[timedelta] = None) -> List[Dict[str, Any]]:
        """
        Get upload events with filtering options.
        
        Args:
            limit: Maximum number of events to return
            user_id: Filter by user ID
            status: Filter by status
            threat_level: Filter by threat level
            time_delta: Filter by time range
            
        Returns:
            List of upload events
        """
        with self._lock:
            events = self._events.copy()
        
        # Apply filters
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        
        if status:
            events = [e for e in events if e.status == status]
        
        if threat_level:
            events = [e for e in events if e.threat_level == threat_level]
        
        if time_delta:
            cutoff_time = datetime.utcnow() - time_delta
            events = [e for e in events if e.timestamp > cutoff_time]
        
        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [event.to_dict() for event in events[:limit]]
    
    def get_upload_statistics(self, time_delta: timedelta = timedelta(days=1)) -> Dict[str, Any]:
        """
        Get upload statistics.
        
        Args:
            time_delta: Time period to analyze
            
        Returns:
            Upload statistics
        """
        cutoff_time = datetime.utcnow() - time_delta
        
        with self._lock:
            recent_events = [e for e in self._events if e.timestamp > cutoff_time]
        
        if not recent_events:
            return {
                'time_period': f"{time_delta.days} days",
                'total_uploads': 0,
                'completed_uploads': 0,
                'failed_uploads': 0,
                'blocked_uploads': 0,
                'quarantined_uploads': 0,
                'total_bytes': 0,
                'average_file_size': 0,
                'threat_distribution': {},
                'status_distribution': {},
                'top_uploaders': [],
                'top_ips': [],
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Calculate statistics
        total_uploads = len(recent_events)
        completed_uploads = len([e for e in recent_events if e.status == UploadStatus.COMPLETED])
        failed_uploads = len([e for e in recent_events if e.status == UploadStatus.FAILED])
        blocked_uploads = len([e for e in recent_events if e.status == UploadStatus.BLOCKED])
        quarantined_uploads = len([e for e in recent_events if e.status == UploadStatus.QUARANTINED])
        
        total_bytes = sum(e.file_size for e in recent_events)
        average_file_size = total_bytes / total_uploads if total_uploads > 0 else 0
        
        # Threat distribution
        threat_distribution = {}
        for event in recent_events:
            threat = event.threat_level.value
            threat_distribution[threat] = threat_distribution.get(threat, 0) + 1
        
        # Status distribution
        status_distribution = {}
        for event in recent_events:
            status = event.status.value
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        # Top uploaders
        user_counts = {}
        for event in recent_events:
            if event.user_id:
                user_counts[event.user_id] = user_counts.get(event.user_id, 0) + 1
        
        top_uploaders = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Top IPs
        ip_counts = {}
        for event in recent_events:
            ip_counts[event.ip_address] = ip_counts.get(event.ip_address, 0) + 1
        
        top_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'time_period': f"{time_delta.days} days",
            'total_uploads': total_uploads,
            'completed_uploads': completed_uploads,
            'failed_uploads': failed_uploads,
            'blocked_uploads': blocked_uploads,
            'quarantined_uploads': quarantined_uploads,
            'success_rate': completed_uploads / total_uploads if total_uploads > 0 else 0,
            'total_bytes': total_bytes,
            'average_file_size': average_file_size,
            'threat_distribution': threat_distribution,
            'status_distribution': status_distribution,
            'top_uploaders': [{'user_id': user, 'count': count} for user, count in top_uploaders],
            'top_ips': [{'ip_address': ip, 'count': count} for ip, count in top_ips],
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_user_statistics(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            User statistics or None if not found
        """
        with self._lock:
            stats = self._user_stats.get(user_id)
            
            if not stats:
                return None
            
            # Convert set to list for JSON serialization
            stats_copy = stats.copy()
            stats_copy['user_ids'] = list(stats_copy['user_ids']) if 'user_ids' in stats_copy else []
            
            return stats_copy
    
    def get_ip_statistics(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific IP address.
        
        Args:
            ip_address: IP address
            
        Returns:
            IP statistics or None if not found
        """
        with self._lock:
            stats = self._ip_stats.get(ip_address)
            
            if not stats:
                return None
            
            # Convert set to list for JSON serialization
            stats_copy = stats.copy()
            stats_copy['user_ids'] = list(stats_copy['user_ids'])
            
            return stats_copy
    
    def _cleanup_old_events(self):
        """Clean up old events based on retention policy."""
        cutoff_time = datetime.utcnow() - timedelta(days=self._retention_days)
        
        with self._lock:
            original_length = len(self._events)
            self._events = [e for e in self._events if e.timestamp > cutoff_time]
            
            # Remove excess events if over limit
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
            
            cleaned_count = original_length - len(self._events)
            
            if cleaned_count > 0:
                logger.debug(f"Cleaned up {cleaned_count} old upload events")
    
    def _start_background_monitoring(self):
        """Start background monitoring tasks."""
        # In a real implementation, this would use a proper background task scheduler
        # For now, we'll just log that this would be started
        logger.info("Upload monitoring background tasks started")
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"upload_{timestamp}_{threading.get_ident()}"
        return hashlib.md5(data.encode()).hexdigest()[:16]

# Global upload monitoring service instance
upload_monitoring_service = UploadMonitoringService()
