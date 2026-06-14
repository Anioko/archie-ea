import traceback

from flask import current_app, jsonify, render_template, request

from app.main.views import main
from app.services.rate_limiter import RateLimitExceeded


def _log_exception(e):
    try:
        tb = traceback.format_exc()
        with open("error_debug.log", "a", encoding="utf-8") as fh:
            fh.write("\n-----\n")
            fh.write(tb)
            fh.write("\n-----\n")
    except Exception:
        # Best effort only; avoid raising further exceptions
        current_app.logger.exception("Failed to write to error_debug.log")


@main.app_errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(e):
    """Global handler for rate limit exceeded errors (import-fix-rate-limiting)."""
    current_app.logger.warning(
        f"Rate limit exceeded: {e.limit}/{e.window} - "
        f"IP: {request.remote_addr}, Path: {request.path}"
    )
    # Return JSON for API/AJAX requests, otherwise a simple text response
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        response = jsonify(
            {
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Limit: {e.limit} per {e.window}.",
                "limit": e.limit,
                "window": e.window,
                "retry_after": e.retry_after,
            }
        )
        response.status_code = 429
        if e.retry_after:
            response.headers["Retry-After"] = str(e.retry_after)
        return response
    else:
        # For non-API requests (form submissions, page loads), return a 429 page
        response = jsonify(
            {
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Please wait and try again. Limit: {e.limit} per {e.window}.",
                "retry_after": e.retry_after,
            }
        )
        response.status_code = 429
        if e.retry_after:
            response.headers["Retry-After"] = str(e.retry_after)
        return response


@main.app_errorhandler(403)
def forbidden(e):
    try:
        return render_template("errors/403.html"), 403
    except Exception:
        _log_exception(e)
        return ("Forbidden", 403)


@main.app_errorhandler(404)
def page_not_found(e):
    try:
        return render_template("errors/404.html"), 404
    except Exception:
        _log_exception(e)
        return ("Page Not Found", 404)


@main.app_errorhandler(500)
def internal_server_error(e):
    try:
        return render_template("errors/500.html"), 500
    except Exception:
        _log_exception(e)
        return ("Internal Server Error", 500)
