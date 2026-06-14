"""
My Applications Module (NS-012, NS-013)

Provides application portfolio view filtered by ownership for the Application Manager persona.
Part of North Star Persona MVP implementation.

ADR Reference: docs/adr/0011-application-manager-persona.md
"""

from flask import Blueprint

my_applications_bp = Blueprint(
    "my_applications",
    __name__,
    url_prefix="/my-applications",
    template_folder="templates",
)

from . import routes  # noqa: F401, E402
