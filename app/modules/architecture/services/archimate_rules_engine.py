"""
ArchiMate Rules Engine

Automated generation of ArchiMate 3.2 elements and relationships from vendor,
product, and capability data. Implements comprehensive mapping rules for
enterprise architecture modeling.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app import db
from app.models import ArchiMateElement, ArchiMateRelationship
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

logger = logging.getLogger(__name__)


@dataclass
class ArchiMateElementSpec:
    """Specification for creating an ArchiMate element."""

    name: str
    type: str
    layer: str
    description: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    source_entity_id: Optional[int] = None
    source_entity_type: Optional[str] = None


@dataclass
class ArchiMateRelationshipSpec:
    """Specification for creating an ArchiMate relationship."""

    source_element: ArchiMateElement
    target_element: ArchiMateElement
    relationship_type: str
    name: Optional[str] = None
    description: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)


class ArchiMateRulesEngine:
    """
    Rules engine for automated ArchiMate 3.2 element and relationship generation.

    Implements comprehensive mapping rules from business/technical domains to
    ArchiMate elements, following ArchiMate 3.2 specifications.
    """

    def __init__(self):
        self.generated_elements: Dict[str, ArchiMateElement] = {}
        self.generated_relationships: List[ArchiMateRelationshipSpec] = []
        self.element_counter = 0

    def generate_elements_for_vendor(self, vendor: VendorOrganization) -> Dict[str, Any]:
        """
        Generate ArchiMate elements for a vendor organization.

        Creates business actor, application components, and supporting elements.
        """
        logger.info(f"Generating ArchiMate elements for vendor: {vendor.name}")

        elements_created = []
        relationships_created = []

        # 1. Create Business Actor for the vendor
        actor_spec = ArchiMateElementSpec(
            name=vendor.name,
            type="business_actor",
            layer="business",
            description=f"Business actor representing {vendor.name}",
            properties={
                "vendor_type": vendor.vendor_type,
                "headquarters": vendor.headquarters_location,
                "founded_year": vendor.year_founded,
                "employee_count": vendor.employee_count,
            },
            source_entity_id=vendor.id,
            source_entity_type="vendor_organization",
        )
        actor_element = self._create_element(actor_spec)
        elements_created.append(actor_element)

        # 2. Create Business Objects for key business concepts
        # Note: business_focus attribute not available in VendorOrganization model
        # This section is commented out until business focus data is available
        # if vendor.business_focus:
        #     for focus in vendor.business_focus.split(','):
        #         focus = focus.strip()
        #         business_object_spec = ArchiMateElementSpec(
        #             name=f"{vendor.name} - {focus}",
        #             type="business_object",
        #             layer="business",
        #             description=f"Business object representing {focus} focus",
        #             properties={"business_focus": focus},
        #             source_entity_id=vendor.id,
        #             source_entity_type="vendor_organization"
        #         )
        #         business_object = self._create_element(business_object_spec)
        #         elements_created.append(business_object)

        #         # Create composition relationship
        #         rel_spec = ArchiMateRelationshipSpec(
        #             source_element_id=actor_element.id,
        #             target_element_id=business_object.id,
        #             relationship_type="composition",
        #             name=f"{actor_element.name} composes {business_object.name}",
        #             description=f"Business actor {actor_element.name} is composed of business object {business_object.name}"
        #         )
        #         relationships_created.append(rel_spec)

        # 3. Create Application Components for major products
        for product in vendor.products:
            app_component_spec = ArchiMateElementSpec(
                name=f"{product.name}",
                type="application_component",
                layer="application",
                description=product.functional_scope or f"Application component for {product.name}",
                properties={
                    "product_family": product.product_family_name,
                    "deployment_model": product.deployment_model,
                    "licensing_model": product.licensing_model,
                    "target_market": product.target_market,
                },
                source_entity_id=product.id,
                source_entity_type="vendor_product",
            )
            app_component = self._create_element(app_component_spec)
            elements_created.append(app_component)

            # Create realization relationship between business actor and application component
            rel_spec = ArchiMateRelationshipSpec(
                source_element=actor_element,
                target_element=app_component,
                relationship_type="realization",
                name=f"{actor_element.name} realizes {app_component.name}",
                description=f"Business actor {actor_element.name} realizes application component {app_component.name}",
            )
            relationships_created.append(rel_spec)

        # 4. Create Technology Services for infrastructure capabilities
        # Note: infrastructure_capabilities field not available in VendorOrganization model
        # This section is commented out until appropriate field is identified
        # if hasattr(vendor, 'infrastructure_capabilities') and vendor.infrastructure_capabilities:
        #     for capability in vendor.infrastructure_capabilities.split(','):
        #         capability = capability.strip()
        #         tech_service_spec = ArchiMateElementSpec(
        #             name=f"{vendor.name} {capability} Service",
        #             type="technology_service",
        #             layer="technology",
        #             description=f"Technology service for {capability}",
        #             properties={"infrastructure_capability": capability},
        #             source_entity_id=vendor.id,
        #             source_entity_type="vendor_organization"
        #         )
        #         tech_service = self._create_element(tech_service_spec)
        #         elements_created.append(tech_service)

        #         # Create realization relationship with application components
        #         for app_component in elements_created:
        #             if app_component.type == "application_component":
        #                 rel_spec = ArchiMateRelationshipSpec(
        #                     source_element_id=tech_service.id,
        #                     target_element_id=app_component.id,
        #                     relationship_type="serving",
        #                     name=f"{tech_service.name} serves {app_component.name}",
        #                     description=f"Technology service {tech_service.name} serves application component {app_component.name}"
        #                 )
        #                 relationships_created.append(rel_spec)

        # Store relationships for later creation
        self.generated_relationships.extend(relationships_created)

        return {
            "vendor_id": vendor.id,
            "vendor_name": vendor.name,
            "elements_created": len(elements_created),
            "relationships_created": len(relationships_created),
            "element_ids": [e.id for e in elements_created],
        }

    def generate_elements_for_product(
        self, product: VendorProduct, vendor: VendorOrganization
    ) -> Dict[str, Any]:
        """
        Generate ArchiMate elements for a specific vendor product.

        Creates application components, interfaces, and supporting elements.
        """
        logger.info(f"Generating ArchiMate elements for product: {product.name}")

        elements_created = []
        relationships_created = []

        # 1. Create Application Component for the product
        app_component_spec = ArchiMateElementSpec(
            name=product.name,
            type="application_component",
            layer="application",
            description=product.functional_scope or f"Application component for {product.name}",
            properties={
                "product_family": product.product_family_name,
                "deployment_model": product.deployment_model,
                "licensing_model": product.licensing_model,
                "target_market": product.target_market,
            },
            source_entity_id=product.id,
            source_entity_type="vendor_product",
        )
        app_component = self._create_element(app_component_spec)
        elements_created.append(app_component)

        # 2. Create Application Interfaces for APIs and integrations
        if product.api_capabilities:
            for api in product.api_capabilities.split(","):
                api = api.strip()
                interface_spec = ArchiMateElementSpec(
                    name=f"{product.name} {api} API",
                    type="application_interface",
                    layer="application",
                    description=f"Application interface for {api} API",
                    properties={"api_capability": api},
                    source_entity_id=product.id,
                    source_entity_type="vendor_product",
                )
                interface = self._create_element(interface_spec)
                elements_created.append(interface)

                # Create composition relationship
                rel_spec = ArchiMateRelationshipSpec(
                    source_element=app_component,
                    target_element=interface,
                    relationship_type="composition",
                    name=f"{app_component.name} exposes {interface.name}",
                    description=f"Application component {app_component.name} exposes interface {interface.name}",
                )
                relationships_created.append(rel_spec)

        # 3. Create Technology Services for underlying infrastructure
        if product.infrastructure_requirements:
            for requirement in product.infrastructure_requirements.split(","):
                requirement = requirement.strip()
                tech_service_spec = ArchiMateElementSpec(
                    name=f"{product.name} {requirement} Service",
                    type="technology_service",
                    layer="technology",
                    description=f"Technology service for {requirement}",
                    properties={"infrastructure_requirement": requirement},
                    source_entity_id=product.id,
                    source_entity_type="vendor_product",
                )
                tech_service = self._create_element(tech_service_spec)
                elements_created.append(tech_service)

                # Create serving relationship
                rel_spec = ArchiMateRelationshipSpec(
                    source_element=tech_service,
                    target_element=app_component,
                    relationship_type="serving",
                    name=f"{tech_service.name} serves {app_component.name}",
                    description=f"Technology service {tech_service.name} serves application component {app_component.name}",
                )
                relationships_created.append(rel_spec)

        # 4. Link to vendor's business actor if it exists
        vendor_actor = self._find_vendor_business_actor(vendor.id)
        if vendor_actor:
            rel_spec = ArchiMateRelationshipSpec(
                source_element=vendor_actor,
                target_element=app_component,
                relationship_type="realization",
                name=f"{vendor.name} realizes {app_component.name}",
                description=f"Business actor {vendor.name} realizes application component {app_component.name}",
            )
            relationships_created.append(rel_spec)

        # Store relationships for later creation
        self.generated_relationships.extend(relationships_created)

        return {
            "product_id": product.id,
            "product_name": product.name,
            "elements_created": len(elements_created),
            "relationships_created": len(relationships_created),
            "element_ids": [e.id for e in elements_created],
        }

    def generate_elements_for_capability(self, capability: BusinessCapability) -> Dict[str, Any]:
        """
        Generate ArchiMate elements for a business capability.

        Creates business services, processes, and supporting elements.
        """
        logger.info(f"Generating ArchiMate elements for capability: {capability.name}")

        elements_created = []
        relationships_created = []

        # 1. Create Business Service
        service_spec = ArchiMateElementSpec(
            name=capability.name,
            type="business_service",
            layer="business",
            description=capability.description,
            properties={
                "capability_level": capability.level,
                "domain": capability.domain,
                "subdomain": capability.subdomain,
                "maturity_level": capability.maturity_level,
            },
            source_entity_id=capability.id,
            source_entity_type="business_capability",
        )
        business_service = self._create_element(service_spec)
        elements_created.append(business_service)

        # 2. Create Business Process if detailed process info exists
        if capability.process_flow:
            process_spec = ArchiMateElementSpec(
                name=f"{capability.name} Process",
                type="business_process",
                layer="business",
                description=f"Business process for {capability.name}",
                properties={
                    "process_flow": capability.process_flow,
                    "automation_potential": capability.automation_potential,
                },
                source_entity_id=capability.id,
                source_entity_type="business_capability",
            )
            business_process = self._create_element(process_spec)
            elements_created.append(business_process)

            # Create realization relationship
            rel_spec = ArchiMateRelationshipSpec(
                source_element_id=business_process.id,
                target_element_id=business_service.id,
                relationship_type="realization",
                name=f"{business_process.name} realizes {business_service.name}",
                description=f"Business process {business_process.name} realizes business service {business_service.name}",
            )
            relationships_created.append(rel_spec)

        # 3. Create Business Objects for key data entities
        if capability.key_data_entities:
            for entity in capability.key_data_entities.split(","):
                entity = entity.strip()
                data_object_spec = ArchiMateElementSpec(
                    name=entity,
                    type="business_object",
                    layer="business",
                    description=f"Business object representing {entity}",
                    properties={"data_entity": entity},
                    source_entity_id=capability.id,
                    source_entity_type="business_capability",
                )
                data_object = self._create_element(data_object_spec)
                elements_created.append(data_object)

                # Create access relationship with business service
                rel_spec = ArchiMateRelationshipSpec(
                    source_element_id=business_service.id,
                    target_element_id=data_object.id,
                    relationship_type="access",
                    name=f"{business_service.name} accesses {data_object.name}",
                    description=f"Business service {business_service.name} accesses business object {data_object.name}",
                )
                relationships_created.append(rel_spec)

        # Store relationships for later creation
        self.generated_relationships.extend(relationships_created)

        return {
            "capability_id": capability.id,
            "capability_name": capability.name,
            "elements_created": len(elements_created),
            "relationships_created": len(relationships_created),
            "element_ids": [e.id for e in elements_created],
        }

    def create_relationships_from_mappings(self, mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create ArchiMate relationships from capability-to-vendor mappings.

        Analyzes mappings between business capabilities and vendor products
        to create appropriate ArchiMate relationships.
        """
        logger.info(f"Creating relationships from {len(mappings)} mappings")

        relationships_created = []

        for mapping in mappings:
            # Find source and target elements
            source_element = self._find_element_by_source(
                mapping.get("business_capability_id"), "business_capability"
            )
            target_element = self._find_element_by_source(
                mapping.get("vendor_product_id"), "vendor_product"
            )

            if not source_element or not target_element:
                continue

            # Determine relationship type based on mapping strength and type
            mapping_strength = mapping.get("mapping_strength", "medium")
            mapping_type = mapping.get("mapping_type", "supports")

            if mapping_type == "provides" or mapping_strength == "high":
                rel_type = "serving"
                rel_name = f"{target_element.name} serves {source_element.name}"
            elif mapping_type == "enables":
                rel_type = "realization"
                rel_name = f"{target_element.name} realizes {source_element.name}"
            else:
                rel_type = "association"
                rel_name = f"{target_element.name} associated with {source_element.name}"

            rel_spec = ArchiMateRelationshipSpec(
                source_element_id=target_element.id,
                target_element_id=source_element.id,
                relationship_type=rel_type,
                name=rel_name,
                description=f"Relationship based on {mapping_type} mapping (strength: {mapping_strength})",
                properties={
                    "mapping_type": mapping_type,
                    "mapping_strength": mapping_strength,
                    "mapping_evidence": mapping.get("evidence", ""),
                },
            )
            relationships_created.append(rel_spec)

        # Store relationships for later creation
        self.generated_relationships.extend(relationships_created)

        return {
            "mappings_processed": len(mappings),
            "relationships_created": len(relationships_created),
        }

    # A single generation run that legitimately covers the whole vendor
    # catalogue creates ~435 elements. This cap is not a throttle on that; it
    # is the ceiling above which a request has stopped being a modelling action
    # and become a bulk load that should be scoped. Exceeding it aborts the
    # write entirely rather than truncating it — a half-written model is worse
    # than no model, because nothing in the UI says which half is missing.
    MAX_ELEMENTS_PER_COMMIT = 2000

    def register_element(self, element: ArchiMateElement) -> ArchiMateElement:
        """Queue an element built outside the rules (e.g. by the LLM path).

        Everything that will be written goes through the same choke point, so
        deduplication, the dry-run preview and the cap apply to it too. Adding
        such an element straight to the session bypassed all three.
        """
        self.element_counter += 1
        self.generated_elements[f"{element.type}_{self.element_counter}"] = element
        return element

    @staticmethod
    def _dedupe_key(element) -> tuple:
        """Identity of an element for duplicate purposes: type + folded name.

        Two elements of the same type with the same name in one tenant are the
        same element. That is the definition the product's own duplicate
        detection already uses, so generation must not manufacture rows it will
        then flag.
        """
        name = " ".join((element.name or "").split()).casefold()
        return ((element.type or ""), name)

    def commit_elements_to_database(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Commit all generated elements and relationships to the database.

        Idempotent since 31 Aug 2026. Before this, POSTing an empty body to
        /api/archimate/generate/from-vendors created 435 business actors from
        the global vendor catalogue and a repeat created 435 more — verified
        435 -> 870 -> 1306 rows in one tenant, with no dedup by name, so the
        duplicates then fed the product's own duplicate-detection module.

        Elements whose (type, folded name) already exists in the tenant are
        skipped, and any relationship pointing at a skipped element is
        repointed at the row that already exists. So a repeat run is a no-op
        rather than a second copy of the model.

        Args:
            dry_run: compute what WOULD be written and return the counts
                without adding anything to the session.
        """
        logger.info(
            "Committing ArchiMate elements and relationships to database (dry_run=%s)",
            dry_run,
        )

        # Resolve every generated element to either "new" or "the row that
        # already carries this identity".
        candidate_names = {
            e.name for e in self.generated_elements.values() if e.name
        }
        existing_by_key: Dict[tuple, ArchiMateElement] = {}

        # Outside a request there is no g.current_org_id, so do_orm_execute
        # injects nothing and this lookup would span EVERY tenant — it would
        # then "skip as already existing" an element that belongs to somebody
        # else, leaving this tenant's model silently short of a row. So the
        # cross-run dedupe only applies where the tenant is known; a CLI or
        # scheduler run still dedupes within its own batch.
        from flask import g, has_request_context

        tenant_known = has_request_context() and getattr(g, "current_org_id", None)
        if candidate_names and tenant_known:
            # ArchiMateElement inherits TenantMixin, so do_orm_execute injects
            # the organisation predicate — adding one here would double-filter.
            for row in ArchiMateElement.query.filter(
                ArchiMateElement.name.in_(candidate_names)
            ).all():
                existing_by_key.setdefault(self._dedupe_key(row), row)
        elif candidate_names:
            logger.info(
                "No tenant context: deduplicating within this batch only, "
                "not against rows already in the database."
            )

        resolved: Dict[int, ArchiMateElement] = {}  # id(generated) -> row to use
        to_insert: List[ArchiMateElement] = []
        skipped = 0
        for element in self.generated_elements.values():
            key = self._dedupe_key(element)
            existing = existing_by_key.get(key)
            if existing is not None:
                resolved[id(element)] = existing
                skipped += 1
                continue
            # First occurrence of this identity in THIS batch becomes the row;
            # later ones resolve to it rather than inserting a second copy.
            existing_by_key[key] = element
            resolved[id(element)] = element
            to_insert.append(element)

        if len(to_insert) > self.MAX_ELEMENTS_PER_COMMIT:
            logger.warning(
                "Refusing generation: %d new elements exceeds the %d cap",
                len(to_insert),
                self.MAX_ELEMENTS_PER_COMMIT,
            )
            return {
                "elements_committed": 0,
                "relationships_committed": 0,
                "elements_skipped_existing": skipped,
                "elements_would_create": len(to_insert),
                "success": False,
                "capped": True,
                "cap": self.MAX_ELEMENTS_PER_COMMIT,
                "error": (
                    f"This would create {len(to_insert)} new elements, above the "
                    f"{self.MAX_ELEMENTS_PER_COMMIT} limit for a single generation. "
                    "Scope the request to specific ids and run it again."
                ),
            }

        resolved_elements = [
            resolved[id(e)] for e in self.generated_elements.values()
        ]

        if dry_run:
            return {
                "dry_run": True,
                "resolved_elements": resolved_elements,
                "elements_committed": 0,
                "relationships_committed": 0,
                "elements_would_create": len(to_insert),
                "elements_skipped_existing": skipped,
                "relationships_would_create": len(self.generated_relationships),
                "success": True,
            }

        try:
            for element in to_insert:
                db.session.add(element)

            # Endpoints are read below. Without this flush the new rows have no
            # id yet and every relationship was written with source_id=NULL /
            # target_id=NULL — a relationship joining nothing, in a system of
            # record.
            db.session.flush()

            relationships_committed = 0
            for rel_spec in self.generated_relationships:
                source = resolved.get(
                    id(rel_spec.source_element), rel_spec.source_element
                )
                target = resolved.get(
                    id(rel_spec.target_element), rel_spec.target_element
                )
                if source.id is None or target.id is None:
                    logger.warning(
                        "Skipping relationship %s: endpoint has no id",
                        rel_spec.relationship_type,
                    )
                    continue
                db.session.add(
                    ArchiMateRelationship(
                        source_id=source.id,
                        target_id=target.id,
                        type=rel_spec.relationship_type,
                    )
                )
                relationships_committed += 1

            db.session.commit()

            return {
                "elements_committed": len(to_insert),
                "relationships_committed": relationships_committed,
                "elements_skipped_existing": skipped,
                "resolved_elements": resolved_elements,
                "success": True,
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to commit ArchiMate elements: {e}")
            return {
                "elements_committed": 0,
                "relationships_committed": 0,
                "elements_skipped_existing": skipped,
                "success": False,
                "error": str(e),
            }

    def _create_element(self, spec: ArchiMateElementSpec) -> ArchiMateElement:
        """Create an ArchiMate element from specification."""
        self.element_counter += 1
        # Don't set id manually - let database auto-generate it

        # Convert properties dict to JSON string for database storage
        properties_json = json.dumps(spec.properties) if spec.properties else None

        # Set source fields based on entity type
        kwargs = {
            "name": spec.name,
            "type": spec.type,
            "layer": spec.layer,
            "description": spec.description,
            "properties": properties_json,
        }

        if spec.source_entity_type == "vendor_product":
            kwargs["source_product_id"] = spec.source_entity_id
        # For vendor_organization, we store it in properties for now
        elif spec.source_entity_type == "vendor_organization":
            if spec.properties:
                spec.properties["source_vendor_id"] = spec.source_entity_id
                kwargs["properties"] = json.dumps(spec.properties)
            else:
                kwargs["properties"] = json.dumps({"source_vendor_id": spec.source_entity_id})

        element = ArchiMateElement(**kwargs)

        self.generated_elements[f"{spec.type}_{self.element_counter}"] = element
        return element

    def _find_vendor_business_actor(self, vendor_id: int) -> Optional[str]:
        """Find the business actor element ID for a vendor."""
        for element_id, element in self.generated_elements.items():
            if (
                element.type == "business_actor"
                and element.source_entity_id == vendor_id
                and element.source_entity_type == "vendor_organization"
            ):
                return element_id
        return None

    def _find_element_by_source(
        self, source_id: int, source_type: str
    ) -> Optional[ArchiMateElement]:
        """Find an element by its source entity."""
        for element in self.generated_elements.values():
            if element.source_entity_id == source_id and element.source_entity_type == source_type:
                return element
        return None

    def get_generation_stats(self) -> Dict[str, Any]:
        """Get statistics about generated elements and relationships."""
        element_types = {}
        relationship_types = {}

        for element in self.generated_elements.values():
            element_types[element.type] = element_types.get(element.type, 0) + 1

        for rel in self.generated_relationships:
            relationship_types[rel.relationship_type] = (
                relationship_types.get(rel.relationship_type, 0) + 1
            )

        return {
            "total_elements": len(self.generated_elements),
            "total_relationships": len(self.generated_relationships),
            "element_types": element_types,
            "relationship_types": relationship_types,
        }
