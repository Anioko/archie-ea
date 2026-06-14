"""CMP-046: ArchiMate 3.2 derived relationship computation (sect 5.5).

Implements the derivation rules that compute indirect (derived) relationships
through chains of explicit relationships.  The ArchiMate standard defines
that structural > dependency > other in precedence, and derived rels
"weaken" through the chain.

Derivation table (ArchiMate 3.2, Table 2):
    Composition + X     → X  (composition is transparent)
    Aggregation + X     → X  (aggregation is transparent)
    Realization + X     → X  (realization is transparent)
    Assignment + X      → X  (assignment is transparent)
    Serving + Serving   → Serving
    Serving + Access    → Access
    Access + Serving    → Access
    Flow + Flow         → Flow
    Triggering + Trig   → Triggering

All other combos → weakest: Association.

Max chain depth: 5 (prevent combinatorial explosion).
"""

import logging
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

# ArchiMate 3.2 relationship strength ordering (strongest → weakest)
STRENGTH_ORDER = [
    "Composition", "Aggregation", "Assignment", "Realization",
    "Serving", "Access", "Influence", "Triggering", "Flow",
    "Specialization", "Association",
]
STRENGTH_RANK = {r: i for i, r in enumerate(STRENGTH_ORDER)}

# "Transparent" structural relationships — they propagate without weakening
_TRANSPARENT = frozenset({"Composition", "Aggregation", "Realization", "Assignment"})

# Derivation table: (rel_A_type, rel_B_type) → derived_type
# If both are transparent they just propagate. Otherwise use this table.
_DERIVATION_TABLE = {
    ("Serving", "Serving"): "Serving",
    ("Serving", "Access"): "Access",
    ("Access", "Serving"): "Access",
    ("Flow", "Flow"): "Flow",
    ("Triggering", "Triggering"): "Triggering",
    ("Influence", "Influence"): "Influence",
}

MAX_DEPTH = 5


def _derive_type(type_a: str, type_b: str) -> str:
    """Compute the derived relationship type from chaining type_a → type_b."""
    # If either is transparent, result is the other
    if type_a in _TRANSPARENT:
        return type_b
    if type_b in _TRANSPARENT:
        return type_a
    # Check derivation table
    result = _DERIVATION_TABLE.get((type_a, type_b))
    if result:
        return result
    # Fallback: weakest = Association
    return "Association"


class ArchiMateDerivationService:
    """Compute derived relationships from a set of elements and relationships."""

    def compute_derived(
        self,
        elements: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Compute all derived (indirect) relationships not already explicit.

        Args:
            elements: List of {id, name, type, layer}
            relationships: List of {id, source_id, target_id, type}

        Returns:
            List of derived relationships:
            [{source_id, target_id, type, chain, depth}]
        """
        element_ids = {e["id"] for e in elements}

        # Build adjacency: source_id → [(target_id, rel_type, rel_id)]
        adj: Dict[int, List[Tuple[int, str, int]]] = {}
        for rel in relationships:
            src = rel["source_id"]
            tgt = rel["target_id"]
            if src not in element_ids or tgt not in element_ids:
                continue
            adj.setdefault(src, []).append((tgt, rel["type"], rel["id"]))

        # Existing explicit pairs (source, target) to avoid duplicating
        explicit_pairs: Set[Tuple[int, int]] = set()
        for rel in relationships:
            explicit_pairs.add((rel["source_id"], rel["target_id"]))

        derived: List[Dict[str, Any]] = []
        seen_pairs: Set[Tuple[int, int]] = set()

        # BFS from each element
        for start_id in element_ids:
            # Queue: (current_node, accumulated_type, depth, chain_path)
            queue: List[Tuple[int, str, int, List[int]]] = []
            for next_id, rel_type, rel_id in adj.get(start_id, []):
                queue.append((next_id, rel_type, 1, [start_id, next_id]))

            while queue:
                current, acc_type, depth, path = queue.pop(0)
                if depth >= MAX_DEPTH:
                    continue

                for next_id, rel_type, rel_id in adj.get(current, []):
                    if next_id in path:
                        continue  # No cycles

                    new_type = _derive_type(acc_type, rel_type)
                    new_path = path + [next_id]
                    pair = (start_id, next_id)

                    # Only add if not explicit and not already derived
                    if pair not in explicit_pairs and pair not in seen_pairs and start_id != next_id:
                        seen_pairs.add(pair)
                        derived.append({
                            "source_id": start_id,
                            "target_id": next_id,
                            "type": new_type,
                            "chain": new_path,
                            "depth": len(new_path) - 1,
                        })

                    queue.append((next_id, new_type, depth + 1, new_path))

        logger.info(
            "Derived relationship computation: %d explicit → %d derived",
            len(relationships), len(derived),
        )
        return derived
