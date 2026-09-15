"""Routes package for the Interface Register module. Exposes interface_register_bp."""

from .register_routes import interface_register_bp
from . import comparison_routes  # noqa: F401 - registers /comparison routes on interface_register_bp

__all__ = ["interface_register_bp"]
