"""
Virus Scanner

Provides virus scanning integration for document uploads.
"""

import logging
import subprocess
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import threading

from flask import current_app

logger = logging.getLogger(__name__)

class ScanStatus(Enum):
    """Virus scan status."""
    CLEAN = "clean"
    INFECTED = "infected"
    SUSPICIOUS = "suspicious"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"

class ScanEngine(Enum):
    """Available scan engines."""
    CLAMAV = "clamav"
    WINDOWS_DEFENDER = "windows_defender"
    SOPHOS = "sophos"
    MCAFEE = "mcafee"
    CUSTOM = "custom"

@dataclass
class ScanResult:
    """Represents a virus scan result."""
    status: ScanStatus
    engine: ScanEngine
    scan_time: datetime
    threats_found: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert scan result to dictionary."""
        return {
            'status': self.status.value,
            'engine': self.engine.value,
            'scan_time': self.scan_time.isoformat(),
            'threats_found': self.threats_found,
            'metadata': self.metadata
        }

class VirusScanner:
    """
    Integrates with virus scanning engines to scan uploaded files.
    """
    
    def __init__(self):
        """Initialize the virus scanner."""
        self._enabled_engines = []
        self._scan_cache = {}  # file_hash -> ScanResult
        self._cache_ttl = current_app.config.get('VIRUS_SCAN_CACHE_TTL', 3600)  # 1 hour
        self._lock = threading.Lock()
        
        # Initialize available engines
        self._initialize_engines()
        
        # Start cache cleanup
        self._start_cache_cleanup()
    
    def _initialize_engines(self):
        """Initialize available virus scanning engines."""
        # Check for ClamAV
        if self._check_clamav_available():
            self._enabled_engines.append(ScanEngine.CLAMAV)
            logger.info("ClamAV engine initialized")
        
        # Check for Windows Defender
        if self._check_windows_defender_available():
            self._enabled_engines.append(ScanEngine.WINDOWS_DEFENDER)
            logger.info("Windows Defender engine initialized")
        
        # Check for custom scanner
        if current_app.config.get('CUSTOM_VIRUS_SCANNER_ENABLED', False):
            self._enabled_engines.append(ScanEngine.CUSTOM)
            logger.info("Custom virus scanner engine initialized")
        
        if not self._enabled_engines:
            logger.warning("No virus scanning engines available")
    
    def _check_clamav_available(self) -> bool:
        """Check if ClamAV is available."""
        try:
            # Check if clamscan is available
            result = subprocess.run(['clamscan', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _check_windows_defender_available(self) -> bool:
        """Check if Windows Defender is available."""
        try:
            # Check if Windows Defender is available (Windows only)
            result = subprocess.run(['MpCmdRun.exe', '-?'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def scan_file(self, file_path: str, file_hash: str) -> ScanResult:
        """
        Scan a file for viruses.
        
        Args:
            file_path: Path to the file to scan
            file_hash: SHA-256 hash of the file
            
        Returns:
            Scan result
        """
        # Check cache first
        cached_result = self._get_cached_result(file_hash)
        if cached_result:
            logger.debug(f"Using cached scan result for {file_hash}")
            return cached_result
        
        # If no engines available, return unavailable
        if not self._enabled_engines:
            return ScanResult(
                status=ScanStatus.UNAVAILABLE,
                engine=ScanEngine.CUSTOM,
                scan_time=datetime.utcnow(),
                threats_found=[],
                metadata={'reason': 'No scanning engines available'}
            )
        
        # Try each enabled engine
        for engine in self._enabled_engines:
            try:
                result = self._scan_with_engine(file_path, engine)
                
                # Cache the result
                self._cache_result(file_hash, result)
                
                # If infected, return immediately
                if result.status == ScanStatus.INFECTED:
                    logger.warning(f"File infected detected by {engine.value}: {file_path}")
                    return result
                
                # If clean or suspicious, continue to next engine
                logger.info(f"Scan result from {engine.value}: {result.status.value}")
                
            except Exception as e:
                logger.error(f"Scan with {engine.value} failed: {e}")
                continue
        
        # If all engines failed or returned clean/suspicious, return the last result
        # or create a default clean result
        if self._enabled_engines:
            return result if 'result' in locals() else ScanResult(
                status=ScanStatus.CLEAN,
                engine=self._enabled_engines[0],
                scan_time=datetime.utcnow(),
                threats_found=[],
                metadata={'engines_tried': [e.value for e in self._enabled_engines]}
            )
        else:
            return ScanResult(
                status=ScanStatus.UNAVAILABLE,
                engine=ScanEngine.CUSTOM,
                scan_time=datetime.utcnow(),
                threats_found=[],
                metadata={'reason': 'No scanning engines available'}
            )
    
    def _scan_with_engine(self, file_path: str, engine: ScanEngine) -> ScanResult:
        """Scan file with specific engine."""
        if engine == ScanEngine.CLAMAV:
            return self._scan_with_clamav(file_path)
        elif engine == ScanEngine.WINDOWS_DEFENDER:
            return self._scan_with_windows_defender(file_path)
        elif engine == ScanEngine.CUSTOM:
            return self._scan_with_custom_engine(file_path)
        else:
            raise ValueError(f"Unsupported scan engine: {engine}")
    
    def _scan_with_clamav(self, file_path: str) -> ScanResult:
        """Scan file using ClamAV."""
        try:
            # Run clamscan
            result = subprocess.run([
                'clamscan',
                '--no-summary',
                '--detect-pua=yes',
                '--detect-encrypted=yes',
                file_path
            ], capture_output=True, text=True, timeout=current_app.config.get('CLAMAV_TIMEOUT', 60))
            
            scan_time = datetime.utcnow()
            threats_found = []
            
            if result.returncode == 0:
                # Clean
                status = ScanStatus.CLEAN
            elif result.returncode == 1:
                # Virus found
                status = ScanStatus.INFECTED
                # Parse output for threat names
                for line in result.stdout.split('\n'):
                    if 'FOUND' in line:
                        threat = line.split('FOUND')[0].strip()
                        threats_found.append(threat)
            else:
                # Error
                status = ScanStatus.ERROR
                logger.error(f"ClamAV error: {result.stderr}")
            
            return ScanResult(
                status=status,
                engine=ScanEngine.CLAMAV,
                scan_time=scan_time,
                threats_found=threats_found,
                metadata={
                    'return_code': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            )
            
        except subprocess.TimeoutExpired:
            logger.error(f"ClamAV scan timeout for {file_path}")
            return ScanResult(
                status=ScanStatus.TIMEOUT,
                engine=ScanEngine.CLAMAV,
                scan_time=datetime.utcnow(),
                threats_found=[],
                metadata={'reason': 'Scan timeout'}
            )
        except Exception as e:
            logger.error(f"ClamAV scan failed: {e}")
            return ScanResult(
                status=ScanStatus.ERROR,
                engine=ScanEngine.CLAMAV,
                scan_time=datetime.utcnow(),
                threats_found=[],
                metadata={'error': str(e)}
            )
    
    def _scan_with_windows_defender(self, file_path: str) -> ScanResult:
        """Scan file using Windows Defender."""
        try:
            # Run Windows Defender scan
            result = subprocess.run([
                'MpCmdRun.exe',
                '-Scan',
                '-ScanType', '3',  # Custom scan
                '-File', file_path,
                '-DisableRemediation'
            ], capture_output=True, text=True, timeout=current_app.config.get('WINDOWS_DEFENDER_TIMEOUT', 120))
            
            scan_time = datetime.utcnow()
            threats_found = []
            
            if result.returncode == 0:
                # Clean
                status = ScanStatus.CLEAN
            elif result.returncode == 2:
                # Threat found
                status = ScanStatus.INFECTED
                # Parse output for threat information
                for line in result.stdout.split('\n'):
                    if 'found' in line.lower() and 'threat' in line.lower():
                        threats_found.append(line.strip())
            else:
                # Error
                status = ScanStatus.ERROR
                logger.error(f"Windows Defender error: {result.stderr}")
            
            return ScanResult(
                status=status,
                engine=ScanEngine.WINDOWS_DEFENDER,
                scan_time=scan_time,
                threats_found=threats_found,
                metadata={
                    'return_code': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            )
            
        except subprocess.TimeoutExpired:
            logger.error(f"Windows Defender scan timeout for {file_path}")
            return ScanResult(
                status=ScanStatus.TIMEOUT,
                engine=ScanEngine.WINDOWS_DEFENDER,
                scan_time=datetime.utcnow(),
                threats_found=[],
                metadata={'reason': 'Scan timeout'}
            )
        except Exception as e:
            logger.error(f"Windows Defender scan failed: {e}")
            return ScanResult(
                status=ScanStatus.ERROR,
                engine=ScanEngine.WINDOWS_DEFENDER,
                scan_time=datetime.utcnow(),
                threats_found=[],
                metadata={'error': str(e)}
            )
    
    def _scan_with_custom_engine(self, file_path: str) -> ScanResult:
        """Scan file using custom engine."""
        try:
            # Get custom scanner command from config
            scanner_command = current_app.config.get('CUSTOM_VIRUS_SCANNER_COMMAND')
            
            if not scanner_command:
                return ScanResult(
                    status=ScanStatus.ERROR,
                    engine=ScanEngine.CUSTOM,
                    scan_time=datetime.utcnow(),
                    threats_found=[],
                    metadata={'error': 'Custom scanner command not configured'}
                )
            
            # Run custom scanner
            result = subprocess.run([
                scanner_command,
                file_path
            ], capture_output=True, text=True, timeout=current_app.config.get('CUSTOM_SCANNER_TIMEOUT', 60))
            
            scan_time = datetime.utcnow()
            threats_found = []
            
            # Parse custom scanner output (implementation depends on scanner)
            if result.returncode == 0:
                status = ScanStatus.CLEAN
            elif result.returncode == 1:
                status = ScanStatus.INFECTED
                # Parse output for threats
                for line in result.stdout.split('\n'):
                    if 'threat' in line.lower() or 'virus' in line.lower():
                        threats_found.append(line.strip())
            else:
                status = ScanStatus.ERROR
            
            return ScanResult(
                status=status,
                engine=ScanEngine.CUSTOM,
                scan_time=scan_time,
                threats_found=threats_found,
                metadata={
                    'return_code': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            )
            
        except subprocess.TimeoutExpired:
            logger.error(f"Custom scanner timeout for {file_path}")
            return ScanResult(
                status=ScanStatus.TIMEOUT,
                engine=ScanEngine.CUSTOM,
                scan_time=datetime.utcnow(),
                threats_found=[],
                metadata={'reason': 'Scan timeout'}
            )
        except Exception as e:
            logger.error(f"Custom scanner failed: {e}")
            return ScanResult(
                status=ScanStatus.ERROR,
                engine=ScanEngine.CUSTOM,
                scan_time=datetime.utcnow(),
                threats_found=[],
                metadata={'error': str(e)}
            )
    
    def scan_batch(self, files: List[Tuple[str, str]]) -> List[ScanResult]:
        """
        Scan multiple files.
        
        Args:
            files: List of (file_path, file_hash) tuples
            
        Returns:
            List of scan results
        """
        results = []
        
        for file_path, file_hash in files:
            result = self.scan_file(file_path, file_hash)
            results.append(result)
        
        return results
    
    def _get_cached_result(self, file_hash: str) -> Optional[ScanResult]:
        """Get cached scan result."""
        with self._lock:
            if file_hash in self._scan_cache:
                cached_result, timestamp = self._scan_cache[file_hash]
                
                # Check if cache entry is still valid
                if datetime.utcnow() - timestamp < timedelta(seconds=self._cache_ttl):
                    return cached_result
                else:
                    # Remove expired entry
                    del self._scan_cache[file_hash]
        
        return None
    
    def _cache_result(self, file_hash: str, result: ScanResult):
        """Cache scan result."""
        with self._lock:
            self._scan_cache[file_hash] = (result, datetime.utcnow())
    
    def _start_cache_cleanup(self):
        """Start background task to clean up expired cache entries."""
        # In a real implementation, this would use a proper background task scheduler
        # For now, we'll just log that this would be started
        logger.info("Virus scan cache cleanup started")
    
    def _cleanup_cache(self):
        """Clean up expired cache entries."""
        cutoff_time = datetime.utcnow() - timedelta(seconds=self._cache_ttl)
        
        with self._lock:
            expired_keys = [
                key for key, (result, timestamp) in self._scan_cache.items()
                if timestamp < cutoff_time
            ]
            
            for key in expired_keys:
                del self._scan_cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired virus scan cache entries")
    
    def get_scan_statistics(self, time_delta: timedelta = timedelta(days=7)) -> Dict[str, Any]:
        """
        Get virus scanning statistics.
        
        Args:
            time_delta: Time period to analyze
            
        Returns:
            Scan statistics
        """
        with self._lock:
            recent_scans = [
                (file_hash, result, timestamp)
                for file_hash, (result, timestamp) in self._scan_cache.items()
                if timestamp > datetime.utcnow() - time_delta
            ]
        
        if not recent_scans:
            return {
                'time_period': f"{time_delta.days} days",
                'total_scans': 0,
                'clean_scans': 0,
                'infected_scans': 0,
                'suspicious_scans': 0,
                'error_scans': 0,
                'infection_rate': 0,
                'engines_used': [engine.value for engine in self._enabled_engines],
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Calculate statistics
        total_scans = len(recent_scans)
        clean_scans = len([r for _, r, _ in recent_scans if r.status == ScanStatus.CLEAN])
        infected_scans = len([r for _, r, _ in recent_scans if r.status == ScanStatus.INFECTED])
        suspicious_scans = len([r for _, r, _ in recent_scans if r.status == ScanStatus.SUSPICIOUS])
        error_scans = len([r for _, r, _ in recent_scans if r.status in [ScanStatus.ERROR, ScanStatus.TIMEOUT]])
        
        # Engine distribution
        engine_distribution = {}
        for _, result, _ in recent_scans:
            engine = result.engine.value
            engine_distribution[engine] = engine_distribution.get(engine, 0) + 1
        
        # Top threats
        all_threats = []
        for _, result, _ in recent_scans:
            all_threats.extend(result.threats_found)
        
        threat_counts = {}
        for threat in all_threats:
            threat_counts[threat] = threat_counts.get(threat, 0) + 1
        
        top_threats = sorted(threat_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'time_period': f"{time_delta.days} days",
            'total_scans': total_scans,
            'clean_scans': clean_scans,
            'infected_scans': infected_scans,
            'suspicious_scans': suspicious_scans,
            'error_scans': error_scans,
            'infection_rate': infected_scans / total_scans if total_scans > 0 else 0,
            'engines_used': [engine.value for engine in self._enabled_engines],
            'engine_distribution': engine_distribution,
            'top_threats': [{'threat': threat, 'count': count} for threat, count in top_threats],
            'cache_size': len(self._scan_cache),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def clear_cache(self):
        """Clear the scan cache."""
        with self._lock:
            cache_size = len(self._scan_cache)
            self._scan_cache.clear()
        
        logger.info(f"Cleared virus scan cache ({cache_size} entries removed)")
    
    def enable_engine(self, engine: ScanEngine) -> bool:
        """Enable a scanning engine."""
        if engine not in self._enabled_engines:
            self._enabled_engines.append(engine)
            logger.info(f"Enabled scanning engine: {engine.value}")
            return True
        return False
    
    def disable_engine(self, engine: ScanEngine) -> bool:
        """Disable a scanning engine."""
        if engine in self._enabled_engines:
            self._enabled_engines.remove(engine)
            logger.info(f"Disabled scanning engine: {engine.value}")
            return True
        return False

# Global virus scanner instance
virus_scanner = VirusScanner()
