"""
Database Query Profiling Middleware — DISABLED (STAB-003)

Tracks slow queries, N + 1 problems, and query patterns.
Inspired by django-silk but for Flask.

NOTE: This middleware is DISABLED per STAB-003 stability reset.
init_app() is never called, so no SQLAlchemy event listeners or
before_request/after_request hooks are registered.
Do NOT call query_profiler.init_app(app) until the stability plan is complete.
"""
import functools
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from flask import current_app, g, request
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Thread-local storage for query tracking
_query_stack = threading.local()


class QueryProfile:
    """Profile data for a single query."""

    def __init__(self, statement: str, parameters: tuple, start_time: float):
        self.statement = statement
        self.parameters = parameters
        self.start_time = start_time
        self.end_time: Optional[float] = None
        self.duration_ms: Optional[float] = None
        self.traceback: Optional[str] = None

    def finish(self):
        """Mark query as finished and calculate duration."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000

    def to_dict(self):
        """Convert to dictionary for logging/storage."""
        return {
            "statement": self.statement[:500],  # Truncate long queries
            "parameters": str(self.parameters)[:200] if self.parameters else None,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "timestamp": datetime.fromtimestamp(self.start_time).isoformat(),
        }


class RequestProfile:
    """Profile data for an entire HTTP request."""

    def __init__(self, method: str, path: str):
        self.method = method
        self.path = path
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: Optional[float] = None
        self.queries: List[QueryProfile] = []
        self.status_code: Optional[int] = None

    def add_query(self, query: QueryProfile):
        """Add a query to this request."""
        self.queries.append(query)

    def finish(self, status_code: int):
        """Mark request as finished."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status_code = status_code

    @property
    def query_count(self) -> int:
        """Total number of queries executed."""
        return len(self.queries)

    @property
    def total_query_time_ms(self) -> float:
        """Total time spent in database queries."""
        return sum(q.duration_ms for q in self.queries if q.duration_ms)

    @property
    def has_n_plus_one(self) -> bool:
        """
        Detect potential N + 1 query problems.
        Simple heuristic: >10 similar queries in one request.
        """
        if self.query_count < 10:
            return False

        # Group queries by statement (ignoring parameters)
        statement_counts = defaultdict(int)
        for query in self.queries:
            # Normalize statement (remove parameter placeholders)
            normalized = (
                query.statement.split("WHERE")[0] if "WHERE" in query.statement else query.statement
            )
            statement_counts[normalized] += 1

        # Check if any statement was executed >10 times
        return any(count > 10 for count in statement_counts.values())

    @property
    def slow_queries(self) -> List[QueryProfile]:
        """Get queries slower than 100ms."""
        return [q for q in self.queries if q.duration_ms and q.duration_ms > 100]

    def to_dict(self):
        """Convert to dictionary for logging."""
        return {
            "method": self.method,
            "path": self.path,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "query_count": self.query_count,
            "total_query_time_ms": round(self.total_query_time_ms, 2),
            "has_n_plus_one": self.has_n_plus_one,
            "slow_query_count": len(self.slow_queries),
            "status_code": self.status_code,
            "timestamp": datetime.fromtimestamp(self.start_time).isoformat(),
        }


class QueryProfiler:
    """
    Database query profiler for Flask applications.
    Tracks and analyzes all database queries per request.
    """

    def __init__(self, app=None):
        self.enabled = False
        self.slow_query_threshold_ms = 100
        self.log_all_queries = False

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize profiler with Flask app."""
        # Get configuration
        self.enabled = app.config.get("QUERY_PROFILER_ENABLED", app.debug)
        self.slow_query_threshold_ms = app.config.get("SLOW_QUERY_THRESHOLD_MS", 100)
        self.log_all_queries = app.config.get("LOG_ALL_QUERIES", False)

        if not self.enabled:
            app.logger.info("Query profiler disabled")
            return

        # Register SQLAlchemy event listeners
        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Called before each query execution."""
            if not hasattr(_query_stack, "queries"):
                _query_stack.queries = []

            query = QueryProfile(statement, parameters, time.time())
            _query_stack.queries.append(query)

        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Called after each query execution."""
            if hasattr(_query_stack, "queries") and _query_stack.queries:
                query = _query_stack.queries[-1]
                query.finish()

        # Register Flask request hooks
        @app.before_request
        def before_request():
            """Initialize profiling for this request."""
            # Skip profiling for static files — they should not generate DB queries
            if request.path.startswith("/static/") or request.path == "/favicon.ico":
                return
            g.query_profile = RequestProfile(request.method, request.path)
            _query_stack.queries = []

        @app.after_request
        def after_request(response):
            """Finish profiling and log results."""
            if not hasattr(g, "query_profile"):
                return response

            profile = g.query_profile
            profile.finish(response.status_code)

            # Add queries from thread-local storage
            if hasattr(_query_stack, "queries"):
                for query in _query_stack.queries:
                    profile.add_query(query)

            # Log if needed
            self._log_profile(profile, app)

            # Add profiling headers to response
            if app.debug:
                response.headers["X-Query-Count"] = str(profile.query_count)
                response.headers["X-Query-Time-Ms"] = str(round(profile.total_query_time_ms, 2))
                response.headers["X-Request-Time-Ms"] = str(round(profile.duration_ms, 2))
                if profile.has_n_plus_one:
                    response.headers["X-Query-Warning"] = "Possible N + 1 problem detected"

            return response

        app.logger.info(f"✅ Query profiler enabled (threshold: {self.slow_query_threshold_ms}ms)")

        # Store profiler in app extensions
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["query_profiler"] = self

    def _log_profile(self, profile: RequestProfile, app):
        """Log profiling results based on configuration."""
        # Always log slow requests (>1s) or requests with N + 1 problems
        is_slow = profile.duration_ms and profile.duration_ms > 1000

        if is_slow or profile.has_n_plus_one or self.log_all_queries:
            log_data = profile.to_dict()

            if is_slow:
                app.logger.warning(f"🐌 SLOW REQUEST: {log_data}")

            if profile.has_n_plus_one:
                app.logger.warning(f"⚠️  N + 1 QUERY DETECTED: {log_data}")

            # Log slow queries
            for slow_query in profile.slow_queries:
                app.logger.warning(
                    f"   Slow query ({slow_query.duration_ms:.2f}ms): {slow_query.statement[:200]}"
                )

            if self.log_all_queries and not (is_slow or profile.has_n_plus_one):
                app.logger.debug(f"Query profile: {log_data}")


# Decorator for profiling specific functions
def profile_queries(func):
    """
    Decorator to profile database queries in a specific function.

    Usage:
        @profile_queries
        def expensive_operation():
            # ... database queries ...
            pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Store queries before function execution
        _query_stack.queries = []
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Log query statistics
            duration_ms = (time.time() - start_time) * 1000
            query_count = len(_query_stack.queries) if hasattr(_query_stack, "queries") else 0

            current_app.logger.info(
                f"Function {func.__name__} executed {query_count} queries in {duration_ms:.2f}ms"
            )

    return wrapper


# Global profiler instance
query_profiler = QueryProfiler()
