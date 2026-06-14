"""
Extensions module for Flask application.

All Flask extension instances are defined here so that they can be imported
by any module without circular imports. The ``init_app`` calls happen inside
``create_app()`` in ``app/__init__.py``.

Usage::

    from app.extensions import db, csrf, mail, login_manager, compress
"""

from flask_compress import Compress
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

# --- Core extensions (always available) ---

db = SQLAlchemy()
csrf = CSRFProtect()
mail = Mail()
compress = Compress()

login_manager = LoginManager()
login_manager.session_protection = "basic"
login_manager.login_view = "account.login"

# --- Optional extensions (imported at init_app time) ---
# Flask-Migrate, Flask-RQ, Flasgger are initialised conditionally inside
# create_app() because they may not be installed.
