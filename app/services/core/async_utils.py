"""
Async utilities for Flask application.
Provides shared event loop management to prevent memory leaks.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global event loop instance (thread-local would be better, but Flask context works)
_shared_loop: Optional[asyncio.AbstractEventLoop] = None


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    Get an existing event loop or create a new one safely.

    This prevents memory leaks from creating new event loops per request.
    Reuses existing loop when possible, creates new one only when necessary.

    Returns:
        asyncio.AbstractEventLoop: Active event loop for async operations

    Example:
        loop = get_or_create_event_loop()
        result = loop.run_until_complete(async_function())
    """
    global _shared_loop

    try:
        # Try to get existing loop in current thread
        loop = asyncio.get_event_loop()

        # Check if loop is closed
        if loop.is_closed():
            logger.warning("Event loop was closed, creating new one")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _shared_loop = loop
            return loop

        # Loop exists and is open - reuse it
        _shared_loop = loop
        return loop

    except RuntimeError:
        # No event loop in current thread (common in Flask)
        logger.debug("No event loop in current thread, creating new one")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _shared_loop = loop
        return loop


def run_async_safely(coro):
    """
    Run async coroutine safely using shared event loop.

    Args:
        coro: Coroutine to run

    Returns:
        Result of coroutine execution

    Example:
        result = run_async_safely(analyze_document(file_path))
    """
    loop = get_or_create_event_loop()
    return loop.run_until_complete(coro)
