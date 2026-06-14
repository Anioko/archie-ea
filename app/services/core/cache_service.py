"""
Cache Service for reducing LLM API costs and improving performance

Uses Redis for caching expensive operations like:
- LLM API calls
- Options analysis
- ArchiMate extraction
- Document processing
"""

import hashlib
import json
import logging
import os
from functools import wraps
from typing import Any, Callable, Optional

import redis

logger = logging.getLogger(__name__)


class CacheService:
    """Centralized caching service using Redis"""

    def __init__(self):
        """Initialize Redis connection"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = None  # Default to None

        # Only try to connect if explicitly enabled
        if os.getenv("ENABLE_REDIS_CACHE", "false").lower() == "true":
            try:
                import socket

                socket.setdefaulttimeout(2)  # 2 second timeout
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                # Don't ping here - let it fail gracefully on first use
                logger.info(f"Redis client initialized for {redis_url}")
            except Exception as e:
                logger.warning(f"Redis client initialization failed: {e} - caching disabled")
                self.redis_client = None
        else:
            logger.info("Redis caching disabled (ENABLE_REDIS_CACHE not set to 'true')")

    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate deterministic cache key from function arguments

        Args:
            prefix: Cache key prefix (e.g., 'options_analysis', 'llm_call')
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            MD5 hash of serialized arguments
        """
        # Sort kwargs for deterministic key generation
        sorted_kwargs = {k: kwargs[k] for k in sorted(kwargs.keys())}

        # Create hashable representation
        key_data = {"args": args, "kwargs": sorted_kwargs}

        serialized = json.dumps(key_data, sort_keys=True, default=str)
        hash_key = hashlib.md5(serialized.encode()).hexdigest()

        return f"{prefix}:{hash_key}"

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not self.redis_client:
            return None

        try:
            cached_value = self.redis_client.get(key)
            if cached_value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(cached_value)
            else:
                logger.debug(f"Cache MISS: {key}")
                return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (default: 1 hour)

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            serialized = json.dumps(value, default=str)
            self.redis_client.setex(key, ttl, serialized)
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete value from cache

        Args:
            key: Cache key

        Returns:
            True if deleted, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            deleted = self.redis_client.delete(key)
            if deleted:
                logger.debug(f"Cache DELETE: {key}")
            return bool(deleted)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern

        Args:
            pattern: Pattern to match (e.g., 'options_analysis:*')

        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cache DELETE PATTERN: {pattern} ({deleted} keys)")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            return 0

    def cached(
        self, ttl: int = 3600, prefix: str = "default", invalidate_on: Optional[list] = None
    ):
        """
        Decorator for caching function results

        Args:
            ttl: Time-to-live in seconds (default: 1 hour)
            prefix: Cache key prefix
            invalidate_on: List of events that should invalidate cache

        Usage:
            @cache_service.cached(ttl=86400, prefix="options_analysis")
            def analyze_options(requirement, context):
                # Expensive operation
                return result
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self._generate_cache_key(f"{prefix}:{func.__name__}", *args, **kwargs)

                # Try cache first
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    logger.info(f"Using cached result for {func.__name__}")
                    return cached_value

                # Cache miss - execute function
                logger.info(f"Computing fresh result for {func.__name__}")
                result = func(*args, **kwargs)

                # Store in cache
                self.set(cache_key, result, ttl)

                return result

            # Add method to manually invalidate cache
            wrapper.invalidate_cache = lambda *args, **kwargs: self.delete(
                self._generate_cache_key(f"{prefix}:{func.__name__}", *args, **kwargs)
            )

            return wrapper

        return decorator

    def get_stats(self) -> dict:
        """
        Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        if not self.redis_client:
            return {"status": "disabled"}

        try:
            info = self.redis_client.info("stats")
            return {
                "status": "active",
                "total_keys": self.redis_client.dbsize(),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": info.get("keyspace_hits", 0)
                / max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1)
                * 100,
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"status": "error", "message": str(e)}

    # =========================================================================
    # Shared Context Methods for Intelligent Integration (FR - 001)
    # =========================================================================

    def get_agent_context(self, agent_name: str, context_key: str) -> Optional[Any]:
        """
        Get agent-specific context from cache.

        Args:
            agent_name: Name of the agent
            context_key: Key for the context data

        Returns:
            Cached context value or None if not found
        """
        cache_key = f"agent_context:{agent_name}:{context_key}"
        return self.get(cache_key)

    def set_agent_context(
        self, agent_name: str, context_key: str, value: Any, ttl: int = 3600
    ) -> bool:
        """
        Set agent-specific context in cache.

        Args:
            agent_name: Name of the agent
            context_key: Key for the context data
            value: Value to cache
            ttl: Time-to-live in seconds (default: 1 hour)

        Returns:
            True if successful, False otherwise
        """
        cache_key = f"agent_context:{agent_name}:{context_key}"
        return self.set(cache_key, value, ttl)

    def delete_agent_context(self, agent_name: str, context_key: str = None) -> bool:
        """
        Delete agent context from cache.

        Args:
            agent_name: Name of the agent
            context_key: Optional specific key to delete (None = all agent context)

        Returns:
            True if deleted, False otherwise
        """
        if context_key:
            cache_key = f"agent_context:{agent_name}:{context_key}"
            return self.delete(cache_key)
        else:
            pattern = f"agent_context:{agent_name}:*"
            return self.delete_pattern(pattern) > 0

    def get_shared_workflow_context(self, workflow_id: int) -> dict:
        """
        Get shared context for a workflow instance.

        Args:
            workflow_id: ID of the workflow instance

        Returns:
            Dictionary with workflow context or empty dict if not found
        """
        cache_key = f"workflow_context:{workflow_id}"
        return self.get(cache_key) or {}

    def update_shared_workflow_context(
        self, workflow_id: int, updates: dict, ttl: int = 7200
    ) -> bool:
        """
        Update shared workflow context with new data.

        Args:
            workflow_id: ID of the workflow instance
            updates: Dictionary of updates to merge
            ttl: Time-to-live in seconds (default: 2 hours)

        Returns:
            True if successful, False otherwise
        """
        cache_key = f"workflow_context:{workflow_id}"
        existing = self.get(cache_key) or {}
        existing.update(updates)
        return self.set(cache_key, existing, ttl)

    def clear_workflow_context(self, workflow_id: int) -> bool:
        """
        Clear workflow context when completed.

        Args:
            workflow_id: ID of the workflow instance

        Returns:
            True if deleted, False otherwise
        """
        return self.delete(f"workflow_context:{workflow_id}")

    def share_context_between_agents(
        self,
        source_agent: str,
        target_agents: list,
        context_key: str,
        context_value: Any,
        ttl: int = 3600,
    ) -> bool:
        """
        Share context from one agent to multiple target agents.

        Args:
            source_agent: Name of the source agent
            target_agents: List of target agent names
            context_key: Key for the context data
            context_value: Value to share
            ttl: Time-to-live in seconds (default: 1 hour)

        Returns:
            True if all shares successful, False otherwise
        """
        success = True

        # Store with source agent reference for audit
        shared_data = {
            "value": context_value,
            "source_agent": source_agent,
            "shared_at": json.dumps({"timestamp": "now"}),
        }

        for target in target_agents:
            cache_key = f"agent_context:{target}:shared:{source_agent}:{context_key}"
            if not self.set(cache_key, shared_data, ttl):
                success = False
                logger.warning(f"Failed to share context to agent: {target}")

        if success:
            logger.info(
                f"Context shared from {source_agent} to {len(target_agents)} agents: {context_key}"
            )

        return success

    def get_service_registry(self) -> dict:
        """
        Get the service registry for service mesh.

        Returns:
            Dictionary of registered services and their health status
        """
        cache_key = "service_mesh:registry"
        return self.get(cache_key) or {}

    def register_service(self, service_name: str, service_info: dict, ttl: int = 300) -> bool:
        """
        Register a service in the service mesh registry.

        Args:
            service_name: Name of the service
            service_info: Service information (endpoints, capabilities, health)
            ttl: Time-to-live in seconds (default: 5 minutes for health refresh)

        Returns:
            True if successful, False otherwise
        """
        registry = self.get_service_registry()
        registry[service_name] = {**service_info, "registered_at": json.dumps({"timestamp": "now"})}
        return self.set("service_mesh:registry", registry, ttl)

    def get_circuit_breaker_state(self, service_name: str) -> Optional[dict]:
        """
        Get circuit breaker state for a service.

        Args:
            service_name: Name of the service

        Returns:
            Circuit breaker state dict or None
        """
        cache_key = f"circuit_breaker:{service_name}"
        return self.get(cache_key)

    def set_circuit_breaker_state(self, service_name: str, state: dict, ttl: int = 300) -> bool:
        """
        Set circuit breaker state for a service.

        Args:
            service_name: Name of the service
            state: Circuit breaker state (state, failure_count, last_failure)
            ttl: Time-to-live in seconds (default: 5 minutes)

        Returns:
            True if successful, False otherwise
        """
        cache_key = f"circuit_breaker:{service_name}"
        return self.set(cache_key, state, ttl)


# Global cache instance
cache_service = CacheService()
