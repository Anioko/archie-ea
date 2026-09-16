"""Service for raising gaps between as-is and to-be interface states."""

from __future__ import annotations

from app import db
from app.models.archimate_core import ArchiMateElement
from app.models.implementation_migration import (
    Gap,
    GAP_KIND_PLATEAU_TRANSITION,
    TechnologyRoadmapInitiative,
    validate_gap_kind,
)
from app.modules.interface_register.services.interface_register_service import InterfaceRegisterError
from app.modules.interface_register.services.plateau_pair_service import get_plateau_pair

GAP_TYPES = {"protocol_change", "new_interface", "retirement"}


def raise_interface_gap(element_id, initiative_id, gap_type, **fields) -> Gap:
    """Raise a gap for an interface between as-is and to-be plateaus.
    
    Args:
        element_id: ID of the ApplicationInterface element
        initiative_id: ID of the technology roadmap initiative
        gap_type: Type of gap from GAP_TYPES
        **fields: Additional gap fields (name, description, severity, impact, priority)
        
    Returns:
        Gap: The created gap object
        
    Raises:
        InterfaceRegisterError: If validation fails or plateaus don't exist
    """
    # Validate interface exists
    element = ArchiMateElement.query.filter_by(
        id=element_id,
        type="ApplicationInterface"
    ).first()
    
    if not element:
        raise InterfaceRegisterError("Interface not found")
    
    # Validate gap type
    if gap_type not in GAP_TYPES:
        raise InterfaceRegisterError(
            f"Invalid gap type '{gap_type}'. Must be one of: {', '.join(GAP_TYPES)}"
        )
    
    # Get plateau pair (must exist already)
    pair = get_plateau_pair(initiative_id)
    if pair is None:
        raise InterfaceRegisterError("Set up the As-is/To-be comparison first")
    
    as_is, to_be = pair

    # Generate name if not provided
    name = (fields.get("name") or "").strip()
    if not name:
        name = f"{gap_type.replace('_', ' ').title()} gap: {element.name}"

    # D3: stamp architecture_id from the initiative so architecture-scoped
    # gap surfaces (e.g. roadmap_generator's own architecture_id filter) can
    # correctly include/exclude this gap once gap_kind filtering is in place.
    initiative = TechnologyRoadmapInitiative.query.get(initiative_id)
    architecture_id = initiative.architecture_id if initiative else None

    # Create gap object
    gap = Gap(
        name=name,
        description=(fields.get("description") or "").strip() or None,
        gap_kind=GAP_KIND_PLATEAU_TRANSITION,
        gap_type=gap_type,
        archimate_element_id=element.id,
        originating_plateau_id=as_is.id,
        target_plateau_id=to_be.id,
        architecture_id=architecture_id,
        severity=fields.get("severity") or "medium",
        impact=fields.get("impact") or "medium",
        priority=fields.get("priority") or "medium"
    )
    
    # Validate gap before adding to session
    try:
        validate_gap_kind(gap)
    except ValueError as exc:
        raise InterfaceRegisterError(str(exc))
    
    # Save to database
    try:
        db.session.add(gap)
        db.session.commit()
        return gap
    except Exception:
        db.session.rollback()
        raise
