import time
import threading
from flask import request

class SecurityMiddleware:
    _rate_limit_store = {}
    _lock = threading.Lock()

    @staticmethod
    def add_security_headers(response):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none';"
        )
        response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @classmethod
    def rate_limit_check(cls, user_id, endpoint, limit=100, window=60):
        now = int(time.time())
        key = f"{user_id}:{endpoint}:{now // window}"
        with cls._lock:
            count, ts = cls._rate_limit_store.get(key, (0, now))
            if now - ts >= window:
                count = 0
                ts = now
            if count >= limit:
                return False
            cls._rate_limit_store[key] = (count + 1, ts)
        return True

    @staticmethod
    def validate_secret_strength(secret):
        if not isinstance(secret, str) or len(secret) < 32:
            return False
        has_upper = any(c.isupper() for c in secret)
        has_lower = any(c.islower() for c in secret)
        has_digit = any(c.isdigit() for c in secret)
        return has_upper and has_lower and has_digit
