"""TD-007: Infrastructure Complexity Service — Phase D Technology Architecture.

Computes an infrastructure complexity matrix for every ApplicationComponent,
scoring each application by its Technology-layer element count, ArchiMate
relationship count, and BFS-traversal dependency depth (capped at depth 3).

All queries use the SQLAlchemy ORM — no raw SQL, no hardcoded counts.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.models import ArchiMateElement, ArchiMateRelationship


class InfrastructureComplexityService:
    """Produce an infrastructure complexity matrix for the application portfolio.

    Designed for TOGAF ADM Phase D (Technology Architecture).
    Reuses existing ORM models — never recreates tables or raw SQL.
    """

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def compute_complexity_matrix(self) -> list[dict[str, Any]]:
        """Return complexity scores for every ApplicationComponent.

        For each ApplicationComponent the method:
        1. Counts Technology-layer ArchiMateElement rows linked to the app
           via the ``application_component_id`` foreign key.
        2. Counts ArchiMateRelationship rows where source or target is one
           of the app's own ArchiMate element IDs.
        3. Performs a BFS (max depth 3) over ArchiMateRelationship to
           compute the maximum reachable dependency depth from the app's
           own elements.
        4. Computes complexity_score = (tech_element_count * 0.4)
           + (relationship_count * 0.3) + (dependency_depth * 0.3),
           capped at 100.
        5. Assigns tier: score > 70 → "high", > 40 → "medium", else "low".

        Returns
        -------
        list[dict] — one entry per ApplicationComponent:
            {app_id, app_name, tech_element_count, relationship_count,
             dependency_depth, complexity_score, tier}
        """
        apps = db.session.query(
            ApplicationComponent.id, ApplicationComponent.name
        ).all()
        if not apps:
            return []

        # Everything below is pre-fetched in a fixed number of queries (was
        # ~2 queries PER app -> ~1.7k round-trips on an 867-app portfolio, which
        # blew the request timeout). The per-app loop is now pure in-memory.
        tech_elements_by_app = self._tech_elements_by_app()
        all_elements_by_app = self._all_elements_by_app()
        rel_index, incident = self._relationship_index_and_incident()

        results: list[dict[str, Any]] = []
        for app_id, app_name in apps:
            tech_ids: set[int] = tech_elements_by_app.get(app_id, set())
            tech_element_count = len(tech_ids)

            all_app_element_ids = all_elements_by_app.get(app_id, set())

            # Distinct relationships touching any of the app's elements.
            rel_ids: set[int] = set()
            for eid in all_app_element_ids:
                rel_ids.update(incident.get(eid, ()))
            relationship_count = len(rel_ids)

            # BFS dependency depth over full relationship graph (in-memory)
            dependency_depth = self._bfs_depth(all_app_element_ids, rel_index, max_depth=3)

            raw_score = (
                tech_element_count * 0.4
                + relationship_count * 0.3
                + dependency_depth * 0.3
            )
            complexity_score = round(min(raw_score, 100.0), 2)

            if complexity_score > 70:
                tier = "high"
            elif complexity_score > 40:
                tier = "medium"
            else:
                tier = "low"

            results.append({
                "app_id": app_id,
                "app_name": app_name,
                "tech_element_count": tech_element_count,
                "relationship_count": relationship_count,
                "dependency_depth": dependency_depth,
                "complexity_score": complexity_score,
                "tier": tier,
            })

        return results

    def _all_elements_by_app(self) -> dict[int, set[int]]:
        """Return {app_component_id: {archimate_element_id, ...}} for ALL layers (one query)."""
        rows = (
            db.session.query(
                ArchiMateElement.application_component_id,
                ArchiMateElement.id,
            )
            .filter(ArchiMateElement.application_component_id.isnot(None))
            .all()
        )
        mapping: dict[int, set[int]] = {}
        for app_comp_id, elem_id in rows:
            mapping.setdefault(app_comp_id, set()).add(elem_id)
        return mapping

    def _relationship_index_and_incident(
        self,
    ) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
        """One pass over relationships -> (adjacency index, {element_id: {edge_id,...}}).

        edge_id is the row's enumeration index, so distinct relationship rows stay
        distinct and the per-app relationship count matches a SQL row count.
        """
        rows = (
            db.session.query(
                ArchiMateRelationship.source_id,
                ArchiMateRelationship.target_id,
            )
            .filter(
                ArchiMateRelationship.source_id.isnot(None),
                ArchiMateRelationship.target_id.isnot(None),
            )
            .all()
        )
        index: dict[int, set[int]] = {}
        incident: dict[int, set[int]] = {}
        for edge_id, (src, tgt) in enumerate(rows):
            index.setdefault(src, set()).add(tgt)
            index.setdefault(tgt, set()).add(src)
            incident.setdefault(src, set()).add(edge_id)
            incident.setdefault(tgt, set()).add(edge_id)
        return index, incident

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _tech_elements_by_app(self) -> dict[int, set[int]]:
        """Return {app_component_id: {archimate_element_id, ...}} for Technology layer."""
        rows = (
            db.session.query(
                ArchiMateElement.application_component_id,
                ArchiMateElement.id,
            )
            .filter(
                ArchiMateElement.layer == "Technology",
                ArchiMateElement.application_component_id.isnot(None),
            )
            .all()
        )
        mapping: dict[int, set[int]] = {}
        for app_comp_id, elem_id in rows:
            mapping.setdefault(app_comp_id, set()).add(elem_id)
        return mapping

    def _all_element_ids_for_app(self, app_id: int) -> set[int]:
        """Return all ArchiMateElement IDs (any layer) linked to app_id."""
        rows = (
            db.session.query(ArchiMateElement.id)
            .filter(ArchiMateElement.application_component_id == app_id)
            .all()
        )
        return {r[0] for r in rows}

    def _count_relationships(self, element_ids: set[int]) -> int:
        """Count ArchiMateRelationship rows touching any element in element_ids."""
        if not element_ids:
            return 0
        ids = list(element_ids)
        count = (
            db.session.query(ArchiMateRelationship.id)
            .filter(
                db.or_(
                    ArchiMateRelationship.source_id.in_(ids),
                    ArchiMateRelationship.target_id.in_(ids),
                )
            )
            .count()
        )
        return count

    def _relationship_index(self) -> dict[int, set[int]]:
        """Build adjacency dict {element_id: {neighbour_element_id, ...}} from all relationships."""
        rows = (
            db.session.query(
                ArchiMateRelationship.source_id,
                ArchiMateRelationship.target_id,
            )
            .filter(
                ArchiMateRelationship.source_id.isnot(None),
                ArchiMateRelationship.target_id.isnot(None),
            )
            .all()
        )
        index: dict[int, set[int]] = {}
        for src, tgt in rows:
            index.setdefault(src, set()).add(tgt)
            index.setdefault(tgt, set()).add(src)
        return index

    def _bfs_depth(
        self,
        seed_ids: set[int],
        rel_index: dict[int, set[int]],
        max_depth: int = 3,
    ) -> int:
        """BFS from seed_ids through rel_index; return max reached depth (≤ max_depth)."""
        if not seed_ids or not rel_index:
            return 0

        visited: set[int] = set(seed_ids)
        queue: deque[tuple[int, int]] = deque((nid, 0) for nid in seed_ids)
        max_reached = 0

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                max_reached = max(max_reached, depth)
                continue
            for neighbour in rel_index.get(current_id, set()):
                if neighbour not in visited:
                    visited.add(neighbour)
                    next_depth = depth + 1
                    max_reached = max(max_reached, next_depth)
                    queue.append((neighbour, next_depth))

        return max_reached
