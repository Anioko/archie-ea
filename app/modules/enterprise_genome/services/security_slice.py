"""
Enterprise Genome — SECURITY domain slice builder.

Deterministic, zero-LLM emitter that projects the organisation's control ->
requirement bindings into a SOC 2 / ISO 27001 control-to-requirement matrix
genome slice. This is the "traceability is the product" slice from
docs/adr/0010-enterprise-genome.md and 04_domains.md §5.

Design contract (02_schema.md §3.2 SecuritySlice, adapted to a minimal,
self-contained slice so the BUSINESS/DATA peer slices compose with it):

  * ONE named store.  The authoritative store is ``compliance_requirements`` —
    the row that BINDS a control to the requirement it satisfies. Everything
    else (``compliance_controls``, ``regulatory_frameworks``,
    ``archimate_elements``) is read only as a foreign-key lookup HANGING OFF
    that binding row, never as a second, possibly-disagreeing source of the
    same fact (ADR 0008). The store is labelled in the envelope
    (``store = "compliance_requirements"``).

  * STRUCTURAL, NON-OPTIONAL provenance.  Security controls are not native
    ArchiMate element types (04_domains.md) — they live on side tables. The
    provenance we can carry, and the one an auditor follows, is
    ``control -> the requirement it satisfies -> the motivation ArchiMate
    element that requirement realises``. Every emitted node therefore carries
    ``provenance.archimate_element_id`` (the requirement element's id). A
    binding whose requirement has no resolvable ArchiMate element in the org is
    EXCLUDED — it cannot make it into the slice, because a node without
    provenance is not a legal node. ``build_security_slice`` re-asserts this
    with an assertion so the invariant cannot silently rot.

  * DETERMINISTIC.  No wall-clock, no randomness, ordering fixed. The slice
    dict is a pure function of (organization_id, database contents), so
    ``spec_hash`` is stable and a rebuild is byte-identical.
"""
from __future__ import annotations

import hashlib
import json

from app import db
from app.models.archimate_core import ArchiMateElement
from app.models.compliance_models import (
    ComplianceControl,
    ComplianceRequirement,
    RegulatoryFramework,
)

# Bump on any change to the emitted slice SHAPE (keys / node structure).
SECURITY_SLICE_VERSION = "1.0.0"

# The single authoritative store this slice reads. Labelled in the envelope so
# a consumer knows exactly which system of record the matrix is derived from.
SLICE_STORE = "compliance_requirements"


def build_security_slice(organization_id: int, session=None) -> dict:
    """Build the SECURITY genome slice for ONE organisation.

    Reads the ``compliance_requirements`` binding store, scoped to the tenant by
    the linked ArchiMate element's ``organization_id`` (the binding table has no
    ``organization_id`` column of its own — the requirement element is the
    tenant anchor). Returns a deterministic, provenance-complete dict.

    Args:
        organization_id: tenant whose controls to emit.
        session: SQLAlchemy session (defaults to ``db.session``). Passing the
            test's transactional session keeps the read inside the rollback.

    Returns:
        A dict envelope: ``genome_version, slice, organization_id, store,
        controls[], spec_hash``. ``controls`` is a list of control -> requirement
        nodes, each with non-optional structural provenance.
    """
    if session is None:
        session = db.session

    # ONE query over the binding store, with the control / framework / element
    # lookups joined off its foreign keys. Tenant scope is the element's org.
    # Deterministic ordering: framework code, control code, then binding id.
    rows = (
        session.query(ComplianceRequirement, ComplianceControl, RegulatoryFramework, ArchiMateElement)
        .join(ComplianceControl, ComplianceRequirement.control_id == ComplianceControl.id)
        .join(RegulatoryFramework, ComplianceControl.framework_id == RegulatoryFramework.id)
        .join(ArchiMateElement, ComplianceRequirement.archimate_element_id == ArchiMateElement.id)
        .filter(ArchiMateElement.organization_id == organization_id)
        .order_by(
            RegulatoryFramework.code,
            ComplianceControl.control_code,
            ComplianceRequirement.id,
        )
        .all()
    )

    controls: list[dict] = []
    for req, ctrl, framework, element in rows:
        # STRUCTURAL PROVENANCE — non-optional. The requirement element id is the
        # auditable link "this control exists because of this requirement, which
        # realises this motivation element". No element id => not a node.
        node = {
            "node_id": f"control_{ctrl.id}_req_{req.id}",
            "control": {
                "code": ctrl.control_code,
                "title": ctrl.title,
                "category": ctrl.category or "",
                "official_reference": ctrl.official_reference or "",
            },
            "framework": {
                "code": framework.code,
                "name": framework.name,
            },
            "requirement": {
                "id": req.id,
                "title": req.title,
                "status": req.status or "",
                "implementation_status": req.implementation_status or "",
            },
            "provenance": {
                "origin": "element",
                "archimate_element_id": element.id,
                "archimate_type": element.type or "",
                "element_name": element.name,
                "layer": "motivation",
            },
        }
        # Invariant guard: provenance element id must be present and truthy.
        assert node["provenance"]["archimate_element_id"], (
            "security slice node emitted without structural provenance "
            f"(control {ctrl.id}, requirement {req.id})"
        )
        controls.append(node)

    envelope = {
        "genome_version": SECURITY_SLICE_VERSION,
        "slice": "security",
        "organization_id": organization_id,
        "store": SLICE_STORE,
        "controls": controls,
    }
    envelope["spec_hash"] = _spec_hash(envelope)
    return envelope


def _spec_hash(envelope: dict) -> str:
    """Deterministic sha256 over the slice content (excluding the hash itself).

    No timestamps or randomness feed this, so two builds of the same DB state
    produce byte-identical hashes.
    """
    payload = {k: v for k, v in envelope.items() if k != "spec_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
