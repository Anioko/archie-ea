"""
Procurement Module (NS-010, NS-011)

Provides contract management and license tracking for the Procurement persona.
Part of North Star Persona MVP implementation.

ADR Reference: docs/adr/0010-procurement-persona.md
"""

from flask import Blueprint

procurement_bp = Blueprint(
    "procurement",
    __name__,
    url_prefix="/procurement",
    template_folder="templates",
)

from . import routes  # noqa: F401, E402
