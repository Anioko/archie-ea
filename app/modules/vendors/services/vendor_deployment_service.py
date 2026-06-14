"""
-> app.modules.vendors.services.integration_service

Vendor Deployment Service

Complete deployment pipeline for vendor products to applications.
Coordinates application creation, ArchiMate element cloning, and vendor footprint tracking.
"""

import logging
from datetime import datetime  # dead-code-ok

from app import db
from app.modules.applications.services.application_factory import (  # dead-code-ok
    ApplicationFactory,
    create_vendor_deployment,
)
from app.modules.architecture.services.archimate_element_cloner import (  # dead-code-ok
    clone_vendor_archimate_to_application,
)

logger = logging.getLogger(__name__)


class VendorDeploymentService:
    """Complete deployment service for vendor products."""

    @staticmethod
    def deploy_vendor_product_complete(vendor_product_id, deployment_config):
        """
        Complete deployment process: create application, clone ArchiMate elements, and track vendor footprint.

        Args:
            vendor_product_id: ID of the vendor product to deploy
            deployment_config: Dictionary with deployment parameters

        Returns:
            dict: Complete deployment result
        """
        logger.info(f"Starting complete deployment for vendor product {vendor_product_id}")

        try:
            # Step 1: Create application from vendor product
            app_result = create_vendor_deployment(vendor_product_id, deployment_config)
            application_id = app_result["application_id"]

            logger.info(f"Step 1: Created application {application_id}")

            # Step 2: Clone ArchiMate elements from vendor product template
            archimate_result = clone_vendor_archimate_to_application(
                vendor_product_id, application_id
            )

            logger.info(f"Step 2: Cloned {archimate_result['elements_cloned']} ArchiMate elements")

            # Step 3: Link application to main ArchiMate element if available
            if archimate_result["element_ids"]:
                main_element_id = archimate_result["element_ids"][
                    0
                ]  # Use first cloned element as main
                ApplicationFactory.update_application_with_archimate_link(
                    application_id, main_element_id
                )
                logger.info(
                    f"Step 3: Linked application to main ArchiMate element {main_element_id}"
                )

            # Step 4: Update vendor footprint tracking
            VendorDeploymentService._update_vendor_footprint(
                vendor_product_id, application_id, deployment_config
            )

            logger.info(f"Step 4: Updated vendor footprint tracking")

            # Commit all changes
            db.session.commit()

            # Get final deployment summary
            final_summary = VendorDeploymentService._get_deployment_summary(application_id)

            logger.info(f"Complete deployment successful: {app_result['application_name']}")

            return {
                "success": True,
                "deployment_id": f"deploy_{vendor_product_id}_{application_id}_{int(datetime.utcnow().timestamp())}",
                "application_id": application_id,
                "application_name": app_result["application_name"],
                "vendor_product_id": vendor_product_id,
                "deployment_timestamp": datetime.utcnow().isoformat(),
                "results": {
                    "application_creation": app_result,
                    "archimate_cloning": archimate_result,
                    "vendor_footprint": "updated",
                },
                "summary": final_summary,
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in complete vendor deployment: {str(e)}")
            raise e

    @staticmethod
    def _update_vendor_footprint(vendor_product_id, application_id, deployment_config):
        """
        Update vendor footprint tracking in junction table.

        Args:
            vendor_product_id: ID of the vendor product
            application_id: ID of the application component
            deployment_config: Deployment configuration
        """
        from sqlalchemy import text

        # Get deployment parameters
        deployment_type = deployment_config.get("deployment_type", "primary_system")
        criticality = deployment_config.get("criticality", "business_critical")
        hosting_model = deployment_config.get("hosting_model", "cloud")

        # Update junction table with deployment metadata
        # tenant-filtered: scoped via parent FK (vendor_product_id, archimate_element_id)
        update_query = text(
            """
            UPDATE application_vendor_products
            SET deployment_type = :deployment_type,
                criticality = :criticality,
                hosting_model = :hosting_model,
                implementation_date = :implementation_date,
                notes = :notes
            WHERE vendor_product_id = :vendor_product_id
            AND archimate_element_id IN (
                SELECT id FROM archimate_elements
                WHERE application_component_id = :application_id
            )
        """
        )

        db.session.execute(  # tenant-filtered: scoped via parent FK (vendor_product_id, archimate_element_id)
            update_query,
            {
                "vendor_product_id": vendor_product_id,
                "application_id": application_id,
                "deployment_type": deployment_type,
                "criticality": criticality,
                "hosting_model": hosting_model,
                "implementation_date": datetime.utcnow(),
                "notes": f"Deployed on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
            },
        )

    @staticmethod
    def _get_deployment_summary(application_id):
        """
        Get comprehensive deployment summary.

        Args:
            application_id: ID of the application

        Returns:
            dict: Deployment summary
        """
        try:
            # Get application summary
            app_summary = ApplicationFactory.get_deployment_summary(application_id)
            if not app_summary:
                return None

            # Add additional deployment-specific information
            from sqlalchemy import text

            # Count vendor products linked to this application
            # tenant-filtered: scoped via parent FK (application_component_id)
            vendor_products_query = text(
                """
                SELECT COUNT(DISTINCT vp.id) as vendor_product_count
                FROM application_vendor_products avp
                JOIN vendor_products vp ON avp.vendor_product_id = vp.id
                JOIN archimate_elements ae ON avp.archimate_element_id = ae.id
                WHERE ae.application_component_id = :application_id
            """
            )

            result = db.session.execute(vendor_products_query, {"application_id": application_id})  # tenant-filtered
            vendor_product_count = result.fetchone()["vendor_product_count"]

            # Get ArchiMate element breakdown by type
            # tenant-filtered: scoped via parent FK (application_component_id)
            elements_by_type_query = text(
                """
                SELECT type, COUNT(*) as count
                FROM archimate_elements
                WHERE application_component_id = :application_id
                GROUP BY type
                ORDER BY count DESC
            """
            )

            result = db.session.execute(elements_by_type_query, {"application_id": application_id})  # tenant-filtered
            elements_by_type = {row["type"]: row["count"] for row in result}

            # Enhance summary
            app_summary.update(
                {
                    "vendor_products_count": vendor_product_count,
                    "archimate_elements_by_type": elements_by_type,
                    "deployment_complete": True,
                    "deployment_verified_at": datetime.utcnow().isoformat(),
                }
            )

            return app_summary

        except Exception as e:
            logger.error(f"Error getting deployment summary: {str(e)}")
            return None

    @staticmethod
    def get_vendor_deployment_portfolio(vendor_id):
        """
        Get all applications deployed from a vendor's products.

        Args:
            vendor_id: ID of the vendor organization

        Returns:
            dict: Vendor deployment portfolio
        """
        try:
            from sqlalchemy import text

            from app.models.vendor.vendor_organization import VendorOrganization

            vendor = VendorOrganization.query.get(vendor_id)
            if not vendor:
                raise ValueError(f"Vendor {vendor_id} not found")

            # Get all deployed applications from this vendor (using vendor_product_id FK)
            # tenant-filtered: scoped via parent FK (vendor_organization_id)
            portfolio_query = text(
                """
                SELECT
                    ac.id,
                    ac.name,
                    ac.description,
                    ac.deployment_status,
                    ac.business_criticality,
                    ac.deployment_model,
                    ac.business_owner,
                    ac.created_at,
                    ac.updated_at,
                    vp.name as product_name,
                    vp.product_type as product_category,
                    COUNT(ae.id) as archimate_elements_count
                FROM application_components ac
                JOIN vendor_products vp ON ac.vendor_product_id = vp.id
                LEFT JOIN archimate_elements ae ON ac.id = ae.application_component_id
                WHERE vp.vendor_organization_id = :vendor_id
                AND ac.deployment_status = 'production'
                GROUP BY ac.id, vp.id
                ORDER BY ac.created_at DESC
            """
            )

            result = db.session.execute(portfolio_query, {"vendor_id": vendor_id})  # tenant-filtered
            applications = []

            for row in result:
                deployment_type = "primary_system"  # Default
                applications.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "description": row["description"],
                        "deployment_status": row["deployment_status"],
                        "deployment_type": deployment_type,
                        "criticality": row["business_criticality"],
                        "hosting_model": row["deployment_model"],
                        "business_owner": row["business_owner"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                        "product_name": row["product_name"],
                        "product_category": row["product_category"],
                        "archimate_elements_count": row["archimate_elements_count"],
                    }
                )

            # Calculate portfolio statistics
            total_applications = len(applications)
            products_deployed = len(set(app["product_name"] for app in applications))
            total_elements = sum(app["archimate_elements_count"] for app in applications)

            portfolio = {
                "vendor": {"id": vendor.id, "name": vendor.name, "vendor_type": vendor.vendor_type},
                "statistics": {
                    "total_applications": total_applications,
                    "products_deployed": products_deployed,
                    "total_archimate_elements": total_elements,
                    "average_elements_per_app": total_elements / total_applications
                    if total_applications > 0
                    else 0,
                },
                "applications": applications,
                "generated_at": datetime.utcnow().isoformat(),
            }

            return portfolio

        except Exception as e:
            logger.error(f"Error getting vendor deployment portfolio: {str(e)}")
            raise e

    @staticmethod
    def validate_deployment_prerequisites(vendor_product_id):
        """
        Validate that vendor product is ready for deployment.

        Args:
            vendor_product_id: ID of the vendor product

        Returns:
            tuple: (is_ready, readiness_report)
        """
        try:
            # Get vendor product
            from app.models.vendor.vendor_organization import VendorProduct
            from app.modules.architecture.services.archimate_element_cloner import (
                get_vendor_template_elements,
            )

            vendor_product = VendorProduct.query.get(vendor_product_id)
            if not vendor_product:
                return False, {"error": "Vendor product not found"}

            # Check for template ArchiMate elements
            template_elements = get_vendor_template_elements(vendor_product_id)

            readiness_report = {
                "vendor_product": {
                    "id": vendor_product.id,
                    "name": vendor_product.name,
                    "vendor": vendor_product.vendor_organization.name,
                },
                "template_elements_count": len(template_elements),
                "template_elements_by_type": {},
                "ready_for_deployment": True,
                "warnings": [],
                "errors": [],
            }

            # Analyze template elements by type
            if template_elements:
                element_types = {}
                for element in template_elements:
                    element_types[element.type] = element_types.get(element.type, 0) + 1
                readiness_report["template_elements_by_type"] = element_types
            else:
                readiness_report["ready_for_deployment"] = False
                readiness_report["errors"].append(
                    "No template ArchiMate elements found for this vendor product"
                )

            # Check for essential element types
            essential_types = ["ApplicationComponent", "Node", "Device", "SystemSoftware"]
            missing_essential = [etype for etype in essential_types if etype not in element_types]
            if missing_essential:
                readiness_report["warnings"].append(
                    f'Missing essential element types: {", ".join(missing_essential)}'
                )

            # Check vendor product status
            if vendor_product.vendor_organization.contract_status != "contracted":
                readiness_report["warnings"].append(
                    "Vendor organization is not in contracted status"
                )

            return readiness_report["ready_for_deployment"], readiness_report

        except Exception as e:
            logger.error(f"Error validating deployment prerequisites: {str(e)}")
            return False, {"error": str(e)}


def deploy_vendor_product(vendor_product_id, deployment_config):
    """
    Convenience function for complete vendor product deployment.

    Args:
        vendor_product_id: ID of the vendor product to deploy
        deployment_config: Deployment configuration

    Returns:
        dict: Deployment result
    """
    return VendorDeploymentService.deploy_vendor_product_complete(
        vendor_product_id, deployment_config
    )
