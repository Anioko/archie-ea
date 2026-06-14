"""
DEPRECATED: Import from app.modules.architecture.routes.archimate_crud.routes instead.
-> app.modules.architecture.routes.archimate_crud.routes
Backward-compat re-export. Canonical: app/modules/architecture/routes/archimate_crud/routes.py
"""
# Routes are registered on archimate_crud blueprint via the module copy.
# This file is kept for backward compatibility.
#
# UIQA-004: the shim claimed to be a re-export but exported NOTHING, so every
# legacy `from app.archimate_crud.routes import LAYER_CONFIG/MODEL_REGISTRY`
# (ai-chat document upload, unified chat ArchiMate generation) crashed with
# ImportError — the /ai-chat/upload-document 500. Re-export the canonical names.
from app.modules.architecture.routes.archimate_crud.routes import (  # noqa: F401
    LAYER_CONFIG,
    MODEL_REGISTRY,
)
