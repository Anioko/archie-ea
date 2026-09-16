"""One authority for S/4HANA programme costing against the initiative's investment_budget -- see docs/adr/0008-one-system-of-record.md and Task 04's brief (docs/buckets/sap-s4-interface-register/tasks/04-workpackage-rollup-and-bands.md). Every screen answering 'what is committed against the S/4HANA budget' must call interface_programme_rollup(); a second implementation of this sum is a defect even if it currently agrees (store-agreement gate)."""

from flask import g

from app.models.implementation_migration import Gap, GAP_KIND_PLATEAU_TRANSITION
from app.modules.interface_register.services.interface_register_service import resolve_initiative
from app.modules.interface_register.services.plateau_pair_service import get_plateau_pair


def interface_programme_rollup(initiative_id) -> dict:
    """Calculate the programme costing rollup for an S/4HANA initiative.
    
    Returns:
        dict: Rollup data including committed costs, budget, headroom, etc.
    """
    initiative = resolve_initiative(initiative_id, g.current_org_id)
    
    plateau_pair = get_plateau_pair(initiative_id)
    to_be = plateau_pair[1] if plateau_pair else None
    
    if to_be is None:
        gaps = []
    else:
        gaps = Gap.query.filter_by(
            target_plateau_id=to_be.id,
            gap_kind=GAP_KIND_PLATEAU_TRANSITION
        ).all()
    
    # Build set of distinct work packages
    work_packages_dict = {}
    for gap in gaps:
        for wp in gap.work_packages:
            work_packages_dict[wp.id] = wp
    
    work_packages = sorted(work_packages_dict.values(), key=lambda wp: wp.id)
    
    # Calculate rollup values
    committed_cost = 0.0
    work_packages_missing_cost = 0
    total_effort_hours = 0
    work_packages_missing_effort = 0

    for wp in work_packages:
        if wp.estimated_cost is not None:
            committed_cost += float(wp.estimated_cost)
        else:
            work_packages_missing_cost += 1

        if wp.estimated_effort_hours is not None:
            total_effort_hours += wp.estimated_effort_hours
        else:
            work_packages_missing_effort += 1

    investment_budget = (
        float(initiative.investment_budget)
        if initiative.investment_budget is not None
        else None
    )

    if investment_budget is None:
        headroom = None
        over_budget = None
        overage = None
    else:
        headroom = investment_budget - committed_cost
        over_budget = committed_cost > investment_budget
        overage = (committed_cost - investment_budget) if over_budget else None

    return {
        "initiative": initiative,
        "committed_cost": committed_cost,
        "investment_budget": investment_budget,
        "headroom": headroom,
        "overage": overage,
        "work_packages_missing_cost": work_packages_missing_cost,
        "over_budget": over_budget,
        "total_effort_hours": total_effort_hours,
        "work_packages_missing_effort": work_packages_missing_effort,
        "work_packages": work_packages,
    }
