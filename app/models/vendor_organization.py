"""Compatibility shim for legacy imports.

Some tests and modules import `app.models.vendor_organization` directly while
the canonical implementation lives under `app.models.vendor.vendor_organization`.
This thin shim re-exports the public symbols to preserve backward compatibility
without duplicating model definitions.
"""
from .vendor.vendor_organization import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("_")]
