"""CM-002: Architecture Change Impact Service — Phase H Change Management.

Assesses the blast radius of a change request by traversing ArchiMate
relationships (up to depth 2) to identify downstream application dependencies.
Calls TechnologyStackAuditService for technology context.
All queries use SQLAlchemy ORM — no raw SQL, no hardcoded counts.
"""

import logging
from typing import Any, Dict, List, Set

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.services.technology_stack_audit_service import TechnologyStackAuditService

logger = logging.getLogger(__name__)


def _blast_radius_tier(impact_radius: int) -> str:
    """Classify impact radius into a blast-radius tier.

    Tiers follow enterprise programme governance conventions:
      > 50 apps → "enterprise"   (cross-organisational impact)
      > 20 apps → "program"      (programme-level impact)
      >  5 apps → "project"      (project-level impact)
      else      → "local"        (contained / minimal impact)
    """
    if impact_radius > 50:
        return "enterprise"
    if impact_radius > 20:
        return "program"
    if impact_radius > 5:
        return "project"
    return "local"


class ArchitectureChangeImpactService:
    """Computes change impact / blast-radius for a ChangeRequest.

    Traverses ArchiMateRelationship edges (BFS, up to depth 2) from each
    application element in the change scope.  Returns a structured impact
    assessment dict aligned with the Phase H Change Management workflow.
    """

    MAX_HOPS = 2

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def assess_change_impact(self, change_request_id: int) -> Dict[str, Any]:
        """Return an impact assessment for the given change request.

        Parameters
        ----------
        change_request_id : int
            Primary key of the ChangeRequest row to assess.

        Returns
        -------
        dict with keys:
          change_request_id   : int
          scope_app_count     : int — apps explicitly in scope
          impact_radius       : int — unique downstream apps reached via traversal
          blast_radius_tier   : "enterprise" | "program" | "project" | "local"
          downstream_apps     : list[str] — names of downstream apps
          compliance_risk     : bool — True if any scoped app has compliance_score < 60
        On error:
          {"error": "not_found", "change_request_id": ...}
          {"error": "import_error", "change_request_id": ...}
        """
        # -------------------------------------------------------------- #
        # 1. Load ChangeRequest (guard ImportError for missing model)     #
        # -------------------------------------------------------------- #
        try:
            from app.models.architecture_review_board import ChangeRequest
        except ImportError:
            return {"error": "import_error", "change_request_id": change_request_id}

        change_request = db.session.get(ChangeRequest, change_request_id)
        if change_request is None:
            return {"error": "not_found", "change_request_id": change_request_id}

        # -------------------------------------------------------------- #
        # 2. Derive scope_app_ids from the change request                 #
        # -------------------------------------------------------------- #
        scope_app_ids: List[int] = self._extract_scope_app_ids(change_request)

        # -------------------------------------------------------------- #
        # 3. Load ApplicationComponent rows for in-scope apps             #
        # -------------------------------------------------------------- #
        apps_in_scope: List[ApplicationComponent] = []
        if scope_app_ids:
            apps_in_scope = ApplicationComponent.query.filter(
                ApplicationComponent.id.in_(scope_app_ids)
            ).all()

        scope_app_count = len(apps_in_scope)

        # -------------------------------------------------------------- #
        # 4. BFS traversal of ArchiMateRelationship (depth ≤ MAX_HOPS)   #
        # -------------------------------------------------------------- #
        scope_element_ids: Set[int] = {
            a.archimate_element_id
            for a in apps_in_scope
            if a.archimate_element_id is not None
        }

        downstream_element_ids: Set[int] = set()
        if scope_element_ids:
            all_rels = self._load_all_relationships()
            hop_map = self._bfs_traverse(list(scope_element_ids), all_rels)
            downstream_element_ids = set(hop_map.keys())

        # Map downstream element IDs → ApplicationComponent rows
        downstream_apps: List[ApplicationComponent] = []
        if downstream_element_ids:
            downstream_apps = ApplicationComponent.query.filter(
                ApplicationComponent.archimate_element_id.in_(downstream_element_ids)
            ).all()

        impact_radius = len({a.id for a in downstream_apps})
        downstream_app_names = [a.name for a in downstream_apps]

        # -------------------------------------------------------------- #
        # 5. Technology context via TechnologyStackAuditService           #
        # -------------------------------------------------------------- #
        TechnologyStackAuditService().audit_portfolio()

        # -------------------------------------------------------------- #
        # 6. Blast-radius tier                                            #
        # -------------------------------------------------------------- #
        tier = _blast_radius_tier(impact_radius)

        # -------------------------------------------------------------- #
        # 7. Compliance risk — true if any scoped app has low score       #
        # -------------------------------------------------------------- #
        compliance_risk: bool = self._has_compliance_risk(apps_in_scope)

        return {
            "change_request_id": change_request_id,
            "scope_app_count": scope_app_count,
            "impact_radius": impact_radius,
            "blast_radius_tier": tier,
            "downstream_apps": downstream_app_names,
            "compliance_risk": compliance_risk,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _extract_scope_app_ids(self, change_request) -> List[int]:
        """Extract scope application IDs from the change request payload.

        Checks the following attributes in priority order:
        impact_assessment → new_values → old_values
        within each, looks for keys: scope_app_ids, app_ids, scope.
        """
        for attr in ("impact_assessment", "new_values", "old_values"):
            payload = getattr(change_request, attr, None)
            if isinstance(payload, dict):
                ids = (
                    payload.get("scope_app_ids")
                    or payload.get("app_ids")
                    or payload.get("scope")
                    or []
                )
                if ids and isinstance(ids, list):
                    return [int(i) for i in ids if i is not None]
        return []

    def _load_all_relationships(self) -> List:
        """Load all ArchiMateRelationship rows once (avoids per-hop queries)."""
        try:
            from app.models.models import ArchiMateRelationship  # type: ignore[attr-defined]
            rows = (
                db.session.query(
                    ArchiMateRelationship.source_id,
                    ArchiMateRelationship.target_id,
                )
                .all()
            )
            return rows
        except Exception as exc:
            logger.warning("_load_all_relationships: %s", exc)
            return []

    def _bfs_traverse(
        self,
        seed_ids: List[int],
        relationships: List,
    ) -> Dict[int, int]:
        """BFS from seed_ids over relationships, returning element_id → hop.

        Parameters
        ----------
        seed_ids : list[int]
            Starting ArchiMate element IDs (depth 0 — excluded from result).
        relationships : list
            Iterable of (source_id, target_id) row tuples from ORM query.

        Returns
        -------
        dict mapping each reachable element_id to its minimum hop distance
        from any seed node.  Seed nodes themselves are not included.
        Traversal is capped at MAX_HOPS hops.
        """
        adj: Dict[int, Set[int]] = {}
        for src, tgt in relationships:
            adj.setdefault(src, set()).add(tgt)

        visited: Dict[int, int] = {}
        frontier: Set[int] = set(seed_ids)
        seed_set: Set[int] = set(seed_ids)

        for hop in range(1, self.MAX_HOPS + 1):
            next_frontier: Set[int] = set()
            for node in frontier:
                for neighbour in adj.get(node, set()):
                    if neighbour not in seed_set and neighbour not in visited:
                        visited[neighbour] = hop
                        next_frontier.add(neighbour)
            if not next_frontier:
                break
            frontier = next_frontier

        return visited

    def _has_compliance_risk(self, apps: List[ApplicationComponent]) -> bool:
        """Return True if any app in the list has user_satisfaction_score < 60.

        user_satisfaction_score is used as a proxy for compliance_score since
        ApplicationComponent does not have a dedicated compliance_score column.
        Returns False when no apps are provided or no scores are available.
        """
        for app in apps:
            score = app.user_satisfaction_score
            if score is not None and score < 60:
                return True
        return False
