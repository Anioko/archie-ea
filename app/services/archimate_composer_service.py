"""Service-level helpers for the ArchiMate Composer.

Provides programmatic diagram creation without requiring Flask request context
or @login_required — callable from background services (Slack, Teams, chat).
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

_BASE_URL = "http://127.0.0.1"


def create_diagram(element_ids: List[int], name: str,
                   created_by=None, solution_id: Optional[int] = None) -> Optional[str]:
    """Create a SavedDiagram from ArchiMate element IDs and return its composer URL.

    Uses the same auto-layout algorithm as the HTTP route
    POST /archimate/api/create-diagram-from-elements but callable from any
    service without an active request context.

    Returns the composer URL (e.g. '/archimate/composer?viewpoint=42') or None
    if no matching elements are found.
    """
    if not element_ids:
        return None
    try:
        from app import db
        from app.models.archimate_core import (
            ArchiMateElement, SavedDiagram, SavedDiagramElement,
        )

        elements = ArchiMateElement.query.filter(
            ArchiMateElement.id.in_(element_ids)
        ).all()
        if not elements:
            return None

        layer_order = [
            "Motivation", "Strategy", "Business", "Application",
            "Technology", "Physical", "Implementation", "Other",
        ]
        by_layer: dict = {}
        for el in elements:
            layer = el.layer or "Other"
            by_layer.setdefault(layer, []).append(el)

        diagram = SavedDiagram(
            name=(name or "AI-generated diagram")[:255],
            description=f"Auto-generated from {len(elements)} elements",
            created_by=created_by,
            solution_id=solution_id,
        )
        db.session.add(diagram)
        db.session.flush()

        y_offset = 40
        elem_w, elem_h = 180, 64
        gap_x, gap_y, layer_gap = 30, 20, 40
        cols = 4

        remaining = dict(by_layer)
        for layer_name in layer_order:
            layer_els = remaining.pop(layer_name, [])
            if not layer_els:
                continue
            for idx, el in enumerate(layer_els):
                db.session.add(SavedDiagramElement(
                    diagram_id=diagram.id,
                    element_id=el.id,
                    position_x=40 + (idx % cols) * (elem_w + gap_x),
                    position_y=y_offset + (idx // cols) * (elem_h + gap_y),
                    width=elem_w,
                    height=elem_h,
                    rendering_mode="black_box",
                ))
            rows = (len(layer_els) + cols - 1) // cols
            y_offset += rows * (elem_h + gap_y) + layer_gap

        for layer_els in remaining.values():
            for idx, el in enumerate(layer_els):
                db.session.add(SavedDiagramElement(
                    diagram_id=diagram.id,
                    element_id=el.id,
                    position_x=40 + (idx % cols) * (elem_w + gap_x),
                    position_y=y_offset + (idx // cols) * (elem_h + gap_y),
                    width=elem_w,
                    height=elem_h,
                    rendering_mode="black_box",
                ))
            rows = (len(layer_els) + cols - 1) // cols
            y_offset += rows * (elem_h + gap_y) + layer_gap

        db.session.commit()
        url = f"/archimate/composer?viewpoint={diagram.id}"
        logger.info("composer: created diagram %d ('%s') with %d elements",
                    diagram.id, diagram.name, len(elements))
        return url
    except Exception as exc:
        logger.warning("composer: diagram creation failed: %s", exc)
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
        return None


def element_ids_for_apps(app_names: List[str]) -> List[int]:
    """Look up ArchiMate element IDs for a list of application names.

    Returns element IDs by joining ApplicationComponent.archimate_element_id
    where the app name (case-insensitive) matches one of the supplied names.
    """
    if not app_names:
        return []
    try:
        from app.models.application_portfolio import ApplicationComponent
        lower_names = {n.lower() for n in app_names if n}
        rows = ApplicationComponent.query.with_entities(
            ApplicationComponent.archimate_element_id,
            ApplicationComponent.name,
        ).filter(
            ApplicationComponent.archimate_element_id.isnot(None)
        ).all()
        return [
            r.archimate_element_id
            for r in rows
            if r.name and r.name.lower() in lower_names
        ]
    except Exception as exc:
        logger.debug("composer: element_ids_for_apps error: %s", exc)
        return []


def full_composer_url(relative_url: str) -> str:
    """Convert a relative composer URL to an absolute production URL."""
    return f"{_BASE_URL}{relative_url}"
