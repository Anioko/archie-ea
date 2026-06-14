"""
Security Monitoring Service

Provides comprehensive security event monitoring and detection.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import json
import hashlib

from flask import current_app, request, session

logger = logging.getLogger(__name__)

class SecurityEventType(Enum):
    """Security event types."""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PERMISSION_DENIED = "permission_denied"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_ACCESS = "data_access"
    FILE_UPLOAD = "file_upload"
    CONFIG_CHANGE = "config_change"
    API_ACCESS = "api_access"
    SECURITY_VIOLATION = "security_violation"

class SecuritySeverity(Enum):
    """Security event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SecurityEvent:
    """Represents a security event."""
    id: str
    event_type: SecurityEventType
    severity: SecuritySeverity
    user_id: Optional[str]
    ip_address: str
    user_agent: Optional[str]
    resource: Optional[str]
    action: Optional[str]
    details: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert security event to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        return data

class SecurityMonitoringService:
    """
    Service for monitoring security events and detecting threats.
    """
    
    def __init__(self):
        """Initialize the security monitoring service."""
        self._events = []  # List of security events
        self._event_counts = {}  # event_type -> count
        self._ip_tracker = {}  # ip_address -> event_count, last_seen
        self._user_tracker = {}  # user_id -> event_count, last_seen
        self._lock = threading.Lock()
        
        # Initialize security rules
        self._initialize_security_rules()
    
    def _initialize_security_rules(self):
        """Initialize security monitoring rules."""
        self._security_rules = {
            'brute_force_detection': {
                'condition': self._detect_brute_force,
                'severity': SecuritySeverity.HIGH,
                'message': 'Multiple failed login attempts detected',
                'threshold': 5,  # 5 failed attempts
                'window': 300  # within 5 minutes
            },
            'suspicious_ip_activity': {
                'condition': self._detect_suspicious_ip,
                'severity': SecuritySeverity.MEDIUM,
                'message': 'High volume of requests from single IP',
                'threshold': 100,  # 100 requests
                'window': 60  # within 1 minute
            },
            'privilege_escalation': {
                'condition': self._detect_privilege_escalation,
                'severity': SecuritySeverity.HIGH,
                'message': 'Potential privilege escalation attempt',
                'threshold': 3  # 3 permission denied events
            },
            'data_exfiltration': {
                'condition': self._detect_data_exfiltration,
                'severity': SecuritySeverity.CRITICAL,
                'message': 'Potential data exfiltration detected',
                'threshold': 1000  # 1000 records accessed
            },
            'file_upload_anomaly': {
                'condition': self._detect_file_upload_anomaly,
                'severity': SecuritySeverity.MEDIUM,
                'message': 'Unusual file upload activity detected',
                'threshold': 10  # 10 files uploaded
            }
        }
    
    def log_security_event(self, event_type: SecurityEventType, severity: SecuritySeverity,
                          user_id: Optional[str] = None, resource: Optional[str] = None,
                          action: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Log a security event.
        
        Args:
            event_type: Type of security event
            severity: Severity level
            user_id: User ID (if available)
            resource: Resource being accessed
            action: Action being performed
            details: Additional event details
        """
        # Get request context
        ip_address = getattr(request, 'remote_addr', 'unknown') if request else 'unknown'
        user_agent = getattr(request, 'user_agent', {}).get('string', 'unknown') if request and hasattr(request, 'user_agent') else 'unknown'
        
        # Create security event
        event = SecurityEvent(
            id=self._generate_event_id(),
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource=resource,
            action=action,
            details=details or {},
            timestamp=datetime.utcnow()
        )
        
        with self._lock:
            self._events.append(event)
            self._event_counts[event_type.value] = self._event_counts.get(event_type.value, 0) + 1
            
            # Update IP tracker
            if ip_address != 'unknown':
                self._ip_tracker[ip_address] = {
                    'count': self._ip_tracker.get(ip_address, {}).get('count', 0) + 1,
                    'last_seen': event.timestamp
                }
            
            # Update user tracker
            if user_id:
                self._user_tracker[user_id] = {
                    'count': self._user_tracker.get(user_id, {}).get('count', 0) + 1,
                    'last_seen': event.timestamp
                }
        
        # Check security rules
        self._check_security_rules(event)
        
        # Log the event
        log_level = {
            SecuritySeverity.LOW: logging.INFO,
            SecuritySeverity.MEDIUM: logging.WARNING,
            SecuritySeverity.HIGH: logging.ERROR,
            SecuritySeverity.CRITICAL: logging.CRITICAL
        }.get(severity, logging.INFO)
        
        log_level(f"SECURITY EVENT: {event_type.value} - {user_id} - {ip_address} - {resource} - {action}")
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"{timestamp}_{threading.get_ident()}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
    
    def _check_security_rules(self, event: SecurityEvent):
        """Check security rules against the event."""
        for rule_name, rule in self._security_rules.items():
            try:
                if rule['condition'](event):
                    # Create security alert
                    from .alerting_service import alerting_service, AlertSeverity
                    
                    alert_severity = {
                        SecuritySeverity.LOW: AlertSeverity.INFO,
                        SecuritySeverity.MEDIUM: AlertSeverity.WARNING,
                        SecuritySeverity.HIGH: AlertSeverity.WARNING,
                        SecuritySeverity.CRITICAL: AlertSeverity.CRITICAL
                    }.get(event.severity, AlertSeverity.WARNING)
                    
                    alerting_service.create_manual_alert(
                        name=f"security_{rule_name}",
                        severity=alert_severity,
                        message=f"{rule['message']}: {event.details}",
                        source='security_monitoring',
                        metadata={
                            'rule': rule_name,
                            'event_id': event.id,
                            'event_type': event.event_type.value,
                            'user_id': event.user_id,
                            'ip_address': event.ip_address
                        }
                    )
                    
                    logger.warning(f"Security rule triggered: {rule_name}")
                    
            except Exception as e:
                logger.error(f"Error checking security rule {rule_name}: {e}")
    
    def _detect_brute_force(self, event: SecurityEvent) -> bool:
        """Detect brute force login attempts."""
        if event.event_type != SecurityEventType.LOGIN_FAILURE:
            return False
        
        # Count failed logins from this IP in the last 5 minutes
        cutoff_time = datetime.utcnow() - timedelta(seconds=300)
        
        with self._lock:
            failed_attempts = sum(
                1 for e in self._events
                if (e.event_type == SecurityEventType.LOGIN_FAILURE and
                    e.ip_address == event.ip_address and
                    e.timestamp > cutoff_time)
            )
        
        return failed_attempts >= 5
    
    def _detect_suspicious_ip(self, event: SecurityEvent) -> bool:
        """Detect suspicious IP activity."""
        # Count requests from this IP in the last minute
        cutoff_time = datetime.utcnow() - timedelta(seconds=60)
        
        with self._lock:
            request_count = sum(
                1 for e in self._events
                if (e.ip_address == event.ip_address and
                    e.timestamp > cutoff_time)
            )
        
        return request_count >= 100
    
    def _detect_privilege_escalation(self, event: SecurityEvent) -> bool:
        """Detect privilege escalation attempts."""
        if event.event_type != SecurityEventType.PERMISSION_DENIED:
            return False
        
        # Count permission denied events for this user in the last hour
        cutoff_time = datetime.utcnow() - timedelta(seconds=3600)
        
        with self._lock:
            denied_count = sum(
                1 for e in self._events
                if (e.event_type == SecurityEventType.PERMISSION_DENIED and
                    e.user_id == event.user_id and
                    e.timestamp > cutoff_time)
            )
        
        return denied_count >= 3
    
    def _detect_data_exfiltration(self, event: SecurityEvent) -> bool:
        """Detect potential data exfiltration."""
        if event.event_type != SecurityEventType.DATA_ACCESS:
            return False
        
        # Check if large amount of data accessed
        record_count = event.details.get('record_count', 0)
        return record_count >= 1000
    
    def _detect_file_upload_anomaly(self, event: SecurityEvent) -> bool:
        """Detect unusual file upload activity."""
        if event.event_type != SecurityEventType.FILE_UPLOAD:
            return False
        
        # Count file uploads from this user in the last hour
        cutoff_time = datetime.utcnow() - timedelta(seconds=3600)
        
        with self._lock:
            upload_count = sum(
                1 for e in self._events
                if (e.event_type == SecurityEventType.FILE_UPLOAD and
                    e.user_id == event.user_id and
                    e.timestamp > cutoff_time)
            )
        
        return upload_count >= 10
    
    def get_recent_events(self, limit: int = 100, event_type: Optional[SecurityEventType] = None,
                         severity: Optional[SecuritySeverity] = None) -> List[Dict[str, Any]]:
        """
        Get recent security events.
        
        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type
            severity: Filter by severity
            
        Returns:
            List of security events
        """
        with self._lock:
            events = self._events.copy()
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [event.to_dict() for event in events[:limit]]
    
    def get_security_summary(self) -> Dict[str, Any]:
        """
        Get security monitoring summary.
        
        Returns:
            Security summary statistics
        """
        with self._lock:
            # Event counts by type
            event_counts = {}
            for event_type, count in self._event_counts.items():
                event_counts[event_type] = count
            
            # Recent events (last 24 hours)
            cutoff_time = datetime.utcnow() - timedelta(seconds=86400)
            recent_events = [e for e in self._events if e.timestamp > cutoff_time]
            
            # Severity distribution
            severity_counts = {}
            for event in recent_events:
                severity_counts[event.severity.value] = severity_counts.get(event.severity.value, 0) + 1
            
            # Top IP addresses
            ip_counts = {}
            for event in recent_events:
                ip_counts[event.ip_address] = ip_counts.get(event.ip_address, 0) + 1
            
            top_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # Top users
            user_counts = {}
            for event in recent_events:
                if event.user_id:
                    user_counts[event.user_id] = user_counts.get(event.user_id, 0) + 1
            
            top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                'total_events': len(self._events),
                'recent_events_24h': len(recent_events),
                'event_counts_by_type': event_counts,
                'severity_distribution_24h': severity_counts,
                'top_ip_addresses_24h': [{'ip': ip, 'count': count} for ip, count in top_ips],
                'top_users_24h': [{'user': user, 'count': count} for user, count in top_users],
                'active_rules': len(self._security_rules),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def get_ip_reputation(self, ip_address: str) -> Dict[str, Any]:
        """
        Get IP reputation information.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            IP reputation information
        """
        with self._lock:
            ip_data = self._ip_tracker.get(ip_address, {})
            recent_events = [e for e in self._events if e.ip_address == ip_address]
            
            # Event breakdown
            event_counts = {}
            for event in recent_events:
                event_counts[event.event_type.value] = event_counts.get(event.event_type.value, 0) + 1
            
            # Recent activity (last 24 hours)
            cutoff_time = datetime.utcnow() - timedelta(seconds=86400)
            recent_activity = [e for e in recent_events if e.timestamp > cutoff_time]
            
            return {
                'ip_address': ip_address,
                'total_requests': ip_data.get('count', 0),
                'last_seen': ip_data.get('last_seen', None),
                'recent_requests_24h': len(recent_activity),
                'event_breakdown': event_counts,
                'reputation': self._calculate_ip_reputation(recent_activity)
            }
    
    def _calculate_ip_reputation(self, events: List[SecurityEvent]) -> str:
        """Calculate IP reputation based on events."""
        if not events:
            return 'unknown'
        
        # Count events by severity
        severity_counts = {}
        for event in events:
            severity_counts[event.severity.value] = severity_counts.get(event.severity.value, 0) + 1
        
        # Calculate reputation
        if severity_counts.get('critical', 0) > 0:
            return 'malicious'
        elif severity_counts.get('high', 0) > 2:
            return 'suspicious'
        elif severity_counts.get('medium', 0) > 5:
            return 'suspicious'
        elif severity_counts.get('low', 0) > 10:
            return 'unknown'
        else:
            return 'good'
    
    def cleanup_old_events(self, days_to_keep: int = 30):
        """
        Clean up old security events.
        
        Args:
            days_to_keep: Number of days to keep events
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with self._lock:
            original_count = len(self._events)
            self._events = [e for e in self._events if e.timestamp > cutoff_time]
            
            # Recalculate counts
            self._event_counts.clear()
            for event in self._events:
                self._event_counts[event.event_type.value] = self._event_counts.get(event.event_type.value, 0) + 1
            
            cleaned_count = original_count - len(self._events)
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old security events")

# Global security monitoring service instance
security_monitoring_service = SecurityMonitoringService()
