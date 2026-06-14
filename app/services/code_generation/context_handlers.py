"""
Context Handlers for Code Generation

Provides context-aware data loading for different code generation modes.
"""
from typing import Any, Dict, List, Optional

from app import db
from app.models.application_portfolio import ApplicationComponent

try:
    from app.models.application_layer import Application
except ImportError:
    # Fallback if application_layer not available
    Application = None
import logging

from app.services.mdd_code_generation_service import TechnologyStack, UMLElement

logger = logging.getLogger(__name__)


class EnhancementModeHandler:
    """
    Handle Application Enhancement mode context.

    Loads application data and provides enhancement suggestions for code generation.
    """

    @staticmethod
    def load_application_context(application_id: int) -> Dict[str, Any]:
        """
        Load application context for code generation.

        Args:
            application_id: Application ID

        Returns:
            Dictionary with application context data

        Raises:
            ValueError: If application not found
        """
        if Application is None:
            raise ValueError("Application model not available in this installation")

        application = Application.query.get(application_id)
        if not application:
            raise ValueError(f"Application {application_id} not found")

        # Get application components
        components = ApplicationComponent.query.filter_by(
            application_code=application.application_code
        ).all()

        # Extract technology stack
        tech_stack = EnhancementModeHandler._extract_technology_stack(application)

        context = {
            "application": {
                "id": application.id,
                "name": application.name,
                "description": application.description,
                "technology_stack": tech_stack,
            },
            "components": [
                {
                    "id": comp.id,
                    "name": comp.name,
                    "type": getattr(comp, "component_type", "component"),
                    "description": comp.description,
                }
                for comp in components
            ],
            "suggested_elements": EnhancementModeHandler._suggest_elements(application, components),
        }

        logger.info(f"Loaded application context for {application.name}")
        return context

    @staticmethod
    def _extract_technology_stack(application: Application) -> Dict[str, str]:
        """Extract technology stack from application."""
        # Try to get technology stack from application attributes
        tech_stack = {"primary_language": "python", "framework": "Flask", "database": "postgresql"}

        # Check if application has technology_stack attribute
        if hasattr(application, "technology_stack"):
            app_tech = application.technology_stack
            if isinstance(app_tech, dict):
                tech_stack.update(app_tech)
            elif isinstance(app_tech, str):
                # Parse string format
                if "python" in app_tech.lower():
                    tech_stack["primary_language"] = "python"
                elif "java" in app_tech.lower():
                    tech_stack["primary_language"] = "java"
                elif "typescript" in app_tech.lower() or "node" in app_tech.lower():
                    tech_stack["primary_language"] = "typescript"
                elif "salesforce" in app_tech.lower():
                    tech_stack["primary_language"] = "salesforce"

        return tech_stack

    @staticmethod
    def _suggest_elements(
        application: Application, components: List[ApplicationComponent]
    ) -> List[Dict]:
        """
        Suggest UML elements based on application and components.

        Args:
            application: Application instance
            components: List of application components

        Returns:
            List of suggested UML elements
        """
        suggestions = []

        # Suggest entity for main application
        suggestions.append(
            {
                "name": application.name.replace(" ", ""),
                "element_type": "class",
                "stereotype": "Entity",
                "package": "app.models",
                "description": application.description or f"{application.name} entity",
                "attributes": [
                    {"name": "id", "data_type": "Integer", "visibility": "private"},
                    {"name": "name", "data_type": "String", "visibility": "private"},
                    {"name": "description", "data_type": "Text", "visibility": "private"},
                    {"name": "created_at", "data_type": "DateTime", "visibility": "private"},
                    {"name": "updated_at", "data_type": "DateTime", "visibility": "private"},
                ],
                "methods": [],
            }
        )

        # Suggest service for application
        suggestions.append(
            {
                "name": f'{application.name.replace(" ", "")}Service',
                "element_type": "class",
                "stereotype": "Service",
                "package": "app.services",
                "description": f"Business logic service for {application.name}",
                "attributes": [],
                "methods": [
                    {
                        "name": "create",
                        "return_type": application.name.replace(" ", ""),
                        "parameters": "data: Dict",
                        "visibility": "public",
                    },
                    {
                        "name": "get_by_id",
                        "return_type": application.name.replace(" ", ""),
                        "parameters": "id: int",
                        "visibility": "public",
                    },
                    {
                        "name": "update",
                        "return_type": application.name.replace(" ", ""),
                        "parameters": "id: int, data: Dict",
                        "visibility": "public",
                    },
                    {
                        "name": "delete",
                        "return_type": "bool",
                        "parameters": "id: int",
                        "visibility": "public",
                    },
                ],
            }
        )

        # Suggest controller for application
        suggestions.append(
            {
                "name": f'{application.name.replace(" ", "")}Controller',
                "element_type": "class",
                "stereotype": "Controller",
                "package": "app.api",
                "description": f"REST API controller for {application.name}",
                "attributes": [],
                "methods": [
                    {
                        "name": "get_all",
                        "return_type": "Response",
                        "parameters": "",
                        "visibility": "public",
                    },
                    {
                        "name": "get_by_id",
                        "return_type": "Response",
                        "parameters": "id: int",
                        "visibility": "public",
                    },
                    {
                        "name": "create",
                        "return_type": "Response",
                        "parameters": "",
                        "visibility": "public",
                    },
                    {
                        "name": "update",
                        "return_type": "Response",
                        "parameters": "id: int",
                        "visibility": "public",
                    },
                    {
                        "name": "delete",
                        "return_type": "Response",
                        "parameters": "id: int",
                        "visibility": "public",
                    },
                ],
            }
        )

        # Suggest elements for each component
        for component in components[:5]:  # Limit to first 5 components
            comp_name = component.name.replace(" ", "")
            suggestions.append(
                {
                    "name": comp_name,
                    "element_type": "class",
                    "stereotype": "Entity",
                    "package": "app.models",
                    "description": component.description or f"{component.name} component",
                    "attributes": [
                        {"name": "id", "data_type": "Integer", "visibility": "private"},
                        {"name": "name", "data_type": "String", "visibility": "private"},
                        {"name": "description", "data_type": "Text", "visibility": "private"},
                    ],
                    "methods": [],
                }
            )

        return suggestions

    @staticmethod
    def get_enhancement_suggestions(application: Application) -> List[str]:
        """
        Get enhancement suggestions for application.

        Args:
            application: Application instance

        Returns:
            List of enhancement suggestions
        """
        if Application is None:
            return ["Application model not available for enhancement suggestions"]

        suggestions = []

        app_name = getattr(application, "name", "the application")
        suggestions.append(f"Generate REST API endpoints for {app_name}")
        suggestions.append(f"Create database models for {app_name}")
        suggestions.append(f"Implement business logic services for {app_name}")
        suggestions.append("Add data validation and error handling")
        suggestions.append(f"Generate unit tests for {app_name}")

        return suggestions

    @staticmethod
    def convert_to_uml_elements(context: Dict) -> List[UMLElement]:
        """
        Convert application context to UML elements.

        Args:
            context: Application context dictionary

        Returns:
            List of UMLElement instances
        """
        uml_elements = []

        for suggestion in context.get("suggested_elements", []):
            element = UMLElement(
                name=suggestion["name"],
                element_type=suggestion["element_type"],
                stereotype=suggestion["stereotype"],
                package=suggestion["package"],
                description=suggestion["description"],
            )

            # Add attributes
            for attr in suggestion.get("attributes", []):
                element.add_attribute(
                    name=attr["name"], data_type=attr["data_type"], visibility=attr["visibility"]
                )

            # Add methods
            for method in suggestion.get("methods", []):
                element.add_method(
                    name=method["name"],
                    return_type=method["return_type"],
                    parameters=method["parameters"],
                    visibility=method["visibility"],
                )

            uml_elements.append(element)

        return uml_elements


class ArchitectureModeHandler:
    """
    Handle Architecture-to-Code mode context.

    Loads ArchiMate view data and provides architecture suggestions for code generation.
    """

    @staticmethod
    def load_archimate_context(view_id: int) -> Dict[str, Any]:
        """
        Load ArchiMate view context for code generation.

        Args:
            view_id: ArchiMate view ID

        Returns:
            Dictionary with architecture context data

        Raises:
            ValueError: If view not found
        """
        try:
            from app.models.archimate_element import ArchiMateElement
            from app.models.archimate_view import ArchiMateView
        except ImportError:
            logger.warning("ArchiMate models not available")
            raise ValueError("ArchiMate models not available in this installation")

        view = ArchiMateView.query.get(view_id)
        if not view:
            raise ValueError(f"ArchiMate view {view_id} not found")

        # Get elements in view
        elements = []
        if hasattr(view, "elements"):
            elements = view.elements

        context = {
            "view": {
                "id": view.id,
                "name": view.name,
                "viewpoint": getattr(view, "viewpoint", "application"),
                "description": view.description,
            },
            "elements": [
                {
                    "id": elem.id,
                    "name": elem.name,
                    "type": elem.element_type,
                    "description": getattr(elem, "description", ""),
                }
                for elem in elements
            ],
            "suggested_elements": ArchitectureModeHandler._suggest_from_architecture(
                view, elements
            ),
        }

        logger.info(f"Loaded ArchiMate context for view {view.name}")
        return context

    @staticmethod
    def _suggest_from_architecture(view, elements: List) -> List[Dict]:
        """
        Suggest UML elements based on architecture view.

        Args:
            view: ArchiMate view instance
            elements: List of ArchiMate elements

        Returns:
            List of suggested UML elements
        """
        suggestions = []

        for elem in elements[:10]:  # Limit to first 10 elements
            # Map ArchiMate element types to UML stereotypes
            stereotype_map = {
                "application-component": "Entity",
                "application-service": "Service",
                "application-interface": "Controller",
                "data-object": "Entity",
                "business-object": "Entity",
            }

            elem_type = getattr(elem, "element_type", "component")
            stereotype = stereotype_map.get(elem_type, "Entity")

            suggestions.append(
                {
                    "name": elem.name.replace(" ", ""),
                    "element_type": "class",
                    "stereotype": stereotype,
                    "package": "app.models" if stereotype == "Entity" else "app.services",
                    "description": getattr(elem, "description", f"{elem.name} from architecture"),
                    "attributes": [
                        {"name": "id", "data_type": "Integer", "visibility": "private"},
                        {"name": "name", "data_type": "String", "visibility": "private"},
                    ],
                    "methods": [],
                }
            )

        return suggestions

    @staticmethod
    def get_architecture_suggestions(view) -> List[str]:
        """
        Get architecture-based suggestions.

        Args:
            view: ArchiMate view instance

        Returns:
            List of suggestions
        """
        suggestions = []

        suggestions.append(f"Generate code from {view.name} architecture view")
        suggestions.append("Create application components from architecture elements")
        suggestions.append("Implement services based on architecture layers")
        suggestions.append("Generate data models from business objects")

        return suggestions

    @staticmethod
    def convert_to_uml_elements(context: Dict) -> List[UMLElement]:
        """
        Convert architecture context to UML elements.

        Args:
            context: Architecture context dictionary

        Returns:
            List of UMLElement instances
        """
        uml_elements = []

        for suggestion in context.get("suggested_elements", []):
            element = UMLElement(
                name=suggestion["name"],
                element_type=suggestion["element_type"],
                stereotype=suggestion["stereotype"],
                package=suggestion["package"],
                description=suggestion["description"],
            )

            # Add attributes
            for attr in suggestion.get("attributes", []):
                element.add_attribute(
                    name=attr["name"], data_type=attr["data_type"], visibility=attr["visibility"]
                )

            # Add methods
            for method in suggestion.get("methods", []):
                element.add_method(
                    name=method["name"],
                    return_type=method["return_type"],
                    parameters=method.get("parameters", ""),
                    visibility=method["visibility"],
                )

            uml_elements.append(element)

        return uml_elements


class ContextHandlerFactory:
    """Factory for creating context handlers based on mode."""

    @staticmethod
    def get_handler(mode: str):
        """
        Get appropriate context handler for mode.

        Args:
            mode: Generation mode ('enhancement' or 'architecture')

        Returns:
            Context handler instance

        Raises:
            ValueError: If mode is invalid
        """
        if mode == "enhancement":
            return EnhancementModeHandler()
        elif mode == "architecture":
            return ArchitectureModeHandler()
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'enhancement' or 'architecture'")
