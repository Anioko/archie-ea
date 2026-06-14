"""Factory pattern for creating domain models from templates.

Centralizes domain model creation logic, making it extensible and testable.
Follows Factory pattern from Gang of Four design patterns.
"""

import logging
from typing import Optional, Type

from app import db
from app.models.application_layer import (
    ApplicationCollaboration,
    ApplicationEvent,
    ApplicationFunction,
    ApplicationInterface,
    ApplicationProcess,
    ApplicationService,
    DataObject,
)
from app.models.archimate_core import ArchiMateElement
from app.models.element_templates import ElementTemplate
from app.models.process_data import BusinessProcess

logger = logging.getLogger(__name__)


class DomainModelFactory:
    """Factory for creating domain-specific models from templates."""

    # Registry of element types to model classes
    _MODEL_REGISTRY = {
        "BusinessProcess": BusinessProcess,
        "ApplicationService": ApplicationService,
        "ApplicationFunction": ApplicationFunction,
        "ApplicationProcess": ApplicationProcess,
        "ApplicationInterface": ApplicationInterface,
        "ApplicationEvent": ApplicationEvent,
        "ApplicationCollaboration": ApplicationCollaboration,
        "DataObject": DataObject,
    }

    @classmethod
    def create_from_template(
        cls,
        template: ElementTemplate,
        archimate_element: ArchiMateElement,
        customizations: Optional[dict] = None,
    ) -> Optional[object]:
        """
        Create domain model from template and ArchiMate element.

        Args:
            template: Template to instantiate
            archimate_element: Created ArchiMate element
            customizations: Optional customizations

        Returns:
            Domain model instance or None if type not supported
        """
        model_class = cls._MODEL_REGISTRY.get(template.element_type)

        if not model_class:
            return None

        common_attrs = {
            "name": archimate_element.name,
            "description": archimate_element.description,
            "archimate_element_id": archimate_element.id,
        }

        # TYPE-SPECIFIC ATTRIBUTE MAPPING
        if template.element_type == "BusinessProcess" and template.default_properties:
            try:
                import json

                props = json.loads(template.default_properties)
                common_attrs["process_category"] = props.get("process_category")
            except Exception as e:
                logger.debug("Failed to parse BusinessProcess default_properties: %s", e)

        elif template.element_type == "ApplicationService" and template.default_properties:
            try:
                import json

                props = json.loads(template.default_properties)
                common_attrs["service_type"] = props.get("service_type")
                common_attrs["protocol"] = props.get("protocol")
            except Exception as e:
                logger.debug("Failed to parse ApplicationService default_properties: %s", e)

        elif template.element_type == "ApplicationFunction" and template.default_properties:
            try:
                import json

                props = json.loads(template.default_properties)
                common_attrs["function_type"] = props.get("function_type")
                common_attrs["complexity"] = props.get("complexity")
            except Exception as e:
                logger.debug("Failed to parse ApplicationFunction default_properties: %s", e)

        # Add type-specific attributes
        if template.element_type == "BusinessProcess":
            common_attrs.update(
                {
                    "process_code": template.code
                    # Note: framework info stored in template, not on domain model
                }
            )

        # Apply customizations if provided
        if customizations:
            common_attrs.update(
                {
                    k: v
                    for k, v in customizations.items()
                    if k in ["name", "description"] and v is not None
                }
            )

        return model_class(**common_attrs)

    @classmethod
    def get_model_class(cls, element_type: str) -> Optional[Type]:
        """Get model class for element type."""
        return cls._MODEL_REGISTRY.get(element_type)

    @classmethod
    def register_model(cls, element_type: str, model_class: Type) -> None:
        """
        Register new domain model type.
        Allows extending factory without modifying code (Open/Closed Principle).
        """
        cls._MODEL_REGISTRY[element_type] = model_class

    @classmethod
    def supports_element_type(cls, element_type: str) -> bool:
        """Check if element type has domain model support."""
        return element_type in cls._MODEL_REGISTRY
