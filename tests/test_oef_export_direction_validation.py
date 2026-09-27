"""O-01: the exported OEF must never emit a relationship the ArchiMate 3.2
matrix forbids, including in the direction it is stored.

The 17 Aug 2026 QA register measured 18 of 67 exported relationships as
invalid or inverted: Goal -> Requirement stored backwards (a Requirement
realises a Goal, never the reverse — ArchiMate 3.2 SS5.1.3) x7, and
Goal -> Goal (not a permitted pairing for any non-fallback relationship type)
x3.

``ArchiMateOEFService.export_model_validated`` (app/services/archimate_oef_service.py)
now checks every relationship against ``ArchimateValidityService.is_valid``
(the same corrected matrix C-01 fixed in b1f6a8f) on the way out:
  - valid as stored -> emitted unchanged.
  - invalid as stored but valid reversed -> emitted with source/target
    swapped, and the correction is reported in ``validation_errors``.
  - invalid in both directions -> dropped from the export entirely, and the
    drop is reported in ``validation_errors``. Nothing the matrix forbids is
    ever emitted silently.

This test seeds exactly those two known-invalid shapes plus one valid
relationship as a control, exports, and asserts the exported XML contains
nothing the matrix forbids — the highest-value O-01 test per the register.
"""

from __future__ import annotations

import uuid

import xml.etree.ElementTree as ET

import pytest

NS = "{http://www.opengroup.org/xsd/archimate/3.0/}"


@pytest.fixture
def seeded_model(app, db_session):
    from app.models.archimate_core import ArchitectureModel
    from app.models.models import ArchiMateElement, ArchiMateRelationship

    with app.test_request_context("/"):
        from flask import g

        from app import db

        org = db_session.execute(
            db.text("SELECT id FROM organizations ORDER BY id LIMIT 1")
        ).scalar()
        if org is None:
            from app.models.organization import Organization

            suffix = uuid.uuid4().hex[:8]
            seeded = Organization(name=f"OEF Dir Org {suffix}", slug=f"oef-dir-{suffix}")
            db_session.add(seeded)
            db_session.flush()
            org = seeded.id
        g.current_org_id = org

        suffix = uuid.uuid4().hex[:8]
        model = ArchitectureModel(name=f"OEF Direction Test {suffix}")
        db_session.add(model)
        db_session.flush()

        goal = ArchiMateElement(name=f"Goal {suffix}", type="Goal", architecture_id=model.id)
        goal2 = ArchiMateElement(name=f"Goal2 {suffix}", type="Goal", architecture_id=model.id)
        requirement = ArchiMateElement(
            name=f"Requirement {suffix}", type="Requirement", architecture_id=model.id
        )
        comp = ArchiMateElement(
            name=f"Component {suffix}", type="ApplicationComponent", architecture_id=model.id
        )
        svc = ArchiMateElement(
            name=f"Service {suffix}", type="ApplicationService", architecture_id=model.id
        )
        db_session.add_all([goal, goal2, requirement, comp, svc])
        db_session.flush()

        # Invalid #1: Goal -> Requirement realization, stored BACKWARDS.
        # Correct direction is Requirement -> Goal (realization). Reversible:
        # must be emitted as Requirement -> Goal.
        backwards_realization = ArchiMateRelationship(
            type="realization",
            architecture_id=model.id,
            source_id=goal.id,
            target_id=requirement.id,
        )
        # Invalid #2: Goal -> Goal triggering — a behavioural relationship type
        # not permitted between motivation elements in either direction
        # (composition/aggregation ARE valid for Goal decomposition; triggering
        # is not). Must be dropped.
        goal_goal = ArchiMateRelationship(
            type="triggering",
            architecture_id=model.id,
            source_id=goal.id,
            target_id=goal2.id,
        )
        # Control: a genuinely valid relationship, must survive unchanged.
        valid_realization = ArchiMateRelationship(
            type="realization",
            architecture_id=model.id,
            source_id=comp.id,
            target_id=svc.id,
        )
        db_session.add_all([backwards_realization, goal_goal, valid_realization])
        db_session.commit()

        return {
            "model_id": model.id,
            "goal_id": goal.id,
            "goal2_id": goal2.id,
            "requirement_id": requirement.id,
            "comp_id": comp.id,
            "svc_id": svc.id,
            "backwards_realization_id": backwards_realization.id,
            "goal_goal_id": goal_goal.id,
            "valid_realization_id": valid_realization.id,
        }


def test_export_corrects_or_drops_every_invalid_relationship(app, seeded_model):
    from app.services.archimate_oef_service import ArchiMateOEFService
    from app.services.archimate_validity_service import ArchimateValidityService

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = None  # export_model doesn't filter by org
        service = ArchiMateOEFService()
        xml_str, errors = service.export_model_validated(model_id=seeded_model["model_id"])

    # Both known-invalid relationships must have been reported.
    assert len(errors) == 2, f"expected exactly 2 corrections/drops, got {len(errors)}: {errors}"

    root = ET.fromstring(xml_str)
    elem_type_by_id = {}
    for el in root.find(f"{NS}elements"):
        eid = el.get("identifier").replace("id-", "", 1)
        elem_type_by_id[int(eid)] = el.get(f"{{{service.XSI_NS}}}type")

    validity = ArchimateValidityService()
    rels_el = root.find(f"{NS}relationships")
    seen_source_target = set()
    for rel in rels_el:
        source_id = int(rel.get("source").replace("id-", "", 1))
        target_id = int(rel.get("target").replace("id-", "", 1))
        rel_type = rel.get(f"{{{service.XSI_NS}}}type").lower()
        source_type = elem_type_by_id[source_id]
        target_type = elem_type_by_id[target_id]
        seen_source_target.add((source_id, target_id))

        assert validity.is_valid(source_type, target_type, rel_type), (
            f"export contains a matrix-forbidden relationship: "
            f"{source_type}(id-{source_id}) --{rel_type}--> {target_type}(id-{target_id})"
        )

    # The backwards Goal->Requirement realization must appear reversed
    # (Requirement -> Goal), not as originally stored.
    assert (seeded_model["requirement_id"], seeded_model["goal_id"]) in seen_source_target
    assert (seeded_model["goal_id"], seeded_model["requirement_id"]) not in seen_source_target

    # The Goal->Goal composition (invalid both ways) must be dropped entirely.
    assert (seeded_model["goal_id"], seeded_model["goal2_id"]) not in seen_source_target
    assert (seeded_model["goal2_id"], seeded_model["goal_id"]) not in seen_source_target

    # The valid control relationship must survive unchanged.
    assert (seeded_model["comp_id"], seeded_model["svc_id"]) in seen_source_target


def test_validation_errors_name_the_specific_relationship(app, seeded_model):
    from app.services.archimate_oef_service import ArchiMateOEFService

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = None
        service = ArchiMateOEFService()
        _xml_str, errors = service.export_model_validated(model_id=seeded_model["model_id"])

    joined = "\n".join(errors)
    assert f"id-rel-{seeded_model['backwards_realization_id']}" in joined
    assert f"id-rel-{seeded_model['goal_goal_id']}" in joined
