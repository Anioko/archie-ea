"""
Core middleware package.

Consolidates cross-cutting concerns from scattered locations into a single
namespace:

- **analytics** — Usage analytics for partial features
- **feature_flags** — Feature state management and detection

Sources:
- app/middleware/partial_features_analytics.py
- app/utils/feature_state_manager.py
- app/utils/capability_guardrails.py
- app/utils/policy_enforcer.py

Usage::

    from app.core.middleware.analytics import PartialFeaturesAnalytics
    from app.core.middleware.feature_flags import FeatureState
"""
