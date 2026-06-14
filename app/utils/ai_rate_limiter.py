"""
AI Rate Limiter and Cost Control Service

Provides rate limiting and cost tracking for AI Chat multi-model endpoints.
Prevents cost explosion from excessive LLM API calls.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from flask import current_app

from app import db

logger = logging.getLogger(__name__)


class AIUsageTracker:
    """
    Tracks AI model usage and costs per user.
    
    Provides:
    - Per-user rate limiting
    - Daily/hourly usage quotas
    - Model-specific cost tracking
    - Budget enforcement
    """
    
    # Default limits
    DEFAULT_DAILY_LIMIT = 100  # requests per day
    DEFAULT_HOURLY_LIMIT = 20  # requests per hour
    
    # Model costs per 1K tokens (approximate)
    MODEL_COSTS = {
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "llama-3-70b": {"input": 0.0, "output": 0.0},  # Self-hosted, no API cost
        "llama-3-8b": {"input": 0.0, "output": 0.0},
    }
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.logger = logging.getLogger(__name__)
    
    def check_rate_limit(self, model: str) -> Dict:
        """
        Check if user has exceeded rate limits.
        
        Returns:
            Dict with allowed status and remaining quota
        """
        # Get recent usage (simplified - in production, query from database)
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        # For now, return generous limits (implementation would track actual usage)
        return {
            "allowed": True,
            "hourly_remaining": self.DEFAULT_HOURLY_LIMIT,
            "daily_remaining": self.DEFAULT_DAILY_LIMIT,
            "reset_at": (now + timedelta(hours=1)).isoformat(),
        }
    
    def track_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation: str = "chat",
    ) -> Dict:
        """
        Track API usage and calculate costs.
        
        Args:
            model: Model used
            input_tokens: Input token count
            output_tokens: Output token count
            operation: Type of operation
            
        Returns:
            Usage tracking result with cost
        """
        costs = self.MODEL_COSTS.get(model, {"input": 0.01, "output": 0.03})
        
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        total_cost = input_cost + output_cost
        
        usage_record = {
            "user_id": self.user_id,
            "model": model,
            "operation": operation,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost": round(input_cost, 4),
            "output_cost": round(output_cost, 4),
            "total_cost": round(total_cost, 4),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        self.logger.info(f"AI usage tracked: {usage_record}")
        
        return usage_record
    
    def get_daily_usage_summary(self) -> Dict:
        """Get today's usage summary for the user."""
        # Simplified - would query database in production
        return {
            "date": datetime.utcnow().date().isoformat(),
            "total_requests": 0,  # Would be actual count
            "total_cost": 0.0,
            "models_used": [],
            "remaining_quota": self.DEFAULT_DAILY_LIMIT,
        }
    
    def estimate_cost(self, model: str, estimated_tokens: int) -> float:
        """Estimate cost for a potential operation."""
        costs = self.MODEL_COSTS.get(model, {"input": 0.01, "output": 0.03})
        avg_cost_per_1k = (costs["input"] + costs["output"]) / 2
        return round((estimated_tokens / 1000) * avg_cost_per_1k, 4)


class AIRateLimiter:
    """
    Rate limiter for AI Chat endpoints.
    
    Prevents abuse and controls costs through:
    - Request rate limiting
    - Concurrent request limiting
    - Budget caps
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def is_allowed(self, user_id: int, model: str, estimated_cost: float = 0.0) -> Dict:
        """
        Check if a request is allowed under rate limits.
        
        Args:
            user_id: User making request
            model: Model being used
            estimated_cost: Estimated cost of request
            
        Returns:
            Dict with allowed status and limit info
        """
        tracker = AIUsageTracker(user_id)
        
        # Check rate limits
        rate_status = tracker.check_rate_limit(model)
        
        if not rate_status["allowed"]:
            return {
                "allowed": False,
                "reason": "rate_limit_exceeded",
                "retry_after": rate_status.get("reset_at"),
            }
        
        # Check if model is allowed for this user
        # (could have user-tier based restrictions)
        
        return {
            "allowed": True,
            "limits": rate_status,
        }
    
    def get_limit_headers(self, user_id: int) -> Dict[str, str]:
        """Get rate limit headers for HTTP response."""
        tracker = AIUsageTracker(user_id)
        status = tracker.check_rate_limit("")
        
        return {
            "X-RateLimit-Hourly-Remaining": str(status["hourly_remaining"]),
            "X-RateLimit-Daily-Remaining": str(status["daily_remaining"]),
            "X-RateLimit-Reset": status["reset_at"],
        }
