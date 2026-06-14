"""
Vendor Suggestion Service — capability-backed vendor lookup with LLM fallback.

Queries VendorProductCapability → VendorProductPricing for DB matches.
Falls back to LLM for unknown capabilities (proposals are temporary, NOT persisted).
Handles confirm/reject actions.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import (
    VendorOrganization,
    VendorProduct,
    VendorProductCapability,
    VendorProductPricing,
)
from app.modules.vendors.services.confidence_engine import RANK_SCORES

logger = logging.getLogger(__name__)


class VendorSuggestionService:
    """Capability-backed vendor suggestions with pricing."""

    def get_capability_backed_suggestions(
        self, capability_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """
        For each capability ID, find matching vendor products with pricing.
        Returns list of dicts, one per capability.
        Null-safe: returns empty vendors list for capabilities with no mappings.
        """
        if not capability_ids:
            return []

        results = []
        for cap_id in capability_ids:
            try:
                cap = db.session.get(BusinessCapability, cap_id)
                cap_name = cap.name if cap else f"Capability {cap_id}"

                rows = (
                    db.session.query(
                        VendorProductCapability, VendorProductPricing, VendorProduct, VendorOrganization
                    )
                    .join(VendorProduct, VendorProductCapability.vendor_product_id == VendorProduct.id)
                    .join(VendorOrganization, VendorProduct.vendor_organization_id == VendorOrganization.id)
                    .outerjoin(VendorProductPricing, VendorProductPricing.product_id == VendorProduct.id)
                    .filter(VendorProductCapability.business_capability_id == cap_id)
                    .all()
                )

                vendors = []
                seen_products = set()
                for vpc, pricing, product, vendor in rows:
                    if not product or product.id in seen_products:
                        continue
                    seen_products.add(product.id)

                    annual_cost = None
                    tier = None
                    pricing_id = None
                    if pricing:
                        annual_cost = float(pricing.list_price_annual) if pricing.list_price_annual else None
                        tier = pricing.tier_name
                        pricing_id = pricing.id

                    data_source = getattr(vpc, 'data_source_type', None) or 'seeded'
                    confirmed_count = getattr(vpc, 'confirmed_by_count', None) or 0

                    rank = RANK_SCORES.get(data_source, 0)
                    if data_source == "architect_confirmed" and confirmed_count >= 3:
                        rank = 80

                    vendors.append({
                        "vendor": getattr(vendor, 'name', 'Unknown Vendor'),
                        "product": getattr(product, 'name', 'Unknown Product'),
                        "product_id": product.id,
                        "pricing_id": pricing_id,
                        "coverage_pct": getattr(vpc, 'coverage_percentage', None),
                        "annual_cost": annual_cost,
                        "tier": tier,
                        "data_source_type": data_source,
                        "confirmed_by_count": confirmed_count,
                        "rank": rank,
                        "source": "db",
                    })

                vendors.sort(key=lambda v: v["rank"], reverse=True)

                results.append({
                    "capability_id": cap_id,
                    "capability_name": cap_name,
                    "vendors": vendors,
                })
            except Exception as e:
                logger.warning("Failed to fetch vendors for capability %s: %s", cap_id, e)
                results.append({
                    "capability_id": cap_id,
                    "capability_name": f"Capability {cap_id}",
                    "vendors": [],
                })

        return results

    def confirm_suggestion(self, pricing_id: int, user_id: int) -> Dict[str, Any]:
        """Confirm a vendor pricing suggestion. Updates data_source_type and increments confirmed_by_count."""
        pricing = db.session.get(VendorProductPricing, pricing_id)
        if not pricing:
            raise ValueError(f"Pricing row {pricing_id} not found")

        pricing.data_source_type = "architect_confirmed"
        pricing.confirmed_by_count = (pricing.confirmed_by_count or 0) + 1
        pricing.last_verified_at = datetime.now(timezone.utc)
        db.session.commit()

        logger.info(f"Pricing {pricing_id} confirmed by user {user_id}, count={pricing.confirmed_by_count}")

        return {
            "pricing_id": pricing.id,
            "data_source_type": pricing.data_source_type,
            "confirmed_by_count": pricing.confirmed_by_count,
        }

    def update_pricing(self, pricing_id: int, annual_cost: float, user_id: int) -> Dict[str, Any]:
        """Inline correction — architect updates pricing. Creates new row if value diverges."""
        pricing = db.session.get(VendorProductPricing, pricing_id)
        if not pricing:
            raise ValueError(f"Pricing row {pricing_id} not found")

        if pricing.list_price_annual and abs(float(pricing.list_price_annual) - annual_cost) < 1:
            # Same price — just confirm
            return self.confirm_suggestion(pricing_id, user_id)

        # Different price — update the existing architect_confirmed row for this
        # product+tier if one already exists (prevents duplicate competing rows on
        # concurrent submissions).
        existing_correction = VendorProductPricing.query.filter_by(
            product_id=pricing.product_id,
            tier_name=pricing.tier_name,
            data_source_type="architect_confirmed",
        ).first()

        if existing_correction:
            existing_correction.list_price_annual = annual_cost
            existing_correction.confirmed_by_count = (existing_correction.confirmed_by_count or 0) + 1
            existing_correction.last_verified_at = datetime.now(timezone.utc)
            db.session.commit()

            logger.info(
                f"Pricing {pricing_id} corrected by user {user_id}, "
                f"updated existing correction row id={existing_correction.id}, cost={annual_cost}"
            )

            return {
                "pricing_id": existing_correction.id,
                "data_source_type": "architect_confirmed",
                "confirmed_by_count": existing_correction.confirmed_by_count,
                "annual_cost": annual_cost,
            }

        # No existing correction row — create one
        new_pricing = VendorProductPricing(
            product_id=pricing.product_id,
            pricing_model=pricing.pricing_model,
            tier_name=pricing.tier_name,
            list_price_annual=annual_cost,
            currency=pricing.currency,
            source="Architect Correction",
            data_source_type="architect_confirmed",
            confirmed_by_count=1,
            last_verified_at=datetime.now(timezone.utc),
        )
        db.session.add(new_pricing)
        db.session.commit()

        logger.info(f"Pricing {pricing_id} corrected by user {user_id}, new row id={new_pricing.id}, cost={annual_cost}")

        return {
            "pricing_id": new_pricing.id,
            "data_source_type": "architect_confirmed",
            "confirmed_by_count": 1,
            "annual_cost": annual_cost,
        }

    def vote_coverage(self, capability_mapping_id: int, vote_up: bool,
                      adjusted_coverage: float = None) -> Dict[str, Any]:
        """Vote on capability coverage percentage."""
        vpc = db.session.get(VendorProductCapability, capability_mapping_id)
        if not vpc:
            raise ValueError(f"Capability mapping {capability_mapping_id} not found")

        vpc.confirmed_by_count = (vpc.confirmed_by_count or 0) + 1

        if not vote_up and adjusted_coverage is not None:
            # Weighted average toward new value
            current = vpc.coverage_percentage or 75.0
            count = vpc.confirmed_by_count
            vpc.coverage_percentage = ((current * (count - 1)) + adjusted_coverage) / count

        db.session.commit()

        logger.info(
            f"Coverage mapping {capability_mapping_id} voted {'up' if vote_up else 'down'}, "
            f"count={vpc.confirmed_by_count}, coverage={vpc.coverage_percentage}"
        )

        return {
            "mapping_id": vpc.id,
            "coverage_percentage": vpc.coverage_percentage,
            "confirmed_by_count": vpc.confirmed_by_count,
        }

    def reject_suggestion(self, suggestion_id: str) -> None:
        """Reject a suggestion. No DB write — just discard from UI state."""
        logger.info(f"Suggestion {suggestion_id} rejected, no DB change")
