"""Shared tenant fence for linking an existing Goal/Driver/Requirement to an
ApplicationComponent by direct FK.

Extracted so both blueprints that expose this action --
``app.application_mgmt.motivation_layer_routes`` and
``app.modules.applications.routes.element_routes`` -- enforce the identical
check rather than each carrying its own copy.
"""
from app import db
from app.middleware.tenant_context import current_org_id


def linkable_in_caller_org(entity) -> bool:
    """Whether an unlinked motivation-layer entity (Goal/Driver/Requirement -- none carry an
    organisation column of their own) may be linked into the caller's application.

    The standard creation path always pairs one of these with an ArchiMateElement first
    (archimate_element_id set) -- see motivation_layer_service.py's "Basecoat pattern" comment --
    and ArchiMateElement is TenantMixin. An entity with no archimate_element_id has no reliable
    signal of which organisation it belongs to, so it fails closed rather than being guessed at,
    the same convention scripts/commands/backfill_layer_tenancy.py uses for provenance-only rows.
    """
    org_id = current_org_id()
    if org_id is None or not getattr(entity, "archimate_element_id", None):
        return False
    from app.models.archimate_core import ArchiMateElement

    fenced = db.session.execute(
        db.select(ArchiMateElement).where(ArchiMateElement.id == entity.archimate_element_id)
    ).scalar_one_or_none()
    return fenced is not None
