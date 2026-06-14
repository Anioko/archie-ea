"""
Confidence Engine — multi-source ranking, conflict detection, staleness computation.

Handles the data quality layer for the vendor pricing pipeline.
Ranking is computed at query time, never stored.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

RANK_SCORES = {
    "api_synced": 95,
    "contract_verified": 90,
    "architect_confirmed": 60,
    "seeded": 20,
    "llm_proposed": 10,
}

STALENESS_THRESHOLD_DAYS = 180  # 6 months


class ConfidenceEngine:
    """Multi-source confidence ranking and conflict detection."""

    def get_rank_score(self, data_source_type: str, confirmed_by_count: int = 0) -> int:
        """Compute rank score for a pricing row."""
        base = RANK_SCORES.get(data_source_type, 0)
        if data_source_type == "architect_confirmed" and confirmed_by_count >= 3:
            return 80
        return base

    def detect_conflict(self, prices: list) -> Dict[str, Any]:
        """
        Detect pricing conflicts using variance analysis.

        Returns:
            {"has_conflict": bool, "variance_level": "low"|"medium"|"high",
             "min_price": float, "max_price": float, "variance_pct": float}
        """
        if len(prices) <= 1:
            return {
                "has_conflict": False,
                "variance_level": "low",
                "min_price": prices[0] if prices else 0,
                "max_price": prices[0] if prices else 0,
                "variance_pct": 0,
            }

        min_p = min(prices)
        max_p = max(prices)
        if min_p == 0:
            variance_pct = 100 if max_p > 0 else 0
        else:
            variance_pct = ((max_p - min_p) / min_p) * 100

        if variance_pct > 40:
            level = "high"
        elif variance_pct > 20:
            level = "medium"
        else:
            level = "low"

        return {
            "has_conflict": variance_pct > 20,
            "variance_level": level,
            "min_price": min_p,
            "max_price": max_p,
            "variance_pct": round(variance_pct, 1),
        }

    def select_winner(self, rows: list, org_id: Optional[int] = None) -> Optional[Dict]:
        """
        Select the winning pricing row from multiple sources.

        Priority:
        1. Org-scoped contract pricing (if org_id provided)
        2. Highest rank score among global data
        """
        if not rows:
            return None

        # Check for org-scoped contract
        if org_id:
            org_contracts = [
                r for r in rows
                if r.get("organization_id") == org_id
                and r.get("data_source_type") == "contract_verified"
            ]
            if org_contracts:
                return org_contracts[0]

        # Fall back to highest rank
        scored = []
        for r in rows:
            score = self.get_rank_score(
                r.get("data_source_type", "seeded"),
                r.get("confirmed_by_count", 0),
            )
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else None

    def is_stale(self, last_verified_at: Optional[datetime]) -> bool:
        """Check if a pricing row is stale (> 6 months since verification)."""
        if not last_verified_at:
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(days=STALENESS_THRESHOLD_DAYS)
        if last_verified_at.tzinfo is None:
            last_verified_at = last_verified_at.replace(tzinfo=timezone.utc)
        return last_verified_at < cutoff

    def get_analytics(self) -> Dict[str, Any]:
        """
        Compute pricing analytics for the admin dashboard.

        Returns coverage, confidence distribution, staleness, top gaps, velocity.
        """
        from app import db
        from app.models.business_capabilities import BusinessCapability
        from app.models.vendor.vendor_organization import VendorProductCapability, VendorProductPricing

        total_caps = BusinessCapability.query.count()
        covered_caps = db.session.query(
            db.func.count(db.func.distinct(VendorProductCapability.business_capability_id))
        ).scalar() or 0

        # Confidence distribution
        dist = db.session.query(
            VendorProductPricing.data_source_type,
            db.func.count(VendorProductPricing.id),
        ).group_by(VendorProductPricing.data_source_type).all()

        # Staleness
        cutoff = datetime.now(timezone.utc) - timedelta(days=STALENESS_THRESHOLD_DAYS)
        stale_count = VendorProductPricing.query.filter(
            db.or_(
                VendorProductPricing.last_verified_at < cutoff,
                VendorProductPricing.last_verified_at.is_(None),
            )
        ).count()
        total_pricing = VendorProductPricing.query.count()

        return {
            "total_capabilities": total_caps,
            "covered_capabilities": covered_caps,
            "coverage_pct": round(covered_caps / total_caps * 100, 1) if total_caps > 0 else 0,
            "confidence_distribution": {row[0]: row[1] for row in dist},
            "total_pricing_rows": total_pricing,
            "stale_count": stale_count,
            "fresh_pct": round((total_pricing - stale_count) / total_pricing * 100, 1) if total_pricing > 0 else 0,
        }
