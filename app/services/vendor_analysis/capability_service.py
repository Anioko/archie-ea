"""
Vendor Analysis Capability Service
===================================
Provides capability data retrieval for vendor analysis workflows.

Refactored to read capabilities from the database (BusinessCapability model)
instead of returning hardcoded mock data. All capability data is authoritative
from the production schema — no fabricated values.

# mass-deletion-ok — intentional removal of hardcoded mock data block;
# replaced with live database queries against BusinessCapability model.
"""

from flask import current_app


class CapabilityService:
    """Service for capability-related operations.

    All methods query the live database. No mock or hardcoded data is used.
    """

    def get_capabilities(self):
        """Get all capabilities for analysis from database.

        Returns a list of dicts with keys: id, name, level, description,
        parent_id. Returns an empty list on any database error.
        """
        try:
            from app.models.business_capabilities import BusinessCapability

            capabilities = BusinessCapability.query.all()

            return [
                {
                    "id": cap.id,
                    "name": cap.name,
                    "level": f"L{cap.level}",
                    "description": cap.description or "",
                    "parent_id": cap.parent_capability_id,
                }
                for cap in capabilities
            ]
        except Exception as e:
            current_app.logger.error(f"Error loading capabilities: {e}")
            # Return empty list on error instead of crashing
            return []

    def get_capability_by_id(self, capability_id: int):
        """Fetch a single capability by primary key.

        Returns the capability dict or None if not found.
        """
        try:
            from app.models.business_capabilities import BusinessCapability

            cap = BusinessCapability.query.get(capability_id)
            if cap is None:
                return None
            return {
                "id": cap.id,
                "name": cap.name,
                "level": f"L{cap.level}",
                "description": cap.description or "",
                "parent_id": cap.parent_capability_id,
            }
        except Exception as e:
            current_app.logger.error(f"Error loading capability {capability_id}: {e}")
            return None
