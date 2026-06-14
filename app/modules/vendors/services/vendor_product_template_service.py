"""
-> app.modules.vendors.services.vendor_service

Vendor Product Template Service

Implements the "Product as Template" architecture pattern for vendor product deployments.
When a vendor product is deployed as an application, this service copies all ArchiMate
elements and relationships from the product template to the deployed application instance.

Key Features:
- Deep copy of all ArchiMate layers (except Strategy)
- Maintains relationships between copied elements
- Tracks lineage via template_element_id and source_product_id
- Enables customization while preserving traceability
- Supports architecture governance and compliance

Enterprise Architecture Benefits:
- Portfolio View: Track all instances of a vendor product
- Compliance: Measure deviation from approved architectures
- Standardization: Enforce reference architectures
- Impact Analysis: Identify affected apps when templates change
- License Management: Track all instances per vendor
"""

import logging
from datetime import datetime

from app import db
from app.models.models import ArchiMateElement, ArchiMateRelationship
from app.models.vendor.vendor_organization import VendorProduct

logger = logging.getLogger(__name__)


class VendorProductTemplateService:
    """Service for copying vendor product architecture templates to deployed applications."""

    # Layers to exclude from copying (Strategy is organizational, not per-app)
    EXCLUDED_LAYERS = ["strategy"]

    @staticmethod
    def copy_architecture(product_id, application_component_id, archimate_element_id):
        """
        Deep copy all ArchiMate elements and relationships from vendor product to deployed app.

        Implements the "Product as Template" pattern:
        1. Copies all product elements (except Strategy layer)
        2. Maintains relationships between copied elements
        3. Tracks lineage via template_element_id and source_product_id
        4. Links to deployed application

        Args:
            product_id: VendorProduct ID (source template)
            application_component_id: ApplicationComponent ID (deployed instance)
            archimate_element_id: ArchiMateElement ID of the ApplicationComponent

        Returns:
            dict: {
                'elements_copied': int,
                'relationships_copied': int,
                'layers_copied': list,
                'element_mapping': dict  # old_id -> new_id
            }
        """
        product = VendorProduct.query.get_or_404(product_id)

        logger.info(f"Starting architecture copy from product {product.name} (ID: {product_id})")

        # Get all ArchiMate elements linked to this product
        product_elements = (
            db.session.query(ArchiMateElement)
            .join(ArchiMateElement.vendor_products)
            .filter(VendorProduct.id == product_id)
            .all()
        )

        if not product_elements:
            logger.warning(f"No ArchiMate elements found for product {product.name}")
            return {
                "elements_copied": 0,
                "relationships_copied": 0,
                "layers_copied": [],
                "element_mapping": {},
            }

        # Step 1: Copy elements (excluding Strategy layer)
        element_mapping = {}  # old_id -> new_id
        layers_copied = set()
        elements_copied_count = 0

        for elem in product_elements:
            # Skip Strategy layer elements
            if elem.layer and elem.layer.lower() in VendorProductTemplateService.EXCLUDED_LAYERS:
                logger.debug(f"Skipping Strategy layer element: {elem.name}")
                continue

            # Create copy of element
            new_elem = ArchiMateElement(
                name=elem.name,
                type=elem.type,
                layer=elem.layer,
                description=elem.description,
                documentation=elem.documentation,
                properties=elem.properties,
                stakeholder_interest=elem.stakeholder_interest,
                priority=elem.priority,
                status=elem.status,
                # Template tracking
                template_element_id=elem.id,  # Link back to template
                source_product_id=product_id,  # Track source product
                is_customized=False,  # Initially not customized
                # Link to deployed application
                application_component_id=application_component_id,
                architecture_id=None,  # No architecture model for deployed app yet - query by application_component_id instead
            )

            db.session.add(new_elem)
            db.session.flush()  # Get ID for mapping

            # Track mapping for relationship copying
            element_mapping[elem.id] = new_elem.id
            layers_copied.add(elem.layer)
            elements_copied_count += 1

            logger.debug(f"Copied element: {elem.name} ({elem.type}) -> ID {new_elem.id}")

        # Step 2: Copy relationships between copied elements
        relationships_copied_count = 0

        if element_mapping:
            # Get all relationships where both source and target were copied
            source_ids = list(element_mapping.keys())

            relationships = ArchiMateRelationship.query.filter(
                ArchiMateRelationship.source_id.in_(source_ids),
                ArchiMateRelationship.target_id.in_(source_ids),
            ).all()

            for rel in relationships:
                # Only copy if both source and target elements were copied
                if rel.source_id in element_mapping and rel.target_id in element_mapping:
                    new_rel = ArchiMateRelationship(
                        type=rel.type,
                        source_id=element_mapping[rel.source_id],
                        target_id=element_mapping[rel.target_id],
                        architecture_id=None,  # Match cloned elements - no architecture model yet
                    )
                    db.session.add(new_rel)
                    relationships_copied_count += 1

                    logger.debug(
                        f"Copied relationship: {rel.type} ({element_mapping[rel.source_id]} -> {element_mapping[rel.target_id]})"
                    )

        db.session.commit()

        result = {
            "elements_copied": elements_copied_count,
            "relationships_copied": relationships_copied_count,
            "layers_copied": sorted(list(layers_copied)),
            "element_mapping": element_mapping,
        }

        logger.info(f"Architecture copy complete: {result}")

        return result

    @staticmethod
    def get_template_lineage(archimate_element_id):
        """
        Get the template lineage for a deployed application element.

        Args:
            archimate_element_id: ArchiMateElement ID

        Returns:
            dict: {
                'is_from_template': bool,
                'template_element': ArchiMateElement or None,
                'source_product': VendorProduct or None,
                'is_customized': bool
            }
        """
        element = ArchiMateElement.query.get(archimate_element_id)

        if not element:
            return {"is_from_template": False}

        template_element = None
        if element.template_element_id:
            template_element = ArchiMateElement.query.get(element.template_element_id)

        source_product = None
        if element.source_product_id:
            source_product = VendorProduct.query.get(element.source_product_id)

        return {
            "is_from_template": bool(element.template_element_id or element.source_product_id),
            "template_element": template_element,
            "source_product": source_product,
            "is_customized": element.is_customized,
        }

    @staticmethod
    def mark_as_customized(archimate_element_id, customization_notes=None):
        """
        Mark an element as customized (deviated from template).

        Args:
            archimate_element_id: ArchiMateElement ID
            customization_notes: Optional notes about the customization

        Returns:
            bool: Success status
        """
        element = ArchiMateElement.query.get(archimate_element_id)

        if not element:
            return False

        element.is_customized = True
        if customization_notes:
            element.customization_notes = customization_notes

        db.session.commit()

        logger.info(f"Element {element.name} marked as customized")

        return True

    @staticmethod
    def get_product_instances(product_id):
        """
        Get all application instances deployed from this vendor product.

        Args:
            product_id: VendorProduct ID

        Returns:
            list: List of dicts with instance information
        """
        from app.models.application_layer import ApplicationComponent

        instances = (
            db.session.query(ApplicationComponent)
            .join(
                ArchiMateElement, ArchiMateElement.id == ApplicationComponent.archimate_element_id
            )
            .filter(ArchiMateElement.source_product_id == product_id)
            .all()
        )

        return [
            {
                "id": app.id,
                "name": app.name,
                "deployment_status": app.deployment_status,
                "deployment_model": app.deployment_model,
                "business_criticality": app.business_criticality,
            }
            for app in instances
        ]
