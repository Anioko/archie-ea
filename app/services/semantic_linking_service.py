"""
Semantic Linking Service

Orchestrates the semantic population and auto-linking for Application Components.
Leverages DocumentEntityMatchingService for fuzzy matching and logical inference.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.services.document_entity_matching_service import DocumentEntityMatchingService

logger = logging.getLogger(__name__)


class SemanticLinkingService:
    """
    Service for automating the linking of ApplicationComponent entities
    to other ArchiMate elements (Capabilities, etc.) using semantic matching.
    """

    def __init__(self):
        self.matcher = DocumentEntityMatchingService()

    def generate_linking_proposals(self, application_id: int) -> Dict[str, Any]:
        """
        Generate semantic linking proposals for a given application.

        Args:
            application_id: The ID of the application to analyze.

        Returns:
            A dictionary containing proposed links categorized by type.
        """
        app = ApplicationComponent.query.get(application_id)
        if not app:
            return {"error": "Application not found"}

        # Prepare the "extracted entities" structure that the matcher expects
        # We treat the application itself as the source "document"
        fake_extracted_entities = {
            "application_data": {
                "name": app.name,
                "description": app.description or "",
                "technology_stack": self._parse_tech_stack(app.technology_stack),
                "business_domain": app.business_domain,
                "business_functions": app.get_business_functions(),
            },
            "archimate_elements": [],  # Could populate this if we parse description for keywords
        }

        # Run the matcher
        # We are cheating slightly here: we are "matching" the app against the DB.
        # But what we really want is to find related entities *for* this app.
        # The matcher usually matches "extracted entities" TO "db entities".
        # So we need to feed it potential extracted entities derived from the app's text.

        # Strategy:
        # 1. Extract potential entity names from the App's description/name using simple NLP/keywords
        # 2. Feed those into the matcher to find DB matches.

        # Extract potential keywords/entities from description
        potential_entities = self._extract_potential_entities_from_text(
            app.name + " " + (app.description or "")
        )

        # Now run matching for these potential entities
        fake_extracted_entities["archimate_elements"] = [
            {"name": term, "type": "BusinessCapability"}
            for term in potential_entities["capabilities"]
        ] + [{"name": term, "type": "BusinessProcess"} for term in potential_entities["processes"]]

        # Match Capabilities
        capability_matches = self.matcher.match_extracted_entities(
            fake_extracted_entities, entity_type="capability", persona="enterprise_architect"
        )

        # Filter out what is already linked
        existing_capability_ids = [m.capability_id for m in app.capability_mappings]

        filtered_matches = []
        for match in capability_matches.get("matches", []):
            if match.get("entity_id") not in existing_capability_ids:
                filtered_matches.append(match)

        # Also check "potential_duplicates" or "new_entities" if we want to be fancy,
        # but for auto-linking we mostly care about high-confidence matches to existing things.

        return {
            "application_id": app.id,
            "application_name": app.name,
            "proposed_capabilities": filtered_matches,
            # We can extend this to Process, DataObject, etc.
        }

    def apply_links(
        self, application_id: int, selected_links: Dict[str, List[int]]
    ) -> Dict[str, Any]:
        """
        Apply the selected links to the application.

        Args:
            application_id: The app ID.
            selected_links: Dict like {'capabilities': [id1, id2], 'processes': [id3]}
        """
        app = ApplicationComponent.query.get(application_id)
        if not app:
            return {"success": False, "error": "Application not found"}

        applied_count = 0

        # Apply Capabilities
        from app.models.application_portfolio import ApplicationCapabilityMapping

        if "capabilities" in selected_links:
            for cap_id in selected_links["capabilities"]:
                # Check if exists
                exists = ApplicationCapabilityMapping.query.filter_by(
                    application_component_id=app.id, capability_id=cap_id
                ).first()

                if not exists:
                    mapping = ApplicationCapabilityMapping(
                        application_component_id=app.id,
                        capability_id=cap_id,
                        support_level="partial",  # Default
                        is_active=True,
                    )
                    db.session.add(mapping)
                    applied_count += 1

        try:
            db.session.commit()
            return {"success": True, "applied_count": applied_count}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": str(e)}

    def _parse_tech_stack(self, tech_stack_str: Optional[str]) -> List[str]:
        if not tech_stack_str:
            return []
        return [t.strip() for t in tech_stack_str.split(",") if t.strip()]

    def _extract_potential_entities_from_text(self, text: str) -> Dict[str, List[str]]:
        """
        Extract potential entities (e.g. Capability names) from text using keyword matching.
        """
        candidates = {"capabilities": [], "processes": []}

        if not text:
            return candidates

        text_lower = text.lower()

        # 1. Reverse match against all capabilities
        # Limit to 2000 to be safe
        all_caps = (
            db.session.query(BusinessCapability.id, BusinessCapability.name).limit(2000).all()
        )

        for cap_id, cap_name in all_caps:
            if not cap_name:
                continue

            # Use regex for whole word matching to avoid partial matches
            # e.g. avoid matching "Art" in "Department"
            # escape matches special regex chars in name
            pattern = r"\b" + re.escape(cap_name.lower()) + r"\b"
            if re.search(pattern, text_lower):
                candidates["capabilities"].append(cap_name)

        return candidates
