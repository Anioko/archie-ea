"""Service helpers for the Business Model Canvas module.

Kept deliberately thin — the model already carries most of the logic
(get_block/set_block/to_dict). This module exists for the small pieces of
business logic that don't belong on the ORM model itself.
"""

from app import db
from app.models.business_model import (
    CANVAS_BLOCKS,
    OPERATING_MODEL_TYPES,
    BusinessModelCanvas,
)


def list_canvases():
    """Return all canvases for the current tenant, most recently updated first."""
    return (
        BusinessModelCanvas.query.order_by(BusinessModelCanvas.updated_at.desc())
        .all()
    )


def get_canvas_or_none(canvas_id):
    return BusinessModelCanvas.query.get(canvas_id)


def create_canvas(name, description=None, operating_model_type=None):
    if operating_model_type and operating_model_type not in OPERATING_MODEL_TYPES:
        raise ValueError(f"Invalid operating_model_type: {operating_model_type}")
    canvas = BusinessModelCanvas(
        name=name or "Untitled Canvas",
        description=description,
        operating_model_type=operating_model_type,
    )
    db.session.add(canvas)
    db.session.commit()
    return canvas


def update_canvas_meta(canvas, name=None, description=None, operating_model_type=None):
    if name is not None:
        canvas.name = name
    if description is not None:
        canvas.description = description
    if operating_model_type is not None:
        if operating_model_type and operating_model_type not in OPERATING_MODEL_TYPES:
            raise ValueError(f"Invalid operating_model_type: {operating_model_type}")
        canvas.operating_model_type = operating_model_type or None
    db.session.commit()
    return canvas


def save_block(canvas, block_key, content):
    if block_key not in CANVAS_BLOCKS:
        raise ValueError(f"Unknown canvas block: {block_key}")
    canvas.set_block(block_key, content)
    db.session.commit()
    return canvas


def delete_canvas(canvas):
    db.session.delete(canvas)
    db.session.commit()
