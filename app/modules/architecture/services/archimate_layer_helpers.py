# WARNING: THIS FILE IS NOT REGISTERED
# mass-deletion-ok
"""
Helper methods for multi-stage ArchiMate generation
Delegates layer generation to ArchiMateLayerGenerators
"""

from typing import Any, Dict, List

from app.models.application_portfolio import ApplicationComponent


def add_layer_generation_methods(service_class):
    """Add layer generation helper methods to AIImportService."""

    def _build_comprehensive_app_context(self, app: ApplicationComponent, context: str) -> str:
        """Build comprehensive application context for ArchiMate generation."""
        return self.layer_generators.build_comprehensive_app_context(app, context)

    def _generate_motivation_layer(
        self, app: ApplicationComponent, app_context: str
    ) -> List[Dict[str, Any]]:
        """Generate Motivation layer elements."""
        return self.layer_generators.generate_motivation_layer(app, app_context)

    def _generate_strategy_layer(
        self, app: ApplicationComponent, app_context: str, motivation_elements: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate Strategy layer elements."""
        return self.layer_generators.generate_strategy_layer(app, app_context, motivation_elements)

    def _generate_business_layer(
        self, app: ApplicationComponent, app_context: str, strategy_elements: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate Business layer elements."""
        return self.layer_generators.generate_business_layer(app, app_context, strategy_elements)

    def _generate_application_layer(
        self, app: ApplicationComponent, app_context: str, business_elements: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate Application layer elements."""
        return self.layer_generators.generate_application_layer(app, app_context, business_elements)

    def _generate_technology_layer(
        self, app: ApplicationComponent, app_context: str, application_elements: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate Technology layer elements."""
        return self.layer_generators.generate_technology_layer(
            app, app_context, application_elements
        )

    def _generate_physical_layer(
        self, app: ApplicationComponent, app_context: str
    ) -> List[Dict[str, Any]]:
        """Generate Physical layer elements."""
        return self.layer_generators.generate_physical_layer(app, app_context)

    def _generate_implementation_layer(
        self, app: ApplicationComponent, app_context: str
    ) -> List[Dict[str, Any]]:
        """Generate Implementation layer elements."""
        return self.layer_generators.generate_implementation_layer(app, app_context)

    # Add methods to class
    service_class._build_comprehensive_app_context = _build_comprehensive_app_context
    service_class._generate_motivation_layer = _generate_motivation_layer
    service_class._generate_strategy_layer = _generate_strategy_layer
    service_class._generate_business_layer = _generate_business_layer
    service_class._generate_application_layer = _generate_application_layer
    service_class._generate_technology_layer = _generate_technology_layer
    service_class._generate_physical_layer = _generate_physical_layer
    service_class._generate_implementation_layer = _generate_implementation_layer

    return service_class
