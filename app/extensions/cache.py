"""
Redis caching extension for Flask application.
Provides decorator-based caching for expensive operations.
"""
import functools
import pickle
from typing import Any, Callable, Optional

import redis
from flask import current_app, g, has_request_context


class CacheManager:
    """
    Centralized cache management with Redis backend.
    Supports multiple serialization formats and TTL management.
    """

    def __init__(self, app=None):
        self.redis_client: Optional[redis.Redis] = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize Redis connection from Flask config."""
        redis_url = app.config.get("REDIS_URL", "redis://localhost:6379/0")
        redis_options = {
            "decode_responses": False,  # We'll handle serialization ourselves
            "socket_timeout": 2,
            "socket_connect_timeout": 2,
            "retry_on_timeout": False,
            "health_check_interval": 30,
        }

        try:
            self.redis_client = redis.from_url(redis_url, **redis_options)
            # Test connection with short timeout
            self.redis_client.ping()
            app.logger.info(f"✅ Redis cache connected: {redis_url}")
        except (redis.ConnectionError, redis.TimeoutError, ConnectionRefusedError, OSError) as e:
            app.logger.warning(f"⚠️  Redis connection failed: {e}. Caching disabled.")
            self.redis_client = None

        # Store cache manager in app extensions
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["cache"] = self

    def get(self, key: str, default=None) -> Any:
        """Get value from cache."""
        if not self.redis_client:
            return default

        try:
            value = self.redis_client.get(key)
            if value is None:
                return default
            return pickle.loads(value)
        except Exception as e:
            current_app.logger.error(f"Cache GET error for key {key}: {e}")
            return default

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (will be pickled)
            ttl: Time to live in seconds (default 5 minutes)
        """
        if not self.redis_client:
            return False

        try:
            serialized = pickle.dumps(value)
            return self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            current_app.logger.error(f"Cache SET error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.redis_client:
            return False

        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            current_app.logger.error(f"Cache DELETE error for key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Redis pattern (e.g., 'user:*', 'api:v1:*')

        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            current_app.logger.error(f"Cache DELETE_PATTERN error for pattern {pattern}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.redis_client:
            return False

        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            current_app.logger.error(f"Cache EXISTS error for key {key}: {e}")
            return False

    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter in cache."""
        if not self.redis_client:
            return None

        try:
            return self.redis_client.incrby(key, amount)
        except Exception as e:
            current_app.logger.error(f"Cache INCR error for key {key}: {e}")
            return None

    def expire(self, key: str, ttl: int) -> bool:
        """Update TTL for existing key."""
        if not self.redis_client:
            return False

        try:
            return bool(self.redis_client.expire(key, ttl))
        except Exception as e:
            current_app.logger.error(f"Cache EXPIRE error for key {key}: {e}")
            return False

    def flush_all(self) -> bool:
        """Flush all cache data (use with caution in production)."""
        if not self.redis_client:
            return False

        try:
            self.redis_client.flushdb()
            return True
        except Exception as e:
            current_app.logger.error(f"Cache FLUSH error: {e}")
            return False

    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self.redis_client:
            return {"status": "disconnected"}

        try:
            info = self.redis_client.info("stats")
            memory = self.redis_client.info("memory")
            return {
                "status": "connected",
                "total_keys": self.redis_client.dbsize(),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info),
                "memory_used": memory.get("used_memory_human", "N/A"),
                "memory_peak": memory.get("used_memory_peak_human", "N/A"),
            }
        except Exception as e:
            current_app.logger.error(f"Cache STATS error: {e}")
            return {"status": "error", "error": str(e)}

    def _calculate_hit_rate(self, stats: dict) -> str:
        """Calculate cache hit rate percentage."""
        hits = stats.get("keyspace_hits", 0)
        misses = stats.get("keyspace_misses", 0)
        total = hits + misses
        if total == 0:
            return "0.00%"
        return f"{(hits / total * 100):.2f}%"


# Singleton instance
cache_manager = CacheManager()


def current_tenant_key() -> str:
    """The organisation component of every cache key.

    Archie's tenancy is enforced by an ORM event that adds
    ``organization_id = g.current_org_id`` to queries, so two organisations
    calling the same function get different rows back. A cache key built only
    from the function name and its arguments therefore collides across
    tenants — and for a cached *view* that takes no arguments, the key is a
    constant, so the first organisation to load the page fills the cache and
    every other organisation is served that organisation's rendered HTML until
    the TTL expires.

    Including the tenant here rather than at each call site makes the safe
    behaviour the default: a new ``@cached`` cannot leak by omission.
    """
    org_id = getattr(g, "current_org_id", None) if has_request_context() else None
    # One spelling for "no tenant", so a CLI call and an unauthenticated request
    # share a bucket that no real organisation can ever collide with.
    return f"org:{org_id}" if org_id is not None else "org:none"


def cached(ttl: int = 300, key_prefix: str = "", key_func: Optional[Callable] = None):
    """
    Decorator for caching function results.

    Usage:
        @cached(ttl=600, key_prefix='user_profile')
        def get_user_profile(user_id):
            return expensive_database_query(user_id)

    Args:
        ttl: Cache TTL in seconds (default 5 minutes)
        key_prefix: Prefix for cache key
        key_func: Custom function to generate cache key from args/kwargs.
            If the value it returns is ``None``, the cache is bypassed
            entirely for that call (fail closed) rather than caching under
            an unscoped key that every other caller would then share.

    Every key is ALSO scoped to the calling organisation — see
    ``current_tenant_key``. The two mechanisms were built independently on
    two branches for the same defect and both are kept: the automatic tenant
    prefix makes a new ``@cached`` safe by omission, and the fail-closed
    key_func lets a call site scope on something the prefix cannot see and
    refuse to cache when it cannot.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            tenant = current_tenant_key()
            if key_func:
                key_suffix = key_func(*args, **kwargs)
                if key_suffix is None:
                    # Fail closed: key_func could not produce a scoping
                    # value, so run uncached rather than cache an answer
                    # under a key every other caller would also match.
                    return func(*args, **kwargs)
                cache_key = f"{tenant}:{key_prefix}:{key_suffix}"
            else:
                # Default: use function name + args + kwargs
                args_str = "_".join(str(arg) for arg in args)
                kwargs_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = (
                    f"{tenant}:{key_prefix}:{func.__name__}:{args_str}:{kwargs_str}"
                )

            # Try to get from cache
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                current_app.logger.debug(f"Cache HIT: {cache_key}")
                return cached_value

            # Cache miss - execute function
            current_app.logger.debug(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)

            # Store in cache
            cache_manager.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


def invalidate_cache(pattern: str, all_tenants: bool = False):
    """
    Invalidate cache keys matching pattern.

    Usage:
        invalidate_cache('user:123:*')
        invalidate_cache('api:v1:applications:*')

    The pattern is scoped to the calling organisation, matching how ``cached``
    builds its keys. Pass ``all_tenants=True`` only from maintenance paths that
    genuinely need to clear every organisation's entries.
    """
    if not all_tenants:
        pattern = f"{current_tenant_key()}:{pattern}"
    deleted = cache_manager.delete_pattern(pattern)
    current_app.logger.info(f"Invalidated {deleted} cache keys matching: {pattern}")
    return deleted
