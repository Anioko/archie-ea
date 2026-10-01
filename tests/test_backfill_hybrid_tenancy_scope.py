"""flask backfill-hybrid-tenancy-scope classifies pre-existing shared-catalogue
rows left with tenancy_scope IS NULL (the shape reconcile-schema produces for
every row that existed before HybridTenantMixin was added), which otherwise
stay invisible to every organisation per
test_unclassified_null_organisation_row_is_not_automatically_shared in
tests/test_hybrid_tenant_mixin.py.
"""
from __future__ import annotations

import uuid


def _framework(name, code, **kw):
    from app.models.framework import EnterpriseArchitectureFramework

    return EnterpriseArchitectureFramework(
        name=name, code=code, framework_type="architecture", **kw
    )


def test_unclassified_rows_are_set_to_reference_or_tenant_by_organization_id(
    db_session, make_org
):
    from app.commands.backfill_hybrid_tenancy_scope import repair_hybrid_tenancy_scope
    from app.models.framework import EnterpriseArchitectureFramework

    org = make_org("hybrid-backfill")
    suffix = uuid.uuid4().hex[:10]
    unclassified_shared = _framework(
        f"Unclassified shared {suffix}", f"UNC-SHARED-{suffix}", organization_id=None
    )
    unclassified_owned = _framework(
        f"Unclassified owned {suffix}", f"UNC-OWNED-{suffix}", organization_id=org.id
    )
    already_classified = _framework(
        f"Already classified {suffix}", f"CLS-{suffix}",
        organization_id=None, tenancy_scope="reference",
    )
    db_session.add_all((unclassified_shared, unclassified_owned, already_classified))
    db_session.flush()
    assert unclassified_shared.tenancy_scope is None
    assert unclassified_owned.tenancy_scope is None

    stats = repair_hybrid_tenancy_scope()

    assert stats["repaired"].get("enterprise_architecture_frameworks", 0) >= 2
    db_session.refresh(unclassified_shared)
    db_session.refresh(unclassified_owned)
    db_session.refresh(already_classified)
    assert unclassified_shared.tenancy_scope == "reference"
    assert unclassified_owned.tenancy_scope == "tenant"
    # Already classified before the run: untouched, not recounted.
    assert already_classified.tenancy_scope == "reference"


def test_backfill_makes_a_previously_invisible_row_visible_again(
    db_session, make_org, tenant_ctx
):
    from app.commands.backfill_hybrid_tenancy_scope import repair_hybrid_tenancy_scope
    from app.models.framework import EnterpriseArchitectureFramework

    org = make_org("hybrid-backfill-visibility")
    unclassified = _framework(
        f"Unclassified {uuid.uuid4().hex[:10]}", f"VIS-{uuid.uuid4().hex[:10]}",
        organization_id=None,
    )
    db_session.add(unclassified)
    db_session.flush()
    unclassified_id = unclassified.id
    db_session.expunge_all()

    with tenant_ctx(org.id):
        assert EnterpriseArchitectureFramework.query.filter_by(id=unclassified_id).first() is None

    repair_hybrid_tenancy_scope()
    db_session.expunge_all()

    with tenant_ctx(org.id):
        visible = EnterpriseArchitectureFramework.query.filter_by(id=unclassified_id).first()
        assert visible is not None


def test_dry_run_reports_without_changing_anything(db_session):
    from app.commands.backfill_hybrid_tenancy_scope import repair_hybrid_tenancy_scope

    unclassified = _framework(
        f"Dry run {uuid.uuid4().hex[:10]}", f"DRY-{uuid.uuid4().hex[:10]}",
        organization_id=None,
    )
    db_session.add(unclassified)
    # Committed (a savepoint release under this fixture, not a real commit --
    # see db_session's own docstring) so the dry run's own rollback below
    # cannot undo this row along with whatever it examined.
    db_session.commit()

    stats = repair_hybrid_tenancy_scope(dry_run=True)

    assert stats["repaired"].get("enterprise_architecture_frameworks", 0) >= 1
    db_session.refresh(unclassified)
    assert unclassified.tenancy_scope is None
