"""Vendor evaluation workflow service — shortlist, compare, decide.

Manages the vendor evaluation shortlist for solutions. Uses the existing
``solution_vendor_products`` junction table with ``implementation_type='shortlisted'``
to distinguish evaluation candidates from fully linked products.  The winner gets
``implementation_type='selected'``.
"""

import logging
from datetime import datetime

from sqlalchemy import and_

from app import db

logger = logging.getLogger(__name__)

# Maximum shortlist size before a warning is emitted.
MAX_SHORTLIST_RECOMMENDED = 4


class SolutionVendorEvalService:
    """Manages vendor evaluation workflow for solutions."""

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_vendor_products(self, query="", category=None, limit=20):
        """Search vendor products by name / category.

        Returns a list of dicts suitable for JSON serialisation.
        """
        from app.models.vendor.vendor_organization import (
            VendorOrganization,
            VendorProduct,
        )

        limit = min(max(1, limit), 50)

        q = db.session.query(
            VendorProduct.id,
            VendorProduct.name,
            VendorProduct.product_family_name,
            VendorProduct.licensing_model,
            VendorProduct.deployment_model,
            VendorProduct.market_position,
            VendorProduct.vendor_organization_id,
            VendorOrganization.name.label("vendor_name"),
        ).outerjoin(
            VendorOrganization,
            VendorProduct.vendor_organization_id == VendorOrganization.id,
        )

        if query:
            safe_query = query.replace("%", r"\%").replace("_", r"\_")
            pattern = f"%{safe_query}%"
            q = q.filter(
                db.or_(
                    VendorProduct.name.ilike(pattern),
                    VendorOrganization.name.ilike(pattern),
                )
            )

        if category:
            safe_cat = category.replace("%", r"\%").replace("_", r"\_")
            q = q.filter(VendorProduct.product_family_name.ilike(f"%{safe_cat}%"))

        q = q.order_by(VendorProduct.name).limit(limit)
        rows = q.all()

        return [
            {
                "id": r.id,
                "name": r.name,
                "product_family": r.product_family_name or "",
                "licensing_model": r.licensing_model or "",
                "deployment_model": r.deployment_model or "",
                "market_position": r.market_position or "",
                "vendor_id": r.vendor_organization_id,
                "vendor_name": r.vendor_name or "Unknown",
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Shortlist read
    # ------------------------------------------------------------------

    def get_shortlist(self, solution_id):
        """Get vendor products shortlisted (implementation_type='shortlisted')."""
        from app.models.solution_models import solution_vendor_products
        from app.models.vendor.vendor_organization import (
            VendorOrganization,
            VendorProduct,
        )

        rows = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            db.select(
                VendorProduct.id,
                VendorProduct.name,
                VendorProduct.product_family_name,
                VendorProduct.licensing_model,
                VendorProduct.deployment_model,
                VendorProduct.market_position,
                VendorProduct.vendor_organization_id,
                VendorOrganization.name.label("vendor_name"),
                solution_vendor_products.c.created_at,
            )
            .select_from(
                solution_vendor_products.join(
                    VendorProduct,
                    solution_vendor_products.c.vendor_product_id == VendorProduct.id,
                )
            )
            .outerjoin(
                VendorOrganization,
                VendorProduct.vendor_organization_id == VendorOrganization.id,
            )
            .where(
                and_(
                    solution_vendor_products.c.solution_id == solution_id,
                    solution_vendor_products.c.implementation_type == "shortlisted",
                )
            )
        ).fetchall()

        return [
            {
                "id": r.id,
                "name": r.name,
                "product_family": r.product_family_name or "",
                "licensing_model": r.licensing_model or "",
                "deployment_model": r.deployment_model or "",
                "market_position": r.market_position or "",
                "vendor_id": r.vendor_organization_id,
                "vendor_name": r.vendor_name or "Unknown",
                "shortlisted_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Shortlist mutate
    # ------------------------------------------------------------------

    def add_to_shortlist(self, solution_id, product_id, notes=""):
        """Add a vendor product to the evaluation shortlist.

        Returns ``(item_dict, warning_msg | None)`` on success.
        Raises ``ValueError`` for invalid input.
        """
        from app.models.solution_models import solution_vendor_products
        from app.models.vendor.vendor_organization import VendorProduct

        vp = db.session.get(VendorProduct, product_id)
        if not vp:
            raise ValueError("Vendor product not found")

        # Already shortlisted?
        existing = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            solution_vendor_products.select().where(
                and_(
                    solution_vendor_products.c.solution_id == solution_id,
                    solution_vendor_products.c.vendor_product_id == product_id,
                )
            )
        ).first()
        if existing:
            raise ValueError("Product already on shortlist or linked to this solution")

        # Current shortlist count
        current_count = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            db.select(db.func.count()).select_from(solution_vendor_products).where(
                and_(
                    solution_vendor_products.c.solution_id == solution_id,
                    solution_vendor_products.c.implementation_type == "shortlisted",
                )
            )
        ).scalar()

        db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            solution_vendor_products.insert().values(
                solution_id=solution_id,
                vendor_product_id=product_id,
                implementation_type="shortlisted",
                license_count=None,
            )
        )
        db.session.commit()

        vendor_name = "Unknown"
        if getattr(vp, "vendor_organization", None):
            vendor_name = vp.vendor_organization.name

        item = {
            "id": vp.id,
            "name": vp.name,
            "product_family": getattr(vp, "product_family_name", "") or "",
            "licensing_model": getattr(vp, "licensing_model", "") or "",
            "deployment_model": getattr(vp, "deployment_model", "") or "",
            "market_position": getattr(vp, "market_position", "") or "",
            "vendor_id": vp.vendor_organization_id,
            "vendor_name": vendor_name,
        }

        warning = None
        new_count = current_count + 1
        if new_count > MAX_SHORTLIST_RECOMMENDED:
            warning = (
                f"Shortlist has {new_count} products. "
                f"Recommended maximum is {MAX_SHORTLIST_RECOMMENDED} for effective comparison."
            )
            logger.info(
                "Solution %s shortlist exceeds recommended max (%d > %d)",
                solution_id,
                new_count,
                MAX_SHORTLIST_RECOMMENDED,
            )

        return item, warning

    def remove_from_shortlist(self, solution_id, product_id):
        """Remove a vendor product from the shortlist.

        Returns the number of rows deleted (0 or 1).
        """
        from app.models.solution_models import solution_vendor_products

        result = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            solution_vendor_products.delete().where(
                and_(
                    solution_vendor_products.c.solution_id == solution_id,
                    solution_vendor_products.c.vendor_product_id == product_id,
                    solution_vendor_products.c.implementation_type == "shortlisted",
                )
            )
        )
        db.session.commit()
        return result.rowcount

    # ------------------------------------------------------------------
    # Category helpers
    # ------------------------------------------------------------------

    def get_product_categories(self):
        """Return distinct non-null product categories (product_family_name)."""
        from app.models.vendor.vendor_organization import VendorProduct

        rows = (
            db.session.query(VendorProduct.product_family_name)
            .filter(VendorProduct.product_family_name.isnot(None))
            .distinct()
            .order_by(VendorProduct.product_family_name)
            .all()
        )
        return [r[0] for r in rows if r[0]]

    # ------------------------------------------------------------------
    # Comparison matrix
    # ------------------------------------------------------------------

    def _compute_tco_estimate(self, product):
        """Compute a 3-year TCO estimate from VendorProduct pricing fields.

        Returns a dict with yearly breakdown and total, or None if no data.
        """
        base = float(product.base_license_cost_annual or 0)
        impl = float(product.implementation_cost_estimate or 0)
        support_pct = float(product.support_cost_percentage or 0) / 100.0

        if base == 0 and impl == 0:
            return None

        annual_support = base * support_pct
        year_1 = base + impl + annual_support
        year_2 = base + annual_support
        year_3 = base + annual_support
        total = year_1 + year_2 + year_3

        return {
            "base_license_annual": round(base, 2),
            "implementation_cost": round(impl, 2),
            "annual_support": round(annual_support, 2),
            "year_1": round(year_1, 2),
            "year_2": round(year_2, 2),
            "year_3": round(year_3, 2),
            "total_3yr": round(total, 2),
        }

    def _compute_capability_score(self, product):
        """Compute a capability coverage score (0-100) from product ratings.

        Uses the 1-10 rating fields on VendorProduct; averages available ones.
        """
        rating_fields = [
            "scalability_rating",
            "security_rating",
            "usability_rating",
            "performance_rating",
            "reliability_rating",
            "innovation_rating",
        ]
        values = []
        for field in rating_fields:
            val = getattr(product, field, None)
            if val is not None:
                values.append(int(val))

        if not values:
            return None

        avg = sum(values) / len(values)
        return round((avg / 10.0) * 100, 1)

    def _compute_risk_indicators(self, product):
        """Return risk indicators based on product metadata."""
        risks = []

        maturity = getattr(product, "product_maturity", None) or ""
        if maturity.lower() in ("emerging", "declining"):
            risks.append({
                "category": "maturity",
                "level": "high",
                "description": f"Product maturity is '{maturity}'",
            })

        eol = getattr(product, "end_of_life_date", None)
        if eol and eol < datetime.utcnow():
            risks.append({
                "category": "end_of_life",
                "level": "critical",
                "description": "Product has passed end-of-life date",
            })
        elif eol:
            risks.append({
                "category": "end_of_life",
                "level": "medium",
                "description": f"End of life: {eol.strftime('%Y-%m-%d')}",
            })

        market = getattr(product, "market_position", None) or ""
        if market.lower() == "niche":
            risks.append({
                "category": "market_position",
                "level": "medium",
                "description": "Niche market position — limited ecosystem",
            })

        adoption = getattr(product, "adoption_rate", None) or ""
        if adoption.lower() == "early_adopter":
            risks.append({
                "category": "adoption",
                "level": "medium",
                "description": "Early adopter stage — limited reference implementations",
            })

        risk_count = len(risks)
        if risk_count == 0:
            overall = "low"
        elif risk_count <= 2:
            overall = "medium"
        else:
            overall = "high"

        return {
            "overall": overall,
            "risk_count": risk_count,
            "indicators": risks,
        }

    def get_comparison_matrix(self, solution_id):
        """Build a comparison matrix for all shortlisted products.

        Returns a dict with:
        - ``products``: list of product dicts with TCO, capability, risk data
        - ``criteria``: list of comparison criteria
        - ``has_data``: whether any products are on the shortlist
        - ``winner_product_id``: id of the currently selected winner (if any)
        """
        from app.models.solution_models import solution_vendor_products
        from app.models.vendor.vendor_organization import (
            VendorOrganization,
            VendorProduct,
        )

        # Fetch shortlisted + selected products
        rows = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            db.select(
                VendorProduct,
                VendorOrganization.name.label("vendor_name"),
                solution_vendor_products.c.implementation_type,
            )
            .select_from(
                solution_vendor_products.join(
                    VendorProduct,
                    solution_vendor_products.c.vendor_product_id == VendorProduct.id,
                )
            )
            .outerjoin(
                VendorOrganization,
                VendorProduct.vendor_organization_id == VendorOrganization.id,
            )
            .where(
                and_(
                    solution_vendor_products.c.solution_id == solution_id,
                    solution_vendor_products.c.implementation_type.in_(
                        ["shortlisted", "selected"]
                    ),
                )
            )
        ).all()

        if not rows:
            return {
                "products": [],
                "criteria": [],
                "has_data": False,
                "winner_product_id": None,
            }

        products = []
        winner_product_id = None

        for product, vendor_name, impl_type in rows:
            tco = self._compute_tco_estimate(product)
            capability_score = self._compute_capability_score(product)
            risk = self._compute_risk_indicators(product)

            # Compute a normalised TCO score (lower is better, scale 0-100)
            tco_score = None
            if tco and tco["total_3yr"] > 0:
                tco_score = tco["total_3yr"]

            if impl_type == "selected":
                winner_product_id = product.id

            products.append({
                "id": product.id,
                "name": product.name,
                "vendor_name": vendor_name or "Unknown",
                "product_family": product.product_family_name or "",
                "licensing_model": product.licensing_model or "",
                "deployment_model": product.deployment_model or "",
                "market_position": product.market_position or "",
                "is_selected": impl_type == "selected",
                "tco": tco,
                "tco_raw": tco_score,
                "capability_score": capability_score,
                "risk": risk,
                "ratings": {
                    "scalability": product.scalability_rating,
                    "security": product.security_rating,
                    "usability": product.usability_rating,
                    "performance": product.performance_rating,
                    "reliability": product.reliability_rating,
                    "innovation": product.innovation_rating,
                },
            })

        # Normalise TCO scores across products (inverse: cheapest = 100)
        tco_values = [p["tco_raw"] for p in products if p["tco_raw"] is not None]
        if tco_values:
            max_tco = max(tco_values)
            for p in products:
                if p["tco_raw"] is not None and max_tco > 0:
                    p["tco_score"] = round((1 - p["tco_raw"] / max_tco) * 100, 1)
                else:
                    p["tco_score"] = None
        else:
            for p in products:
                p["tco_score"] = None

        criteria = [
            {"key": "tco_score", "label": "TCO (3-Year)", "description": "Lower total cost = higher score", "default_weight": 30},
            {"key": "capability_score", "label": "Capability Coverage", "description": "Average of product ratings", "default_weight": 35},
            {"key": "risk_score", "label": "Risk Profile", "description": "Lower risk = higher score", "default_weight": 20},
            {"key": "market_score", "label": "Market Position", "description": "Leader/Challenger scoring", "default_weight": 15},
        ]

        # Compute risk and market scores for MCDA
        for p in products:
            risk_level = p["risk"]["overall"]
            p["risk_score"] = {"low": 100, "medium": 60, "high": 20}.get(risk_level, 50)

            market = (p["market_position"] or "").lower()
            p["market_score"] = {
                "leader": 100,
                "challenger": 75,
                "visionary": 60,
                "niche": 40,
            }.get(market, 50)

        return {
            "products": products,
            "criteria": criteria,
            "has_data": True,
            "winner_product_id": winner_product_id,
        }

    # ------------------------------------------------------------------
    # Decision recording
    # ------------------------------------------------------------------

    def record_decision(self, solution_id, product_id, rationale, criteria_weights=None):
        """Record the vendor selection decision.

        Sets the chosen product's ``implementation_type`` to ``'selected'``
        and resets any previously selected product back to ``'shortlisted'``.

        Args:
            solution_id: The solution ID.
            product_id: The winning vendor product ID.
            rationale: Free-text rationale for the decision.
            criteria_weights: Optional dict of criterion weights used.

        Returns:
            dict with decision details.

        Raises:
            ValueError: If product is not on the shortlist.
        """
        from app.models.solution_models import Solution, solution_vendor_products
        from app.models.vendor.vendor_organization import VendorProduct

        # Verify product is on shortlist
        existing = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            solution_vendor_products.select().where(
                and_(
                    solution_vendor_products.c.solution_id == solution_id,
                    solution_vendor_products.c.vendor_product_id == product_id,
                    solution_vendor_products.c.implementation_type.in_(
                        ["shortlisted", "selected"]
                    ),
                )
            )
        ).first()

        if not existing:
            raise ValueError("Product is not on the evaluation shortlist")

        # Reset any previously selected product back to shortlisted
        db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            solution_vendor_products.update()
            .where(
                and_(
                    solution_vendor_products.c.solution_id == solution_id,
                    solution_vendor_products.c.implementation_type == "selected",
                )
            )
            .values(implementation_type="shortlisted")
        )

        # Mark the winner as selected
        db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            solution_vendor_products.update()
            .where(
                and_(
                    solution_vendor_products.c.solution_id == solution_id,
                    solution_vendor_products.c.vendor_product_id == product_id,
                )
            )
            .values(implementation_type="selected")
        )

        db.session.commit()

        product = db.session.get(VendorProduct, product_id)
        vendor_name = "Unknown"
        if product and getattr(product, "vendor_organization", None):
            vendor_name = product.vendor_organization.name

        logger.info(
            "Vendor decision recorded: solution=%s, product=%s (%s), rationale_length=%d",
            solution_id,
            product_id,
            product.name if product else "?",
            len(rationale or ""),
        )

        return {
            "solution_id": solution_id,
            "selected_product_id": product_id,
            "product_name": product.name if product else "Unknown",
            "vendor_name": vendor_name,
            "rationale": rationale or "",
            "criteria_weights": criteria_weights or {},
            "decided_at": datetime.utcnow().isoformat(),
        }
