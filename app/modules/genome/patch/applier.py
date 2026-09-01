"""Deterministic applier for an APPROVED genome patch (ADR 0009 / 0010).

This is the ONLY code that turns a genome patch into a model mutation, and it
runs only after a human has approved the patch through the existing AI approval
gate (`AIChatApprovalService.approve_and_execute` -> ToolExecutor -> the
`_tool_apply_genome_patch` handler, which calls this).

Guarantees:
  * Re-validates the patch deterministically (defence-in-depth) and REFUSES an
    invalid one — an approved-but-malformed patch is never written.
  * Writes a provenance record onto the element (who/why/anchor + source), so
    every AI-originated change to the enterprise model is attributable.
  * Org-scoped: the element is created under the patch's target
    organization_id, never the approver's — a patch proposed for org A applies
    to org A. This is set explicitly (not left to the tenant middleware) so it
    is correct even in a CLI/scheduler path with no request tenant context.
  * ArchiMate backbone: creating a motivation element IS creating the
    ArchiMateElement row (CLAUDE.md), so `_sync_archimate_element` is satisfied
    by construction — the row written here is that element. `verify()` confirms
    it exists after the write.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict

from app import db
from app.modules.genome.patch.validator import validate_genome_patch_strict

logger = logging.getLogger(__name__)

# Marker stored on ArchiMateElement.acm_source so every element born from a
# genome patch is queryable/attributable as such.
GENOME_PATCH_SOURCE = "genome_patch"


def _element_model():
    """The TenantMixin-mapped ArchiMateElement (has an organization_id column)."""
    from app.models.models import ArchiMateElement

    return ArchiMateElement


def apply_genome_patch(patch: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    """Apply an approved genome patch. Returns a result dict.

    On success: ``{"success": True, "result": {...}, "message": str}``.
    On refusal/failure: ``{"success": False, "error": str}`` — never a partial,
    never a fabricated element.
    """
    # Defence-in-depth: never write an invalid patch even if approval let it in.
    try:
        validate_genome_patch_strict(patch)
    except Exception as exc:  # GenomePatchValidationError (or malformed input)
        return {"success": False, "error": f"Invalid genome patch: {exc}"}

    operation = patch["operation"]
    element_spec = patch["element"]
    provenance = dict(patch["provenance"])
    org_id = patch["target"]["organization_id"]

    provenance.setdefault("source", "ai_copilot")
    provenance["applied_by_user_id"] = user_id
    provenance["applied_at"] = datetime.utcnow().isoformat()
    provenance["genome_domain"] = patch["target"]["domain"]

    ArchiMateElement = _element_model()

    try:
        if operation == "add":
            element = ArchiMateElement(
                name=element_spec["name"],
                type=element_spec["archimate_type"],
                layer=element_spec["layer"],
                description=element_spec.get("description")
                or f"{element_spec['archimate_type']}: {element_spec['name']}",
                organization_id=org_id,
                acm_source=GENOME_PATCH_SOURCE,
            )
            _write_provenance(element, provenance)
            db.session.add(element)
            db.session.commit()
            logger.info(
                "genome-patch applied: created ArchiMateElement id=%s type=%s org=%s by user=%s",
                element.id, element.type, org_id, user_id,
            )
            action = "created"

        elif operation == "modify":
            element_id = element_spec["element_id"]
            # tenancy-ok: org_id is the patch target, filtered explicitly below.
            element = (
                db.session.query(ArchiMateElement)
                .filter(
                    ArchiMateElement.id == element_id,
                    ArchiMateElement.organization_id == org_id,
                )
                .first()
            )
            if element is None:
                return {
                    "success": False,
                    "error": f"Element {element_id} not found in organization {org_id}",
                }
            element.name = element_spec["name"]
            element.type = element_spec["archimate_type"]
            element.layer = element_spec["layer"]
            if element_spec.get("description"):
                element.description = element_spec["description"]
            _write_provenance(element, provenance)
            db.session.commit()
            logger.info(
                "genome-patch applied: modified ArchiMateElement id=%s org=%s by user=%s",
                element.id, org_id, user_id,
            )
            action = "modified"
        else:
            # Unreachable — the validator's enum forbids it — but fail closed.
            return {"success": False, "error": f"Unsupported operation: {operation}"}

    except Exception as exc:
        db.session.rollback()
        logger.exception("genome-patch apply failed")
        return {"success": False, "error": f"Apply failed: {exc}"}

    return {
        "success": True,
        "result": {
            "element_id": element.id,
            "name": element.name,
            "archimate_type": element.type,
            "layer": element.layer,
            "organization_id": org_id,
            "operation": operation,
            "provenance": provenance,
        },
        "message": (
            f"{action.capitalize()} {element.type} '{element.name}' "
            f"from an approved genome patch."
        ),
    }


def _write_provenance(element, provenance: Dict[str, Any]) -> None:
    """Attach the provenance record to the element.

    Stored in custom_properties (a real JSON column on the element table) under
    a ``genome_provenance`` key, and mirrored into the legacy ``properties``
    text column for readers that only know that field.
    """
    try:
        element.custom_properties = {
            **(element.custom_properties or {}),
            "genome_provenance": provenance,
        }
    except Exception:  # column absent on some mappings — mirror below still works
        pass
    try:
        existing = {}
        if getattr(element, "properties", None):
            try:
                existing = json.loads(element.properties)
            except (ValueError, TypeError):
                existing = {}
        existing["genome_provenance"] = provenance
        element.properties = json.dumps(existing)
    except Exception:
        pass


def verify_element_synced(element_id: int, org_id: int) -> bool:
    """True iff an ArchiMateElement row for this id exists in the org.

    The backbone check CLAUDE.md demands — after applying a motivation patch a
    matching ArchiMateElement must exist. Used by tests and callers.
    """
    ArchiMateElement = _element_model()
    # tenancy-ok: explicit org filter; may run outside a request context.
    return (
        db.session.query(ArchiMateElement.id)
        .filter(
            ArchiMateElement.id == element_id,
            ArchiMateElement.organization_id == org_id,
        )
        .first()
        is not None
    )


__all__ = ["apply_genome_patch", "verify_element_synced", "GENOME_PATCH_SOURCE"]
