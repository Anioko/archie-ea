"""Datetime helper utilities for the application."""
from datetime import datetime, timezone


def utcnow():
    """Return timezone-aware UTC datetime.

    This is a replacement for datetime.utcnow() which returns timezone-naive datetime.
    All datetime objects in the database should be timezone-aware.
    """
    return datetime.now(timezone.utc)
