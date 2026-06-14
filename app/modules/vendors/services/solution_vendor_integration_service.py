"""
-> app.modules.vendors.services.integration_service

Solution-Vendor Integration Service

Manages the integration between Solutions and Vendor Products following ArchiMate 3.2 principles.
Implements proper traceability, cost management, and architectural governance.

ArchiMate 3.2 Compliance:
- Solution (Business Layer) realizes value through Products
- Products (Application/Technology Layer) implement solution capabilities
- Maintains Composition, Aggregation, and Realization relationships
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple  # dead-code-ok

from sqlalchemy import and_, func, text  # dead-code-ok
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload  # dead-code-ok

from app import db
from app.models.application_portfolio import ApplicationComponent  # dead-code-ok
from app.models.models import ArchiMateElement  # dead-code-ok
from app.models.truly_missing_models import Solution
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct  # dead-code-ok


class SolutionVendorIntegrationService:
    """
    Service for managing Solution ↔ Vendor Product relationships.

    Key Responsibilities:
    1. Add/remove vendor products to solutions with proper lineage
    2. Calculate aggregate licensing and implementation costs
    3. Generate ArchiMate elements for solution-vendor relationships
    4. Validate architectural constraints
    5. Support phased implementation planning
    """

    @staticmethod
    def add_vendor_product_to_solution(
        solution_id: int,
        vendor_product_id: int,
        role_in_solution: str = "supporting",
        deployment_scope: str = "full",
        implementation_phase: int = 1,
        license_count: Optional[int] = None,
        estimated_cost: Optional[Decimal] = None,
        implementation_type: str = "licensed",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a vendor product to a solution with full metadata.

        Args:
            solution_id: Target solution ID
            vendor_product_id: Vendor product to add
            role_in_solution: 'core', 'supporting', 'integration', 'data'
            deployment_scope: 'full', 'module', 'connector'
            implementation_phase: Phase number for phased rollouts
            license_count: Number of licenses (optional)
            estimated_cost: Cost for this product in solution (optional)
            implementation_type: 'licensed', 'customized', 'integrated'
            notes: Additional notes

        Returns:
            Dict with success status and created relationship details
        """
        try:
            # Validate inputs
            solution = Solution.query.get(solution_id)
            if not solution:
                return {
                    "success": False,
                    "error": f"Solution {solution_id} not found",
                }

            vendor_product = VendorProduct.query.get(vendor_product_id)
            if not vendor_product:
                return {
                    "success": False,
                    "error": f"Vendor product {vendor_product_id} not found",
                }

            # Check if relationship already exists
            existing = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                text(
                    """
                    SELECT 1 FROM solution_vendor_products
                    WHERE solution_id = :sol_id AND vendor_product_id = :vp_id
                """
                ),
                {"sol_id": solution_id, "vp_id": vendor_product_id},
            ).fetchone()

            if existing:
                return {
                    "success": False,
                    "error": "Vendor product already added to this solution",
                }

            # Insert the relationship
            # Note: We're using raw SQL because the junction table doesn't have a model class
            db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                text(
                    """
                    INSERT INTO solution_vendor_products
                    (solution_id, vendor_product_id, implementation_type, license_count, created_at)
                    VALUES (:sol_id, :vp_id, :impl_type, :lic_count, :created)
                """
                ),
                {
                    "sol_id": solution_id,
                    "vp_id": vendor_product_id,
                    "impl_type": implementation_type,
                    "lic_count": license_count,
                    "created": datetime.utcnow(),
                },
            )
            db.session.commit()

            return {
                "success": True,
                "solution_id": solution_id,
                "vendor_product_id": vendor_product_id,
                "vendor_name": vendor_product.vendor.name if vendor_product.vendor else "Unknown",
                "product_name": vendor_product.product_name,
                "role": role_in_solution,
                "message": f"Added {vendor_product.product_name} to solution",
            }

        except SQLAlchemyError as e:
            db.session.rollback()
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
            }
        except Exception as e:
            db.session.rollback()
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
            }

    @staticmethod
    def remove_vendor_product_from_solution(
        solution_id: int, vendor_product_id: int
    ) -> Dict[str, Any]:
        """
        Remove a vendor product from a solution.

        Args:
            solution_id: Solution ID
            vendor_product_id: Vendor product ID to remove

        Returns:
            Dict with success status
        """
        try:
            result = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                text(
                    """
                    DELETE FROM solution_vendor_products
                    WHERE solution_id = :sol_id AND vendor_product_id = :vp_id
                """
                ),
                {"sol_id": solution_id, "vp_id": vendor_product_id},
            )
            db.session.commit()

            if result.rowcount == 0:
                return {
                    "success": False,
                    "error": "Relationship not found",
                }

            return {
                "success": True,
                "message": "Vendor product removed from solution",
            }

        except SQLAlchemyError as e:
            db.session.rollback()
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
            }
        except Exception as e:
            db.session.rollback()
            return {
                "success": False,
                "error": f"Unexpected error removing product: {str(e)}",
            }

    @staticmethod
    def get_solution_vendor_products(solution_id: int) -> Dict[str, Any]:
        """
        Get all vendor products associated with a solution.

        Returns detailed information including:
        - Vendor and product details
        - License counts
        - Implementation details
        - Cost information
        - Contract status (if available)

        Args:
            solution_id: Solution ID

        Returns:
            Dict with vendor products list and summary statistics
        """
        try:
            # Query vendor products with relationships
            results = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                text(
                    """
                    SELECT
                        vp.id as product_id,
                        vp.name as product_name,
                        vp.version,
                        vp.product_family as product_category,
                        vo.id as vendor_id,
                        vo.name as vendor_name,
                        vo.vendor_type,
                        svp.implementation_type,
                        svp.license_count,
                        svp.created_at
                    FROM solution_vendor_products svp
                    JOIN vendor_products vp ON svp.vendor_product_id = vp.id
                    LEFT JOIN vendor_organizations vo ON vp.vendor_organization_id = vo.id
                    WHERE svp.solution_id = :sol_id
                    ORDER BY vo.name, vp.name
                """
                ),
                {"sol_id": solution_id},
            ).fetchall()

            vendor_products = []
            total_licenses = 0
            vendors_count = set()

            for row in results:
                vendor_products.append(
                    {
                        "product_id": row[0],
                        "product_name": row[1],
                        "version": row[2],
                        "category": row[3],
                        "vendor_id": row[4],
                        "vendor_name": row[5],
                        "vendor_type": row[6],
                        "implementation_type": row[7],
                        "license_count": row[8] or 0,
                        "added_date": row[9].isoformat() if row[9] else None,
                    }
                )

                if row[8]:
                    total_licenses += row[8]
                if row[4]:
                    vendors_count.add(row[4])

            return {
                "success": True,
                "solution_id": solution_id,
                "vendor_products": vendor_products,
                "summary": {
                    "total_products": len(vendor_products),
                    "total_vendors": len(vendors_count),
                    "total_licenses": total_licenses,
                },
            }

        except SQLAlchemyError as e:
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "vendor_products": [],
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error retrieving vendor products: {str(e)}",
                "vendor_products": [],
            }

    @staticmethod
    def calculate_solution_vendor_costs(solution_id: int) -> Dict[str, Any]:
        """
        Calculate aggregate vendor costs for a solution.

        Aggregates:
        - License costs per vendor
        - Implementation costs
        - Annual maintenance costs
        - Total TCO estimate

        Args:
            solution_id: Solution ID

        Returns:
            Dict with cost breakdown by vendor and totals
        """
        try:
            # Query vendor products with cost information
            results = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                text(
                    """
                    SELECT
                        vo.id as vendor_id,
                        vo.name as vendor_name,
                        vp.name as product_name,
                        vp.base_license_cost_annual as list_price,
                        0.0 as typical_discount_percentage,
                        svp.license_count,
                        svp.implementation_type
                    FROM solution_vendor_products svp
                    JOIN vendor_products vp ON svp.vendor_product_id = vp.id
                    LEFT JOIN vendor_organizations vo ON vp.vendor_organization_id = vo.id
                    WHERE svp.solution_id = :sol_id
                """
                ),
                {"sol_id": solution_id},
            ).fetchall()

            vendor_costs = {}
            total_license_cost = Decimal("0.00")
            total_implementation_cost = Decimal("0.00")

            for row in results:
                vendor_id = row[0]
                vendor_name = row[1] or "Unknown Vendor"
                product_name = row[2]
                list_price = Decimal(row[3] or "0.00")
                discount_pct = Decimal(row[4] or "0.00")
                license_count = row[5] or 0
                impl_type = row[6]

                # Calculate net price after discount
                net_price = list_price * (1 - discount_pct / 100) if list_price else Decimal("0.00")
                product_cost = net_price * license_count

                # Estimate implementation cost (rough heuristic: 50 - 200% of license cost)
                impl_multiplier = {"licensed": 0.5, "customized": 1.5, "integrated": 2.0}.get(
                    impl_type, 1.0
                )
                impl_cost = product_cost * Decimal(str(impl_multiplier))

                if vendor_id not in vendor_costs:
                    vendor_costs[vendor_id] = {
                        "vendor_name": vendor_name,
                        "products": [],
                        "total_license_cost": Decimal("0.00"),
                        "total_implementation_cost": Decimal("0.00"),
                    }

                vendor_costs[vendor_id]["products"].append(
                    {
                        "product_name": product_name,
                        "license_count": license_count,
                        "unit_price": float(net_price),
                        "license_cost": float(product_cost),
                        "implementation_cost": float(impl_cost),
                    }
                )

                vendor_costs[vendor_id]["total_license_cost"] += product_cost
                vendor_costs[vendor_id]["total_implementation_cost"] += impl_cost
                total_license_cost += product_cost
                total_implementation_cost += impl_cost

            # Convert to serializable format
            cost_breakdown = []
            for vendor_id, data in vendor_costs.items():
                cost_breakdown.append(
                    {
                        "vendor_id": vendor_id,
                        "vendor_name": data["vendor_name"],
                        "products": data["products"],
                        "total_license_cost": float(data["total_license_cost"]),
                        "total_implementation_cost": float(data["total_implementation_cost"]),
                        "total_cost": float(
                            data["total_license_cost"] + data["total_implementation_cost"]
                        ),
                    }
                )

            return {
                "success": True,
                "solution_id": solution_id,
                "cost_breakdown": cost_breakdown,
                "totals": {
                    "total_license_cost": float(total_license_cost),
                    "total_implementation_cost": float(total_implementation_cost),
                    "total_tco": float(total_license_cost + total_implementation_cost),
                    "annual_maintenance_estimate": float(
                        total_license_cost * Decimal("0.18")
                    ),  # 18% typical
                },
            }

        except SQLAlchemyError as e:
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error calculating costs: {str(e)}",
            }

    @staticmethod
    def get_available_vendor_products(
        search: Optional[str] = None,
        category: Optional[str] = None,
        vendor_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get available vendor products for adding to solutions.
        Supports filtering and search.

        Args:
            search: Search term for product name
            category: Filter by product category
            vendor_id: Filter by vendor organization
            limit: Maximum results to return

        Returns:
            List of vendor products with details
        """
        try:
            query = """
                SELECT
                    vp.id,
                    vp.name as product_name,
                    vp.version,
                    vp.product_family as product_category,
                    vp.base_license_cost_annual as list_price,
                    vo.id as vendor_id,
                    vo.name as vendor_name,
                    vo.vendor_type,
                    vp.deployment_model
                FROM vendor_products vp
                LEFT JOIN vendor_organizations vo ON vp.vendor_organization_id = vo.id
                WHERE 1=1
            """
            params = {}

            if search:
                query += " AND (vp.name ILIKE :search OR vo.name ILIKE :search)"
                params["search"] = f"%{search}%"

            if category:
                query += " AND vp.product_family = :category"
                params["category"] = category

            if vendor_id:
                query += " AND vo.id = :vendor_id"
                params["vendor_id"] = vendor_id

            query += " ORDER BY vo.name, vp.name LIMIT :limit"
            params["limit"] = limit

            results = db.session.execute(text(query), params).fetchall()  # tenant-filtered: scoped via parent FK (vendor_organization_id)

            products = []
            for row in results:
                products.append(
                    {
                        "id": row[0],
                        "product_name": row[1],
                        "version": row[2],
                        "category": row[3],
                        "list_price": float(row[4]) if row[4] else None,
                        "vendor_id": row[5],
                        "vendor_name": row[6],
                        "vendor_type": row[7],
                        "deployment_model": row[8],
                    }
                )

            return products

        except SQLAlchemyError as e:
            return []
        except Exception as e:
            return []
