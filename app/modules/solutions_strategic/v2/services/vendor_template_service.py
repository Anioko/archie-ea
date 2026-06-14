"""
VendorTemplateService — deterministic vendor→ArchiMate element auto-population.

When an architect links an SAP or Microsoft vendor product to a solution,
this service looks up the canonical element template and pre-links matching
Technology/Application layer ArchiMate elements with pending_review=True.

Design invariants:
- Deterministic: same vendor_product_id always produces same elements
- Idempotent: calling twice returns {"linked": 0, "skipped": N} on second call
- Non-silent: every linked element gets pending_review=True in spec_data
- Reversible: architect can remove any auto-linked element individually
"""
from __future__ import annotations

import logging
from datetime import datetime

from app import db

logger = logging.getLogger(__name__)

VENDOR_KEY_MAP = {
    "SAP": "SAP",
    "Salesforce": "SALESFORCE",
    "Microsoft Power Platform": "MICROSOFT_POWER",
    "Microsoft": "MICROSOFT_DYNAMICS",
}


class VendorTemplateService:

    @staticmethod
    def get_vendor_key(vendor_org_name: str) -> str | None:
        """Resolve a vendor org name to a canonical vendor key.

        Uses longest-match first to avoid 'Microsoft' matching before
        'Microsoft Power Platform'.
        """
        sorted_keys = sorted(VENDOR_KEY_MAP.keys(), key=len, reverse=True)
        for name_fragment in sorted_keys:
            if name_fragment.lower() in vendor_org_name.lower():
                return VENDOR_KEY_MAP[name_fragment]
        return None

    @classmethod
    def get_solution_vendor_keys(cls, solution) -> list[str]:
        """Resolve canonical vendor keys for a solution's linked vendor products."""
        keys: list[str] = []
        try:
            products = solution.vendor_products.all() if hasattr(solution.vendor_products, "all") else list(solution.vendor_products or [])
            for vp in products:
                vendor_org = getattr(vp, "vendor_organization", None)
                org_name = getattr(vendor_org, "name", "") if vendor_org else ""
                key = cls.get_vendor_key(org_name)
                if key and key not in keys:
                    keys.append(key)
        except Exception:
            logger.debug("VendorTemplateService.get_solution_vendor_keys fallback to empty", exc_info=True)
        return keys

    @classmethod
    def populate_from_vendor(
        cls, solution_id: int, vendor_product_id: int, user_id: int
    ) -> dict:
        """Link canonical template elements to the solution.

        Returns {"linked": N, "skipped": M, "elements": [...]}.
        Idempotent — skips elements already linked to this solution.
        Never modifies existing confirmed elements.
        """
        try:
            from app.models.vendor.vendor_organization import VendorProduct, VendorArchiMateTemplate
            from app.models.solution_archimate_element import SolutionArchiMateElement

            vp = VendorProduct.query.get(vendor_product_id)
            if not vp:
                logger.warning("VendorTemplateService: product %s not found", vendor_product_id)
                return {"linked": 0, "skipped": 0, "elements": []}

            # Resolve vendor key via org name (relationship is vendor_organization, not vendor)
            vendor_org = getattr(vp, "vendor_organization", None)
            org_name = getattr(vendor_org, "name", "") if vendor_org else ""
            vendor_key = cls.get_vendor_key(org_name)
            if not vendor_key:
                return {"linked": 0, "skipped": 0, "elements": []}

            templates = VendorArchiMateTemplate.query.filter_by(
                vendor_key=vendor_key
            ).order_by(VendorArchiMateTemplate.display_order).all()

            if not templates:
                logger.info("VendorTemplateService: no templates for vendor_key=%s", vendor_key)
                return {"linked": 0, "skipped": 0, "elements": []}

            # Get existing element IDs to detect duplicates
            existing_ids = {
                row.element_id
                for row in SolutionArchiMateElement.query.filter_by(solution_id=solution_id).all()
                if row.element_id is not None
            }

            linked = []
            skipped = 0
            for tmpl in templates:
                if not tmpl.element_id:
                    skipped += 1
                    continue
                if tmpl.element_id in existing_ids:
                    skipped += 1
                    continue

                # Base spec_data for all vendor-template-linked elements
                spec = {
                    "source": "vendor_template",
                    "version": tmpl.version or "2025.1",
                    "pending_review": True,
                    "mandatory": tmpl.mandatory,
                    "linked_by_user_id": user_id,
                    "linked_at": datetime.utcnow().isoformat(),
                }
                # If this template carries domain field seeds (DataObject entries),
                # pre-populate fields so architects confirm from a validated baseline
                # rather than LLM-inferred fields.
                seed = tmpl.get_spec_data_seed() if hasattr(tmpl, "get_spec_data_seed") else None
                if seed and seed.get("fields"):
                    spec["fields"] = seed["fields"]
                    spec["fields_status"] = "vendor_seeded"
                    if seed.get("business_rules"):
                        spec["business_rules_seed"] = seed["business_rules"]

                entry = SolutionArchiMateElement(
                    solution_id=solution_id,
                    element_id=tmpl.element_id,
                    layer_type=tmpl.archimate_layer or "Technology",
                    element_table="archimate_elements",
                    element_name=tmpl.element_name,
                    spec_data=spec,
                )
                db.session.add(entry)
                existing_ids.add(tmpl.element_id)
                linked.append(tmpl.to_dict())

            if linked:
                db.session.commit()
                logger.info(
                    "VendorTemplateService: linked %d elements for solution=%s vendor=%s",
                    len(linked), solution_id, vendor_key,
                )

            return {"linked": len(linked), "skipped": skipped, "elements": linked}

        except Exception:
            db.session.rollback()
            logger.exception(
                "VendorTemplateService.populate_from_vendor failed for solution=%s product=%s",
                solution_id, vendor_product_id,
            )
            return {"linked": 0, "skipped": 0, "elements": []}
