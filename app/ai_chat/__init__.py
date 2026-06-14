from .routes import ai_chat

try:
    from .entity_matching_routes import entity_matching_bp
except ImportError:
    # Create a dummy blueprint if entity_matching_routes doesn't exist
    from flask import Blueprint

    entity_matching_bp = Blueprint("entity_matching", __name__)

try:
    from .business_output_routes import business_output_bp
except ImportError:
    from flask import Blueprint

    business_output_bp = Blueprint("business_output", __name__)

try:
    from .data_interaction_routes import data_interaction_bp
except ImportError:
    from flask import Blueprint

    data_interaction_bp = Blueprint("data_interaction", __name__)
