"""
Metrics Decorator

Provides decorators for automatically collecting metrics from Flask routes and functions.
"""

import time
import logging
from functools import wraps
from typing import Callable, Any

from flask import request, g
from app.monitoring.metrics_service import metrics_service
from app.monitoring.security_monitoring import security_monitoring_service, SecurityEventType, SecuritySeverity

logger = logging.getLogger(__name__)

def track_http_requests(f: Callable) -> Callable:
    """
    Decorator to track HTTP request metrics.
    
    Automatically tracks:
    - Request count
    - Request duration
    - Error rate
    - Security events for failed requests
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        status = 'success'
        
        try:
            # Increment request counter
            endpoint = request.endpoint or 'unknown'
            method = request.method or 'unknown'
            
            metrics_service.increment_counter('http_requests_total', labels={
                'method': method,
                'endpoint': endpoint
            })
            
            # Log security event for API access
            if request.path.startswith('/api/'):
                user_id = getattr(g, 'user_id', None) if hasattr(g, 'user_id') else None
                security_monitoring_service.log_security_event(
                    event_type=SecurityEventType.API_ACCESS,
                    severity=SecuritySeverity.LOW,
                    user_id=user_id,
                    resource=request.path,
                    action=method,
                    details={'endpoint': endpoint, 'method': method}
                )
            
            # Execute the function
            result = f(*args, **kwargs)
            
            return result
            
        except Exception as e:
            status = 'error'
            
            # Increment error counter
            metrics_service.increment_counter('http_errors_total', labels={
                'method': request.method or 'unknown',
                'endpoint': request.endpoint or 'unknown',
                'error_type': type(e).__name__
            })
            
            # Log security event for permission denied
            if 'permission' in str(e).lower() or 'unauthorized' in str(e).lower():
                user_id = getattr(g, 'user_id', None) if hasattr(g, 'user_id') else None
                security_monitoring_service.log_security_event(
                    event_type=SecurityEventType.PERMISSION_DENIED,
                    severity=SecuritySeverity.MEDIUM,
                    user_id=user_id,
                    resource=request.path,
                    action=request.method or 'unknown',
                    details={'error': str(e)}
                )
            
            # Re-raise the exception
            raise
            
        finally:
            # Record request duration
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            metrics_service.record_histogram('http_request_duration_ms', duration, labels={
                'method': request.method or 'unknown',
                'endpoint': request.endpoint or 'unknown',
                'status': status
            })
    
    return decorated_function

def track_database_queries(f: Callable) -> Callable:
    """
    Decorator to track database query metrics.
    
    Automatically tracks:
    - Query count
    - Query duration
    - Query errors
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        
        try:
            # Increment query counter
            metrics_service.increment_counter('database_queries_total')
            
            # Execute the function
            result = f(*args, **kwargs)
            
            return result
            
        except Exception as e:
            # Increment error counter
            metrics_service.increment_counter('database_errors_total', labels={
                'error_type': type(e).__name__
            })
            
            # Re-raise the exception
            raise
            
        finally:
            # Record query duration
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            metrics_service.record_histogram('database_query_duration_ms', duration)
    
    return decorated_function

def track_llm_requests(f: Callable) -> Callable:
    """
    Decorator to track LLM request metrics.
    
    Automatically tracks:
    - LLM request count
    - LLM request duration
    - LLM errors
    - Token usage (if available)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        
        try:
            # Increment LLM request counter
            metrics_service.increment_counter('llm_requests_total')
            
            # Execute the function
            result = f(*args, **kwargs)
            
            # Try to extract token usage from result if available
            if isinstance(result, dict) and 'usage' in result:
                usage = result['usage']
                if 'prompt_tokens' in usage:
                    metrics_service.increment_counter('llm_prompt_tokens_total', usage['prompt_tokens'])
                if 'completion_tokens' in usage:
                    metrics_service.increment_counter('llm_completion_tokens_total', usage['completion_tokens'])
                if 'total_tokens' in usage:
                    metrics_service.increment_counter('llm_total_tokens_total', usage['total_tokens'])
            
            return result
            
        except Exception as e:
            # Increment LLM error counter
            metrics_service.increment_counter('llm_errors_total', labels={
                'error_type': type(e).__name__
            })
            
            # Log security event for LLM failures
            user_id = getattr(g, 'user_id', None) if hasattr(g, 'user_id') else None
            security_monitoring_service.log_security_event(
                event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
                severity=SecuritySeverity.MEDIUM,
                user_id=user_id,
                resource='llm_service',
                action='request',
                details={'error': str(e)}
            )
            
            # Re-raise the exception
            raise
            
        finally:
            # Record LLM request duration
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            metrics_service.record_histogram('llm_request_duration_ms', duration)
    
    return decorated_function

def track_file_uploads(f: Callable) -> Callable:
    """
    Decorator to track file upload metrics.
    
    Automatically tracks:
    - File upload count
    - Upload duration
    - File size
    - Upload errors
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        
        try:
            # Get file size if available
            file_size = 0
            if request and request.files:
                for file in request.files.values():
                    if file and hasattr(file, 'content_length'):
                        file_size += file.content_length or 0
            
            # Increment upload counter
            metrics_service.increment_counter('file_uploads_total')
            
            # Log security event for file upload
            user_id = getattr(g, 'user_id', None) if hasattr(g, 'user_id') else None
            security_monitoring_service.log_security_event(
                event_type=SecurityEventType.FILE_UPLOAD,
                severity=SecuritySeverity.LOW,
                user_id=user_id,
                resource='file_upload',
                action='upload',
                details={'file_size': file_size, 'files_count': len(request.files) if request and request.files else 0}
            )
            
            # Execute the function
            result = f(*args, **kwargs)
            
            return result
            
        except Exception as e:
            # Increment upload error counter
            metrics_service.increment_counter('file_upload_errors_total', labels={
                'error_type': type(e).__name__
            })
            
            # Log security event for upload failures
            user_id = getattr(g, 'user_id', None) if hasattr(g, 'user_id') else None
            security_monitoring_service.log_security_event(
                event_type=SecurityEventType.SECURITY_VIOLATION,
                severity=SecuritySeverity.MEDIUM,
                user_id=user_id,
                resource='file_upload',
                action='upload_failed',
                details={'error': str(e)}
            )
            
            # Re-raise the exception
            raise
            
        finally:
            # Record upload duration
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            metrics_service.record_histogram('file_upload_duration_ms', duration)
    
    return decorated_function

def track_business_events(event_type: str):
    """
    Decorator factory to track business events.
    
    Args:
        event_type: Type of business event (e.g., 'application_created', 'vendor_created')
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Execute the function
                result = f(*args, **kwargs)
                
                # Increment business event counter
                metrics_service.increment_counter(f'{event_type}_total')
                
                # Log security event for business actions
                user_id = getattr(g, 'user_id', None) if hasattr(g, 'user_id') else None
                security_monitoring_service.log_security_event(
                    event_type=SecurityEventType.DATA_ACCESS,
                    severity=SecuritySeverity.LOW,
                    user_id=user_id,
                    resource=event_type,
                    action='create',
                    details={'event_type': event_type}
                )
                
                return result
                
            except Exception as e:
                # Increment business event error counter
                metrics_service.increment_counter(f'{event_type}_errors_total', labels={
                    'error_type': type(e).__name__
                })
                
                # Re-raise the exception
                raise
        
        return decorated_function
    return decorator

# Convenience decorators for common business events
track_application_created = track_business_events('application_created')
track_vendor_created = track_business_events('vendor_created')
track_workflow_started = track_business_events('workflow_started')
track_workflow_completed = track_business_events('workflow_completed')
track_consolidation_created = track_business_events('consolidation_created')
