import logging

from app.models.vendor.vendor_organization import VendorOrganization

logger = logging.getLogger(__name__)


class VendorService:
    """Service for vendor-related operations."""

    def get_vendors(self):
        """Get all vendors from the database."""
        try:
            vendors = VendorOrganization.query.order_by(VendorOrganization.name).all()
            return [
                {
                    "id": v.id,
                    "name": v.name,
                    "organization_type": v.vendor_type or "Unknown",
                    "description": v.display_name or v.name,
                }
                for v in vendors
            ]
        except Exception as e:
            logger.error(f"Failed to load vendors from database: {e}")
            return []
