"""
ADM Phase Element Guide Service — SA-003.

Maps TOGAF ADM phases A-H to the ArchiMate element types that architects
should create during that phase, and calculates a completion score based
on elements already present in the archimate_elements table.
"""

# ---------------------------------------------------------------------------
# Phase → element type mapping  (THE canonical constant)
# ---------------------------------------------------------------------------

PHASE_ELEMENT_MAP: dict[str, list[str]] = {
    "A": ["Stakeholder", "Driver", "Goal", "Principle"],
    "B": [
        "BusinessActor",
        "BusinessRole",
        "BusinessProcess",
        "BusinessService",
        "BusinessFunction",
        "BusinessObject",
    ],
    "C": [
        "ApplicationComponent",
        "ApplicationService",
        "ApplicationFunction",
        "DataObject",
        "DataStore",
        "DataComponent",
    ],
    "D": [
        "Device",
        "SystemSoftware",
        "TechnologyService",
        "TechnologyInterface",
        "Node",
        "Network",
    ],
    "E": ["Plateau", "Gap", "WorkPackage"],
    "F": ["WorkPackage", "Plateau", "Gap"],
    "G": ["Constraint", "Requirement"],
    "H": ["Driver", "Goal"],
}

# ArchiMate layer for each element type
_LAYER_MAP: dict[str, str] = {
    "Stakeholder": "motivation",
    "Driver": "motivation",
    "Goal": "motivation",
    "Principle": "motivation",
    "Constraint": "motivation",
    "Requirement": "motivation",
    "BusinessActor": "business",
    "BusinessRole": "business",
    "BusinessProcess": "business",
    "BusinessService": "business",
    "BusinessFunction": "business",
    "BusinessObject": "business",
    "ApplicationComponent": "application",
    "ApplicationService": "application",
    "ApplicationFunction": "application",
    "DataObject": "application",
    "DataStore": "application",
    "DataComponent": "application",
    "Device": "technology",
    "SystemSoftware": "technology",
    "TechnologyService": "technology",
    "TechnologyInterface": "technology",
    "Node": "technology",
    "Network": "technology",
    "Plateau": "implementation_migration",
    "Gap": "implementation_migration",
    "WorkPackage": "implementation_migration",
}

_DESCRIPTION_MAP: dict[str, str] = {
    "Stakeholder": "A person, role, or organisation with an interest in the architecture outcome",
    "Driver": "An external or internal condition that motivates the organisation to change",
    "Goal": "A high-level statement of intent or aspiration for the architecture",
    "Principle": "A qualitative statement of intent that guides the architecture",
    "BusinessActor": "An organisational entity capable of performing behaviour",
    "BusinessRole": "The responsibility for performing specific business behaviour",
    "BusinessProcess": "A sequence of business behaviours that achieves a result",
    "BusinessService": "An explicitly defined exposed business behaviour",
    "BusinessFunction": "A collection of business behaviour based on a set of criteria",
    "BusinessObject": "A concept used within a particular business domain",
    "ApplicationComponent": "An encapsulation of application functionality",
    "ApplicationService": "An explicitly defined exposed application behaviour",
    "ApplicationFunction": "Automated behaviour that can be performed by an application component",
    "DataObject": "Data structured for automated processing",
    "DataStore": "A persistent storage of data",
    "DataComponent": "An encapsulation of data",
    "Device": "A physical IT resource upon which system software and artifacts can be stored",
    "SystemSoftware": "Software that provides or contributes to an environment for storing, executing, and using software",
    "TechnologyService": "An explicitly defined exposed technology behaviour",
    "TechnologyInterface": "A point of access where technology services offered by a node can be accessed",
    "Node": "A computational or physical resource that hosts, manipulates, or interacts with other computational resources",
    "Network": "A communication or other infrastructure between nodes",
    "Plateau": "A relatively stable state of the architecture that exists during a limited period of time",
    "Gap": "A statement of difference between two plateaus",
    "WorkPackage": "A series of actions identified and designed to achieve specific results",
    "Constraint": "A factor that limits or constrains the realisation of goals",
    "Requirement": "A statement of need that must be realised by the system",
}


def get_suggested_elements_for_phase(phase: str) -> list[dict]:
    """Return suggested ArchiMate element types for the given ADM phase.

    Args:
        phase: ADM phase code (A-H).

    Returns:
        List of dicts: [{"type": str, "layer": str, "description": str}].
        Empty list for unknown phases.
    """
    phase = phase.upper()
    types = PHASE_ELEMENT_MAP.get(phase, [])
    return [
        {
            "type": t,
            "layer": _LAYER_MAP.get(t, ""),
            "description": _DESCRIPTION_MAP.get(t, ""),
        }
        for t in types
    ]


def get_phase_completion_score(phase: str, board_id: int | None = None) -> dict:
    """Return element-creation progress for the given ADM phase.

    Counts how many of the suggested element types for *phase* have at least
    one ArchiMateElement row in the database.  ``board_id`` is accepted for
    API compatibility but the current implementation counts across all
    elements (the table is not partitioned by board).

    Args:
        phase:    ADM phase code (A-H).
        board_id: Optional board id (reserved for future scoping).

    Returns:
        {"total_suggested": int, "created": int, "pct": int}
    """
    phase = phase.upper()
    suggested = PHASE_ELEMENT_MAP.get(phase, [])
    total = len(suggested)
    if total == 0:
        return {"total_suggested": 0, "created": 0, "pct": 0}

    try:
        from app.models.archimate_core import ArchiMateElement  # type: ignore[import]

        created_types: set[str] = set()
        rows = (
            ArchiMateElement.query  # type: ignore[attr-defined]
            .with_entities(ArchiMateElement.type)
            .filter(ArchiMateElement.type.in_(suggested))  # model-safety-ok
            .distinct()
            .all()  # model-safety-ok
        )
        for row in rows:
            if row.type:
                created_types.add(row.type)
        created = len(created_types)
    except Exception:
        created = 0

    pct = round(created / total * 100) if total else 0
    return {"total_suggested": total, "created": created, "pct": pct}
