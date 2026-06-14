"""
ArchiMate Service

Orchestrates ArchiMate 3.2 element generation, relationship management,
and automated enterprise architecture modeling from vendor and capability data.
"""

import json
import logging
from datetime import datetime  # dead-code-ok: used in element timestamps
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import selectinload

from app import db
from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel
from app.models.archimate import ElementType, Layer, RelationshipType
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct  # dead-code-ok: VendorProduct used by rules engine
from app.services.archimate.archimate_rules_engine import ArchiMateRulesEngine

logger = logging.getLogger(__name__)

# Valid ArchiMate element types the LLM is allowed to produce
# Extended to include Strategy + Motivation layers for BIZBOK cross-domain generation
_LLM_VALID_ELEMENT_TYPES = {
    # Application layer
    "ApplicationFunction", "ApplicationService", "ApplicationComponent",
    "ApplicationInterface", "DataObject",
    # Business layer
    "BusinessProcess", "BusinessFunction", "BusinessService",
    "BusinessActor", "BusinessRole", "BusinessObject", "Product",
    # Strategy layer (BIZBOK core)
    "Capability", "Resource", "ValueStream", "CourseOfAction",
    # Motivation layer
    "Stakeholder", "Driver", "Assessment", "Goal", "Outcome",
    "Principle", "Requirement", "Constraint",
    # Implementation layer
    "WorkPackage", "Deliverable", "Plateau", "Gap",
}

# Valid ArchiMate layers the LLM is allowed to produce
_LLM_VALID_LAYERS = {
    "application", "business", "motivation", "strategy", "implementation",
}

# Valid relationship types the LLM is allowed to produce
_LLM_VALID_RELATIONSHIP_TYPES = {
    "Realization", "Serving", "Access", "Triggering", "Flow",
    "Composition", "Aggregation", "Assignment", "Influence", "Association",
    # Legacy aliases
    "realizes", "serves", "accesses", "triggers",
}


class ArchiMateService:
    """
    Main service for ArchiMate 3.2 enterprise architecture management.

    Provides comprehensive functionality for:
    - Automated element generation from business data
    - Relationship management and validation
    - Architecture model creation and management
    - ArchiMate 3.2 compliance validation
    """

    def __init__(self):
        self.rules_engine = ArchiMateRulesEngine()

    def generate_architecture_from_vendors(
        self, vendor_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Generate complete ArchiMate architecture from vendor data.

        Args:
            vendor_ids: Specific vendor IDs to process, or None for all vendors

        Returns:
            Dict with generation statistics and results
        """
        logger.info(f"Generating ArchiMate architecture from vendors: {vendor_ids or 'all'}")

        # Get vendors to process (eager-load products to avoid N+1)
        if vendor_ids:
            vendors = VendorOrganization.query.options(
                selectinload(VendorOrganization.products)
            ).filter(VendorOrganization.id.in_(vendor_ids)).all()
        else:
            vendors = VendorOrganization.query.options(
                selectinload(VendorOrganization.products)
            ).all()

        total_vendors = len(vendors)
        processed_vendors = 0
        total_elements = 0
        total_relationships = 0

        for vendor in vendors:
            try:
                # Generate elements for vendor
                vendor_result = self.rules_engine.generate_elements_for_vendor(vendor)
                processed_vendors += 1
                total_elements += vendor_result.get("elements_created", 0)
                total_relationships += vendor_result.get("relationships_created", 0)

                logger.info(f"Processed vendor {vendor.name}: {vendor_result}")

                # Generate elements for vendor's products
                for product in vendor.products:
                    try:
                        product_result = self.rules_engine.generate_elements_for_product(
                            product, vendor
                        )
                        total_elements += product_result.get("elements_created", 0)
                        total_relationships += product_result.get("relationships_created", 0)
                        logger.info(f"Processed product {product.name}: {product_result}")
                    except Exception as e:
                        logger.error(f"Failed to generate elements for product {product.name}: {e}")

            except Exception as e:
                logger.error(f"Failed to generate elements for vendor {vendor.name}: {e}")

        # Commit all generated elements and relationships
        commit_result = self.rules_engine.commit_elements_to_database()

        return {
            "vendors_processed": processed_vendors,
            "total_vendors": total_vendors,
            "elements_created": total_elements,
            "relationships_created": total_relationships,
            "commit_success": commit_result.get("success", False),
            "generation_stats": self.rules_engine.get_generation_stats(),
        }

    @staticmethod
    def _build_llm_prompt(capability: "BusinessCapability") -> str:
        """Build org-context-enriched LLM prompt for ArchiMate generation."""
        from app import db as _db

        cap_name = capability.name or "Unknown"
        cap_level = capability.level if capability.level is not None else 1
        cap_description = capability.description or "No description available"

        # Query real app coverage — the moat
        app_context = "No applications currently cover this capability (GAP)."

        return (
            "You are an enterprise architect generating ArchiMate 3.2 elements for a "
            "SPECIFIC organization. Use the real application data below — "
            "reference actual app names, flag gaps as requirements.\n\n"
            f"## Capability\nName: {cap_name}\n"
            f"Level: {cap_level} (1=Strategic, 2=Tactical, 3=Operational)\n"
            f"Description: {cap_description}\n\n"
            f"## Current Application Landscape\n{app_context}\n\n"
            "## Instructions\n"
            "Generate 3-6 ArchiMate elements. NAME real applications where they "
            "exist. Flag GAPS as Requirement elements.\n"
            "Return ONLY a JSON array. Each element:\n"
            "- type: ApplicationFunction | ApplicationService | DataObject | "
            "BusinessProcess | Requirement | BusinessService\n"
            "- name: specific to THIS organization (use real app names)\n"
            "- layer: application | business | motivation\n"
            "- relationship_type: realizes | serves | accesses | triggers"
        )

    @staticmethod
    def _parse_llm_elements(raw_response: str) -> Optional[List[Dict[str, str]]]:
        """
        Parse the JSON array returned by the LLM.

        Returns a list of element dicts if valid, or None if parsing fails
        or the response does not match the expected schema.
        """
        if not raw_response:
            return None

        # Strip markdown fences if the LLM wrapped output in ```json ... ```
        text = raw_response.strip()
        if text.startswith("```"):
            # Remove opening fence (possibly ```json)
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            # Remove closing fence
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3].rstrip()

        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None

        if not isinstance(parsed, list):
            return None

        # Validate each element has the required keys with acceptable values
        validated: List[Dict[str, str]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            el_type = item.get("type", "")
            el_name = item.get("name", "")
            el_layer = item.get("layer", "")
            el_rel = item.get("relationship_type", "")

            if (
                el_type in _LLM_VALID_ELEMENT_TYPES
                and el_layer in _LLM_VALID_LAYERS
                and el_rel in _LLM_VALID_RELATIONSHIP_TYPES
                and el_name
            ):
                validated.append(
                    {
                        "type": el_type,
                        "name": el_name,
                        "layer": el_layer,
                        "relationship_type": el_rel,
                    }
                )

        return validated if validated else None

    def _try_llm_generation(
        self, capability: "BusinessCapability"
    ) -> Optional[List[ArchiMateElement]]:
        """
        Attempt to generate ArchiMate elements for a capability via LLM.

        Returns a list of created ArchiMateElement instances on success,
        or None if LLM is unavailable or parsing fails.
        """
        try:
            from app.modules.ai_chat.services.llm_service_impl import LLMService

            provider, model = LLMService._get_configured_provider()
        except Exception as exc:
            logger.info(
                "LLM provider not available for ArchiMate generation, "
                "falling back to rules engine: %s",
                exc,
            )
            return None

        prompt = self._build_llm_prompt(capability)

        try:
            raw_response, _interaction = LLMService._call_llm(
                prompt=prompt,
                model=model,
                provider=provider,
                user_id=None,
                max_tokens=1000,
            )
        except Exception as exc:
            logger.warning(
                "LLM call failed for capability '%s', "
                "falling back to rules engine: %s",
                capability.name,
                exc,
            )
            return None

        parsed = self._parse_llm_elements(raw_response)
        if parsed is None:
            logger.warning(
                "LLM returned unparseable response for capability '%s', "
                "falling back to rules engine.",
                capability.name,
            )
            return None

        # Convert parsed dicts into ArchiMateElement DB records
        created: List[ArchiMateElement] = []
        properties_base = {
            "capability_id": capability.id,
            "capability_name": capability.name,
            "generation_source": "llm",
        }

        for elem_spec in parsed:
            props = {**properties_base, "relationship_type": elem_spec["relationship_type"]}
            element = ArchiMateElement(
                name=elem_spec["name"],
                type=elem_spec["type"],
                layer=elem_spec["layer"],
                description=(
                    f"LLM-generated element for capability: {capability.name}"
                ),
                properties=json.dumps(props),
            )
            db.session.add(element)
            created.append(element)

        logger.info(
            "LLM generated %d ArchiMate elements for capability '%s'",
            len(created),
            capability.name,
        )
        return created

    def generate_architecture_from_capabilities(
        self, capability_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Generate ArchiMate elements from business capabilities.

        Attempts LLM-powered generation first for contextually meaningful
        element names. Falls back to the deterministic rules engine when
        the LLM is unavailable or returns unparseable output.

        Args:
            capability_ids: Specific capability IDs to process, or None for all capabilities

        Returns:
            Dict with generation statistics, results, and created_elements list
        """
        logger.info(f"Generating ArchiMate elements from capabilities: {capability_ids or 'all'}")

        # Get capabilities to process
        if capability_ids:
            capabilities = BusinessCapability.query.filter(
                BusinessCapability.id.in_(capability_ids)
            ).all()
        else:
            capabilities = BusinessCapability.query.all()

        total_capabilities = len(capabilities)
        processed_capabilities = 0
        total_elements = 0
        total_relationships = 0
        all_element_ids: List[int] = []
        all_created_elements: List[ArchiMateElement] = []

        for capability in capabilities:
            try:
                # Try LLM generation first
                llm_elements = self._try_llm_generation(capability)

                if llm_elements is not None:
                    # LLM succeeded — use its elements
                    processed_capabilities += 1
                    total_elements += len(llm_elements)
                    all_created_elements.extend(llm_elements)
                    logger.info(
                        "LLM processed capability %s: %d elements",
                        capability.name,
                        len(llm_elements),
                    )
                else:
                    # Fallback to deterministic rules engine
                    capability_result = self.rules_engine.generate_elements_for_capability(
                        capability
                    )
                    processed_capabilities += 1
                    total_elements += capability_result.get("elements_created", 0)
                    total_relationships += capability_result.get("relationships_created", 0)
                    all_element_ids.extend(capability_result.get("element_ids", []))
                    logger.info(
                        "Rules engine processed capability %s: %s",
                        capability.name,
                        capability_result,
                    )

            except Exception as e:
                logger.error(f"Failed to generate elements for capability {capability.name}: {e}")

        # Commit all generated elements and relationships
        commit_result = self.rules_engine.commit_elements_to_database()

        # Collect the actual committed element objects for callers that need them
        created_elements = all_created_elements + [
            elem for elem in self.rules_engine.generated_elements.values()
        ]

        return {
            "capabilities_processed": processed_capabilities,
            "total_capabilities": total_capabilities,
            "elements_created": total_elements,
            "relationships_created": total_relationships,
            "commit_success": commit_result.get("success", False),
            "generation_stats": self.rules_engine.get_generation_stats(),
            "created_elements": created_elements,
        }

    def create_relationships_from_mappings(self, mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create ArchiMate relationships from capability-to-vendor mappings.

        Args:
            mappings: List of mapping dictionaries with business_capability_id, vendor_product_id, etc.

        Returns:
            Dict with relationship creation statistics
        """
        logger.info(f"Creating relationships from {len(mappings)} mappings")

        result = self.rules_engine.create_relationships_from_mappings(mappings)

        # Commit relationships
        commit_result = self.rules_engine.commit_elements_to_database()

        return {**result, "commit_success": commit_result.get("success", False)}

    def get_architecture_model(self, model_id: int) -> Optional[ArchitectureModel]:
        """
        Retrieve an architecture model by ID.

        Args:
            model_id: Architecture model ID

        Returns:
            ArchitectureModel instance or None
        """
        return ArchitectureModel.query.get(model_id)

    def create_architecture_model(
        self, name: str, description: Optional[str] = None, model_type: str = "enterprise"
    ) -> ArchitectureModel:
        """
        Create a new architecture model.

        Args:
            name: Model name
            description: Model description
            model_type: Type of architecture model

        Returns:
            Created ArchitectureModel instance
        """
        model = ArchitectureModel(
            name=name, description=description, model_type=model_type, version="1.0"
        )

        db.session.add(model)
        db.session.commit()

        logger.info(f"Created architecture model: {model.name} (ID: {model.id})")
        return model

    def get_elements_by_type(
        self, element_type: str, layer: Optional[str] = None
    ) -> List[ArchiMateElement]:
        """
        Get ArchiMate elements by type and optional layer.

        Args:
            element_type: Element type to filter by
            layer: Optional layer filter

        Returns:
            List of matching ArchiMateElement instances
        """
        query = ArchiMateElement.query.filter_by(type=element_type)

        if layer:
            query = query.filter_by(layer=layer)

        return query.all()

    def get_element_relationships(self, element_id: int) -> List[ArchiMateRelationship]:
        """
        Get all relationships for a specific element.

        Args:
            element_id: ArchiMate element ID

        Returns:
            List of ArchiMateRelationship instances
        """
        return ArchiMateRelationship.query.filter(
            db.or_(
                ArchiMateRelationship.source_id == element_id,
                ArchiMateRelationship.target_id == element_id,
            )
        ).all()

    def validate_archimate_compliance(self) -> Dict[str, Any]:
        """
        Validate ArchiMate 3.2 compliance of the current model.

        Returns:
            Dict with compliance validation results
        """
        logger.info("Validating ArchiMate 3.2 compliance")

        # Get all elements and relationships
        elements = ArchiMateElement.query.all()
        relationships = ArchiMateRelationship.query.all()

        validation_results = {
            "total_elements": len(elements),
            "total_relationships": len(relationships),
            "compliance_issues": [],
            "is_compliant": True,
        }

        # Validate element types
        valid_element_types = {et.value for et in ElementType}
        for element in elements:
            if element.type not in valid_element_types:
                validation_results["compliance_issues"].append(
                    {
                        "type": "invalid_element_type",
                        "element_id": element.id,
                        "element_name": element.name,
                        "invalid_type": element.type,
                    }
                )
                validation_results["is_compliant"] = False

        # Validate relationship types
        valid_relationship_types = {rt.value for rt in RelationshipType}
        for relationship in relationships:
            if relationship.type not in valid_relationship_types:
                validation_results["compliance_issues"].append(
                    {
                        "type": "invalid_relationship_type",
                        "relationship_id": relationship.id,
                        "invalid_type": relationship.type,
                    }
                )
                validation_results["is_compliant"] = False

        # Validate layers
        valid_layers = {layer for layer in Layer}
        for element in elements:
            if element.layer not in valid_layers:
                validation_results["compliance_issues"].append(
                    {
                        "type": "invalid_layer",
                        "element_id": element.id,
                        "element_name": element.name,
                        "invalid_layer": element.layer,
                    }
                )
                validation_results["is_compliant"] = False

        logger.info(
            f"ArchiMate compliance validation: {'PASS' if validation_results['is_compliant'] else 'FAIL'}"
        )
        return validation_results

    def get_architecture_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the ArchiMate architecture.

        Returns:
            Dict with architecture statistics
        """
        from sqlalchemy import func

        # Use database aggregation instead of loading all rows into memory
        elements_by_type = dict(
            db.session.query(
                ArchiMateElement.type, func.count(ArchiMateElement.id)
            ).group_by(ArchiMateElement.type).all()
        )
        elements_by_layer = dict(
            db.session.query(
                ArchiMateElement.layer, func.count(ArchiMateElement.id)
            ).group_by(ArchiMateElement.layer).all()
        )
        relationships_by_type = dict(
            db.session.query(
                ArchiMateRelationship.type,
                func.count(ArchiMateRelationship.id),
            ).group_by(ArchiMateRelationship.type).all()
        )

        total_elements = sum(elements_by_type.values())
        total_relationships = sum(relationships_by_type.values())
        total_models = db.session.query(func.count(ArchitectureModel.id)).scalar() or 0
        # ArchiMateElement has no updated_at; relationships carry a real
        # modification timestamp, so use that as the architecture's last-updated.
        last_updated = db.session.query(
            func.max(ArchiMateRelationship.updated_at)
        ).scalar()

        return {
            "total_elements": total_elements,
            "elements_by_type": elements_by_type,
            "elements_by_layer": elements_by_layer,
            "total_relationships": total_relationships,
            "relationships_by_type": relationships_by_type,
            "total_models": total_models,
            "last_updated": last_updated,
        }

    def get_models(self, domain=None, status=None):
        """Architecture models (ArchitectureModel rows)."""
        from app.models.models import ArchitectureModel
        return [
            {"id": m.id, "name": m.name, "version": getattr(m, "version", None),
             "is_default": getattr(m, "is_default", None), "solution_id": getattr(m, "solution_id", None)}
            for m in ArchitectureModel.query.limit(500).all()
        ]