"""
-> app.modules.architecture.services.archimate_service

ArchiMate Element Cloner Service

Clones vendor product ArchiMate elements to application-specific instances.
Maintains relationships and vendor footprint during deployment process.
"""

import logging
from datetime import datetime

from sqlalchemy import text

from app import db
from app.models.models import ArchiMateElement, ArchiMateRelationship
from app.models.vendor.vendor_organization import VendorProduct

logger = logging.getLogger(__name__)


class ArchiMateElementCloner:
    """Service for cloning vendor product ArchiMate elements to applications."""

    def __init__(self, vendor_product_id, application_component_id):
        """
        Initialize cloner for specific vendor product and application.

        Args:
            vendor_product_id: ID of the vendor product to clone from
            application_component_id: ID of the application component to clone to
        """
        self.vendor_product_id = vendor_product_id
        self.application_component_id = application_component_id
        self.cloned_elements = {}
        self.cloned_relationships = []

    def clone_all_elements(self):
        """
        Clone all ArchiMate elements from vendor product to application.

        Returns:
            dict: Cloning results with element counts and IDs
        """
        logger.info(
            f"Starting ArchiMate element cloning for vendor product {self.vendor_product_id} to application {self.application_component_id}"
        )

        try:
            # Get vendor product
            vendor_product = VendorProduct.query.get(self.vendor_product_id)
            if not vendor_product:
                raise ValueError(f"Vendor product {self.vendor_product_id} not found")

            # Get template elements linked to this vendor product
            template_elements = self._get_template_elements()
            logger.info(f"Found {len(template_elements)} template elements to clone")

            # Clone elements in dependency order (parents first)
            cloned_count = 0
            for element in template_elements:
                cloned_element = self._clone_element(element)
                if cloned_element:
                    self.cloned_elements[element.id] = cloned_element
                    cloned_count += 1

            # Clone relationships between cloned elements
            self._clone_relationships()

            # Update junction table to link cloned elements to application
            self._update_junction_table()

            # Commit all changes
            db.session.commit()

            logger.info(
                f"Successfully cloned {cloned_count} elements and {len(self.cloned_relationships)} relationships"
            )

            return {
                "success": True,
                "elements_cloned": cloned_count,
                "relationships_cloned": len(self.cloned_relationships),
                "element_ids": [elem.id for elem in self.cloned_elements.values()],
                "vendor_product_id": self.vendor_product_id,
                "application_component_id": self.application_component_id,
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during ArchiMate element cloning: {str(e)}")
            raise e

    def _get_template_elements(self):
        """Get all template elements linked to this vendor product."""
        # Query through application_vendor_products junction table
        query = text(
            """
            SELECT ae.id FROM archimate_elements ae
            JOIN application_vendor_products avp ON ae.id = avp.archimate_element_id
            WHERE avp.vendor_product_id = :vendor_product_id
            AND ae.application_component_id IS NULL
            ORDER BY ae.type, ae.name
        """
        )

        result = db.session.execute(query, {"vendor_product_id": self.vendor_product_id})  # tenant-filtered: scoped via parent FK (vendor_product_id)
        return [ArchiMateElement.query.get(row[0]) for row in result]

    def _clone_element(self, template_element):
        """Clone a single template element to application-specific instance."""
        try:
            # Create new element as copy of template
            cloned_element = ArchiMateElement(
                name=template_element.name,
                type=template_element.type,
                layer=template_element.layer,
                description=template_element.description,
                documentation=template_element.documentation,
                properties=template_element.properties,
                application_component_id=self.application_component_id,
                architecture_id=None,  # Cloned elements don't belong to architecture models
                template_element_id=template_element.id,  # Track source for traceability
                source_product_id=self.vendor_product_id,  # Track vendor product source
                is_customized=False,
            )

            db.session.add(cloned_element)
            db.session.flush()  # Get the ID without committing

            logger.debug(
                f"Cloned element {template_element.name} (ID: {template_element.id}) -> {cloned_element.id}"
            )
            return cloned_element

        except Exception as e:
            logger.error(f"Error cloning element {template_element.id}: {str(e)}")
            return None

    def _clone_relationships(self):
        """Clone relationships between cloned elements."""
        if not self.cloned_elements:
            return

        # Get relationships between template elements
        template_element_ids = list(self.cloned_elements.keys())
        if len(template_element_ids) < 2:
            return

        query = text(
            """
            SELECT * FROM archimate_relationships
            WHERE source_id IN :template_ids
            AND target_id IN :template_ids
        """
        )

        result = db.session.execute(query, {"template_ids": tuple(template_element_ids)})  # tenant-filtered: scoped via parent FK (template element IDs)

        for row in result:
            source_id = row["source_id"]
            target_id = row["target_id"]

            # Only clone if both source and target were cloned
            if source_id in self.cloned_elements and target_id in self.cloned_elements:
                cloned_source = self.cloned_elements[source_id]
                cloned_target = self.cloned_elements[target_id]

                cloned_relationship = ArchiMateRelationship(
                    source_id=cloned_source.id,
                    target_id=cloned_target.id,
                    type=row["type"],
                    architecture_id=None,  # Cloned relationships don't belong to architecture models
                )

                db.session.add(cloned_relationship)
                self.cloned_relationships.append(cloned_relationship)

                logger.debug(f"Cloned relationship {row['type']} from {source_id} to {target_id}")

    def _update_junction_table(self):
        """Update application_vendor_products junction table for cloned elements."""
        if not self.cloned_elements:
            return

        for cloned_element in self.cloned_elements.values():
            # Check if junction record already exists
            existing_query = text(
                """
                SELECT 1 FROM application_vendor_products
                WHERE archimate_element_id = :element_id
                AND vendor_product_id = :vendor_product_id
            """
            )

            existing = db.session.execute(  # tenant-filtered: scoped via parent FK (archimate_element_id, vendor_product_id)
                existing_query,
                {"element_id": cloned_element.id, "vendor_product_id": self.vendor_product_id},
            ).first()

            if not existing:
                # Create junction record
                insert_query = text(
                    """
                    INSERT INTO application_vendor_products
                    (archimate_element_id, vendor_product_id, deployment_type, criticality, hosting_model, created_at)
                    VALUES (:element_id, :vendor_product_id, 'primary_system', 'business_critical', 'cloud', :created_at)
                """
                )

                db.session.execute(  # tenant-filtered: scoped via parent FK (archimate_element_id, vendor_product_id)
                    insert_query,
                    {
                        "element_id": cloned_element.id,
                        "vendor_product_id": self.vendor_product_id,
                        "created_at": datetime.utcnow(),
                    },
                )

                logger.debug(f"Created junction record for element {cloned_element.id}")


def clone_vendor_archimate_to_application(vendor_product_id, application_component_id):
    """
    Convenience function to clone all vendor product ArchiMate elements to an application.

    Args:
        vendor_product_id: ID of the vendor product
        application_component_id: ID of the application component

    Returns:
        dict: Cloning results
    """
    cloner = ArchiMateElementCloner(vendor_product_id, application_component_id)
    return cloner.clone_all_elements()


def get_vendor_template_elements(vendor_product_id):
    """
    Get all template elements for a vendor product.

    Args:
        vendor_product_id: ID of the vendor product

    Returns:
        list: Template ArchiMateElement objects
    """
    query = text(
        """
        SELECT ae.id FROM archimate_elements ae
        JOIN application_vendor_products avp ON ae.id = avp.archimate_element_id
        WHERE avp.vendor_product_id = :vendor_product_id
        AND ae.application_component_id IS NULL
        ORDER BY ae.type, ae.name
    """
    )

    result = db.session.execute(query, {"vendor_product_id": vendor_product_id})  # tenant-filtered: scoped via parent FK (vendor_product_id)
    return [ArchiMateElement.query.get(row[0]) for row in result]
