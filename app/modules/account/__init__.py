"""
Account module - User authentication, registration, and account management.

Migrated from:
- app/account/views.py (14 routes + 1 before_app_request hook)
- app/account/forms.py (7 WTForms classes)

URL prefix preserved: /account

Endpoints:
- /account/login
- /account/register
- /account/logout
- /account/manage
- /account/manage/info
- /account/manage/change-password
- /account/manage/change-email
- /account/manage/change-email/<token>
- /account/reset-password
- /account/reset-password/<token>
- /account/confirm-account
- /account/confirm-account/<token>
- /account/join-from-invite/<user_id>/<token>
- /account/unconfirmed
"""
from flask import Flask


def register(app: Flask) -> None:
    """Register the account module with the Flask app.

    Args:
        app: Flask application instance.
    """
    from .routes.account_routes import account_bp

    app.register_blueprint(account_bp, url_prefix="/account")

    app.logger.info("[MODULE] account registered (auth + management)")
