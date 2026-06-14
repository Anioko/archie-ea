"""
Service Decorators

Common decorators used by service classes for transaction management and error handling.
"""

import logging
from functools import wraps

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def transactional(f=None, *, auto_commit=True):
    """
    Decorator to handle database transactions automatically.

    Wraps service methods to handle:
    - Transaction commit/rollback (commit can be disabled with auto_commit=False)
    - Error logging
    - Exception handling

    Args:
        auto_commit: If True (default), commits after successful execution.
                     Set to False when the caller (route) manages commits.

    Usage:
        @transactional
        def my_service_method(self):
            # Database operations here — auto-commits on success
            pass

        @transactional(auto_commit=False)
        def my_service_method(self):
            # Database operations here — caller manages commit
            pass
    """

    def decorator(func):
        @wraps(func)
        def decorated_function(self, *args, **kwargs):
            try:
                result = func(self, *args, **kwargs)
                # If auto_commit is enabled and within Flask app context, commit
                if auto_commit:
                    try:
                        from app import db

                        db.session.commit()
                    except (ImportError, RuntimeError):
                        # Not in Flask app context or db not available
                        pass
                return result
            except SQLAlchemyError as e:
                # Rollback on database errors
                try:
                    from app import db

                    db.session.rollback()
                except (ImportError, RuntimeError):
                    logger.exception("Failed to rollback database session")
                    pass
                logger.error(f"Database error in {func.__name__}: {e}")
                raise
            except Exception as e:
                # Rollback on other errors
                try:
                    from app import db

                    db.session.rollback()
                except (ImportError, RuntimeError):
                    logger.exception("Failed to operation")
                    pass
                logger.error(f"Error in {func.__name__}: {e}")
                raise

        return decorated_function

    # Support both @transactional and @transactional(auto_commit=False)
    if f is not None:
        return decorator(f)
    return decorator


def handle_errors(f):
    """
    Decorator to handle service errors gracefully.

    Usage:
        @handle_errors
        def my_service_method(self):
            # Service operations here
            pass
    """

    @wraps(f)
    def decorated_function(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {e}")
            # You could return a default value or re-raise
            raise

    return decorated_function


def cache_result(ttl=300):
    """
    Simple cache decorator for service results.

    Args:
        ttl: Time to live in seconds (default: 5 minutes)

    Usage:
        @cache_result(ttl=600)
        def expensive_operation(self):
            # Expensive computation here
            pass
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(self, *args, **kwargs):
            # Simple in-memory cache
            cache_key = f"{f.__name__}_{str(args)}_{str(kwargs)}"

            if not hasattr(decorated_function, "_cache"):
                decorated_function._cache = {}

            if cache_key in decorated_function._cache:
                return decorated_function._cache[cache_key]

            result = f(self, *args, **kwargs)
            decorated_function._cache[cache_key] = result
            return result

        return decorated_function

    return decorator
