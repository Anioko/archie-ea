"""
Application mapping service — imports from inlined canonical sources.

Consolidates:
- application_mapping_orchestrator (ApplicationMappingOrchestrator)
- application_architecture_mapper (ApplicationArchitectureMapperService)
- application_to_uml_adapter (ApplicationToUMLAdapter)
"""

from app.modules.applications.services.application_mapping_orchestrator import (  # noqa: F401
    ApplicationMappingOrchestrator,
    MappingOptions,
    MappingResult,
    get_application_mapping_orchestrator,
)

from app.modules.applications.services.application_architecture_mapper import (  # noqa: F401
    ApplicationArchitectureMapperService,
)

# UML adapter — has broken import (TechnologyProduct model), lazy-load
try:
    from app.modules.applications.services.application_to_uml_adapter import (  # noqa: F401
        ApplicationToUMLAdapter,
        BulkCodeGenerationContext,
    )
except ImportError:
    ApplicationToUMLAdapter = None  # type: ignore[assignment,misc]
    BulkCodeGenerationContext = None  # type: ignore[assignment,misc]
