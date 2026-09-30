"""Shared tenant fence for ``ProcessApplicationMapping`` and
``CapabilityProcessMapping`` (``app/models/apqc_process.py``).

Neither model carries an ``organization_id`` of its own -- ownership is only
reachable via ``application_id`` (-> ``ApplicationComponent``, TenantMixin)
or ``capability_id`` (-> ``BusinessCapability``, TenantMixin). Before this
module existed, the identical join-and-filter pattern was written inline at
eleven call sites across three route files (PRs 301, 303, 306), and three
separate reviews caught leaks each time one of the eleven was missed. This
is the one copy: every read, write and delete of either table goes through
one of the functions below, not a fifth inlined copy.

Fail-closed convention, matching the rest of the codebase's tenant fences:
no ambient organisation, no row, or a row owned by a different organisation
all return ``None`` (single-row functions) or an empty/pre-filtered query
(list functions) -- never the unfenced row.
"""
from __future__ import annotations

from typing import Optional

from app import db
from app.models.application_layer import ApplicationComponent
from app.models.apqc_process import CapabilityProcessMapping, ProcessApplicationMapping
from app.models.business_capabilities import BusinessCapability
from app.utils.tenant_sql import current_org_id

__all__ = [
    "application_owned_by_caller",
    "capability_owned_by_caller",
    "fenced_process_application_mapping",
    "fenced_capability_process_mapping",
    "owned_process_application_mappings_query",
    "owned_capability_process_mappings_query",
]


def application_owned_by_caller(application_id) -> Optional[ApplicationComponent]:
    """The ``ApplicationComponent`` with this id, only if it belongs to the
    caller's organisation. ``None`` on no ambient org, no such row, or a
    foreign owner."""
    org_id = current_org_id()
    if org_id is None or not application_id:
        return None
    return db.session.execute(
        db.select(ApplicationComponent).where(
            ApplicationComponent.id == application_id,
            ApplicationComponent.organization_id == org_id,
        )
    ).scalar_one_or_none()


def capability_owned_by_caller(capability_id) -> Optional[BusinessCapability]:
    """The ``BusinessCapability`` with this id, only if it belongs to the
    caller's organisation. ``None`` on no ambient org, no such row, or a
    foreign owner."""
    org_id = current_org_id()
    if org_id is None or not capability_id:
        return None
    return db.session.execute(
        db.select(BusinessCapability).where(
            BusinessCapability.id == capability_id,
            BusinessCapability.organization_id == org_id,
        )
    ).scalar_one_or_none()


def fenced_process_application_mapping(mapping_id) -> Optional[ProcessApplicationMapping]:
    """The ``ProcessApplicationMapping`` with this id, only if its
    ``application_id`` belongs to the caller's organisation. ``None``
    otherwise -- use this in place of ``ProcessApplicationMapping.query.get()``
    for any id taken from a request (URL, body or query string)."""
    mapping = db.session.get(ProcessApplicationMapping, mapping_id)
    if mapping is None:
        return None
    if application_owned_by_caller(mapping.application_id) is None:
        return None
    return mapping


def fenced_capability_process_mapping(mapping_id) -> Optional[CapabilityProcessMapping]:
    """The ``CapabilityProcessMapping`` with this id, only if its
    ``capability_id`` belongs to the caller's organisation. ``None``
    otherwise -- use this in place of ``CapabilityProcessMapping.query.get()``
    for any id taken from a request."""
    mapping = db.session.get(CapabilityProcessMapping, mapping_id)
    if mapping is None:
        return None
    if capability_owned_by_caller(mapping.capability_id) is None:
        return None
    return mapping


def owned_process_application_mappings_query():
    """A ``ProcessApplicationMapping`` query joined to the caller's own
    ``ApplicationComponent`` rows. Add further ``.filter(...)`` calls on
    ``ProcessApplicationMapping`` columns as needed. Returns a query that
    matches nothing when there is no ambient organisation (never an
    unfiltered query) -- check ``current_org_id()`` first if the caller
    needs to distinguish "no org" from "no matching rows"."""
    org_id = current_org_id()
    query = ProcessApplicationMapping.query.join(
        ApplicationComponent,
        ProcessApplicationMapping.application_id == ApplicationComponent.id,
    )
    if org_id is None:
        return query.filter(db.false())
    return query.filter(ApplicationComponent.organization_id == org_id)


def owned_capability_process_mappings_query():
    """A ``CapabilityProcessMapping`` query joined to the caller's own
    ``BusinessCapability`` rows. Add further ``.filter(...)`` calls on
    ``CapabilityProcessMapping`` columns as needed. Returns a query that
    matches nothing when there is no ambient organisation (never an
    unfiltered query)."""
    org_id = current_org_id()
    query = CapabilityProcessMapping.query.join(
        BusinessCapability,
        CapabilityProcessMapping.capability_id == BusinessCapability.id,
    )
    if org_id is None:
        return query.filter(db.false())
    return query.filter(BusinessCapability.organization_id == org_id)
