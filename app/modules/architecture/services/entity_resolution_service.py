"""
Entity Resolution Service

Advanced entity resolution and disambiguation for document analysis.
Features:
- Acronym expansion (CRM → Customer Relationship Management → Salesforce CRM)
- Vendor/product name normalization
- Technology stack standardization
- Entity linking to knowledge base
- Confidence scoring for resolutions
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import func, or_

from app import db
from app.models.application_layer import ApplicationComponent
from app.models.archimate_core import ArchiMateElement
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

logger = logging.getLogger(__name__)


class EntityResolutionService:
    """
    Service for resolving and disambiguating entities extracted from documents.
    """

    # Common acronyms and their expansions
    COMMON_ACRONYMS = {
        "CRM": ["Customer Relationship Management", "Salesforce CRM", "Microsoft Dynamics CRM"],
        "ERP": ["Enterprise Resource Planning", "SAP ERP", "Oracle ERP", "Microsoft Dynamics ERP"],
        "HRIS": ["Human Resources Information System", "Workday", "SAP SuccessFactors"],
        "HCM": ["Human Capital Management", "Workday HCM", "Oracle HCM"],
        "SCM": ["Supply Chain Management", "SAP SCM", "Oracle SCM"],
        "PLM": ["Product Lifecycle Management", "Siemens PLM", "PTC Windchill"],
        "MES": ["Manufacturing Execution System", "Siemens MES", "Rockwell MES"],
        "SCADA": ["Supervisory Control and Data Acquisition", "Siemens SCADA", "Rockwell SCADA"],
        "BI": ["Business Intelligence", "Tableau", "Power BI", "Qlik"],
        "DW": ["Data Warehouse", "Snowflake", "Amazon Redshift", "Google BigQuery"],
        "API": ["Application Programming Interface"],
        "REST": ["REST API", "RESTful API"],
        "SOAP": ["SOAP API", "SOAP Web Service"],
        "ESB": ["Enterprise Service Bus", "MuleSoft ESB", "IBM ESB"],
        "MDM": ["Master Data Management", "Informatica MDM", "SAP MDM"],
        "DWH": ["Data Warehouse", "Snowflake", "Amazon Redshift"],
        "WMS": ["Warehouse Management System", "SAP WMS", "Oracle WMS"],
        "TMS": ["Transportation Management System", "SAP TMS", "Oracle TMS"],
    }

    # Vendor name variations
    VENDOR_VARIATIONS = {
        "microsoft": ["MS", "Microsoft Corp", "Microsoft Corporation", "MSFT"],
        "oracle": ["Oracle Corp", "Oracle Corporation"],
        "salesforce": ["SF", "Salesforce.com", "SFDC"],
        "sap": ["SAP AG", "SAP SE"],
        "amazon": ["AWS", "Amazon Web Services", "Amazon"],
        "google": ["GCP", "Google Cloud Platform", "Google Cloud"],
        "ibm": ["IBM Corp", "International Business Machines"],
        "adobe": ["Adobe Systems", "Adobe Inc"],
    }

    def __init__(self):
        """Initialize entity resolution service."""
        self._build_resolution_cache()

    def _build_resolution_cache(self):
        """Build cache of known entities from database."""
        self._known_applications = {}
        self._known_vendors = {}
        self._known_products = {}

        try:
            # Cache application names
            apps = ApplicationComponent.query.with_entities(
                ApplicationComponent.id,
                ApplicationComponent.name,
                func.lower(ApplicationComponent.name).label("name_lower"),
            ).all()
            for app in apps:
                self._known_applications[app.name_lower] = {
                    "id": app.id,
                    "name": app.name,
                    "type": "application",
                }

            # Cache vendor names
            vendors = VendorOrganization.query.with_entities(
                VendorOrganization.id,
                VendorOrganization.name,
                func.lower(VendorOrganization.name).label("name_lower"),
            ).all()
            for vendor in vendors:
                self._known_vendors[vendor.name_lower] = {
                    "id": vendor.id,
                    "name": vendor.name,
                    "type": "vendor",
                }

            logger.info(
                f"Cached {len(self._known_applications)} applications and {len(self._known_vendors)} vendors"
            )
        except Exception as e:
            logger.warning(f"Could not build resolution cache: {e}")

    def resolve_entity(
        self, entity_name: str, entity_type: Optional[str] = None, context: Optional[str] = None
    ) -> Dict:
        """
        Resolve an entity name to its canonical form and link to database.

        Args:
            entity_name: The entity name to resolve
            entity_type: Optional type hint ('application', 'vendor', 'product', etc.)
            context: Optional context text for disambiguation

        Returns:
            Resolution result with canonical name, confidence, and database link
        """
        original_name = entity_name.strip()
        normalized = self._normalize_name(original_name)

        # Step 1: Check if it's an acronym
        acronym_resolution = self._resolve_acronym(original_name, context)
        if acronym_resolution:
            return acronym_resolution

        # Step 2: Check database for exact/close match
        db_match = self._match_in_database(normalized, entity_type)
        if db_match:
            return db_match

        # Step 3: Vendor name normalization
        vendor_match = self._normalize_vendor_name(normalized)
        if vendor_match and vendor_match != normalized:
            # Re-check database with normalized vendor name
            db_match = self._match_in_database(vendor_match, "vendor")
            if db_match:
                return db_match

        # Step 4: Technology stack standardization
        tech_match = self._standardize_technology(normalized)
        if tech_match and tech_match != normalized:
            return {
                "original": original_name,
                "resolved": tech_match,
                "confidence": 0.75,
                "method": "technology_standardization",
                "database_match": None,
                "suggestions": [tech_match],
            }

        # Step 5: Fuzzy matching against known entities
        fuzzy_match = self._fuzzy_match(normalized, entity_type)
        if fuzzy_match and fuzzy_match["confidence"] > 0.7:
            return fuzzy_match

        # No resolution found
        return {
            "original": original_name,
            "resolved": original_name,  # Keep original if no resolution
            "confidence": 0.0,
            "method": "no_match",
            "database_match": None,
            "suggestions": [],
        }

    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for matching."""
        # Remove extra whitespace
        name = " ".join(name.split())
        # Remove common prefixes/suffixes
        name = re.sub(r"^(The|A|An)\s+", "", name, flags=re.IGNORECASE)
        # Remove special characters but keep spaces
        name = re.sub(r"[^\w\s-]", "", name)
        return name.strip().lower()

    def _resolve_acronym(self, name: str, context: Optional[str]) -> Optional[Dict]:
        """Resolve acronyms to full names."""
        name_upper = name.upper().strip()

        # Direct acronym match
        if name_upper in self.COMMON_ACRONYMS:
            expansions = self.COMMON_ACRONYMS[name_upper]
            best_match = expansions[0]  # Default to first expansion

            # If context provided, try to disambiguate
            if context:
                context_lower = context.lower()
                for expansion in expansions:
                    # Check if expansion or vendor name appears in context
                    if any(word.lower() in context_lower for word in expansion.split()):
                        best_match = expansion
                        break

            # Check if resolved name exists in database
            db_match = self._match_in_database(best_match.lower(), None)
            if db_match and db_match["database_match"]:
                return {
                    "original": name,
                    "resolved": db_match["database_match"]["name"],
                    "confidence": 0.9,
                    "method": "acronym_resolution_with_db_match",
                    "database_match": db_match["database_match"],
                    "suggestions": expansions,
                }

            return {
                "original": name,
                "resolved": best_match,
                "confidence": 0.85,
                "method": "acronym_resolution",
                "database_match": None,
                "suggestions": expansions,
            }

        return None

    def _match_in_database(
        self, normalized_name: str, entity_type: Optional[str]
    ) -> Optional[Dict]:
        """Match entity against database records."""
        matches = []

        # Search applications
        if not entity_type or entity_type == "application":
            app_match = self._known_applications.get(normalized_name)
            if app_match:
                matches.append(
                    {
                        "type": "application",
                        "id": app_match["id"],
                        "name": app_match["name"],
                        "confidence": 1.0,
                    }
                )

        # Search vendors
        if not entity_type or entity_type == "vendor":
            vendor_match = self._known_vendors.get(normalized_name)
            if vendor_match:
                matches.append(
                    {
                        "type": "vendor",
                        "id": vendor_match["id"],
                        "name": vendor_match["name"],
                        "confidence": 1.0,
                    }
                )

        if matches:
            best_match = max(matches, key=lambda x: x["confidence"])
            return {
                "original": normalized_name,
                "resolved": best_match["name"],
                "confidence": best_match["confidence"],
                "method": "database_exact_match",
                "database_match": {
                    "type": best_match["type"],
                    "id": best_match["id"],
                    "name": best_match["name"],
                },
                "suggestions": [m["name"] for m in matches],
            }

        return None

    def _normalize_vendor_name(self, name: str) -> Optional[str]:
        """Normalize vendor name variations."""
        name_lower = name.lower()

        for canonical, variations in self.VENDOR_VARIATIONS.items():
            if name_lower == canonical or name_lower in [v.lower() for v in variations]:
                return canonical.title()

        return None

    def _standardize_technology(self, name: str) -> Optional[str]:
        """Standardize technology stack names."""
        name_lower = name.lower()

        # Common technology mappings
        tech_mappings = {
            "react.js": "React",
            "reactjs": "React",
            "node.js": "Node.js",
            "nodejs": "Node.js",
            "vue.js": "Vue.js",
            "vuejs": "Vue.js",
            "angular.js": "Angular",
            "angularjs": "Angular",
            "postgres": "PostgreSQL",
            "postgresql": "PostgreSQL",
            "mysql": "MySQL",
            "mssql": "Microsoft SQL Server",
            "sql server": "Microsoft SQL Server",
            "aws s3": "Amazon S3",
            "aws ec2": "Amazon EC2",
            "gcp": "Google Cloud Platform",
        }

        return tech_mappings.get(name_lower, None)

    def _fuzzy_match(self, normalized_name: str, entity_type: Optional[str]) -> Optional[Dict]:
        """Fuzzy match against known entities."""
        best_match = None
        best_score = 0.0
        best_entity = None

        # Search in appropriate cache
        search_space = {}
        if not entity_type or entity_type == "application":
            search_space.update(self._known_applications)
        if not entity_type or entity_type == "vendor":
            search_space.update(self._known_vendors)

        for cached_name, entity_data in search_space.items():
            similarity = SequenceMatcher(None, normalized_name, cached_name).ratio()
            if similarity > best_score and similarity > 0.7:
                best_score = similarity
                best_match = cached_name
                best_entity = entity_data

        if best_match:
            return {
                "original": normalized_name,
                "resolved": best_entity["name"],
                "confidence": best_score,
                "method": "fuzzy_match",
                "database_match": {
                    "type": best_entity["type"],
                    "id": best_entity["id"],
                    "name": best_entity["name"],
                },
                "suggestions": [best_entity["name"]],
            }

        return None

    def resolve_entities_batch(
        self, entities: List[Dict], context: Optional[str] = None
    ) -> List[Dict]:
        """
        Resolve a batch of entities.

        Args:
            entities: List of entity dicts with 'name' and optionally 'type'
            context: Optional shared context for all entities

        Returns:
            List of resolution results
        """
        results = []
        for entity in entities:
            entity_name = entity.get("name", "")
            entity_type = entity.get("type")
            resolution = self.resolve_entity(entity_name, entity_type, context)
            results.append({**entity, "resolution": resolution})

        return results
