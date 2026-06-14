"""SEC-002: Simple in-memory rate limiter for composer endpoints."""
import time
from collections import defaultdict
from functools import wraps
from flask import jsonify, request
from flask_login import current_user

_WINDOW = 60  # seconds
_MAX_REQUESTS = 10  # per window

_counters: dict = defaultdict(list)


def composer_rate_limit(f):
    """Decorator: allow at most 10 requests per minute per user/IP."""
    @wraps(f)
    def decorated(*args, **kwargs):
        now = time.time()
        key = str(getattr(current_user, 'id', None) or request.remote_addr or 'anon')
        # Clean old timestamps
        _counters[key] = [t for t in _counters[key] if now - t < _WINDOW]
        if len(_counters[key]) >= _MAX_REQUESTS:
            return jsonify({"error": "Rate limit exceeded. Try again later.", "retry_after": _WINDOW}), 429
        _counters[key].append(now)
        return f(*args, **kwargs)
    return decorated
