"""
Content Validator

Provides comprehensive content validation for document uploads.
"""

import logging
import hashlib

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    magic = None
    MAGIC_AVAILABLE = False
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import os

from flask import current_app

logger = logging.getLogger(__name__)

class ValidationStatus(Enum):
    """Validation status levels."""
    VALID = "valid"
    INVALID = "invalid"
    SUSPICIOUS = "suspicious"
    BLOCKED = "blocked"

class ThreatLevel(Enum):
    """Threat level for content."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ValidationResult:
    """Represents a content validation result."""
    status: ValidationStatus
    threat_level: ThreatLevel
    confidence: float
    issues: List[str]
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            'status': self.status.value,
            'threat_level': self.threat_level.value,
            'confidence': self.confidence,
            'issues': self.issues,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }

class ContentValidator:
    """
    Validates uploaded content for security threats and compliance.
    """
    
    def __init__(self):
        """Initialize the content validator."""
        self._allowed_mime_types = current_app.config.get('ALLOWED_UPLOAD_MIME_TYPES', [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain',
            'text/csv',
            'image/jpeg',
            'image/png',
            'image/gif'
        ])
        
        self._max_file_size = current_app.config.get('MAX_UPLOAD_SIZE', 100 * 1024 * 1024)  # 100MB
        self._blocked_extensions = current_app.config.get('BLOCKED_EXTENSIONS', [
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', '.jar',
            '.app', '.deb', '.pkg', '.dmg', '.rpm', '.msi', '.msp', '.msm'
        ])
        
        # Initialize threat patterns
        self._initialize_threat_patterns()
    
    def _initialize_threat_patterns(self):
        """Initialize threat detection patterns."""
        self._threat_patterns = {
            'executable_signatures': [
                b'MZ\x90\x00',  # Windows PE
                b'\x7fELF',      # Linux ELF
                b'\xca\xfe\xba\xbe',  # Java class
                b'#!/bin/bash',  # Shell script
                b'#!/bin/sh',    # Shell script
                b'#!/usr/bin/env python',  # Python script
            ],
            'suspicious_strings': [
                b'eval(base64_decode',
                b'system(',
                b'shell_exec(',
                b'passthru(',
                b'exec(',
                b'<script',
                b'javascript:',
                b'vbscript:',
                b'data:text/html',
                b'<?php',
                b'<%',
                b'<%',
            ],
            'path_traversal_patterns': [
                r'\.\.[\\/]',
                r'\.\.[\\/]\.\.[\\/]',
                r'%2e%2e%2f',
                r'%2e%2e\\',
                r'\.\.\/',
                r'\.\.\\',
            ],
            'injection_patterns': [
                r'<script[^>]*>',
                r'javascript:',
                r'on\w+\s*=',
                r'expression\s*\(',
                r'@import',
                r'binding\s*:',
            ],
            'macro_patterns': [
                b'Auto_Open',
                b'Auto_Close',
                b'Document_Open',
                b'Workbook_Open',
                rb'Sub\s+\w+\s*\(',
                rb'Function\s+\w+\s*\(',
                rb'Application\.Run',
            ]
        }
    
    def validate_file(self, file_path: str, filename: str, 
                      content: Optional[bytes] = None) -> ValidationResult:
        """
        Validate a file for security threats.
        
        Args:
            file_path: Path to the file
            filename: Original filename
            content: Optional file content (if already read)
            
        Returns:
            Validation result
        """
        issues = []
        threat_level = ThreatLevel.NONE
        confidence = 1.0
        metadata = {}
        
        try:
            # Read content if not provided
            if content is None:
                with open(file_path, 'rb') as f:
                    content = f.read()
            
            # Basic file checks
            file_size = len(content)
            metadata['file_size'] = file_size
            
            # Check file size
            if file_size > self._max_file_size:
                issues.append(f"File size ({file_size} bytes) exceeds maximum allowed size ({self._max_file_size} bytes)")
                threat_level = ThreatLevel.HIGH
                confidence = 0.9
            
            # Check file extension
            file_ext = os.path.splitext(filename)[1].lower()
            metadata['file_extension'] = file_ext
            
            if file_ext in self._blocked_extensions:
                issues.append(f"File extension '{file_ext}' is blocked")
                threat_level = ThreatLevel.CRITICAL
                confidence = 1.0
            
            # Check MIME type
            mime_type = self._get_mime_type(file_path, content)
            metadata['mime_type'] = mime_type
            
            if mime_type not in self._allowed_mime_types:
                issues.append(f"MIME type '{mime_type}' is not allowed")
                threat_level = max(threat_level, ThreatLevel.HIGH)
                confidence = min(confidence, 0.8)
            
            # Check for executable signatures
            executable_issues = self._check_executable_signatures(content)
            issues.extend(executable_issues)
            if executable_issues:
                threat_level = max(threat_level, ThreatLevel.CRITICAL)
                confidence = 1.0
            
            # Check for suspicious content
            suspicious_issues = self._check_suspicious_content(content, filename)
            issues.extend(suspicious_issues)
            if suspicious_issues:
                threat_level = max(threat_level, ThreatLevel.HIGH)
                confidence = min(confidence, 0.8)
            
            # Check for path traversal in filename
            path_issues = self._check_path_traversal(filename)
            issues.extend(path_issues)
            if path_issues:
                threat_level = max(threat_level, ThreatLevel.CRITICAL)
                confidence = 1.0
            
            # Check for injection patterns
            injection_issues = self._check_injection_patterns(content, filename)
            issues.extend(injection_issues)
            if injection_issues:
                threat_level = max(threat_level, ThreatLevel.MEDIUM)
                confidence = min(confidence, 0.7)
            
            # Check for macros in office documents
            macro_issues = self._check_macros(content, mime_type)
            issues.extend(macro_issues)
            if macro_issues:
                threat_level = max(threat_level, ThreatLevel.MEDIUM)
                confidence = min(confidence, 0.6)
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(content)
            metadata['file_hash'] = file_hash
            
            # Check against known malicious hashes (if available)
            hash_issues = self._check_malicious_hashes(file_hash)
            issues.extend(hash_issues)
            if hash_issues:
                threat_level = max(threat_level, ThreatLevel.CRITICAL)
                confidence = 1.0
            
            # Determine final status
            if threat_level == ThreatLevel.CRITICAL or any('blocked' in issue.lower() for issue in issues):
                status = ValidationStatus.BLOCKED
            elif threat_level == ThreatLevel.HIGH:
                status = ValidationStatus.INVALID
            elif threat_level == ThreatLevel.MEDIUM:
                status = ValidationStatus.SUSPICIOUS
            else:
                status = ValidationStatus.VALID
            
            return ValidationResult(
                status=status,
                threat_level=threat_level,
                confidence=confidence,
                issues=issues,
                metadata=metadata,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Content validation failed: {e}")
            return ValidationResult(
                status=ValidationStatus.INVALID,
                threat_level=ThreatLevel.MEDIUM,
                confidence=0.5,
                issues=[f"Validation error: {str(e)}"],
                metadata={'error': str(e)},
                timestamp=datetime.utcnow()
            )
    
    def _get_mime_type(self, file_path: str, content: bytes) -> str:
        """Get MIME type of file."""
        if MAGIC_AVAILABLE:
            try:
                mime_type = magic.from_buffer(content, mime=True)
                return mime_type
            except Exception as e:
                logger.warning(f"Failed to detect MIME type via python-magic: {e}")
        else:
            logger.warning("python-magic not available; using extension-based MIME detection")
        # Fallback to extension-based detection
            _, ext = os.path.splitext(file_path)
            extension_map = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xls': 'application/vnd.ms-excel',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.ppt': 'application/vnd.ms-powerpoint',
                '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                '.txt': 'text/plain',
                '.csv': 'text/csv',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif'
            }
            return extension_map.get(ext.lower(), 'application/octet-stream')
    
    def _check_executable_signatures(self, content: bytes) -> List[str]:
        """Check for executable file signatures."""
        issues = []
        
        for signature in self._threat_patterns['executable_signatures']:
            if signature in content[:1024]:  # Check first 1KB
                issues.append(f"Executable signature detected: {signature.hex()}")
                break
        
        return issues
    
    def _check_suspicious_content(self, content: bytes, filename: str) -> List[str]:
        """Check for suspicious content patterns."""
        issues = []
        content_lower = content.lower()
        
        for pattern in self._threat_patterns['suspicious_strings']:
            if pattern in content_lower:
                issues.append(f"Suspicious content detected: {pattern.decode('utf-8', errors='ignore')}")
        
        return issues
    
    def _check_path_traversal(self, filename: str) -> List[str]:
        """Check for path traversal patterns."""
        issues = []
        
        for pattern in self._threat_patterns['path_traversal_patterns']:
            if re.search(pattern, filename, re.IGNORECASE):
                issues.append(f"Path traversal pattern detected: {pattern}")
        
        return issues
    
    def _check_injection_patterns(self, content: bytes, filename: str) -> List[str]:
        """Check for injection patterns."""
        issues = []
        
        # Only check text-based files for injection
        try:
            content_str = content.decode('utf-8', errors='ignore')
            
            for pattern in self._threat_patterns['injection_patterns']:
                if re.search(pattern, content_str, re.IGNORECASE):
                    issues.append(f"Injection pattern detected: {pattern}")
                    break
        except UnicodeDecodeError:
            # Not a text file, skip injection checks
            pass
        
        return issues
    
    def _check_macros(self, content: bytes, mime_type: str) -> List[str]:
        """Check for macros in office documents."""
        issues = []
        
        # Only check office documents for macros
        if not any(office_type in mime_type for office_type in ['word', 'excel', 'powerpoint', 'office']):
            return issues
        
        for pattern in self._threat_patterns['macro_patterns']:
            if pattern in content:
                issues.append(f"Macro pattern detected: {pattern.decode('utf-8', errors='ignore')}")
        
        return issues
    
    def _calculate_file_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()
    
    def _check_malicious_hashes(self, file_hash: str) -> List[str]:
        """Check against known malicious file hashes."""
        issues = []
        
        # In a real implementation, this would check against a database of known malicious hashes
        # For now, just return empty list (would be populated with actual threat intelligence)
        malicious_hashes = current_app.config.get('MALICIOUS_FILE_HASHES', [])
        
        if file_hash in malicious_hashes:
            issues.append("File hash matches known malicious file")
        
        return issues
    
    def validate_batch(self, files: List[Tuple[str, str, Optional[bytes]]]) -> List[ValidationResult]:
        """
        Validate multiple files.
        
        Args:
            files: List of (file_path, filename, content) tuples
            
        Returns:
            List of validation results
        """
        results = []
        
        for file_path, filename, content in files:
            result = self.validate_file(file_path, filename, content)
            results.append(result)
        
        return results
    
    def get_validation_summary(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """
        Get summary of validation results.
        
        Args:
            results: List of validation results
            
        Returns:
            Validation summary
        """
        total_files = len(results)
        valid_files = len([r for r in results if r.status == ValidationStatus.VALID])
        suspicious_files = len([r for r in results if r.status == ValidationStatus.SUSPICIOUS])
        invalid_files = len([r for r in results if r.status == ValidationStatus.INVALID])
        blocked_files = len([r for r in results if r.status == ValidationStatus.BLOCKED])
        
        threat_distribution = {}
        for result in results:
            threat = result.threat_level.value
            threat_distribution[threat] = threat_distribution.get(threat, 0) + 1
        
        all_issues = []
        for result in results:
            all_issues.extend(result.issues)
        
        return {
            'total_files': total_files,
            'valid_files': valid_files,
            'suspicious_files': suspicious_files,
            'invalid_files': invalid_files,
            'blocked_files': blocked_files,
            'success_rate': valid_files / total_files if total_files > 0 else 0,
            'threat_distribution': threat_distribution,
            'total_issues': len(all_issues),
            'common_issues': self._get_common_issues(all_issues),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _get_common_issues(self, issues: List[str]) -> List[Dict[str, Any]]:
        """Get most common issues from validation results."""
        issue_counts = {}
        for issue in issues:
            # Extract issue type (first part before ':')
            issue_type = issue.split(':')[0] if ':' in issue else issue
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        # Sort by count and return top issues
        sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {'issue_type': issue_type, 'count': count}
            for issue_type, count in sorted_issues[:10]
        ]
    
    def update_allowed_mime_types(self, mime_types: List[str]):
        """Update allowed MIME types."""
        self._allowed_mime_types = mime_types
        logger.info(f"Updated allowed MIME types: {mime_types}")
    
    def update_blocked_extensions(self, extensions: List[str]):
        """Update blocked file extensions."""
        self._blocked_extensions = extensions
        logger.info(f"Updated blocked extensions: {extensions}")
    
    def add_threat_pattern(self, category: str, pattern: bytes):
        """Add a custom threat pattern."""
        if category not in self._threat_patterns:
            self._threat_patterns[category] = []
        
        self._threat_patterns[category].append(pattern)
        logger.info(f"Added threat pattern to {category}: {pattern.hex()}")

# Global content validator instance
content_validator = ContentValidator()
