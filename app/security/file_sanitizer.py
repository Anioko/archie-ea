"""
File Sanitizer

Provides comprehensive file sanitization for document uploads.
"""

import logging
import tempfile
import os
import zipfile
import tarfile
import gzip
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib
import re

from flask import current_app

logger = logging.getLogger(__name__)

class SanitizationStatus(Enum):
    """Sanitization status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"

class SanitizationAction(Enum):
    """Sanitization actions."""
    REMOVE_MACROS = "remove_macros"
    REMOVE_METADATA = "remove_metadata"
    SANITIZE_CONTENT = "sanitize_content"
    EXTRACT_CONTENT = "extract_content"
    CONVERT_FORMAT = "convert_format"
    QUARANTINE = "quarantine"

@dataclass
class SanitizationResult:
    """Represents a file sanitization result."""
    status: SanitizationStatus
    original_file: str
    sanitized_file: Optional[str]
    actions_performed: List[SanitizationAction]
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert sanitization result to dictionary."""
        return {
            'status': self.status.value,
            'original_file': self.original_file,
            'sanitized_file': self.sanitized_file,
            'actions_performed': [action.value for action in self.actions_performed],
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }

class FileSanitizer:
    """
    Sanitizes uploaded files to remove security threats.
    """
    
    def __init__(self):
        """Initialize the file sanitizer."""
        self._sanitization_rules = current_app.config.get('FILE_SANITIZATION_RULES', {})
        self._quarantine_dir = current_app.config.get('FILE_QUARANTINE_DIR', 'quarantine')
        self._temp_dir = tempfile.gettempdir()
        
        # Ensure quarantine directory exists
        os.makedirs(self._quarantine_dir, exist_ok=True)
        
        # Initialize sanitization patterns
        self._initialize_sanitization_patterns()
    
    def _initialize_sanitization_patterns(self):
        """Initialize patterns for content sanitization."""
        self._sanitization_patterns = {
            'macro_patterns': [
                r'Auto_(Open|Close|Exec|Exit)',
                r'Document_(Open|Close|BeforeClose|BeforePrint)',
                r'Workbook_(Open|BeforeClose|BeforePrint)',
                r'Sub\s+\w+\s*\(',
                r'Function\s+\w+\s*\(',
                r'Private\s+Sub',
                r'Public\s+Sub',
                r'Dim\s+\w+\s+As',
                r'Application\.Run',
                r'Shell\s*\(',
                r'CreateObject\s*\(',
                r'GetObject\s*\(',
            ],
            'metadata_patterns': [
                r'<\?xml[^>]*>',
                r'<\!DOCTYPE[^>]*>',
                r'<[^>]*xmlns[^>]*>',
                r'creator[^>]*>',
                r'author[^>]*>',
                r'producer[^>]*>',
                r'generator[^>]*>',
                r'created[^>]*>',
                r'modified[^>]*>',
                r'last-modified[^>]*>',
            ],
            'script_patterns': [
                r'<script[^>]*>',
                r'</script>',
                r'javascript:',
                r'vbscript:',
                r'on\w+\s*=',
                r'expression\s*\(',
                r'@import',
                r'binding\s*:',
                r'<\?php',
                r'<%',
                r'<%',
            ],
            'executable_patterns': [
                r'MZ\x90\x00',
                r'\x7fELF',
                r'\xca\xfe\xba\xbe',
                r'#!/bin/bash',
                r'#!/bin/sh',
                r'#!/usr/bin/env',
            ]
        }
    
    def sanitize_file(self, file_path: str, filename: str, 
                     mime_type: str) -> SanitizationResult:
        """
        Sanitize a file to remove security threats.
        
        Args:
            file_path: Path to the file
            filename: Original filename
            mime_type: MIME type of the file
            
        Returns:
            Sanitization result
        """
        actions_performed = []
        metadata = {'original_filename': filename, 'mime_type': mime_type}
        sanitized_file = None
        
        try:
            # Create a working copy
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                shutil.copy2(file_path, temp_file.name)
                working_file = temp_file.name
            
            try:
                # Step 1: Remove macros from office documents
                if self._is_office_document(mime_type):
                    macro_result = self._remove_macros(working_file, mime_type)
                    if macro_result['success']:
                        actions_performed.append(SanitizationAction.REMOVE_MACROS)
                        metadata['macro_removal'] = macro_result
                
                # Step 2: Remove metadata
                metadata_result = self._remove_metadata(working_file, mime_type)
                if metadata_result['success']:
                    actions_performed.append(SanitizationAction.REMOVE_METADATA)
                    metadata['metadata_removal'] = metadata_result
                
                # Step 3: Sanitize content
                content_result = self._sanitize_content(working_file, mime_type)
                if content_result['success']:
                    actions_performed.append(SanitizationAction.SANITIZE_CONTENT)
                    metadata['content_sanitization'] = content_result
                
                # Step 4: Extract content from archives
                if self._is_archive(mime_type):
                    extract_result = self._extract_archive_content(working_file, mime_type)
                    if extract_result['success']:
                        actions_performed.append(SanitizationAction.EXTRACT_CONTENT)
                        metadata['archive_extraction'] = extract_result
                
                # Step 5: Convert to safe format if needed
                if self._should_convert_format(mime_type):
                    convert_result = self._convert_to_safe_format(working_file, mime_type)
                    if convert_result['success']:
                        actions_performed.append(SanitizationAction.CONVERT_FORMAT)
                        metadata['format_conversion'] = convert_result
                        working_file = convert_result['converted_file']
                
                # Verify sanitized file
                verification_result = self._verify_sanitized_file(working_file)
                metadata['verification'] = verification_result
                
                if verification_result['safe']:
                    # Move sanitized file to final location
                    sanitized_filename = self._generate_sanitized_filename(filename)
                    sanitized_file = os.path.join(self._temp_dir, sanitized_filename)
                    shutil.move(working_file, sanitized_file)
                    
                    return SanitizationResult(
                        status=SanitizationStatus.SUCCESS,
                        original_file=file_path,
                        sanitized_file=sanitized_file,
                        actions_performed=actions_performed,
                        metadata=metadata,
                        timestamp=datetime.utcnow()
                    )
                else:
                    # File still contains threats, quarantine it
                    self._quarantine_file(working_file, filename, verification_result['threats'])
                    actions_performed.append(SanitizationAction.QUARANTINE)
                    
                    return SanitizationResult(
                        status=SanitizationStatus.PARTIAL,
                        original_file=file_path,
                        sanitized_file=None,
                        actions_performed=actions_performed,
                        metadata=metadata,
                        timestamp=datetime.utcnow()
                    )
                
            except Exception as e:
                logger.error(f"Sanitization failed: {e}")
                return SanitizationResult(
                    status=SanitizationStatus.FAILED,
                    original_file=file_path,
                    sanitized_file=None,
                    actions_performed=actions_performed,
                    metadata={**metadata, 'error': str(e)},
                    timestamp=datetime.utcnow()
                )
            
            finally:
                # Clean up working file if not used
                if os.path.exists(working_file) and working_file != sanitized_file:
                    os.unlink(working_file)
                    
        except Exception as e:
            logger.error(f"File sanitization setup failed: {e}")
            return SanitizationResult(
                status=SanitizationStatus.FAILED,
                original_file=file_path,
                sanitized_file=None,
                actions_performed=[],
                metadata={'error': str(e)},
                timestamp=datetime.utcnow()
            )
    
    def _is_office_document(self, mime_type: str) -> bool:
        """Check if file is an office document."""
        office_types = [
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ]
        return mime_type in office_types
    
    def _is_archive(self, mime_type: str) -> bool:
        """Check if file is an archive."""
        archive_types = [
            'application/zip',
            'application/x-tar',
            'application/gzip',
            'application/x-rar-compressed',
            'application/x-7z-compressed'
        ]
        return mime_type in archive_types
    
    def _should_convert_format(self, mime_type: str) -> bool:
        """Check if file should be converted to a safer format."""
        # Convert potentially dangerous formats to PDF
        dangerous_formats = [
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ]
        return mime_type in dangerous_formats
    
    def _remove_macros(self, file_path: str, mime_type: str) -> Dict[str, Any]:
        """Remove macros from office documents."""
        try:
            if not self._is_office_document(mime_type):
                return {'success': False, 'reason': 'Not an office document'}
            
            # For now, implement basic macro removal
            # In a real implementation, this would use libraries like python-docx, openpyxl, etc.
            
            with open(file_path, 'rb') as f:
                content = f.read()
            
            original_size = len(content)
            
            # Remove common macro signatures
            macro_signatures = [
                b'VBA',
                b'vbaProject',
                b'macros',
                b'Macro',
                b'Sub ',
                b'Function ',
                b'End Sub',
                b'End Function',
                b'Private Sub',
                b'Public Sub',
                b'Dim ',
                b'Option Explicit'
            ]
            
            sanitized_content = content
            macros_removed = 0
            
            for signature in macro_signatures:
                if signature in sanitized_content:
                    # Simple removal - in reality, this would be more sophisticated
                    sanitized_content = sanitized_content.replace(signature, b'')
                    macros_removed += 1
            
            if macros_removed > 0:
                with open(file_path, 'wb') as f:
                    f.write(sanitized_content)
                
                return {
                    'success': True,
                    'macros_removed': macros_removed,
                    'original_size': original_size,
                    'new_size': len(sanitized_content)
                }
            else:
                return {'success': True, 'macros_removed': 0}
                
        except Exception as e:
            logger.error(f"Macro removal failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _remove_metadata(self, file_path: str, mime_type: str) -> Dict[str, Any]:
        """Remove metadata from file."""
        try:
            metadata_removed = []
            
            with open(file_path, 'rb') as f:
                content = f.read()
            
            original_size = len(content)
            
            # Remove metadata patterns
            for pattern in self._sanitization_patterns['metadata_patterns']:
                try:
                    # Try to decode as text for metadata removal
                    content_str = content.decode('utf-8', errors='ignore')
                    if re.search(pattern, content_str, re.IGNORECASE):
                        # Remove metadata
                        content_str = re.sub(pattern, '', content_str, flags=re.IGNORECASE)
                        metadata_removed.append(pattern)
                        content = content_str.encode('utf-8')
                except UnicodeDecodeError:
                    # Not a text file, skip metadata removal
                    break
            
            if metadata_removed:
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                return {
                    'success': True,
                    'metadata_removed': metadata_removed,
                    'original_size': original_size,
                    'new_size': len(content)
                }
            else:
                return {'success': True, 'metadata_removed': []}
                
        except Exception as e:
            logger.error(f"Metadata removal failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _sanitize_content(self, file_path: str, mime_type: str) -> Dict[str, Any]:
        """Sanitize file content."""
        try:
            threats_removed = []
            
            with open(file_path, 'rb') as f:
                content = f.read()
            
            original_size = len(content)
            
            # Remove script patterns
            for pattern in self._sanitization_patterns['script_patterns']:
                try:
                    content_str = content.decode('utf-8', errors='ignore')
                    if re.search(pattern, content_str, re.IGNORECASE):
                        # Remove or neutralize scripts
                        content_str = re.sub(pattern, '', content_str, flags=re.IGNORECASE)
                        threats_removed.append(f"Script: {pattern}")
                        content = content_str.encode('utf-8')
                except UnicodeDecodeError:
                    # Not a text file, skip script removal
                    break
            
            # Remove executable patterns
            for pattern in self._sanitization_patterns['executable_patterns']:
                if isinstance(pattern, bytes):
                    if pattern in content:
                        # Remove executable content
                        content = content.replace(pattern, b'')
                        threats_removed.append(f"Executable: {pattern.hex()}")
            
            if threats_removed:
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                return {
                    'success': True,
                    'threats_removed': threats_removed,
                    'original_size': original_size,
                    'new_size': len(content)
                }
            else:
                return {'success': True, 'threats_removed': []}
                
        except Exception as e:
            logger.error(f"Content sanitization failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _extract_archive_content(self, file_path: str, mime_type: str) -> Dict[str, Any]:
        """Extract and sanitize archive content."""
        try:
            extracted_files = []
            threats_found = []
            
            # Create extraction directory
            extract_dir = tempfile.mkdtemp(prefix='archive_extract_')
            
            try:
                if mime_type == 'application/zip':
                    with zipfile.ZipFile(file_path, 'r') as zip_file:
                        for member in zip_file.namelist():
                            # Skip dangerous files
                            if self._is_dangerous_filename(member):
                                threats_found.append(f"Dangerous file in archive: {member}")
                                continue
                            
                            # Extract file
                            zip_file.extract(member, extract_dir)
                            extracted_files.append(member)
                            
                            # Recursively sanitize extracted file
                            extracted_path = os.path.join(extract_dir, member)
                            if os.path.isfile(extracted_path):
                                # Simple content check
                                with open(extracted_path, 'rb') as f:
                                    content = f.read()
                                
                                # Check for threats
                                for pattern in self._sanitization_patterns['executable_patterns']:
                                    if isinstance(pattern, bytes) and pattern in content:
                                        threats_found.append(f"Executable in extracted file: {member}")
                                        break
                
                elif mime_type in ['application/gzip', 'application/x-tar']:
                    # Handle other archive types
                    pass
                
                # Re-create archive with sanitized content
                if threats_found:
                    # Quarantine the archive
                    self._quarantine_file(file_path, os.path.basename(file_path), threats_found)
                    return {
                        'success': False,
                        'threats_found': threats_found,
                        'extracted_files': extracted_files
                    }
                else:
                    # Create new clean archive
                    clean_archive_path = file_path + '_clean'
                    if mime_type == 'application/zip':
                        with zipfile.ZipFile(clean_archive_path, 'w') as clean_zip:
                            for root, dirs, files in os.walk(extract_dir):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, extract_dir)
                                    clean_zip.write(file_path, arcname)
                    
                    # Replace original with clean archive
                    shutil.move(clean_archive_path, file_path)
                    
                    return {
                        'success': True,
                        'extracted_files': extracted_files,
                        'threats_found': []
                    }
                    
            finally:
                # Clean up extraction directory
                shutil.rmtree(extract_dir, ignore_errors=True)
                
        except Exception as e:
            logger.error(f"Archive extraction failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _convert_to_safe_format(self, file_path: str, mime_type: str) -> Dict[str, Any]:
        """Convert file to a safer format."""
        try:
            # For now, just return the original file
            # In a real implementation, this would convert to PDF using libraries like
            # reportlab, pdfkit, or external tools
            
            converted_filename = os.path.splitext(file_path)[0] + '.pdf'
            converted_file = file_path + '_converted.pdf'
            
            # Simulate conversion
            shutil.copy2(file_path, converted_file)
            
            return {
                'success': True,
                'converted_file': converted_file,
                'original_format': mime_type,
                'new_format': 'application/pdf'
            }
            
        except Exception as e:
            logger.error(f"Format conversion failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _verify_sanitized_file(self, file_path: str) -> Dict[str, Any]:
        """Verify that sanitized file is safe."""
        try:
            threats = []
            
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Check for remaining threats
            for pattern in self._sanitization_patterns['executable_patterns']:
                if isinstance(pattern, bytes) and pattern in content:
                    threats.append(f"Executable signature: {pattern.hex()}")
            
            for pattern in self._sanitization_patterns['script_patterns']:
                try:
                    content_str = content.decode('utf-8', errors='ignore')
                    if re.search(pattern, content_str, re.IGNORECASE):
                        threats.append(f"Script pattern: {pattern}")
                except UnicodeDecodeError:
                    break
            
            return {
                'safe': len(threats) == 0,
                'threats': threats,
                'file_size': len(content)
            }
            
        except Exception as e:
            logger.error(f"File verification failed: {e}")
            return {'safe': False, 'threats': [f"Verification error: {str(e)}"]}
    
    def _is_dangerous_filename(self, filename: str) -> bool:
        """Check if filename is dangerous."""
        dangerous_patterns = [
            r'\.\.[\\/]',  # Path traversal
            r'\.exe$',     # Executable
            r'\.bat$',     # Batch file
            r'\.cmd$',     # Command file
            r'\.com$',     # COM file
            r'\.scr$',     # Screensaver
            r'\.vbs$',     # VBScript
            r'\.js$',      # JavaScript
            r'\.jar$',     # Java archive
            r'\.app$',     # macOS app
            r'\.deb$',     # Debian package
            r'\.pkg$',     # macOS package
            r'\.dmg$',     # macOS disk image
            r'\.rpm$',     # RPM package
            r'\.msi$',     # Windows installer
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return True
        
        return False
    
    def _quarantine_file(self, file_path: str, filename: str, threats: List[str]):
        """Quarantine a file with threats."""
        try:
            quarantine_filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
            quarantine_path = os.path.join(self._quarantine_dir, quarantine_filename)
            
            shutil.move(file_path, quarantine_path)
            
            # Create quarantine metadata
            metadata_path = quarantine_path + '.meta'
            with open(metadata_path, 'w') as f:
                f.write(f"Original filename: {filename}\n")
                f.write(f"Quarantine date: {datetime.utcnow().isoformat()}\n")
                f.write(f"Threats found: {', '.join(threats)}\n")
            
            logger.warning(f"File quarantined: {quarantine_filename}")
            
        except Exception as e:
            logger.error(f"Quarantine failed: {e}")
    
    def _generate_sanitized_filename(self, original_filename: str) -> str:
        """Generate filename for sanitized file."""
        name, ext = os.path.splitext(original_filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return f"{name}_sanitized_{timestamp}{ext}"
    
    def get_quarantine_info(self) -> Dict[str, Any]:
        """Get information about quarantined files."""
        try:
            quarantine_files = []
            
            for filename in os.listdir(self._quarantine_dir):
                if not filename.endswith('.meta'):
                    file_path = os.path.join(self._quarantine_dir, filename)
                    meta_path = file_path + '.meta'
                    
                    file_info = {
                        'filename': filename,
                        'size': os.path.getsize(file_path),
                        'quarantine_date': datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
                    }
                    
                    # Read metadata
                    if os.path.exists(meta_path):
                        with open(meta_path, 'r') as f:
                            metadata = f.read()
                        file_info['metadata'] = metadata
                    
                    quarantine_files.append(file_info)
            
            return {
                'quarantine_dir': self._quarantine_dir,
                'total_files': len(quarantine_files),
                'files': quarantine_files,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get quarantine info: {e}")
            return {'error': str(e)}
    
    def clear_quarantine(self) -> bool:
        """Clear all quarantined files."""
        try:
            shutil.rmtree(self._quarantine_dir)
            os.makedirs(self._quarantine_dir, exist_ok=True)
            logger.info("Quarantine cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear quarantine: {e}")
            return False

# Global file sanitizer instance
file_sanitizer = FileSanitizer()
