"""Pins that app/models/archimate_element_types.py (the element-type registry)
and app/models/archimate_core.py (the relationship-validity classifier) agree
on one canonical layer string per element type, and that a relationship
touching a Grouping, Junction or Location companion element
(app/models/structural_elements.py) validates to a defined result instead of
the ambiguous "element type not in registry" unknown-layer skip.

No database access is needed: ArchiMateElementTypes and validate_relationship
are both pure Python over module-level data.
"""

from __future__ import annotations

import re


def _snake_case(pascal_name: str) -> str:
    """The PascalCase -> snake_case convention already used at the
    ArchiMateElement.type / _ELEMENT_TYPE_LAYER boundary elsewhere in this
    codebase (e.g. app/modules/ai_chat/services/workbench_kernel.py's
    _pascal_to_snake): 'WorkPackage' -> 'work_package'.
    """
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", pascal_name).lower()


def test_every_element_type_layer_is_recognised_by_the_relationship_validator():
    """Every one of the 58 ArchiMate element types must resolve to a layer
    _ELEMENT_TYPE_LAYER also knows about, and both authorities must spell
    that layer the same way. Before the fix this fails for the five
    Implementation & Migration types (WorkPackage, Deliverable,
    ImplementationEvent, Plateau, Gap): ArchiMateElementTypes says
    'implementation_migration', _ELEMENT_TYPE_LAYER says 'implementation'.
    """
    from app.models.archimate_core import _ELEMENT_TYPE_LAYER
    from app.models.archimate_element_types import ArchiMateElementTypes

    all_elements = ArchiMateElementTypes.get_all_elements()
    assert all_elements, "the element type registry must not be empty"

    missing = []
    mismatched = []
    for name, definition in all_elements.items():
        key = _snake_case(name)
        if key not in _ELEMENT_TYPE_LAYER:
            missing.append((name, key))
            continue
        if _ELEMENT_TYPE_LAYER[key] != definition.layer:
            mismatched.append((name, _ELEMENT_TYPE_LAYER[key], definition.layer))

    assert not missing, f"element types missing from _ELEMENT_TYPE_LAYER: {missing}"
    assert not mismatched, (
        "archimate_core._ELEMENT_TYPE_LAYER disagrees with "
        f"ArchiMateElementTypes on the canonical layer string: {mismatched}"
    )


def test_workpackage_resolves_to_one_canonical_implementation_migration_layer():
    """Direct regression pin for the reported defect: the seventh layer must
    read 'implementation_migration' from both authorities, not
    'implementation_migration' from one and 'implementation' from the other.
    """
    from app.models.archimate_core import _ELEMENT_TYPE_LAYER
    from app.models.archimate_element_types import ArchiMateElementTypes

    assert (
        ArchiMateElementTypes.get_element_type("WorkPackage").layer
        == "implementation_migration"
    )
    assert _ELEMENT_TYPE_LAYER["work_package"] == "implementation_migration"


def test_workpackage_to_gap_relationship_still_validates_after_the_spelling_fix():
    """Realigning the spelling must not silently break the relationship-
    validity matrix lookups for the layer it renames -- a same-layer
    Implementation & Migration relationship must still validate True.
    """
    from app.models.archimate_core import validate_relationship

    is_valid, message = validate_relationship("realization", "work_package", "gap")
    assert is_valid is True
    assert "implementation_migration" in message


def test_grouping_relationship_validates_to_a_defined_result_not_unknown():
    """structural_elements.py creates the Grouping companion ArchiMateElement
    with layer="Reference"; a relationship touching it must resolve to a
    real verdict, not the "not in registry / skipped" unknown-layer escape
    hatch.
    """
    from app.models.archimate_core import validate_relationship

    is_valid, message = validate_relationship(
        "association", "Grouping", "business_process"
    )
    assert is_valid is True
    assert "unknown" not in message.lower()
    assert "not in registry" not in message.lower()


def test_junction_relationship_validates_to_a_defined_result_not_unknown():
    from app.models.archimate_core import validate_relationship

    is_valid, message = validate_relationship(
        "association", "Junction", "application_component"
    )
    assert is_valid is True
    assert "unknown" not in message.lower()
    assert "not in registry" not in message.lower()


def test_location_relationship_validates_to_a_defined_result_not_unknown():
    from app.models.archimate_core import validate_relationship

    is_valid, message = validate_relationship("association", "node", "Location")
    assert is_valid is True
    assert "unknown" not in message.lower()
    assert "not in registry" not in message.lower()


def test_genuinely_unrecognised_type_still_skips_like_before():
    """The structural-element short-circuit must not swallow the existing,
    unrelated "type not in the registry at all" case -- a made-up type
    still gets the old, honest skip message.
    """
    from app.models.archimate_core import validate_relationship

    is_valid, message = validate_relationship(
        "association", "totally_made_up_type", "business_process"
    )
    assert is_valid is True
    assert "not in registry" in message.lower()
