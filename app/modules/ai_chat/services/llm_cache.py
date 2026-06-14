"""
-> app.modules.ai_chat.services.llm_service

LLM Response Caching Service

Intelligent caching for expensive LLM operations to reduce API costs and improve response times.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

from flask import current_app

logger = logging.getLogger(__name__)


class LLMCache:
    """
    Intelligent caching service for LLM responses.

    Features:
    - Content-based cache keys (hash of requirements + context)
    - Configurable TTL
    - Memory-based storage (Redis recommended for production)
    - Cache hit/miss metrics
    """

    def __init__(self, default_ttl: int = 3600):
        """
        Initialize LLM cache.

        Args:
            default_ttl: Default time-to-live in seconds (1 hour default)
        """
        self.default_ttl = default_ttl
        self._cache = {}  # In-memory cache (use Redis in production)
        self._expiry = {}
        self._hits = 0
        self._misses = 0

    def _generate_cache_key(
        self, requirements: str, context: str = "", model_name: str = ""
    ) -> str:
        """
        Generate a stable cache key based on input content.

        Args:
            requirements: Business requirements text
            context: Additional context
            model_name: Model name (affects output)

        Returns:
            SHA - 256 hash of normalized inputs
        """
        # Normalize inputs for consistent hashing
        normalized_req = requirements.strip().lower()
        normalized_ctx = context.strip().lower()
        normalized_model = model_name.strip().lower()

        # Create composite string for hashing
        composite = f"req:{normalized_req}|ctx:{normalized_ctx}|model:{normalized_model}"

        # Generate SHA - 256 hash
        return hashlib.sha256(composite.encode("utf-8")).hexdigest()

    def get(
        self, requirements: str, context: str = "", model_name: str = ""
    ) -> Optional[Dict[Any, Any]]:
        """
        Retrieve cached LLM response if available and not expired.

        Args:
            requirements: Business requirements text
            context: Additional context
            model_name: Model name

        Returns:
            Cached response dict or None if not found/expired
        """
        cache_key = self._generate_cache_key(requirements, context, model_name)

        # Check if key exists and not expired
        if cache_key not in self._cache:
            self._misses += 1
            logger.debug(f"Cache miss for key: {cache_key}")
            return None

        # Check expiry
        if time.time() > self._expiry.get(cache_key, 0):
            # Expired - remove from cache
            del self._cache[cache_key]
            del self._expiry[cache_key]
            self._misses += 1
            logger.debug(f"Cache expired for key: {cache_key}")
            return None

        # Cache hit
        self._hits += 1
        logger.info(f"Cache hit for key: {cache_key}")
        return self._cache[cache_key].copy()

    def set(
        self,
        requirements: str,
        context: str,
        model_name: str,
        response: Dict[Any, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """
        Store LLM response in cache.

        Args:
            requirements: Business requirements text
            context: Additional context
            model_name: Model name
            response: LLM response to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        cache_key = self._generate_cache_key(requirements, context, model_name)
        ttl = ttl or self.default_ttl

        # Don't cache responses with errors
        if "error" in response:
            logger.debug(f"Not caching error response for key: {cache_key}")
            return

        # Store response and set expiry
        self._cache[cache_key] = response.copy()
        self._expiry[cache_key] = time.time() + ttl

        logger.info(f"Cached response for key: {cache_key}, TTL: {ttl}s")

        # Basic cache size management (remove oldest if too large)
        max_cache_size = current_app.config.get("LLM_CACHE_MAX_SIZE", 100)
        if len(self._cache) > max_cache_size:
            self._evict_oldest()

    def _evict_oldest(self):
        """Remove the oldest cache entry."""
        if not self._expiry:
            return

        oldest_key = min(self._expiry.keys(), key=lambda k: self._expiry[k])
        del self._cache[oldest_key]
        del self._expiry[oldest_key]
        logger.debug(f"Evicted oldest cache entry: {oldest_key}")

    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        self._expiry.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache performance metrics
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 2),
            "cache_size": len(self._cache),
            "total_requests": total_requests,
        }

    def is_cacheable(self, requirements: str, context: str = "") -> bool:
        """
        Determine if a request should be cached based on content analysis.

        Args:
            requirements: Business requirements text
            context: Additional context

        Returns:
            True if request should be cached
        """
        # Don't cache very short or very long requirements
        if len(requirements) < 50 or len(requirements) > 20000:
            return False

        # Don't cache requirements with time-sensitive content
        time_sensitive_keywords = [
            "today",
            "tomorrow",
            "this week",
            "urgent",
            "asap",
            "current date",
        ]
        req_lower = requirements.lower()

        for keyword in time_sensitive_keywords:
            if keyword in req_lower:
                return False

        return True


# Global cache instance
_llm_cache = LLMCache()


def get_cache() -> LLMCache:
    """Get the global LLM cache instance."""
    return _llm_cache
