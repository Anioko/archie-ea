"""
-> app.modules.vendors.services.integration_service

endor-to-capability linkage utilities.

Provides helpers for populating and maintaining the `vendor_capability_risks`
association table, including:

* Backfilling relationships from existing vendor product mappings and
  transformation initiatives
* Ensuring a link exists (or updating risk metadata) between a vendor and a
  capability
* Removing links when no longer required
* Generating vendor suggestions for newly created capabilities based on vendor
  templates
* Persisting auto-suggestion breadcrumbs so humans can confirm or reject the
  linkage later

These helpers keep the logic in one place so it can be reused by CLI commands,
HTTP endpoints, and background automation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.orm import joinedload

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import (
    EnterpriseInitiative,
    VendorOrganization,
    VendorProduct,
    VendorProductCapability,
    vendor_capability_risks,
)
from app.models.vendor_stack_template import VendorStackTemplate
from app.modules.vendors.v2.services import transactional


@dataclass
class LinkResult:
    """Summary of a single ensure/remove attempt."""

    vendor_id: int
    capability_id: int
    action: str  # 'created', 'updated', 'removed', 'skipped'
    reason: str = ""


class VendorCapabilityLinkService:
    """Service for managing vendor → capability risk linkages."""

    @transactional
    def __init__(self, session=None) -> None:
        self.session = session or db.session

    # ------------------------------------------------------------------
    # Core association helpers
    # ------------------------------------------------------------------
    def ensure_link(
        self,
        vendor: VendorOrganization | int,
        capability: BusinessCapability | int,
        *,
        risk_level: Optional[str] = None,
        risk_type: Optional[str] = None,
        impact_description: Optional[str] = None,
        mitigation_strategy: Optional[str] = None,
        contingency_plan: Optional[str] = None,
        source: Optional[str] = None,
    ) -> LinkResult:
        """Create or update the vendor-capability association."""

        vendor_id = vendor.id if isinstance(vendor, VendorOrganization) else int(vendor)
        capability_id = (
            capability.id if isinstance(capability, BusinessCapability) else int(capability)
        )

        existing = self.session.execute(
            select(vendor_capability_risks.c.vendor_organization_id)
            .where(vendor_capability_risks.c.vendor_organization_id == vendor_id)
            .where(vendor_capability_risks.c.business_capability_id == capability_id)
        ).first()

        # Map parameter names to actual table column names:
        # impact_description → risk_description (table column)
        # contingency_plan has no table column, append to mitigation if present
        effective_mitigation = mitigation_strategy
        if contingency_plan and mitigation_strategy:
            effective_mitigation = f"{mitigation_strategy} | Contingency: {contingency_plan}"
        elif contingency_plan:
            effective_mitigation = f"Contingency: {contingency_plan}"

        payload = {
            "risk_level": risk_level,
            "risk_type": risk_type,
            "risk_description": impact_description,
            "mitigation_strategy": effective_mitigation,
        }
        clean_payload = {key: value for key, value in payload.items() if value is not None}

        if existing:
            if clean_payload:
                self.session.execute(
                    update(vendor_capability_risks)
                    .where(vendor_capability_risks.c.vendor_organization_id == vendor_id)
                    .where(vendor_capability_risks.c.business_capability_id == capability_id)
                    .values(**clean_payload)
                )
                action = "updated"
            else:
                action = "skipped"
            return LinkResult(vendor_id, capability_id, action, source or "ensure_link")

        insert_payload = {
            "vendor_organization_id": vendor_id,
            "business_capability_id": capability_id,
            "risk_level": risk_level or "medium",
            "risk_type": risk_type or "vendor_dependency",
            "risk_description": impact_description,
            "mitigation_strategy": effective_mitigation,
            "created_at": datetime.utcnow(),
        }
        self.session.execute(vendor_capability_risks.insert().values(**insert_payload))
        return LinkResult(vendor_id, capability_id, "created", source or "ensure_link")

    def remove_link(
        self,
        vendor: VendorOrganization | int,
        capability: BusinessCapability | int,
    ) -> LinkResult:
        """Remove an association if it exists."""

        vendor_id = vendor.id if isinstance(vendor, VendorOrganization) else int(vendor)
        capability_id = (
            capability.id if isinstance(capability, BusinessCapability) else int(capability)
        )

        result = self.session.execute(
            delete(vendor_capability_risks)
            .where(vendor_capability_risks.c.vendor_organization_id == vendor_id)
            .where(vendor_capability_risks.c.business_capability_id == capability_id)
        )
        action = "removed" if result.rowcount else "skipped"
        return LinkResult(vendor_id, capability_id, action, "remove_link")

    # ------------------------------------------------------------------
    # Backfill routines
    # ------------------------------------------------------------------
    def backfill_from_existing_sources(
        self,
        *,
        min_coverage: int = 40,
        include_initiatives: bool = True,
        include_products: bool = True,
    ) -> dict:
        """Backfill vendor links from products and initiatives."""

        summary = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "sources": {
                "product_mappings": {"created": 0, "updated": 0, "skipped": 0},
                "initiatives": {"created": 0, "updated": 0, "skipped": 0},
            },
        }

        if include_products:
            product_results = self._backfill_from_product_capabilities(min_coverage)
            for result in product_results:
                summary["sources"]["product_mappings"][result.action] += 1
                summary[result.action] += 1

        if include_initiatives:
            initiative_results = self._backfill_from_initiatives()
            for result in initiative_results:
                summary["sources"]["initiatives"][result.action] += 1
                summary[result.action] += 1

        return summary

    def _backfill_from_product_capabilities(self, min_coverage: int) -> List[LinkResult]:
        """Infer vendor links from VendorProductCapability coverage."""

        results: List[LinkResult] = []
        vendors = (
            VendorOrganization.query.options(
                joinedload(VendorOrganization.products)
                .joinedload(VendorProduct.capability_mappings)
                .joinedload(VendorProductCapability.business_capability)
            )
            .order_by(VendorOrganization.name.asc())
            .all()
        )

        for vendor in vendors:
            for product in vendor.products:
                for mapping in product.capability_mappings:
                    capability = mapping.business_capability
                    if not capability:
                        continue

                    coverage = mapping.coverage_percentage or 0
                    if min_coverage and coverage < min_coverage:
                        results.append(
                            LinkResult(
                                vendor.id,
                                capability.id,
                                "skipped",
                                "coverage_below_threshold",
                            )
                        )
                        continue

                    risk_level = self._derive_risk_level(vendor, mapping)
                    reason = (
                        f"{product.name} covers {capability.name} " f"({coverage:.0f}% coverage)."
                    )
                    mitigation = "Track alternate vendors for critical capabilities."
                    contingency = "Maintain documented fallback procedures."

                    result = self.ensure_link(
                        vendor,
                        capability,
                        risk_level=risk_level,
                        risk_type="product_dependency",
                        impact_description=reason,
                        mitigation_strategy=mitigation,
                        contingency_plan=contingency,
                        source="product_mapping",
                    )
                    results.append(result)

        return results

    def _backfill_from_initiatives(self) -> List[LinkResult]:
        """Infer links from enterprise initiatives that touch vendors + capabilities."""

        initiatives = (
            EnterpriseInitiative.query.options(
                joinedload(EnterpriseInitiative.evaluated_vendors),
                joinedload(EnterpriseInitiative.target_capabilities),
            )
            .order_by(EnterpriseInitiative.name.asc())
            .all()
        )

        results: List[LinkResult] = []
        for initiative in initiatives:
            if not initiative.evaluated_vendors or not initiative.target_capabilities:
                continue

            risk_level = (initiative.risk_level or "medium").lower()
            risk_type = "initiative_dependency"
            for vendor in initiative.evaluated_vendors:
                for capability in initiative.target_capabilities:
                    reason = (
                        f"Initiative {initiative.name} evaluates {vendor.name} "
                        f"against capability {capability.name}."
                    )
                    mitigation = "Ensure initiative exit criteria capture vendor dependencies."
                    contingency = "Validate contingency plans as part of initiative governance."

                    result = self.ensure_link(
                        vendor,
                        capability,
                        risk_level=risk_level,
                        risk_type=risk_type,
                        impact_description=reason,
                        mitigation_strategy=mitigation,
                        contingency_plan=contingency,
                        source="initiative",
                    )
                    results.append(result)

        return results

    # ------------------------------------------------------------------
    # Suggestion helpers
    # ------------------------------------------------------------------
    def suggest_vendors_for_capability(
        self,
        capability: BusinessCapability,
        *,
        threshold: float = 0.72,
        limit: int = 5,
    ) -> List[dict]:
        """Return vendor suggestions using template capability names."""

        suggestions: List[dict] = []
        templates = VendorStackTemplate.query.order_by(VendorStackTemplate.vendor_name.asc()).all()

        capability_name = capability.name.lower()
        seen_vendor_ids = set()

        for template in templates:
            if not template.capabilities_enabled:
                continue

            try:
                parsed = json.loads(template.capabilities_enabled)
                if not isinstance(parsed, list):
                    continue
            except (TypeError, ValueError):
                continue

            best_match = None
            best_ratio = 0.0
            for entry in parsed:
                cap_entry_name = (entry.get("name") or "").lower()
                if not cap_entry_name:
                    continue
                ratio = SequenceMatcher(None, capability_name, cap_entry_name).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = entry

            if not best_match or best_ratio < threshold:
                continue

            vendor = self._find_vendor_by_name(template.vendor_company_name or template.vendor_name)
            if not vendor or vendor.id in seen_vendor_ids:
                continue

            suggestions.append(
                {
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.display_name or vendor.name,
                    "confidence": round(best_ratio, 2),
                    "coverage_percentage": best_match.get("coverage_percentage"),
                    "source": f"template:{template.name}",
                    "capability_name": best_match.get("name"),
                }
            )
            seen_vendor_ids.add(vendor.id)

            if len(suggestions) >= limit:
                break

        return suggestions

    def store_suggestions(
        self,
        capability: BusinessCapability,
        suggestions: Sequence[dict],
        *,
        source: str,
    ) -> None:
        """Append suggestion breadcrumbs to the capability's evolution notes."""

        if not suggestions:
            return

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        suggestion_lines = [
            f"{item['vendor_name']} (confidence {item['confidence']:.2f}) via {item['source']}"
            for item in suggestions
        ]
        entry = f"[{timestamp}] Auto-suggested vendors from {source}: " + "; ".join(
            suggestion_lines
        )

        if capability.evolution_notes:
            capability.evolution_notes = f"{capability.evolution_notes}\n{entry}"
        else:
            capability.evolution_notes = entry

    # ------------------------------------------------------------------
    # Auto-link convenience helpers
    # ------------------------------------------------------------------
    def auto_link_capability_from_vendor_name(
        self,
        capability: BusinessCapability,
        vendor_name: Optional[str],
        *,
        reason: Optional[str] = None,
        coverage_percentage: Optional[float] = None,
    ) -> Optional[LinkResult]:
        """Ensure a link exists for a vendor identified by name."""

        if not vendor_name:
            return None

        vendor = self._find_vendor_by_name(vendor_name)
        if not vendor:
            return None

        inferred_risk = self._infer_risk_level_from_vendor(vendor)
        impact = reason or f"Auto-linked by vendor name ({vendor_name})."
        if coverage_percentage is not None:
            impact = f"{impact} Coverage: {coverage_percentage:.0f}%"

        return self.ensure_link(
            vendor,
            capability,
            risk_level=inferred_risk,
            risk_type="template_auto_link",
            impact_description=impact,
            mitigation_strategy="Review auto-created vendor link for accuracy.",
            contingency_plan="Document fallback vendor if auto-link is confirmed.",
            source="vendor_name",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _derive_risk_level(
        self,
        vendor: VendorOrganization,
        mapping: VendorProductCapability,
    ) -> str:
        coverage = mapping.coverage_percentage or 0
        lock_in = vendor.vendor_lock_in_risk or 5

        if coverage >= 90 or lock_in >= 8:
            return "critical"
        if coverage >= 75 or lock_in >= 6:
            return "high"
        if coverage >= 50 or lock_in >= 4:
            return "medium"
        return "low"

    def _infer_risk_level_from_vendor(self, vendor: VendorOrganization) -> str:
        lock_in = vendor.vendor_lock_in_risk or 5
        if lock_in >= 8:
            return "critical"
        if lock_in >= 6:
            return "high"
        if lock_in >= 4:
            return "medium"
        return "low"

    def _find_vendor_by_name(self, vendor_name: str) -> Optional[VendorOrganization]:
        if not vendor_name:
            return None

        vendor = VendorOrganization.query.filter(VendorOrganization.name.ilike(vendor_name)).first()
        if vendor:
            return vendor

        return VendorOrganization.query.filter(
            VendorOrganization.display_name.ilike(vendor_name)
        ).first()


__all__ = ["VendorCapabilityLinkService", "LinkResult"]
