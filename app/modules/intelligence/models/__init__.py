"""T-003/T-005: models for the Four Intelligences derived-fact store.

Deliberately no eager imports here (matching this module's original empty
``__all__``): both model modules are imported lazily, from inside
``app/models/__init__.py``'s ``register_models()``-equivalent function body,
to avoid import-order/circularity hazards at module-import time -- the same
convention every other model registration in that file follows.
"""

from __future__ import annotations

__all__: list[str] = []
