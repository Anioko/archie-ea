"""Business information model service — the BIZBOK information map.

Joins four things Archie already held separately:

* ``DataDomain``      — the grouping (Customer, Product, Finance)
* ``BusinessObject``  — the object itself, already ArchiMate-mirrored
* ``CapabilityObjectCrud`` — capability x object CRUD (the one new table)
* ``DataObjectStorage``    — which application masters / consumes the object

Object-to-object structure (an Order **composes** Order Lines) is written as an
``ArchiMateRelationship`` between the two objects' business-layer elements, not
into a private table — ArchiMate is the backbone, so the element browser, the
traceability chain and the viewpoint editor all see these relationships for
free.

Failure policy: read paths log and return a neutral empty shape so a page can
render an honest empty state rather than 500. Write paths raise, so the route
can roll back and tell the user the write failed. Neither path ever substitutes
a plausible number for a missing one — a count that could not be computed is
``None`` and renders as an em dash.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models.archimate_core import ArchiMateRelationship
from app.models.business_capabilities import BusinessCapability
from app.models.business_layer import BusinessObject
from app.models.information_model import CRUD_FLAGS, CapabilityObjectCrud
from app.models.process_data import DataDomain
from app.models.relationship_tables import DataObjectStorage

logger = logging.getLogger(__name__)

# Values stored on BusinessObject.data_classification. Capitalised because
# BusinessObject.is_high_risk already compares against this spelling.
DATA_CLASSIFICATIONS = ("Public", "Internal", "Confidential", "Restricted")

OBJECT_TYPES = ("Master Data", "Transactional", "Reference", "Analytical")

# ArchiMate relationship types that carry meaning between two business objects.
# Deliberately a subset: a "serving" relationship between two passive objects
# is not something ArchiMate 3.2 permits.
OBJECT_RELATIONSHIP_TYPES = ("composition", "aggregation", "association", "specialization")

# Which part an application plays for an object.
SYSTEM_ROLES = ("system_of_record", "system_of_entry", "consumer", "replica")

SYSTEM_ROLE_LABELS = {
    "system_of_record": "System of Record",
    "system_of_entry": "System of Entry",
    "consumer": "Consumer",
    "replica": "Replica",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _clean(value: Any) -> Optional[str]:
    """Trim a form value; empty string becomes None so the column stays NULL."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "on", "yes"}


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _crud_letters(row: CapabilityObjectCrud) -> Optional[str]:
    return row.crud_letters


# ---------------------------------------------------------------------------
# Data domains
# ---------------------------------------------------------------------------


def list_domains() -> List[Dict[str, Any]]:
    """Every data domain with the number of business objects filed under it.

    ``object_count`` is ``None`` when the count could not be taken, which the
    template renders as an em dash — a 0 there would be indistinguishable from
    a domain that genuinely holds nothing.
    """
    try:
        domains = DataDomain.query.order_by(DataDomain.name).all()
    except Exception:
        logger.error("Failed to list data domains", exc_info=True)
        return []

    results: List[Dict[str, Any]] = []
    for domain in domains:
        try:
            object_count = BusinessObject.query.filter(
                BusinessObject.data_domain_id == domain.id
            ).count()
        except Exception:
            logger.warning(
                "Failed to count business objects in domain %s", domain.id, exc_info=True
            )
            object_count = None

        results.append(
            {
                "id": domain.id,
                "code": domain.code,
                "name": domain.name,
                "description": domain.description,
                "domain_type": domain.domain_type,
                "criticality": domain.criticality,
                "data_owner": domain.data_owner,
                "data_steward": domain.data_steward,
                "data_classification": domain.data_classification,
                "object_count": object_count,
            }
        )
    return results


def create_domain(data: Dict[str, Any]) -> DataDomain:
    """Create a data domain. Raises on failure so the caller can roll back."""
    name = _clean(data.get("name"))
    if not name:
        raise ValueError("A data domain needs a name.")

    domain = DataDomain(
        name=name,
        code=_clean(data.get("code")),
        description=_clean(data.get("description")),
        domain_type=_clean(data.get("domain_type")),
        criticality=_clean(data.get("criticality")),
        data_owner=_clean(data.get("data_owner")),
        data_steward=_clean(data.get("data_steward")),
        data_classification=_clean(data.get("data_classification")),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(domain)
    db.session.commit()
    return domain


def update_domain(domain_id: int, data: Dict[str, Any]) -> Optional[DataDomain]:
    domain = DataDomain.query.filter(DataDomain.id == domain_id).first()
    if not domain:
        return None

    if "name" in data:
        name = _clean(data.get("name"))
        if not name:
            raise ValueError("A data domain needs a name.")
        domain.name = name

    for field in (
        "code",
        "description",
        "domain_type",
        "criticality",
        "data_owner",
        "data_steward",
        "data_classification",
    ):
        if field in data:
            setattr(domain, field, _clean(data.get(field)))

    domain.updated_at = datetime.utcnow()
    db.session.commit()
    return domain


def delete_domain(domain_id: int) -> bool:
    """Delete a domain, leaving its objects in place but unfiled.

    Deliberately not a cascade: the objects are the record, the domain is a
    grouping. Silently destroying a Customer object because somebody tidied up
    a folder would be unrecoverable.
    """
    domain = DataDomain.query.filter(DataDomain.id == domain_id).first()
    if not domain:
        return False

    BusinessObject.query.filter(
        BusinessObject.data_domain_id == domain_id,
        BusinessObject.organization_id == domain.organization_id,
    ).update({"data_domain_id": None}, synchronize_session=False)

    db.session.delete(domain)
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Business objects
# ---------------------------------------------------------------------------


def _object_summary(obj: BusinessObject, domain_names: Dict[int, str]) -> Dict[str, Any]:
    return {
        "id": obj.id,
        "code": obj.code,
        "name": obj.name,
        "description": obj.description,
        "object_type": obj.object_type,
        "data_classification": obj.data_classification,
        "data_steward": obj.data_steward,
        "data_domain_id": obj.data_domain_id,
        "domain_name": domain_names.get(obj.data_domain_id),
        "contains_pii": bool(obj.contains_pii),
        "archimate_element_id": obj.archimate_element_id,
    }


def list_objects(domain_id: Optional[int] = None, search: str = "") -> List[Dict[str, Any]]:
    """Business objects, optionally filtered by domain and/or name substring."""
    try:
        query = BusinessObject.query
        if domain_id is not None:
            query = query.filter(BusinessObject.data_domain_id == domain_id)
        term = (search or "").strip()
        if term:
            query = query.filter(BusinessObject.name.ilike(f"%{term}%"))
        objects = query.order_by(BusinessObject.name).all()
    except Exception:
        logger.error("Failed to list business objects", exc_info=True)
        return []

    domain_names = _domain_name_map()
    return [_object_summary(obj, domain_names) for obj in objects]


def _domain_name_map() -> Dict[int, str]:
    try:
        return {d.id: d.name for d in DataDomain.query.all()}
    except Exception:
        logger.warning("Failed to load data domain names", exc_info=True)
        return {}


def build_information_map() -> Dict[str, Any]:
    """Domains, each with the objects filed under it, plus the unfiled ones.

    The shape the index page renders. ``unfiled`` is a real group, not an
    error: an object with no domain is a modelling gap the architect should be
    able to see and fix, so it is shown rather than hidden.
    """
    domains = list_domains()
    objects = list_objects()

    by_domain: Dict[Optional[int], List[Dict[str, Any]]] = {}
    for obj in objects:
        by_domain.setdefault(obj["data_domain_id"], []).append(obj)

    for domain in domains:
        domain["objects"] = by_domain.get(domain["id"], [])

    return {
        "domains": domains,
        "unfiled": by_domain.get(None, []),
        "object_count": len(objects),
    }


def get_object(object_id: int) -> Optional[BusinessObject]:
    try:
        return BusinessObject.query.filter(BusinessObject.id == object_id).first()
    except Exception:
        logger.error("Failed to fetch business object %s", object_id, exc_info=True)
        return None


def create_object(data: Dict[str, Any]) -> BusinessObject:
    """Create a business object.

    An ORM insert, so the ``before_insert`` listener in
    ``app/models/business_layer.py`` fires and mirrors the row into the
    ArchiMate business layer as a ``BusinessObject`` element. A Core insert
    would skip that and leave the object invisible to the element browser and
    to the AI assistant, which reads the ArchiMate layer.
    """
    name = _clean(data.get("name"))
    if not name:
        raise ValueError("A business object needs a name.")

    obj = BusinessObject(
        name=name,
        code=_clean(data.get("code")),
        description=_clean(data.get("description")),
        data_domain_id=_to_int(data.get("data_domain_id")),
        object_type=_clean(data.get("object_type")),
        data_classification=_clean(data.get("data_classification")),
        business_domain=_clean(data.get("business_domain")),
        data_steward=_clean(data.get("data_steward")),
        data_custodian=_clean(data.get("data_custodian")),
        contains_pii=_to_bool(data.get("contains_pii")),
        gdpr_scope=_to_bool(data.get("gdpr_scope")),
        retention_period_days=_to_int(data.get("retention_period_days")),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(obj)
    db.session.commit()
    return obj


def update_object(object_id: int, data: Dict[str, Any]) -> Optional[BusinessObject]:
    obj = get_object(object_id)
    if not obj:
        return None

    if "name" in data:
        name = _clean(data.get("name"))
        if not name:
            raise ValueError("A business object needs a name.")
        obj.name = name

    for field in (
        "code",
        "description",
        "object_type",
        "data_classification",
        "business_domain",
        "data_steward",
        "data_custodian",
    ):
        if field in data:
            setattr(obj, field, _clean(data.get(field)))

    if "data_domain_id" in data:
        obj.data_domain_id = _to_int(data.get("data_domain_id"))
    if "retention_period_days" in data:
        obj.retention_period_days = _to_int(data.get("retention_period_days"))
    # Checkboxes are absent from the form body when unticked, so these read the
    # whole submitted mapping rather than testing for the key.
    obj.contains_pii = _to_bool(data.get("contains_pii"))
    obj.gdpr_scope = _to_bool(data.get("gdpr_scope"))

    obj.updated_at = datetime.utcnow()
    db.session.commit()
    return obj


def delete_object(object_id: int) -> bool:
    """Delete a business object and the links that only exist to describe it."""
    obj = get_object(object_id)
    if not obj:
        return False

    element_id = obj.archimate_element_id
    org_id = obj.organization_id

    CapabilityObjectCrud.query.filter(
        CapabilityObjectCrud.business_object_id == object_id,
        CapabilityObjectCrud.organization_id == org_id,
    ).delete(synchronize_session=False)
    DataObjectStorage.query.filter(
        DataObjectStorage.business_object_id == object_id,
        DataObjectStorage.organization_id == org_id,
    ).delete(synchronize_session=False)

    if element_id:
        ArchiMateRelationship.query.filter(
            db.or_(
                ArchiMateRelationship.source_id == element_id,
                ArchiMateRelationship.target_id == element_id,
            )
        ).delete(synchronize_session=False)

    db.session.delete(obj)
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Object-to-object relationships (ArchiMate)
# ---------------------------------------------------------------------------


def _objects_by_element_id() -> Dict[int, BusinessObject]:
    try:
        rows = BusinessObject.query.filter(
            BusinessObject.archimate_element_id.isnot(None)
        ).all()
    except Exception:
        logger.error("Failed to index business objects by element id", exc_info=True)
        return {}
    return {row.archimate_element_id: row for row in rows}


def list_object_relationships(object_id: int) -> Dict[str, List[Dict[str, Any]]]:
    """Outgoing and incoming relationships to other business objects.

    Only relationships whose other end is itself a business object are listed —
    an ``access`` relationship from an application component is shown by the
    applications panel instead, and mixing the two would misdescribe both.
    """
    empty: Dict[str, List[Dict[str, Any]]] = {"outgoing": [], "incoming": []}
    obj = get_object(object_id)
    if not obj or not obj.archimate_element_id:
        return empty

    element_id = obj.archimate_element_id
    by_element = _objects_by_element_id()

    try:
        rows = ArchiMateRelationship.query.filter(
            db.or_(
                ArchiMateRelationship.source_id == element_id,
                ArchiMateRelationship.target_id == element_id,
            )
        ).all()
    except Exception:
        logger.error("Failed to load relationships for object %s", object_id, exc_info=True)
        return empty

    for rel in rows:
        if rel.source_id == element_id:
            other = by_element.get(rel.target_id)
            bucket = "outgoing"
        else:
            other = by_element.get(rel.source_id)
            bucket = "incoming"
        if other is None or other.id == object_id:
            continue
        empty[bucket].append(
            {
                "id": rel.id,
                "type": rel.type,
                "description": rel.description,
                "object_id": other.id,
                "object_name": other.name,
                "object_code": other.code,
            }
        )

    empty["outgoing"].sort(key=lambda r: (r["type"] or "", r["object_name"] or ""))
    empty["incoming"].sort(key=lambda r: (r["type"] or "", r["object_name"] or ""))
    return empty


def create_object_relationship(
    source_object_id: int,
    target_object_id: int,
    relationship_type: str,
    description: Optional[str] = None,
) -> ArchiMateRelationship:
    """Relate two business objects through the ArchiMate layer."""
    if source_object_id == target_object_id:
        raise ValueError("A business object cannot be related to itself.")

    relationship_type = (relationship_type or "").strip().lower()
    if relationship_type not in OBJECT_RELATIONSHIP_TYPES:
        raise ValueError(
            "relationship_type must be one of: " + ", ".join(OBJECT_RELATIONSHIP_TYPES)
        )

    source = get_object(source_object_id)
    target = get_object(target_object_id)
    if not source or not target:
        raise ValueError("Both business objects must exist.")
    if not source.archimate_element_id or not target.archimate_element_id:
        raise ValueError(
            "Both business objects need an ArchiMate element before they can be related."
        )

    existing = ArchiMateRelationship.query.filter(
        ArchiMateRelationship.type == relationship_type,
        ArchiMateRelationship.source_id == source.archimate_element_id,
        ArchiMateRelationship.target_id == target.archimate_element_id,
    ).first()
    if existing:
        if description is not None:
            existing.description = _clean(description)
            db.session.commit()
        return existing

    rel = ArchiMateRelationship(
        type=relationship_type,
        source_id=source.archimate_element_id,
        target_id=target.archimate_element_id,
        description=_clean(description),
    )
    db.session.add(rel)
    db.session.commit()
    return rel


def delete_object_relationship(relationship_id: int) -> bool:
    rel = ArchiMateRelationship.query.filter(
        ArchiMateRelationship.id == relationship_id
    ).first()
    if not rel:
        return False
    db.session.delete(rel)
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Capability x object CRUD matrix
# ---------------------------------------------------------------------------


def _crud_cell_payload(row: CapabilityObjectCrud) -> Dict[str, Any]:
    return {
        "id": row.id,
        "capability_id": row.capability_id,
        "business_object_id": row.business_object_id,
        "creates": bool(row.creates),
        "reads": bool(row.reads),
        "updates": bool(row.updates),
        "deletes": bool(row.deletes),
        "is_owning_capability": bool(row.is_owning_capability),
        "letters": _crud_letters(row),
        "notes": row.notes,
    }


def build_crud_matrix(domain_id: Optional[int] = None) -> Dict[str, Any]:
    """Capability x business-object CRUD grid.

    Rows are the capabilities that already say something about at least one
    object — an unmapped capability is added by the picker, not by listing
    every capability in the model, which for a real taxonomy is thousands.

    Returns the documented empty shape on failure, never raises.
    """
    empty = {"objects": [], "capabilities": [], "cells": {}, "domain_id": domain_id}

    try:
        object_query = BusinessObject.query
        if domain_id is not None:
            object_query = object_query.filter(BusinessObject.data_domain_id == domain_id)
        objects = object_query.order_by(BusinessObject.name).all()
    except Exception:
        logger.error("Failed to load business objects for the CRUD matrix", exc_info=True)
        return empty

    object_ids = [o.id for o in objects]
    if not object_ids:
        return {**empty, "objects": []}

    try:
        rows = CapabilityObjectCrud.query.filter(
            CapabilityObjectCrud.business_object_id.in_(object_ids)
        ).all()
    except Exception:
        logger.error("Failed to load CRUD cells", exc_info=True)
        return empty

    capability_ids = sorted({r.capability_id for r in rows})
    capabilities: List[Dict[str, Any]] = []
    if capability_ids:
        try:
            for cap in (
                BusinessCapability.query.filter(BusinessCapability.id.in_(capability_ids))
                .order_by(BusinessCapability.name)
                .all()
            ):
                capabilities.append({"id": cap.id, "name": cap.name, "code": cap.code})
        except Exception:
            logger.error("Failed to load capabilities for the CRUD matrix", exc_info=True)
            return empty

    cells = {f"{r.capability_id}:{r.business_object_id}": _crud_cell_payload(r) for r in rows}

    domain_names = _domain_name_map()
    return {
        "objects": [_object_summary(o, domain_names) for o in objects],
        "capabilities": capabilities,
        "cells": cells,
        "domain_id": domain_id,
    }


def upsert_crud_cell(
    capability_id: int, business_object_id: int, data: Dict[str, Any]
) -> CapabilityObjectCrud:
    """Create or update one CRUD cell. Raises on a bad reference."""
    capability = BusinessCapability.query.filter(
        BusinessCapability.id == capability_id
    ).first()
    if not capability:
        raise ValueError("Capability not found.")
    obj = get_object(business_object_id)
    if not obj:
        raise ValueError("Business object not found.")

    row = CapabilityObjectCrud.query.filter(
        CapabilityObjectCrud.capability_id == capability_id,
        CapabilityObjectCrud.business_object_id == business_object_id,
    ).first()
    if row is None:
        row = CapabilityObjectCrud(
            capability_id=capability_id,
            business_object_id=business_object_id,
            created_at=datetime.utcnow(),
        )
        db.session.add(row)

    for field in CRUD_FLAGS:
        if field in data:
            setattr(row, field, _to_bool(data.get(field)))
    if "is_owning_capability" in data:
        row.is_owning_capability = _to_bool(data.get("is_owning_capability"))
    if "notes" in data:
        row.notes = _clean(data.get("notes"))

    row.updated_at = datetime.utcnow()
    db.session.commit()
    return row


def delete_crud_cell(capability_id: int, business_object_id: int) -> bool:
    row = CapabilityObjectCrud.query.filter(
        CapabilityObjectCrud.capability_id == capability_id,
        CapabilityObjectCrud.business_object_id == business_object_id,
    ).first()
    if not row:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


def list_object_capabilities(business_object_id: int) -> List[Dict[str, Any]]:
    """The CRUD rows for one object, with capability names attached."""
    try:
        rows = CapabilityObjectCrud.query.filter(
            CapabilityObjectCrud.business_object_id == business_object_id
        ).all()
    except Exception:
        logger.error(
            "Failed to load capability CRUD for object %s", business_object_id, exc_info=True
        )
        return []

    if not rows:
        return []

    try:
        names = {
            cap.id: (cap.name, cap.code)
            for cap in BusinessCapability.query.filter(
                BusinessCapability.id.in_([r.capability_id for r in rows])
            ).all()
        }
    except Exception:
        logger.error("Failed to load capability names", exc_info=True)
        names = {}

    result = []
    for row in rows:
        name, code = names.get(row.capability_id, (None, None))
        payload = _crud_cell_payload(row)
        payload["capability_name"] = name
        payload["capability_code"] = code
        result.append(payload)
    result.sort(key=lambda r: (r["capability_name"] or ""))
    return result


def search_capabilities(search: str = "", limit: int = 25) -> List[Dict[str, Any]]:
    """Capability picker results. Raises nothing; an error is an empty list logged."""
    try:
        query = BusinessCapability.query
        term = (search or "").strip()
        if term:
            query = query.filter(
                db.or_(
                    BusinessCapability.name.ilike(f"%{term}%"),
                    BusinessCapability.code.ilike(f"%{term}%"),
                )
            )
        rows = query.order_by(BusinessCapability.name).limit(max(1, min(limit, 100))).all()
    except Exception:
        logger.error("Capability search failed", exc_info=True)
        raise
    return [{"id": c.id, "name": c.name, "code": c.code} for c in rows]


def search_objects(
    search: str = "", limit: int = 25, exclude_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    query = BusinessObject.query
    term = (search or "").strip()
    if term:
        query = query.filter(
            db.or_(
                BusinessObject.name.ilike(f"%{term}%"),
                BusinessObject.code.ilike(f"%{term}%"),
            )
        )
    if exclude_id is not None:
        query = query.filter(BusinessObject.id != exclude_id)
    rows = query.order_by(BusinessObject.name).limit(max(1, min(limit, 100))).all()
    return [{"id": o.id, "name": o.name, "code": o.code} for o in rows]


# ---------------------------------------------------------------------------
# Application mastering (system of record vs consumer)
# ---------------------------------------------------------------------------


def list_object_applications(business_object_id: int) -> List[Dict[str, Any]]:
    """Which applications hold this object, and in what role.

    ``application_name`` is ``None`` for a legacy row whose application cannot
    be resolved — the template renders an em dash. Guessing a name from the
    other, ambiguous FK would be inventing a system of record.
    """
    try:
        rows = DataObjectStorage.query.filter(
            DataObjectStorage.business_object_id == business_object_id
        ).all()
    except Exception:
        logger.error(
            "Failed to load application links for object %s", business_object_id, exc_info=True
        )
        return []

    result = []
    for row in rows:
        application = None
        try:
            application = row.application
        except Exception:
            logger.warning(
                "Failed to resolve application for storage link %s", row.id, exc_info=True
            )

        result.append(
            {
                "id": row.id,
                "application_id": row.application_id,
                "application_name": getattr(application, "name", None),
                "system_role": row.system_role,
                "system_role_label": SYSTEM_ROLE_LABELS.get(row.system_role),
                "is_master_source": bool(row.is_master_source),
                "storage_type": row.storage_type,
                "notes": row.notes,
            }
        )
    result.sort(key=lambda r: (r["system_role"] != "system_of_record", r["application_name"] or ""))
    return result


def set_object_application(
    business_object_id: int, application_id: int, data: Dict[str, Any]
) -> DataObjectStorage:
    """Record (or re-record) the part one application plays for one object."""
    from app.models.application_portfolio import ApplicationComponent

    obj = get_object(business_object_id)
    if not obj:
        raise ValueError("Business object not found.")

    application = ApplicationComponent.query.filter(
        ApplicationComponent.id == application_id
    ).first()
    if not application:
        raise ValueError("Application not found.")

    system_role = (_clean(data.get("system_role")) or "").lower() or None
    if system_role is not None and system_role not in SYSTEM_ROLES:
        raise ValueError("system_role must be one of: " + ", ".join(SYSTEM_ROLES))

    element_id = getattr(application, "archimate_element_id", None)
    if not element_id:
        raise ValueError(
            "The application has no ArchiMate element yet, so the link cannot be recorded."
        )

    row = DataObjectStorage.query.filter(
        DataObjectStorage.business_object_id == business_object_id,
        DataObjectStorage.application_id == application_id,
    ).first()
    if row is None:
        row = DataObjectStorage(
            business_object_id=business_object_id,
            application_id=application_id,
            application_component_id=element_id,
            created_at=datetime.utcnow(),
        )
        db.session.add(row)
    else:
        row.application_component_id = element_id

    row.system_role = system_role
    row.is_master_source = system_role == "system_of_record"
    if "storage_type" in data:
        row.storage_type = _clean(data.get("storage_type"))
    if "notes" in data:
        row.notes = _clean(data.get("notes"))
    row.updated_at = datetime.utcnow()

    db.session.commit()
    return row


def delete_object_application(link_id: int) -> bool:
    row = DataObjectStorage.query.filter(DataObjectStorage.id == link_id).first()
    if not row:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Object detail
# ---------------------------------------------------------------------------


def get_object_detail(object_id: int) -> Optional[Dict[str, Any]]:
    """Everything the object detail page renders, or None when it does not exist."""
    obj = get_object(object_id)
    if not obj:
        return None

    domain_names = _domain_name_map()
    detail = _object_summary(obj, domain_names)
    detail.update(
        {
            "business_domain": obj.business_domain,
            "data_custodian": obj.data_custodian,
            "gdpr_scope": bool(obj.gdpr_scope),
            "retention_period_days": obj.retention_period_days,
            "operational_status": obj.operational_status,
            "relationships": list_object_relationships(object_id),
            "capabilities": list_object_capabilities(object_id),
            "applications": list_object_applications(object_id),
        }
    )
    detail["system_of_record"] = next(
        (
            app_link["application_name"]
            for app_link in detail["applications"]
            if app_link["system_role"] == "system_of_record"
        ),
        None,
    )
    return detail
