"""Business information model module (BIZBOK information map).

Self-contained module in the ``app/modules/`` layout: ``routes/``, ``services/``
and a ``register(app)`` entrypoint, following ``app/modules/capabilities/``.
"""

import logging

from flask import Flask

logger = logging.getLogger(__name__)


def register(app: Flask) -> None:
    """Register the information-model blueprint."""
    from .routes.information_model_routes import information_model

    if information_model.name in app.blueprints:
        return

    app.register_blueprint(information_model)
    app.logger.info(
        "[BLUEPRINT] Information Model registered at /information-model"
    )
