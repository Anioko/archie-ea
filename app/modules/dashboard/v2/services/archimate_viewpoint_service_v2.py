"""Dashboard v2 adapter for the ArchiMate viewpoint service's layer-type map."""

import importlib

_archimate_viewpoint_service = importlib.import_module(
    "app.services.archimate_viewpoint_service"
)
LAYER_TYPES = _archimate_viewpoint_service.LAYER_TYPES
LAYER_TYPE_TO_LAYER = _archimate_viewpoint_service.LAYER_TYPE_TO_LAYER

__all__ = ["LAYER_TYPES", "LAYER_TYPE_TO_LAYER"]
