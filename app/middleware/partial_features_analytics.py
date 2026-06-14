"""
Usage Analytics Middleware for PARTIAL Features — DISABLED (STAB-002)

Tracks page views, feature interactions, and errors for all 32 PARTIAL features
to establish usage baselines before committing to 278-hour completion roadmap.

NOTE: This middleware is DISABLED per STAB-002 stability reset.
init_app() is never called, so before_request/after_request hooks are not registered.
Do NOT call partial_features_analytics.init_app(app) until the stability plan is complete.

This middleware automatically instruments routes when added to route files.
"""
import uuid
from flask import current_app, g, request, session
from app.models.usage_analytics import UsageAnalytics


class PartialFeaturesAnalytics:
    """Middleware for tracking PARTIAL feature usage."""

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the middleware with the Flask app."""
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_request(self._teardown_request)

        # Add config defaults
        app.config.setdefault('ENABLE_USAGE_ANALYTICS', True)
        app.config.setdefault('ANALYTICS_TRACKED_FEATURES', [
            'batch_import_routes',
            'dedupe_routes',
            'import_recovery_routes',
            'solution_architect_routes',
            'solution_composer_routes',
            'unified_duplicate_routes',
            'unified_low_priority_routes',
            'vendor_mdm_api',
            'abacus_consolidation',
            'ai_assistance_routes',
            'ai_dedupe_routes',
            'ai_gap_detection_routes',
            'batch_import_view_routes',
            'consolidation_list_routes',
            'enterprise_api_routes',
            'options_analysis_api',
            'security_api',
            'streaming_import_routes',
            'workflow_optimization_routes',
            'capability_naming_routes',
            'unified_enterprise_routes',
            'webhook',
            'enterprise_api',
            'adm_kanban_routes',
            'enhanced_applications_routes',
            'advanced_governance_routes',
            'architect_ui_routes',
            'import_recovery_ui_routes',
            'intelligent_agents_routes',
            'predictive_analytics_routes',
            'root_routes',
            'testing_routes'
        ])

    def _before_request(self):
        """Set up analytics tracking for the request."""
        if not current_app.config.get('ENABLE_USAGE_ANALYTICS', False):
            return

        # Skip static files — no analytics needed
        if request.path.startswith("/static/") or request.path == "/favicon.ico":
            return

        # Generate or get session ID
        if 'analytics_session_id' not in session:
            session['analytics_session_id'] = str(uuid.uuid4())

        g.analytics_session_id = session.get('analytics_session_id')
        g.analytics_start_time = request.environ.get('REQUEST_TIME', 0)
        g.analytics_feature_name = self._extract_feature_name(request.path)
        g.analytics_user_id = getattr(g, 'user', None).id if hasattr(g, 'user') and g.user else None

        # Track page view
        if g.analytics_feature_name:
            UsageAnalytics.track_event(
                event_type='page_view',
                feature_name=g.analytics_feature_name,
                route_path=request.path,
                user_id=g.analytics_user_id,
                session_id=g.analytics_session_id,
                request=request
            )

    def _after_request(self, response):
        """Track successful responses."""
        if not current_app.config.get('ENABLE_USAGE_ANALYTICS', False):
            return response

        # Track feature interactions (successful API calls)
        if (g.get('analytics_feature_name') and
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
                request=request
            )

        return response

    def _teardown_request(self, exception):
        """Track errors if they occurred."""
        if not current_app.config.get('ENABLE_USAGE_ANALYTICS', False):
            return

        if exception and g.get('analytics_feature_name'):
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
                request=request
            )

    def _extract_feature_name(self, path):
        """Extract feature name from request path."""
        # Map URL patterns to feature names
        feature_mappings = {
            '/batch-import': 'batch_import_routes',
            '/dedupe': 'dedupe_routes',
            '/import-recovery': 'import_recovery_routes',
            '/solution-architect': 'solution_architect_routes',
            '/solution-composer': 'solution_composer_routes',
            '/unified-duplicate': 'unified_duplicate_routes',
            '/unified-low-priority': 'unified_low_priority_routes',
            '/vendor-mdm': 'vendor_mdm_api',
            '/abacus-consolidation': 'abacus_consolidation',
            '/ai-assistance': 'ai_assistance_routes',
            '/ai-dedupe': 'ai_dedupe_routes',
            '/ai-gap-detection': 'ai_gap_detection_routes',
            '/batch-import-view': 'batch_import_view_routes',
            '/consolidation-list': 'consolidation_list_routes',
            '/enterprise-api': 'enterprise_api_routes',
            '/options-analysis': 'options_analysis_api',
            '/security-api': 'security_api',
            '/streaming-import': 'streaming_import_routes',
            '/workflow-optimization': 'workflow_optimization_routes',
            '/capability-naming': 'capability_naming_routes',
            '/unified-enterprise': 'unified_enterprise_routes',
            '/webhook': 'webhook',
            '/enterprise-api': 'enterprise_api',
            '/adm-kanban': 'adm_kanban_routes',
            '/enhanced-applications': 'enhanced_applications_routes',
            '/advanced-governance': 'advanced_governance_routes',
            '/architect-ui': 'architect_ui_routes',
            '/import-recovery-ui': 'import_recovery_ui_routes',
            '/intelligent-agents': 'intelligent_agents_routes',
            '/predictive-analytics': 'predictive_analytics_routes',
            '/root': 'root_routes',
            '/testing': 'testing_routes'
        }

        for prefix, feature_name in feature_mappings.items():
            if path.startswith(prefix):
                return feature_name

        return None

    def _calculate_response_time(self):
        """Calculate response time in milliseconds."""
        if hasattr(g, 'analytics_start_time'):
            import time
            return int((time.time() - g.analytics_start_time) * 1000)
        return 0


# Create global instance
partial_features_analytics = PartialFeaturesAnalytics()