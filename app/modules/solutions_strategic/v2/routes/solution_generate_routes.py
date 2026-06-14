"""Solution Generate-Phase API (BPP-014).

POST /api/solutions/<id>/generate-phase
Runs the ArchiMate Inference Engine to fill gaps for a given TOGAF ADM phase.
"""
import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app import db
from app.models.solution_models import Solution
from app.models.solution_archimate_element import SolutionArchiMateElement
from app.modules.architecture.services.inference_engine_service import ArchiMateInferenceEngine
from app.utils.element_provenance import tag_provenance

logger = logging.getLogger(__name__)

solution_generate_bp = Blueprint(
    "solution_generate", __name__, url_prefix="/api/solutions"
)

# Phase → ArchiMate element types that seed inference for that phase
PHASE_TYPE_MAP = {
    "A": {
        "source_types": ["Goal", "goal", "Driver", "driver", "Stakeholder", "stakeholder"],
        "label": "Vision",
    },
    "B": {
        "source_types": ["Capability", "capability"],
        "label": "Business Architecture",
    },
    "C": {
        "source_types": ["BusinessProcess", "business_process"],
        "label": "Information Systems",
    },
    "D": {
        "source_types": ["ApplicationComponent", "application_component"],
        "label": "Technology Architecture",
    },
    "E": {
        "source_types": ["Gap", "gap", "WorkPackage", "work_package", "Deliverable", "deliverable"],
        "label": "Opportunities & Solutions",
        "viewpoint": "implementation_migration",
        "element_types": ["Gap", "WorkPackage", "Deliverable"],
        "relationship_rules": [("Gap", "WorkPackage", "Triggers"), ("WorkPackage", "Deliverable", "Realizes")],
        "required_elements": ["Gap", "WorkPackage", "Deliverable"],
    },
    "F": {
        "source_types": ["Gap", "gap", "Plateau", "plateau", "WorkPackage", "work_package"],
        "label": "Migration Planning",
        "viewpoint": "implementation_migration",
        "element_types": ["Plateau", "WorkPackage"],
        "relationship_rules": [("Plateau", "WorkPackage", "Aggregation"), ("WorkPackage", "WorkPackage", "Triggers")],
        "required_elements": ["Plateau", "WorkPackage"],
    },
    "G": {
        "source_types": ["Goal", "goal", "Requirement", "requirement", "Principle", "principle", "Constraint", "constraint"],
        "label": "Implementation Governance",
        "viewpoint": "goal_realization",
        "element_types": ["Goal", "Requirement", "Principle", "Constraint"],
        "relationship_rules": [("Goal", "Requirement", "Realizes"), ("Requirement", "Principle", "Association")],
        "required_elements": ["Goal", "Requirement", "Principle", "Constraint"],
    },
    "R": {
        "source_types": ["Assessment", "assessment", "Stakeholder", "stakeholder", "Driver", "driver"],
        "label": "Requirements Management",
        "viewpoint": "stakeholder",
        "element_types": ["Assessment"],
        "relationship_rules": [("Assessment", "Stakeholder", "Association"), ("Assessment", "Driver", "Association")],
        "required_elements": ["Assessment"],
    },
    "H": {
        "source_types": ["Outcome", "outcome", "Goal", "goal", "Deliverable", "deliverable"],
        "label": "Architecture Change Management",
        "viewpoint": "outcome_realization",
        "element_types": ["Outcome", "Goal", "Deliverable"],
        "relationship_rules": [("Outcome", "Goal", "Realizes"), ("Goal", "Deliverable", "Realizes")],
        "required_elements": ["Outcome", "Goal", "Deliverable"],
    },
    "T": {
        "source_types": [],
        "label": "Traceability",
        "viewpoint": "layered",
        "element_types": [],
        "relationship_rules": [],
        "required_elements": [],
        "trace_chain_repair": True,
    },
}


def _link_element_to_solution(solution_id: int, element_id: int, element_type: str = "", layer: str = "") -> bool:
    """Link an element to a solution with role='ai_derived'. Returns True if created.

    Production schema requires layer_type (NOT NULL) and element_table (NOT NULL).
    Idempotent: skips if element_id is already linked to this solution.
    """
    # Idempotency: check by element_id
    existing = SolutionArchiMateElement.query.filter_by(
        solution_id=solution_id, element_id=element_id
    ).first()
    if existing:
        return False

    # Look up actual element from ArchiMate catalog
    layer_type = (layer or "application").lower()
    element_name = element_type or ""
    real_elem = None
    try:
        from app.models.archimate_core import ArchiMateElement
        real_elem = ArchiMateElement.query.get(element_id)
    except Exception as e:
        logger.debug("Could not look up element %d: %s", element_id, e)

    if real_elem and real_elem.name:
        element_name = real_elem.name
        if not layer:
            layer_type = (real_elem.layer or "application").lower()
        if not element_type:
            element_type = real_elem.element_type or ""

        # Idempotency: check by element_name + layer_type (catches re-created elements with new IDs)
        name_match = SolutionArchiMateElement.query.filter_by(
            solution_id=solution_id, element_name=element_name, layer_type=layer_type
        ).first()
        if name_match:
            return False

    junction = SolutionArchiMateElement(
        solution_id=solution_id,
        element_id=element_id,
        element_role="ai_derived",
    )
    # Set production-required fields if they exist on the model
    if hasattr(junction, "layer_type"):
        junction.layer_type = layer_type
    if hasattr(junction, "element_table"):
        junction.element_table = "archimate_elements"
    if hasattr(junction, "element_name"):
        junction.element_name = element_name
    if hasattr(junction, "is_new_element"):
        junction.is_new_element = True

    db.session.add(junction)
    return True


@solution_generate_bp.route(
    "/<int:solution_id>/generate-phase", methods=["POST"]
)
@login_required
def generate_phase(solution_id):
    """Generate missing ArchiMate elements for a TOGAF ADM phase.

    Request body::

        {"phase": "A", "dry_run": true}

    Response::

        {
          "phase": "A",
          "label": "Vision",
          "source_elements": 3,
          "preview": [...],            # dry_run only
          "created_count": 5,          # non-dry_run only
          "linked_count": 4,           # non-dry_run only
          "completeness_before": 0.3,
          "completeness_after": 0.85,
          "errors": []
        }
    """
    solution = Solution.query.get(solution_id)
    if not solution:
        return jsonify({"error": "Solution not found"}), 404

    body = request.get_json(silent=True) or {}
    phase = body.get("phase", "").upper()
    dry_run = body.get("dry_run", True)

    if phase not in PHASE_TYPE_MAP:
        valid = ", ".join(sorted(PHASE_TYPE_MAP.keys()))
        return jsonify({"error": f"Invalid phase '{phase}'. Valid: {valid}"}), 400

    phase_cfg = PHASE_TYPE_MAP[phase]
    source_types = phase_cfg["source_types"]

    try:
        engine = ArchiMateInferenceEngine(0)

        # Find source elements linked to this solution that match the phase type filter
        junctions = SolutionArchiMateElement.query.filter_by(
            solution_id=solution_id
        ).all()

        source_elements = []
        for junc in junctions:
            node = engine.graph.get_node(junc.element_id)
            if node and node.element_type in source_types:
                source_elements.append(node)

        # Phase T (traceability) operates on ALL linked elements, not filtered by type
        is_trace_phase = phase_cfg.get("trace_chain_repair", False)

        if not source_elements and not is_trace_phase:
            return jsonify({
                "phase": phase,
                "label": phase_cfg["label"],
                "source_elements": 0,
                "message": f"No {phase_cfg['label']} elements linked to this solution.",
                "preview": [] if dry_run else None,
                "created_count": 0,
                "linked_count": 0,
                "completeness_before": 1.0,
                "completeness_after": 1.0,
                "errors": [],
            }), 200

        # Gather completeness_before scores
        completeness_scores_before = []
        for node in source_elements:
            diag = engine.diagnose(node.id)
            completeness_scores_before.append(diag.completeness)
        completeness_before = (
            sum(completeness_scores_before) / len(completeness_scores_before)
            if completeness_scores_before else 1.0
        )

        created_ids = set()
        errors = []

        if dry_run:
            # Preview mode: collect what would be created without persisting
            preview = []
            for node in source_elements:
                # Check downstream gaps
                broken = engine.detect_broken_chain(node)
                for gap in broken:
                    key = (gap["to"], gap.get("from_id", node.id))
                    if key not in created_ids:
                        created_ids.add(key)
                        preview.append({
                            "action": "create_downstream",
                            "from_element": node.element_type,
                            "from_id": node.id,
                            "missing_type": gap["to"],
                            "relationship": gap["relationship"],
                        })
                # Check upstream gaps
                upstream_types = engine.rules.allowed_upstream_types(node.element_type)
                upstream_nodes = engine.graph.get_neighbors(node.id, direction="in")
                upstream_existing = {n.element_type for n in upstream_nodes}
                for ut in upstream_types:
                    if ut not in upstream_existing:
                        key = (ut, node.id)
                        if key not in created_ids:
                            created_ids.add(key)
                            preview.append({
                                "action": "create_upstream",
                                "for_element": node.element_type,
                                "for_id": node.id,
                                "missing_type": ut,
                            })

            return jsonify({
                "phase": phase,
                "label": phase_cfg["label"],
                "source_elements": len(source_elements),
                "preview": preview,
                "completeness_before": round(completeness_before, 3),
                "completeness_after": None,
                "errors": errors,
            }), 200

        # --- Execution mode ---
        created_count = 0
        linked_count = 0
        provenance_records = []

        # Phase T is special: trace chain repair across all linked elements
        if phase_cfg.get("trace_chain_repair"):
            try:
                for junc in junctions:
                    node = engine.graph.get_node(junc.element_id)
                    if node:
                        repair_result = engine.repair(node.id, dry_run=False)
                        for created_node in repair_result.elements_created:
                            elem_id = created_node.id if hasattr(created_node, "id") else created_node
                            etype = getattr(created_node, "element_type", "")
                            elayer = getattr(created_node, "layer", "")
                            if elem_id not in created_ids:
                                created_ids.add(elem_id)
                                created_count += 1
                                if _link_element_to_solution(solution_id, elem_id, etype, elayer):
                                    linked_count += 1
                                provenance_records.append(
                                    tag_provenance({"id": elem_id, "type": etype}, phase)
                                )
                        errors.extend(repair_result.errors)
            except Exception as e:
                logger.warning("Trace chain repair failed: %s", e)
                errors.append(f"Trace chain repair failed: {e}")
        else:
            for node in source_elements:
                # Downstream repair
                try:
                    repair_result = engine.repair(node.id, dry_run=False)
                    for created_node in repair_result.elements_created:
                        elem_id = created_node.id if hasattr(created_node, "id") else created_node
                        etype = getattr(created_node, "element_type", "")
                        elayer = getattr(created_node, "layer", "")
                        if elem_id not in created_ids:
                            created_ids.add(elem_id)
                            created_count += 1
                            if _link_element_to_solution(solution_id, elem_id, etype, elayer):
                                linked_count += 1
                            provenance_records.append(
                                tag_provenance({"id": elem_id, "type": etype}, phase)
                            )
                    errors.extend(repair_result.errors)
                except Exception as e:
                    logger.warning("Repair failed for element %s: %s", node.id, e)
                    errors.append(f"Repair failed for {node.element_type} ({node.id}): {e}")

                # Upstream inference
                try:
                    upstream_types = engine.rules.allowed_upstream_types(node.element_type)
                    upstream_nodes = engine.graph.get_neighbors(node.id, direction="in")
                    upstream_existing = {n.element_type for n in upstream_nodes}
                    for ut in upstream_types:
                        if ut not in upstream_existing:
                            new_node = engine._infer_missing_downstream(node, [ut])
                            if new_node:
                                elem_id = new_node.id if hasattr(new_node, "id") else new_node
                                if elem_id not in created_ids:
                                    created_ids.add(elem_id)
                                    created_count += 1
                                    etype = getattr(new_node, "element_type", ut)
                                    elayer = getattr(new_node, "layer", "")
                                    if _link_element_to_solution(solution_id, elem_id, etype, elayer):
                                        linked_count += 1
                                    provenance_records.append(
                                        tag_provenance({"id": elem_id, "type": etype}, phase)
                                    )
                                # Create relationship from new upstream to current node
                                rel_type = engine.rules.canonical_rel_type(ut, node.element_type)
                                engine.graph.get_or_create_relationship(
                                    new_node.id, node.id, rel_type,
                                    metadata={"source_tag": "phase_generate", "confidence": 0.8}
                                )
                except Exception as e:
                    logger.warning("Upstream inference failed for element %s: %s", node.id, e)
                    errors.append(f"Upstream inference failed for {node.element_type} ({node.id}): {e}")

        db.session.commit()

        # Compute completeness_after
        completeness_scores_after = []
        for node in source_elements:
            diag = engine.diagnose(node.id)
            completeness_scores_after.append(diag.completeness)
        completeness_after = (
            sum(completeness_scores_after) / len(completeness_scores_after)
            if completeness_scores_after else 1.0
        )

        return jsonify({
            "phase": phase,
            "label": phase_cfg["label"],
            "source_elements": len(source_elements),
            "created_count": created_count,
            "linked_count": linked_count,
            "completeness_before": round(completeness_before, 3),
            "completeness_after": round(completeness_after, 3),
            "errors": errors,
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception("generate_phase failed for solution %s phase %s", solution_id, phase)
        return jsonify({"error": f"Generation failed: {e}"}), 500


@solution_generate_bp.route(
    "/<int:solution_id>/bootstrap-architecture", methods=["POST"]
)
@login_required
def bootstrap_architecture(solution_id):
    """Bootstrap a full architecture chain from the solution's description.

    Solves the cold start problem: new solutions have no linked elements,
    so generate-phase has nothing to work with. This endpoint:
    1. Reads the solution's name + description
    2. Creates a Goal element from the solution name
    3. Runs the inference engine to generate the full chain
    4. Links all created elements to the solution

    Request: {"dry_run": true}
    """
    solution = Solution.query.get(solution_id)
    if not solution:
        return jsonify({"error": "Solution not found"}), 404

    body = request.get_json(silent=True) or {}
    dry_run = body.get("dry_run", True)

    # Check if solution already has linked elements
    existing_links = SolutionArchiMateElement.query.filter_by(
        solution_id=solution_id
    ).count()

    # Build the seed text from solution fields
    seed_text = solution.name or ""
    if solution.description:
        seed_text = solution.description[:200]

    if not seed_text.strip():
        return jsonify({
            "error": "Solution has no name or description to bootstrap from.",
        }), 400

    try:
        engine = ArchiMateInferenceEngine(0)

        # Create the root Goal from solution name
        goal_name = solution.name
        if len(goal_name) > 95:
            goal_name = goal_name[:92] + "..."

        if dry_run:
            # Preview: show what would be created
            # Estimate the chain from a Goal
            preview = [{"type": "Goal", "name": goal_name, "direction": "root", "source": "solution"}]
            downstream_types = []
            current_type = "Goal"
            for _ in range(10):  # max chain depth
                required = engine.rules.required_downstream(current_type)
                if not required:
                    break
                next_type = required[0][0]
                root_name = engine.rules._extract_root_name(goal_name)
                preview.append({
                    "type": next_type,
                    "name": "%s: %s" % (next_type, root_name[:60]),
                    "direction": "downstream",
                    "source": "rule",
                })
                current_type = next_type

            # Also show upstream from Goal
            for ut in engine.rules.allowed_upstream_types("Goal"):
                root_name = engine.rules._extract_root_name(goal_name)
                preview.append({
                    "type": ut,
                    "name": "%s: %s" % (ut, root_name[:60]),
                    "direction": "upstream",
                    "source": "rule",
                })

            return jsonify({
                "dry_run": True,
                "solution_name": solution.name,
                "existing_links": existing_links,
                "would_create": preview,
                "count": len(preview),
            })

        # --- Execution mode ---
        # 1. Create the root Goal
        goal_node = engine.graph.get_or_create_node(
            "Goal",
            {"name": goal_name},
            {"description": seed_text},
        )
        engine._log_provenance(goal_node, "created", "user")

        # 2. Generate the full chain from the Goal (with LLM refinement enabled)
        engine.context.skip_semantic_pass = False
        result = engine.generate_chain(goal_node.id, direction="down")

        # 3. Link everything to the solution
        created_ids = set()
        linked_count = 0

        # Link the root goal
        if _link_element_to_solution(solution_id, goal_node.id, goal_node.element_type, goal_node.layer):
            linked_count += 1
        created_ids.add(goal_node.id)

        # Link all chain elements
        for node in result.chain:
            if node.id not in created_ids:
                created_ids.add(node.id)
                if _link_element_to_solution(solution_id, node.id, node.element_type, node.layer):
                    linked_count += 1

        # Link elements_created (from repair operations during chain generation)
        for node in result.elements_created:
            elem_id = node.id if hasattr(node, "id") else node
            etype = getattr(node, "element_type", "")
            elayer = getattr(node, "layer", "")
            if elem_id not in created_ids:
                created_ids.add(elem_id)
                if _link_element_to_solution(solution_id, elem_id, etype, elayer):
                    linked_count += 1

        # 4. Also create upstream elements (Driver, Stakeholder)
        upstream_types = engine.rules.allowed_upstream_types("Goal")
        for ut in upstream_types:
            existing_up = engine.graph.get_neighbors(goal_node.id, direction="in")
            if not any(n.element_type == ut for n in existing_up):
                new_node = engine._infer_missing_downstream(goal_node, [ut])
                if new_node and new_node.id not in created_ids:
                    created_ids.add(new_node.id)
                    if _link_element_to_solution(solution_id, new_node.id, getattr(new_node, "element_type", ut), getattr(new_node, "layer", "")):
                        linked_count += 1
                    rel_type = engine.rules.canonical_rel_type(ut, "Goal")
                    engine.graph.get_or_create_relationship(
                        new_node.id, goal_node.id, rel_type,
                        metadata={"source_tag": "bootstrap", "confidence": 0.9}
                    )

        db.session.commit()

        return jsonify({
            "dry_run": False,
            "solution_name": solution.name,
            "goal_id": goal_node.id,
            "goal_name": goal_name,
            "chain_length": len(result.chain),
            "elements_created": len(result.elements_created),
            "linked_to_solution": linked_count,
            "errors": result.errors,
        })

    except Exception as e:
        db.session.rollback()
        logger.exception("bootstrap_architecture failed for solution %s", solution_id)
        return jsonify({"error": f"Bootstrap failed: {e}"}), 500


@solution_generate_bp.route(
    "/<int:solution_id>/smart-defaults", methods=["POST"]
)
@login_required
def smart_defaults(solution_id):
    """NON-LLM smart population from real platform data.

    Queries capabilities, applications, vendor products, and generates
    template drivers/goals/constraints based on solution metadata.

    Request: {"dry_run": true}  (default: preview only)
             {"dry_run": false} (apply defaults — creates real DB records)
    """
    from app.modules.solutions_strategic.v2.services.smart_defaults_service import (
        generate_smart_defaults,
        apply_smart_defaults,
    )

    solution = Solution.query.get(solution_id)
    if not solution:
        return jsonify({"error": "Solution not found"}), 404

    body = request.get_json(silent=True) or {}
    dry_run = body.get("dry_run", True)
    # If client sends selected items, filter defaults to only those
    selected = body.get("selected")

    try:
        defaults = generate_smart_defaults(solution)

        if dry_run:
            return jsonify({
                "dry_run": True,
                "solution_name": solution.name,
                "defaults": defaults,
            })

        # Fix 2: Filter defaults to only selected items if provided
        if selected and isinstance(selected, dict):
            for key in ["capabilities", "applications", "vendor_products", "drivers", "goals", "constraints"]:
                if key in selected:
                    selected_ids = set(selected[key])
                    if key in ("drivers", "goals", "constraints"):
                        # These use name as key since they might not have unique ids in preview
                        defaults[key] = [item for item in defaults.get(key, []) if item.get("name") in selected_ids]
                    else:
                        defaults[key] = [item for item in defaults.get(key, []) if item.get("id") in selected_ids]

        # Apply defaults — create real records
        result = apply_smart_defaults(solution, defaults)
        db.session.commit()

        created = result["counts"]
        created_ids = result["created_ids"]

        return jsonify({
            "dry_run": False,
            "solution_name": solution.name,
            "created": created,
            "created_ids": created_ids,
            "summary": defaults.get("summary", ""),
            "total": sum(created.values()),
        })

    except Exception as e:
        db.session.rollback()
        logger.exception("smart_defaults failed for solution %s", solution_id)
        return jsonify({"error": f"Smart defaults failed: {e}"}), 500


@solution_generate_bp.route(
    "/<int:solution_id>/revert-smart-defaults", methods=["POST"]
)
@login_required
def revert_smart_defaults_route(solution_id):
    """Revert the last smart defaults apply.

    Request: {"created_ids": {...}}  — the created_ids from the apply response
    """
    from app.modules.solutions_strategic.v2.services.smart_defaults_service import (
        revert_smart_defaults,
    )

    solution = Solution.query.get(solution_id)
    if not solution:
        return jsonify({"error": "Solution not found"}), 404

    body = request.get_json(silent=True) or {}
    created_ids = body.get("created_ids")
    if not created_ids:
        return jsonify({"error": "No created_ids provided"}), 400

    try:
        reverted = revert_smart_defaults(solution, created_ids)
        db.session.commit()
        return jsonify({
            "success": True,
            "reverted": reverted,
            "total": sum(reverted.values()),
        })
    except Exception as e:
        db.session.rollback()
        logger.exception("revert_smart_defaults failed for solution %s", solution_id)
        return jsonify({"error": f"Revert failed: {e}"}), 500


@solution_generate_bp.route(
    "/<int:solution_id>/refine-names", methods=["POST"]
)
@login_required
def refine_names(solution_id):
    """Refine auto-generated element names using LLM.

    Runs Pass 3 (semantic refinement) on all ArchiMate elements linked
    to this solution. Returns before/after name pairs.

    Request: {"dry_run": true}
    Response: {"refined": [{"id": 1, "type": "Goal", "before": "...", "after": "..."}], ...}
    """
    from app.models.archimate_core import ArchiMateElement
    from app.modules.architecture.services.inference_providers import PROVIDER_REGISTRY, _llm_refine_element

    solution = Solution.query.get(solution_id)
    if not solution:
        return jsonify({"error": "Solution not found"}), 404

    body = request.get_json(silent=True) or {}
    dry_run = body.get("dry_run", True)

    try:
        junctions = SolutionArchiMateElement.query.filter_by(
            solution_id=solution_id
        ).all()

        if not junctions:
            return jsonify({
                "refined": [],
                "total": 0,
                "message": "No elements linked to this solution.",
            })

        results = []
        for junc in junctions:
            elem = ArchiMateElement.query.get(junc.element_id)
            if not elem:
                continue

            etype = elem.type or ""
            old_name = elem.name or ""
            old_desc = getattr(elem, "description", "") or ""

            # Skip elements that already have good names (no "for" pattern)
            if " for " not in old_name and ": " not in old_name:
                continue

            refined = _llm_refine_element(
                etype, old_name, old_desc,
                layer_hint=getattr(elem, "layer", "") or "",
            )

            if refined and refined["name"] != old_name:
                entry = {
                    "id": elem.id,
                    "type": etype,
                    "before": old_name,
                    "after": refined["name"],
                    "description": refined.get("description", ""),
                }
                results.append(entry)

                if not dry_run:
                    elem.name = refined["name"]
                    if refined.get("description") and hasattr(elem, "description"):
                        elem.description = refined["description"]

        if not dry_run:
            db.session.commit()

        return jsonify({
            "dry_run": dry_run,
            "refined": results,
            "total": len(results),
            "solution_name": solution.name,
        })

    except Exception as e:
        db.session.rollback()
        logger.exception("refine_names failed for solution %s", solution_id)
        return jsonify({"error": f"Refinement failed: {e}"}), 500
