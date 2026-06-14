"""
Shared services — cross-module service layer components.

Re-exports commonly-needed service utilities and base classes
so modules can import from a single namespace::

    from app.shared.services import audit_action
"""

from app.shared.services.audit_service import audit_action

__all__ = ["audit_action"]
