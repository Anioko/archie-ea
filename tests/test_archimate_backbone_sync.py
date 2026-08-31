"""Every motivation entity must be ABLE to join the ArchiMate backbone.

CLAUDE.md: "ArchiMate is the backbone, not a view ... A plain textarea is not an
acceptable substitute -- the field IS the element."

The `archimate-backbone` gate counted 53 creation paths that never synced. What
the count hid is that roughly half of them COULD NOT HAVE: Risk,
SolutionDriver, SolutionGoal, SolutionConstraint and SolutionRisk had no
archimate column at all, and SolutionRequirement's archimate_requirement_id
points at the enterprise `requirements` table, not at an element. A convention
cannot be followed where the schema has no place to record compliance.

These tests pin the structural precondition, so the situation cannot return: the
mapping is complete, and every model in it can actually store its link.
"""

import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _checker_motivation_set():
    """The entity set the gate enforces, read from the gate itself."""
    path = os.path.join(REPO, "scripts", "check_archimate_backbone.py")
    spec = importlib.util.spec_from_file_location("_backbone_checker", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return set(module.MOTIVATION)


def test_the_mapping_covers_exactly_what_the_gate_enforces():
    """A type the gate flags but the helper cannot map is an unfixable finding."""
    from app.services.archimate_backbone import ELEMENT_TYPES

    gate = _checker_motivation_set()
    mapped = set(ELEMENT_TYPES)
    assert not (gate - mapped), (
        "the gate flags these types but archimate_backbone.ELEMENT_TYPES cannot "
        "map them, so the finding could never be closed: %s" % sorted(gate - mapped)
    )


def test_every_mapped_motivation_model_can_store_its_link(app):
    """The precondition that was missing for six of thirteen models."""
    from app import db
    from app.services.archimate_backbone import ELEMENT_TYPES

    with app.app_context():
        by_name = {}
        for mapper in db.Model.registry.mappers:
            by_name.setdefault(mapper.class_.__name__, mapper.class_)

        missing = []
        for type_name in sorted(ELEMENT_TYPES):
            model = by_name.get(type_name)
            if model is None:
                continue  # not mapped in this build; nothing can create one
            if "archimate_element_id" not in model.__table__.c:
                missing.append("%s (%s)" % (type_name, model.__table__.name))

    assert not missing, (
        "these motivation models have nowhere to record their ArchiMate "
        "element, so their creation paths cannot join the backbone at any "
        "price: %s" % ", ".join(missing)
    )


@pytest.mark.parametrize("layer_expected", ["Motivation", "Implementation"])
def test_every_mapping_names_a_real_archimate_layer(layer_expected):
    from app.services.archimate_backbone import ELEMENT_TYPES

    layers = {layer for _, layer in ELEMENT_TYPES.values()}
    assert layers <= {"Motivation", "Implementation"}, (
        "unexpected ArchiMate layer in the mapping: %s" % sorted(layers)
    )
    assert layer_expected in layers


def test_a_risk_joins_the_backbone_when_synced(db_session, make_org):
    """End to end on the model that had no link column until now.

    Uses the shared fixtures from tests/conftest.py -- db_session runs inside a
    transaction that is always rolled back, so this cannot leave residue in the
    shared test database.
    """
    from app.models.archimate_core import ArchiMateElement
    from app.models.risk import Risk
    from app.services.archimate_backbone import sync_archimate_element

    org = make_org("backbone")
    risk = Risk(
        organization_id=org.id,
        title="Unencrypted PII at rest",
        description="Customer records stored without disk encryption.",
        likelihood=4,
        impact=5,
    )
    db_session.add(risk)
    db_session.flush()

    element = sync_archimate_element(risk, session=db_session)
    assert element is not None
    assert risk.archimate_element_id == element.id
    assert element.type == "Assessment"
    assert element.layer == "Motivation"
    assert element.organization_id == org.id

    # Idempotent: a second call must not create a second element.
    assert sync_archimate_element(risk, session=db_session) is None
    assert db_session.query(ArchiMateElement).filter_by(
        organization_id=org.id, name="Unencrypted PII at rest"
    ).count() == 1


def test_an_unnamed_motivation_row_raises_rather_than_skipping(db_session, make_org):
    """Silently skipping is what produced a backbone with holes in it."""
    from app.models.risk import Risk
    from app.services.archimate_backbone import sync_archimate_element

    org = make_org("unnamed")
    risk = Risk(organization_id=org.id, title="", description="", likelihood=1, impact=1)
    with pytest.raises(ValueError, match="no name/title"):
        sync_archimate_element(risk, session=db_session)
