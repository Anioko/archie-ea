"""System of record for data entities, undeclared copies and master data domains.

One answer to "which application is authoritative for this data?": the
``DataEntity.system_of_record_application_id`` column, mirrored as an ArchiMate
Serving relationship (application element -> data object element). The older
free-text ``DataEntity.system_of_record`` is kept in step with the declared
application's name so the two never disagree.

An application "holds" an entity when it has a ``DataObject`` (an application
data object) whose name or table name matches the entity's name, business name
or technical name. Every application that holds an entity other than its
declared system of record is a copy of it.
"""

import logging
import re
from datetime import datetime

from sqlalchemy import select

from app import db
from app.models.application_layer import DataObject
from app.models.application_portfolio import ApplicationComponent
from app.models.process_data import BusinessProcess, DataDomain, DataEntity, process_data_flow

logger = logging.getLogger(__name__)


class DataSorError(Exception):
    """A declaration that cannot be made; the message is shown to the user."""


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _entity_keys(entity):
    keys = {_norm(entity.name), _norm(entity.business_name), _norm(entity.technical_name)}
    keys.discard("")
    return keys


def _holders_by_entity(org_id, entities):
    """{entity_id: {application_id: matching data object name}} for one organisation."""
    if not entities:
        return {}
    rows = (
        db.session.query(
            DataObject.name, DataObject.table_name, DataObject.application_component_id
        )
        .filter(
            DataObject.organization_id == org_id,
            DataObject.application_component_id.isnot(None),
        )
        .all()
    )
    by_key = {}
    for name, table_name, app_id in rows:
        for key in {_norm(name), _norm(table_name)} - {""}:
            by_key.setdefault(key, {}).setdefault(app_id, name)
    result = {}
    for entity in entities:
        holders = {}
        for key in _entity_keys(entity):
            for app_id, obj_name in by_key.get(key, {}).items():
                holders.setdefault(app_id, obj_name)
        result[entity.id] = holders
    return result


def _application_names(org_id, app_ids):
    if not app_ids:
        return {}
    rows = (
        db.session.query(ApplicationComponent.id, ApplicationComponent.name)
        .filter(
            ApplicationComponent.organization_id == org_id,
            ApplicationComponent.id.in_(list(app_ids)),
        )
        .all()
    )
    return dict(rows)


def get_application(org_id, application_id):
    """The application, only if it belongs to this organisation."""
    if not application_id:
        return None
    return (
        db.session.query(ApplicationComponent)
        .filter(
            ApplicationComponent.id == application_id,
            ApplicationComponent.organization_id == org_id,
        )
        .first()
    )


def get_entity(org_id, entity_id):
    return (
        db.session.query(DataEntity)
        .filter(DataEntity.id == entity_id, DataEntity.organization_id == org_id)
        .first()
    )


def get_domain(org_id, domain_id):
    return (
        db.session.query(DataDomain)
        .filter(DataDomain.id == domain_id, DataDomain.organization_id == org_id)
        .first()
    )


def _serving_link_query(app_element_id, entity_element_id):
    from app.models.models import ArchiMateRelationship

    return db.session.query(ArchiMateRelationship).filter_by(
        type="serving", source_id=app_element_id, target_id=entity_element_id
    )


def declare_system_of_record(org_id, entity_id, application_id, user_id=None):
    """Declare the application that is authoritative for a data entity.

    Writes the column, keeps the text label in step, and records the ArchiMate
    Serving relationship. Redeclaring replaces the previous application's
    relationship. Returns the entity.
    """
    entity = get_entity(org_id, entity_id)
    if entity is None:
        raise DataSorError("That data entity was not found.")
    application = get_application(org_id, application_id)
    if application is None:
        raise DataSorError("Pick an application from your portfolio.")
    if not application.archimate_element_id:
        raise DataSorError(
            "That application has no ArchiMate element yet, so the link cannot be modelled."
        )
    if not entity.archimate_element_id:
        raise DataSorError(
            "That data entity has no ArchiMate element yet, so the link cannot be modelled."
        )

    previous_id = entity.system_of_record_application_id
    if previous_id and previous_id != application.id:
        previous = get_application(org_id, previous_id)
        if previous is not None and previous.archimate_element_id:
            for stale in _serving_link_query(
                previous.archimate_element_id, entity.archimate_element_id
            ).all():
                db.session.delete(stale)

    if not _serving_link_query(application.archimate_element_id, entity.archimate_element_id).first():
        from app.models.models import ArchiMateElement
        from app.modules.architecture.services.archimate_relationship_service import (
            ArchiMateRelationshipService,
        )

        source = db.session.get(ArchiMateElement, application.archimate_element_id)
        target = db.session.get(ArchiMateElement, entity.archimate_element_id)
        link = ArchiMateRelationshipService.create_relationship(
            source, target, "serving", entity.architecture_id
        )
        if link is None:
            raise DataSorError("The ArchiMate relationship could not be recorded.")

    entity.system_of_record_application_id = application.id
    entity.system_of_record = application.name
    entity.system_of_record_declared_by_id = user_id
    entity.system_of_record_declared_at = datetime.utcnow()
    db.session.commit()
    return entity


def declare_golden_source(org_id, domain_id, application_id):
    """Set (or, with no application, clear) the golden source of a data domain."""
    domain = get_domain(org_id, domain_id)
    if domain is None:
        raise DataSorError("That data domain was not found.")
    if application_id:
        application = get_application(org_id, application_id)
        if application is None:
            raise DataSorError("Pick an application from your portfolio.")
        domain.golden_source_application_id = application.id
    else:
        domain.golden_source_application_id = None
    db.session.commit()
    return domain


def entity_holders(org_id, entity):
    """Applications holding this entity, each labelled by their role.

    role is ``system_of_record`` for the declared application, ``copy`` for any
    other holder once one is declared, and ``undeclared`` while none is.
    """
    holders = _holders_by_entity(org_id, [entity]).get(entity.id, {})
    names = _application_names(org_id, set(holders) | {entity.system_of_record_application_id})
    declared = entity.system_of_record_application_id
    rows = []
    for app_id, object_name in holders.items():
        if declared and app_id == declared:
            role = "system_of_record"
        elif declared:
            role = "copy"
        else:
            role = "undeclared"
        rows.append(
            {
                "application_id": app_id,
                "application_name": names.get(app_id, "—"),
                "data_object_name": object_name,
                "role": role,
            }
        )
    rows.sort(key=lambda r: (r["role"] != "system_of_record", r["application_name"]))
    return rows


def consumers_by_entity(org_id, entity_ids):
    """{entity_id: sorted names of the business processes that take it as an input}."""
    if not entity_ids:
        return {}
    rows = db.session.execute(
        select(process_data_flow.c.data_entity_id, BusinessProcess.name)
        .join(BusinessProcess, BusinessProcess.id == process_data_flow.c.process_id)
        .where(
            process_data_flow.c.data_entity_id.in_(list(entity_ids)),
            process_data_flow.c.flow_type == "input",
            BusinessProcess.organization_id == org_id,
        )
    ).all()
    result = {}
    for entity_id, name in rows:
        result.setdefault(entity_id, set()).add(name)
    return {k: sorted(v) for k, v in result.items()}


def list_entities(org_id):
    """Every entity in the organisation with its declared system of record."""
    entities = (
        db.session.query(DataEntity)
        .filter(DataEntity.organization_id == org_id)
        .order_by(DataEntity.name)
        .all()
    )
    names = _application_names(org_id, {e.system_of_record_application_id for e in entities})
    return [
        {"entity": e, "system_of_record_name": names.get(e.system_of_record_application_id)}
        for e in entities
    ]


def undeclared_copies(org_id):
    """Entities held by more than one application with no declared system of record.

    Ranked by the number of business processes that consume the entity.
    """
    entities = (
        db.session.query(DataEntity)
        .filter(
            DataEntity.organization_id == org_id,
            DataEntity.system_of_record_application_id.is_(None),
        )
        .all()
    )
    holders = _holders_by_entity(org_id, entities)
    flagged = [e for e in entities if len(holders.get(e.id, {})) > 1]
    names = _application_names(
        org_id, {app_id for e in flagged for app_id in holders[e.id]}
    )
    consumers = consumers_by_entity(org_id, [e.id for e in flagged])
    rows = [
        {
            "entity": e,
            "applications": sorted(names.get(a, "—") for a in holders[e.id]),
            "consumer_count": len(consumers.get(e.id, [])),
        }
        for e in flagged
    ]
    rows.sort(key=lambda r: (-r["consumer_count"], r["entity"].name))
    return rows


def master_domains(org_id):
    """Master data domains with golden source, entities and their consumers."""
    domains = (
        db.session.query(DataDomain)
        .filter(DataDomain.organization_id == org_id, DataDomain.domain_type == "master")
        .order_by(DataDomain.name)
        .all()
    )
    names = _application_names(org_id, {d.golden_source_application_id for d in domains})
    entity_ids = [e.id for d in domains for e in d.entities]
    consumers = consumers_by_entity(org_id, entity_ids)
    return [
        {
            "domain": d,
            "golden_source_name": names.get(d.golden_source_application_id),
            "entities": [
                {"entity": e, "consumers": consumers.get(e.id, [])}
                for e in sorted(d.entities, key=lambda e: e.name)
            ],
        }
        for d in domains
    ]
