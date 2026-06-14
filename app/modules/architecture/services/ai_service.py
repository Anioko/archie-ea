"""
Architecture AI service — imports from inlined canonical sources.

Consolidates AI/LLM, semantic, and intelligence services:
- app.services.ai_architecture_service (AIArchitectureService — 13KB)
- app.services.ai_architecture_analysis_service (AIArchitectureAnalysisService — 29KB)
- app.services.archimate.archimate_llm_service (ArchiMateLLMService — 27KB)
- app.services.archimate.multi_modal_llm_service (MultiModalLLMService — 27KB)
- app.services.archimate.archimate_prompts (ArchiMatePrompts — 71KB)
- app.services.archimate.enhanced_archimate_extractor (EnhancedArchiMateExtractor — 25KB)
- app.services.archimate.entity_resolution_service (EntityResolutionService — 13KB)
- app.services.archimate.semantic_similarity_service (SemanticSimilarityService — 14KB)
- app.services.archimate.confidence_scoring_service (ConfidenceScoringService — 14KB)
- app.services.archimate.feedback_learning_service (FeedbackLearningService — 12KB)
- app.services.archimate.knowledge_graph_service (KnowledgeGraphService — 9KB)
- app.services.archimate.missing_fields_analyzer (MissingFieldsAnalyzer — 12KB)
- app.services.archimate.gemini_file_search_service (GeminiFileSearchService — 12KB)
- app.services.agents.archimate_mapping_agent (ArchiMateMappingAgent — 9KB)
"""

from app.modules.architecture.services.ai_architecture_service import (  # noqa: F401
    CognitiveArchitectureService,
)

from app.modules.architecture.services.ai_architecture_analysis_service import (  # noqa: F401
    AIArchitectureAnalysisService,
)

from app.modules.architecture.services.archimate_llm_service import (  # noqa: F401
    ArchiMateLLMService,
)

from app.modules.architecture.services.multi_modal_llm_service import (  # noqa: F401
    MultiModalLLMService,
)

from app.modules.architecture.services.enhanced_archimate_extractor import (  # noqa: F401
    EnhancedArchiMateExtractor,
)

from app.modules.architecture.services.entity_resolution_service import (  # noqa: F401
    EntityResolutionService,
)

from app.modules.architecture.services.semantic_similarity_service import (  # noqa: F401
    SemanticSimilarityService,
)

from app.modules.architecture.services.confidence_scoring_service import (  # noqa: F401
    ConfidenceScoringService,
)

from app.modules.architecture.services.feedback_learning_service import (  # noqa: F401
    FeedbackLearningService,
)

from app.modules.architecture.services.knowledge_graph_service import (  # noqa: F401
    KnowledgeGraphService,
)

from app.modules.architecture.services.missing_fields_analyzer import (  # noqa: F401
    MissingFieldsAnalyzer,
)

from app.modules.architecture.services.gemini_file_search_service import (  # noqa: F401
    GeminiFileSearchService,
)

try:
    from app.modules.architecture.services.archimate_mapping_agent import (  # noqa: F401
        ArchiMateMappingAgent,
    )
except ImportError:
    ArchiMateMappingAgent = None  # type: ignore[assignment,misc]
