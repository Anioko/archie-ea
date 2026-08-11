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

from flask import current_app, flash, render_template  # dead-code-ok
from flask_login import login_required

from app.extensions.cache import cached

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
        known_ids = {c.id for c in capabilities}
        children_by_parent = {}
        for c in capabilities:
            if c.parent_capability_id:
                children_by_parent.setdefault(c.parent_capability_id, []).append(c)

        rendered = set()

        def cap_to_dict(cap, ancestors):
            # A parent cycle would recurse until the stack blew and the whole
            # page fell into the error branch below. Imported hierarchies are
            # the realistic source of one, so stop at the repeat instead.
            rendered.add(cap.id)
            kids = [
                k for k in children_by_parent.get(cap.id, []) if k.id not in ancestors
            ]
            return {
                "name": cap.name,
                "description": cap.description or "",
                "level": cap.level,
                "domain": cap.business_domain or "Unknown",
                "category": cap.category or "",
                "capability_type": "core",
                "functions": [],
                "children": [cap_to_dict(k, ancestors | {cap.id}) for k in kids],
            }

        # A root is a capability nothing else parents — not "level == 1".
        # Keying roots off the level column dropped every capability that had no
        # parent and a level of 2, 3 or NULL, which is the ordinary shape of a
        # freshly imported or partly decomposed model: the rows were in the
        # database, counted on the capability map, and absent from this tree.
        # A row whose parent_capability_id points outside the result set is also
        # a root here, otherwise it has no ancestor to be rendered under and
        # disappears the same way.
        roots = [
            c
            for c in capabilities
            if not c.parent_capability_id or c.parent_capability_id not in known_ids
        ]
        children = [cap_to_dict(r, frozenset()) for r in roots]

        # Anything still unrendered is in a parent cycle, so no member of it is
        # parentless and none of them would appear at all. Surfacing them at the
        # top level is the only presentation that does not silently lose rows.
        for cap in capabilities:
            if cap.id not in rendered:
                children.append(cap_to_dict(cap, frozenset()))

        catalog = {"children": children}

        return render_template("capability_map/hierarchy.html", catalog=catalog)
    except Exception as e:
        from app import db

        db.session.rollback()
        current_app.logger.exception("Unexpected error loading hierarchy: %s", e)
        flash("Error loading the capability hierarchy. Please try again.", "error")
        # The catalog shape is required by the Alpine tree, so it stays a dict
        # with an empty children list - no invented nodes. load_error is what
        # tells the user the tree is empty because nothing could be read.
        return render_template(
            "capability_map/hierarchy.html",
            catalog={"children": []},
            load_error="The capability hierarchy could not be read.",
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
