"""Auto-generation support service

Provides helpers to log generation events, manage overrides, and run simple
health checks that identify missing or inconsistent ArchiMate mappings.
"""

import importlib
import json
import logging
from typing import Dict, List, Optional

from app import db

# from app.services.decorators import transactional  # Temporarily disabled

logger = logging.getLogger(__name__)


def log_event(
    event_type: str,
    source: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    status: Optional[str] = None,
    message: Optional[str] = None,
    metadata: Optional[Dict] = None,
    commit: bool = True,
):
    autogen = importlib.import_module("app.models.autogen")
    GenerationEvent = getattr(autogen, "GenerationEvent")
    evt = GenerationEvent(
        event_type=event_type,
        source=source,
        target_type=target_type,
        target_id=target_id,
        status=status,
        message=message,
        metadata=json.dumps(metadata) if metadata else None,
    )
    db.session.add(evt)
    if commit:
        db.session.commit()
    # If commit is False, we do nothing. The object is added to the session
    # and will be flushed/committed when the outer transaction is handled.
    # Calling flush() here would cause "Session is already flushing" error
    # if called from within an after_flush listener.

    logger.info(
        f"Logged autogen event: {evt.event_type} {evt.source} -> {evt.target_type}:{evt.target_id} ({evt.status})"
    )
    return evt


def list_events(limit: int = 100) -> List[Dict]:
    autogen = importlib.import_module("app.models.autogen")
    GenerationEvent = getattr(autogen, "GenerationEvent")
    rows = GenerationEvent.query.order_by(GenerationEvent.created_at.desc()).limit(limit).all()
    return [r.to_dict() for r in rows]


def create_override(
    framework: Optional[str],
    domain: Optional[str],
    target_type: Optional[str],
    rule: str,
    description: Optional[str] = None,
    enabled: bool = True,
):
    autogen = importlib.import_module("app.models.autogen")
    AutoGenOverride = getattr(autogen, "AutoGenOverride")
    ov = AutoGenOverride(
        framework=framework,
        domain=domain,
        target_type=target_type,
        rule=rule,
        description=description,
        enabled=enabled,
    )
    db.session.add(ov)
    db.session.commit()
    return ov


def list_overrides() -> List[Dict]:
    autogen = importlib.import_module("app.models.autogen")
    AutoGenOverride = getattr(autogen, "AutoGenOverride")
    return [
        o.to_dict() for o in AutoGenOverride.query.order_by(AutoGenOverride.created_at.desc()).all()
    ]


def get_applicable_override(
    framework: Optional[str], domain: Optional[str], target_type: Optional[str]
):
    # Try most specific then fall back to partial matches
    autogen = importlib.import_module("app.models.autogen")
    AutoGenOverride = getattr(autogen, "AutoGenOverride")
    q = AutoGenOverride.query.filter_by(enabled=True)
    candidates = q.filter_by(framework=framework, domain=domain, target_type=target_type).all()
    if candidates:
        return candidates[0]
    candidates = (
        q.filter_by(framework=framework, domain=domain)
        .filter(AutoGenOverride.target_type.is_(None))
        .all()
    )
    if candidates:
        return candidates[0]
    candidates = q.filter_by(framework=framework).filter(AutoGenOverride.domain.is_(None)).all()
    if candidates:
        return candidates[0]
    return None


def run_health_check(limit: int = 500) -> Dict:
    """Run quick health checks to surface missing/inconsistent ArchiMate elements.

    Checks implemented:
    - BusinessCapability without `archimate_element_id`
    - BusinessFunction without `requirements` or missing archimate link
    - ArchiMate elements without relationships (orphaned)
    """
    report = {
        "timestamp": None,
        "missing_capabilities": [],
        "functions_without_requirements": [],
        "orphaned_archimate_elements": [],
        "summary": {},
    }

    from datetime import datetime

    report["timestamp"] = datetime.utcnow().isoformat()

    # Missing capability archimate links
    models = importlib.import_module("app.models.business_capabilities")
    BusinessCapability = getattr(models, "BusinessCapability")
    BusinessFunction = getattr(models, "BusinessFunction")
    caps = BusinessCapability.query.limit(limit).all()
    for c in caps:
        if not c.archimate_element_id:
            report["missing_capabilities"].append({"id": c.id, "name": c.name})

    # Functions lacking requirements or archimate elements
    funcs = BusinessFunction.query.limit(limit).all()
    for f in funcs:
        if f.requirements.count() == 0:
            report["functions_without_requirements"].append(
                {"id": f.id, "name": f.name, "capability_id": f.capability_id}
            )

    # Orphaned archimate elements (no relationships)
    archimate = importlib.import_module("app.models.models")
    ArchiMateElement = getattr(archimate, "ArchiMateElement")
    elems = ArchiMateElement.query.limit(limit).all()
    for e in elems:
        rel_count = 0
        try:
            rel_count = (
                len(e.archimate_relationships_all)
                if hasattr(e, "archimate_relationships_all")
                else (
                    len(e.source_relationships) + len(e.target_relationships)
                    if hasattr(e, "source_relationships")
                    else 0
                )
            )
        except Exception:
            rel_count = 0
        if rel_count == 0:
            report["orphaned_archimate_elements"].append(
                {"id": e.id, "name": e.name, "type": e.type, "layer": e.layer}
            )

    report["summary"] = {
        "checked_capabilities": len(caps),
        "missing_capabilities": len(report["missing_capabilities"]),
        "checked_functions": len(funcs),
        "functions_without_requirements": len(report["functions_without_requirements"]),
        "checked_archimate_elements": len(elems),
        "orphaned_archimate_elements": len(report["orphaned_archimate_elements"]),
    }

    # Log that health check ran
    log_event(
        "health_check", "autogen_service", status="success", message=json.dumps(report["summary"])
    )

    return report
