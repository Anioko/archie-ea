"""
MIGRATION: Copied from app/archimate_crud/__init__.py
Architecture CRUD Dashboard
Unified interface for managing Motivation, Strategy, and Business layer elements
"""

from flask import Blueprint

archimate_crud = Blueprint("archimate_crud", __name__, url_prefix="/architecture")

from . import routes
