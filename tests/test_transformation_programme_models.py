"""Canonical Transformation Programme model and database invariants."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.benefit import Benefit
from app.models.implementation_migration import WorkPackage
from app.models.mixins import TenantMixin
from app.models.solution_models import Solution
from app.models.strategic import RoadmapItem, StrategicInitiative
from app.models.transformation_programme import (
    MeasureDefinition,
    ProgrammeOutcomeCommitment,
    ProgrammeRoleAssignment,
    ProgrammeWorkstream,
)


@pytest.fixture(scope="module", autouse=True)
def transformation_schema(app, _schema):
    """Install the privileged constraints container boot installs in production."""
    from app.commands.reconcile_schema import _reconcile

    with app.app_context():
        _added, failed, _missing, _blocking = _reconcile(dry_run=False)
        assert failed == []


def _make_user(db_session, org, label="user"):
    from app.models.user import User

    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"{label}-{suffix}@example.test",
        first_name=label,
        organization_id=org.id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _programme_graph(db_session, org, label="programme"):
    owner = _make_user(db_session, org, f"{label}-owner")
    programme = StrategicInitiative(
        name=f"{label} {uuid.uuid4().hex[:8]}",
        record_kind="transformation_programme",
        organization_id=org.id,
        owner_id=owner.id,
    )
    db_session.add(programme)
    db_session.flush()
    stream = ProgrammeWorkstream(
        organization_id=org.id,
        programme_id=programme.id,
        workstream_type="application_rationalisation",
        objective="Remove avoidable run cost",
        lifecycle_stage="objective",
        revision=1,
    )
    db_session.add(stream)
    db_session.flush()
    return owner, programme, stream


def _expect_integrity_error(db_session, row):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(row)
        db_session.flush()


def test_transformation_programme_graph_is_tenant_scoped(db_session, make_org, tenant_ctx):
    org_a, org_b = make_org("A"), make_org("B")
    with tenant_ctx(org_a.id):
        programme = StrategicInitiative(
            name="Reduce run cost", record_kind="transformation_programme"
        )
        db_session.add(programme)
        db_session.flush()
        stream = ProgrammeWorkstream(
            organization_id=org_a.id,
            programme_id=programme.id,
            workstream_type="application_rationalisation",
            objective="Remove avoidable run cost",
            lifecycle_stage="objective",
            revision=1,
        )
        db_session.add(stream)
        db_session.flush()
        stream_id = stream.id

    db_session.expunge_all()
    with tenant_ctx(org_b.id):
        assert (
            db_session.scalar(
                db.select(ProgrammeWorkstream).where(ProgrammeWorkstream.id == stream_id)
            )
            is None
        )


def test_nullable_metrics_do_not_become_zero():
    measure = MeasureDefinition(metric_name="Annual run cost", unit="GBP")
    assert measure.baseline_value is None
    assert measure.target_value is None
    assert measure.to_dict()["baseline_value"] is None


def test_new_programme_children_reject_cross_tenant_parents(db_session, make_org):
    org_a, org_b = make_org("parent-a"), make_org("parent-b")
    owner_a, programme_a, stream_a = _programme_graph(db_session, org_a, "A")
    owner_b = _make_user(db_session, org_b, "B-owner")

    _expect_integrity_error(
        db_session,
        ProgrammeWorkstream(
            organization_id=org_b.id,
            programme_id=programme_a.id,
            workstream_type="application_rationalisation",
            objective="Foreign programme",
            lifecycle_stage="objective",
        ),
    )
    _expect_integrity_error(
        db_session,
        ProgrammeRoleAssignment(
            organization_id=org_a.id,
            programme_id=programme_a.id,
            workstream_id=stream_a.id,
            user_id=owner_b.id,
            role="contributor",
            effective_from=date(2026, 8, 22),
            assigned_by_id=owner_a.id,
        ),
    )
    _expect_integrity_error(
        db_session,
        ProgrammeOutcomeCommitment(
            organization_id=org_a.id,
            programme_id=programme_a.id,
            workstream_id=stream_a.id,
            statement="Reduce cost",
            owner_id=owner_b.id,
            improvement_direction="decrease",
            lifecycle="committed",
        ),
    )

    outcome = ProgrammeOutcomeCommitment(
        organization_id=org_a.id,
        programme_id=programme_a.id,
        workstream_id=stream_a.id,
        statement="Reduce cost",
        owner_id=owner_a.id,
        improvement_direction="decrease",
        lifecycle="committed",
    )
    db_session.add(outcome)
    db_session.flush()
    _expect_integrity_error(
        db_session,
        MeasureDefinition(
            organization_id=org_b.id,
            outcome_commitment_id=outcome.id,
            metric_name="Annual run cost",
            unit="GBP",
            currency="GBP",
            aggregation="sum",
        ),
    )


def test_roadmap_item_is_tenant_scoped():
    assert issubclass(RoadmapItem, TenantMixin)


@pytest.mark.parametrize("delivery_kind", ["roadmap", "work_package", "benefit", "solution"])
def test_delivery_link_programme_must_match_workstream(
    db_session, make_org, delivery_kind
):
    org = make_org(f"delivery-{delivery_kind}")
    _owner, _programme_a, stream_a = _programme_graph(db_session, org, "A")
    _owner_b, programme_b, _stream_b = _programme_graph(db_session, org, "B")

    rows = {
        "roadmap": RoadmapItem(
            organization_id=org.id,
            title="Roadmap row",
            initiative_id=programme_b.id,
            programme_workstream_id=stream_a.id,
        ),
        "work_package": WorkPackage(
            organization_id=org.id,
            name="Work row",
            strategic_initiative_id=programme_b.id,
            programme_workstream_id=stream_a.id,
        ),
        "benefit": Benefit(
            organization_id=org.id,
            name="Benefit row",
            strategic_initiative_id=programme_b.id,
            programme_workstream_id=stream_a.id,
        ),
        "solution": Solution(
            organization_id=org.id,
            name="Solution row",
            initiative_id=programme_b.id,
            workstream_id=stream_a.id,
        ),
    }
    _expect_integrity_error(db_session, rows[delivery_kind])


@pytest.mark.parametrize("delivery_kind", ["roadmap", "work_package", "benefit"])
def test_materialisation_key_is_unique_within_tenant(db_session, make_org, delivery_kind):
    org = make_org(f"materialisation-{delivery_kind}")
    common = {"organization_id": org.id, "materialisation_key": "same-key"}
    factories = {
        "roadmap": lambda suffix: RoadmapItem(title=f"Roadmap {suffix}", **common),
        "work_package": lambda suffix: WorkPackage(name=f"Work {suffix}", **common),
        "benefit": lambda suffix: Benefit(name=f"Benefit {suffix}", **common),
    }
    db_session.add(factories[delivery_kind]("one"))
    db_session.flush()
    _expect_integrity_error(db_session, factories[delivery_kind]("two"))


def test_null_materialisation_keys_are_not_treated_as_duplicates(db_session, make_org):
    org = make_org("null-materialisation")
    db_session.add_all(
        [
            WorkPackage(name="One", organization_id=org.id),
            WorkPackage(name="Two", organization_id=org.id),
        ]
    )
    db_session.flush()


def test_programme_and_workstream_deletes_are_restricted(db_session, make_org):
    org = make_org("restrict")
    _owner, programme, stream = _programme_graph(db_session, org, "restrict")
    work = WorkPackage(
        name="Protected work",
        organization_id=org.id,
        strategic_initiative_id=programme.id,
        programme_workstream_id=stream.id,
    )
    db_session.add(work)
    db_session.flush()

    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.delete(stream)
        db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.delete(programme)
        db_session.flush()


def test_benefit_legacy_initiative_delete_sets_null(db_session, make_org):
    from app.models.vendor.vendor_organization import EnterpriseInitiative

    org = make_org("legacy-benefit")
    legacy = EnterpriseInitiative(
        name=f"Legacy {uuid.uuid4().hex[:8]}", organization_id=org.id
    )
    db_session.add(legacy)
    db_session.flush()
    benefit = Benefit(
        name="Preserved benefit",
        organization_id=org.id,
        legacy_enterprise_initiative_id=legacy.id,
    )
    db_session.add(benefit)
    db_session.flush()
    benefit_id = benefit.id

    db_session.delete(legacy)
    db_session.flush()
    db_session.expire_all()

    preserved = db_session.get(Benefit, benefit_id)
    assert preserved is not None
    assert preserved.legacy_enterprise_initiative_id is None


def test_existing_rows_with_null_additive_links_still_serialize(db_session, make_org):
    org = make_org("legacy-null-columns")
    programme = StrategicInitiative(name="Old initiative", organization_id=org.id)
    roadmap = RoadmapItem(title="Old roadmap item", organization_id=org.id)
    work = WorkPackage(name="Old work package", organization_id=org.id)
    benefit = Benefit(name="Old benefit", organization_id=org.id)
    db_session.add_all([programme, roadmap, work, benefit])
    db_session.flush()

    assert programme.to_dict()["record_kind"] is None
    assert roadmap.to_dict()["programme_workstream_id"] is None
    assert roadmap.to_dict()["materialisation_key"] is None
    assert work.to_dict()["strategic_initiative_id"] is None
    assert work.to_dict()["programme_workstream_id"] is None
    assert benefit.to_dict()["strategic_initiative_id"] is None
    assert benefit.to_dict()["legacy_enterprise_initiative_id"] is None
