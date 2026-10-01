"""R1-B20 PR 2 (TB-0160): shared-catalogue rows read-only to organisations,
tailored through a per-organisation override row.

Generalises UnifiedCapability's own scope/reference_capability_id pattern
(tested in tests/test_tenant_isolation.py's
test_capability_reference_and_current_tenant_are_visible_but_foreign_tenant_is_hidden
and test_capability_reference_is_read_only_inside_a_tenant_request) onto
every HybridTenantMixin class at once, via the do_orm_execute/before_flush
pair in app/middleware/tenant_isolation.py. EnterpriseArchitectureFramework
stands in for all twelve classes here -- the mechanism is generic on the
mixin, not per-model, so one representative model exercises it for all.
"""
from __future__ import annotations

import uuid

import pytest


def _framework(name, code, **kw):
    from app.models.framework import EnterpriseArchitectureFramework

    return EnterpriseArchitectureFramework(
        name=name, code=code, framework_type="architecture", **kw
    )


def test_reference_and_current_tenant_are_visible_but_foreign_tenant_is_hidden(
    db_session, make_org, tenant_ctx
):
    """Hybrid reads expose reference plus own rows, never another org's rows."""
    org_a, org_b = make_org("hybrid-a"), make_org("hybrid-b")
    suffix = uuid.uuid4().hex[:10]
    reference = _framework(
        "Reference framework", f"REF-{suffix}",
        tenancy_scope="reference", organization_id=None,
    )
    own = _framework(
        "Org A framework", f"A-{suffix}",
        tenancy_scope="tenant", organization_id=org_a.id,
    )
    foreign = _framework(
        "Org B framework", f"B-{suffix}",
        tenancy_scope="tenant", organization_id=org_b.id,
    )
    db_session.add_all((reference, own, foreign))
    db_session.flush()
    wanted = {reference.id, own.id, foreign.id}
    db_session.expunge_all()

    from app.models.framework import EnterpriseArchitectureFramework

    with tenant_ctx(org_a.id):
        visible = {
            row.id
            for row in EnterpriseArchitectureFramework.query.filter(
                EnterpriseArchitectureFramework.id.in_(wanted)
            ).all()
        }

    assert reference.id in visible
    assert own.id in visible
    assert foreign.id not in visible


def test_unclassified_null_organisation_row_is_not_automatically_shared(
    db_session, make_org, tenant_ctx
):
    """organization_id IS NULL alone is not enough -- tenancy_scope must say
    "reference" explicitly, matching UnifiedCapability's own rule."""
    from app.models.framework import EnterpriseArchitectureFramework

    org = make_org("hybrid-unclassified")
    unclassified = _framework(
        "Unclassified framework", f"UNC-{uuid.uuid4().hex[:10]}",
        organization_id=None,
    )
    db_session.add(unclassified)
    db_session.flush()
    unclassified_id = unclassified.id
    db_session.expunge_all()

    with tenant_ctx(org.id):
        visible = EnterpriseArchitectureFramework.query.filter_by(
            id=unclassified_id
        ).first()

    assert visible is None


def test_reference_row_is_read_only_inside_a_tenant_request(db_session, tenant_ctx, make_org):
    """A tenant must not mutate the shared reference catalogue it can read."""
    from app.models.framework import EnterpriseArchitectureFramework

    org = make_org("hybrid-writer")
    reference = _framework(
        "Immutable reference framework", f"IMM-{uuid.uuid4().hex[:10]}",
        tenancy_scope="reference", organization_id=None,
    )
    db_session.add(reference)
    db_session.flush()
    reference_id = reference.id
    db_session.expunge_all()

    with tenant_ctx(org.id):
        loaded = EnterpriseArchitectureFramework.query.filter_by(id=reference_id).first()
        assert loaded is not None
        loaded.name = "Tenant attempted edit"
        with pytest.raises(PermissionError, match="reference rows are read-only"):
            db_session.flush()


def test_platform_write_context_lets_a_platform_write_edit_a_reference_row(
    db_session, tenant_ctx, make_org
):
    """platform_write_context is the escape hatch a platform-admin route
    (e.g. activate_extension in app/main/framework_management_routes.py)
    uses to edit the shared catalogue despite still carrying its own
    organisation's tenant context -- the same write the test above confirms
    an ordinary tenant request cannot make."""
    from app.middleware.tenant_isolation import platform_write_context
    from app.models.framework import EnterpriseArchitectureFramework

    org = make_org("hybrid-platform-writer")
    reference = _framework(
        "Platform-editable reference framework", f"PLAT-{uuid.uuid4().hex[:10]}",
        tenancy_scope="reference", organization_id=None,
    )
    db_session.add(reference)
    db_session.flush()
    reference_id = reference.id
    db_session.expunge_all()

    with tenant_ctx(org.id):
        loaded = EnterpriseArchitectureFramework.query.filter_by(id=reference_id).first()
        assert loaded is not None
        with platform_write_context():
            loaded.name = "Platform edit"
            db_session.flush()

        # Restored once the block exits: an ordinary write right after is
        # still refused, proving this did not leave tenant scoping disabled.
        loaded.name = "Tenant attempted edit after the block"
        with pytest.raises(PermissionError, match="reference rows are read-only"):
            db_session.flush()


def test_bulk_update_inside_a_tenant_request_is_refused(db_session, tenant_ctx, make_org):
    """Model.query.filter(...).update(...) never touches session.new/dirty,
    so before_flush's ownership/scope checks cannot see it; a WHERE-scoped
    bulk update would still let a tenant set organization_id/tenancy_scope
    on their own row to anything, e.g. reparenting it into the shared
    catalogue. Refused outright instead -- the ORM per-instance path (which
    before_flush does protect) is the only way to write these tables inside
    a tenant request."""
    from app.models.framework import EnterpriseArchitectureFramework

    org = make_org("hybrid-bulk-write")
    own_row = _framework(
        f"Own row {uuid.uuid4().hex[:10]}", f"BULK-{uuid.uuid4().hex[:10]}",
        tenancy_scope="tenant", organization_id=org.id,
    )
    db_session.add(own_row)
    db_session.flush()
    own_row_id = own_row.id
    db_session.expunge_all()

    with tenant_ctx(org.id):
        with pytest.raises(PermissionError, match="bulk update/delete"):
            EnterpriseArchitectureFramework.query.filter_by(id=own_row_id).update(
                {"organization_id": None, "tenancy_scope": "reference"}
            )


def test_a_new_tenant_row_is_stamped_with_organisation_and_scope(db_session, tenant_ctx, make_org):
    """A row created with no organization_id/tenancy_scope inside a tenant
    request is stamped with the caller's own organisation and "tenant",
    not left to default to a shared reference row by omission."""
    from app.models.framework import EnterpriseArchitectureFramework

    org = make_org("hybrid-autostamp")
    with tenant_ctx(org.id):
        row = _framework("Autostamped framework", f"AUTO-{uuid.uuid4().hex[:10]}")
        db_session.add(row)
        db_session.flush()
        assert row.organization_id == org.id
        assert row.tenancy_scope == "tenant"


def test_one_organisations_tenant_row_is_read_only_to_another(db_session, tenant_ctx, make_org):
    """Cross-organisation writes are refused the same way reference writes
    are. Confirmed two ways: org B's own read never finds org A's row at
    all (do_orm_execute), and before_flush refuses the write on its own as
    defence in depth -- a row already warm in the identity map from org A's
    own context (no expunge in between, unlike the other tests here) is the
    one real way to reach the write guard despite the read guard, matching
    the g-leak trap tests/conftest.py documents for exactly this shape:
    object state surviving a tenant-context switch within one session."""
    from app.models.framework import EnterpriseArchitectureFramework

    org_a, org_b = make_org("hybrid-cross-a"), make_org("hybrid-cross-b")
    with tenant_ctx(org_a.id):
        row = _framework("Org A's own framework", f"CROSS-{uuid.uuid4().hex[:10]}")
        db_session.add(row)
        db_session.flush()
        row_id = row.id

    with tenant_ctx(org_b.id):
        not_visible = EnterpriseArchitectureFramework.query.filter_by(id=row_id).first()
        assert not_visible is None

        # Still warm from org A's own context above (no expunge): this is
        # the one path that reaches before_flush at all for a foreign row.
        row.name = "Org B attempted edit"
        with pytest.raises(PermissionError, match="owned by another organisation"):
            db_session.flush()


def test_tailoring_row_is_the_effective_value_for_its_own_organisation_only(
    db_session, tenant_ctx, make_org
):
    """A tenant's tailoring row (tailored_from_id -> the reference row)
    becomes the effective value for that organisation only; a second
    organisation still sees the untailored reference value (Playwright's
    "Tailor for my organisation" acceptance criterion, exercised here at the
    data layer)."""
    from app.models.framework import EnterpriseArchitectureFramework

    org_a, org_b = make_org("hybrid-tailor-a"), make_org("hybrid-tailor-b")
    reference = _framework(
        "Shared TOGAF profile", f"TOGAF-{uuid.uuid4().hex[:10]}",
        tenancy_scope="reference", organization_id=None,
        maturity_level="established",
    )
    db_session.add(reference)
    db_session.flush()
    reference_id = reference.id

    with tenant_ctx(org_a.id):
        tailored = EnterpriseArchitectureFramework(
            name=reference.name, code=f"TOGAF-A-{uuid.uuid4().hex[:6]}",
            framework_type="architecture",
            maturity_level="mature", tailored_from_id=reference_id,
        )
        db_session.add(tailored)
        db_session.flush()
        tailored_id = tailored.id

    db_session.expunge_all()

    with tenant_ctx(org_a.id):
        effective_for_a = EnterpriseArchitectureFramework.effective(reference_id, org_a.id)
        assert effective_for_a.id == tailored_id
        assert effective_for_a.maturity_level == "mature"

    db_session.expunge_all()

    with tenant_ctx(org_b.id):
        effective_for_b = EnterpriseArchitectureFramework.effective(reference_id, org_b.id)
        assert effective_for_b.id == reference_id
        assert effective_for_b.maturity_level == "established"
