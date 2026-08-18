"""Application-wide request throttling (finding F-06).

Before this module the only throttle in the codebase was
``app.services.rate_limiter.rate_limit``, applied by hand to a handful of
authentication routes. Everything else — every read API, every create/update
endpoint — was unbounded, which the QA sweep demonstrated with 40 unthrottled
GETs and 25 unthrottled POSTs. That matters here beyond the usual abuse case:
ARCH-001 records four complete outages under *single-user* load, so an
unthrottled client is also an availability control that does not exist.

Design notes
------------
* Limits are declared **globally** here rather than per route, so a new
  blueprint is covered the moment it is registered. Per-route overrides remain
  available via ``limiter.limit`` / ``limiter.exempt``.
* Storage prefers Redis (``REDISTOGO_URL``) so a counter survives a gunicorn
  worker recycle and is shared across workers — an in-memory counter divided by
  N workers is N times the intended limit. If Redis is absent or unreachable we
  fall back to in-memory and log it, because a dev box without Redis must still
  boot.
* Keys are per authenticated user where possible, per IP otherwise. Keying an
  authenticated app purely on IP would make a single office NAT one bucket.
"""

import logging
import os

logger = logging.getLogger(__name__)

limiter = None

# Endpoints that must never be throttled, with the exact endpoint names this
# app registers (verified against app.url_map, not guessed):
#  - liveness/version probes. A throttled /health reads as an outage to the
#    orchestrator and would make the healthcheck flap — which is the restart
#    loop ARCH-001 is actually about, so throttling it would make the finding
#    worse rather than better.
#  - the CSP violation report sink. Rate-limiting it would silently discard
#    exactly the reports that matter (a real attack generates many).
#  - static assets: one page load pulls dozens, exhausting any sane limit.
_EXEMPT_ENDPOINTS = {
    "static",
    "global_health_check",   # /health
    "health.health",         # /health (blueprint duplicate)
    "healthz",
    "version_endpoint",      # /version
    "csp_report",            # /api/csp-report
}

_DEFAULT_LIMITS = ["1000 per hour", "120 per minute"]
# Writes are the expensive, state-changing half; hold them well below reads.
_WRITE_LIMITS = ["300 per hour", "30 per minute"]

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _write_limits():
    """Per-request extra limits, applied only to state-changing verbs.

    Expressed as a callable in ``default_limits`` rather than by decorating the
    app: Flask-Limiter's ``limit()`` decorator expects a view function, and an
    empty string means "no additional limit for this request".
    """
    from flask import request

    if request.method.upper() not in _WRITE_METHODS:
        return ""
    return "; ".join(_WRITE_LIMITS)


def _storage_uri():
    """Return a Redis URI when one is reachable, else in-memory.

    Reachability is probed here rather than left to first use: Flask-Limiter
    raises on a dead backend at request time, which would turn a missing Redis
    into a 500 on every route instead of a degraded limiter.
    """
    url = (
        os.environ.get("RATELIMIT_STORAGE_URI")
        or os.environ.get("REDISTOGO_URL")
        or os.environ.get("REDIS_URL")
        or ""
    ).strip()
    if not url:
        logger.info("Rate limiting: no Redis configured — using in-memory storage")
        return "memory://"
    try:
        import redis

        redis.from_url(url, socket_connect_timeout=2).ping()
        return url
    except Exception as exc:  # pragma: no cover - depends on deployment
        logger.warning(
            "Rate limiting: Redis at %s unreachable (%s) — falling back to "
            "in-memory storage. Limits will be per-worker until Redis returns.",
            url.split("@")[-1],
            exc,
        )
        return "memory://"


def _identity():
    """Per-user key when authenticated, per-IP otherwise."""
    try:
        from flask_login import current_user

        if current_user and current_user.is_authenticated:
            return f"user:{current_user.get_id()}"
    except Exception as exc:
        logger.debug("rate-limit identity: current_user unavailable: %s", exc)
    from flask_limiter.util import get_remote_address

    return f"ip:{get_remote_address()}"


def init_rate_limiting(app):
    """Install Flask-Limiter with global default limits.

    Never fatal: a limiter that fails to install must degrade to "no throttle",
    not to "no application".
    """
    global limiter
    try:
        from flask_limiter import Limiter
    except ImportError:  # pragma: no cover - dependency is pinned
        app.logger.warning(
            "Rate limiting disabled: flask_limiter is not installed"
        )
        return None

    # Flask-Limiter's own RATELIMIT_ENABLED is a *wiring* switch, not a runtime
    # one: init_app returns early when it is false, so the before_request hook
    # is never registered and the limiter can never be turned back on. Keep it
    # true and gate at request time on the app's own RATE_LIMITING_ENABLED flag
    # (already honoured by app/services/rate_limiter.py) so the switch is real.
    app.config["RATELIMIT_ENABLED"] = True
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)  # emits Retry-After
    # Off by default under TESTING: the whole suite shares one session-scoped
    # app and one loopback address, so a live limiter would 429 unrelated tests.
    enabled = app.config.setdefault(
        "RATE_LIMITING_ENABLED", not app.config.get("TESTING", False)
    )

    try:
        limiter = Limiter(
            key_func=_identity,
            app=app,
            # Writes carry their own, tighter bucket on top of the default.
            default_limits=[*_DEFAULT_LIMITS, _write_limits],
            storage_uri=_storage_uri(),
            strategy="fixed-window",
            enabled=True,
            headers_enabled=True,
        )
    except Exception as exc:
        app.logger.warning("Rate limiting install failed (non-fatal): %s", exc)
        return None

    @limiter.request_filter
    def _exempt():
        from flask import current_app, request

        if not current_app.config.get("RATE_LIMITING_ENABLED", True):
            return True
        endpoint = request.endpoint or ""
        return endpoint in _EXEMPT_ENDPOINTS or (request.path or "").startswith(
            "/static/"
        )

    @app.errorhandler(429)
    def _too_many_requests(err):
        from flask import jsonify, render_template, request

        retry_after = getattr(err, "retry_after", None) or getattr(
            getattr(err, "response", None), "headers", {}
        ).get("Retry-After")
        wants_json = (
            "/api/" in request.path
            or request.content_type == "application/json"
            or request.accept_mimetypes.best == "application/json"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )
        if wants_json:
            resp = jsonify(
                {
                    "success": False,
                    "error": "Rate limit exceeded. Slow down and retry shortly.",
                }
            )
        else:
            try:
                resp = app.make_response(
                    render_template("errors/429.html", retry_after=retry_after)
                )
            except Exception:
                resp = app.make_response(
                    "Rate limit exceeded. Please retry shortly."
                )
        resp.status_code = 429
        if retry_after:
            resp.headers["Retry-After"] = str(retry_after)
        return resp

    app.logger.info(
        "Rate limiting enabled=%s defaults=%s writes=%s",
        enabled,
        _DEFAULT_LIMITS,
        _WRITE_LIMITS,
    )
    return limiter
