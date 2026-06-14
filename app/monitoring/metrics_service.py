"""
Metrics Service

Provides comprehensive metrics collection and aggregation for system monitoring.
"""

import logging
import time  # dead-code-ok
from datetime import datetime, timedelta  # dead-code-ok
from typing import Dict, List, Any, Optional  # dead-code-ok
from collections import defaultdict, deque
import threading

from flask import current_app  # dead-code-ok

logger = logging.getLogger(__name__)

class MetricsService:
    """
    Service for collecting, storing, and aggregating system metrics.
    """
    
    def __init__(self):
        """Initialize the metrics service."""
        self._metrics = defaultdict(lambda: {
            'count': 0,
            'sum': 0,
            'min': float('inf'),
            'max': float('-inf'),
            'last_updated': None
        })
        self._counters = defaultdict(int)
        self._gauges = defaultdict(float)
        self._histograms = defaultdict(lambda: deque(maxlen=1000))  # Keep last 1000 values
        self._lock = threading.Lock()
        
        # Initialize system metrics
        self._initialize_system_metrics()
    
    def _initialize_system_metrics(self):
        """Initialize system-wide metrics tracking."""
        # Application metrics
        self._gauges['app_uptime'] = 0.0
        self._counters['http_requests_total'] = 0
        self._counters['http_errors_total'] = 0
        self._counters['database_queries_total'] = 0
        self._counters['llm_requests_total'] = 0
        self._counters['llm_errors_total'] = 0
        
        # Business metrics
        self._counters['applications_created_total'] = 0
        self._counters['vendors_created_total'] = 0
        self._counters['documents_uploaded_total'] = 0
        self._counters['workflows_started_total'] = 0
        self._counters['workflows_completed_total'] = 0
        self._counters['consolidation_candidates_total'] = 0
        
        # Performance metrics
        self._histograms['http_request_duration_ms']
        self._histograms['database_query_duration_ms']
        self._histograms['llm_request_duration_ms']
        self._histograms['file_upload_duration_ms']
    
    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict] = None):
        """
        Increment a counter metric.
        
        Args:
            name: Counter name
            value: Increment value (default: 1)
            labels: Optional labels for the counter
        """
        with self._lock:
            if labels:
                # Create labeled counter name
                label_str = ','.join(f"{k}={v}" for k, v in sorted(labels.items()))
                full_name = f"{name}{{{label_str}}}"
                self._counters[full_name] += value
            else:
                self._counters[name] += value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict] = None):
        """
        Set a gauge metric value.
        
        Args:
            name: Gauge name
            value: Gauge value
            labels: Optional labels for the gauge
        """
        with self._lock:
            if labels:
                label_str = ','.join(f"{k}={v}" for k, v in sorted(labels.items()))
                full_name = f"{name}{{{label_str}}}"
                self._gauges[full_name] = value
            else:
                self._gauges[name] = value
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict] = None):
        """
        Record a value in a histogram.
        
        Args:
            name: Histogram name
            value: Value to record
            labels: Optional labels for the histogram
        """
        with self._lock:
            if labels:
                label_str = ','.join(f"{k}={v}" for k, v in sorted(labels.items()))
                full_name = f"{name}{{{label_str}}}"
                self._histograms[full_name].append(value)
            else:
                self._histograms[name].append(value)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.
        
        Returns:
            Dictionary containing all metrics
        """
        with self._lock:
            metrics = {}
            
            # Add counters
            for name, value in self._counters.items():
                metrics[name] = {
                    'type': 'counter',
                    'value': value,
                    'help': f'Counter metric for {name}'
                }
            
            # Add gauges
            for name, value in self._gauges.items():
                metrics[name] = {
                    'type': 'gauge',
                    'value': value,
                    'help': f'Gauge metric for {name}'
                }
            
            # Add histograms
            for name, values in self._histograms.items():
                if values:
                    sorted_values = sorted(values)
                    metrics[name] = {
                        'type': 'histogram',
                        'count': len(values),
                        'sum': sum(values),
                        'min': min(values),
                        'max': max(values),
                        'mean': sum(values) / len(values),
                        'p50': sorted_values[len(sorted_values) // 2],
                        'p95': sorted_values[int(len(sorted_values) * 0.95)],
                        'p99': sorted_values[int(len(sorted_values) * 0.99)],
                        'help': f'Histogram metric for {name}'
                    }
            
            # Add system metrics
            metrics.update(self._get_system_metrics())
            
            return metrics
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system-level metrics.
        
        Returns:
            Dictionary containing system metrics
        """
        metrics = {}
        
        try:
            # Memory metrics
            import psutil
            memory = psutil.virtual_memory()
            metrics['system_memory_bytes'] = {
                'type': 'gauge',
                'value': memory.total,
                'help': 'Total system memory in bytes'
            }
            metrics['system_memory_available_bytes'] = {
                'type': 'gauge',
                'value': memory.available,
                'help': 'Available system memory in bytes'
            }
            metrics['system_memory_percent'] = {
                'type': 'gauge',
                'value': memory.percent,
                'help': 'System memory usage percentage'
            }
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics['system_cpu_percent'] = {
                'type': 'gauge',
                'value': cpu_percent,
                'help': 'System CPU usage percentage'
            }
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            metrics['system_disk_bytes'] = {
                'type': 'gauge',
                'value': disk.total,
                'help': 'Total disk space in bytes'
            }
            metrics['system_disk_free_bytes'] = {
                'type': 'gauge',
                'value': disk.free,
                'help': 'Free disk space in bytes'
            }
            metrics['system_disk_percent'] = {
                'type': 'gauge',
                'value': (disk.total - disk.free) / disk.total * 100,
                'help': 'Disk usage percentage'
            }
            
        except Exception as e:
            logger.warning(f"Failed to collect system metrics: {e}")
        
        # Database metrics
        try:
            from app import db
            
            # Get database connection pool info if available
            if hasattr(db.engine.pool, 'size'):
                metrics['database_pool_size'] = {
                    'type': 'gauge',
                    'value': db.engine.pool.size(),
                    'help': 'Database connection pool size'
                }
                metrics['database_pool_checked_in'] = {
                    'type': 'gauge',
                    'value': db.engine.pool.checkedin(),
                    'help': 'Database connections checked in'
                }
                metrics['database_pool_checked_out'] = {
                    'type': 'gauge',
                    'value': db.engine.pool.checkedout(),
                    'help': 'Database connections checked out'
                }
            
            # Get table row counts
            table_metrics = self._get_table_metrics()
            metrics.update(table_metrics)
            
        except Exception as e:
            logger.warning(f"Failed to collect database metrics: {e}")
        
        return metrics
    
    def _get_table_metrics(self) -> Dict[str, Any]:
        """
        Get database table metrics.
        
        Returns:
            Dictionary containing table metrics
        """
        metrics = {}
        
        try:
            from app import db
            
            tables_to_monitor = [
                'application_components',
                'vendor_organizations',
                'unified_capabilities',
                'llm_interactions',
                'consolidation_candidates',
                'ea_workflow_instances'
            ]
            
            for table in tables_to_monitor:
                # table is from the static allow-list above (never user input);
                # db.text() is required under SQLAlchemy 2.0 — a bare string raises
                # and was being silently swallowed by the except below.
                try:
                    result = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table}"))  # tenant-exempt: metrics monitoring
                    count = result.scalar()
                    metrics[f'database_table_rows{{table="{table}"}}'] = {
                        'type': 'gauge',
                        'value': count,
                        'help': f'Number of rows in {table} table'
                    }
                except Exception as e:
                    logger.debug(f"Failed to get row count for {table}: {e}")
                    
        except Exception as e:
            logger.warning(f"Failed to collect table metrics: {e}")
        
        return metrics
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._initialize_system_metrics()
    
    def get_metric_summary(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """
        Get summary of a specific metric.
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Metric summary or None if not found
        """
        with self._lock:
            all_metrics = self.get_all_metrics()
            return all_metrics.get(metric_name)

# Global metrics service instance
metrics_service = MetricsService()
