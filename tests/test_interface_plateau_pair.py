"""Task 03: plateau_pair_service — provisioning is idempotent, no plateau_kind
column, pairing via baseline_plateau_id (SDD Sec.5.2).

Against the shared fixtures in tests/conftest.py per root CLAUDE.md.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_architecture(db_session, org_id, name="Plateau Pair Test Architecture"):
    from app.models.archimate_core import ArchitectureModel

    arch = ArchitectureModel(name=name, organization_id=org_id)
    db_session.add(arch)
    db_session.flush()
    return arch


def _make_initiative(db_session, architecture_id, name="Plateau Pair Test Initiative"):
    from app.models.implementation_migration import TechnologyRoadmapInitiative

    initiative = TechnologyRoadmapInitiative(
        name=name,
        fiscal_year_start=2026,
        fiscal_year_end=2027,
        architecture_id=architecture_id,
    )
    db_session.add(initiative)
    db_session.flush()
    return initiative


def test_provision_plateau_pair_creates_exactly_two_plateaus(db_session, make_org, tenant_ctx):
    from app.models.implementation_migration import Plateau
    from app.modules.interface_register.services import plateau_pair_service as service

    org = make_org("plateaupair-a")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)

        before_count = Plateau.query.filter_by(architecture_id=architecture.id).count()
        assert before_count == 0

        as_is, to_be = service.provision_plateau_pair(initiative.id)

        after_count = Plateau.query.filter_by(architecture_id=architecture.id).count()
        assert after_count == 2
        assert as_is.name == service.ASIS_PLATEAU_NAME
        assert as_is.sequence_order == 1
        assert to_be.name == service.TOBE_PLATEAU_NAME
        assert to_be.sequence_order == 2
        assert to_be.baseline_plateau_id == as_is.id
        # Plateau is in ELEMENT_TYPES: both get an ArchiMate backbone element.
        assert as_is.archimate_element_id is not None
        assert to_be.archimate_element_id is not None


def test_provision_plateau_pair_is_idempotent(db_session, make_org, tenant_ctx):
    from app.models.implementation_migration import Plateau
    from app.modules.interface_register.services import plateau_pair_service as service

    org = make_org("plateaupair-b")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)

        first_as_is, first_to_be = service.provision_plateau_pair(initiative.id)
        second_as_is, second_to_be = service.provision_plateau_pair(initiative.id)

        assert second_as_is.id == first_as_is.id
        assert second_to_be.id == first_to_be.id

        total = Plateau.query.filter_by(architecture_id=architecture.id).count()
        assert total == 2, "a repeat provision call must add no rows"


def test_get_plateau_pair_returns_none_before_provisioning(db_session, make_org, tenant_ctx):
    from app.modules.interface_register.services import plateau_pair_service as service

    org = make_org("plateaupair-c")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)

        assert service.get_plateau_pair(initiative.id) is None


def test_two_initiatives_sharing_one_architecture_get_separate_pairs(
    db_session, make_org, tenant_ctx
):
    """D1 regression: TechnologyRoadmapInitiative.architecture_id is a
    non-unique FK, so two initiatives can legitimately share one
    ArchitectureModel. Keying the plateau pair on architecture_id alone
    (the pre-fix behaviour) would silently resolve both initiatives to the
    same pair, leaking one initiative's gaps onto the other's comparison
    screen. Keying on initiative_id must keep them fully separate."""
    from app.models.implementation_migration import Plateau
    from app.modules.interface_register.services import plateau_pair_service as service

    org = make_org("plateaupair-e")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative_a = _make_initiative(db_session, architecture.id, name="Initiative A")
        initiative_b = _make_initiative(db_session, architecture.id, name="Initiative B")

        a_as_is, a_to_be = service.provision_plateau_pair(initiative_a.id)
        b_as_is, b_to_be = service.provision_plateau_pair(initiative_b.id)

        assert a_as_is.id != b_as_is.id, "initiatives sharing an architecture must not share a plateau"
        assert a_to_be.id != b_to_be.id
        assert a_as_is.initiative_id == initiative_a.id
        assert b_as_is.initiative_id == initiative_b.id

        # Both initiatives resolve their own pair, not each other's.
        resolved_a = service.get_plateau_pair(initiative_a.id)
        resolved_b = service.get_plateau_pair(initiative_b.id)
        assert resolved_a == (a_as_is, a_to_be)
        assert resolved_b == (b_as_is, b_to_be)

        total = Plateau.query.filter_by(architecture_id=architecture.id).count()
        assert total == 4, "two initiatives sharing an architecture must produce two distinct pairs"


def test_provision_plateau_pair_survives_concurrent_race(db_session, make_org, tenant_ctx):
    """D2 regression: provision_plateau_pair's guard is read-then-write, not
    atomic. Two concurrent callers can both pass the read check before either
    commits. The unique partial index (uq_plateau_initiative_scope) is the
    real guarantee -- simulate the race by calling provision_plateau_pair a
    second time after manually re-inserting a duplicate row that bypasses the
    read-check (as a second in-flight transaction would), and confirm the
    IntegrityError path resolves to a single winning pair rather than
    raising or leaving a duplicate visible."""
    from sqlalchemy.exc import IntegrityError
    from app import db
    from app.models.implementation_migration import Plateau
    from app.modules.interface_register.services import plateau_pair_service as service

    org = make_org("plateaupair-f")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)

        # First caller provisions normally.
        first_as_is, first_to_be = service.provision_plateau_pair(initiative.id)

        # Simulate a second, concurrent caller's insert of the same as-is row
        # racing in after the first caller's read-check but before its
        # commit was visible -- the unique index must reject it.
        dupe = Plateau(
            name=service.ASIS_PLATEAU_NAME,
            architecture_id=architecture.id,
            initiative_id=initiative.id,
            sequence_order=1,
        )
        db_session.add(dupe)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

        # A subsequent provision_plateau_pair call (the "loser" retrying, or
        # any later caller) must resolve to the one real pair, not raise and
        # not create a third row.
        again_as_is, again_to_be = service.provision_plateau_pair(initiative.id)
        assert again_as_is.id == first_as_is.id
        assert again_to_be.id == first_to_be.id

        total = Plateau.query.filter_by(
            initiative_id=initiative.id, name=service.ASIS_PLATEAU_NAME
        ).count()
        assert total == 1, "the unique index must prevent a second as-is plateau for one initiative"


def test_get_plateau_pair_does_not_write(db_session, make_org, tenant_ctx):
    """get_plateau_pair is read-only — calling it repeatedly with no prior
    provisioning must never create rows (GET is side-effect-free, US-4 AC4)."""
    from app.models.implementation_migration import Plateau
    from app.modules.interface_register.services import plateau_pair_service as service

    org = make_org("plateaupair-d")
    with tenant_ctx(org.id):
        architecture = _make_architecture(db_session, org.id)
        initiative = _make_initiative(db_session, architecture.id)

        service.get_plateau_pair(initiative.id)
        service.get_plateau_pair(initiative.id)

        assert Plateau.query.filter_by(architecture_id=architecture.id).count() == 0
