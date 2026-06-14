"""
ArchiMate core service — imports from inlined canonical sources.

Consolidates core ArchiMate services:
- app.services.archimate.archimate_service (ArchiMateService — 12KB)
- app.services.archimate.archimate_template_service (ArchiMateTemplateService — 30KB)
- app.services.archimate.archimate_validator (ArchiMateValidator — 36KB)
- app.services.archimate.archimate_validation_engine (ArchiMateValidationEngine — 35KB)
- app.services.archimate.archimate_rules_engine (ArchiMateRulesEngine — 23KB)
- app.services.archimate.archimate_metrics_service (ArchiMateMetricsService — 22KB)
- app.services.archimate.element_type_normalizer (ElementTypeNormalizer — 10KB)
- app.services.archimate.archimate_xml_export_service (ArchiMateXmlExportService — 6KB)
- app.services.unified_archimate_services (UnifiedArchiMateServices — 105KB)
- app.services.comprehensive_archimate_service (ComprehensiveArchiMateService — 36KB)
- app.services.archimate_validation_service (18KB)
- app.services.archimate_metamodel_validator (15KB)
- app.services.archimate_element_cloner (9KB)
"""

from app.modules.architecture.services.archimate_core_service import (  # noqa: F401
    ArchiMateService,
)

from app.modules.architecture.services.archimate_template_service import (  # noqa: F401
    ArchiMateTemplateService,
)

from app.modules.architecture.services.archimate_validator import (  # noqa: F401
    ArchiMateValidator,
)

from app.modules.architecture.services.archimate_validation_engine import (  # noqa: F401
    ArchiMateValidationEngine,
)

from app.modules.architecture.services.archimate_rules_engine import (  # noqa: F401
    ArchiMateRulesEngine,
)

from app.modules.architecture.services.archimate_metrics_service import (  # noqa: F401
    ArchiMateMetricsService,
)

from app.modules.architecture.services.element_type_normalizer import (  # noqa: F401
    ElementTypeNormalizer,
)

from app.modules.architecture.services.archimate_xml_export_service import (  # noqa: F401
    ArchiMateXMLExportService,
)

from app.modules.architecture.services.unified_archimate_services import (  # noqa: F401
    UnifiedArchiMateServices,
)

from app.modules.architecture.services.comprehensive_archimate_service import (  # noqa: F401
    ComprehensiveArchiMateService,
)

try:
    from app.modules.architecture.services.archimate_validation_service import (  # noqa: F401
        ArchiMateValidationService,
    )
except (ImportError, AttributeError):
    ArchiMateValidationService = None  # type: ignore[assignment,misc]

from app.modules.architecture.services.archimate_metamodel_validator import (  # noqa: F401
    ArchiMateMetamodelValidator,
)

from app.modules.architecture.services.archimate_element_cloner import (  # noqa: F401
    ArchiMateElementCloner,
)
