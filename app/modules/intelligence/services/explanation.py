"""Why a worked-out connection exists: the recorded facts behind one derived row.

A derived row stores its chain as relationship ids. This turns that chain back
into the facts a person can check: each drawn relationship in order, the two
elements it joins, who drew it and when, the rule that combined the links, and
the architecture decisions recorded against any element on the way.

Nothing is derived here. The row comes from the derived-fact store's one
accessor (``derived_facts``), the rule's words from the rule table
(``archimate_derivation_service.describe_rule``) and each link's words from the
one wording table (``plain_terms.link_sentence``).

Every read carries the caller's organisation, so an explanation can only name
that organisation's elements, relationships, people and decisions. A chain link
that no longer resolves inside it stays in the list, marked as not recorded,
rather than being dropped or filled in. Every ``href`` is built only for a
record that was just read inside the organisation, so it opens a real page.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import url_for
from werkzeug.routing import BuildError

from app.extensions import db

# Why a value is absent. Each is shown as "not recorded" with its reason; none
# is ever replaced by an invented value.
RELATIONSHIP_NOT_RECORDED = "relationship_not_recorded"
ELEMENT_NOT_RECORDED = "element_not_recorded"
DRAWN_BY_NOT_RECORDED = "drawn_by_not_recorded"
DRAWN_AT_NOT_RECORDED = "drawn_at_not_recorded"
RULE_NOT_RECORDED = "rule_not_recorded"


def _user_label(user) -> Optional[str]:
    first = (getattr(user, "first_name", None) or "").strip()
    last = (getattr(user, "last_name", None) or "").strip()
    full = f"{first} {last}".strip()
    return full or getattr(user, "username", None) or getattr(user, "email", None)


def _element_href(element_id: int) -> Optional[str]:
    try:
        return url_for("archimate.element_impact_graph_page", element_id=element_id)
    except BuildError:  # the page's blueprint did not register: no link, not a dead one
        return None


def _decision_href(decision_id: int) -> Optional[str]:
    try:
        return url_for("arch_decisions.view_decision", decision_id=decision_id)
    except BuildError:
        return None


def explain_fact(organization_id: int, fact: Dict[str, Any]) -> Dict[str, Any]:
    """The explanation of one serialised derived fact of ``organization_id``."""
    from app.models import ArchiMateElement, ArchiMateRelationship
    from app.models.architecture_decision import ArchitectureDecision
    from app.modules.intelligence.services.plain_terms import link_sentence
    from app.services.archimate_derivation_service import describe_rule
    from app.utils.tenant_users import user_in_org

    chain_ids: List[int] = list(fact.get("chain") or [])
    relationships = {}
    if chain_ids:
        rows = db.session.execute(
            db.select(ArchiMateRelationship).where(
                ArchiMateRelationship.id.in_(chain_ids),
                ArchiMateRelationship.organization_id == organization_id,
            )
        ).scalars().all()
        relationships = {r.id: r for r in rows}

    element_ids = {fact.get("source_element_id"), fact.get("target_element_id")}
    element_ids.update(fact.get("chain_element_ids") or [])
    for rel in relationships.values():
        element_ids.update((rel.source_id, rel.target_id))
    element_ids.discard(None)
    elements = {}
    if element_ids:
        rows = db.session.execute(
            db.select(ArchiMateElement).where(
                ArchiMateElement.id.in_(sorted(element_ids)),
                ArchiMateElement.organization_id == organization_id,
            )
        ).scalars().all()
        elements = {e.id: e for e in rows}

    def element(element_id) -> Dict[str, Any]:
        row = elements.get(element_id)
        if row is None:
            return {"id": None, "name": None, "href": None, "reason": ELEMENT_NOT_RECORDED}
        return {
            "id": row.id,
            "name": row.name,
            "type": row.type,
            "layer": row.layer,
            "href": _element_href(row.id),
        }

    people: Dict[int, Optional[str]] = {}

    def drawn_by(user_id) -> Optional[str]:
        if user_id is None:
            return None
        if user_id not in people:
            user = user_in_org(user_id, organization_id)
            people[user_id] = _user_label(user) if user is not None else None
        return people[user_id]

    links = []
    for position, rel_id in enumerate(chain_ids, start=1):
        rel = relationships.get(rel_id)
        if rel is None:
            links.append(
                {
                    "position": position,
                    "relationship_id": None,
                    "resolved": False,
                    "reason": RELATIONSHIP_NOT_RECORDED,
                }
            )
            continue
        source = element(rel.source_id)
        target = element(rel.target_id)
        who = drawn_by(rel.created_by_id)
        links.append(
            {
                "position": position,
                "relationship_id": rel.id,
                "resolved": True,
                "type": rel.type,
                "sentence": link_sentence(
                    source_name=source["name"], target_name=target["name"], relation_type=rel.type
                ),
                "source": source,
                "target": target,
                "drawn_by": who,
                "drawn_by_reason": None if who else DRAWN_BY_NOT_RECORDED,
                "drawn_at": rel.created_at.isoformat() if rel.created_at else None,
                "drawn_at_reason": None if rel.created_at else DRAWN_AT_NOT_RECORDED,
                # How the relationship itself came to exist when nobody drew it
                # (read from a diagram's notation, say); None when stated outright.
                "inferred_from": rel.derived_from,
            }
        )

    decisions = [
        {
            "id": d.id,
            "reference": d.decision_id,
            "title": d.title,
            "status": d.status,
            "href": _decision_href(d.id),
        }
        for d in ArchitectureDecision.affecting_elements(sorted(elements), organization_id)
    ]

    rule = describe_rule(fact.get("rule_id"))
    return {
        "derived_id": fact.get("id"),
        "source": element(fact.get("source_element_id")),
        "target": element(fact.get("target_element_id")),
        "derived_type": fact.get("derived_type"),
        "rule_id": fact.get("rule_id"),
        "rule": rule,
        "rule_reason": None if rule else RULE_NOT_RECORDED,
        "depth": fact.get("depth"),
        "stale": bool(fact.get("stale")),
        "computed_at": fact.get("computed_at"),
        "links": links,
        "complete": bool(links) and all(link["resolved"] for link in links),
        "decisions": decisions,
    }


def explain_derived_fact(organization_id: int, derived_id: int) -> Optional[Dict[str, Any]]:
    """The explanation of derived row ``derived_id``, or ``None`` when that row is
    not one of ``organization_id``'s (another organisation's id reads as absent)."""
    from app.modules.intelligence.services.derived_facts import get_derived_fact

    fact = get_derived_fact(organization_id, derived_id, include_stale=True)
    if fact is None:
        return None
    return explain_fact(organization_id, fact)


__all__ = ["explain_derived_fact", "explain_fact"]
