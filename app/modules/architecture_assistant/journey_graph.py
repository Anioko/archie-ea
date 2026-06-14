# mass-deletion-ok — intentional refactor: replaced hand-rolled BFS with ArchiMateInferenceEngine delegation
"""Journey-scoped graph wrapper over ArchiMateInferenceEngine.

Creates an ArchitectureModel per journey, manages solution→architecture link,
and delegates chain logic to the canonical ArchiMateInferenceEngine.
"""

import logging

from app import db
from app.modules.architecture.services.architecture_graph_facade import GraphNode

logger = logging.getLogger(__name__)


class JourneyGraph:
    """Manages the architecture graph for a single journey/solution."""

    def __init__(self, architecture_id: int, solution_id: int):
        self._architecture_id = architecture_id
        self._solution_id = solution_id
        self._engine = None

    @property
    def architecture_id(self):
        return self._architecture_id

    @property
    def solution_id(self):
        return self._solution_id

    @property
    def engine(self):
        """Lazy-load the ArchiMateInferenceEngine."""
        if self._engine is None:
            from app.modules.architecture.services.inference_engine_service import ArchiMateInferenceEngine
            self._engine = ArchiMateInferenceEngine(self._architecture_id)
        return self._engine

    @property
    def facade(self):
        """Access the engine's internal graph facade for direct node operations."""
        return self.engine.graph

    @classmethod
    def create_for_solution(cls, solution_id: int, name: str = None) -> "JourneyGraph":
        """Create a new ArchitectureModel for a journey and return the wrapper."""
        from app.models.archimate_core import ArchitectureModel

        model = ArchitectureModel(
            name=name or f"Journey Architecture for Solution {solution_id}",
            version="1.0",
            solution_id=solution_id,
        )
        db.session.add(model)
        db.session.commit()
        logger.info("Created ArchitectureModel %d for solution %d", model.id, solution_id)
        return cls(architecture_id=model.id, solution_id=solution_id)

    @classmethod
    def resume_for_solution(cls, solution_id: int) -> "JourneyGraph":
        """Find an existing ArchitectureModel for a solution, or create one."""
        from app.models.archimate_core import ArchitectureModel

        model = ArchitectureModel.query.filter_by(solution_id=solution_id).first()
        if model:
            return cls(architecture_id=model.id, solution_id=solution_id)
        return cls.create_for_solution(solution_id)

    def create_inference_skeleton(self, root_nodes):
        """Create the full architecture skeleton from accepted capabilities.

        Delegates to ArchiMateInferenceEngine.generate_chain() which runs
        all 3 inference passes (intra-layer, cross-layer canonical chain,
        semantic refinement) with full provenance tracking.

        Args:
            root_nodes: List of GraphNode objects (accepted capabilities)

        Returns:
            dict with counts: {nodes_created, relationships_created}
        """
        engine = self.engine
        total_nodes = 0
        total_rels = 0

        for node in root_nodes:
            try:
                result = engine.generate_chain(node.id)
                total_nodes += len(result.elements_created)
                total_rels += len(result.relationships_created)
            except Exception as e:
                logger.warning(
                    "generate_chain failed for node %d (%s): %s",
                    node.id, node.name, e,
                )

        return {"nodes_created": total_nodes, "relationships_created": total_rels}

    def get_elements_by_layer(self):
        """Get elements created for THIS journey only, grouped by ArchiMate layer.

        Unlike facade.find_nodes() which includes the entire NULL-architecture
        catalog as fallback, this only returns elements scoped to our
        ArchitectureModel — the ones actually generated for this solution.
        """
        from app.models.archimate_core import ArchiMateElement

        elements = ArchiMateElement.query.filter_by(
            architecture_id=self._architecture_id
        ).all()

        by_layer = {}
        for elem in elements:
            layer = (elem.layer or "unknown").lower()
            by_layer.setdefault(layer, []).append(
                GraphNode(
                    id=elem.id,
                    element_type=elem.type or "",
                    name=elem.name or "",
                    layer=layer,
                    model=elem,
                )
            )
        return by_layer

    def repair(self, node_id: int = None, dry_run: bool = False):
        """Detect and fix broken chains in the journey's architecture.

        If node_id is given, repairs only that element's chain.
        If node_id is None, repairs all root elements (capabilities).

        Args:
            node_id: Specific element to repair, or None for all roots
            dry_run: If True, returns plan without persisting changes

        Returns:
            RepairResult with elements_created, relationships_created, errors
        """
        engine = self.engine
        if node_id:
            return engine.repair(node_id, dry_run=dry_run)
        # Repair all root nodes (capabilities)
        all_nodes = self.facade.find_nodes(element_type="Capability", filters={})
        results = []
        for node in all_nodes:
            try:
                results.append(engine.repair(node.id, dry_run=dry_run))
            except Exception as e:
                logger.warning("repair failed for node %d: %s", node.id, e)
        return results

    def validate_completeness(self):
        """Run the inference engine's architecture-wide diagnostic.

        Delegates to ArchiMateInferenceEngine.diagnose_architecture() which
        checks every element against the canonical chain rules.

        Returns dict with issues, completeness scores per layer, and overall score.
        """
        try:
            diag = self.engine.diagnose_architecture()
        except Exception as e:
            logger.warning("diagnose_architecture failed: %s", e)
            return {"issues": [], "completeness": {}, "overall": 0}

        # diagnose_architecture() iterates all elements in the same order as find_nodes()
        all_nodes = self.facade.find_nodes(element_type=None, filters={})
        issues = []
        layer_scores = {}

        for idx, chain_diag in enumerate(diag.chain_diagnostics):
            node = all_nodes[idx] if idx < len(all_nodes) else None
            elem_id = node.id if node else None
            elem_name = node.name if node else ""
            layer = (node.layer if node else None) or "unknown"

            for missing_type in chain_diag.missing:
                issues.append({
                    "element_id": elem_id,
                    "element_name": elem_name,
                    "element_type": chain_diag.element_type,
                    "missing_type": missing_type,
                    "severity": "required",
                })

            layer_scores.setdefault(layer, {"total": 0, "complete": 0})
            layer_scores[layer]["total"] += 1
            if chain_diag.completeness >= 1.0:
                layer_scores[layer]["complete"] += 1

        completeness = {}
        for layer, counts in layer_scores.items():
            pct = round(counts["complete"] / counts["total"] * 100) if counts["total"] > 0 else 0
            completeness[layer] = {"percentage": pct, "complete": counts["complete"], "total": counts["total"]}

        return {
            "issues": issues,
            "completeness": completeness,
            "overall": round(diag.overall_completeness * 100),
        }
