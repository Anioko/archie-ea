"""Legacy compatibility module exposing `Application`.

Provides a small wrapper so `from app.models.application import Application`
continues to work by referencing the canonical `ApplicationComponent` model.
"""
from .application_portfolio import ApplicationComponent

# Backwards-compatible name expected by older modules/tests
Application = ApplicationComponent

__all__ = ["Application", "ApplicationComponent"]
