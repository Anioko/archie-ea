"""
Application core service — imports from inlined canonical sources.

Consolidates:
- application_factory (ApplicationFactory)
- application_similarity_service (ApplicationSimilarityService)
- application_consolidation_service (ApplicationConsolidationService)
- application_merging_service (ApplicationMergeService)
- abacus_application_importer (AbacusApplicationImporter)
"""

from app.modules.applications.services.application_factory import (  # noqa: F401
    ApplicationFactory,
    create_vendor_deployment,
)

from app.modules.applications.services.application_similarity_service import (  # noqa: F401
    ApplicationSimilarityService,
)

from app.modules.applications.services.application_consolidation_service import (  # noqa: F401
    ApplicationConsolidationService,
)

from app.modules.applications.services.application_merging_service import (  # noqa: F401
    ApplicationMatchingService,
    ApplicationMergeService,
    MergeCandidate,
    MergeConfig,
)

from app.modules.applications.services.abacus_application_importer import (  # noqa: F401
    AbacusApplicationImporter,
    AbacusApplicationUpsertHandler,
    AbacusComponentTransformer,
)
