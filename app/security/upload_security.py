"""
Upload Security Service

Provides comprehensive security for document uploads.
"""

import logging
import os
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from flask import current_app
from .content_validator import content_validator, ValidationStatus, ThreatLevel
from .virus_scanner import virus_scanner, ScanStatus
from .file_sanitizer import file_sanitizer, SanitizationStatus
from .upload_monitoring import upload_monitoring_service, UploadStatus

logger = logging.getLogger(__name__)

@dataclass
class UploadSecurityResult:
    """Represents the result of upload security processing."""
    status: str
    allowed: bool
    threat_level: str
    validation_result: Optional[Dict[str, Any]]
    scan_result: Optional[Dict[str, Any]]
    sanitization_result: Optional[Dict[str, Any]]
    final_file_path: Optional[str]
    security_metadata: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'status': self.status,
            'allowed': self.allowed,
            'threat_level': self.threat_level,
            'validation_result': self.validation_result,
            'scan_result': self.scan_result,
            'sanitization_result': self.sanitization_result,
            'final_file_path': self.final_file_path,
            'security_metadata': self.security_metadata,
            'timestamp': self.timestamp.isoformat()
        }

class UploadSecurityService:
    """
    Provides comprehensive security for document uploads.
    """
    
    def __init__(self):
        """Initialize the upload security service."""
        self._enabled = current_app.config.get('UPLOAD_SECURITY_ENABLED', True)
        self._strict_mode = current_app.config.get('UPLOAD_SECURITY_STRICT_MODE', False)
        self._temp_dir = tempfile.gettempdir()
        
        logger.info(f"Upload security service initialized (enabled: {self._enabled}, strict_mode: {self._strict_mode})")
    
    def process_upload(self, file_path: str, filename: str, 
                      content: Optional[bytes] = None) -> UploadSecurityResult:
        """
        Process an uploaded file through all security checks.
        
        Args:
            file_path: Path to the uploaded file
            filename: Original filename
            content: Optional file content (if already read)
            
        Returns:
            Upload security result
        """
        if not self._enabled:
            return UploadSecurityResult(
                status="security_disabled",
                allowed=True,
                threat_level="none",
                validation_result=None,
                scan_result=None,
                sanitization_result=None,
                final_file_path=file_path,
                security_metadata={'security_enabled': False},
                timestamp=datetime.utcnow()
            )
        
        # Start monitoring
        event_id = upload_monitoring_service.log_upload_start(filename, os.path.getsize(file_path), "application/octet-stream")
        
        try:
            # Step 1: Content validation
            validation_result = self._validate_content(file_path, filename, content)
            
            # Step 2: Virus scanning
            scan_result = self._scan_for_viruses(file_path, filename, content)
            
            # Step 3: Determine if upload should be blocked
            if self._should_block_upload(validation_result, scan_result):
                upload_monitoring_service.log_upload_blocked(
                    event_id, 
                    self._get_block_reason(validation_result, scan_result),
                    self._get_max_threat_level(validation_result, scan_result)
                )
                
                return UploadSecurityResult(
                    status="blocked",
                    allowed=False,
                    threat_level=self._get_max_threat_level(validation_result, scan_result).value,
                    validation_result=validation_result.to_dict() if validation_result else None,
                    scan_result=scan_result.to_dict() if scan_result else None,
                    sanitization_result=None,
                    final_file_path=None,
                    security_metadata={
                        'blocked': True,
                        'block_reason': self._get_block_reason(validation_result, scan_result),
                        'event_id': event_id
                    },
                    timestamp=datetime.utcnow()
                )
            
            # Step 4: File sanitization
            sanitization_result = self._sanitize_file(file_path, filename, validation_result.mime_type if validation_result else "application/octet-stream")
            
            # Step 5: Final security check
            final_check = self._final_security_check(validation_result, scan_result, sanitization_result)
            
            # Step 6: Determine final file path
            final_file_path = self._get_final_file_path(file_path, sanitization_result)
            
            # Complete monitoring
            upload_monitoring_service.log_upload_completion(
                event_id,
                self._calculate_file_hash(final_file_path),
                0,  # Duration would be calculated in real implementation
                validation_result.to_dict() if validation_result else None,
                scan_result.to_dict() if scan_result else None,
                sanitization_result.to_dict() if sanitization_result else None
            )
            
            return UploadSecurityResult(
                status="completed",
                allowed=True,
                threat_level=self._get_max_threat_level(validation_result, scan_result).value,
                validation_result=validation_result.to_dict() if validation_result else None,
                scan_result=scan_result.to_dict() if scan_result else None,
                sanitization_result=sanitization_result.to_dict() if sanitization_result else None,
                final_file_path=final_file_path,
                security_metadata={
                    'blocked': False,
                    'sanitized': sanitization_result.status != SanitizationStatus.SUCCESS if sanitization_result else False,
                    'event_id': event_id
                },
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Upload security processing failed: {e}")
            upload_monitoring_service.log_upload_failure(event_id, str(e))
            
            return UploadSecurityResult(
                status="error",
                allowed=not self._strict_mode,  # Allow in non-strict mode
                threat_level="medium",
                validation_result=None,
                scan_result=None,
                sanitization_result=None,
                final_file_path=file_path if not self._strict_mode else None,
                security_metadata={
                    'error': str(e),
                    'strict_mode': self._strict_mode,
                    'event_id': event_id
                },
                timestamp=datetime.utcnow()
            )
    
    def _validate_content(self, file_path: str, filename: str, 
                         content: Optional[bytes] = None) -> Any:
        """Validate file content."""
        try:
            return content_validator.validate_file(file_path, filename, content)
        except Exception as e:
            logger.error(f"Content validation failed: {e}")
            # Return a default validation result
            from .content_validator import ValidationResult
            return ValidationResult(
                status=ValidationStatus.INVALID,
                threat_level=ThreatLevel.MEDIUM,
                confidence=0.5,
                issues=[f"Validation error: {str(e)}"],
                metadata={'error': str(e)},
                timestamp=datetime.utcnow()
            )
    
    def _scan_for_viruses(self, file_path: str, filename: str, 
                         content: Optional[bytes] = None) -> Any:
        """Scan file for viruses."""
        try:
            file_hash = self._calculate_file_hash(file_path)
            return virus_scanner.scan_file(file_path, file_hash)
        except Exception as e:
            logger.error(f"Virus scanning failed: {e}")
            # Return a default scan result
            from .virus_scanner import ScanResult, ScanEngine, ScanStatus
            return ScanResult(
                status=ScanStatus.ERROR,
                engine=ScanEngine.CUSTOM,
                scan_time=datetime.utcnow(),
                threats_found=[],
                metadata={'error': str(e)}
            )
    
    def _sanitize_file(self, file_path: str, filename: str, mime_type: str) -> Any:
        """Sanitize file content."""
        try:
            return file_sanitizer.sanitize_file(file_path, filename, mime_type)
        except Exception as e:
            logger.error(f"File sanitization failed: {e}")
            # Return a default sanitization result
            from .file_sanitizer import SanitizationResult, SanitizationStatus
            return SanitizationResult(
                status=SanitizationStatus.FAILED,
                original_file=file_path,
                sanitized_file=None,
                actions_performed=[],
                metadata={'error': str(e)},
                timestamp=datetime.utcnow()
            )
    
    def _should_block_upload(self, validation_result: Any, scan_result: Any) -> bool:
        """Determine if upload should be blocked."""
        # Block if validation status is blocked
        if hasattr(validation_result, 'status') and validation_result.status == ValidationStatus.BLOCKED:
            return True
        
        # Block if scan status is infected
        if hasattr(scan_result, 'status') and scan_result.status == ScanStatus.INFECTED:
            return True
        
        # Block if threat level is critical
        validation_threat = getattr(validation_result, 'threat_level', ThreatLevel.NONE)
        scan_threat = getattr(scan_result, 'threat_level', ThreatLevel.NONE)
        
        max_threat = max(validation_threat, scan_threat)
        
        if max_threat == ThreatLevel.CRITICAL:
            return True
        
        # In strict mode, block high threat levels
        if self._strict_mode and max_threat == ThreatLevel.HIGH:
            return True
        
        return False
    
    def _get_block_reason(self, validation_result: Any, scan_result: Any) -> str:
        """Get reason for blocking upload."""
        reasons = []
        
        if hasattr(validation_result, 'status') and validation_result.status == ValidationStatus.BLOCKED:
            reasons.append("Content validation blocked")
        
        if hasattr(scan_result, 'status') and scan_result.status == ScanStatus.INFECTED:
            reasons.append("Virus detected")
        
        validation_threat = getattr(validation_result, 'threat_level', ThreatLevel.NONE)
        scan_threat = getattr(scan_result, 'threat_level', ThreatLevel.NONE)
        
        max_threat = max(validation_threat, scan_threat)
        
        if max_threat == ThreatLevel.CRITICAL:
            reasons.append("Critical threat detected")
        elif self._strict_mode and max_threat == ThreatLevel.HIGH:
            reasons.append("High threat detected (strict mode)")
        
        return "; ".join(reasons) if reasons else "Security policy violation"
    
    def _get_max_threat_level(self, validation_result: Any, scan_result: Any) -> ThreatLevel:
        """Get maximum threat level from validation and scan results."""
        validation_threat = getattr(validation_result, 'threat_level', ThreatLevel.NONE)
        scan_threat = getattr(scan_result, 'threat_level', ThreatLevel.NONE)
        
        return max(validation_threat, scan_threat)
    
    def _final_security_check(self, validation_result: Any, scan_result: Any, 
                             sanitization_result: Any) -> bool:
        """Perform final security check after sanitization."""
        # If sanitization failed and we're in strict mode, block
        if self._strict_mode and hasattr(sanitization_result, 'status') and sanitization_result.status == SanitizationStatus.FAILED:
            return False
        
        # If sanitization was partial and we're in strict mode, check threats
        if self._strict_mode and hasattr(sanitization_result, 'status') and sanitization_result.status == SanitizationStatus.PARTIAL:
            # Additional checks would go here
            pass
        
        return True
    
    def _get_final_file_path(self, original_path: str, sanitization_result: Any) -> str:
        """Get the final file path after processing."""
        if hasattr(sanitization_result, 'sanitized_file') and sanitization_result.sanitized_file:
            return sanitization_result.sanitized_file
        
        return original_path
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        import hashlib
        
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def get_security_summary(self, time_delta: Any = None) -> Dict[str, Any]:
        """
        Get comprehensive security summary.
        
        Args:
            time_delta: Time period to analyze (default: 24 hours)
            
        Returns:
            Security summary
        """
        if time_delta is None:
            from datetime import timedelta
            time_delta = timedelta(days=1)
        
        # Get statistics from all components
        upload_stats = upload_monitoring_service.get_upload_statistics(time_delta)
        scan_stats = virus_scanner.get_scan_statistics(time_delta)
        
        # Get validation statistics
        validation_summary = content_validator.get_validation_summary([])
        
        return {
            'time_period': upload_stats['time_period'],
            'upload_security': {
                'enabled': self._enabled,
                'strict_mode': self._strict_mode,
                'statistics': upload_stats
            },
            'content_validation': validation_summary,
            'virus_scanning': scan_stats,
            'file_sanitization': {
                'quarantine_info': file_sanitizer.get_quarantine_info()
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def update_configuration(self, config: Dict[str, Any]):
        """Update security configuration."""
        if 'enabled' in config:
            self._enabled = config['enabled']
            logger.info(f"Upload security enabled: {self._enabled}")
        
        if 'strict_mode' in config:
            self._strict_mode = config['strict_mode']
            logger.info(f"Upload security strict mode: {self._strict_mode}")
        
        # Update component configurations
        if 'content_validation' in config:
            content_validator.update_allowed_mime_types(config['content_validation'].get('allowed_mime_types', []))
            content_validator.update_blocked_extensions(config['content_validation'].get('blocked_extensions', []))
        
        if 'virus_scanning' in config:
            # Update virus scanner configuration
            pass
        
        if 'file_sanitization' in config:
            # Update file sanitizer configuration
            pass
    
    def enable_strict_mode(self):
        """Enable strict security mode."""
        self._strict_mode = True
        logger.warning("Upload security strict mode enabled")
    
    def disable_strict_mode(self):
        """Disable strict security mode."""
        self._strict_mode = False
        logger.info("Upload security strict mode disabled")
    
    def enable_security(self):
        """Enable upload security."""
        self._enabled = True
        logger.info("Upload security enabled")
    
    def disable_security(self):
        """Disable upload security."""
        self._enabled = False
        logger.warning("Upload security disabled")

# Global upload security service instance
upload_security_service = UploadSecurityService()
