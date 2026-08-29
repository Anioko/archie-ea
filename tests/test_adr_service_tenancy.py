"""Architecture Decision Records must not cross organisations.

`architecture_decisions` is mapped twice:

    app/models/architecture_decision.py    class ArchitectureDecision(TenantMixin, db.Model)
    app/models/architecture_decisions.py   class ArchitectureDecision(db.Model)

Both are live in the mapper registry -- unlike `archimate_core`, which resolves the
same ambiguity with a conditional re-export, nothing here chooses. `TenantMixin` is
what installs the ORM-event filter and the `organization_id` auto-set, so a query
through the unscoped twin is not filtered and raises nothing when it returns
another organisation's rows.

`app/services/adr_service.py:17` imports the unscoped one, and
`app/modules/architecture/routes/adr_routes.py` serves it over HTTP.

ADRs are governance records: they state what an organisation decided, why, and what
it rejected. Leaking them across tenants is both a confidentiality breach and a
correctness one -- a decision list that silently includes another company's
decisions is worse than an empty one, because it reads as authoritative.

These tests were written to prove the exposure before it was fixed, and they stay
to stop it returning by the same route: one import line decides it.
"""

from __future__ import annotations

import uuid

import pytest


def _make_adr(db_session, organization_id, title):
    """Insert through the tenant-scoped mapping, explicitly scoped.

    Explicit because these tests run outside a request, where the tenant
    middleware's before_flush hook does not run and would leave organization_id
    NULL.
    """
    from app.models.architecture_decision import ArchitectureDecision

    row = ArchitectureDecision(
        title=title,
        organization_id=organization_id,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_adr_service_lists_only_this_organisations_decisions(
    db_session, make_org, tenant_ctx
):
    """The list must not include another organisation's governance record."""
    from app.services.adr_service import ADRService

    org_a = make_org("adr-a")
    org_b = make_org("adr-b")

    mine = f"Ours {uuid.uuid4().hex[:6]}"
    theirs = f"Theirs {uuid.uuid4().hex[:6]}"
    _make_adr(db_session, org_a.id, mine)
    _make_adr(db_session, org_b.id, theirs)
    db_session.commit()

    with tenant_ctx(org_a.id):
        db_session.expunge_all()   # defeat the identity map; force real SQL
        titles = [getattr(row, "title", None) for row in ADRService.list_adrs()]

    assert mine in titles, "the caller's own ADR was missing from the list"
    assert theirs not in titles, (
        "ADRService.list_adrs returned another organisation's architecture "
        "decision. The service imports the unscoped ArchitectureDecision mapping, "
        "which carries no TenantMixin and therefore no query filter."
    )


def test_adr_service_cannot_fetch_another_organisations_decision(
    db_session, make_org, tenant_ctx
):
    """Fetch by id must not reach across the tenant boundary either."""
    from app.services.adr_service import ADRService

    org_a = make_org("adr-fetch-a")
    org_b = make_org("adr-fetch-b")

    foreign = _make_adr(db_session, org_b.id, f"Foreign {uuid.uuid4().hex[:6]}")
    db_session.commit()
    foreign_id = foreign.id

    with tenant_ctx(org_a.id):
        db_session.expunge_all()
        fetched = ADRService.get_adr(foreign_id)

    assert fetched is None, (
        "ADRService.get_adr returned an architecture decision belonging to another "
        "organisation"
    )


def test_adr_service_uses_the_tenant_scoped_mapping():
    """Pin the import itself: this is a one-line regression away at all times."""
    from app.models.mixins import TenantMixin
    from app.services import adr_service

    assert issubclass(adr_service.ArchitectureDecision, TenantMixin), (
        "adr_service imports the unscoped ArchitectureDecision mapping "
        "(app/models/architecture_decisions.py). Import the tenant-scoped one from "
        "app/models/architecture_decision.py instead."
    )
