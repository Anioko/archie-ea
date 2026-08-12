"""
Customer Journey Service

Business logic for the BIZBOK customer journey map: journeys, their ordered
stages, and the stage -> BusinessCapability links that turn a journey picture
into architecture.

Shape of the module mirrors ``value_stream_service`` deliberately — the two
maps are siblings and a reader who knows one should not have to learn the
other.

Read paths are fault-tolerant: they log and return a neutral shape so a bad row
renders an empty state rather than a 500. They never invent a value; where a
measurement is absent the dict carries ``None`` and the template renders an em
dash. Write paths raise, and the caller owns the rollback.
"""

import logging
from typing import Any, Dict, List, Optional

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.customer_journey import (
    SENTIMENT_SCALE,
    SUPPORT_TYPES,
    CustomerJourney,
    CustomerJourneyStage,
    CustomerJourneyStageCapability,
)

logger = logging.getLogger(__name__)

VALID_JOURNEY_TYPES = {"acquisition", "onboarding", "service", "retention", "exit"}
VALID_LIFECYCLE_STATUSES = {"draft", "current", "target"}

# The ArchiMate mirror for a journey. Lower case layer: the element browser and
# the layer APIs key on lower case, and `_ArchiMateLayerType` canonicalises to
# it on the way into the database anyway.
ARCHIMATE_JOURNEY_TYPE = "BusinessProcess"
ARCHIMATE_JOURNEY_LAYER = "business"


# ---------------------------------------------------------------------------
# Journey CRUD
# ---------------------------------------------------------------------------


def list_journeys() -> List[Dict[str, Any]]:
    """Every journey with its stage count and distinct linked-capability count."""
    results: List[Dict[str, Any]] = []
    try:
        journeys = CustomerJourney.query.order_by(CustomerJourney.name).all()
    except Exception:
        logger.error("Failed to list customer journeys", exc_info=True)
        return results

    for journey in journeys:
        try:
            stage_count = journey.stages.count()
        except Exception:
            logger.warning(
                "Failed to count stages for customer journey %s", journey.id, exc_info=True
            )
            stage_count = None

        try:
            capability_count = (
                db.session.query(CustomerJourneyStageCapability.capability_id)
                .filter(CustomerJourneyStageCapability.journey_id == journey.id)
                .distinct()
                .count()
            )
        except Exception:
            logger.warning(
                "Failed to count linked capabilities for customer journey %s",
                journey.id,
                exc_info=True,
            )
            capability_count = None

        results.append(
            {
                "id": journey.id,
                "code": journey.code,
                "name": journey.name,
                "description": journey.description,
                "persona_name": journey.persona_name,
                "journey_type": journey.journey_type,
                "lifecycle_status": journey.lifecycle_status,
                "business_owner": journey.business_owner,
                "stage_count": stage_count,
                "capability_count": capability_count,
                "archimate_element_id": journey.archimate_element_id,
            }
        )
    return results


def get_journey(journey_id: int) -> Optional[CustomerJourney]:
    """Fetch a single journey, or None."""
    try:
        return CustomerJourney.query.filter(CustomerJourney.id == journey_id).first()
    except Exception:
        logger.error("Failed to fetch customer journey %s", journey_id, exc_info=True)
        return None


def _journey_to_dict(journey: CustomerJourney) -> Dict[str, Any]:
    return {
        "id": journey.id,
        "code": journey.code,
        "name": journey.name,
        "description": journey.description,
        "persona_name": journey.persona_name,
        "persona_description": journey.persona_description,
        "persona_element_id": journey.persona_element_id,
        "journey_type": journey.journey_type,
        "lifecycle_status": journey.lifecycle_status,
        "business_owner": journey.business_owner,
        "archimate_element_id": journey.archimate_element_id,
    }


def get_journey_with_stages(journey_id: int) -> Optional[Dict[str, Any]]:
    """A journey dict enriched with its ordered stages and their capability links."""
    journey = get_journey(journey_id)
    if not journey:
        return None

    try:
        stages = (
            CustomerJourneyStage.query.filter(
                CustomerJourneyStage.journey_id == journey_id
            )
            .order_by(CustomerJourneyStage.stage_order)
            .all()
        )
    except Exception:
        logger.error(
            "Failed to load stages for customer journey %s", journey_id, exc_info=True
        )
        stages = []

    links_by_stage = _capability_links_by_stage(journey_id)

    data = _journey_to_dict(journey)
    data["stages"] = [
        dict(_stage_to_dict(stage), capabilities=links_by_stage.get(stage.id, []))
        for stage in stages
    ]
    # Sentiment curve for the whole journey. Only rated stages contribute; an
    # unrated stage carries None so the chart shows a gap rather than a zero.
    data["sentiment_curve"] = [
        {
            "stage_id": stage["id"],
            "stage_name": stage["name"],
            "sentiment": stage["sentiment"],
            "sentiment_score": stage["sentiment_score"],
        }
        for stage in data["stages"]
    ]
    return data


def create_journey(data: Dict[str, Any]) -> CustomerJourney:
    """Create a journey and its ArchiMate mirror. Raises; caller rolls back."""
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")

    journey = CustomerJourney(
        name=name,
        code=(data.get("code") or "").strip() or None,
        description=data.get("description") or None,
        persona_name=(data.get("persona_name") or "").strip() or None,
        persona_description=data.get("persona_description") or None,
        persona_element_id=_to_int(data.get("persona_element_id")),
        journey_type=_choice(data.get("journey_type"), VALID_JOURNEY_TYPES),
        lifecycle_status=_choice(data.get("lifecycle_status"), VALID_LIFECYCLE_STATUSES),
        business_owner=(data.get("business_owner") or "").strip() or None,
    )
    db.session.add(journey)
    db.session.flush()

    element_id = _sync_archimate_element(journey)
    if element_id is not None:
        journey.archimate_element_id = element_id

    db.session.commit()
    return journey


def update_journey(journey_id: int, data: Dict[str, Any]) -> Optional[CustomerJourney]:
    """Update a journey. Returns None when it does not exist."""
    journey = get_journey(journey_id)
    if not journey:
        return None

    for field in ("name", "code", "description", "persona_name",
                  "persona_description", "business_owner"):
        if field in data:
            value = data.get(field)
            value = value.strip() if isinstance(value, str) else value
            # `name` is NOT NULL — an empty submission keeps the current value
            # rather than writing a row the database will reject.
            if field == "name" and not value:
                continue
            setattr(journey, field, value or None)

    if "journey_type" in data:
        journey.journey_type = _choice(data.get("journey_type"), VALID_JOURNEY_TYPES)
    if "lifecycle_status" in data:
        journey.lifecycle_status = _choice(
            data.get("lifecycle_status"), VALID_LIFECYCLE_STATUSES
        )
    if "persona_element_id" in data:
        journey.persona_element_id = _to_int(data.get("persona_element_id"))

    # Keep the ArchiMate mirror's name in step, so the element browser does not
    # show a name the journey page no longer uses.
    if journey.archimate_element_id:
        _rename_archimate_element(journey)

    db.session.commit()
    return journey


def delete_journey(journey_id: int) -> bool:
    """Delete a journey with its stages and capability links."""
    journey = get_journey(journey_id)
    if not journey:
        return False

    CustomerJourneyStageCapability.query.filter(
        CustomerJourneyStageCapability.journey_id == journey_id
    ).delete(synchronize_session=False)
    CustomerJourneyStage.query.filter(
        CustomerJourneyStage.journey_id == journey_id
    ).delete(synchronize_session=False)
    db.session.delete(journey)
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Stage CRUD
# ---------------------------------------------------------------------------


def _stage_to_dict(stage: CustomerJourneyStage) -> Dict[str, Any]:
    return {
        "id": stage.id,
        "journey_id": stage.journey_id,
        "stage_order": stage.stage_order,
        "name": stage.name,
        "description": stage.description,
        "customer_goal": stage.customer_goal,
        "touchpoints": _split_lines(stage.touchpoints),
        "touchpoints_text": stage.touchpoints,
        "channel": stage.channel,
        "pain_points": _split_lines(stage.pain_points),
        "pain_points_text": stage.pain_points,
        "sentiment": stage.sentiment,
        # None, not 0: an unrated stage is not a neutral stage.
        "sentiment_score": stage.sentiment_score,
    }


def get_stage(stage_id: int) -> Optional[CustomerJourneyStage]:
    try:
        return CustomerJourneyStage.query.filter(
            CustomerJourneyStage.id == stage_id
        ).first()
    except Exception:
        logger.error("Failed to fetch journey stage %s", stage_id, exc_info=True)
        return None


def create_stage(journey_id: int, data: Dict[str, Any]) -> Optional[CustomerJourneyStage]:
    """Add a stage to a journey, auto-numbering it when the order is blank."""
    journey = get_journey(journey_id)
    if not journey:
        return None

    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")

    stage_order = _to_int(data.get("stage_order"))
    if stage_order is None:
        max_order = (
            db.session.query(db.func.max(CustomerJourneyStage.stage_order))
            .filter(CustomerJourneyStage.journey_id == journey_id)
            .scalar()
        )
        stage_order = (max_order or 0) + 1

    sentiment, sentiment_score = _sentiment(data.get("sentiment"))

    stage = CustomerJourneyStage(
        journey_id=journey_id,
        stage_order=stage_order,
        name=name,
        description=data.get("description") or None,
        customer_goal=data.get("customer_goal") or None,
        touchpoints=data.get("touchpoints") or None,
        channel=(data.get("channel") or "").strip() or None,
        pain_points=data.get("pain_points") or None,
        sentiment=sentiment,
        sentiment_score=sentiment_score,
    )
    db.session.add(stage)
    db.session.commit()
    return stage


def update_stage(stage_id: int, data: Dict[str, Any]) -> Optional[CustomerJourneyStage]:
    stage = get_stage(stage_id)
    if not stage:
        return None

    for field in ("name", "description", "customer_goal", "touchpoints",
                  "channel", "pain_points"):
        if field in data:
            value = data.get(field)
            value = value.strip() if isinstance(value, str) else value
            if field == "name" and not value:
                continue
            setattr(stage, field, value or None)

    if "stage_order" in data:
        stage.stage_order = _to_int(data.get("stage_order")) or stage.stage_order
    if "sentiment" in data:
        stage.sentiment, stage.sentiment_score = _sentiment(data.get("sentiment"))

    db.session.commit()
    return stage


def delete_stage(stage_id: int) -> bool:
    stage = get_stage(stage_id)
    if not stage:
        return False
    CustomerJourneyStageCapability.query.filter(
        CustomerJourneyStageCapability.stage_id == stage_id
    ).delete(synchronize_session=False)
    db.session.delete(stage)
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Stage -> capability -> application
# ---------------------------------------------------------------------------


def _capability_links_by_stage(journey_id: int) -> Dict[int, List[Dict[str, Any]]]:
    """Every stage->capability link for a journey, grouped by stage id."""
    by_stage: Dict[int, List[Dict[str, Any]]] = {}
    try:
        links = CustomerJourneyStageCapability.query.filter(
            CustomerJourneyStageCapability.journey_id == journey_id
        ).all()
    except Exception:
        logger.error(
            "Failed to load capability links for customer journey %s",
            journey_id,
            exc_info=True,
        )
        return by_stage

    capability_ids = sorted({link.capability_id for link in links if link.capability_id})
    capabilities = _capabilities_by_id(capability_ids)

    for link in links:
        capability = capabilities.get(link.capability_id)
        by_stage.setdefault(link.stage_id, []).append(
            {
                "link_id": link.id,
                "capability_id": link.capability_id,
                "capability_name": capability.name if capability else None,
                "capability_code": capability.code if capability else None,
                "capability_level": capability.level if capability else None,
                "support_type": link.support_type,
                "support_level": link.support_level,
                "notes": link.notes,
            }
        )
    for rows in by_stage.values():
        rows.sort(key=lambda row: (row["capability_name"] or "").lower())
    return by_stage


def _capabilities_by_id(capability_ids: List[int]) -> Dict[int, BusinessCapability]:
    if not capability_ids:
        return {}
    try:
        return {
            capability.id: capability
            for capability in BusinessCapability.query.filter(
                BusinessCapability.id.in_(capability_ids)
            ).all()
        }
    except Exception:
        logger.error("Failed to load business capabilities for a journey", exc_info=True)
        return {}


def build_capability_grid(journey_id: int) -> Dict[str, Any]:
    """The capability (rows) x stage (columns) grid for one journey.

    Same shape as the value stream's BIZBOK grid, plus an ``applications`` list
    per capability row: the systems already mapped to that capability, which is
    what makes the journey traceable down to the portfolio.

    Returns the documented empty shape for a journey that does not exist —
    never raises.
    """
    empty: Dict[str, Any] = {
        "journey": None,
        "stages": [],
        "capabilities": [],
        "cells": {},
    }

    journey = get_journey(journey_id)
    if not journey:
        return empty

    try:
        stages = (
            CustomerJourneyStage.query.filter(
                CustomerJourneyStage.journey_id == journey_id
            )
            .order_by(CustomerJourneyStage.stage_order)
            .all()
        )
    except Exception:
        logger.error(
            "Failed to load stages while building the grid for customer journey %s",
            journey_id,
            exc_info=True,
        )
        stages = []

    try:
        links = CustomerJourneyStageCapability.query.filter(
            CustomerJourneyStageCapability.journey_id == journey_id
        ).all()
    except Exception:
        logger.error(
            "Failed to load capability links while building the grid for customer journey %s",
            journey_id,
            exc_info=True,
        )
        links = []

    capability_ids = sorted({link.capability_id for link in links if link.capability_id})
    capabilities = _capabilities_by_id(capability_ids)
    applications = applications_for_capabilities(capability_ids)

    cells: Dict[str, Any] = {}
    for link in links:
        if not link.capability_id or not link.stage_id:
            continue
        cells[f"{link.capability_id}:{link.stage_id}"] = {
            "link_id": link.id,
            "support_type": link.support_type,
            "support_level": link.support_level,
            "notes": link.notes,
        }

    capability_rows = []
    for capability_id in capability_ids:
        capability = capabilities.get(capability_id)
        if capability is None:
            continue
        capability_rows.append(
            {
                "id": capability.id,
                "name": capability.name,
                "code": capability.code,
                "level": capability.level,
                "applications": applications.get(capability_id, []),
            }
        )
    capability_rows.sort(key=lambda row: (row["name"] or "").lower())

    return {
        "journey": {"id": journey.id, "code": journey.code, "name": journey.name},
        "stages": [_stage_to_dict(stage) for stage in stages],
        "capabilities": capability_rows,
        "cells": cells,
    }


def applications_for_capabilities(
    capability_ids: List[int],
) -> Dict[int, List[Dict[str, Any]]]:
    """The applications already mapped to each capability, keyed by capability id.

    A capability with no mapped application yields no entry at all rather than
    an empty list standing in for "we did not look" — the caller distinguishes
    the two by asking for ``.get(id, [])`` only when the lookup succeeded.
    """
    if not capability_ids:
        return {}
    try:
        from app.models.application_capability import ApplicationCapabilityMapping
        from app.models.application_portfolio import ApplicationComponent

        rows = (
            db.session.query(
                ApplicationCapabilityMapping.business_capability_id,
                ApplicationComponent.id,
                ApplicationComponent.name,
            )
            .join(
                ApplicationComponent,
                ApplicationComponent.id
                == ApplicationCapabilityMapping.application_component_id,
            )
            .filter(
                ApplicationCapabilityMapping.business_capability_id.in_(capability_ids)
            )
            .all()
        )
    except Exception:
        logger.error(
            "Failed to load applications behind the capabilities of a journey",
            exc_info=True,
        )
        return {}

    by_capability: Dict[int, List[Dict[str, Any]]] = {}
    for capability_id, application_id, application_name in rows:
        entries = by_capability.setdefault(capability_id, [])
        if not any(entry["id"] == application_id for entry in entries):
            entries.append({"id": application_id, "name": application_name})
    for entries in by_capability.values():
        entries.sort(key=lambda entry: (entry["name"] or "").lower())
    return by_capability


def list_linkable_capabilities(
    journey_id: int, search: str = "", limit: int = 25
) -> List[Dict[str, Any]]:
    """Capabilities not yet a row in this journey's grid, for the picker."""
    try:
        linked_ids = {
            row[0]
            for row in db.session.query(CustomerJourneyStageCapability.capability_id)
            .filter(CustomerJourneyStageCapability.journey_id == journey_id)
            .distinct()
            .all()
        }
    except Exception:
        logger.error(
            "Failed to load linked capability ids for customer journey %s",
            journey_id,
            exc_info=True,
        )
        linked_ids = set()

    try:
        query = BusinessCapability.query
        if linked_ids:
            query = query.filter(~BusinessCapability.id.in_(linked_ids))
        if search:
            query = query.filter(BusinessCapability.name.ilike(f"%{search}%"))
        capabilities = query.order_by(BusinessCapability.name).limit(limit).all()
    except Exception:
        logger.error(
            "Failed to search linkable capabilities for customer journey %s",
            journey_id,
            exc_info=True,
        )
        raise

    return [
        {"id": c.id, "name": c.name, "code": c.code, "level": c.level}
        for c in capabilities
    ]


def upsert_capability_link(
    stage_id: int, capability_id: int, data: Dict[str, Any]
) -> CustomerJourneyStageCapability:
    """Create or update the (stage, capability) cell. Raises on bad input."""
    if not stage_id or not capability_id:
        raise ValueError("stage_id and capability_id are required")

    stage = get_stage(stage_id)
    if not stage:
        raise ValueError("stage not found")

    capability = BusinessCapability.query.filter(
        BusinessCapability.id == capability_id
    ).first()
    if not capability:
        raise ValueError("capability not found")

    support_level = _to_int(data.get("support_level"))
    if support_level is not None:
        support_level = max(1, min(5, support_level))

    support_type = _choice(data.get("support_type"), set(SUPPORT_TYPES))

    link = CustomerJourneyStageCapability.query.filter_by(
        stage_id=stage_id, capability_id=capability_id
    ).first()
    if not link:
        link = CustomerJourneyStageCapability(
            journey_id=stage.journey_id,
            stage_id=stage_id,
            capability_id=capability_id,
        )
        db.session.add(link)

    # journey_id is derived from the stage, never from the request body.
    link.journey_id = stage.journey_id
    link.support_type = support_type
    link.support_level = support_level
    if "notes" in data:
        link.notes = data.get("notes") or None

    db.session.commit()
    return link


def delete_capability_link(stage_id: int, capability_id: int) -> bool:
    link = CustomerJourneyStageCapability.query.filter_by(
        stage_id=stage_id, capability_id=capability_id
    ).first()
    if not link:
        return False
    db.session.delete(link)
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# ArchiMate backbone
# ---------------------------------------------------------------------------


def _sync_archimate_element(journey: CustomerJourney) -> Optional[int]:
    """Mirror a journey into `archimate_elements` and return the new element id.

    A journey that exists only in its own table is a diagram; the point of the
    mirror is that it shows up in the element browser, the layer APIs and the
    traceability views alongside every other business-layer element.

    Returns None (and logs) when the element cannot be created, so a journey is
    still saved rather than the whole write failing — but the caller can tell,
    because ``archimate_element_id`` stays NULL and the detail page says so.
    """
    try:
        from app.models.models import ArchiMateElement

        element = ArchiMateElement(
            name=journey.name,
            type=ARCHIMATE_JOURNEY_TYPE,
            layer=ARCHIMATE_JOURNEY_LAYER,
            description=journey.description
            or f"Customer journey: {journey.name}",
        )
        organization_id = getattr(journey, "organization_id", None)
        if organization_id is not None:
            element.organization_id = organization_id
        db.session.add(element)
        db.session.flush()
        return element.id
    except Exception:
        logger.error(
            "Failed to create the ArchiMate element for customer journey %s",
            getattr(journey, "id", None),
            exc_info=True,
        )
        return None


def _rename_archimate_element(journey: CustomerJourney) -> None:
    try:
        from app.models.models import ArchiMateElement

        element = ArchiMateElement.query.filter(
            ArchiMateElement.id == journey.archimate_element_id
        ).first()
        if element is not None:
            element.name = journey.name
    except Exception:
        logger.error(
            "Failed to rename the ArchiMate element for customer journey %s",
            getattr(journey, "id", None),
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sentiment(raw) -> tuple:
    """Normalise a sentiment label to (label, score).

    An unrecognised or blank label yields ``(None, None)`` — not
    ``("neutral", 0)``, which would put a measurement in the database that
    nobody made.
    """
    if not raw:
        return None, None
    label = str(raw).strip().lower()
    if label not in SENTIMENT_SCALE:
        return None, None
    return label, SENTIMENT_SCALE[label]


def _choice(value, allowed):
    """Keep a value only when it is one of the allowed ones, else None."""
    if value in (None, ""):
        return None
    normalised = str(value).strip().lower()
    return normalised if normalised in allowed else None


def _split_lines(value) -> List[str]:
    if not value:
        return []
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _to_int(value, default=None):
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
