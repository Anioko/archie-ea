"""
Capability Map — template-rendering views and shared helpers.

Extracted from app/routes/capability_map_routes.py (lines 49-82, 1300-1338, 3016-3082).

Routes:
    - index()           GET ""  "/"
    - hierarchy()       GET "/hierarchy"
    - network()         GET "/network"
    - simple_view()     GET "/simple"
    - dashboard()       GET "/dashboard"

Helpers:
    - build_nodes_edges(catalog)   — used by mapping_routes.api_nodes_edges()
"""

from flask import current_app, jsonify, render_template, request  # dead-code-ok
from flask_login import login_required

from app.extensions.cache import cached
from app.exceptions import (  # dead-code-ok
    BusinessRuleError,
    DatabaseError,
    ExternalServiceError,
    IntegrityError,
    NotFoundError,
    ValidationError,
)

from . import capability_map


@capability_map.route("")
@capability_map.route("/")
@login_required
def index():
    """Main capability mapping page"""
    return render_template("capability_map/index.html")


@capability_map.route("/hierarchy")
@login_required
@cached(ttl=300, key_prefix="capability_map:hierarchy")
def hierarchy():
    """Capability hierarchy visualization — uses real BusinessCapability data."""
    try:
        from app.models.business_capabilities import BusinessCapability

        capabilities = BusinessCapability.query.order_by(
            BusinessCapability.level, BusinessCapability.name
        ).all()

        # Build parent lookup
        by_id = {c.id: c for c in capabilities}
        children_by_parent = {}
        for c in capabilities:
            if c.parent_capability_id:
                children_by_parent.setdefault(c.parent_capability_id, []).append(c)

        def cap_to_dict(cap):
            kids = children_by_parent.get(cap.id, [])
            return {
                "name": cap.name,
                "description": cap.description or "",
                "level": cap.level,
                "domain": cap.business_domain or "Unknown",
                "category": cap.category or "",
                "capability_type": "core",
                "functions": [],
                "children": [cap_to_dict(k) for k in kids],
            }

        # Root = L1 capabilities (no parent)
        roots = [c for c in capabilities if c.level == 1]
        catalog = {"children": [cap_to_dict(r) for r in roots]}

        return render_template("capability_map/hierarchy.html", catalog=catalog)
    except Exception as e:
        current_app.logger.error(f"Unexpected error loading hierarchy: {e}")
        return render_template(
            "capability_map/hierarchy.html", catalog={"children": []}
        )


@capability_map.route("/network")
@login_required
def network():
    """Capability network visualization"""
    return render_template("capability_map/network.html")


@capability_map.route("/simple")
@login_required
def simple_view():
    """Simple static view of capabilities (no API dependencies)"""
    return render_template("capability_map/simple.html")


@capability_map.route("/dashboard")
@login_required
@cached(ttl=300, key_prefix="capability_map:dashboard")
def dashboard():
    """Comprehensive dashboard with multiple visualization types"""
    try:
        # Get statistics
        from app.services.application_capability_catalog import (
            ApplicationCapabilityCatalogService,
        )

        validation = ApplicationCapabilityCatalogService.validate_capability_structure()
        catalog = ApplicationCapabilityCatalogService.get_catalog_hierarchy()

        # Get application statistics
        from app.models.application_layer import ApplicationComponent

        applications = ApplicationComponent.query.count()
        from app.models.business_capabilities import ApplicationCapabilityCoverage

        mappings = ApplicationCapabilityCoverage.query.count()

        return render_template(
            "capability_map/index.html",
            catalog=catalog,
            validation=validation,
            app_count=applications,
            mapping_count=mappings,
        )
    except Exception as e:
        current_app.logger.error(f"Error loading capability map: {e}")
        return render_template(
            "capability_map/error.html",
            error="An unexpected error occurred. Please try again.",
        )


# ---------------------------------------------------------------------------
# Helper: build_nodes_edges — used by mapping_routes.api_nodes_edges()
# ---------------------------------------------------------------------------


def build_nodes_edges(catalog):
    """Build nodes and edges for network visualization"""
    nodes = []
    edges = []
    node_id = 0

    # catalog is a tree root dict with "children"; flatten to list of capabilities
    capabilities = catalog.get("children", []) if isinstance(catalog, dict) else catalog

    # Add capability nodes
    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        nodes.append(
            {
                "id": node_id,
                "name": capability.get("name", "Unknown"),
                "category": capability.get("category", "capability"),
                "level": capability.get("level", 1),
                "domain": capability.get("domain", "Unknown"),
                "type": capability.get("type", "capability"),
            }
        )
        cap_node_id = node_id
        node_id += 1

        # Add function nodes for this capability
        for function in capability.get("functions", []):
            if not isinstance(function, dict):
                continue
            nodes.append(
                {
                    "id": node_id,
                    "name": function.get("name", "Unknown"),
                    "category": "function",
                    "level": function.get("level", 2),
                    "domain": capability.get("domain", "Unknown"),
                    "type": "function",
                }
            )
            # Edge from capability to its function
            edges.append({"source": cap_node_id, "target": node_id})
            node_id += 1

        # Recurse into children
        for child in capability.get("children", []):
            if not isinstance(child, dict):
                continue
            nodes.append(
                {
                    "id": node_id,
                    "name": child.get("name", "Unknown"),
                    "category": child.get("category", "capability"),
                    "level": child.get("level", 2),
                    "domain": child.get("domain", capability.get("domain", "Unknown")),
                    "type": child.get("type", "capability"),
                }
            )
            edges.append({"source": cap_node_id, "target": node_id})
            node_id += 1

    return nodes, edges
