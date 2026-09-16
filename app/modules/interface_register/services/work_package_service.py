"""Attaches a costed WorkPackage to an interface Gap (US-6 AC6). The write path for Task 04's rollup -- see programme_rollup_service.py for the read path."""

import math

from app import db
from app.models.implementation_migration import Gap, GAP_KIND_PLATEAU_TRANSITION, WorkPackage
from app.modules.interface_register.services.interface_register_service import InterfaceRegisterError
from app.modules.interface_register.services.plateau_pair_service import get_plateau_pair

# Postgres int4 ceiling -- estimated_effort_hours is db.Integer
# (app/models/implementation_migration.py). No existing domain-specific hours
# cap was found elsewhere in the codebase, so this uses the column's own
# storage limit as the validation boundary (D7).
MAX_INT4 = 2_147_483_647


def _parse_optional_number(raw, *, as_int=False):
    """Parse an optional number from form input.

    Returns:
        float|int|None: Parsed number or None if input is None/empty

    Raises:
        InterfaceRegisterError: if the raw value is non-numeric, non-finite
            (NaN/Infinity), or negative.
    """
    if raw is None:
        return None

    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None

    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise InterfaceRegisterError("Estimated cost and effort hours must be numeric")

    if not math.isfinite(value):
        raise InterfaceRegisterError("Estimated cost and effort hours must be a finite number")

    if value < 0:
        raise InterfaceRegisterError("Estimated cost and effort hours must not be negative")

    if as_int:
        int_value = int(round(value))
        if int_value > MAX_INT4:
            raise InterfaceRegisterError(
                f"Estimated effort hours must be {MAX_INT4:,} or less"
            )
        return int_value
    return value


def attach_work_package_to_gap(gap_id, *, initiative_id=None, name=None, estimated_cost=None, estimated_effort_hours=None) -> WorkPackage:
    """Attach a costed WorkPackage to an interface gap.

    Args:
        gap_id: ID of the gap to attach to
        initiative_id: initiative the gap must belong to (via its To-Be
            plateau) -- required so a gap belonging to a different
            initiative cannot be targeted by posting a mismatched
            initiative_id (D3).
        name: Name for the work package
        estimated_cost: Estimated cost (optional)
        estimated_effort_hours: Estimated effort in hours (optional)

    Returns:
        WorkPackage: The created work package object

    Raises:
        InterfaceRegisterError: If validation fails
    """
    gap = Gap.query.filter_by(
        id=gap_id,
        gap_kind=GAP_KIND_PLATEAU_TRANSITION
    ).first()

    if gap is None:
        raise InterfaceRegisterError("Gap not found")

    if initiative_id is not None:
        plateau_pair = get_plateau_pair(initiative_id)
        to_be = plateau_pair[1] if plateau_pair else None
        if to_be is None or gap.target_plateau_id != to_be.id:
            raise InterfaceRegisterError("Gap does not belong to this initiative")

    clean_name = (name or "").strip() or f"Work package: {gap.name}"
    
    cost = _parse_optional_number(estimated_cost)
    hours = _parse_optional_number(estimated_effort_hours, as_int=True)
    
    work_package = WorkPackage(
        name=clean_name,
        architecture_id=gap.architecture_id,
        plateau_id=gap.target_plateau_id,
        estimated_cost=cost,
        estimated_effort_hours=hours,
        status="planned"
    )
    
    try:
        db.session.add(work_package)
        gap.work_packages.append(work_package)
        db.session.commit()
        return work_package
    except Exception:
        db.session.rollback()
        raise
