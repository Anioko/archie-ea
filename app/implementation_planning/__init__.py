"""
DEPRECATED: This file is migrated to app/modules/applications/.
Registration is now centralized via app.modules.applications.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

Implementation Planning Blueprint

ArchiMate 3.2 Implementation & Migration Planning module for enterprise architecture.

This blueprint provides comprehensive implementation planning capabilities including:
- WorkPackage management and tracking
- Deliverable management
- Gap analysis and discovery
- Plateau state management
- ImplementationEvent tracking
- Gantt chart visualization
- Export capabilities (CSV, PNG, JPG)

Complies with:
- ArchiMate 3.2 Specification
- Flask blueprint patterns
- RESTful API design
- shadcn/ui design system
"""

from flask import Blueprint, abort

# Create the implementation planning blueprint
implementation_planning = Blueprint(
    "implementation_planning", __name__, template_folder="templates", url_prefix="/implementation"
)

# Mark as guardrailed BEFORE routes are registered
from app.core.compat import mark_blueprint_guardrailed
mark_blueprint_guardrailed(implementation_planning)


@implementation_planning.before_request
def _check_feature_flag():
    """Block all requests — module deprecated.

    Unlike ``is_feature_enabled`` (which defaults to True when a flag row
    is missing), this guard defaults to **disabled** so the module stays
    off even on a fresh database that hasn't run the seed script.
    """
    from app.models.feature_flags import FeatureFlag

    flag = FeatureFlag.query.filter_by(
        key="architecture_implementation_planning"
    ).first()
    # Only allow access when the flag explicitly exists AND is active
    if not flag or not flag.is_active:
        abort(404)


# Import routes to register them
from . import routes
