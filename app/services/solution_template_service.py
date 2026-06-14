"""SA-006: Solution design template service.

Provides pre-built scaffolds for common architecture patterns.
"""

import logging
from datetime import datetime

from app import db
from app.models.archimate_core import ArchiMateElement
from app.models.solution_element import SolutionElement
from app.models.solution_models import Solution

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template catalogue
# ---------------------------------------------------------------------------

SOLUTION_TEMPLATES: dict[str, dict] = {
    "microservices": {
        "name": "Microservices Platform",
        "description": (
            "API Gateway, independent services, message bus, polyglot data stores, "
            "and centralised observability. Ideal for teams that need independent "
            "deployment and scaling per service."
        ),
        "elements": [
            {"type": "ApplicationComponent", "layer": "application", "name": "API Gateway"},
            {"type": "ApplicationService",   "layer": "application", "name": "Auth Service"},
            {"type": "ApplicationService",   "layer": "application", "name": "Order Service"},
            {"type": "ApplicationService",   "layer": "application", "name": "Inventory Service"},
            {"type": "TechnologyService",    "layer": "technology",  "name": "Message Bus"},
            {"type": "DataObject",           "layer": "application", "name": "Order Data Store"},
            {"type": "DataObject",           "layer": "application", "name": "Inventory Data Store"},
            {"type": "TechnologyService",    "layer": "technology",  "name": "Monitoring & Tracing"},
        ],
    },
    "event_driven": {
        "name": "Event-Driven Architecture",
        "description": (
            "Event broker, producers, consumers, and durable event store. "
            "Decouples services through asynchronous events, enabling resilient "
            "and loosely coupled integrations."
        ),
        "elements": [
            {"type": "TechnologyService",    "layer": "technology",  "name": "Event Broker"},
            {"type": "ApplicationComponent", "layer": "application", "name": "Event Producer A"},
            {"type": "ApplicationComponent", "layer": "application", "name": "Event Producer B"},
            {"type": "ApplicationComponent", "layer": "application", "name": "Event Consumer A"},
            {"type": "ApplicationComponent", "layer": "application", "name": "Event Consumer B"},
            {"type": "DataObject",           "layer": "application", "name": "Event Store"},
            {"type": "ApplicationService",   "layer": "application", "name": "Dead-Letter Handler"},
        ],
    },
    "cqrs_event_sourcing": {
        "name": "CQRS / Event Sourcing",
        "description": (
            "Command side (writes) separated from query side (reads) with an event "
            "store as the source of truth. Projections rebuild read models from the "
            "immutable event log."
        ),
        "elements": [
            {"type": "ApplicationService",   "layer": "application", "name": "Command Handler"},
            {"type": "ApplicationService",   "layer": "application", "name": "Query Handler"},
            {"type": "DataObject",           "layer": "application", "name": "Event Store"},
            {"type": "ApplicationComponent", "layer": "application", "name": "Aggregate Root"},
            {"type": "ApplicationComponent", "layer": "application", "name": "Read Model Projection"},
            {"type": "DataObject",           "layer": "application", "name": "Read Database"},
            {"type": "TechnologyService",    "layer": "technology",  "name": "Message Bus"},
        ],
    },
    "three_tier_web": {
        "name": "Three-Tier Web",
        "description": (
            "Classic presentation / application / data tiers augmented with a load "
            "balancer and CDN for scalability. A proven pattern for web applications "
            "requiring clear separation of concerns."
        ),
        "elements": [
            {"type": "TechnologyService",    "layer": "technology",  "name": "CDN"},
            {"type": "TechnologyService",    "layer": "technology",  "name": "Load Balancer"},
            {"type": "ApplicationComponent", "layer": "application", "name": "Presentation Tier"},
            {"type": "ApplicationComponent", "layer": "application", "name": "Application Tier"},
            {"type": "DataObject",           "layer": "application", "name": "Data Tier"},
            {"type": "TechnologyService",    "layer": "technology",  "name": "Cache Layer"},
        ],
    },
    "data_lake": {
        "name": "Data Lake / Analytics",
        "description": (
            "Ingestion pipeline, multi-zone storage (raw / curated / consumption), "
            "analytical serving layer, and governance. Supports both batch and "
            "streaming workloads."
        ),
        "elements": [
            {"type": "ApplicationService",   "layer": "application", "name": "Ingestion Pipeline"},
            {"type": "DataObject",           "layer": "application", "name": "Raw Zone"},
            {"type": "DataObject",           "layer": "application", "name": "Curated Zone"},
            {"type": "DataObject",           "layer": "application", "name": "Consumption Zone"},
            {"type": "ApplicationComponent", "layer": "application", "name": "Analytical Serving Layer"},
            {"type": "ApplicationService",   "layer": "application", "name": "Data Governance"},
            {"type": "TechnologyService",    "layer": "technology",  "name": "Streaming Engine"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def list_templates() -> list[dict]:
    """Return the template catalogue (id, name, description, element_count)."""
    return [
        {
            "id": tid,
            "name": tpl["name"],
            "description": tpl["description"],
            "element_count": len(tpl["elements"]),
        }
        for tid, tpl in SOLUTION_TEMPLATES.items()
    ]


def create_solution_from_template(
    template_id: str,
    solution_name: str,
    created_by: int,
) -> dict:
    """Create a Solution + SolutionElement rows from a template.

    Returns a dict with ``solution_id`` and ``redirect_url``.
    Raises ``ValueError`` for unknown template_id.
    """
    tpl = SOLUTION_TEMPLATES.get(template_id)
    if tpl is None:
        raise ValueError(f"Unknown template: {template_id!r}")

    solution = Solution(
        name=solution_name or tpl["name"],
        description=tpl["description"],
        solution_type="Platform",
        status="planned",
        governance_status="draft",
        created_by_id=created_by,
        created_at=datetime.utcnow(),
    )
    db.session.add(solution)
    db.session.flush()  # populate solution.id

    for elem_spec in tpl["elements"]:
        archimate_elem = _get_or_create_element(
            name=elem_spec["name"],
            elem_type=elem_spec["type"],
            layer=elem_spec["layer"],
        )
        se = SolutionElement(
            solution_id=solution.id,
            archimate_element_id=archimate_elem.id,
            layer=elem_spec["layer"],
        )
        db.session.add(se)

    db.session.commit()
    logger.info("SA-006: created solution %d from template %s", solution.id, template_id)

    return {
        "solution_id": solution.id,
        "redirect_url": f"/solutions/{solution.id}",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_or_create_element(name: str, elem_type: str, layer: str) -> ArchiMateElement:
    """Return an existing ArchiMateElement or create a new one."""
    elem = ArchiMateElement.query.filter_by(name=name, type=elem_type).first()
    if elem is None:
        elem = ArchiMateElement(
            name=name,
            type=elem_type,
            layer=layer,
            scope="enterprise",
        )
        db.session.add(elem)
        db.session.flush()
    return elem
