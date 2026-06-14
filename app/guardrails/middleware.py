"""
Guardrail Enforcement Middleware.

Real-time monitoring of requests for guardrail violations.
"""
import logging
import re
import time
from functools import wraps

from flask import request

logger = logging.getLogger(__name__)


class GuardrailMiddleware:
    """Simple passthrough middleware that monitors requests without modifying responses."""

    def __init__(self, wsgi_app, flask_app=None):
        self.wsgi_app = wsgi_app
        self.flask_app = flask_app
        self.violations = []
        self.request_patterns = {}

    def __call__(self, environ, start_response):
        # Simple passthrough - don't wrap start_response to avoid "Headers already set" issues
        return self.wsgi_app(environ, start_response)

    def log_violation(self, violation_type, details):
        """Log guardrail violations"""
        violation = {
            "timestamp": time.time(),
            "type": violation_type,
            "details": details,
            "url": self.current_environ.get("PATH_INFO", "N/A") if self.current_environ else "N/A",
            "method": self.current_environ.get("REQUEST_METHOD", "N/A")
            if self.current_environ
            else "N/A",
        }

        self.violations.append(violation)

        # Keep only last 100 violations
        if len(self.violations) > 100:
            self.violations = self.violations[-100:]

        # Log violation
        logger.warning(f"[GUARDRAIL VIOLATION] {violation_type} - {details}")


def guardrail_monitor(view_func):
    """Decorator to monitor specific views for guardrail violations"""

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        # Pre-request checks
        if hasattr(request, "view_args"):
            view_signature = f"{request.endpoint}:{hash(str(request.view_args))}"

            # Check for pattern fragmentation
            if detect_pattern_fragmentation(request):
                logger.warning(f"[PATTERN_FRAGMENTATION] detected in {request.endpoint}")

        # Execute view
        result = view_func(*args, **kwargs)

        # Post-request checks
        if hasattr(result, "status_code") and result.status_code >= 400:
            logger.warning(f"[RESPONSE_ERROR] {request.endpoint} returned {result.status_code}")

        return result

    return wrapped_view


def detect_pattern_fragmentation(request):
    """Detect if request shows pattern fragmentation"""
    # Check for inconsistent parameter patterns
    if hasattr(request, "args") and request.args:
        # Look for inconsistent naming patterns
        args_keys = list(request.args.keys())

        # Check for mixed naming conventions
        has_snake_case = any("_" in key for key in args_keys)
        has_camel_case = any(re.search("[a-z][A-Z]", key) for key in args_keys)

        if has_snake_case and has_camel_case:
            return True

    return False


class RealTimeMonitor:
    """Real-time monitoring of guardrail compliance"""

    def __init__(self, app=None):
        self.app = app
        self.metrics = {
            "requests_total": 0,
            "violations_total": 0,
            "fragmentation_detected": 0,
            "api_inconsistencies": 0,
        }

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize monitoring with Flask app"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)

        # Register CLI commands
        @app.cli.command()
        def guardrail_stats():
            """Show guardrail violation statistics"""
            print("[Guardrail Statistics]")
            for metric, value in self.metrics.items():
                print(f"  {metric}: {value}")

    def before_request(self):
        """Monitor incoming requests"""
        self.metrics["requests_total"] += 1

        # Check request for violations
        if self.check_request_violations():
            self.metrics["violations_total"] += 1

    def after_request(self, response):
        """Monitor outgoing responses"""
        # Check response for violations
        if response.status_code >= 400:
            self.metrics["violations_total"] += 1

        return response

    def check_request_violations(self):
        """Check if request violates guardrails"""
        violations = []

        # Check for inconsistent API patterns
        if request.path.startswith("/api/"):
            if self.check_api_inconsistency():
                violations.append("API_INCONSISTENCY")
                self.metrics["api_inconsistencies"] += 1

        # Check for UI fragmentation indicators
        if request.path.startswith("/"):
            if self.check_ui_fragmentation_indicators():
                violations.append("UI_FRAGMENTATION")
                self.metrics["fragmentation_detected"] += 1

        return len(violations) > 0

    def check_api_inconsistency(self):
        """Check for API inconsistencies"""
        # Look for inconsistent parameter naming
        if request.args:
            param_names = list(request.args.keys())

            # Check for mixed conventions
            snake_case_params = [p for p in param_names if "_" in p]
            camel_case_params = [p for p in param_names if re.search("[a-z][A-Z]", p)]

            if snake_case_params and camel_case_params:
                return True

        return False

    def check_ui_fragmentation_indicators(self):
        """Check for indicators of UI fragmentation"""
        # Check for inconsistent query parameters
        if request.args:
            # Look for parameters that suggest different UI patterns
            fragment_indicators = ["view_type", "display_mode", "layout", "format"]

            found_indicators = [p for p in fragment_indicators if p in request.args]
            if len(found_indicators) > 1:
                return True

        return False


# Flask extension pattern
class GuardrailEnforcement:
    """Flask extension for guardrail enforcement"""

    def __init__(self, app=None):
        self.monitor = None
        self.middleware = None

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize guardrail enforcement"""
        self.monitor = RealTimeMonitor(app)
        self.middleware = GuardrailMiddleware(app.wsgi_app, app)

        # Wrap the app with middleware
        app.wsgi_app = self.middleware

        # Store extension on app
        app.guardrail_enforcement = self

        # Add configuration
        app.config.setdefault(
            "GUARDRAIL_ENFORCEMENT",
            {"enabled": True, "block_on_violation": False, "log_violations": True},
        )
