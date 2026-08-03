"""Tenant isolation invariants.

Archie is multi-tenant, and isolation is not enforced by query code — it is
enforced by two SQLAlchemy event listeners in ``app/middleware/tenant_isolation.py``:

* ``do_orm_execute``  adds ``WHERE organization_id = g.current_org_id`` to ORM SELECTs
* ``before_flush``    sets ``organization_id`` on newly inserted ``TenantMixin`` rows

Nothing in the type system, and nothing a reviewer can see at a call site, tells
you whether a given query is scoped. That makes these tests the *only* mechanism
that can establish isolation holds. There are 55 ``TenantMixin`` models.

Two gaps are known and encoded below as strict xfails
-----------------------------------------------------
``do_orm_execute`` returns early for anything that is not a SELECT::

    if not orm_execute_state.is_select:
        return

and ``before_flush`` only walks ``session.new`` (inserts). So **bulk UPDATE and
bulk DELETE are not tenant-filtered at all**, even inside a request context. The
repository contains 35 bulk ``.update()`` / ``.delete()`` call sites.

Those two tests are marked ``xfail(strict=True)``: they document the gap without
breaking the build on pre-existing behaviour, and if the gap is ever closed the
strict xfail *fails*, forcing the marker to be removed. See
docs/adr/0003-tenant-isolation-gaps.md.

``test_get_by_id_is_tenant_scoped`` is NOT xfailed
--------------------------------------------------
Whether ``Query.get()`` honours ``with_loader_criteria`` decides whether
``app/api/v1/applications.py:482`` is a cross-tenant delete vector: that endpoint's
only authorisation check is a ``.get()`` returning None for a foreign id.

**Executed 2026-07-30: it PASSES** — ``.get()`` is scoped, so that endpoint is safe.
The test stays un-xfailed as a regression guard, because the endpoint's safety depends
on this behaviour continuing to hold. If it ever fails, that is a confirmed
cross-tenant delete, not a flaky test.

Suite status when last run: 6 passed, 2 xfailed (the two documented gaps).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_app_component(db_session, org_id, name):
    """Insert an ApplicationComponent directly attributed to *org_id*.

    ApplicationComponent is a TenantMixin model and is the exact model used by the
    bulk-delete endpoint under review, so the tests exercise the real target.
    ``name`` is its only non-nullable business column.
    """
    from app.models.application_portfolio import ApplicationComponent

    row = ApplicationComponent(name=name, organization_id=org_id)
    db_session.add(row)
    db_session.flush()
    return row


# --------------------------------------------------------------- SELECT scoping


def test_select_is_scoped_to_current_org(db_session, make_org, tenant_ctx):
    """The core invariant: org A must not see org B's rows."""
    from app.models.application_portfolio import ApplicationComponent

    org_a, org_b = make_org("a"), make_org("b")
    _make_app_component(db_session, org_a.id, "App owned by A")
    b_row = _make_app_component(db_session, org_b.id, "App owned by B")

    with tenant_ctx(org_a.id):
        visible = ApplicationComponent.query.all()
        visible_ids = {row.id for row in visible}

    assert b_row.id not in visible_ids, (
        "TENANT LEAK: a query in org A's context returned org B's row. "
        "The do_orm_execute filter in app/middleware/tenant_isolation.py is not applying."
    )
    assert all(row.organization_id == org_a.id for row in visible), (
        "TENANT LEAK: query returned rows belonging to another organization."
    )


def test_filtered_select_cannot_reach_other_org(db_session, make_org, tenant_ctx):
    """Explicitly filtering by a foreign id must still return nothing."""
    from app.models.application_portfolio import ApplicationComponent

    org_a, org_b = make_org("a"), make_org("b")
    b_row = _make_app_component(db_session, org_b.id, "App owned by B")

    with tenant_ctx(org_a.id):
        found = ApplicationComponent.query.filter_by(id=b_row.id).first()

    assert found is None, (
        f"TENANT LEAK: org A retrieved org B's row (id={b_row.id}) by filtering on its id."
    )


def test_get_by_id_is_tenant_scoped(db_session, make_org, tenant_ctx):
    """``Query.get()`` must not return another tenant's row.

    This is the authorisation check that ``DELETE /api/v1/applications/<id>``
    relies on. A failure here means that endpoint deletes across tenants.
    """
    from app.models.application_portfolio import ApplicationComponent

    org_a, org_b = make_org("a"), make_org("b")
    b_row = _make_app_component(db_session, org_b.id, "App owned by B")
    b_row_id = b_row.id

    # Expire everything so .get() must hit the database rather than the identity map,
    # which would otherwise mask the absence of a filter.
    db_session.expunge_all()

    with tenant_ctx(org_a.id):
        fetched = ApplicationComponent.query.get(b_row_id)

    assert fetched is None, (
        "SECURITY: Query.get() returned another tenant's row. "
        "app/api/v1/applications.py:482 authorises its bulk delete solely with this "
        "call, so org A can delete org B's application. Fix by scoping the lookup "
        "explicitly (filter_by(organization_id=...)) rather than relying on .get()."
    )


def test_get_by_id_is_NOT_scoped_on_an_identity_map_hit(db_session, make_org, tenant_ctx):
    """The limit of the guarantee above, pinned so it cannot be over-read.

    The preceding test calls ``expunge_all()`` so ``.get()`` must hit the database.
    That is the only case it covers, and CLAUDE.md previously generalised it to
    "``Query.get()`` *is* scoped (verified)". It is not.

    On an identity-map HIT, ``.get()`` returns the cached object without emitting
    SQL, so ``do_orm_execute`` never fires and no tenant predicate is applied. This
    test asserts that leaky behaviour deliberately: it documents a real property of
    SQLAlchemy rather than a defect we intend to fix, and it will fail loudly if a
    future change makes the identity map tenant-aware — at which point the guidance
    below can be relaxed.

    Consequence, and the reason this is written down: a single request is a single
    tenant on a single session, so request-handling code is unaffected. The exposure
    is code that loops over tenants *within one session* — CLI commands, the
    scheduler, importers, and tests. There, call ``db.session.remove()`` between
    tenants and put ``organization_id`` in the predicate.
    """
    from app.models.application_portfolio import ApplicationComponent

    org_a, org_b = make_org("a"), make_org("b")
    b_row = _make_app_component(db_session, org_b.id, "App owned by B")
    b_row_id = b_row.id

    # Deliberately NO expunge: load B's row as B so it sits in the identity map.
    with tenant_ctx(org_b.id):
        assert ApplicationComponent.query.get(b_row_id) is not None

    with tenant_ctx(org_a.id):
        leaked = ApplicationComponent.query.get(b_row_id)
    assert leaked is not None, (
        "Query.get() no longer returns a cached cross-tenant row. That is an "
        "improvement, not a failure — the identity map has become tenant-aware. "
        "Relax the CLI/scheduler guidance in CLAUDE.md and delete this test."
    )

    # And the control: once the cache is dropped, the filter does apply.
    db_session.expunge_all()
    with tenant_ctx(org_a.id):
        assert ApplicationComponent.query.get(b_row_id) is None, (
            "SECURITY: .get() reached another tenant's row even on a cold session."
        )


# --------------------------------------------------------------- INSERT scoping


def test_insert_inherits_current_org(db_session, make_org, tenant_ctx):
    """before_flush must stamp organization_id on new rows."""
    from app.models.application_portfolio import ApplicationComponent

    org_a = make_org("a")

    with tenant_ctx(org_a.id):
        row = ApplicationComponent(name="Created inside org A context")
        db_session.add(row)
        db_session.flush()
        assigned = row.organization_id

    assert assigned == org_a.id, (
        f"expected organization_id to be auto-set to {org_a.id}, got {assigned!r}. "
        "The before_flush listener in tenant_isolation.py is not applying."
    )


def test_explicit_org_on_insert_is_not_overwritten(db_session, make_org, tenant_ctx):
    """An explicitly-set organization_id must win over the ambient context."""
    from app.models.application_portfolio import ApplicationComponent

    org_a, org_b = make_org("a"), make_org("b")

    with tenant_ctx(org_a.id):
        row = ApplicationComponent(name="Explicitly attributed to B", organization_id=org_b.id)
        db_session.add(row)
        db_session.flush()
        assigned = row.organization_id

    assert assigned == org_b.id, "an explicit organization_id must not be overwritten"


# --------------------------------------------------------------- known gaps


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN GAP: do_orm_execute returns early for non-SELECT, so bulk UPDATE is "
        "not tenant-filtered. See docs/adr/0003-tenant-isolation-gaps.md. "
        "If this now passes, the gap was fixed — remove this marker."
    ),
)
def test_bulk_update_cannot_cross_tenants(db_session, make_org, tenant_ctx):
    """A bulk UPDATE in org A's context must not modify org B's rows."""
    from app.models.application_portfolio import ApplicationComponent

    org_a, org_b = make_org("a"), make_org("b")
    b_row = _make_app_component(db_session, org_b.id, "Original name")
    b_row_id = b_row.id

    with tenant_ctx(org_a.id):
        ApplicationComponent.query.filter_by(id=b_row_id).update(
            {"name": "Overwritten from org A"}, synchronize_session=False
        )
        db_session.flush()

    db_session.expunge_all()
    after = db_session.get(ApplicationComponent, b_row_id)
    assert after is not None and after.name == "Original name", (
        "TENANT LEAK: a bulk UPDATE executed in org A's context modified org B's row."
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN GAP: bulk DELETE is not tenant-filtered (non-SELECT path). This is the "
        "mechanism behind the app/api/v1/applications.py:482 delete. "
        "See docs/adr/0003-tenant-isolation-gaps.md. Remove this marker once fixed."
    ),
)
def test_bulk_delete_cannot_cross_tenants(db_session, make_org, tenant_ctx):
    """A bulk DELETE in org A's context must not remove org B's rows."""
    from app.models.application_portfolio import ApplicationComponent

    org_a, org_b = make_org("a"), make_org("b")
    b_row = _make_app_component(db_session, org_b.id, "App owned by B")
    b_row_id = b_row.id

    with tenant_ctx(org_a.id):
        ApplicationComponent.query.filter_by(id=b_row_id).delete(synchronize_session=False)
        db_session.flush()

    db_session.expunge_all()
    assert db_session.get(ApplicationComponent, b_row_id) is not None, (
        "TENANT LEAK: a bulk DELETE executed in org A's context removed org B's row."
    )


# --------------------------------------------------------------- documented no-op


def test_no_tenant_context_is_unfiltered_by_design(db_session, make_org):
    """Outside a request context there is no filtering — assert it, don't assume it.

    ``tenant_isolation.py`` documents this as intentional ("NO-OPs when
    g.current_org_id is None (CLI, migrations, background tasks)"). It is pinned
    here because the ~80 CLI commands and the APScheduler jobs run in exactly this
    mode: any of them that reads tenant data sees *every* organization's rows. If
    that ever changes, this test tells you the CLI's data visibility changed.
    """
    from app.models.application_portfolio import ApplicationComponent

    org_a, org_b = make_org("a"), make_org("b")
    a_row = _make_app_component(db_session, org_a.id, "App owned by A")
    b_row = _make_app_component(db_session, org_b.id, "App owned by B")

    ids = {row.id for row in ApplicationComponent.query.all()}
    assert {a_row.id, b_row.id} <= ids, (
        "expected unfiltered access with no tenant context — the documented CLI behaviour"
    )
