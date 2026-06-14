"""
Solution → ArchiMate Repository Sync Service

Auto-creates ArchiMate domain model elements from Solution analysis data
(drivers, goals, requirements, constraints, recommendations, risks, plateaus)
and links them via SolutionArchiMateElement junctions.

Used by solution_design_routes.py after solution creation/edit.
"""

import logging

from app import db
from app.models.archimate_core import ArchiMateElement
from app.models.implementation_migration import Plateau as ArchPlateau
from app.models.implementation_migration import WorkPackage
from app.models.models import ConstraintElement, Requirement
from app.models.motivation import Assessment, Driver, Goal
from app.models.strategy_layer import CourseOfAction
from app.models.solution_models import Solution, SolutionArchiMateElement

logger = logging.getLogger(__name__)


# Maps (source_model_name) → (target_model, target_table, layer_type, element_type)
SYNC_MAP = {
    "SolutionDriver": {
        "model": Driver,
        "table": "drivers",
        "layer": "motivation",
        "element_type": "Driver",
    },
    "SolutionGoal": {
        "model": Goal,
        "table": "goals",
        "layer": "motivation",
        "element_type": "Goal",
    },
    "SolutionRequirement": {
        "model": Requirement,
        "table": "requirements",
        "layer": "motivation",
        "element_type": "Requirement",
    },
    "SolutionConstraint": {
        "model": ConstraintElement,
        "table": "constraints",
        "layer": "motivation",
        "element_type": "Constraint",
    },
    "SolutionRecommendation": {
        "model": CourseOfAction,
        "table": "courses_of_action",
        "layer": "strategy",
        "element_type": "CourseOfAction",
    },
    "SolutionRisk": {
        "model": Assessment,
        "table": "assessments",
        "layer": "motivation",
        "element_type": "Assessment",
    },
    "SolutionPlateau": {
        "model": ArchPlateau,
        "table": "plateaus",
        "layer": "implementation",
        "element_type": "Plateau",
    },
}


def _map_driver_fields(source):
    """Map SolutionDriver fields to ArchiMate Driver fields."""
    driver_type = None
    if hasattr(source, "driver_type") and source.driver_type:
        dt = source.driver_type
        driver_type = dt.value if hasattr(dt, "value") else str(dt)
    return {
        "name": source.name,
        "description": source.description or f"Driver: {source.name}",
        "driver_type": driver_type,
        "source": "solution_sync",
    }


def _map_goal_fields(source):
    """Map SolutionGoal fields to ArchiMate Goal fields."""
    return {
        "name": source.name,
        "description": source.description or f"Goal: {source.name}",
        "goal_type": "strategic",
    }


def _map_requirement_fields(source):
    """Map SolutionRequirement fields to ArchiMate Requirement fields."""
    req_type = None
    if hasattr(source, "requirement_type") and source.requirement_type:
        rt = source.requirement_type
        req_type = rt.value if hasattr(rt, "value") else str(rt)
    return {
        "title": source.name,
        "description": source.description or f"Requirement: {source.name}",
        "type": req_type,
        "priority": str(source.priority) if source.priority else None,
    }


def _map_constraint_fields(source):
    """Map SolutionConstraint fields to ArchiMate ConstraintElement fields."""
    ctype = None
    if hasattr(source, "constraint_type") and source.constraint_type:
        ct = source.constraint_type
        ctype = ct.value if hasattr(ct, "value") else str(ct)
    return {
        "name": source.name,
        "description": source.description or f"Constraint: {source.name}",
        "constraint_type": ctype,
    }


def _map_recommendation_fields(source):
    """Map SolutionRecommendation fields to ArchiMate CourseOfAction fields."""
    name = f"Recommendation: {source.option_type.value if hasattr(source.option_type, 'value') else source.option_type}"
    if hasattr(source, "justification") and source.justification:
        name = source.justification[:200]
    return {
        "name": name,
        "description": source.justification or f"Recommendation (rank {source.rank})",
        "action_type": "initiative",
    }


def _map_risk_fields(source):
    """Map SolutionRisk fields to ArchiMate Assessment fields."""
    return {
        "name": f"Risk: {source.risk_description[:200]}" if source.risk_description else "Risk Assessment",
        "description": source.risk_description or "Risk assessment from solution analysis",
        "assessment_type": "Risk",
        "result_score": source.impact or source.probability,
    }


def _map_plateau_fields(source):
    """Map SolutionPlateau fields to ArchiMate Plateau fields."""
    return {
        "name": source.name,
        "description": source.description or f"Plateau: {source.name}",
        "sequence_order": source.order if hasattr(source, "order") else None,
        "target_date": source.target_date if hasattr(source, "target_date") else None,
    }


# Dispatcher: source_type → field mapper
_FIELD_MAPPERS = {
    "SolutionDriver": _map_driver_fields,
    "SolutionGoal": _map_goal_fields,
    "SolutionRequirement": _map_requirement_fields,
    "SolutionConstraint": _map_constraint_fields,
    "SolutionRecommendation": _map_recommendation_fields,
    "SolutionRisk": _map_risk_fields,
    "SolutionPlateau": _map_plateau_fields,
}


def sync_solution_element(solution_id, source_instance, source_type):
    """
    Sync a single solution analysis element to its ArchiMate domain counterpart.

    1. Maps source fields to ArchiMate domain model fields.
    2. Checks for existing domain record by name (avoids dupes).
    3. Creates domain model record + ArchiMateElement record.
    4. Creates SolutionArchiMateElement junction.
    5. Returns the created/found domain element, or None on error.
    """
    if source_type not in SYNC_MAP:
        logger.warning(f"Unknown source_type: {source_type}")
        return None

    mapping = SYNC_MAP[source_type]
    target_model = mapping["model"]
    target_table = mapping["table"]
    layer = mapping["layer"]
    element_type = mapping["element_type"]

    mapper_fn = _FIELD_MAPPERS.get(source_type)
    if not mapper_fn:
        return None

    fields = mapper_fn(source_instance)
    element_name = fields.get("name") or fields.get("title") or "Unnamed"

    # Check for existing domain record by name to avoid duplicates
    name_col = "name" if hasattr(target_model, "name") else "title"
    existing = target_model.query.filter(
        getattr(target_model, name_col) == element_name
    ).first()

    if existing:
        domain_record = existing
    else:
        # Create new domain model record
        # Filter fields to only those the model accepts
        valid_fields = {}
        for k, v in fields.items():
            if hasattr(target_model, k) and v is not None:
                valid_fields[k] = v
        domain_record = target_model(**valid_fields)
        db.session.add(domain_record)
        db.session.flush()

    # Ensure domain record has an archimate_element_id
    # (event listeners on some models auto-create this, but not all)
    if hasattr(domain_record, "archimate_element_id") and not domain_record.archimate_element_id:
        ae = ArchiMateElement(
            name=element_name,
            type=element_type,
            layer=layer.capitalize(),
            description=fields.get("description", f"{element_type}: {element_name}"),
        )
        db.session.add(ae)
        db.session.flush()
        domain_record.archimate_element_id = ae.id

    # Create SolutionArchiMateElement junction (if not already present)
    existing_junction = SolutionArchiMateElement.query.filter_by(
        solution_id=solution_id,
        layer_type=layer,
        element_table=target_table,
        element_id=domain_record.id,
    ).first()

    if not existing_junction:
        junction = SolutionArchiMateElement(
            solution_id=solution_id,
            layer_type=layer,
            element_table=target_table,
            element_id=domain_record.id,
            element_name=element_name,
            relationship_type="realizes",
            is_new_element=not bool(existing),
            notes=f"Auto-synced from {source_type}",
        )
        db.session.add(junction)

    return domain_record


def sync_all_for_solution(solution_id):
    """
    Sync all analysis data for a solution to ArchiMate repository elements.

    Loads the solution's analysis session and syncs:
    - SolutionDrivers → Driver
    - SolutionGoals → Goal
    - SolutionRequirements → Requirement
    - SolutionConstraints → ConstraintElement
    - SolutionRecommendations → CourseOfAction
    - SolutionRisks → Assessment
    - SolutionPlateaus → Plateau
    - SolutionCapabilityMappings → SolutionArchiMateElement for BusinessCapability

    Returns dict with counts of synced elements per type.
    """
    solution = Solution.query.get(solution_id)
    if not solution:
        logger.error(f"Solution {solution_id} not found")
        return {"error": "Solution not found"}

    counts = {}

    # Sync from analysis session (drivers, goals, requirements, constraints)
    if solution.analysis_session_id:
        from app.models.solution_architect_models import (
            SolutionAnalysisSession,
            SolutionConstraint,
            SolutionDriver,
            SolutionGoal,
            SolutionPrinciple,
            SolutionRecommendation,
            SolutionRequirement,
        )

        session_record = SolutionAnalysisSession.query.get(solution.analysis_session_id)
        if session_record and session_record.problem_definition:
            problem = session_record.problem_definition

            # Drivers
            drivers = SolutionDriver.query.filter_by(problem_id=problem.id).all()
            for d in drivers:
                sync_solution_element(solution_id, d, "SolutionDriver")
            counts["drivers"] = len(drivers)

            # Goals
            goals = SolutionGoal.query.filter_by(problem_id=problem.id).all()
            for g in goals:
                sync_solution_element(solution_id, g, "SolutionGoal")
            counts["goals"] = len(goals)

            # Requirements
            requirements = SolutionRequirement.query.filter_by(problem_id=problem.id).all()
            for r in requirements:
                sync_solution_element(solution_id, r, "SolutionRequirement")
            counts["requirements"] = len(requirements)

            # Constraints
            constraints = SolutionConstraint.query.filter_by(problem_id=problem.id).all()
            for c in constraints:
                sync_solution_element(solution_id, c, "SolutionConstraint")
            counts["constraints"] = len(constraints)

            # Recommendations
            recommendations = SolutionRecommendation.query.filter_by(
                session_id=session_record.id
            ).all()
            for rec in recommendations:
                sync_solution_element(solution_id, rec, "SolutionRecommendation")
            counts["recommendations"] = len(recommendations)

            # Capability mappings → link BusinessCapability via SolutionArchiMateElement
            from app.models.solution_models import SolutionCapabilityMapping

            cap_mappings = SolutionCapabilityMapping.query.filter_by(
                problem_id=problem.id
            ).all()
            for cm in cap_mappings:
                existing_junction = SolutionArchiMateElement.query.filter_by(
                    solution_id=solution_id,
                    layer_type="strategy",
                    element_table="business_capability",
                    element_id=cm.capability_id,
                ).first()
                if not existing_junction:
                    from app.models.business_capabilities import BusinessCapability

                    cap = BusinessCapability.query.get(cm.capability_id)
                    cap_name = cap.name if cap else f"Capability {cm.capability_id}"
                    junction = SolutionArchiMateElement(
                        solution_id=solution_id,
                        layer_type="strategy",
                        element_table="business_capability",
                        element_id=cm.capability_id,
                        element_name=cap_name,
                        relationship_type="serves",
                        is_new_element=False,
                        notes="Auto-synced from SolutionCapabilityMapping",
                    )
                    db.session.add(junction)
            counts["capabilities"] = len(cap_mappings)

    # Sync lifecycle elements (risks, plateaus)
    from app.models.solution_lifecycle_models import SolutionPlateau, SolutionRisk

    risks = SolutionRisk.query.filter_by(solution_id=solution_id).all()
    for risk in risks:
        sync_solution_element(solution_id, risk, "SolutionRisk")
    counts["risks"] = len(risks)

    plateaus = SolutionPlateau.query.filter_by(solution_id=solution_id).all()
    for p in plateaus:
        sync_solution_element(solution_id, p, "SolutionPlateau")
    counts["plateaus"] = len(plateaus)

    # Remove orphaned junctions (element no longer exists in source)
    _cleanup_orphaned_junctions(solution_id)

    db.session.flush()
    logger.info(f"Synced ArchiMate elements for solution {solution_id}: {counts}")
    return counts


def sync_work_packages(solution_id):
    """
    Sync RoadmapWorkPackage records for a solution to ArchiMate WorkPackage records.

    Creates ArchiMate WorkPackage domain records and links them via
    SolutionArchiMateElement for end-to-end traceability.

    Returns count of synced work packages.
    """
    from app.models.roadmap_models import RoadmapWorkPackage

    rwps = RoadmapWorkPackage.query.filter_by(
        source_type="solution", source_id=solution_id
    ).all()

    count = 0
    for rwp in rwps:
        # Check for existing ArchiMate WorkPackage by name
        existing = WorkPackage.query.filter_by(name=rwp.name).first()
        if existing:
            wp = existing
        else:
            wp = WorkPackage(
                name=rwp.name,
                description=rwp.description or f"Work package for solution {solution_id}",
                status=rwp.status or "planned",
                priority=rwp.priority or "medium",
                start_date=rwp.start_date.date() if rwp.start_date else None,
                target_date=rwp.end_date.date() if rwp.end_date else None,
                estimated_cost=rwp.estimated_cost,
                actual_cost=rwp.actual_cost,
                context="solution",
                context_id=solution_id,
            )
            db.session.add(wp)
            db.session.flush()

            # Create ArchiMateElement if needed
            if not wp.archimate_element_id:
                ae = ArchiMateElement(
                    name=rwp.name,
                    type="WorkPackage",
                    layer="Implementation",
                    description=rwp.description or f"Work package: {rwp.name}",
                )
                db.session.add(ae)
                db.session.flush()
                wp.archimate_element_id = ae.id

        # Create SolutionArchiMateElement junction
        existing_junction = SolutionArchiMateElement.query.filter_by(
            solution_id=solution_id,
            layer_type="implementation",
            element_table="work_packages",
            element_id=wp.id,
        ).first()

        if not existing_junction:
            junction = SolutionArchiMateElement(
                solution_id=solution_id,
                layer_type="implementation",
                element_table="work_packages",
                element_id=wp.id,
                element_name=wp.name,
                relationship_type="realizes",
                is_new_element=not bool(existing),
                notes="Auto-synced from RoadmapWorkPackage",
            )
            db.session.add(junction)
            count += 1

    db.session.flush()
    logger.info(f"Synced {count} work packages for solution {solution_id}")
    return count


def sync_phase_h_outcomes(solution_id):
    """
    Sync Phase H metrics to ArchiMate MotivationOutcome elements.

    For each SolutionMetric, creates/updates an ArchiMateElement of type Outcome
    with achievement percentage calculation.

    Returns list of outcome dicts with achievement data.
    """
    from app.models.archimate_motivation import MotivationOutcome
    from app.models.solution_lifecycle_models import SolutionMetric

    metrics = SolutionMetric.query.filter_by(solution_id=solution_id).all()
    outcomes = []

    for metric in metrics:
        # Calculate achievement percentage
        achievement_pct = None
        if metric.baseline_value is not None and metric.target_value is not None:
            if metric.actual_value is not None:
                try:
                    baseline = float(metric.baseline_value)
                    target = float(metric.target_value)
                    actual = float(metric.actual_value)
                    if target != baseline:
                        achievement_pct = ((actual - baseline) / (target - baseline)) * 100
                        achievement_pct = round(max(0, min(200, achievement_pct)), 1)
                except (ValueError, TypeError, ZeroDivisionError):
                    pass

        # Find or create MotivationOutcome
        outcome_name = f"Outcome: {metric.name}"
        existing = MotivationOutcome.query.filter_by(name=outcome_name).first()

        if existing:
            outcome = existing
            outcome.current_value = str(metric.actual_value) if metric.actual_value is not None else None
            outcome.achievement_level = str(achievement_pct) if achievement_pct is not None else None
            if achievement_pct is not None:
                if achievement_pct >= 100:
                    outcome.realization_status = "realized"
                elif achievement_pct >= 75:
                    outcome.realization_status = "on_track"
                elif achievement_pct >= 25:
                    outcome.realization_status = "in_progress"
                else:
                    outcome.realization_status = "not_started"
        else:
            outcome = MotivationOutcome(
                name=outcome_name,
                description=f"Value realization outcome for metric: {metric.name}",
                measurement_criteria=f"Unit: {metric.unit}" if metric.unit else None,
                target_value=str(metric.target_value) if metric.target_value is not None else None,
                current_value=str(metric.actual_value) if metric.actual_value is not None else None,
                baseline_value=str(metric.baseline_value) if metric.baseline_value is not None else None,
                measurement_unit=metric.unit,
                achievement_level=str(achievement_pct) if achievement_pct is not None else None,
                realization_status="not_started",
            )
            db.session.add(outcome)
            db.session.flush()

        # Create SolutionArchiMateElement junction
        existing_junction = SolutionArchiMateElement.query.filter_by(
            solution_id=solution_id,
            layer_type="motivation",
            element_table="motivation_outcomes",
            element_id=outcome.id,
        ).first()

        if not existing_junction:
            junction = SolutionArchiMateElement(
                solution_id=solution_id,
                layer_type="motivation",
                element_table="motivation_outcomes",
                element_id=outcome.id,
                element_name=outcome_name,
                relationship_type="realizes",
                is_new_element=not bool(existing),
                notes="Auto-synced from Phase H metric",
            )
            db.session.add(junction)

        outcomes.append({
            "metric_name": metric.name,
            "baseline": metric.baseline_value,
            "target": metric.target_value,
            "actual": metric.actual_value,
            "achievement_pct": achievement_pct,
            "status": metric.status,
            "outcome_id": outcome.id,
        })

    db.session.flush()
    logger.info(f"Synced {len(outcomes)} Phase H outcomes for solution {solution_id}")
    return outcomes


def _cleanup_orphaned_junctions(solution_id):
    """
    Remove SolutionArchiMateElement junctions whose source records no longer exist.
    Checks each junction's element_table + element_id against the actual table.
    """
    junctions = SolutionArchiMateElement.query.filter_by(solution_id=solution_id).all()

    # Build lookup of table → model
    table_model_map = {}
    for cfg in SYNC_MAP.values():
        table_model_map[cfg["table"]] = cfg["model"]
    # Add capability
    from app.models.business_capabilities import BusinessCapability
    table_model_map["business_capability"] = BusinessCapability

    orphans = []
    for j in junctions:
        model = table_model_map.get(j.element_table)
        if model:
            exists = model.query.get(j.element_id)
            if not exists:
                orphans.append(j)

    for orphan in orphans:
        db.session.delete(orphan)

    if orphans:
        logger.info(f"Removed {len(orphans)} orphaned junctions for solution {solution_id}")
