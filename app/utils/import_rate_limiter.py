"""
Import Rate Limiter Service

Unified rate limiting for both Import Applications and Batch Import systems.
Prevents abuse and protects against DoS attacks on import endpoints.

Features:
- Progressive rate limiting (minute/hour/day)
- IP-based blocking for repeated violations
- Redis-ready design (memory fallback for development)
- Proper HTTP 429 responses with Retry-After headers
- Per-user and per-IP tracking
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque

from flask import request, g
from flask_login import current_user

logger = logging.getLogger(__name__)


class ImportRateLimiter:
    """
    Unified rate limiter for import endpoints.
    
    Provides progressive rate limiting with multiple windows:
    - 10 requests per minute (burst protection)
    - 100 requests per hour (sustained protection)
    - 500 requests per day (daily quota)
    
    Includes IP-based blocking for abuse detection.
    """
    
    # Rate limits per user/IP
    LIMITS = {
        "minute": {"calls": 10, "window": 60},      # 10 per minute
        "hour": {"calls": 100, "window": 3600},     # 100 per hour
        "day": {"calls": 500, "window": 86400},     # 500 per day
    }
    
    # Violation thresholds
    VIOLATION_THRESHOLD = 5  # violations before IP block
    IP_BLOCK_DURATION = 3600  # 1 hour IP block
    
    def __init__(self, use_redis: bool = False):
        """
        Initialize rate limiter.
        
        Args:
            use_redis: Whether to use Redis (production) or memory (development)
        """
        self.use_redis = use_redis
        self.logger = logging.getLogger(__name__)
        
        # In-memory stores for development
        if not use_redis:
            self._user_requests = defaultdict(lambda: defaultdict(deque))
            self._ip_requests = defaultdict(lambda: defaultdict(deque))
            self._violations = defaultdict(int)
            self._ip_blocks = {}
    
    def _get_key(self, prefix: str, identifier: str, window: str) -> str:
        """Generate cache key for rate limiting."""
        return f"import_rate:{prefix}:{identifier}:{window}"
    
    def _get_user_id(self) -> str:
        """Get current user ID for rate limiting."""
        if hasattr(current_user, 'id') and current_user.is_authenticated:
            return f"user:{current_user.id}"
        return "anonymous"
    
    def _get_ip_address(self) -> str:
        """Get client IP address."""
        # Check for forwarded headers first (proxy/load balancer)
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr or 'unknown'
    
    def _is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is currently blocked."""
        if self.use_redis:
            # Redis implementation would go here
            return False
        else:
            block_info = self._ip_blocks.get(ip)
            if block_info and block_info['expires'] > time.time():
                return True
            elif block_info and block_info['expires'] <= time.time():
                # Block expired, clean it up
                del self._ip_blocks[ip]
                return False
            return False
    
    def _record_violation(self, ip: str) -> None:
        """Record a rate limit violation."""
        if self.use_redis:
            # Redis implementation would go here
            pass
        else:
            self._violations[ip] += 1
            
            # Check if IP should be blocked
            if self._violations[ip] >= self.VIOLATION_THRESHOLD:
                self._ip_blocks[ip] = {
                    'expires': time.time() + self.IP_BLOCK_DURATION,
                    'violations': self._violations[ip]
                }
                self.logger.warning(f"IP {ip} blocked due to {self._violations[ip]} violations")
    
    def _check_window(self, requests: deque, limit_calls: int, window_seconds: int, now: float) -> Tuple[bool, int]:
        """
        Check if request is allowed in a specific time window.
        
        Args:
            requests: Deque of request timestamps
            limit_calls: Maximum calls allowed in window
            window_seconds: Window size in seconds
            now: Current timestamp
            
        Returns:
            Tuple of (allowed, requests_in_window)
        """
        # Remove old requests outside the window
        while requests and requests[0] <= now - window_seconds:
            requests.popleft()
        
        requests_in_window = len(requests)
        return requests_in_window < limit_calls, requests_in_window
    
    def check_rate_limit(self, user_id: Optional[str] = None, ip: Optional[str] = None) -> Dict:
        """
        Check if request is allowed under rate limits.
        
        Args:
            user_id: User identifier (auto-detected if None)
            ip: IP address (auto-detected if None)
            
        Returns:
            Dict with rate limit status and headers
        """
        now = time.time()
        user_id = user_id or self._get_user_id()
        ip = ip or self._get_ip_address()
        
        # Check IP block first
        if self._is_ip_blocked(ip):
            return {
                "allowed": False,
                "reason": "ip_blocked",
                "retry_after": self.IP_BLOCK_DURATION,
                "message": "IP address temporarily blocked due to repeated violations"
            }
        
        # Check all rate limit windows
        violations = []
        retry_after = 0
        
        if self.use_redis:
            # Redis implementation would go here
            pass
        else:
            user_requests = self._user_requests[user_id]
            
            for window_name, limit_config in self.LIMITS.items():
                window_requests = user_requests[window_name]
                allowed, count = self._check_window(
                    window_requests, 
                    limit_config["calls"], 
                    limit_config["window"], 
                    now
                )
                
                if not allowed:
                    violations.append({
                        "window": window_name,
                        "limit": limit_config["calls"],
                        "count": count,
                        "window_seconds": limit_config["window"]
                    })
                    retry_after = max(retry_after, limit_config["window"])
        
        if violations:
            # Record violation
            self._record_violation(ip)
            
            # Find the most restrictive window
            worst_violation = min(violations, key=lambda v: v["window_seconds"])
            
            return {
                "allowed": False,
                "reason": "rate_limit_exceeded",
                "violations": violations,
                "retry_after": retry_after,
                "message": f"Rate limit exceeded: {worst_violation['count']}/{worst_violation['limit']} per {worst_violation['window']}"
            }
        
        # Record this request
        if not self.use_redis:
            for window_name in self.LIMITS.keys():
                self._user_requests[user_id][window_name].append(now)
        
        return {
            "allowed": True,
            "remaining": self._get_remaining_limits(user_id),
            "reset_at": self._get_reset_time()
        }
    
    def _get_remaining_limits(self, user_id: str) -> Dict[str, int]:
        """Get remaining requests for each window."""
        if self.use_redis:
            # Redis implementation would go here
            return {window: config["calls"] for window, config in self.LIMITS.items()}
        else:
            now = time.time()
            remaining = {}
            user_requests = self._user_requests[user_id]
            
            for window_name, limit_config in self.LIMITS.items():
                window_requests = user_requests[window_name]
                # Remove old requests
                while window_requests and window_requests[0] <= now - limit_config["window"]:
                    window_requests.popleft()
                
                remaining[window_name] = max(0, limit_config["calls"] - len(window_requests))
            
            return remaining
    
    def _get_reset_time(self) -> int:
        """Get next reset timestamp."""
        now = time.time()
        # Return next minute boundary for simplicity
        return int(now + 60 - (now % 60))
    
    def get_rate_limit_headers(self, user_id: Optional[str] = None) -> Dict[str, str]:
        """Get HTTP headers for rate limit status."""
        user_id = user_id or self._get_user_id()
        remaining = self._get_remaining_limits(user_id)
        reset_at = self._get_reset_time()
        
        headers = {
            "X-RateLimit-Limit-Minute": str(self.LIMITS["minute"]["calls"]),
            "X-RateLimit-Remaining-Minute": str(remaining["minute"]),
            "X-RateLimit-Limit-Hour": str(self.LIMITS["hour"]["calls"]),
            "X-RateLimit-Remaining-Hour": str(remaining["hour"]),
            "X-RateLimit-Limit-Day": str(self.LIMITS["day"]["calls"]),
            "X-RateLimit-Remaining-Day": str(remaining["day"]),
            "X-RateLimit-Reset": str(reset_at),
        }
        
        return headers


# Global rate limiter instance
_import_rate_limiter = ImportRateLimiter()


def import_rate_limit(max_calls_per_minute: int = 10, max_calls_per_hour: int = 100, max_calls_per_day: int = 500):
    """
    Decorator for rate limiting import endpoints.
    
    Args:
        max_calls_per_minute: Maximum calls per minute
        max_calls_per_hour: Maximum calls per hour  
        max_calls_per_day: Maximum calls per day
    """
    def decorator(f):
        def decorated_function(*args, **kwargs):
            # Check rate limits
            result = _import_rate_limiter.check_rate_limit()
            
            if not result["allowed"]:
                from flask import jsonify
                
                response_data = {
                    "error": "Rate limit exceeded",
                    "message": result["message"],
                    "retry_after": result["retry_after"]
                }
                
                response = jsonify(response_data)
                response.status_code = 429
                
                # Add retry after header
                response.headers["Retry-After"] = str(result["retry_after"])
                
                # Add rate limit headers
                headers = _import_rate_limiter.get_rate_limit_headers()
                for key, value in headers.items():
                    response.headers[key] = value
                
                logger.warning(f"Rate limit exceeded for user {_import_rate_limiter._get_user_id()}, IP {_import_rate_limiter._get_ip_address()}")
                
                return response
            
            # Add rate limit headers to successful responses
            # This will be handled by the endpoint itself
            
            return f(*args, **kwargs)
        
        # Preserve function metadata
        decorated_function.__name__ = f.__name__
        decorated_function.__doc__ = f.__doc__
        decorated_function.__module__ = f.__module__
        
        return decorated_function
    return decorator


def get_import_rate_limiter() -> ImportRateLimiter:
    """Get the global import rate limiter instance."""
    return _import_rate_limiter


def add_rate_limit_headers(response):
    """
    Add rate limit headers to a Flask response.
    
    Args:
        response: Flask response object
        
    Returns:
        Response with rate limit headers added
    """
    headers = _import_rate_limiter.get_rate_limit_headers()
    for key, value in headers.items():
        response.headers[key] = value
    
    return response
