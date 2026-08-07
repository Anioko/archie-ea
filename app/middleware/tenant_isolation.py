"""
Tenant isolation middleware — automatic query filtering + write protection.

Layer 1: SQLAlchemy do_orm_execute event adds WHERE organization_id = X
          to every ORM SELECT on TenantMixin models.

Layer 3: before_flush event auto-sets organization_id on new TenantMixin
          records when the caller didn't set it explicitly.

Both layers are NO-OPs when g.current_org_id is None (CLI, migrations,
background tasks, unauthenticated requests).
"""

import logging

from flask import g
from sqlalchemy.orm import with_loader_criteria

from app.extensions import db
from app.models.mixins.core import TenantMixin

logger = logging.getLogger(__name__)


def install_tenant_filter(app):
    """Wire SQLAlchemy event listeners for automatic tenant scoping."""

    @db.event.listens_for(db.session, "do_orm_execute")
    def _add_tenant_filter(orm_execute_state):
        # Skip if no tenant context (CLI commands, migrations, system tasks)
        if not hasattr(g, "current_org_id") or g.current_org_id is None:
            return

        # SELECT plus ORM-enabled bulk UPDATE/DELETE. Inserts are handled by
        # before_flush below. This closes ADR-0003 gap 1: the early return for
        # non-SELECT statements meant Model.query.filter(...).update()/.delete()
        # ran with NO tenant predicate even inside an authenticated request, so
        # safety at all 35 bulk-write call sites rested on a scoped read having
        # happened first — an invariant held by convention, not mechanism.
        # with_loader_criteria is honoured by ORM-enabled UPDATE and DELETE
        # (SQLAlchemy 1.4+), so the same option covers all three.
        if not (
            orm_execute_state.is_select
            or orm_execute_state.is_update
            or orm_execute_state.is_delete
        ):
            return

        # Add WHERE organization_id = X to all TenantMixin models
        orm_execute_state.statement = orm_execute_state.statement.options(
            with_loader_criteria(
                TenantMixin,
                lambda cls: cls.organization_id == g.current_org_id,
                include_aliases=True,
            )
        )

    @db.event.listens_for(db.session, "before_flush")
    def _set_tenant_on_new(session, flush_context, instances):
        if not hasattr(g, "current_org_id") or g.current_org_id is None:
            return
        for obj in session.new:
            if isinstance(obj, TenantMixin) and getattr(obj, "organization_id", None) is None:
                obj.organization_id = g.current_org_id

    app.logger.info("Tenant isolation filters installed (do_orm_execute + before_flush)")
