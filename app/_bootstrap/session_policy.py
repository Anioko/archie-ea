"""Server-authoritative session idle timeout (finding F-07).

The platform had exactly one session control: ``PERMANENT_SESSION_LIFETIME``
of 8 hours (config.py), an *absolute* cap. There was no idle timeout, and the
only thing resembling one — ``static/js/core/06-session-timeout.js`` — is a
client-side timer that starts at page load, never resets on activity and polls
``/health`` (a liveness endpoint that says nothing about the session). Anything
that does not execute page JavaScript, which is every direct API call, was
unaffected by it entirely.

This module adds the missing half: a ``before_request`` check that compares a
last-activity timestamp *stored in the signed session cookie* against now, and
tears the session down when the gap exceeds the configured idle window. It is
authoritative because the client cannot move the timestamp forward without
making a request, and cannot forge it without the secret key.

The absolute cap is deliberately left alone and remains separate:
``PERMANENT_SESSION_LIFETIME`` bounds how long a session may live at all, this
bounds how long it may sit unused. Both apply.

Configuration
-------------
``SESSION_IDLE_TIMEOUT`` — ``timedelta`` or seconds. Defaults to 30 minutes,
the enterprise-typical value the finding asks for. Set to 0 to disable.
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

#: Session key holding the epoch seconds of the last request this session made.
LAST_ACTIVITY_KEY = "_last_activity_at"

_DEFAULT_IDLE = timedelta(minutes=30)

#: Requests that must NOT count as activity. A background /health poll from an
#: abandoned tab would otherwise refresh the stamp forever - which is exactly
#: the defect the old client-side "extend" button had, since it pinged /health.
_EXEMPT_ENDPOINTS = {
    "static",
    "global_health_check",   # /health
    "health.health",         # /health (blueprint duplicate)
    "healthz",
    "version_endpoint",      # /version
    "csp_report",            # /api/csp-report
}


def _idle_seconds(app):
    raw = app.config.get("SESSION_IDLE_TIMEOUT", _DEFAULT_IDLE)
    if isinstance(raw, timedelta):
        return int(raw.total_seconds())
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(_DEFAULT_IDLE.total_seconds())


def _now():
    return int(datetime.now(timezone.utc).timestamp())


def init_session_policy(app):
    """Install the idle-timeout ``before_request`` hook."""

    idle_seconds = _idle_seconds(app)
    app.config["SESSION_IDLE_TIMEOUT_SECONDS"] = idle_seconds

    # Exposed to templates so the courtesy client-side warning uses the same
    # number as the server rather than its own hard-coded 8 hours.
    @app.context_processor
    def _inject_idle_timeout():
        return {"session_idle_timeout_seconds": idle_seconds}

    if idle_seconds <= 0:
        app.logger.info("Session idle timeout disabled (SESSION_IDLE_TIMEOUT=0)")
        return

    @app.before_request
    def _enforce_idle_timeout():
        from flask import jsonify, redirect, request, session, url_for
        from flask_login import current_user, logout_user

        # Static assets and the liveness probe must not keep a session alive:
        # a background /health poll from an abandoned tab would otherwise
        # refresh the timestamp forever, which is exactly the defect the
        # existing client-side "extend" button has.
        # Endpoint names verified against app.url_map, not guessed: /health is
        # registered twice (an inline route and a blueprint), and /version is a
        # build probe. Guessing "health" would have silently exempted nothing.
        endpoint = request.endpoint or ""
        if endpoint in _EXEMPT_ENDPOINTS or request.path.startswith("/static/"):
            return None

        try:
            authenticated = bool(current_user and current_user.is_authenticated)
        except Exception as exc:
            logger.debug("idle timeout: current_user unavailable: %s", exc)
            return None

        if not authenticated:
            return None

        now = _now()
        last = session.get(LAST_ACTIVITY_KEY)

        if isinstance(last, int) and now - last > idle_seconds:
            user_label = getattr(current_user, "email", None) or current_user.get_id()
            logout_user()
            session.clear()
            logger.info(
                "Session idle timeout: signed out %s after %ss idle (limit %ss)",
                user_label,
                now - last,
                idle_seconds,
            )
            wants_json = (
                "/api/" in request.path
                or "/ai-chat/" in request.path
                or request.content_type == "application/json"
                or request.accept_mimetypes.best == "application/json"
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            )
            if wants_json:
                resp = jsonify(
                    {
                        "success": False,
                        "error": "Session expired due to inactivity. Please log in again.",
                        "code": "session_idle_timeout",
                    }
                )
                resp.status_code = 401
                return resp
            try:
                login_url = url_for("account.login", timeout="idle")
            except Exception:
                login_url = "/account/login?timeout=idle"
            return redirect(login_url)

        # Genuine activity — advance the stamp. ``session.permanent`` is set at
        # login; writing here also refreshes the absolute-lifetime cookie,
        # which is the pre-existing SESSION_REFRESH_EACH_REQUEST behaviour.
        session[LAST_ACTIVITY_KEY] = now
        return None

    app.logger.info("Session idle timeout enabled: %ss", idle_seconds)
