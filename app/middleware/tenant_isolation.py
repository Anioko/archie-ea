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
from contextlib import contextmanager

from flask import g
from sqlalchemy import text
from sqlalchemy.orm import with_loader_criteria

from app.extensions import db
from app.models.mixins.core import HybridTenantMixin, TenantMixin

logger = logging.getLogger(__name__)


@contextmanager
def platform_write_context():
    """Suspend tenant scoping for the duration of the block.

    A platform admin is still an ordinary tenant as far as g.current_org_id
    is concerned (platform_admin_required only checks a flag on the current
    user, it does not clear tenant context), so a write to a reference-scoped
    HybridTenantMixin row from inside a platform-admin route hits the same
    before_flush guard an ordinary tenant's write would, and is refused.

    Both guards already treat "no tenant context" as the trusted/platform
    path (CLI, migrations, background tasks -- see this module's own
    docstring), so this reuses that existing path rather than adding a
    second one: call-sites that are already gated by platform_admin_required
    wrap their write in this block to use it deliberately.
    """
    had_org_id = hasattr(g, "current_org_id")
    previous = g.current_org_id if had_org_id else None
    g.current_org_id = None
    try:
        yield
    finally:
        if had_org_id:
            g.current_org_id = previous
        else:
            del g.current_org_id


def set_database_tenant_context(connection, organization_id):
    """Set the trigger-visible tenant for this transaction only.

    ``set_config(..., true)`` is PostgreSQL's transaction-local equivalent of
    ``SET LOCAL``.  Commit/rollback clears it before a pooled connection can be
    reused by another request.
    """

    if organization_id is None:
        return
    connection.execute(
        text("SELECT set_config('archie.organization_id', :organization_id, true)"),
        {"organization_id": str(organization_id)},
    )


def install_tenant_filter(app):
    """Wire SQLAlchemy event listeners for automatic tenant scoping."""

    @db.event.listens_for(db.session, "after_begin")
    def _set_database_tenant_after_begin(session, transaction, connection):
        if hasattr(g, "current_org_id") and g.current_org_id is not None:
            set_database_tenant_context(connection, g.current_org_id)

    @db.event.listens_for(db.session, "do_orm_execute")
    def _add_soft_delete_filter(orm_execute_state):
        # KNOWN REGRESSION closure (see 9cda379): bulk-delete soft-deletes
        # ApplicationComponent via a nullable deleted_at column, but nothing
        # filtered it back out of read paths, so a "deleted" application kept
        # appearing in every list/detail/dashboard/count query. Rather than
        # patch the ~150 call sites individually (a fourth independent count
        # path per file, exactly what the register is asking us to stop
        # doing), filter it once here, the same mechanism the tenant
        # predicate already uses. Applies unconditionally — unlike the tenant
        # predicate below, a soft-deleted row should stay hidden from ORM
        # reads even outside a request context (CLI, scheduler). Recovery
        # (`UPDATE ... SET deleted_at = NULL`) is raw SQL and bypasses the
        # ORM entirely, so it is unaffected.
        if not orm_execute_state.is_select:
            return
        from app.models.application_portfolio import ApplicationComponent
        from app.models.archimate_core import ArchiMateElement

        orm_execute_state.statement = orm_execute_state.statement.options(
            with_loader_criteria(
                ApplicationComponent,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            ),
            # fix/qa-register-100: bulk-delete soft-deletes the application's
            # ArchiMate mirror element too (see deleted_at on ArchiMateElement
            # in app/models/models.py) — filter it the same unconditional way
            # so composer palette, relationship matrix, OEF export and AI
            # context all stop seeing it without per-call-site changes.
            with_loader_criteria(
                ArchiMateElement,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            ),
        )

    @db.event.listens_for(db.session, "do_orm_execute")
    def _add_tenant_filter(orm_execute_state):
        # Skip if no tenant context (CLI commands, migrations, system tasks)
        if not hasattr(g, "current_org_id") or g.current_org_id is None:
            return

        # The request middleware sets this eagerly.  Reasserting it here also
        # covers tests/workers that establish ``g.current_org_id`` directly
        # and sessions that move to a fresh transaction after a mid-request
        # commit.
        set_database_tenant_context(
            orm_execute_state.session.connection(), g.current_org_id
        )

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
        set_database_tenant_context(session.connection(), g.current_org_id)
        for obj in session.new:
            if isinstance(obj, TenantMixin) and getattr(obj, "organization_id", None) is None:
                obj.organization_id = g.current_org_id

    # R1-B20 PR 2 (TB-0160): shared-catalogue reads and writes. Generalises
    # UnifiedCapability's own do_orm_execute/before_flush pair (bottom of
    # app/models/unified_capability.py) across every HybridTenantMixin class
    # at once via with_loader_criteria's base-class form -- the same
    # mechanism _add_tenant_filter above already uses for TenantMixin.
    @db.event.listens_for(db.session, "do_orm_execute")
    def _add_hybrid_tenant_filter(orm_execute_state):
        if not (
            orm_execute_state.is_select
            or orm_execute_state.is_update
            or orm_execute_state.is_delete
        ):
            return
        organization_id = getattr(g, "current_org_id", None)
        if organization_id is None:
            # No tenant context (CLI, migrations, system tasks): every row
            # is visible, matching TenantMixin's own no-op outside a request
            # -- a platform-only surface, not an ordinary organisation read.
            return
        if orm_execute_state.is_select:
            # Own rows (reference or tenant, whichever this organisation's
            # own id happens to be on) plus every explicitly-classified
            # reference row. An unclassified NULL-organisation row
            # (tenancy_scope not yet "reference") is excluded either way --
            # the same "not automatically shared" rule
            # UnifiedCapability.visibility_predicate documents.
            predicate = lambda cls: db.or_(  # noqa: E731
                cls.organization_id == organization_id,
                db.and_(
                    cls.organization_id.is_(None),
                    cls.tenancy_scope == "reference",
                ),
            )
            orm_execute_state.statement = orm_execute_state.statement.options(
                with_loader_criteria(HybridTenantMixin, predicate, include_aliases=True)
            )
            return
        # A bulk UPDATE/DELETE (Model.query.filter(...).update(...), or
        # update(Table)/delete(Table) passed to session.execute()) never
        # touches session.new/dirty/deleted, so before_flush's ownership and
        # scope checks below cannot see it -- scoping the WHERE clause the
        # way the SELECT branch above does would still let a tenant set
        # organization_id/tenancy_scope on their own row to whatever they
        # want (e.g. reparent it out of their tenant into the shared
        # catalogue), since a WHERE-only scope restricts which rows match,
        # not what values get written. No call site does this today, so
        # refusing it outright costs nothing and closes that gap; a caller
        # that needs it goes through the ORM per-instance path instead,
        # where before_flush actually enforces the rules.
        try:
            entity_cls = orm_execute_state.bind_mapper.class_
        except Exception:
            entity_cls = None
        if entity_cls is not None and issubclass(entity_cls, HybridTenantMixin):
            raise PermissionError(
                "bulk update/delete on a shared-catalogue table is refused inside "
                "a tenant request; use the ORM per-instance path instead"
            )

    @db.event.listens_for(db.session, "before_flush")
    def _protect_hybrid_tenant_writes(session, flush_context, instances):
        organization_id = getattr(g, "current_org_id", None)
        if organization_id is None:
            return

        for row in (item for item in session.new if isinstance(item, HybridTenantMixin)):
            if row.tenancy_scope == "reference":
                raise PermissionError(
                    "reference rows are read-only inside a tenant request"
                )
            if row.organization_id is None:
                row.organization_id = organization_id
            if row.organization_id != organization_id:
                raise PermissionError(
                    "rows owned by another organisation are read-only"
                )
            if row.tenancy_scope is None:
                row.tenancy_scope = "tenant"

        for row in (
            item
            for item in session.dirty.union(session.deleted)
            if isinstance(item, HybridTenantMixin)
        ):
            from sqlalchemy import inspect as sa_inspect

            history = sa_inspect(row).attrs.organization_id.history
            original_organization_id = (
                history.deleted[0] if history.deleted else row.organization_id
            )
            if original_organization_id is None:
                raise PermissionError(
                    "reference rows are read-only inside a tenant request"
                )
            if (
                original_organization_id != organization_id
                or row.organization_id != organization_id
            ):
                raise PermissionError(
                    "rows owned by another organisation are read-only"
                )

    app.logger.info(
        "Tenant isolation filters installed "
        "(do_orm_execute + before_flush, TenantMixin + HybridTenantMixin)"
    )
