"""
Compatibility wrappers for the account module (legacy -> v2).

Feature-flag gating: USE_ACCOUNT_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.mapping_registry import register_routes
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("account")


class AccountCompatStats(CompatStats):
    """Thread-safe hit counter for legacy account endpoints."""
    pass


LEGACY_ROUTE_MAP = {
    "account.login":                {"url": "/account/login",                          "v2": "account.login",                "method": "GET,POST"},
    "account.register":             {"url": "/account/register",                       "v2": "account.register",             "method": "GET,POST"},
    "account.logout":               {"url": "/account/logout",                         "v2": "account.logout",               "method": "GET"},
    "account.manage":               {"url": "/account/manage",                         "v2": "account.manage",               "method": "GET,POST"},
    "account.reset_password_request": {"url": "/account/reset-password",               "v2": "account.reset_password_request", "method": "GET,POST"},
    "account.reset_password":       {"url": "/account/reset-password/<token>",         "v2": "account.reset_password",       "method": "GET,POST"},
    "account.change_password":      {"url": "/account/manage/change-password",         "v2": "account.change_password",      "method": "GET,POST"},
    "account.change_email_request": {"url": "/account/manage/change-email",            "v2": "account.change_email_request", "method": "GET,POST"},
    "account.change_email":         {"url": "/account/manage/change-email/<token>",    "v2": "account.change_email",         "method": "GET,POST"},
    "account.confirm_request":      {"url": "/account/confirm-account",                "v2": "account.confirm_request",      "method": "GET"},
    "account.confirm":              {"url": "/account/confirm-account/<token>",         "v2": "account.confirm",              "method": "GET"},
    "account.join_from_invite":     {"url": "/account/join-from-invite/<user_id>/<token>", "v2": "account.join_from_invite", "method": "GET,POST"},
    "account.unconfirmed":          {"url": "/account/unconfirmed",                    "v2": "account.unconfirmed",          "method": "GET"},
}

register_routes("account", LEGACY_ROUTE_MAP)

wrap_legacy_account_bp = make_legacy_wrapper(_config, AccountCompatStats)
