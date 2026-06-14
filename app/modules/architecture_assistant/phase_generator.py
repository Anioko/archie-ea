"""Phase-Level Architecture Generator — per-TOGAF-phase generation with dry-run preview.

Replaces the monolithic "Generate Architecture" approach with controlled,
phase-by-phase generation using the inference engine's diagnose() for preview
and repair() for execution.
"""

import logging

from app import db

logger = logging.getLogger(__name__)

# TOGAF phase → source element types → target element types
PHASE_CONFIG = {
    "A": {
        "name": "Motivation",
        "source_types": ["Goal", "Driver", "Stakeholder"],
        "target_types": ["Outcome", "Requirement", "Constraint", "Principle", "Assessment"],
    },
    "B": {
        "name": "Business Architecture",
        "source_types": ["Capability", "Goal"],
        "target_types": ["BusinessProcess", "BusinessRole", "BusinessObject", "BusinessService"],
    },
    "C": {
        "name": "Application Architecture",
        "source_types": ["BusinessProcess", "BusinessService", "Capability"],
        "target_types": ["ApplicationService", "ApplicationComponent", "DataObject", "ApplicationFunction"],
    },
    "D": {
        "name": "Technology Architecture",
        "source_types": ["ApplicationComponent", "ApplicationService"],
        "target_types": ["TechnologyService", "Node", "SystemSoftware", "Artifact", "CommunicationNetwork"],
    },
    "F": {
        "name": "Migration Planning",
        "source_types": ["Gap"],
        "target_types": ["WorkPackage", "Deliverable", "Plateau"],
    },
}


class PhaseGeneratorService:
    """Generates architecture elements per TOGAF phase using the inference engine."""

    def generate_phase(self, solution_id, phase, dry_run=True):
        """Generate missing elements for a specific TOGAF phase.

        Args:
            solution_id: solution to generate for
            phase: TOGAF phase letter (A, B, C, D, F)
            dry_run: if True, preview what would be created without persisting

        Returns:
            dict with source_elements, would_create (dry_run) or created elements
        """
        phase = phase.upper()
        if phase not in PHASE_CONFIG:
            return {"error": f"Invalid phase: {phase}. Valid: {list(PHASE_CONFIG.keys())}"}

        config = PHASE_CONFIG[phase]

        from app.modules.architecture_assistant.journey_graph import JourneyGraph
        graph = JourneyGraph.resume_for_solution(solution_id)

        # Find source elements for this phase
        source_elements = []
        for src_type in config["source_types"]:
            nodes = graph.facade.find_nodes(element_type=src_type, filters={})
            # Filter to only elements in THIS journey's architecture
            for node in nodes:
                if node.model and getattr(node.model, 'architecture_id', None) == graph.architecture_id:
                    source_elements.append(node)

        if not source_elements:
            return {
                "phase": phase,
                "phase_name": config["name"],
                "dry_run": dry_run,
                "source_elements": [],
                "would_create": [] if dry_run else None,
                "message": f"No {'/'.join(config['source_types'])} elements found. Complete earlier phases first.",
            }

        if dry_run:
            return self._dry_run(graph, source_elements, config, phase)
        else:
            return self._execute(graph, source_elements, config, phase, solution_id)

    def _dry_run(self, graph, source_elements, config, phase):
        """Preview what would be created without persisting."""
        missing_by_type = {}

        for node in source_elements:
            try:
                diag = graph.engine.diagnose(node.id)
                for chain_diag in diag.chain_diagnostics:
                    for missing_type in chain_diag.missing:
                        if missing_type in config["target_types"]:
                            missing_by_type.setdefault(missing_type, {
                                "type": missing_type,
                                "count": 0,
                                "source_elements": [],
                                "reason": f"{node.element_type}s without downstream {missing_type}",
                            })
                            missing_by_type[missing_type]["count"] += 1
                            if node.name not in missing_by_type[missing_type]["source_elements"]:
                                missing_by_type[missing_type]["source_elements"].append(node.name)
            except Exception as e:
                logger.warning("Diagnose failed for node %d: %s", node.id, e)

        would_create = list(missing_by_type.values())
        total_would_create = sum(item["count"] for item in would_create)

        # Estimate completeness after generation
        current_total = len(graph.facade.find_nodes(element_type=None, filters={}))
        estimated_after = round(
            (current_total + total_would_create) /
            max(current_total + total_would_create, 1) * 100
        ) if total_would_create > 0 else 100

        return {
            "phase": phase,
            "phase_name": config["name"],
            "dry_run": True,
            "source_elements": [
                {"id": n.id, "type": n.element_type, "name": n.name}
                for n in source_elements
            ],
            "would_create": would_create,
            "total_would_create": total_would_create,
            "estimated_completeness_after": estimated_after,
        }

    def _execute(self, graph, source_elements, config, phase, solution_id):
        """Execute generation — create missing elements via inference engine repair."""
        total_elements = 0
        total_rels = 0
        errors = []

        for node in source_elements:
            try:
                result = graph.engine.repair(node.id, dry_run=False)
                total_elements += len(result.elements_created)
                total_rels += len(result.relationships_created)
            except Exception as e:
                logger.warning("Repair failed for node %d (%s): %s", node.id, node.name, e)
                errors.append(f"{node.name}: {str(e)}")

        if total_elements > 0:
            db.session.commit()

        # Get updated elements for this phase's target types
        created_elements = []
        for target_type in config["target_types"]:
            nodes = graph.facade.find_nodes(element_type=target_type, filters={})
            for node in nodes:
                if node.model and getattr(node.model, 'architecture_id', None) == graph.architecture_id:
                    created_elements.append({
                        "id": node.id,
                        "type": node.element_type,
                        "name": node.name,
                        "description": getattr(node.model, 'description', '') or '',
                    })

        logger.info(
            "Phase %s executed: %d elements, %d relationships created for solution %d",
            phase, total_elements, total_rels, solution_id,
        )

        return {
            "phase": phase,
            "phase_name": config["name"],
            "dry_run": False,
            "elements_created": total_elements,
            "relationships_created": total_rels,
            "created_elements": created_elements,
            "errors": errors,
        }

    def get_phase_status(self, solution_id):
        """Get completeness status for all phases.

        Returns dict with per-phase element counts and completeness.
        """
        from app.modules.architecture_assistant.journey_graph import JourneyGraph
        graph = JourneyGraph.resume_for_solution(solution_id)

        status = {}
        for phase_key, config in PHASE_CONFIG.items():
            source_count = 0
            target_count = 0

            for src_type in config["source_types"]:
                nodes = graph.facade.find_nodes(element_type=src_type, filters={})
                source_count += sum(
                    1 for n in nodes
                    if n.model and getattr(n.model, 'architecture_id', None) == graph.architecture_id
                )

            for tgt_type in config["target_types"]:
                nodes = graph.facade.find_nodes(element_type=tgt_type, filters={})
                target_count += sum(
                    1 for n in nodes
                    if n.model and getattr(n.model, 'architecture_id', None) == graph.architecture_id
                )

            status[phase_key] = {
                "name": config["name"],
                "source_count": source_count,
                "target_count": target_count,
                "has_sources": source_count > 0,
                "completeness": "complete" if target_count > 0 and source_count > 0
                    else "ready" if source_count > 0
                    else "blocked",
            }

        return status
