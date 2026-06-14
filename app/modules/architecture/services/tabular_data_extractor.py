"""
Tabular Data Extractor for ArchiMate Engine

Parses Excel/CSV files and maps them to ArchiMate elements.
Supports application portfolios, server inventories, business capability catalogs, etc.
"""

import csv
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from app import db
from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel
from app.services.llm_service import LLMService

# Column mapping templates for common portfolio types
COLUMN_MAPPINGS = {
    "application_portfolio": {
        "element_type": "ApplicationComponent",
        "layer": "Application",
        "required_columns": ["name"],
        "optional_columns": {
            "vendor": "properties.vendor",
            "version": "properties.version",
            "business_process": "relationships.realizes",
            "technology_stack": "relationships.composed_of",
            "cost": "properties.cost",
            "lifecycle_status": "properties.lifecycle_status",
            "owner": "properties.owner",
            "criticality": "properties.criticality",
        },
    },
    "server_inventory": {
        "element_type": "Node",
        "layer": "Technology",
        "required_columns": ["name"],
        "optional_columns": {
            "hostname": "properties.hostname",
            "ip_address": "properties.ip_address",
            "os": "properties.operating_system",
            "location": "properties.location",
            "environment": "properties.environment",
            "applications_hosted": "relationships.hosts",
            "cpu": "properties.cpu",
            "memory": "properties.memory",
            "storage": "properties.storage",
        },
    },
    "business_capability_catalog": {
        "element_type": "Capability",
        "layer": "Strategy",
        "required_columns": ["name"],
        "optional_columns": {
            "description": "description",
            "parent_capability": "relationships.aggregates",
            "supporting_applications": "relationships.realized_by",
            "maturity_level": "properties.maturity_level",
            "strategic_importance": "properties.strategic_importance",
            "investment_priority": "properties.investment_priority",
        },
    },
    "business_process_catalog": {
        "element_type": "BusinessProcess",
        "layer": "Business",
        "required_columns": ["name"],
        "optional_columns": {
            "description": "description",
            "owner": "properties.owner",
            "supporting_applications": "relationships.realized_by",
            "actors": "relationships.assigned_to",
            "inputs": "relationships.accesses",
            "outputs": "relationships.produces",
            "kpis": "properties.kpis",
        },
    },
    "technology_service_catalog": {
        "element_type": "TechnologyService",
        "layer": "Technology",
        "required_columns": ["name"],
        "optional_columns": {
            "description": "description",
            "provider": "properties.provider",
            "sla": "properties.sla",
            "consuming_applications": "relationships.serves",
            "underlying_infrastructure": "relationships.realized_by",
        },
    },
}


class TabularDataExtractor:
    """
    Service for extracting ArchiMate elements from tabular data (Excel/CSV)
    """

    def __init__(self):
        """Initialize the tabular data extractor"""
        pass

    def detect_portfolio_type(self, df: pd.DataFrame) -> str:
        """
        Auto-detect the type of portfolio from column names

        Args:
            df: Pandas DataFrame with the data

        Returns:
            Portfolio type key from COLUMN_MAPPINGS
        """
        columns_lower = [col.lower().strip() for col in df.columns]

        # Check for application portfolio indicators
        app_indicators = ["application", "vendor", "version", "technology_stack"]
        if any(ind in " ".join(columns_lower) for ind in app_indicators):
            return "application_portfolio"

        # Check for server inventory indicators
        server_indicators = ["hostname", "ip_address", "server", "node", "os", "operating_system"]
        if any(ind in " ".join(columns_lower) for ind in server_indicators):
            return "server_inventory"

        # Check for capability indicators
        capability_indicators = ["capability", "maturity", "strategic_importance"]
        if any(ind in " ".join(columns_lower) for ind in capability_indicators):
            return "business_capability_catalog"

        # Check for process indicators
        process_indicators = ["process", "owner", "kpi", "actor"]
        if any(ind in " ".join(columns_lower) for ind in process_indicators):
            return "business_process_catalog"

        # Check for service indicators
        service_indicators = ["service", "sla", "provider"]
        if any(ind in " ".join(columns_lower) for ind in service_indicators):
            return "technology_service_catalog"

        # Default to application portfolio if unclear
        return "application_portfolio"

    def normalize_column_name(self, column: str) -> str:
        """
        Normalize column names for matching

        Args:
            column: Raw column name from file

        Returns:
            Normalized column name (lowercase, underscores)
        """
        return column.lower().strip().replace(" ", "_").replace("-", "_")

    def map_columns(self, df: pd.DataFrame, portfolio_type: str) -> Dict[str, str]:
        """
        Map DataFrame columns to ArchiMate properties

        Args:
            df: Pandas DataFrame
            portfolio_type: Type of portfolio

        Returns:
            Dictionary mapping normalized column names to property paths
        """
        mapping_template = COLUMN_MAPPINGS.get(portfolio_type, {})
        column_mapping = {}

        # Normalize all column names
        normalized_columns = {self.normalize_column_name(col): col for col in df.columns}

        # Map required columns
        required = mapping_template.get("required_columns", [])
        for req_col in required:
            norm_req = self.normalize_column_name(req_col)
            if norm_req in normalized_columns:
                column_mapping[normalized_columns[norm_req]] = "name"

        # Check for name column variations
        name_variations = [
            "name",
            "application_name",
            "server_name",
            "capability_name",
            "process_name",
            "service_name",
            "title",
            "component_name",
        ]
        for var in name_variations:
            norm_var = self.normalize_column_name(var)
            if norm_var in normalized_columns and "name" not in column_mapping.values():
                column_mapping[normalized_columns[norm_var]] = "name"
                break

        # Map optional columns
        optional = mapping_template.get("optional_columns", {})
        for opt_col, target_path in optional.items():
            norm_opt = self.normalize_column_name(opt_col)
            if norm_opt in normalized_columns:
                column_mapping[normalized_columns[norm_opt]] = target_path

        return column_mapping

    def read_file(self, file_path: str) -> pd.DataFrame:
        """
        Read Excel or CSV file into DataFrame

        Args:
            file_path: Path to the file

        Returns:
            Pandas DataFrame

        Raises:
            ValueError: If file format is not supported
        """
        ext = file_path.rsplit(".", 1)[-1].lower()

        if ext == "csv":
            return pd.read_csv(file_path, encoding="utf-8-sig")  # Handle BOM
        elif ext in ["xls", "xlsx"]:
            return pd.read_excel(file_path, engine="openpyxl" if ext == "xlsx" else "xlrd")
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def extract_elements(
        self,
        file_path: str,
        architecture_id: int,
        portfolio_type: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Extract ArchiMate elements from tabular data

        Args:
            file_path: Path to Excel/CSV file
            architecture_id: ID of parent architecture
            portfolio_type: Optional explicit portfolio type (auto-detected if None)
            user_id: Optional user ID for tracking

        Returns:
            Dictionary with extraction results:
            {
                'elements_created': int,
                'relationships_created': int,
                'portfolio_type': str,
                'errors': List[str],
                'warnings': List[str]
            }
        """
        results = {
            "elements_created": 0,
            "relationships_created": 0,
            "portfolio_type": "",
            "errors": [],
            "warnings": [],
        }

        try:
            # Read file
            df = self.read_file(file_path)

            if df.empty:
                results["errors"].append("File is empty or has no data")
                return results

            # Detect or use provided portfolio type
            detected_type = portfolio_type or self.detect_portfolio_type(df)
            results["portfolio_type"] = detected_type

            # Get mapping configuration
            mapping_config = COLUMN_MAPPINGS.get(detected_type)
            if not mapping_config:
                results["errors"].append(f"Unknown portfolio type: {detected_type}")
                return results

            # Map columns
            column_mapping = self.map_columns(df, detected_type)

            # Check if we have name column
            if "name" not in column_mapping.values():
                results["errors"].append("Could not find a 'name' column in the file")
                return results

            # Get architecture
            architecture = db.session.get(ArchitectureModel, architecture_id)
            if not architecture:
                results["errors"].append(f"Architecture {architecture_id} not found")
                return results

            # Process each row
            element_map = {}  # Store created elements for relationship linking

            for idx, row in df.iterrows():
                try:
                    # Extract element name
                    name_col = [col for col, target in column_mapping.items() if target == "name"][
                        0
                    ]
                    element_name = str(row[name_col]).strip()

                    if not element_name or element_name.lower() in ["nan", "none", ""]:
                        results["warnings"].append(f"Row {idx + 2}: Skipping row with empty name")
                        continue

                    # Check if element already exists
                    existing = ArchiMateElement.query.filter_by(
                        architecture_id=architecture_id,
                        name=element_name,
                        type=mapping_config["element_type"],
                    ).first()

                    if existing:
                        results["warnings"].append(
                            f"Row {idx + 2}: Element '{element_name}' already exists, skipping"
                        )
                        element_map[element_name] = existing
                        continue

                    # Create new element
                    element = ArchiMateElement(
                        architecture_id=architecture_id,
                        name=element_name,
                        type=mapping_config["element_type"],
                        layer=mapping_config["layer"],
                        created_at=datetime.utcnow(),
                    )

                    # Extract properties and description
                    properties = {}
                    relationships_to_create = {}

                    for col, target_path in column_mapping.items():
                        if col == name_col or target_path == "name":
                            continue

                        value = row[col]
                        if pd.isna(value) or str(value).strip() == "":
                            continue

                        value_str = str(value).strip()

                        # Handle different target paths
                        if target_path == "description":
                            element.description = value_str
                        elif target_path.startswith("properties."):
                            prop_name = target_path.split(".", 1)[1]
                            properties[prop_name] = value_str
                        elif target_path.startswith("relationships."):
                            rel_type = target_path.split(".", 1)[1]
                            relationships_to_create[rel_type] = value_str

                    # Store properties as JSON
                    if properties:
                        element.properties = properties

                    # Save element
                    db.session.add(element)
                    db.session.flush()  # Get element ID

                    element_map[element_name] = element
                    results["elements_created"] += 1

                    # Store relationship data for later processing
                    if relationships_to_create:
                        element._pending_relationships = relationships_to_create

                except Exception as row_error:
                    results["errors"].append(f"Row {idx + 2}: {str(row_error)}")
                    continue

            # Commit all elements first
            db.session.commit()

            # Process relationships after all elements are created
            for element_name, element in element_map.items():
                if hasattr(element, "_pending_relationships"):
                    for rel_type, target_names in element._pending_relationships.items():
                        # Parse comma-separated target names
                        targets = [t.strip() for t in target_names.split(",")]

                        for target_name in targets:
                            if not target_name:
                                continue

                            # Find or create target element
                            target_element = element_map.get(target_name)

                            if target_element:
                                # Map relationship type to ArchiMate relationship
                                archimate_rel_type = self._map_relationship_type(rel_type)

                                # Create relationship
                                relationship = ArchiMateRelationship(
                                    architecture_id=architecture_id,
                                    source_id=element.id,
                                    target_id=target_element.id,
                                    type=archimate_rel_type,
                                    created_at=datetime.utcnow(),
                                )
                                db.session.add(relationship)
                                results["relationships_created"] += 1

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            results["errors"].append(f"Fatal error: {str(e)}")

        return results

    def _map_relationship_type(self, semantic_type: str) -> str:
        """
        Map semantic relationship type to ArchiMate relationship type

        Args:
            semantic_type: Semantic relationship name (e.g., 'realizes', 'hosts')

        Returns:
            ArchiMate relationship type
        """
        mapping = {
            "realizes": "Realization",
            "realized_by": "Realization",
            "composed_of": "Composition",
            "aggregates": "Aggregation",
            "hosts": "Assignment",
            "assigned_to": "Assignment",
            "serves": "Serving",
            "accesses": "Access",
            "produces": "Flow",
            "triggers": "Triggering",
            "influences": "Influence",
            "specializes": "Specialization",
        }

        return mapping.get(semantic_type, "Association")

    def generate_sample_template(self, portfolio_type: str) -> pd.DataFrame:
        """
        Generate sample template DataFrame for a portfolio type

        Args:
            portfolio_type: Type of portfolio

        Returns:
            Sample DataFrame with example data
        """
        if portfolio_type == "application_portfolio":
            return pd.DataFrame(
                [
                    {
                        "Application Name": "Customer Portal",
                        "Vendor": "Internal",
                        "Version": "2.1",
                        "Business Process Supported": "Customer Onboarding",
                        "Technology Stack": "React, Node.js, PostgreSQL",
                        "Cost": "50000",
                        "Lifecycle Status": "Active",
                        "Owner": "Digital Team",
                        "Criticality": "High",
                    }
                ]
            )
        elif portfolio_type == "server_inventory":
            return pd.DataFrame(
                [
                    {
                        "Server Name": "APP-PROD - 01",
                        "Hostname": "app-prod - 01.example.com",
                        "IP Address": "10.0.1.50",
                        "OS": "Ubuntu 22.04",
                        "Location": "AWS us-east - 1",
                        "Environment": "Production",
                        "Applications Hosted": "Customer Portal",
                        "CPU": "8 cores",
                        "Memory": "32GB",
                        "Storage": "500GB SSD",
                    }
                ]
            )
        elif portfolio_type == "business_capability_catalog":
            return pd.DataFrame(
                [
                    {
                        "Capability Name": "Customer Management",
                        "Description": "Ability to manage customer information",
                        "Parent Capability": "Customer Experience",
                        "Supporting Applications": "CRM System",
                        "Maturity Level": "Level 3",
                        "Strategic Importance": "High",
                        "Investment Priority": "1",
                    }
                ]
            )
        else:
            return pd.DataFrame()
