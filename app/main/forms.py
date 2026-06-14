"""Shared WTForms definitions used across the main blueprint.

Currently we primarily need a lightweight base form that provides CSRF
protection for routes that submit via standard HTML forms without any
input fields. Keeping the definition within ``app.main`` avoids circular
imports for other blueprints that only require the CSRF token handling.
"""

from flask_wtf import FlaskForm


class Form(FlaskForm):
    """Minimal form used for CSRF-only submissions."""

    pass
