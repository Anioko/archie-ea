"""

Application to UML Adapter Service

Converts archie ApplicationComponent models to MDD UMLElement format
for code generation. This adapter bridges the gap between archie's
enterprise architecture data model and MDD's UML-based code generation.
"""
import logging
from typing import Dict, List

from app.models import ApplicationComponent, BusinessCapability
from app.services.mdd_code_generation_service import UMLElement

logger = logging.getLogger(__name__)


class ApplicationToUMLAdapter:
    """
    Adapter to convert archie ApplicationComponent to MDD UMLElement.

    This enables MDD hybrid code generation to work with archie's
    existing application portfolio data.
    """

    @staticmethod
    def _determine_element_type(application: ApplicationComponent) -> str:
        """Determine UML element type from application."""
        component_type = (application.component_type or "").lower()

        type_mapping = {
            "service": "service",
            "application": "class",
            "component": "component",
            "interface": "interface",
            "api": "interface",
            "database": "entity",
            "microservice": "service",
        }

        return type_mapping.get(component_type, "class")

    @staticmethod
    def _determine_stereotype(application: ApplicationComponent) -> str:
        """Determine UML stereotype from application."""
        component_type = (application.component_type or "").lower()

        stereotype_mapping = {
            "service": "Service",
            "api": "Controller",
            "database": "Repository",
            "application": "Entity",
            "microservice": "Service",
            "interface": "Interface",
        }

        return stereotype_mapping.get(component_type, "Entity")

    @staticmethod
    def _get_package_name(application: ApplicationComponent) -> str:
        """Generate package name from application metadata."""
        if hasattr(application, "organization") and application.organization:
            org_name = application.organization.replace(" ", "").lower()
            app_name = (application.name or "").replace(" ", "").lower()
            return f"com.{org_name}.{app_name}"

        app_name = (application.name or "generated").replace(" ", "").lower()
        return f"com.enterprise.{app_name}"

    @staticmethod
    def _add_capability_attributes(uml_element: UMLElement, application: ApplicationComponent):
        """Add business capabilities as UML attributes."""
        try:
            from app.models import ApplicationCapabilityMapping

            mappings = ApplicationCapabilityMapping.query.filter_by(
                application_id=application.id
            ).all()

            for mapping in mappings[:10]:
                if mapping.capability:
                    uml_element.add_attribute(
                        name=f"capability_{mapping.capability.apqc_id}".replace(".", "_"),
                        data_type="BusinessCapability",
                        visibility="private",
                        default_value=None,
                    )

        except Exception as e:
            logger.warning(f"Could not add capability attributes: {str(e)}")

    @staticmethod
    def _add_standard_attributes(uml_element: UMLElement, application: ApplicationComponent):
        """Add standard application attributes to UML element."""
        uml_element.add_attribute("id", "Integer", "private")
        uml_element.add_attribute("name", "String", "private")
        uml_element.add_attribute("description", "String", "private")
        uml_element.add_attribute("lifecycle_status", "String", "private")
        uml_element.add_attribute("component_type", "String", "private")
        uml_element.add_attribute("created_at", "DateTime", "private")
        uml_element.add_attribute("updated_at", "DateTime", "private")

    @staticmethod
    def _add_standard_methods(uml_element: UMLElement, application: ApplicationComponent):
        """Add standard CRUD methods to UML element."""
        class_name = uml_element.name

        uml_element.add_method(
            name="__init__",
            return_type="None",
            parameters="self, name: str, description: str = None",
            visibility="public",
            is_constructor=True,
        )

        uml_element.add_method(
            name="get_id", return_type="Integer", parameters="self", visibility="public"
        )

        uml_element.add_method(
            name="get_name", return_type="String", parameters="self", visibility="public"
        )

        uml_element.add_method(
            name="update", return_type="Boolean", parameters="self, **kwargs", visibility="public"
        )

        uml_element.add_method(
            name="to_dict", return_type="Dict", parameters="self", visibility="public"
        )

    @staticmethod
    def _extract_technology_stack(application: ApplicationComponent) -> Dict:
        """Extract technology stack information from application."""
        tech_stack = {
            "primary_language": ApplicationToUMLAdapter._detect_primary_language(application),
            "framework": ApplicationToUMLAdapter._detect_framework(application),
            "database": ApplicationToUMLAdapter._detect_database(application),
            "technologies": [],
        }

        try:
            from app.models import ApplicationTechnologyMapping

            tech_mappings = ApplicationTechnologyMapping.query.filter_by(
                application_id=application.id
            ).all()

            for mapping in tech_mappings:
                if mapping.technology_product:
                    tech_stack["technologies"].append(
                        {
                            "name": mapping.technology_product.name,
                            "category": mapping.technology_product.category,
                            "vendor": mapping.technology_product.vendor_name,
                        }
                    )

        except Exception as e:
            logger.warning(f"Could not extract technology mappings: {str(e)}")

        return tech_stack

    @staticmethod
    def _detect_primary_language(application: ApplicationComponent) -> str:
        """Detect primary programming language from application metadata."""
        try:
            from app.models import ApplicationTechnologyMapping

            tech_mappings = ApplicationTechnologyMapping.query.filter_by(
                application_id=application.id
            ).all()

            language_keywords = {
                "python": ["python", "django", "flask", "fastapi"],
                "java": ["java", "spring", "hibernate", "maven"],
                "javascript": ["javascript", "node", "express", "react"],
                "typescript": ["typescript", "angular", "nestjs"],
                "csharp": ["c#", ".net", "asp.net"],
                "salesforce": ["salesforce", "apex", "lightning"],
            }

            for mapping in tech_mappings:
                if mapping.technology_product:
                    tech_name = mapping.technology_product.name.lower()
                    for lang, keywords in language_keywords.items():
                        if any(keyword in tech_name for keyword in keywords):
                            return lang

        except Exception as e:
            logger.warning(f"Could not detect language: {str(e)}")

        return "python"

    @staticmethod
    def _detect_framework(application: ApplicationComponent) -> str:
        """Detect framework from application metadata."""
        try:
            from app.models import ApplicationTechnologyMapping

            tech_mappings = ApplicationTechnologyMapping.query.filter_by(
                application_id=application.id
            ).all()

            framework_keywords = {
                "Flask": ["flask"],
                "Django": ["django"],
                "FastAPI": ["fastapi"],
                "Spring Boot": ["spring", "spring boot"],
                "Express": ["express"],
                "NestJS": ["nestjs", "nest"],
                "React": ["react"],
                "Angular": ["angular"],
                "Salesforce": ["salesforce", "apex"],
            }

            for mapping in tech_mappings:
                if mapping.technology_product:
                    tech_name = mapping.technology_product.name.lower()
                    for framework, keywords in framework_keywords.items():
                        if any(keyword in tech_name for keyword in keywords):
                            return framework

        except Exception as e:
            logger.warning(f"Could not detect framework: {str(e)}")

        return "Flask"

    @staticmethod
    def _detect_database(application: ApplicationComponent) -> str:
        """Detect database from application metadata."""
        try:
            from app.models import ApplicationTechnologyMapping

            tech_mappings = ApplicationTechnologyMapping.query.filter_by(
                application_id=application.id
            ).all()

            db_keywords = {
                "postgresql": ["postgres", "postgresql"],
                "mysql": ["mysql", "mariadb"],
                "mongodb": ["mongodb", "mongo"],
                "oracle": ["oracle"],
                "sqlserver": ["sql server", "mssql"],
                "sqlite": ["sqlite"],
            }

            for mapping in tech_mappings:
                if mapping.technology_product:
                    tech_name = mapping.technology_product.name.lower()
                    for db, keywords in db_keywords.items():
                        if any(keyword in tech_name for keyword in keywords):
                            return db

        except Exception as e:
            logger.warning(f"Could not detect database: {str(e)}")

        return "postgresql"


class BulkCodeGenerationContext:
    """
    Context manager for bulk code generation from multiple applications.

    Handles batching, technology stack detection, and result aggregation.
    """

    def __init__(
        self,
        application_ids: List[int],
        override_language: str = None,
        override_framework: str = None,
    ):
        self.application_ids = application_ids
        self.override_language = override_language
        self.override_framework = override_framework
        self.applications = []
        self.uml_elements = []
        self.technology_stacks = {}

    def prepare(self):
        """Prepare context for code generation."""
        self.load_applications()
        self.convert_to_uml()
        self.detect_technology_stacks()
