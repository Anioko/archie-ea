"""
Account v2 — Full guardrail-enabled module using new architecture.

Strangler Fig migration from app/modules/account/ (v1).
Uses:
- app.core.decorators (guarded_route, timed_route)
- app.core.api (api_success, api_error)
- app.core.compat (mark_blueprint_guardrailed)
- app.core.validation (schemas)

Feature flag: USE_ACCOUNT_GUARDRAILS
Fallback: v1 routes (unchanged)

Rollback: Set USE_ACCOUNT_GUARDRAILS=false → v1 routes take over instantly.

Endpoints preserved (all under /account prefix):
- /login, /register, /logout
- /manage, /manage/info, /manage/change-password, /manage/change-email, /manage/change-email/<token>
- /reset-password, /reset-password/<token>
- /confirm-account, /confirm-account/<token>
- /join-from-invite/<user_id>/<token>
- /unconfirmed
"""

from flask import Flask


def register(app: Flask) -> None:
    """Register the account v2 module."""
    from .routes import account_bp_v2

    app.register_blueprint(account_bp_v2, url_prefix="/account")

    app.logger.info("[MODULE-V2] account v2 registered (guardrail-enabled)")
