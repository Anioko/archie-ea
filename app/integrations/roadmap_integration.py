"""
Roadmap System Integration
Integrate the roadmap API blueprint with the main application
"""

# Add this to app/__init__.py or app/api/__init__.py
from app.api.roadmap_api import roadmap_bp


def register_roadmap_blueprints(app):
    """Register all roadmap-related blueprints"""
    app.register_blueprint(roadmap_bp)
    return app
