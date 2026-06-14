"""
ADM Rate Limiter

Per-user rate limits for ADM Kanban API endpoints.
Prevents abuse and ensures fair usage.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from flask import current_app, g, request

from app import db

# redis_client is optional — import lazily to avoid ImportError when Redis is not configured
try:
    from app import redis_client  # type: ignore[attr-defined]
except ImportError:
    redis_client = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class ADMRateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int = 60):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)


class ADMRateLimiter:
    """
    Rate limiter for ADM Kanban API.

    Provides per-user rate limits with different tiers for different operations.
    """

    # Rate limit tiers (requests per window)
    DEFAULT_LIMITS = {
        "read": {"requests": 100, "window": 60},  # 100 reads per minute
        "write": {"requests": 20, "window": 60},  # 20 writes per minute
        "approval": {"requests": 10, "window": 60},  # 10 approvals per minute
        "transition": {"requests": 5, "window": 60},  # 5 transitions per minute
        "admin": {"requests": 50, "window": 60},  # 50 admin ops per minute
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis = redis_client

    def _get_key(self, user_id: int, action_type: str) -> str:
        """Generate Redis key for rate limit tracking."""
        return f"adm_ratelimit:{user_id}:{action_type}"

    def check_rate_limit(
        self, user_id: int, action_type: str = "read"
    ) -> Dict[str, Any]:
        """
        Check if user has exceeded rate limit.

        Args:
            user_id: User ID to check
            action_type: Type of action (read, write, approval, transition, admin)

        Returns:
            Rate limit status

        Raises:
            ADMRateLimitExceeded: If rate limit exceeded
        """
        if not self.redis:
            # Redis not available, allow request
            return {"allowed": True, "remaining": -1}

        limit_config = self.DEFAULT_LIMITS.get(action_type, self.DEFAULT_LIMITS["read"])
        max_requests = limit_config["requests"]
        window = limit_config["window"]

        key = self._get_key(user_id, action_type)
        now = time.time()

        # Get current count
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window)
        results = pipe.execute()

        current_count = results[1]

        if current_count >= max_requests:
            # Rate limit exceeded
            retry_after = window - (now % window)
            raise ADMRateLimitExceeded(
                f"Rate limit exceeded for {action_type}. Try again in {retry_after} seconds.",
                retry_after=int(retry_after),
            )

        return {
            "allowed": True,
            "remaining": max_requests - current_count - 1,
            "limit": max_requests,
            "window": window,
        }

    def get_rate_limit_status(self, user_id: int) -> Dict[str, Any]:
        """Get current rate limit status for all action types."""

        status = {}
        for action_type in self.DEFAULT_LIMITS.keys():
            key = self._get_key(user_id, action_type)
            if self.redis:
                current = self.redis.zcard(key)
                limit = self.DEFAULT_LIMITS[action_type]["requests"]
                status[action_type] = {
                    "used": current,
                    "remaining": max(0, limit - current),
                    "limit": limit,
                }
            else:
                status[action_type] = {"used": 0, "remaining": -1, "limit": -1}

        return status


# Singleton instance
adm_rate_limiter = ADMRateLimiter()
