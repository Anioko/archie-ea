"""TD-001: Technology Stack Audit Service — Phase D Technology Architecture.

Classifies all 881+ ApplicationComponent rows by hosting/deployment model,
surfaces which apps have ArchiMate technology layer assignments (Node, Device,
SystemSoftware, TechnologyService) and which are missing technology layer
coverage.  All queries use the SQLAlchemy ORM — no raw SQL, no hardcoded counts.
"""

from collections import defaultdict
from typing import Any

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.technology_layer import (
    Device,
    Node,
    SystemSoftware,
    TechnologyService,
)


class TechnologyStackAuditService:
    """Produces a technology stack audit for the entire application portfolio.

    Designed for the TOGAF ADM Phase D (Technology Architecture) workflow.
    Reuses existing ORM models — never recreates tables or raw SQL.
    """

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def audit_portfolio(self) -> dict[str, Any]:
        """Return a full technology stack audit of the application portfolio.

        Returns
        -------
        dict with keys:
          hosting_breakdown   : {deployment_model_value: count}
          apps_with_node_assignment : int — apps that have ≥1 Node row via FK
          apps_with_technology_layer : int — apps covered by any tech-layer entity
          apps_missing_technology_layer : list[int] — app_ids with no tech-layer rows
          technology_layer_coverage : dict — breakdown by layer entity type
          cloud_provider_breakdown : {provider_value: count}
          total_apps : int
        """
        hosting = self._hosting_breakdown()
        node_ids, device_ids, sw_ids, svc_ids = self._technology_layer_app_ids()

        covered_ids = node_ids | device_ids | sw_ids | svc_ids
        all_ids = self._all_app_ids()
        missing_ids = sorted(all_ids - covered_ids)

        cloud_breakdown = self._cloud_provider_breakdown()

        return {
            "total_apps": len(all_ids),
            "hosting_breakdown": hosting,
            "apps_with_node_assignment": len(node_ids),
            "apps_with_technology_layer": len(covered_ids),
            "apps_missing_technology_layer": missing_ids,
            "technology_layer_coverage": {
                "node": len(node_ids),
                "device": len(device_ids),
                "system_software": len(sw_ids),
                "technology_service": len(svc_ids),
            },
            "cloud_provider_breakdown": cloud_breakdown,
        }

    def deployment_model_summary(self) -> list[dict[str, Any]]:
        """Return per-deployment-model totals with node coverage counts.

        Each entry: {deployment_model, app_count, apps_with_nodes, coverage_pct}
        """
        rows = (
            db.session.query(
                ApplicationComponent.deployment_model,
                db.func.count(ApplicationComponent.id).label("app_count"),
            )
            .group_by(ApplicationComponent.deployment_model)
            .all()
        )

        # Build node coverage map per deployment model
        node_rows = (
            db.session.query(
                ApplicationComponent.deployment_model,
                db.func.count(db.func.distinct(Node.application_component_id)).label("n"),
            )
            .join(Node, Node.application_component_id == ApplicationComponent.id)
            .group_by(ApplicationComponent.deployment_model)
            .all()
        )
        node_map = {r.deployment_model: r.n for r in node_rows}

        result = []
        for r in rows:
            dm = r.deployment_model or "unknown"
            count = r.app_count
            nodes = node_map.get(r.deployment_model, 0)
            result.append({
                "deployment_model": dm,
                "app_count": count,
                "apps_with_nodes": nodes,
                "coverage_pct": round(nodes / count * 100, 1) if count else 0.0,
            })

        return sorted(result, key=lambda x: x["app_count"], reverse=True)

    def tech_debt_indicators(self) -> dict[str, Any]:
        """Surface apps with potential technology debt.

        Returns apps with:
          - no_deployment_model : missing deployment_model value
          - no_technology_stack : missing technology_stack JSON field
          - no_primary_database : missing primary_database value
          - no_cloud_provider   : cloud apps with no cloud_provider specified
        """
        base = db.session.query(ApplicationComponent)
        total = base.count()

        no_dm = base.filter(
            (ApplicationComponent.deployment_model == None) |  # noqa: E711
            (ApplicationComponent.deployment_model == "")
        ).count()

        no_ts = base.filter(
            (ApplicationComponent.technology_stack == None) |  # noqa: E711
            (ApplicationComponent.technology_stack == "")
        ).count()

        no_db = base.filter(
            (ApplicationComponent.primary_database == None) |  # noqa: E711
            (ApplicationComponent.primary_database == "")
        ).count()

        # Cloud apps with no cloud_provider
        no_cp = base.filter(
            ApplicationComponent.deployment_model.in_(["cloud", "hybrid", "saas"]),
            (ApplicationComponent.cloud_provider == None) |  # noqa: E711
            (ApplicationComponent.cloud_provider == "")
        ).count()

        return {
            "total_apps": total,
            "no_deployment_model": no_dm,
            "no_technology_stack": no_ts,
            "no_primary_database": no_db,
            "cloud_apps_without_provider": no_cp,
            "debt_score": round((no_dm + no_ts + no_db) / max(total, 1) * 100, 1),
        }

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _all_app_ids(self) -> set[int]:
        rows = db.session.query(ApplicationComponent.id).all()
        return {r.id for r in rows}

    def _hosting_breakdown(self) -> dict[str, int]:
        rows = (
            db.session.query(
                ApplicationComponent.deployment_model,
                db.func.count(ApplicationComponent.id).label("cnt"),
            )
            .group_by(ApplicationComponent.deployment_model)
            .all()
        )
        breakdown: dict[str, int] = defaultdict(int)
        for r in rows:
            key = r.deployment_model or "unknown"
            breakdown[key] += r.cnt
        return dict(breakdown)

    def _technology_layer_app_ids(self) -> tuple[set[int], set[int], set[int], set[int]]:
        """Return (node_app_ids, device_app_ids, sw_app_ids, svc_app_ids)."""
        def _app_ids_for(model):
            rows = (
                db.session.query(model.application_component_id)
                .filter(model.application_component_id != None)  # noqa: E711
                .distinct()
                .all()
            )
            return {r[0] for r in rows}

        return (
            _app_ids_for(Node),
            _app_ids_for(Device),
            _app_ids_for(SystemSoftware),
            _app_ids_for(TechnologyService),
        )

    def _cloud_provider_breakdown(self) -> dict[str, int]:
        rows = (
            db.session.query(
                ApplicationComponent.cloud_provider,
                db.func.count(ApplicationComponent.id).label("cnt"),
            )
            .filter(ApplicationComponent.cloud_provider != None)  # noqa: E711
            .filter(ApplicationComponent.cloud_provider != "")
            .group_by(ApplicationComponent.cloud_provider)
            .all()
        )
        return {r.cloud_provider: r.cnt for r in rows}
