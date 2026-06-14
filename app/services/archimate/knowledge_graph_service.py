"""
DEPRECATED: Import from app.modules.architecture.services instead.
-> app.modules.architecture.services.knowledge_graph_service
Backward-compat re-export. Canonical: app/modules/architecture/services/knowledge_graph_service.py
"""
from app.modules.architecture.services.knowledge_graph_service import (  # noqa: F401
    KnowledgeGraphService,
)

# Note: KGNode, KGEdge, KGPath, KGQuery classes don't exist in source
# If needed, they should be defined in the source module first
