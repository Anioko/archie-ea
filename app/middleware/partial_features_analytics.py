"""
Usage analytics middleware — page views on module-directory endpoints.

Writes one `usage_analytics` row per request whose endpoint is one this app's
module directory knows about (app/modules/modules_directory/routes.py), keyed
by the endpoint name. No personal data is stored: `UsageAnalytics.track_event`
is called without a `request` argument here, so `user_agent`, `ip_address` and
`referrer` stay `None` on every event this middleware writes. A signed-in user
who has turned analytics off for themselves (Settings > Enable Analytics) is
not tracked.

`ENABLE_USAGE_ANALYTICS` is owned by config.py; this module only reads it.
"""
import time
import uuid
from flask import current_app, g, request, session
from flask_login import current_user

from app.models.usage_analytics import UsageAnalytics


class PartialFeaturesAnalytics:
    """Writes one page-view event per module-directory endpoint request."""

    def __init__(self, app=None):
        self.app = app
        self._directory_endpoints = frozenset()
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Register the before/after/teardown hooks with the Flask app, and
        build the endpoint set once, here, rather than on every request."""
        self._directory_endpoints = self._compute_directory_endpoints()
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_request(self._teardown_request)

    def _compute_directory_endpoints(self):
        """The set of endpoint names this middleware writes an event for:
        every module-directory link, plus the aliases the directory
        deliberately hides (`_NOT_RENDERED`) — a folded or not-rendered
        surface is still reachable by a direct request, and its count still
        matters for a retirement decision. Imported from the directory
        module, not copied, so it stays the one place this set is
        maintained. Built once, at install time: the directory's contents
        are fixed Python module state (SIDEBAR_ZONES / _MORE_TOOLS), not
        something that changes between requests within one running process."""
        from app.modules.modules_directory.routes import (
            _NOT_RENDERED,
            all_module_links,
        )

        endpoints = {link["endpoint"] for link in all_module_links()}
        endpoints.update(_NOT_RENDERED.keys())
        return frozenset(endpoints)

    def _opted_out(self):
        """True when the signed-in user has turned analytics off for
        themselves. Anonymous requests are never opted out — there is no
        per-user preference to read for them."""
        if not current_user.is_authenticated:
            return False
        return bool(current_user.get_notification_preference("analytics_opt_out"))

    def _before_request(self):
        """Record a page-view event for a request to a directory endpoint."""
        if not current_app.config.get('ENABLE_USAGE_ANALYTICS', False):
            return

        # Skip static files — no analytics needed
        if request.path.startswith("/static/") or request.path == "/favicon.ico":
            return

        # Generate or get session ID
        if 'analytics_session_id' not in session:
            session['analytics_session_id'] = str(uuid.uuid4())

        g.analytics_session_id = session.get('analytics_session_id')
        # request.environ has no 'REQUEST_TIME' key (that is not a WSGI
        # standard key Flask/Werkzeug populate); reading it always returned
        # the 0 default, so the "elapsed" time below was actually
        # time.time() - 0, i.e. the epoch time in milliseconds, not a
        # duration. time.time() captured here is a real start time.
        g.analytics_start_time = time.time()
        g.analytics_feature_name = (
            request.endpoint if request.endpoint in self._directory_endpoints else None
        )
        g.analytics_user_id = current_user.id if current_user.is_authenticated else None

        if not g.analytics_feature_name or self._opted_out():
            return

        # No `request=` argument — the event carries only the endpoint name,
        # the route path, and the session/user ids above.
        UsageAnalytics.track_event(
            event_type='page_view',
            feature_name=g.analytics_feature_name,
            route_path=request.path,
            user_id=g.analytics_user_id,
            session_id=g.analytics_session_id,
        )

    def _after_request(self, response):
        """Track successful write interactions on a directory endpoint."""
        if not current_app.config.get('ENABLE_USAGE_ANALYTICS', False):
            return response

        if (g.get('analytics_feature_name') and
            not self._opted_out() and
            request.method in ['POST', 'PUT', 'PATCH', 'DELETE'] and
            response.status_code < 400):

            UsageAnalytics.track_event(
                event_type='feature_interaction',
                feature_name=g.analytics_feature_name,
                route_path=request.path,
                user_id=g.analytics_user_id,
                session_id=g.analytics_session_id,
                event_metadata={
                    'method': request.method,
                    'status_code': response.status_code,
                    'response_time_ms': self._calculate_response_time()
                },
            )

        return response

    def _teardown_request(self, exception):
        """Track an unhandled error on a directory endpoint."""
        if not current_app.config.get('ENABLE_USAGE_ANALYTICS', False):
            return

        if exception and g.get('analytics_feature_name') and not self._opted_out():
            UsageAnalytics.track_event(
                event_type='error_occurred',
                feature_name=g.analytics_feature_name,
                route_path=request.path,
                user_id=g.analytics_user_id,
                session_id=g.analytics_session_id,
                event_metadata={
                    'error_type': type(exception).__name__,
                    'error_message': str(exception),
                    'method': request.method
                },
            )

    def _calculate_response_time(self):
        """Calculate response time in milliseconds."""
        if hasattr(g, 'analytics_start_time'):
            return int((time.time() - g.analytics_start_time) * 1000)
        return 0
