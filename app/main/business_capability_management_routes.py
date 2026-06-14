# WARNING: THIS FILE IS NOT REGISTERED — blueprint never added to app.
# The canonical capabilities blueprint is 'capability_map'.
#!/usr/bin/env python3
"""
Business Capability Management Routes

Provides routes for managing business capability lists, taxonomy,
and organization separate from maturity management.
"""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import text

from app import db
from app.utils.business_capability_classifier import BusinessCapabilityClassifier

# Create blueprint
business_capability_management = Blueprint("business_capability_management", __name__)


@business_capability_management.route("/capabilities")
@login_required
def capabilities_overview():
    """Main overview of all business capabilities"""

    try:
        # Get all capabilities
        _org_params = {}

        # Classify capabilities by business grouping
        classified_capabilities = {}
        for cap in capabilities:
            classification = BusinessCapabilityClassifier.classify_capability_by_name(
                cap.name, cap.description
            )
            if classification:
                grouping_key = classification["grouping_key"]
                if grouping_key not in classified_capabilities:
                    classified_capabilities[grouping_key] = {
                        "info": BusinessCapabilityClassifier.get_grouping_summary(
                            grouping_key
                        ),
                        "capabilities": [],
                    }
                classified_capabilities[grouping_key]["capabilities"].append(
                    {"capability": cap, "classification": classification}
                )

        # Get overall statistics
        total_capabilities = len(capabilities)
        classified_count = sum(
            len(data["capabilities"]) for data in classified_capabilities.values()
        )

        return render_template(
            "business_capability/overview.html",
            classified_capabilities=classified_capabilities,
            total_capabilities=total_capabilities,
            classified_count=classified_count,
        )

    except Exception as e:
        flash("Error loading capabilities overview. Please try again.", "error")
        return render_template(
            "business_capability/overview.html",
            classified_capabilities={},
            total_capabilities=0,
            classified_count=0,
        )


@business_capability_management.route("/capabilities/groupings")
@login_required
def groupings_overview():
    """Overview of all business groupings"""

    try:
        # Get all business groupings
        groupings = BusinessCapabilityClassifier.get_business_groupings()

        # Get capability counts for each grouping
        grouping_stats = {}

        for grouping_key, grouping_data in groupings.items():
            # Count capabilities in this grouping
            _grp_params = {
                "keyword1": f"%{grouping_key}%",
                "keyword2": f"%{grouping_data['name'].split()[0].lower()}%",
                "keyword3": f"%{grouping_data['icon']}%",
            }
            grouping_stats[grouping_key] = {
                "count": count,
                "subcategories": grouping_data["subcategories"],
            }

        return render_template(
            "business_capability/overview.html",
            groupings=groupings,
            grouping_stats=grouping_stats,
        )

    except Exception as e:
        flash("Error loading groupings overview. Please try again.", "error")
        return redirect(url_for("capability_map.simple_view"))


@business_capability_management.route("/capabilities/grouping/<grouping_key>")
@login_required
def grouping_detail(grouping_key):
    """Detailed view of a specific business grouping"""

    try:
        # Get grouping information
        grouping_info = BusinessCapabilityClassifier.get_grouping_summary(grouping_key)

        if not grouping_info:
            flash(f'Business grouping "{grouping_key}" not found', "error")
            return redirect(
                url_for("capability_map.simple_view")
            )

        # Get capabilities in this grouping
        _org_filter2 = ""
        _org_params2 = {}

        # Filter and classify capabilities for this grouping
        grouping_capabilities = []
        for cap in all_capabilities:
            classification = BusinessCapabilityClassifier.classify_capability_by_name(
                cap.name, cap.description
            )
            if classification and classification["grouping_key"] == grouping_key:
                grouping_capabilities.append(
                    {"capability": cap, "classification": classification}
                )

        # Group by subcategory
        subcategory_capabilities = {}
        for cap_data in grouping_capabilities:
            subcat_key = cap_data["classification"]["subcategory_key"]
            if subcat_key not in subcategory_capabilities:
                subcategory_capabilities[subcat_key] = {
                    "info": grouping_info["subcategories"][subcat_key],
                    "capabilities": [],
                }
            subcategory_capabilities[subcat_key]["capabilities"].append(cap_data)

        return render_template(
            "business_capability/overview.html",
            grouping_info=grouping_info,
            subcategory_capabilities=subcategory_capabilities,
            total_capabilities=len(grouping_capabilities),
        )

    except Exception as e:
        flash("Error loading grouping detail. Please try again.", "error")
        return redirect(url_for("capability_map.simple_view"))


@business_capability_management.route("/capabilities/taxonomy")
@login_required
def capability_taxonomy():
    """Capability taxonomy and hierarchy view"""

    try:
        # Get all capabilities with their classifications
        _org_filter3 = ""
        _org_params3 = {}

        # Organize by capability type and level
        capability_types = BusinessCapabilityClassifier.get_capability_types()
        capability_levels = BusinessCapabilityClassifier.get_capability_levels()

        # Classify and organize capabilities
        organized_capabilities = {}

        for cap in capabilities:
            classification = BusinessCapabilityClassifier.classify_capability_by_name(
                cap.name, cap.description
            )

            # Determine capability type
            cap_type = "other"
            for type_key, type_data in capability_types.items():
                if classification:
                    # Simple heuristic based on classification
                    if classification["grouping_key"] in ["strategic"]:
                        cap_type = "management"
                    elif classification["grouping_key"] in ["support"]:
                        cap_type = "supporting"
                    else:
                        cap_type = "primary"
                break

            if cap_type not in organized_capabilities:
                organized_capabilities[cap_type] = {
                    "info": capability_types.get(
                        cap_type,
                        {
                            "name": cap_type.title(),
                            "description": "Uncategorized capabilities",
                        },
                    ),
                    "capabilities": [],
                }

            organized_capabilities[cap_type]["capabilities"].append(
                {"capability": cap, "classification": classification}
            )

        return render_template(
            "business_capability/overview.html",
            organized_capabilities=organized_capabilities,
            capability_types=capability_types,
            capability_levels=capability_levels,
        )

    except Exception as e:
        flash("Error loading capability taxonomy. Please try again.", "error")
        return redirect(url_for("capability_map.simple_view"))


@business_capability_management.route("/capabilities/search")
@login_required
def search_capabilities():
    """Search and filter business capabilities"""

    query = request.args.get("q", "")
    grouping = request.args.get("grouping", "")
    capability_type = request.args.get("type", "")
    strategic_importance = request.args.get("strategic_importance", "")
    page = int(request.args.get("page", 1))
    per_page = 20

    try:
        # Build base query
        base_query = """
            SELECT id, name, domain, description, category, capability_type,
                   strategic_importance, business_owner, created_at, updated_at
            FROM business_capability
            WHERE 1=1
        """

        params = {}


        if query:
            base_query += " AND (name ILIKE :query OR description ILIKE :query)"
            params["query"] = f"%{query}%"

        # Add ordering and pagination
        base_query += (
            " ORDER BY strategic_importance DESC, name LIMIT :limit OFFSET :offset"
        )
        params["limit"] = per_page
        params["offset"] = (page - 1) * per_page

        result = db.session.execute(text(base_query), params)  # tenant-filtered
        capabilities = result.fetchall()

        # Classify capabilities
        classified_capabilities = []
        for cap in capabilities:
            classification = BusinessCapabilityClassifier.classify_capability_by_name(
                cap.name, cap.description
            )
            classified_capabilities.append(
                {"capability": cap, "classification": classification}
            )

        # Filter by grouping if specified
        if grouping:
            classified_capabilities = [
                cap_data
                for cap_data in classified_capabilities
                if cap_data["classification"]
                and cap_data["classification"]["grouping_key"] == grouping
            ]

        # Get total count for pagination
        count_query = base_query.replace(
            "SELECT id, name, domain, description, category, capability_type, strategic_importance, business_owner, created_at, updated_at",
            "SELECT COUNT(*)",
        ).replace(
            "ORDER BY strategic_importance DESC, name LIMIT :limit OFFSET :offset", ""
        )

        count_result = db.session.execute(text(count_query), params)  # tenant-filtered
        total_count = count_result.scalar()

        # Get available groupings
        groupings = BusinessCapabilityClassifier.get_business_groupings()
        capability_types = BusinessCapabilityClassifier.get_capability_types()

        return render_template(
            "business_capability/overview.html",
            classified_capabilities=classified_capabilities,
            groupings=groupings,
            capability_types=capability_types,
            total_count=total_count,
            page=page,
            per_page=per_page,
            query=query,
            selected_grouping=grouping,
            selected_type=capability_type,
            selected_importance=strategic_importance,
        )

    except Exception as e:
        flash("Error searching capabilities. Please try again.", "error")
        return render_template(
            "business_capability/overview.html",
            classified_capabilities=[],
            groupings={},
            capability_types={},
            total_count=0,
        )


@business_capability_management.route("/capabilities/detail/<int:capability_id>")
@login_required
def capability_detail(capability_id):
    """Detailed view of a specific capability"""

    try:
        # Get capability details
        _detail_params = {"capability_id": capability_id}
        _org_clause_d = ""

        capability = result.fetchone()

        if not capability:
            flash("Capability not found", "error")
            return redirect(
                url_for("capability_map.simple_view")
            )

        # Classify the capability
        classification = BusinessCapabilityClassifier.classify_capability_by_name(
            capability.name, capability.description
        )

        # Get related capabilities (same grouping)
        related_capabilities = []
        if classification:
            _rel_params = {
                "capability_id": capability_id,
                "keyword1": f"%{classification['grouping_key']}%",
                "keyword2": f"%{classification['subcategory_key']}%",
            }
            _org_clause_r = ""

        return render_template(
            "business_capability/overview.html",
            capability=capability,
            classification=classification,
            related_capabilities=related_capabilities,
        )

    except Exception as e:
        flash("Error loading capability detail. Please try again.", "error")
        return redirect(url_for("capability_map.simple_view"))


@business_capability_management.route("/capabilities/analytics")
@login_required
def capability_analytics():
    """Analytics and insights for business capabilities"""

    try:
        # Get capability distribution analytics
        _org_filter_a = ""
        _org_params_a = {}

        # Get domain distribution
        _org_and_a = ""

        # Get category distribution
        result = db.session.execute(  # tenant-filtered
            text(
                f"""
            SELECT category, COUNT(*) as count
            FROM business_capability
            WHERE category IS NOT NULL{_org_and_a}
            GROUP BY category
            ORDER BY count DESC
            LIMIT 20
        """
            ),
            _org_params_a,
        )
        category_distribution = result.fetchall()

        # Get business grouping distribution
        all_capabilities = []
        result = db.session.execute(  # tenant-filtered
            text(
                f"""
            SELECT id, name, description
            FROM business_capability
            {_org_filter_a}
            ORDER BY name
        """
            ),
            _org_params_a,
        )
        capabilities = result.fetchall()

        grouping_distribution = {}
        for cap in capabilities:
            classification = BusinessCapabilityClassifier.classify_capability_by_name(
                cap.name, cap.description
            )
            if classification:
                grouping_key = classification["grouping_key"]
                grouping_name = classification["grouping_name"]
                if grouping_key not in grouping_distribution:
                    grouping_distribution[grouping_key] = {
                        "name": grouping_name,
                        "count": 0,
                    }
                grouping_distribution[grouping_key]["count"] += 1

        return render_template(
            "business_capability/overview.html",
            overall_stats=overall_stats,
            domain_distribution=domain_distribution,
            category_distribution=category_distribution,
            grouping_distribution=grouping_distribution,
        )

    except Exception as e:
        flash("Error loading capability analytics. Please try again.", "error")
        return redirect(url_for("capability_map.simple_view"))
