"""
Flask App Integration for Navigation Registry V2

Shows how to integrate the new navigation registry into Flask app,
validate on startup, and provide context processor for templates.
"""

from flask import Flask, g
from flask_login import current_user

from app.config.navigation_registry_v2 import get_registry, validate_on_startup
from app.config.navigation_sections_v2 import register_all_sections


def init_navigation(app: Flask) -> None:
    """
    Initialize navigation system on Flask app startup.
    
    Do this in app/__init__.py:
    
    ```python
    from app.config.navigation_setup import init_navigation
    
    def create_app():
        app = Flask(__name__)
        # ... other setup ...
        
        # Initialize navigation AFTER blueprints registered
        init_navigation(app)
        
        return app
    ```
    """
    
    # Step 1: Register all sections
    app.logger.debug("[Navigation] Registering sections...")
    register_all_sections()

    # Step 2: Validate registry on startup
    app.logger.debug("[Navigation] Validating registry...")
    if not validate_on_startup():
        # IMPORTANT: Fail loudly in development, warn in production
        if app.debug:
            raise RuntimeError("Navigation registry validation failed. See logs above.")
        else:
            app.logger.error("Navigation registry validation failed. Some menu items may be broken.")
    
    # Step 3: Add template context processor
    @app.context_processor
    def inject_navigation():
        """
        Inject navigation into all templates.
        
        Usage in templates:
        ```jinja2
        {% for section in nav_sections %}
            <nav-section :section="{{ section | tojson }}" />
        {% endfor %}
        ```
        """
        # Get current endpoint from Flask
        from flask import request
        current_endpoint = request.endpoint
        
        # Load applications and vendors for dynamic items
        # (This should be optimized with caching)
        applications = []
        vendors = []
        
        try:
            from app.models import ApplicationComponent, Vendor
            from app import db
            
            # Get top N most-used applications
            applications = db.session.query(ApplicationComponent)\
                .limit(15)\
                .all()
            
            # Get top N most-used vendors
            vendors = db.session.query(Vendor)\
                .limit(15)\
                .all()
        except Exception as e:
            app.logger.debug(f"Could not load dynamic items: {e}")
        
        # Get navigation sections
        registry = get_registry()
        nav_sections = registry.get_navigation_sections(
            current_endpoint=current_endpoint,
            user=current_user if current_user.is_authenticated else None,
            applications=applications,
            vendors=vendors,
            include_disabled=False,  # Hide disabled items in UI
        )
        
        # Get breadcrumbs
        from flask import request
        breadcrumbs = registry.get_breadcrumb_trail(
            current_endpoint=current_endpoint,
            current_url=request.path,
        )
        
        return {
            "nav_sections": nav_sections,
            "nav_breadcrumbs": breadcrumbs,
            "nav_registry": registry,  # For advanced usage
        }
    
    app.logger.info("✓ Navigation system initialized")


# ============================================================================
# USAGE IN TEMPLATES
# ============================================================================
"""
Example: app/templates/components/admin_sidebar.html

<nav>
    {% for section in nav_sections %}
        <nav-section 
            :section="{{ section | tojson }}"
            :is-collapsible="{{ section.collapsible | tojson }}"
        />
    {% endfor %}
</nav>

Example: Breadcrumb component

<nav class="breadcrumb">
    {% for breadcrumb in nav_breadcrumbs %}
        <a href="{{ breadcrumb.url }}">{{ breadcrumb.label }}</a>
        {% if not loop.last %}<span>/</span>{% endif %}
    {% endfor %}
</nav>
"""


# ============================================================================
# USAGE IN PYTHON CODE
# ============================================================================
"""
Getting navigation programmatically:

from app.config.navigation_registry_v2 import get_registry

registry = get_registry()

# Get sections for a specific user
sections = registry.get_navigation_sections(
    current_endpoint="admin.index",
    user=current_user,
    applications=app_list,
    vendors=vendor_list,
)

# Check if endpoint is valid
is_valid = registry._endpoint_exists("admin.index")

# Get breadcrumbs
breadcrumbs = registry.get_breadcrumb_trail(
    current_endpoint="vendors.vendor_detail",
    current_url="/applications/vendors/42"
)
"""


# ============================================================================
# MIGRATION GUIDE: Old Registry → New Registry
# ============================================================================
"""
If you're using the old navigation_registry.py:

BEFORE (Old):
    from app.config.navigation_registry import get_navigation_sections
    
    nav = get_navigation_sections(
        current_endpoint=request.endpoint,
        applications=app_list,
        vendors=vendor_list,
    )

AFTER (New):
    from app.config.navigation_registry_v2 import get_registry
    
    registry = get_registry()
    nav = registry.get_navigation_sections(
        current_endpoint=request.endpoint,
        user=current_user,  # NEW: permission checking
        applications=app_list,
        vendors=vendor_list,
        include_disabled=False,  # NEW: hide disabled items
    )

KEY DIFFERENCES:
✓ New: user parameter (for permission checks)
✓ New: include_disabled parameter
✓ New: Validation on startup
✓ New: Proper logging for errors
✓ New: Support for nested items
✓ New: Permission model (roles/visibility)
"""


# ============================================================================
# ERROR HANDLING
# ============================================================================
"""
Common Errors & Solutions:

1. AttributeError: 'Vendor' object has no attribute 'vendor_type'
   CAUSE: Dynamic items trying to access missing field
   SOLUTION: Check badge_field matches actual model field name
   CODE: dynamic_items_badge_field="status"  # Not "vendor_type"

2. RuntimeError: Endpoint 'admin.does_not_exist' not registered
   CAUSE: Typo in endpoint name
   SOLUTION: Check Flask app has route registered
   CODE: @app.route("/admin/users")
         def registered_users():
             # This creates endpoint "main.registered_users"

3. WARNING: Failed to generate URL for endpoint 'vendors.detail': id=None
   CAUSE: Object missing id field
   SOLUTION: Ensure all objects in dynamic list have id field
   CODE: if not hasattr(vendor, 'id'):
             logger.warning(f"Vendor missing id: {vendor}")

4. Circular parent-child reference detected in section 'xyz'
   CAUSE: Section references itself as parent
   SOLUTION: Check parent_section field points to actual parent
   CODE: parent_section="enterprise_architecture"  # Must exist

5. Endpoint 'X' used in multiple sections (A, B)
   CAUSE: Same endpoint registered in 2+ menus
   SOLUTION: Check for duplicates in sections
   NOTE: This is just a warning, not an error
"""
