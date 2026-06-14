"""Feature flag decorators and helpers.

Provides decorators for route protection and template helpers.
"""

from functools import wraps

from flask import abort, render_template, request

from app.models.feature_flags import FeatureFlag


def feature_required(feature_key: str, fallback_template: str = None):
    """Decorator to require a feature flag to be enabled.

    Usage:
        @app.route('/solutions/')
        @feature_required('solutions_management')
        def solutions_list():
            ...

    Args:
        feature_key: Feature flag key to check
        fallback_template: Optional template to render if disabled (default: 404)
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not FeatureFlag.is_feature_enabled(feature_key):
                if fallback_template:
                    feature = FeatureFlag.query.filter_by(key=feature_key).first()
                    return render_template(
                        fallback_template,
                        feature=feature,
                        feature_name=feature.name if feature else feature_key,
                    )
                abort(404)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def check_route_feature_flag():
    """Check if current route is controlled by a feature flag.

    Returns feature flag or None. Can be used in before_request handlers.
    """
    feature = FeatureFlag.get_route_feature(request.path)
    if feature and not feature.is_active:
        return feature
    return None


def get_feature_context():
    """Get feature flag context for templates.

    Returns:
        Dict with feature checking functions for use in templates
    """
    return {
        "is_feature_enabled": FeatureFlag.is_feature_enabled,
        "get_feature": lambda key: FeatureFlag.query.filter_by(key=key).first(),
        "sidebar_features": FeatureFlag.get_sidebar_features(),
    }
