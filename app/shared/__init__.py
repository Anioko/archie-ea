"""
Shared package — cross-module components used by multiple domain modules.

Re-exports commonly-needed base classes, mixins, and services so that
module code can import from a single namespace::

    from app.shared.models import BaseModel, AuditLog
    from app.shared.schemas import PaginationSchema

This package does NOT contain domain-specific logic — it provides the
shared infrastructure that domain modules build upon.
"""
