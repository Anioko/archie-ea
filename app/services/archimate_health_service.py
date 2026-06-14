"""ArchiMate Model Health Service.

Provides health metrics and quality diagnostics for ArchiMate models stored
in the database. Used by the architecture_health dashboard route.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func

from app import db
from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship


def _load_application_component():
    """Lazy import to avoid circular imports at module load time."""
    try:
        from app.models.application_portfolio import ApplicationComponent  # noqa: PLC0415

        return ApplicationComponent
    except ImportError:
        return None


class ArchiMateHealthService:
    """Computes health metrics for ArchiMate model data."""

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def get_health_summary(self) -> dict[str, Any]:
        """Return overall model health metrics.

        Keys returned:
          total_elements, elements_with_name, elements_with_description,
          elements_with_layer, elements_with_type, stale_count,
          broken_relationships, completeness_pct
        """
        total = db.session.query(func.count(ArchiMateElement.id)).scalar() or 0
        with_name = (
            db.session.query(func.count(ArchiMateElement.id))
            .filter(
                ArchiMateElement.name.isnot(None),
                ArchiMateElement.name != "",
            )
            .scalar()
            or 0
        )
        with_desc = (
            db.session.query(func.count(ArchiMateElement.id))
            .filter(
                ArchiMateElement.description.isnot(None),
                ArchiMateElement.description != "",
            )
            .scalar()
            or 0
        )
        with_layer = (
            db.session.query(func.count(ArchiMateElement.id))
            .filter(ArchiMateElement.layer.isnot(None))
            .scalar()
            or 0
        )
        with_type = (
            db.session.query(func.count(ArchiMateElement.id))
            .filter(ArchiMateElement.type.isnot(None))
            .scalar()
            or 0
        )

        stale = len(self.get_stale_elements())
        broken = len(self.get_broken_relationships())

        # Completeness: element has name AND layer AND type
        complete = (
            db.session.query(func.count(ArchiMateElement.id))
            .filter(
                ArchiMateElement.name.isnot(None),
                ArchiMateElement.name != "",
                ArchiMateElement.layer.isnot(None),
                ArchiMateElement.type.isnot(None),
            )
            .scalar()
            or 0
        )
        completeness_pct = round(complete / total * 100, 1) if total else 0.0

        return {
            "total_elements": total,
            "elements_with_name": with_name,
            "elements_with_description": with_desc,
            "elements_with_layer": with_layer,
            "elements_with_type": with_type,
            "stale_count": stale,
            "broken_relationships": broken,
            "completeness_pct": completeness_pct,
        }

    def get_stale_elements(self, days: int = 90) -> list[dict[str, Any]]:
        """Return elements not reviewed/updated in the last *days* days.

        Falls back to last_reviewed_date because ArchiMateElement does not
        carry a generic updated_at column. Elements with no review date at
        all are also treated as stale.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.session.query(ArchiMateElement)
            .filter(
                (ArchiMateElement.last_reviewed_date.is_(None))
                | (ArchiMateElement.last_reviewed_date < cutoff)
            )
            .order_by(ArchiMateElement.last_reviewed_date.asc().nullsfirst())
            .all()
        )
        return [self._element_to_dict(e) for e in rows]

    def get_incomplete_elements(self) -> list[dict[str, Any]]:
        """Return elements missing required fields (name, layer, element type)."""
        rows = (
            db.session.query(ArchiMateElement)
            .filter(
                (ArchiMateElement.name.is_(None))
                | (ArchiMateElement.name == "")
                | (ArchiMateElement.layer.is_(None))
                | (ArchiMateElement.type.is_(None))
            )
            .order_by(ArchiMateElement.id)
            .all()
        )
        return [self._element_to_dict(e) for e in rows]

    def get_broken_relationships(self) -> list[dict[str, Any]]:
        """Return relationships with null or missing source/target elements."""
        # Collect all valid element IDs once
        valid_ids: set[int] = {
            row[0]
            for row in db.session.query(ArchiMateElement.id).all()
        }

        all_rels = db.session.query(ArchiMateRelationship).all()
        broken = []
        for rel in all_rels:
            issues = []
            if rel.source_id is None:
                issues.append("source_id is null")
            elif rel.source_id not in valid_ids:
                issues.append(f"source #{rel.source_id} not found")
            if rel.target_id is None:
                issues.append("target_id is null")
            elif rel.target_id not in valid_ids:
                issues.append(f"target #{rel.target_id} not found")
            if issues:
                broken.append(
                    {
                        "id": rel.id,
                        "type": rel.type or "(untyped)",
                        "source_id": rel.source_id,
                        "target_id": rel.target_id,
                        "source_name": rel.source.name if rel.source else None,
                        "target_name": rel.target.name if rel.target else None,
                        "issue": "; ".join(issues),
                    }
                )
        return broken

    def get_layer_distribution(self) -> dict[str, int]:
        """Return count of elements per ArchiMate layer."""
        rows = (
            db.session.query(
                ArchiMateElement.layer,
                func.count(ArchiMateElement.id).label("cnt"),
            )
            .group_by(ArchiMateElement.layer)
            .order_by(func.count(ArchiMateElement.id).desc())
            .all()
        )
        # Use canonical layer order; append any unexpected layers at the end
        ordered_layers = [
            "Strategy",
            "Motivation",
            "Business",
            "Application",
            "Technology",
            "Physical",
            "Implementation & Migration",
        ]
        dist: dict[str, int] = {layer: 0 for layer in ordered_layers}
        for layer, cnt in rows:
            key = layer or "(unset)"
            if key in dist:
                dist[key] = cnt
            else:
                dist[key] = cnt
        return dist

    def get_model_coverage_by_application(self) -> list[dict[str, Any]]:
        """Return applications with/without linked ArchiMate elements."""
        AppComponent = _load_application_component()
        if AppComponent is None:
            return []

        rows = (
            db.session.query(
                AppComponent.id,
                AppComponent.name,
                func.count(ArchiMateElement.id).label("element_count"),
            )
            .outerjoin(
                ArchiMateElement,
                ArchiMateElement.application_component_id == AppComponent.id,
            )
            .group_by(AppComponent.id, AppComponent.name)
            .order_by(func.count(ArchiMateElement.id).asc(), AppComponent.name)
            .all()
        )
        return [
            {
                "app_id": r.id,
                "app_name": r.name,
                "element_count": r.element_count,
                "has_elements": r.element_count > 0,
            }
            for r in rows
        ]

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _element_to_dict(e: ArchiMateElement) -> dict[str, Any]:
        missing = []
        if not e.name:
            missing.append("name")
        if not e.layer:
            missing.append("layer")
        if not e.type:
            missing.append("type")
        return {
            "id": e.id,
            "name": e.name or "(unnamed)",
            "layer": e.layer or "(unset)",
            "type": e.type or "(unset)",
            "description": e.description or "",
            "last_reviewed_date": (
                e.last_reviewed_date.isoformat() if e.last_reviewed_date else None
            ),
            "missing_fields": missing,
        }
