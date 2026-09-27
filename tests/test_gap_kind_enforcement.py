"""Task 03: validate_gap_kind() enforcement via the before_insert/before_update
listener registered on Gap in app/models/implementation_migration.py.

Against the shared fixtures in tests/conftest.py per root CLAUDE.md.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_architecture(db_session, org_id, name="Gap Kind Test Architecture"):
    from app.models.archimate_core import ArchitectureModel

    arch = ArchitectureModel(name=name, organization_id=org_id)
    db_session.add(arch)
    db_session.flush()
    return arch


def _make_plateau(db_session, org_id, architecture_id, name, sequence_order):
    from app.models.implementation_migration import Plateau

    plateau = Plateau(
        name=name,
        organization_id=org_id,
        architecture_id=architecture_id,
        sequence_order=sequence_order,
    )
    db_session.add(plateau)
    db_session.flush()
    return plateau


def test_plateau_transition_gap_missing_both_plateaus_raises_on_flush(
    db_session, make_org, tenant_ctx
):
    from app.models.implementation_migration import Gap, GAP_KIND_PLATEAU_TRANSITION

    org = make_org("gapkind-a")
    with tenant_ctx(org.id):
        gap = Gap(
            name="Untethered transition gap",
            gap_kind=GAP_KIND_PLATEAU_TRANSITION,
            organization_id=org.id,
        )
        db_session.add(gap)
        with pytest.raises(ValueError):
            db_session.flush()


def test_plateau_transition_gap_missing_target_plateau_raises_on_flush(
    db_session, make_org, tenant_ctx
):
    from app.models.implementation_migration import Gap, GAP_KIND_PLATEAU_TRANSITION

    org = make_org("gapkind-b")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        as_is = _make_plateau(db_session, org.id, architecture.id, "As-is", 1)

        gap = Gap(
            name="Half-tethered transition gap",
            gap_kind=GAP_KIND_PLATEAU_TRANSITION,
            organization_id=org.id,
            originating_plateau_id=as_is.id,
        )
        db_session.add(gap)
        with pytest.raises(ValueError):
            db_session.flush()


def test_capability_shortfall_gap_inserts_unaffected(db_session, make_org, tenant_ctx):
    """Zero behaviour change for existing data: nothing in the tree writes
    gap_kind=plateau_transition today, so every existing/default-kind row
    must insert exactly as before the listener was added."""
    from app.models.implementation_migration import Gap, GAP_KIND_CAPABILITY_SHORTFALL

    org = make_org("gapkind-c")
    with tenant_ctx(org.id):
        gap = Gap(
            name="Weak capability",
            gap_kind=GAP_KIND_CAPABILITY_SHORTFALL,
            organization_id=org.id,
        )
        db_session.add(gap)
        db_session.flush()

        assert gap.id is not None
        assert gap.gap_kind == GAP_KIND_CAPABILITY_SHORTFALL


def test_valid_plateau_transition_gap_inserts(db_session, make_org, tenant_ctx):
    from app.models.implementation_migration import Gap, GAP_KIND_PLATEAU_TRANSITION

    org = make_org("gapkind-d")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        as_is = _make_plateau(db_session, org.id, architecture.id, "As-is", 1)
        to_be = _make_plateau(db_session, org.id, architecture.id, "To-be", 2)

        gap = Gap(
            name="Protocol change gap",
            gap_kind=GAP_KIND_PLATEAU_TRANSITION,
            gap_type="protocol_change",
            organization_id=org.id,
            originating_plateau_id=as_is.id,
            target_plateau_id=to_be.id,
        )
        db_session.add(gap)
        db_session.flush()

        assert gap.id is not None
        assert gap.gap_kind == GAP_KIND_PLATEAU_TRANSITION


def test_update_to_plateau_transition_without_plateaus_raises_on_flush(
    db_session, make_org, tenant_ctx
):
    """The listener is also registered on before_update, not just insert."""
    from app.models.implementation_migration import Gap, GAP_KIND_CAPABILITY_SHORTFALL, GAP_KIND_PLATEAU_TRANSITION

    org = make_org("gapkind-e")
    with tenant_ctx(org.id):
        gap = Gap(
            name="Starts as a shortfall",
            gap_kind=GAP_KIND_CAPABILITY_SHORTFALL,
            organization_id=org.id,
        )
        db_session.add(gap)
        db_session.flush()

        gap.gap_kind = GAP_KIND_PLATEAU_TRANSITION
        with pytest.raises(ValueError):
            db_session.flush()
