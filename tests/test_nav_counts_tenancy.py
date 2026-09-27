"""Sidebar counts must be the signed-in tenant's, and must not leak between tenants.

Found by driving a real browser: signed in as a business architect of the SG
Tadley demo tenant (14 applications), the sidebar read "Applications (38)" —
the total across every organisation, 24 of which belong to a different customer.
"All Elements (434)" against that tenant's 71, likewise.

Two independent defects produced it, and each is enough on its own:

1. ``db.session.query(db.func.count(Model.id))`` is a COLUMN query, not an
   entity query, and ``with_loader_criteria`` — the whole basis of tenant
   isolation in this codebase — only applies to entity queries. So the counts
   were never filtered, in any request, for any tenant.
2. ``_nav_counts_cache`` was a single module-level dict with no tenant in its
   key. Even with correct filtering, the first organisation to load a page
   would populate it and every other organisation would be served that
   organisation's numbers for the next five minutes.
"""

import pytest

from app._bootstrap.context_processors import compute_nav_counts


@pytest.fixture
def two_tenants(app, db_session, make_org):
    """Two orgs with deliberately different application counts."""
    from app.models.application_portfolio import ApplicationComponent

    # Built with NO request context: organization_id is explicit, so TenantMixin's
    # before_flush has nothing to fill in, and this avoids mutating g.current_org_id
    # across a single flush — doing that silently lost the first org's row.
    small = make_org("nav-small")
    large = make_org("nav-large")
    db_session.add(ApplicationComponent(name="Solo App", organization_id=small.id))
    for i in range(3):
        db_session.add(
            ApplicationComponent(name=f"Big App {i}", organization_id=large.id)
        )
    db_session.commit()
    return small, large


def test_counts_are_scoped_to_the_signed_in_tenant(app, db_session, two_tenants):
    from app.models.application_portfolio import ApplicationComponent

    small, large = two_tenants

    actual = {
        oid: db_session.query(ApplicationComponent)
        .filter(ApplicationComponent.organization_id == oid)
        .count()
        for oid in (small.id, large.id)
    }
    assert actual == {small.id: 1, large.id: 3}, f"fixture precondition failed: {actual}"

    assert compute_nav_counts(small.id)["applications"] == 1, (
        "sidebar application count is not scoped to the signed-in organisation"
    )
    assert compute_nav_counts(large.id)["applications"] == 3


def test_counts_do_not_leak_through_the_cache(app, db_session, two_tenants):
    """The decisive one: ask as tenant A, then as tenant B, back-to-back."""
    small, large = two_tenants

    first = compute_nav_counts(small.id)["applications"]
    second = compute_nav_counts(large.id)["applications"]
    third = compute_nav_counts(small.id)["applications"]

    assert (first, second, third) == (1, 3, 1), (
        f"cache served one tenant's counts to another: got {first}, {second}, {third}"
    )


def test_no_tenant_context_does_not_poison_a_tenant_entry(app, db_session, two_tenants):
    """An unauthenticated render must not overwrite a tenant's cached counts."""
    small, _large = two_tenants

    compute_nav_counts(small.id)
    compute_nav_counts(None)  # e.g. the login page
    assert compute_nav_counts(small.id)["applications"] == 1
