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

from flask import current_app, flash, g, render_template  # dead-code-ok
from flask_login import login_required

from app.extensions.cache import cached

from . import capability_map


def _compute_capability_mapping_counts():
    """Real per-capability app-mapping counts, org-scoped, one bounded query.

    Returns ``None`` (not ``{}``) when the count could not be computed at
    all — e.g. no tenant context, or the query itself failed — so callers
    can tell "we asked and every capability truly has 0 mapped apps" (a
    real, dict-shaped answer, possibly all-zero) apart from "we never
    asked" (None). ``cap_to_dict`` below turns that into
    ``mapping_count: None`` on every node, which the hierarchy page's
    ``getCoverageDotClass`` renders as no dot at all rather than a
    fabricated red one, and the legend only appears when this returned a
    real dict.

    ``ApplicationCapabilityMapping`` is not ``TenantMixin`` (see the model),
    so the org predicate here is deliberate, not defence-in-depth. It is
    applied via the FK parent ``BusinessCapability`` (which *is*
    ``TenantMixin``), not ``ApplicationCapabilityMapping.organization_id`` --
    that column is NULL on every row in production (added nullable by
    reconcile-schema, never backfilled), so a predicate directly on it would
    report every capability as having 0 mapped apps for every org. See
    e622d36 / rationalization_scoring_service.py for the precedent.
    """
    org_id = getattr(g, "current_org_id", None)
    if org_id is None:
        return None

    from sqlalchemy import func

    from app import db
    from app.models.application_capability import ApplicationCapabilityMapping
    from app.models.business_capabilities import BusinessCapability

    try:
        rows = (
            db.session.query(
                ApplicationCapabilityMapping.business_capability_id,
                func.count(ApplicationCapabilityMapping.id),
            )
            .join(
                BusinessCapability,
                ApplicationCapabilityMapping.business_capability_id == BusinessCapability.id,
            )
            .filter(BusinessCapability.organization_id == org_id)
            .group_by(ApplicationCapabilityMapping.business_capability_id)
            .all()
        )
    except Exception:
        current_app.logger.exception("Could not compute capability mapping counts")
        return None

    return dict(rows)


@capability_map.route("")
@capability_map.route("/")
@login_required
def index():
    """Main capability mapping page"""
    from app.modules.capabilities.services.capability_count_service import (
        count_business_capabilities,
    )

    try:
        total_capabilities = count_business_capabilities()
    except Exception:
        current_app.logger.exception("Could not count business capabilities")
        total_capabilities = None

    return render_template("capability_map/index.html", total_capabilities=total_capabilities)


@capability_map.route("/hierarchy")
@login_required
@cached(
    ttl=300,
    key_prefix="capability_map:hierarchy",
    key_func=lambda: getattr(g, "current_org_id", None),
)
def hierarchy():
    """Capability hierarchy visualization — uses real BusinessCapability data."""
    from app.modules.capabilities.services.capability_count_service import (
        count_business_capabilities,
    )

    try:
        total_capabilities = count_business_capabilities()
    except Exception:
        current_app.logger.exception("Could not count business capabilities")
        total_capabilities = None

    try:
        from app.models.business_capabilities import BusinessCapability

        capabilities = BusinessCapability.query.order_by(
            BusinessCapability.level, BusinessCapability.name
        ).all()

        # Build parent lookup
        children_by_parent = {}
        for c in capabilities:
            if c.parent_capability_id:
                children_by_parent.setdefault(c.parent_capability_id, []).append(c)

        # Real per-capability app-mapping counts (or None — see the
        # function's docstring for why None is not the same as {}).
        mapping_counts = _compute_capability_mapping_counts()

        def cap_to_dict(cap):
            kids = children_by_parent.get(cap.id, [])
            mapping_count = (
                mapping_counts.get(cap.id, 0) if mapping_counts is not None else None
            )
            return {
                "name": cap.name,
                "description": cap.description or "",
                "level": cap.level,
                # Falsy values hide the badge in the template; "Unknown" and a
                # hardcoded "core" pill were fabricated labels on every row.
                "domain": cap.business_domain or "",
                "category": cap.category or "",
                "capability_type": getattr(cap, "capability_type", None) or "",
                "functions": [],
                "mapping_count": mapping_count,
                "children": [cap_to_dict(k) for k in kids],
            }

        # Root = L1 capabilities (no parent)
        roots = [c for c in capabilities if c.level == 1]
        catalog = {"children": [cap_to_dict(r) for r in roots]}

        return render_template(
            "capability_map/hierarchy.html",
            catalog=catalog,
            total_capabilities=total_capabilities,
            has_coverage_data=mapping_counts is not None,
        )
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
            total_capabilities=total_capabilities,
            has_coverage_data=False,
        )


@capability_map.route("/network")
@login_required
def network():
    """Capability network visualization"""
    return render_template("capability_map/network.html")


@capability_map.route("/simple")
@login_required
@cached(
    ttl=300,
    key_prefix="capability_map:simple",
    key_func=lambda: getattr(g, "current_org_id", None),
)
def simple_view():
    """Simple flat view of capabilities — real BusinessCapability data.

    Was previously a 612-line static template with no context at all: a
    hardcoded "38 capabilities / 124 functions / 11 domains" and a fictional
    "Digital Application Platform" taxonomy, shown identically to every
    tenant. Rebuilt on the same query pattern as ``hierarchy()`` above —
    level-1 roots with their direct children — but flattened for a page
    that is meant to be simple, not a recursive tree.
    """
    try:
        from app.models.business_capabilities import BusinessCapability

        capabilities = BusinessCapability.query.order_by(
            BusinessCapability.level, BusinessCapability.name
        ).all()

        children_by_parent = {}
        for c in capabilities:
            if c.parent_capability_id:
                children_by_parent.setdefault(c.parent_capability_id, []).append(c)

        def child_to_dict(cap):
            return {
                "name": cap.name,
                "description": cap.description or "",
                "level": cap.level,
                "domain": cap.business_domain or "",
            }

        roots = [c for c in capabilities if c.level == 1]
        capability_groups = [
            {
                "name": root.name,
                "description": root.description or "",
                "level": root.level,
                "domain": root.business_domain or "",
                "children": [
                    child_to_dict(child) for child in children_by_parent.get(root.id, [])
                ],
            }
            for root in roots
        ]

        levels = [c.level for c in capabilities if c.level is not None]
        domains = {c.business_domain for c in capabilities if c.business_domain}

        stats = {
            "total": len(capabilities),
            "l1_count": len(roots),
            "max_depth": max(levels) if levels else None,
            "domain_count": len(domains),
        }

        return render_template(
            "capability_map/simple.html",
            capability_groups=capability_groups,
            stats=stats,
        )
    except Exception:
        from app import db

        db.session.rollback()
        current_app.logger.exception("Could not load the simple capability view")
        flash("Error loading the capability view. Please try again.", "error")
        return render_template(
            "capability_map/simple.html",
            capability_groups=[],
            stats={"total": None, "l1_count": None, "max_depth": None, "domain_count": None},
            load_error="The capability list could not be read.",
        )


@capability_map.route("/dashboard")
@login_required
@cached(
    ttl=300,
    key_prefix="capability_map:dashboard",
    key_func=lambda: getattr(g, "current_org_id", None),
)
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
