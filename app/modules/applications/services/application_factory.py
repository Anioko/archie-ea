"""

Application Factory Service

Creates ApplicationComponent instances from vendor product deployments.
Handles application metadata, configuration, and initial setup.
"""

import logging
from datetime import datetime

from app.models.application_layer import ApplicationComponent
from app.models.vendor.vendor_organization import VendorProduct

logger = logging.getLogger(__name__)


class ApplicationFactory:
    """Factory for creating ApplicationComponent instances from vendor products."""

    @staticmethod
    def update_application_with_archimate_link(application_id, archimate_element_id):
        """
        Update application with ArchiMate element link.

        Args:
            application_id: ID of the application component
            archimate_element_id: ID of the main ArchiMate element
        """
        try:
            application = ApplicationComponent.query.get(application_id)
            if not application:
                raise ValueError(f"Application {application_id} not found")

            application.archimate_element_id = archimate_element_id
            application.updated_at = datetime.utcnow()

            logger.info(
                f"Linked application {application_id} to ArchiMate element {archimate_element_id}"
            )

        except Exception as e:
            logger.error(f"Error linking application to ArchiMate element: {str(e)}")
            raise e

    @staticmethod
    def get_deployment_summary(application_id):
        """
        Get deployment summary for an application.

        Args:
            application_id: ID of the application

        Returns:
            dict: Deployment summary information
        """
        try:
            application = ApplicationComponent.query.get(application_id)
            if not application:
                return None

            # Get vendor product information
            vendor_product = None
            if application.vendor_product_id:
                vendor_product = VendorProduct.query.get(application.vendor_product_id)

            # Count ArchiMate elements
            element_count = 0
            if application.archimate_element_id:
                from app.models.models import ArchiMateElement

                element_count = ArchiMateElement.query.filter_by(
                    application_component_id=application_id
                ).count()

            # Get deployment type from metadata
            deployment_type = "primary_system"  # Default
            if application.metadata and isinstance(application.metadata, dict):
                deployment_type = application.metadata.get("deployment_type", "primary_system")

            summary = {
                "application_id": application.id,
                "application_name": application.name,
                "deployment_status": application.deployment_status,
                "deployment_type": deployment_type,  # Get from metadata
                "criticality": application.business_criticality,
                "hosting_model": application.deployment_model,
                "business_owner": application.business_owner,
                "created_at": application.created_at.isoformat()
                if application.created_at
                else None,
                "updated_at": application.updated_at.isoformat()
                if application.updated_at
                else None,
                "archimate_elements_count": element_count,
                "has_archimate_link": bool(application.archimate_element_id),
                "vendor_product": {
                    "id": vendor_product.id if vendor_product else None,
                    "name": vendor_product.name if vendor_product else None,
                    "category": vendor_product.product_type if vendor_product else None,
                    "vendor": {
                        "id": vendor_product.vendor_organization.id if vendor_product else None,
                        "name": vendor_product.vendor_organization.name if vendor_product else None,
                    }
                    if vendor_product
                    else None,
                },
                "metadata": dict(application.metadata) if application.metadata else {},
            }

            return summary

        except Exception as e:
            logger.error(f"Error getting deployment summary: {str(e)}")
            return None


def create_vendor_deployment(vendor_product_id, deployment_config):
    """
    Complete deployment process: create application and link to vendor product.

    Args:
        vendor_product_id: ID of the vendor product to deploy
        deployment_config: Deployment configuration

    Returns:
        dict: Deployment result with application and summary
    """
    try:
        # Get vendor product
        vendor_product = VendorProduct.query.get(vendor_product_id)
        if not vendor_product:
            raise ValueError(f"Vendor product {vendor_product_id} not found")

        # Validate configuration
        is_valid, errors = ApplicationFactory.validate_deployment_config(deployment_config)
        if not is_valid:
            raise ValueError(f"Invalid deployment configuration: {', '.join(errors)}")

        # Create application
        application = ApplicationFactory.create_application_from_vendor_product(
            vendor_product, deployment_config
        )

        # Get deployment summary
        summary = ApplicationFactory.get_deployment_summary(application.id)

        logger.info(f"Successfully created deployment: {application.name}")

        return {
            "success": True,
            "application_id": application.id,
            "application_name": application.name,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Error in vendor deployment: {str(e)}")
        raise e
