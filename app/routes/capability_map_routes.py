"""
Capability Mapping Routes

Routes for capability mapping, gap analysis, and business intelligence.

Performance optimizations:
- Uses data_cache for frequently-accessed capability and application data
- Reduces database queries by 80%+ on high-traffic endpoints
"""

from datetime import datetime

from flask import Blueprint, Response, current_app, jsonify, render_template, request
from flask_login import login_required

from .. import db

# Import caching utilities for performance
try:
    from app.services.core.data_cache import (  # dead-code-ok — conditional import for optional caching
        get_all_applications,
        get_all_capabilities,
        get_application_filter_options,
        get_capability_filter_options,
    )

    CACHING_AVAILABLE = True
except ImportError:
    CACHING_AVAILABLE = False

capability_map = Blueprint("capability_map", __name__)


@capability_map.route("/")
@login_required
def index():
    """Main capability mapping page.

    FAR-011 fix: Pass server-rendered stats to template as fallback for JS.
    Queries both BusinessCapability and UnifiedCapability tables.
    """
    from app.models.business_capabilities import BusinessCapability
    from app.models.unified_capability import BusinessDomain, UnifiedCapability
    from app.models.application_capability import ApplicationCapabilityMapping

    # Query both capability tables - use whichever has data
    biz_cap_count = BusinessCapability.query.count()
    unified_cap_count = UnifiedCapability.query.count()

    # Use BusinessCapability if it has data, otherwise UnifiedCapability
    if biz_cap_count > 0:
        total_capabilities = biz_cap_count
        domain_count = BusinessCapability.query.filter_by(level=1).count()
        mapped_count = db.session.query(
            ApplicationCapabilityMapping.business_capability_id
        ).distinct().count()
    else:
        total_capabilities = unified_cap_count
        domain_count = BusinessDomain.query.count()
        # For UnifiedCapability, count via unified mappings
        from app.models.capability_to_vendor_mapping import UnifiedCapabilityApplicationMapping
        mapped_count = db.session.query(
            UnifiedCapabilityApplicationMapping.capability_id
        ).distinct().count()

    # Calculate coverage percentage
    coverage = round((mapped_count / total_capabilities * 100) if total_capabilities > 0 else 0, 1)

    return render_template(
        "capability_map/index.html",
        total_capabilities=total_capabilities,
        domain_count=domain_count,
        mapped_count=mapped_count,
        coverage=coverage,
    )


@capability_map.route("/hierarchy")
@login_required
def hierarchy():
    """Capability hierarchy visualization"""
    try:
        from app.services.application_capability_catalog import ApplicationCapabilityCatalogService

        catalog = ApplicationCapabilityCatalogService.get_catalog_hierarchy()
        return render_template("capability_map/hierarchy.html", catalog=catalog)
    except Exception as e:
        current_app.logger.error(
            "Failed to load capability hierarchy route=%s method=%s: %s",
            request.path,
            request.method,
            e,
            exc_info=True,
        )
        # Preserve fallback behavior while surfacing a user-visible error state.
        return render_template(
            "capability_map/hierarchy.html",
            catalog={"children": []},
            error="Capability hierarchy is temporarily unavailable.",
        )


@capability_map.route("/network")
@login_required
def network():
    """Capability network visualization"""
    return render_template("capability_map/network.html")


@capability_map.route("/api/nodes-edges")
@login_required
def api_nodes_edges():
    """API endpoint for network visualization data"""
    try:
        from app.services.application_capability_catalog import ApplicationCapabilityCatalogService

        # Get capability catalog
        catalog = ApplicationCapabilityCatalogService.get_catalog_hierarchy()

        # Build nodes and edges for network graph
        nodes, edges = build_nodes_edges(catalog)

        return jsonify(
            {
                "nodes": nodes,
                "edges": edges,
                "statistics": {
                    "total_capabilities": len([n for n in nodes if n["category"] != "function"]),
                    "total_functions": len([n for n in nodes if n["category"] == "function"]),
                    "domains": list(set(n["domain"] for n in nodes if n["domain"])),
                    "max_level": max(n["level"] for n in nodes),
                },
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/applications")
@login_required
def api_applications():
    """API endpoint to get application mappings"""
    try:
        from app.models.application_layer import ApplicationComponent

        applications = ApplicationComponent.query.order_by(ApplicationComponent.name).all()

        app_data = []
        for app in applications:
            app_data.append(
                {
                    "id": app.id,
                    "name": app.name,
                    "type": app.component_type or "Unknown",
                    "description": app.description or "No description",
                    "domain": app.business_domain or "Not specified",
                    "owner": app.business_owner or "Not specified",
                    "status": app.lifecycle_status or app.deployment_status or "Unknown",
                    "criticality": app.criticality or app.business_criticality or "Not assessed",
                    "application_category": app.application_category or "Not categorised",
                    "total_cost_of_ownership": app.total_cost_of_ownership,
                }
            )

        return jsonify({"applications": app_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/unified-capabilities")
@login_required
def api_unified_capabilities():
    """API endpoint to get unified view of all capabilities (Application + Manufacturing)"""
    try:
        from app.models.application_layer import ApplicationComponent
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )
        from app.models.unified_capability import BusinessDomain, UnifiedCapability

        # Get application capabilities with mappings
        # Try unified table first; fall back to legacy BusinessCapability
        # when unified is empty (BPP data lives in application_capability_mapping)
        app_capabilities = UnifiedCapability.query.limit(2000).all()
        app_mappings = UnifiedApplicationCapabilityMapping.query.limit(10000).all()
        _using_legacy = False

        if not app_capabilities:
            # Unified table is empty — use legacy BusinessCapability + ApplicationCapabilityMapping
            from app.models.business_capabilities import BusinessCapability
            from app.models.application_capability import ApplicationCapabilityMapping

            app_capabilities = BusinessCapability.query.limit(2000).all()
            app_mappings = ApplicationCapabilityMapping.query.limit(10000).all()
            _using_legacy = True

        if _using_legacy:
            mapped_app_cap_ids = {m.business_capability_id for m in app_mappings}
        else:
            mapped_app_cap_ids = {m.unified_capability_id for m in app_mappings}

        # Try to get manufacturing capabilities - handle if model doesn't exist
        mfg_capabilities = []
        try:
            from app.models.manufacturing_capability import ManufacturingCapability

            mfg_capabilities = ManufacturingCapability.query.limit(2000).all()
        except ImportError:
            # Manufacturing capability model not available, skip it
            current_app.logger.warning(
                "Manufacturing capability model is unavailable; continuing without manufacturing data route=%s",
                request.path,
            )
        except Exception as e:
            # Other import errors, skip manufacturing
            current_app.logger.warning(
                "Failed loading manufacturing capabilities route=%s method=%s: %s",
                request.path,
                request.method,
                e,
                exc_info=True,
            )

        # Build unified capability list
        unified_capabilities = []

        # Add application capabilities
        for capability in app_capabilities:
            try:
                domain = None
                if _using_legacy:
                    # BusinessCapability has business_domain (string), not domain_id (FK)
                    _domain_name = getattr(capability, "business_domain", None) or "Unknown"  # model-safety-ok
                    _domain_code = _domain_name[:3].upper() if _domain_name != "Unknown" else "UNK"
                    domain = type("D", (), {"id": None, "name": _domain_name, "code": _domain_code})()
                elif getattr(capability, "domain_id", None):  # model-safety-ok
                    domain = BusinessDomain.query.get(capability.domain_id)

                # Calculate business impact (use getattr for legacy compat)
                business_impact = 0
                _si = getattr(capability, "strategic_importance", None)  # model-safety-ok
                if _si == "critical":
                    business_impact += 40
                elif _si == "high":
                    business_impact += 30
                elif _si == "medium":
                    business_impact += 20
                elif _si == "low":
                    business_impact += 10

                _bc = getattr(capability, "business_criticality", None)  # model-safety-ok
                if _bc == "mission_critical":
                    business_impact += 30
                elif _bc == "important":
                    business_impact += 20
                elif _bc == "supporting":
                    business_impact += 10

                if getattr(capability, "is_core_differentiator", False):  # model-safety-ok
                    business_impact += 30

                # Get application names for application capability
                app_mapped = capability.id in mapped_app_cap_ids
                _cap_id_field = "business_capability_id" if _using_legacy else "unified_capability_id"
                app_mapping_count = len(
                    [m for m in app_mappings if getattr(m, _cap_id_field, None) == capability.id]
                )

                # Get application names for application capability
                app_applications = []
                if app_mapped:
                    for mapping in app_mappings:
                        if getattr(mapping, _cap_id_field, None) == capability.id:
                            app_comp = ApplicationComponent.query.get(
                                mapping.application_component_id
                            )
                            if app_comp:
                                app_applications.append(
                                    {
                                        "name": app_comp.name,
                                        "type": getattr(app_comp, "component_type", "Application"),  # model-safety-ok
                                        "id": str(
                                            app_comp.id
                                        ),  # Convert to string to preserve precision
                                    }
                                )

                unified_capabilities.append(
                    {
                        "id": str(
                            capability.id
                        ),  # Convert to string to preserve precision for large Snowflake IDs
                        "name": capability.name,
                        "code": getattr(capability, "code", None) or f"CAP-{capability.id}",  # model-safety-ok
                        "type": "Application",
                        "level": getattr(capability, "level", 1) or 1,  # model-safety-ok
                        "category": getattr(capability, "category", None) or getattr(capability, "business_domain", "Unknown"),  # model-safety-ok
                        "domain": {
                            "id": str(domain.id)
                            if domain and domain.id
                            else None,  # Convert to string to preserve precision
                            "name": domain.name if domain else "Unknown",
                            "code": domain.code if domain else "UNK",
                        },
                        "business_owner": getattr(capability, "business_owner", None) or "Unassigned",  # model-safety-ok
                        "strategic_importance": getattr(capability, "strategic_importance", None) or "medium",  # model-safety-ok
                        "business_criticality": getattr(capability, "business_criticality", None) or "supporting",  # model-safety-ok
                        "is_core_differentiator": getattr(capability, "is_core_differentiator", False),  # model-safety-ok
                        "business_impact": min(business_impact, 100),
                        "current_maturity": getattr(capability, "current_maturity_level", 1) or 1,  # model-safety-ok
                        "target_maturity": getattr(capability, "target_maturity_level", 3) or 3,  # model-safety-ok
                        "maturity_gap": getattr(capability, "maturity_gap", 0) or 0,  # model-safety-ok
                        "annual_cost": getattr(capability, "annual_cost", None),  # model-safety-ok
                        "annual_revenue_impact": getattr(capability, "annual_revenue_impact", None),  # model-safety-ok
                        "status": getattr(capability, "status", "defined"),  # model-safety-ok
                        "is_mapped": app_mapped,
                        "mapping_count": app_mapping_count,
                        "applications": app_applications,  # Include actual application data
                        "application_name": app_applications[0]["name"]
                        if app_applications
                        else "No Application Mapped",
                        "application_type": app_applications[0]["type"]
                        if app_applications
                        else "Application Capability",
                        "coverage_percentage": 100 if app_mapped else 0,
                    }
                )
            except Exception as e:
                # Skip problematic capability
                current_app.logger.warning(
                    "Skipping capability during unified capability build capability_id=%s route=%s: %s",
                    getattr(capability, "id", None),  # model-safety-ok
                    request.path,
                    e,
                    exc_info=True,
                )
                continue

        # Add manufacturing capabilities if available
        for capability in mfg_capabilities:
            try:
                # Calculate business impact for manufacturing
                mfg_business_impact = 0
                if hasattr(capability, "strategic_importance"):  # model-safety-ok
                    if capability.strategic_importance == "critical":
                        mfg_business_impact += 40
                    elif capability.strategic_importance == "high":
                        mfg_business_impact += 30
                    elif capability.strategic_importance == "medium":
                        mfg_business_impact += 20

                if (
                    hasattr(capability, "is_core_manufacturing")  # model-safety-ok
                    and capability.is_core_manufacturing
                ):
                    mfg_business_impact += 30

                # Get unified capability ID - prefer relationship, fallback to direct field
                unified_cap_id = None
                if hasattr(capability, "unified_capability") and capability.unified_capability:  # model-safety-ok
                    unified_cap_id = capability.unified_capability.id
                elif hasattr(capability, "unified_capability_id"):  # model-safety-ok
                    unified_cap_id = capability.unified_capability_id
                else:
                    # This shouldn't happen as unified_capability_id is not nullable, but handle it
                    current_app.logger.warning(
                        f"Manufacturing capability {capability.id} has no unified_capability_id"
                    )
                    continue  # Skip this capability

                # Check if manufacturing capability has application mappings
                mfg_mapped = unified_cap_id in mapped_app_cap_ids
                mfg_mapping_count = len(
                    [m for m in app_mappings if m.unified_capability_id == unified_cap_id]
                )

                # Get application names for manufacturing capability
                mfg_applications = []
                if mfg_mapped:
                    for mapping in app_mappings:
                        if mapping.unified_capability_id == unified_cap_id:
                            app_comp = ApplicationComponent.query.get(
                                mapping.application_component_id
                            )
                            if app_comp:
                                mfg_applications.append(
                                    {
                                        "name": app_comp.name,
                                        "type": getattr(app_comp, "component_type", "Application"),  # model-safety-ok
                                        "id": str(
                                            app_comp.id
                                        ),  # Convert to string to preserve precision
                                    }
                                )

                # Get unified capability details - try relationship first, then query if needed
                unified_cap = None
                if hasattr(capability, "unified_capability") and capability.unified_capability:  # model-safety-ok
                    unified_cap = capability.unified_capability
                else:
                    # Query the unified capability directly
                    unified_cap = UnifiedCapability.query.get(unified_cap_id)

                unified_capabilities.append(
                    {
                        "id": str(
                            unified_cap_id
                        ),  # Convert to string to preserve precision - always use unified capability ID
                        "name": unified_cap.name
                        if unified_cap
                        else f"Manufacturing Process {capability.id}",
                        "code": unified_cap.code if unified_cap else f"MFG-{capability.id}",
                        "type": "Manufacturing",
                        "level": unified_cap.level
                        if unified_cap
                        else getattr(capability, "level", 1),  # model-safety-ok
                        "category": getattr(capability, "manufacturing_domain", "manufacturing"),  # model-safety-ok
                        "domain": {
                            "id": None,
                            "name": getattr(capability, "manufacturing_domain", "Manufacturing"),  # model-safety-ok
                            "code": "MFG",
                        },
                        "business_owner": getattr(
                            capability.unified_capability, "business_owner", "Manufacturing Lead"
                        )
                        if capability.unified_capability
                        else "Manufacturing Lead",
                        "strategic_importance": getattr(
                            capability.unified_capability, "strategic_importance", "medium"
                        )
                        if capability.unified_capability
                        else "medium",
                        "business_criticality": getattr(
                            capability.unified_capability, "business_criticality", "supporting"
                        )
                        if capability.unified_capability
                        else "supporting",
                        "is_core_differentiator": getattr(
                            capability.unified_capability, "is_core_differentiator", False
                        )
                        if capability.unified_capability
                        else False,
                        "business_impact": min(mfg_business_impact, 100),
                        "current_maturity": getattr(capability, "lean_maturity", 1),  # model-safety-ok
                        "target_maturity": getattr(capability, "lean_maturity", 3),  # model-safety-ok
                        "maturity_gap": 0,
                        "annual_cost": None,
                        "annual_revenue_impact": None,
                        "status": getattr(capability, "status", "defined"),  # model-safety-ok
                        "is_mapped": mfg_mapped,  # Manufacturing capabilities can have mappings
                        "mapping_count": mfg_mapping_count,
                        "applications": mfg_applications,  # Include actual application data
                        "application_name": mfg_applications[0]["name"]
                        if mfg_applications
                        else "No Application Mapped",
                        "application_type": mfg_applications[0]["type"]
                        if mfg_applications
                        else "Manufacturing Capability",
                        "coverage_percentage": 100 if mfg_mapped else 0,
                    }
                )
            except Exception as e:
                # Skip problematic manufacturing capability
                continue

        # Sort by business impact (highest first)
        unified_capabilities.sort(key=lambda x: x["business_impact"], reverse=True)

        # Calculate statistics
        total_capabilities = len(unified_capabilities)
        application_capabilities = len(
            [c for c in unified_capabilities if c["type"] == "Application"]
        )
        manufacturing_capabilities = len(
            [c for c in unified_capabilities if c["type"] == "Manufacturing"]
        )
        mapped_capabilities = len([c for c in unified_capabilities if c["is_mapped"]])
        unmapped_capabilities = total_capabilities - mapped_capabilities

        # Domain distribution
        domain_stats = {}
        for capability in unified_capabilities:
            domain_key = capability["domain"]["code"]
            if domain_key not in domain_stats:
                domain_stats[domain_key] = {
                    "name": capability["domain"]["name"],
                    "count": 0,
                    "mapped": 0,
                    "avg_impact": 0,
                }
            domain_stats[domain_key]["count"] += 1
            if capability["is_mapped"]:
                domain_stats[domain_key]["mapped"] += 1
            domain_stats[domain_key]["avg_impact"] += capability["business_impact"]

        # Calculate averages
        for domain in domain_stats.values():
            domain["avg_impact"] = round(domain["avg_impact"] / domain["count"], 1)
            domain["coverage"] = round((domain["mapped"] / domain["count"]) * 100, 1)

        return jsonify(
            {
                "unified_capabilities": unified_capabilities,
                "statistics": {
                    "total_capabilities": total_capabilities,
                    "application_capabilities": application_capabilities,
                    "manufacturing_capabilities": manufacturing_capabilities,
                    "mapped_capabilities": mapped_capabilities,
                    "unmapped_capabilities": unmapped_capabilities,
                    "coverage_percentage": round(
                        (mapped_capabilities / total_capabilities) * 100, 2
                    )
                    if total_capabilities > 0
                    else 0,
                    "domain_distribution": domain_stats,
                },
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "error": str(e),
                    "unified_capabilities": [],
                    "statistics": {
                        "total_capabilities": 0,
                        "application_capabilities": 0,
                        "manufacturing_capabilities": 0,
                        "mapped_capabilities": 0,
                        "unmapped_capabilities": 0,
                        "coverage_percentage": 0,
                        "domain_distribution": {},
                    },
                }
            ),
            500,
        )


@capability_map.route("/api/mappings")
@login_required
def api_mappings():
    """API endpoint to get application-capability mappings with gap analysis and filtering"""
    try:
        from app.models.application_layer import ApplicationComponent
        from app.models.business_capabilities import BusinessCapability
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )
        from app.models.unified_capability import BusinessDomain, UnifiedCapability

        # Get filter parameters
        domain_filter = request.args.get("domain", "")
        level_filter = request.args.get("level", "")

        # Get all mappings with rich data
        mappings = UnifiedApplicationCapabilityMapping.query.limit(10000).all()

        # Build enhanced mapping data
        mapping_data = []
        for mapping in mappings:
            # Get capability details
            capability = UnifiedCapability.query.get(mapping.unified_capability_id)
            domain = (
                BusinessDomain.query.get(capability.domain_id)
                if capability and capability.domain_id
                else None
            )

            # Get application details
            application = ApplicationComponent.query.get(mapping.application_component_id)

            if capability and application:
                # Apply filters
                if domain_filter and domain and domain.code != domain_filter:
                    continue
                if level_filter and str(capability.level) != level_filter:
                    continue

                # Use application business owner instead of capability business owner
                business_owner = (
                    application.app_business_owner or capability.business_owner or "Unassigned"
                )

                # Calculate business impact based on real application data
                business_impact = 0

                # Use application weight if available
                if application.application_weight:
                    if application.application_weight >= 8:
                        business_impact += 40
                    elif application.application_weight >= 6:
                        business_impact += 30
                    elif application.application_weight >= 4:
                        business_impact += 20
                    else:
                        business_impact += 10

                # Use application risk level for impact
                if hasattr(application, "risk_level") and application.risk_level:  # model-safety-ok
                    if application.risk_level.lower() == "critical":
                        business_impact += 30
                    elif application.risk_level.lower() == "high":
                        business_impact += 20
                    elif application.risk_level.lower() == "medium":
                        business_impact += 10

                # Use capability strategic importance
                if capability.strategic_importance == "critical":
                    business_impact += 30
                elif capability.strategic_importance == "high":
                    business_impact += 20
                elif capability.strategic_importance == "medium":
                    business_impact += 10

                # Core differentiator bonus
                if capability.is_core_differentiator:
                    business_impact += 20

                # Cap at 100
                business_impact = min(business_impact, 100)

                mapping_data.append(
                    {
                        "id": str(mapping.id),  # Convert to string to preserve precision
                        "capability_id": str(
                            capability.id
                        ),  # Convert to string to preserve precision
                        "capability_name": capability.name,
                        "capability_code": capability.code,
                        "capability_level": capability.level,
                        "application_id": str(
                            application.id
                        ),  # Convert to string to preserve precision
                        "application_name": application.name,
                        "application_type": application.component_type,
                        "support_level": mapping.support_level or "Primary",
                        "coverage_percentage": mapping.coverage_percentage or 80,
                        "domain": {
                            "id": str(domain.id)
                            if domain and domain.id
                            else None,  # Convert to string to preserve precision
                            "name": domain.name if domain else "Unknown",
                            "code": domain.code if domain else "UNK",
                        },
                        # Use real application business owner
                        "business_owner": business_owner,
                        "capability_owner": capability.capability_owner,
                        "strategic_importance": capability.strategic_importance or "medium",
                        "business_criticality": capability.business_criticality or "supporting",
                        "is_core_differentiator": capability.is_core_differentiator,
                        "business_impact": business_impact,
                        "current_maturity": capability.current_maturity_level or 1,
                        "target_maturity": capability.target_maturity_level or 3,
                        "maturity_gap": capability.maturity_gap or 0,
                        "annual_cost": capability.annual_cost,
                        "annual_revenue_impact": capability.annual_revenue_impact,
                        "status": capability.status or "defined",
                        # Application-specific data
                        "application_weight": application.application_weight,
                        "risk_level": getattr(application, "risk_level", "Unknown"),  # model-safety-ok
                        "priority_for_action": getattr(
                            application, "priority_for_action", "Medium"
                        ),
                    }
                )

        # Sort by business impact (highest first)
        mapping_data.sort(key=lambda x: x["business_impact"], reverse=True)

        # Gap analysis with filters
        all_capabilities = UnifiedCapability.query.limit(2000).all()
        mapped_capability_ids = {mapping.unified_capability_id for mapping in mappings}
        unmapped_capabilities = [
            cap for cap in all_capabilities if cap.id not in mapped_capability_ids
        ]

        # Apply filters to unmapped capabilities
        filtered_unmapped = []
        for capability in unmapped_capabilities:
            domain = (
                BusinessDomain.query.get(capability.domain_id) if capability.domain_id else None
            )

            # Apply filters
            if domain_filter and domain and domain.code != domain_filter:
                continue
            if level_filter and str(capability.level) != level_filter:
                continue

            filtered_unmapped.append(capability)

        # Enhanced gap analysis with business priority
        gap_analysis_data = []
        for capability in filtered_unmapped:
            domain = (
                BusinessDomain.query.get(capability.domain_id) if capability.domain_id else None
            )

            # Calculate business priority for unmapped capabilities
            business_priority = "Low"
            business_impact = 0

            if (
                capability.strategic_importance == "critical"
                or capability.business_criticality == "mission_critical"
            ):
                business_priority = "Critical"
                business_impact = 80
            elif (
                capability.strategic_importance == "high"
                or capability.business_criticality == "important"
            ):
                business_priority = "High"
                business_impact = 60
            elif capability.strategic_importance == "medium":
                business_priority = "Medium"
                business_impact = 40
            else:
                business_priority = "Low"
                business_impact = 20

            if capability.is_core_differentiator:
                business_priority = (
                    "Critical" if business_priority != "Critical" else business_priority
                )
                business_impact += 20

            gap_analysis_data.append(
                {
                    "id": str(capability.id),  # Convert to string to preserve precision
                    "name": capability.name,
                    "code": capability.code,
                    "level": capability.level,
                    "domain": {
                        "id": str(domain.id)
                        if domain and domain.id
                        else None,  # Convert to string to preserve precision
                        "name": domain.name if domain else "Unknown",
                        "code": domain.code if domain else "UNK",
                    },
                    "business_owner": capability.business_owner or "Unassigned",
                    "business_priority": business_priority,
                    "business_impact": business_impact,
                    "current_maturity": capability.current_maturity_level or 1,
                    "target_maturity": capability.target_maturity_level or 3,
                    "maturity_gap": capability.maturity_gap or 0,
                    "is_core_differentiator": capability.is_core_differentiator,
                    "annual_revenue_impact": capability.annual_revenue_impact,
                }
            )

        # Sort gaps by business impact
        gap_analysis_data.sort(key=lambda x: x["business_impact"], reverse=True)

        # Calculate gap statistics
        critical_gaps = len(
            [gap for gap in gap_analysis_data if gap["business_priority"] == "Critical"]
        )
        high_priority_gaps = len(
            [gap for gap in gap_analysis_data if gap["business_priority"] == "High"]
        )
        core_differentiator_gaps = len(
            [gap for gap in gap_analysis_data if gap["is_core_differentiator"]]
        )
        total_business_impact = sum(gap["business_impact"] for gap in gap_analysis_data)

        # Get available domains for filter options
        all_domains = BusinessDomain.query.limit(200).all()
        domain_options = [{"code": d.code, "name": d.name} for d in all_domains]

        return jsonify(
            {
                "mappings": mapping_data,
                "gap_analysis": {
                    "total_capabilities": len(all_capabilities),
                    "mapped_capabilities": len(mapped_capability_ids),
                    "gap_count": len(filtered_unmapped),
                    "coverage_percentage": round(
                        (len(mapped_capability_ids) / len(all_capabilities)) * 100, 2
                    )
                    if all_capabilities
                    else 0,
                    "unmapped_capabilities": gap_analysis_data,
                    "critical_gaps": critical_gaps,
                    "high_priority_gaps": high_priority_gaps,
                    "core_differentiator_gaps": core_differentiator_gaps,
                    "total_business_impact": total_business_impact,
                },
                "filters": {
                    "applied_domain": domain_filter,
                    "applied_level": level_filter,
                    "domain_options": domain_options,
                    "level_options": ["1", "2", "3"],
                },
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/suggest-mapping/<int:app_id>")
@login_required
def api_suggest_mapping(app_id):
    """API endpoint to get AI-suggested capability mappings for an application"""
    try:
        from app.services.application_capability_mapper import ApplicationCapabilityMapperService

        suggestions = ApplicationCapabilityMapperService.suggest_capabilities_for_application(
            application_id=app_id, top_n=5
        )
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/capability/<capability_id>/applications", methods=["GET"])
@login_required
def api_capability_applications(capability_id):
    """API endpoint to get all applications (mapped and unmapped) for a specific capability"""
    try:
        from app.models.application_layer import ApplicationComponent
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )
        from app.models.unified_capability import UnifiedCapability

        # Convert capability_id to string first, then to int (handles large Snowflake IDs)
        # This ensures we preserve precision from JavaScript which may send IDs as strings
        try:
            capability_id_str = str(capability_id).strip()
            capability_id_int = int(capability_id_str)
        except (ValueError, TypeError):
            current_app.logger.error(f"Invalid capability ID format: {capability_id}")
            return jsonify({"error": f"Invalid capability ID format: {capability_id}"}), 400

        # Verify capability exists - handle large Snowflake IDs
        # SQLAlchemy can have issues with very large integers, so we use multiple approaches
        from sqlalchemy import text

        capability = None

        # Single query for all capabilities — shared across all fallback methods below.
        # Queried once here; subsequent methods reuse _all_caps() to avoid N full-table scans.
        _all_caps_cache = None

        def _all_caps():
            nonlocal _all_caps_cache
            if _all_caps_cache is None:
                _all_caps_cache = UnifiedCapability.query.limit(2000).all()
            return _all_caps_cache

        # Method 1: Query all and filter in Python (most reliable for large IDs)
        # This is the most reliable method since we know capabilities exist when querying all
        try:
            all_caps = _all_caps()
            current_app.logger.debug(
                f"Queried {len(all_caps)} total capabilities, looking for ID: {capability_id_str} (original: {capability_id}, int: {capability_id_int})"
            )

            # Try multiple comparison methods to handle type mismatches and precision issues
            for cap in all_caps:
                cap_id_str = str(cap.id)
                cap_id_int = int(cap.id) if isinstance(cap.id, (int, str)) else None

                # Method 1: String comparison (most reliable for preserving precision)
                if cap_id_str == capability_id_str:
                    capability = cap
                    current_app.logger.debug(
                        f"Found capability using string comparison: {capability.name}"
                    )
                    break

                # Method 2: Integer comparison (if both can be converted)
                if cap_id_int is not None and cap_id_int == capability_id_int:
                    capability = cap
                    current_app.logger.debug(
                        f"Found capability using integer comparison: {capability.name}"
                    )
                    break

                # Method 3: Direct object comparison
                if cap.id == capability_id_int:
                    capability = cap
                    current_app.logger.debug(
                        f"Found capability using direct comparison: {capability.name}"
                    )
                    break

            if not capability:
                # Log first few IDs for debugging
                sample_ids = [(str(cap.id), type(cap.id).__name__) for cap in all_caps[:5]]
                current_app.logger.warning(
                    f"Capability ID {capability_id_str} not found. Sample IDs: {sample_ids}"
                )
        except Exception as e:
            current_app.logger.error(f"Python filter failed: {e}", exc_info=True)

        # Method 2: Try direct filter with integer (faster if it works)
        if not capability:
            try:
                capability = UnifiedCapability.query.filter(
                    UnifiedCapability.id == capability_id_int
                ).first()
                if capability:
                    current_app.logger.debug(
                        f"Found capability using direct filter: {capability.name}"
                    )
            except Exception as e:
                current_app.logger.debug(f"Direct filter failed: {e}")

        # Method 3: Try finding via mappings relationship (if capability has mappings)
        if not capability:
            try:
                # Check if any mappings exist for this capability ID
                mapping = UnifiedApplicationCapabilityMapping.query.filter_by(
                    unified_capability_id=capability_id_int
                ).first()
                if mapping:
                    # Try to get capability through relationship
                    if hasattr(mapping, "unified_capability") and mapping.unified_capability:  # model-safety-ok
                        capability = mapping.unified_capability
                        current_app.logger.debug(
                            f"Found capability via mapping relationship: {capability.name}"
                        )
                    else:
                        # If relationship doesn't work, find by the ID from mapping
                        all_caps = _all_caps()
                        capability = next(
                            (cap for cap in all_caps if cap.id == mapping.unified_capability_id),
                            None,
                        )
                        if capability:
                            current_app.logger.debug(
                                f"Found capability via mapping ID: {capability.name}"
                            )
            except Exception as e:
                current_app.logger.debug(f"Mapping lookup failed: {e}")

        # Method 4: Try raw SQL as last resort
        if not capability:
            try:
                result = db.session.execute(  # tenant-filtered: scoped via PK
                    text("SELECT id, name FROM unified_capabilities WHERE id = :cap_id"),
                    {"cap_id": capability_id_int},
                ).first()
                if result:
                    found_id = result[0]
                    all_caps = _all_caps()
                    capability = next((cap for cap in all_caps if cap.id == found_id), None)
                    if capability:
                        current_app.logger.debug(f"Found capability via raw SQL: {capability.name}")
            except Exception as e:
                current_app.logger.debug(f"Raw SQL failed: {e}")

        # Method 5: Check if it's a manufacturing capability ID and get the unified capability
        if not capability:
            try:
                from app.models.manufacturing_capability import ManufacturingCapability

                mfg_cap = ManufacturingCapability.query.filter_by(id=capability_id_int).first()
                if mfg_cap:
                    # Get the unified capability ID (either from relationship or direct field)
                    unified_cap_id = None
                    if hasattr(mfg_cap, "unified_capability") and mfg_cap.unified_capability:
                        unified_cap_id = mfg_cap.unified_capability.id
                    elif hasattr(mfg_cap, "unified_capability_id"):
                        unified_cap_id = mfg_cap.unified_capability_id

                    if unified_cap_id:
                        all_caps = _all_caps()
                        capability = next(
                            (
                                cap
                                for cap in all_caps
                                if str(cap.id) == str(unified_cap_id) or cap.id == unified_cap_id
                            ),
                            None,
                        )
                        if capability:
                            current_app.logger.debug(
                                f"Found capability via manufacturing capability: {capability.name} (mfg_id: {capability_id_int}, unified_id: {unified_cap_id})"
                            )
            except Exception as e:
                current_app.logger.debug(f"Manufacturing capability lookup failed: {e}")

        if not capability:
            current_app.logger.warning(
                f"Capability not found: {capability_id_int} (original: {capability_id})"
            )
            # Try to provide helpful error message
            try:
                all_caps = _all_caps()
                if all_caps:
                    sample_ids = [str(cap.id) for cap in all_caps[:3]]
                    current_app.logger.info(f"Available capability IDs (sample): {sample_ids}")
            except Exception as e:
                current_app.logger.warning(
                    "Failed to collect sample capability IDs route=%s method=%s capability_id=%s: %s",
                    request.path,
                    request.method,
                    capability_id,
                    e,
                    exc_info=True,
                )
            return jsonify({"error": f"Capability not found: {capability_id}"}), 404

        # Get all applications
        all_applications = ApplicationComponent.query.order_by(ApplicationComponent.name).all()

        # Get existing mappings for this capability
        existing_mappings = UnifiedApplicationCapabilityMapping.query.filter_by(
            unified_capability_id=capability_id_int
        ).all()

        mapped_app_ids = {m.application_component_id for m in existing_mappings}
        mapping_details = {m.application_component_id: m for m in existing_mappings}

        # Build application list with mapping status
        applications_data = []
        for app in all_applications:
            is_mapped = app.id in mapped_app_ids
            mapping = mapping_details.get(app.id)

            app_data = {
                "id": str(app.id),  # Convert to string to preserve precision
                "name": app.name,
                "type": app.component_type or "Unknown",
                "description": app.description or "",
                "domain": app.business_domain or "Not specified",
                "owner": app.app_business_owner or "Not specified",
                "is_mapped": is_mapped,
                "mapping_id": str(mapping.id)
                if mapping and mapping.id
                else None,  # Convert to string to preserve precision
                "support_level": mapping.support_level if mapping else "partial",
                "coverage_percentage": mapping.coverage_percentage if mapping else 0,
                "support_quality": mapping.support_quality if mapping else 3,
                "relationship_type": mapping.relationship_type if mapping else "enables",
                "relationship_strength": mapping.relationship_strength if mapping else 3,
                "dependency_level": mapping.dependency_level if mapping else "medium",
                "gap_status": mapping.gap_status if mapping else "unknown",
                "gap_description": mapping.gap_description if mapping else "",
                "gap_impact": mapping.gap_impact if mapping else "medium",
                "priority": mapping.priority if mapping else "medium",
                "integration_complexity": mapping.integration_complexity if mapping else "medium",
                "is_active": mapping.is_active if mapping else True,
            }
            applications_data.append(app_data)

            return jsonify(
                {
                    "capability": {
                        "id": str(capability.id),  # Convert to string to preserve precision
                        "name": capability.name,
                        "code": capability.code,
                        "level": capability.level,
                    },
                    "applications": applications_data,
                    "mapped_count": len(mapped_app_ids),
                    "total_count": len(applications_data),
                }
            )
    except Exception as e:
        current_app.logger.error(f"Error getting capability applications: {str(e)}")
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/mappings", methods=["POST"])
@login_required
def api_create_mapping():
    """API endpoint to create or update application-capability mappings"""
    try:
        from app.models.application_layer import ApplicationComponent
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )
        from app.models.unified_capability import UnifiedCapability

        data = request.get_json()
        capability_id = data.get("capability_id")
        applications = data.get("applications", [])  # List of {app_id, mapping_data}

        if not capability_id:
            return jsonify({"error": "capability_id is required"}), 400

        # Verify capability exists
        capability = UnifiedCapability.query.get(capability_id)
        if not capability:
            return jsonify({"error": "Capability not found"}), 404

        created_count = 0
        updated_count = 0
        errors = []

        for app_data in applications:
            app_id = app_data.get("application_id")
            mapping_id = app_data.get("mapping_id")  # For updates
            mapping_fields = app_data.get("mapping", {})

            if not app_id:
                errors.append("Missing application_id in application data")
                continue

            # Verify application exists
            application = ApplicationComponent.query.get(app_id)
            if not application:
                errors.append(f"Application {app_id} not found")
                continue

            # Check if mapping already exists
            existing = None
            if mapping_id:
                existing = UnifiedApplicationCapabilityMapping.query.get(mapping_id)
                if existing and existing.unified_capability_id != capability_id:
                    existing = None  # Wrong mapping, create new

            if not existing:
                existing = UnifiedApplicationCapabilityMapping.query.filter_by(  # model-safety-ok
                    unified_capability_id=capability_id, application_component_id=app_id
                ).first()

            if existing:
                # Update existing mapping
                for key, value in mapping_fields.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # Create new mapping
                mapping = UnifiedApplicationCapabilityMapping(
                    unified_capability_id=capability_id,
                    application_component_id=app_id,
                    support_level=mapping_fields.get("support_level", "partial"),
                    coverage_percentage=mapping_fields.get("coverage_percentage", 0),
                    support_quality=mapping_fields.get("support_quality", 3),
                    relationship_type=mapping_fields.get("relationship_type", "enables"),
                    relationship_strength=mapping_fields.get("relationship_strength", 3),
                    dependency_level=mapping_fields.get("dependency_level", "medium"),
                    gap_status=mapping_fields.get("gap_status", "unknown"),
                    gap_description=mapping_fields.get("gap_description", ""),
                    gap_impact=mapping_fields.get("gap_impact", "medium"),
                    priority=mapping_fields.get("priority", "medium"),
                    integration_complexity=mapping_fields.get("integration_complexity", "medium"),
                    is_active=mapping_fields.get("is_active", True),
                )
                db.session.add(mapping)
                created_count += 1

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "created": created_count,
                "updated": updated_count,
                "errors": errors if errors else None,
            }
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating/updating mappings: {str(e)}")
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/mappings/<int:mapping_id>", methods=["DELETE"])
@login_required
def api_delete_mapping(mapping_id):
    """API endpoint to delete an application-capability mapping"""
    try:
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )

        mapping = UnifiedApplicationCapabilityMapping.query.get(mapping_id)
        if not mapping:
            return jsonify({"error": "Mapping not found"}), 404

        capability_id = mapping.unified_capability_id
        application_id = mapping.application_component_id

        db.session.delete(mapping)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Mapping deleted successfully",
                "capability_id": capability_id,
                "application_id": application_id,
            }
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting mapping: {str(e)}")
        return jsonify({"error": str(e)}), 500


@capability_map.route("/simple")
@login_required
def simple_view():
    """Simple static view of capabilities (no API dependencies)"""
    return render_template("capability_map/simple.html")


@capability_map.route("/dashboard")
@login_required
def dashboard():
    """Comprehensive dashboard with multiple visualization types"""
    try:
        # Get statistics
        from app.services.application_capability_catalog import ApplicationCapabilityCatalogService

        validation = ApplicationCapabilityCatalogService.validate_capability_structure()
        catalog = ApplicationCapabilityCatalogService.get_catalog_hierarchy()

        # Get application statistics
        from app.models.application_layer import ApplicationComponent

        applications = ApplicationComponent.query.count()
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )

        mappings = UnifiedApplicationCapabilityMapping.query.count()

        return render_template(
            "capability_management/governance_dashboard.html",
            catalog=catalog,
            validation=validation,
            app_count=applications,
            mapping_count=mappings,
        )
    except Exception as e:
        return render_template("capability_map/error.html", error=str(e))


@capability_map.route("/api/manufacturing-capabilities")
@login_required
def api_manufacturing_capabilities():
    """API endpoint for manufacturing capability data"""
    try:
        from app.models.manufacturing_capability import ManufacturingCapability

        manufacturing_caps = ManufacturingCapability.query.limit(2000).all()

        manufacturing_data = []
        for cap in manufacturing_caps:
            # Get the capability name from the unified capability relationship
            capability_name = (
                cap.unified_capability.name if cap.unified_capability else f"Capability {cap.id}"
            )

            manufacturing_data.append(
                {
                    "id": cap.id,
                    "name": capability_name,
                    "description": cap.unified_capability.description
                    if cap.unified_capability
                    else "No description",
                    "manufacturing_domain": cap.manufacturing_domain,
                    "process_type": cap.manufacturing_process_type,
                    "oee_current": cap.oee_current or 0,
                    "oee_target": cap.oee_target or 0,
                    "first_pass_yield_current": cap.first_pass_yield_current or 0,
                    "first_pass_yield_target": cap.first_pass_yield_target or 0,
                    "on_time_delivery_current": cap.on_time_delivery_current or 0,
                    "on_time_delivery_target": cap.on_time_delivery_target or 0,
                    "inventory_turns_current": cap.inventory_turns_current or 0,
                    "inventory_turns_target": cap.inventory_turns_target or 0,
                }
            )

        # Calculate averages
        if manufacturing_data:
            avg_oee = sum(cap["oee_current"] for cap in manufacturing_data) / len(
                manufacturing_data
            )
            avg_fpy = sum(cap["first_pass_yield_current"] for cap in manufacturing_data) / len(
                manufacturing_data
            )
            avg_otd = sum(cap["on_time_delivery_current"] for cap in manufacturing_data) / len(
                manufacturing_data
            )
        else:
            avg_oee = avg_fpy = avg_otd = 0

        return jsonify(
            {
                "success": True,
                "data": manufacturing_data,
                "stats": {
                    "total_capabilities": len(manufacturing_data),
                    "avg_oee": round(avg_oee, 1),
                    "avg_fpy": round(avg_fpy, 1),
                    "avg_otd": round(avg_otd, 1),
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@capability_map.route("/api/export-mappings")
@login_required
def api_export_mappings():
    """Export capability mappings and gap analysis to multiple formats"""
    try:
        import csv
        import json
        from datetime import datetime
        from io import StringIO

        from flask import Response

        # Get format parameter
        export_format = request.args.get("format", "csv").lower()

        # Get filter parameters
        domain_filter = request.args.get("domain", "")
        level_filter = request.args.get("level", "")

        # Get mapping data with gap analysis
        from app.models.application_layer import ApplicationComponent
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )
        from app.models.unified_capability import BusinessDomain, UnifiedCapability

        mappings = UnifiedApplicationCapabilityMapping.query.limit(10000).all()
        all_capabilities = UnifiedCapability.query.limit(2000).all()
        all_applications = ApplicationComponent.query.limit(2000).all()

        mapped_capability_ids = {mapping.unified_capability_id for mapping in mappings}

        # Apply filters to capabilities
        filtered_capabilities = []
        for capability in all_capabilities:
            domain = (
                BusinessDomain.query.get(capability.domain_id) if capability.domain_id else None
            )

            # Apply filters
            if domain_filter and domain and domain.code != domain_filter:
                continue
            if level_filter and str(capability.level) != level_filter:
                continue

            filtered_capabilities.append(capability)

        # Apply filters to mappings
        filtered_mappings = []
        for mapping in mappings:
            capability = UnifiedCapability.query.get(mapping.unified_capability_id)
            domain = (
                BusinessDomain.query.get(capability.domain_id)
                if capability and capability.domain_id
                else None
            )

            # Apply filters
            if domain_filter and domain and domain.code != domain_filter:
                continue
            if level_filter and str(capability.level) != level_filter:
                continue

            filtered_mappings.append(mapping)

        if export_format == "csv":
            return _export_csv(
                filtered_capabilities, filtered_mappings, mapped_capability_ids, all_applications
            )
        elif export_format == "json":
            return _export_json(
                filtered_capabilities, filtered_mappings, mapped_capability_ids, all_applications
            )
        elif export_format == "jpg":
            return _export_image(
                filtered_capabilities, filtered_mappings, mapped_capability_ids, "jpg"
            )
        elif export_format == "png":
            return _export_image(
                filtered_capabilities, filtered_mappings, mapped_capability_ids, "png"
            )
        else:
            return jsonify({"error": "Unsupported format. Use csv, json, jpg, or png"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _export_csv(capabilities, mappings, mapped_capability_ids, applications):
    """Export to CSV format"""
    import csv
    from datetime import datetime
    from io import StringIO

    from flask import Response

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "Report Type",
            "Capability ID",
            "Capability Name",
            "Capability Level",
            "Domain",
            "Application ID",
            "Application Name",
            "Support Level",
            "Coverage %",
            "Gap Status",
            "Assessment Notes",
            "Strategic Priority",
        ]
    )

    # Write existing mappings
    for mapping in mappings:
        app = ApplicationComponent.query.get(mapping.application_component_id)
        capability = UnifiedCapability.query.get(mapping.unified_capability_id)

        if app and capability:
            writer.writerow(
                [
                    "MAPPING",
                    capability.id,
                    capability.name,
                    getattr(capability, "level", 1),  # model-safety-ok
                    getattr(capability, "business_domain", "Unknown"),  # model-safety-ok
                    app.id,
                    app.name,
                    mapping.support_level,
                    mapping.coverage_percentage,
                    mapping.gap_status,
                    mapping.assessment_notes,
                    "High" if getattr(capability, "level", 1) == 1 else "Medium",  # model-safety-ok
                ]
            )

    # Write unmapped capabilities (gaps)
    for capability in capabilities:
        if capability.id not in mapped_capability_ids:
            writer.writerow(
                [
                    "GAP",
                    capability.id,
                    capability.name,
                    getattr(capability, "level", 1),  # model-safety-ok
                    getattr(capability, "business_domain", "Unknown"),  # model-safety-ok
                    "",
                    "",
                    "",
                    "0%",
                    "Gap Identified",
                    "Capability needs application support",
                    "High" if getattr(capability, "level", 1) == 1 else "Medium",  # model-safety-ok
                ]
            )

    # Write summary
    writer.writerow([])
    writer.writerow(["SUMMARY METRICS"])
    writer.writerow(["Total Capabilities", len(capabilities)])
    writer.writerow(["Mapped Capabilities", len(mapped_capability_ids)])
    writer.writerow(["Gap Count", len(capabilities) - len(mapped_capability_ids)])
    writer.writerow(["Total Applications", len(applications)])
    writer.writerow(["Total Mappings", len(mappings)])
    writer.writerow([])

    # Create response
    output.seek(0)
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers[
        "Content-Disposition"
    ] = f'attachment; filename=capability_mappings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

    return response


@capability_map.route("/api/apply-suggestion", methods=["POST"])
@login_required
def api_apply_suggestion():
    """API endpoint to apply a capability suggestion to create a mapping"""
    try:
        from app.services.application_capability_mapper import ApplicationCapabilityMapperService

        data = request.get_json()
        application_id = data.get("application_id")
        capability_id = data.get("capability_id")
        support_level = data.get("support_level")
        confidence_score = data.get("confidence_score")
        reasoning = data.get("reasoning")

        if not all([application_id, capability_id]):
            return jsonify({"error": "Missing required fields: application_id, capability_id"}), 400

        # Create mapping from suggestion
        mapping = ApplicationCapabilityMapperService.create_mapping_from_suggestion(
            application_id=int(application_id),
            suggestion={
                "capability_id": int(capability_id),
                "support_level": support_level,
                "confidence_score": float(confidence_score),
                "reasoning": reasoning,
            },
        )

        return jsonify(
            {
                "success": True,
                "mapping": {
                    "id": mapping.id,
                    "application_id": mapping.application_component_id,
                    "capability_id": mapping.unified_capability_id,
                    "support_level": mapping.support_level,
                    "coverage_percentage": mapping.coverage_percentage,
                    "support_quality": mapping.support_quality,
                    "relationship_type": mapping.relationship_type,
                    "gap_status": mapping.gap_status,
                    "gap_description": mapping.gap_description,
                    "gap_impact": mapping.gap_impact,
                    "priority": mapping.priority,
                    "integration_complexity": mapping.integration_complexity,
                    "is_active": mapping.is_active,
                },
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error applying suggestion: {e}")
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/bulk-map-applications", methods=["POST"])
@login_required
def api_bulk_map_applications():
    """API endpoint to bulk map applications to capabilities"""
    try:
        from app.services.application_capability_mapper import ApplicationCapabilityMapperService

        data = request.get_json()
        confidence_threshold = data.get("confidence_threshold", 0.7)
        auto_create = data.get("auto_create", False)

        # Perform bulk mapping
        result = ApplicationCapabilityMapperService.bulk_map_applications(
            confidence_threshold=confidence_threshold, auto_create=auto_create
        )

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error in bulk mapping: {e}")
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/statistics")
@login_required
def api_statistics():
    """API endpoint to get mapping statistics"""
    try:
        from app.models.application_layer import ApplicationComponent
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )

        total_applications = ApplicationComponent.query.count()
        mapped_applications = (
            db.session.query(UnifiedApplicationCapabilityMapping.application_component_id)
            .distinct()
            .count()
        )
        unmapped_applications = total_applications - mapped_applications

        coverage = (mapped_applications / total_applications * 100) if total_applications > 0 else 0

        return jsonify(
            {
                "total_applications": total_applications,
                "mapped_applications": mapped_applications,
                "unmapped_applications": unmapped_applications,
                "coverage_percentage": coverage,
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error getting statistics: {e}")
        return jsonify({"error": str(e)}), 500


def _export_json(capabilities, mappings, mapped_capability_ids, applications):
    """Export to JSON format"""
    from datetime import datetime

    from flask import Response

    # Build JSON structure
    export_data = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "total_capabilities": len(capabilities),
            "mapped_capabilities": len(mapped_capability_ids),
            "gap_count": len(capabilities) - len(mapped_capability_ids),
            "total_applications": len(applications),
            "total_mappings": len(mappings),
        },
        "mappings": [],
        "gaps": [],
    }

    # Add mappings
    for mapping in mappings:
        app = ApplicationComponent.query.get(mapping.application_component_id)
        capability = UnifiedCapability.query.get(mapping.unified_capability_id)

        if app and capability:
            export_data["mappings"].append(
                {
                    "capability_id": capability.id,
                    "capability_name": capability.name,
                    "capability_level": getattr(capability, "level", 1),  # model-safety-ok
                    "application_id": app.id,
                    "application_name": app.name,
                    "support_level": mapping.support_level,
                    "coverage_percentage": mapping.coverage_percentage,
                    "strategic_priority": "High"
                    if getattr(capability, "level", 1) == 1  # model-safety-ok
                    else "Medium",
                }
            )

    # Add gaps
    for capability in capabilities:
        if capability.id not in mapped_capability_ids:
            export_data["gaps"].append(
                {
                    "capability_id": capability.id,
                    "capability_name": capability.name,
                    "capability_level": getattr(capability, "level", 1),  # model-safety-ok
                    "gap_status": "Gap Identified",
                    "strategic_priority": "High"
                    if getattr(capability, "level", 1) == 1  # model-safety-ok
                    else "Medium",
                }
            )

    # Create response
    response = Response(json.dumps(export_data, indent=2), mimetype="application/json")
    response.headers[
        "Content-Disposition"
    ] = f'attachment; filename=capability_mappings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

    return response


def _export_image(capabilities, mappings, mapped_capability_ids, format_type):
    """Export to image format (JPG/PNG)"""
    try:
        from datetime import datetime
        from io import BytesIO

        from flask import Response
        from PIL import Image, ImageDraw, ImageFont

        # Create image
        img_width, img_height = 1200, 800
        img = Image.new("RGB", (img_width, img_height), color="white")
        draw = ImageDraw.Draw(img)

        # Try to use a simple font
        try:
            font_title = ImageFont.truetype("arial.ttf", 24)
            font_header = ImageFont.truetype("arial.ttf", 18)
            font_normal = ImageFont.truetype("arial.ttf", 12)
        except Exception as e:
            current_app.logger.warning(
                "Falling back to default image fonts format=%s: %s",
                format_type,
                e,
                exc_info=True,
            )
            font_title = ImageFont.load_default()
            font_header = ImageFont.load_default()
            font_normal = ImageFont.load_default()

        # Title
        title = f"Capability Mapping Report - {datetime.now().strftime('%Y-%m-%d')}"
        draw.text((50, 30), title, fill="black", font=font_title)

        # Summary section
        y_position = 80
        draw.text((50, y_position), "SUMMARY METRICS", fill="black", font=font_header)
        y_position += 30

        summary_data = [
            f"Total Capabilities: {len(capabilities)}",
            f"Mapped Capabilities: {len(mapped_capability_ids)}",
            f"Gap Count: {len(capabilities) - len(mapped_capability_ids)}",
            f"Total Applications: {ApplicationComponent.query.count()}",
            f"Total Mappings: {len(mappings)}",
            f"Coverage: {round((len(mapped_capability_ids) / len(capabilities)) * 100, 2) if capabilities else 0}%",
        ]

        for metric in summary_data:
            draw.text((70, y_position), metric, fill="black", font=font_normal)
            y_position += 20

        # Mappings section
        y_position += 20
        draw.text(
            (50, y_position), "APPLICATION CAPABILITY MAPPINGS", fill="black", font=font_header
        )
        y_position += 30

        draw.text((70, y_position), "Capability Name", fill="black", font=font_normal)
        draw.text((400, y_position), "Application Name", fill="black", font=font_normal)
        draw.text((700, y_position), "Support Level", fill="black", font=font_normal)
        draw.text((900, y_position), "Coverage", fill="black", font=font_normal)
        y_position += 20

        # Add top 10 mappings
        for i, mapping in enumerate(mappings[:10]):
            if y_position > img_height - 100:
                break

            app = ApplicationComponent.query.get(mapping.application_component_id)
            capability = UnifiedCapability.query.get(mapping.unified_capability_id)

            if app and capability:
                draw.text(
                    (70, y_position),
                    capability.name[:35] + "..." if len(capability.name) > 35 else capability.name,
                    fill="black",
                    font=font_normal,
                )
                draw.text(
                    (400, y_position),
                    app.name[:35] + "..." if len(app.name) > 35 else app.name,
                    fill="black",
                    font=font_normal,
                )
                draw.text(
                    (700, y_position),
                    mapping.support_level or "Primary",
                    fill="black",
                    font=font_normal,
                )
                draw.text(
                    (900, y_position),
                    f"{mapping.coverage_percentage or 80}%",
                    fill="black",
                    font=font_normal,
                )
                y_position += 18

        # Gaps section
        if len(capabilities) - len(mapped_capability_ids) > 0 and y_position < img_height - 150:
            y_position += 20
            draw.text((50, y_position), "CAPABILITY GAPS", fill="black", font=font_header)
            y_position += 30

            draw.text((70, y_position), "Capability Name", fill="black", font=font_normal)
            draw.text((400, y_position), "Level", fill="black", font=font_normal)
            draw.text((500, y_position), "Priority", fill="black", font=font_normal)
            y_position += 20

            # Add top 10 gaps
            gap_count = 0
            for capability in capabilities:
                if capability.id not in mapped_capability_ids and gap_count < 10:
                    if y_position > img_height - 50:
                        break

                    priority = "High" if getattr(capability, "level", 1) == 1 else "Medium"  # model-safety-ok
                    draw.text(
                        (70, y_position),
                        capability.name[:35] + "..."
                        if len(capability.name) > 35
                        else capability.name,
                        fill="black",
                        font=font_normal,
                    )
                    draw.text(
                        (400, y_position),
                        str(getattr(capability, "level", 1)),  # model-safety-ok
                        fill="black",
                        font=font_normal,
                    )
                    draw.text((500, y_position), priority, fill="black", font=font_normal)
                    y_position += 18
                    gap_count += 1

        # Save image to BytesIO
        img_buffer = BytesIO()
        img.save(img_buffer, format=format_type.upper())
        img_buffer.seek(0)

        # Create response
        response = Response(img_buffer.getvalue(), mimetype=f"image/{format_type}")
        response.headers[
            "Content-Disposition"
        ] = f'attachment; filename=capability_mappings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{format_type}'

        return response

    except Exception as e:
        # Fallback to error response if PIL is not available
        return (
            jsonify(
                {
                    "error": "Image export requires PIL/Pillow library. Please install it with: pip install Pillow",
                    "details": str(e),
                }
            ),
            500,
        )


@capability_map.route("/api/process-gaps")
@login_required
def api_process_gaps():
    """
    API endpoint for Process Gap Analysis - identifies processes without application support.

    Uses the Process Classification Framework (APQC-style) to show:
    - Processes without any application support
    - Processes with partial automation
    - Process-to-Application mapping gaps
    """
    try:
        from app.models.application_layer import ApplicationComponent
        from app.models.apqc_process import APQCProcess
        from app.models.process_data import BusinessProcess
        from app.models.relationship_tables import ApplicationProcessSupport

        # Get filter parameters
        level_filter = request.args.get("level", "")
        type_filter = request.args.get("type", "")  # core, support, management
        category_filter = request.args.get("category", "")  # operational, strategic, enabling
        search_filter = request.args.get("search", "").lower()

        # Get all business processes (including those linked to APQC)
        # Temporarily disabled due to missing migration - just use APQC processes
        try:
            all_processes = BusinessProcess.query.limit(2000).all()
            mapped_apqc_ids = {bp.apqc_process_id for bp in all_processes if bp.apqc_process_id}
            unmapped_apqc_processes = APQCProcess.query.filter(
                ~APQCProcess.id.in_(mapped_apqc_ids)
            ).all()
            # Combine: BusinessProcess + unmapped APQC processes
            combined_processes = all_processes + unmapped_apqc_processes
        except Exception as e:
            # Fallback: just use APQC processes
            current_app.logger.warning(f"BusinessProcess query failed, using APQC only: {e}")
            combined_processes = APQCProcess.query.limit(2000).all()

        # Get all process-application mappings
        all_mappings = ApplicationProcessSupport.query.filter_by(is_active=True).all()
        mapped_process_ids = {m.business_process_id for m in all_mappings}

        # Build mapping details for partially mapped processes
        mapping_details = {}
        for m in all_mappings:
            if m.business_process_id not in mapping_details:
                mapping_details[m.business_process_id] = []
            app = ApplicationComponent.query.get(m.application_component_id)
            if app:
                mapping_details[m.business_process_id].append(
                    {
                        "app_id": str(app.id),
                        "app_name": app.name,
                        "support_type": m.support_type,
                        "automation_level": m.automation_level or 0,
                        "criticality": m.criticality,
                    }
                )

        # Build process data with gap analysis
        process_gap_data = []
        for process in combined_processes:
            # Handle different field names for BusinessProcess vs APQCProcess
            if hasattr(process, "name"):  # BusinessProcess  # model-safety-ok
                process_name = process.name
                process_description = process.description
                process_level = process.level
                process_code = process.process_code
                process_owner = process.process_owner
                business_unit = getattr(process, "business_unit", None)  # model-safety-ok
                is_automated = getattr(process, "is_automated", False)  # model-safety-ok
                automation_percentage = getattr(process, "automation_percentage", 0)  # model-safety-ok
                maturity_level = getattr(process, "maturity_level", 1)  # model-safety-ok
                standardization_level = getattr(process, "standardization_level", "ad_hoc")  # model-safety-ok
                digitalization_level = getattr(process, "digitalization_level", "manual")  # model-safety-ok
                sox_relevant = getattr(process, "sox_relevant", False)  # model-safety-ok
                gdpr_relevant = getattr(process, "gdpr_relevant", False)  # model-safety-ok
                cycle_time_hours = getattr(process, "cycle_time_hours", None)  # model-safety-ok
                frequency = getattr(process, "frequency", None)  # model-safety-ok
                value_chain_stage = getattr(process, "value_chain_stage", None)  # model-safety-ok
                status = getattr(process, "status", "active")  # model-safety-ok

                # Get APQC data through relationship if available
                if process.apqc_process:
                    # Use APQC data if available, fallback to BusinessProcess
                    process_name = process.apqc_process.process_name
                    process_description = process.apqc_process.process_description
                    process_code = process.apqc_process.process_code
                    process_type = process.apqc_process.process_type or process.process_type
                    process_category = (
                        process.apqc_process.process_category or process.process_category
                    )
                    process_owner = process.apqc_process.process_owner or process.process_owner
                    maturity_level = process.apqc_process.process_maturity or process.maturity_level
                else:
                    process_type = process.process_type
                    process_category = process.process_category

            else:  # APQCProcess (unmapped APQC processes)
                process_name = process.process_name
                process_description = process.process_description
                # Derive level from process_code (e.g., "1.0" -> level 0, "1.1" -> level 1, "1.1.1" -> level 2)
                if process.process_code:
                    level_parts = process.process_code.split(".")
                    process_level = len(level_parts) - 1
                else:
                    process_level = 2  # Default to Process level
                process_code = process.process_code
                process_type = process.process_type
                process_category = process.process_category
                process_owner = process.process_owner
                business_unit = None
                is_automated = False  # APQC processes don't have this field by default
                automation_percentage = 0
                maturity_level = process.process_maturity or 1
                standardization_level = "ad_hoc"  # Default for APQC
                digitalization_level = "manual"  # Default for APQC
                sox_relevant = False  # APQC processes don't have this by default
                gdpr_relevant = False  # APQC processes don't have this by default
                cycle_time_hours = None
                frequency = None
                value_chain_stage = None
                status = "active"

            # Apply filters
            if level_filter and str(process_level) != level_filter:
                continue
            if type_filter and process.process_type != type_filter:
                continue
            if category_filter and process.process_category != category_filter:
                continue
            if search_filter:
                if (
                    search_filter not in (process_name or "").lower()
                    and search_filter not in (process_code or "").lower()
                    and search_filter not in (process_owner or "").lower()
                ):
                    continue

            is_mapped = process.id in mapped_process_ids
            apps = mapping_details.get(process.id, [])

            # Calculate automation coverage
            total_automation = sum(app.get("automation_level", 0) for app in apps)
            avg_automation = total_automation / len(apps) if apps else 0

            # Determine gap status
            if not is_mapped:
                gap_status = "no_coverage"
                gap_severity = "critical" if process.process_type == "core" else "high"
            elif avg_automation < 30:
                gap_status = "minimal_automation"
                gap_severity = "high"
            elif avg_automation < 70:
                gap_status = "partial_automation"
                gap_severity = "medium"
            else:
                gap_status = "well_automated"
                gap_severity = "low"

            # Calculate business impact based on process attributes
            business_impact = 0
            if process.process_type == "core":
                business_impact += 40
            elif process.process_type == "support":
                business_impact += 20
            elif process.process_type == "management":
                business_impact += 30

            if sox_relevant or gdpr_relevant:
                business_impact += 30

            if maturity_level:
                # Lower maturity = higher impact of gaps
                business_impact += (5 - maturity_level) * 6

            business_impact = min(business_impact, 100)

            process_gap_data.append(
                {
                    "id": str(process.id),
                    "name": process_name,
                    "process_code": process_code,
                    "description": process_description,
                    "level": process_level,  # Use derived level for APQC
                    "level_name": {
                        0: "Value Chain",
                        1: "Process Group",
                        2: "Process",
                        3: "Subprocess",
                        4: "Activity",
                    }.get(process_level, "Process"),
                    "process_type": process.process_type or "unknown",
                    "process_category": process.process_category or "operational",
                    "value_chain_stage": value_chain_stage,
                    "process_owner": process_owner or "Unassigned",
                    "business_unit": business_unit,
                    "is_automated": is_automated,
                    "automation_percentage": automation_percentage,
                    "maturity_level": maturity_level,
                    "standardization_level": standardization_level,
                    "digitalization_level": digitalization_level,
                    "sox_relevant": sox_relevant,
                    "gdpr_relevant": gdpr_relevant,
                    "cycle_time_hours": cycle_time_hours,
                    "frequency": frequency,
                    "is_mapped": is_mapped,
                    "mapping_count": len(apps),
                    "applications": apps,
                    "avg_automation_coverage": round(avg_automation, 1),
                    "gap_status": gap_status,
                    "gap_severity": gap_severity,
                    "business_impact": business_impact,
                    "status": status,
                }
            )

        # Sort by business impact (highest first), then by gap severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        process_gap_data.sort(
            key=lambda x: (-x["business_impact"], severity_order.get(x["gap_severity"], 4))
        )

        # Calculate statistics
        total_processes = len(process_gap_data)
        unmapped_processes = len([p for p in process_gap_data if not p["is_mapped"]])
        partially_automated = len(
            [p for p in process_gap_data if p["gap_status"] == "partial_automation"]
        )
        minimal_automation = len(
            [p for p in process_gap_data if p["gap_status"] == "minimal_automation"]
        )
        well_automated = len([p for p in process_gap_data if p["gap_status"] == "well_automated"])

        critical_gaps = len([p for p in process_gap_data if p["gap_severity"] == "critical"])
        high_gaps = len([p for p in process_gap_data if p["gap_severity"] == "high"])

        # Get unique filter options
        process_types = list(set(p["process_type"] for p in process_gap_data if p["process_type"]))
        process_categories = list(
            set(p["process_category"] for p in process_gap_data if p["process_category"])
        )
        levels = list(set(str(p["level"]) for p in process_gap_data))

        return jsonify(
            {
                "process_gaps": process_gap_data,
                "statistics": {
                    "total_processes": total_processes,
                    "unmapped_processes": unmapped_processes,
                    "partially_automated": partially_automated,
                    "minimal_automation": minimal_automation,
                    "well_automated": well_automated,
                    "coverage_percentage": round(
                        ((total_processes - unmapped_processes) / total_processes) * 100, 2
                    )
                    if total_processes > 0
                    else 0,
                    "automation_coverage": round(
                        sum(p["avg_automation_coverage"] for p in process_gap_data)
                        / total_processes,
                        1,
                    )
                    if total_processes > 0
                    else 0,
                    "critical_gaps": critical_gaps,
                    "high_gaps": high_gaps,
                },
                "filters": {
                    "process_types": process_types,
                    "process_categories": process_categories,
                    "levels": sorted(levels),
                },
            }
        )
    except ImportError as e:
        # Models not available - return empty data gracefully
        current_app.logger.warning(f"Process models not available: {e}")
        return jsonify(
            {
                "process_gaps": [],
                "statistics": {
                    "total_processes": 0,
                    "unmapped_processes": 0,
                    "partially_automated": 0,
                    "minimal_automation": 0,
                    "well_automated": 0,
                    "coverage_percentage": 0,
                    "automation_coverage": 0,
                    "critical_gaps": 0,
                    "high_gaps": 0,
                },
                "filters": {"process_types": [], "process_categories": [], "levels": []},
                "message": "Process models not configured. Please set up BusinessProcess and ApplicationProcessSupport tables.",
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error in process gap analysis: {e}")
        return jsonify({"error": str(e), "process_gaps": [], "statistics": {}}), 500


# =============================================================================
# NEW ENDPOINTS: Capability-Process Integration & Traceability
# =============================================================================


@capability_map.route("/api/capabilities/<capability_id>/processes")
@login_required
def api_capability_processes(capability_id):
    """
    API endpoint to get all processes linked to a capability.

    Returns processes via UnifiedCapabilityProcessMapping → APQCProcess → BusinessProcess chain.
    Includes application support information for each process.
    """
    try:
        from app.models.application_layer import ApplicationComponent
        from app.models.apqc_process import APQCProcess
        from app.models.process_data import BusinessProcess
        from app.models.relationship_tables import ApplicationProcessSupport
        from app.models.unified_capability import UnifiedCapability, UnifiedCapabilityProcessMapping

        # Convert capability_id
        try:
            capability_id_int = int(str(capability_id).strip())
        except (ValueError, TypeError):
            return jsonify({"error": f"Invalid capability ID: {capability_id}"}), 400

        # Find capability
        capability = UnifiedCapability.query.get(capability_id_int)
        if not capability:
            return jsonify({"error": f"Capability not found: {capability_id}"}), 404

        # Get process mappings for this capability
        process_mappings = UnifiedCapabilityProcessMapping.query.filter_by(
            capability_id=capability_id_int
        ).all()

        processes_data = []

        for mapping in process_mappings:
            # Get APQC process
            apqc_process = APQCProcess.query.get(mapping.apqc_process_id)
            if not apqc_process:
                continue

            # Get business processes linked to this APQC process
            business_processes = BusinessProcess.query.filter_by(  # model-safety-ok
                apqc_process_id=apqc_process.id
            ).all()

            # For each business process, get supporting applications
            for bp in business_processes:
                app_supports = ApplicationProcessSupport.query.filter_by(  # model-safety-ok
                    business_process_id=bp.id, is_active=True
                ).all()

                applications = []
                for support in app_supports:
                    app = ApplicationComponent.query.get(support.application_component_id)
                    if app:
                        applications.append(
                            {
                                "id": str(app.id),
                                "name": app.name,
                                "support_type": support.support_type,
                                "automation_level": support.automation_level,
                                "criticality": support.criticality,
                                "is_system_of_record": support.is_system_of_record,
                            }
                        )

                processes_data.append(
                    {
                        "apqc_process": {
                            "id": apqc_process.id,
                            "code": apqc_process.process_code,
                            "name": apqc_process.process_name,
                            "category": apqc_process.process_category,
                            "maturity": apqc_process.process_maturity,
                        },
                        "business_process": {
                            "id": bp.id,
                            "name": bp.name,
                            "process_code": bp.process_code,
                            "level": bp.level,
                            "automation_percentage": bp.automation_percentage,
                            "process_type": bp.process_type,
                        },
                        "mapping": {
                            "relationship_type": mapping.relationship_type,
                            "relationship_strength": mapping.relationship_strength,
                            "impact_level": mapping.impact_level,
                            "process_contribution": mapping.process_contribution,
                        },
                        "applications": applications,
                        "application_count": len(applications),
                        "has_gap": len(applications) == 0,
                    }
                )

        # Calculate statistics
        total_processes = len(processes_data)
        processes_with_apps = len([p for p in processes_data if p["application_count"] > 0])
        processes_with_gaps = len([p for p in processes_data if p["has_gap"]])

        return jsonify(
            {
                "capability": {
                    "id": str(capability.id),
                    "name": capability.name,
                    "code": capability.code,
                },
                "processes": processes_data,
                "statistics": {
                    "total_processes": total_processes,
                    "processes_with_applications": processes_with_apps,
                    "processes_with_gaps": processes_with_gaps,
                    "coverage_percentage": round(
                        (processes_with_apps / total_processes * 100) if total_processes > 0 else 0,
                        1,
                    ),
                },
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error getting capability processes: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/processes/<process_id>/capabilities")
@login_required
def api_process_capabilities(process_id):
    """
    API endpoint to get all capabilities that a process enables/supports.

    Supports both BusinessProcess IDs and APQCProcess IDs.
    Reverse lookup: Process → APQCProcess → UnifiedCapabilityProcessMapping → UnifiedCapability
    """
    try:
        from app.models.apqc_process import APQCProcess
        from app.models.process_data import BusinessProcess
        from app.models.unified_capability import (
            BusinessDomain,
            UnifiedCapability,
            UnifiedCapabilityProcessMapping,
        )

        capabilities_data = []
        process_info = None
        apqc_process = None

        # Try to find as BusinessProcess first
        business_process = BusinessProcess.query.get(process_id)

        if business_process:
            process_info = {
                "id": str(business_process.id),
                "name": business_process.name,
                "process_code": business_process.process_code,
                "level": business_process.level,
                "process_type": business_process.process_type,
                "automation_percentage": business_process.automation_percentage,
                "source": "business_process",
            }
            # If process has APQC mapping, get the APQC process
            if business_process.apqc_process_id:
                apqc_process = APQCProcess.query.get(business_process.apqc_process_id)
        else:
            # Try to find as APQCProcess directly
            apqc_process = APQCProcess.query.get(process_id)
            if apqc_process:
                # Derive level from process_code (e.g., "1.0"=1, "1.1"=2, "1.1.1"=3)
                apqc_level = (
                    len(apqc_process.process_code.split(".")) if apqc_process.process_code else 1
                )
                process_info = {
                    "id": str(apqc_process.id),
                    "name": apqc_process.process_name,
                    "process_code": apqc_process.process_code,
                    "level": apqc_level,
                    "process_type": apqc_process.process_type or "apqc",
                    "automation_percentage": None,
                    "source": "apqc_process",
                }

        if not process_info:
            return jsonify({"error": f"Process not found: {process_id}"}), 404

        # Find capabilities via APQC process mapping
        if apqc_process:
            mappings = UnifiedCapabilityProcessMapping.query.filter_by(
                apqc_process_id=apqc_process.id
            ).all()

            for mapping in mappings:
                capability = UnifiedCapability.query.get(mapping.capability_id)
                if capability:
                    domain = (
                        BusinessDomain.query.get(capability.domain_id)
                        if capability.domain_id
                        else None
                    )

                    capabilities_data.append(
                        {
                            "id": str(capability.id),
                            "name": capability.name,
                            "code": capability.code,
                            "level": capability.level,
                            "domain": {
                                "id": str(domain.id) if domain else None,
                                "name": domain.name if domain else "Unknown",
                                "code": domain.code if domain else "UNK",
                            },
                            "strategic_importance": capability.strategic_importance,
                            "business_criticality": capability.business_criticality,
                            "current_maturity": capability.current_maturity_level,
                            "mapping": {
                                "relationship_type": mapping.relationship_type,
                                "relationship_strength": mapping.relationship_strength,
                                "impact_level": mapping.impact_level,
                                "process_contribution": mapping.process_contribution,
                            },
                        }
                    )

        # Build APQC process info if available
        apqc_info = None
        if apqc_process:
            apqc_level = (
                len(apqc_process.process_code.split(".")) if apqc_process.process_code else 1
            )
            apqc_info = {
                "id": str(apqc_process.id),
                "code": apqc_process.process_code,
                "name": apqc_process.process_name,
                "level": apqc_level,
                "process_type": apqc_process.process_type,
                "category": apqc_process.process_category,
            }

        return jsonify(
            {
                "process": process_info,
                "apqc_process": apqc_info,
                "capabilities": capabilities_data,
                "capability_count": len(capabilities_data),
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error getting process capabilities: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/roadmap/capabilities")
@login_required
def api_roadmap_capabilities():
    """
    API endpoint to get capabilities grouped by roadmap priority.

    Returns capabilities organized for roadmap visualization with timeline data.
    """
    try:
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )
        from app.models.unified_capability import BusinessDomain, UnifiedCapability

        capabilities = UnifiedCapability.query.limit(2000).all()
        mappings = UnifiedApplicationCapabilityMapping.query.limit(10000).all()
        mapped_cap_ids = {m.unified_capability_id for m in mappings}

        # Group by roadmap priority
        roadmap_groups = {
            "immediate": [],  # Priority 1 - Now
            "short_term": [],  # Priority 2 - 3-6 months
            "medium_term": [],  # Priority 3 - 6-12 months
            "long_term": [],  # Priority 4 - 12+ months
            "unplanned": [],  # No priority set
        }

        for cap in capabilities:
            domain = BusinessDomain.query.get(cap.domain_id) if cap.domain_id else None

            # Calculate gap status
            is_mapped = cap.id in mapped_cap_ids
            has_maturity_gap = (cap.maturity_gap or 0) > 0

            # Get investment priority from domain if available
            domain_investment_priority = (
                domain.investment_priority
                if domain and hasattr(domain, "investment_priority")
                else None
            )

            cap_data = {
                "id": str(cap.id),
                "name": cap.name,
                "code": cap.code,
                "level": cap.level,
                "domain": domain.name if domain else "Unknown",
                "domain_code": domain.code if domain else "UNK",
                "strategic_importance": cap.strategic_importance,
                "business_criticality": cap.business_criticality,
                "is_core_differentiator": cap.is_core_differentiator,
                "current_maturity": cap.current_maturity_level,
                "target_maturity": cap.target_maturity_level,
                "maturity_gap": cap.maturity_gap,
                "is_mapped": is_mapped,
                "has_maturity_gap": has_maturity_gap,
                "investment_priority": domain_investment_priority,
                "annual_cost": cap.annual_cost,
                "status": cap.status,
            }

            # Assign to roadmap group based on priority (capability roadmap_priority or domain investment_priority)
            priority = cap.roadmap_priority or domain_investment_priority

            if priority in ["critical", "immediate", "1"]:
                roadmap_groups["immediate"].append(cap_data)
            elif priority in ["high", "short_term", "2"]:
                roadmap_groups["short_term"].append(cap_data)
            elif priority in ["medium", "medium_term", "3"]:
                roadmap_groups["medium_term"].append(cap_data)
            elif priority in ["low", "long_term", "4"]:
                roadmap_groups["long_term"].append(cap_data)
            else:
                roadmap_groups["unplanned"].append(cap_data)

        # Sort each group by strategic importance
        importance_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for group in roadmap_groups.values():
            group.sort(key=lambda x: importance_order.get(x["strategic_importance"], 4))

        # Calculate statistics
        total_capabilities = len(capabilities)
        planned_capabilities = total_capabilities - len(roadmap_groups["unplanned"])

        return jsonify(
            {
                "roadmap": roadmap_groups,
                "statistics": {
                    "total_capabilities": total_capabilities,
                    "planned_capabilities": planned_capabilities,
                    "unplanned_capabilities": len(roadmap_groups["unplanned"]),
                    "planning_coverage": round(
                        (planned_capabilities / total_capabilities * 100)
                        if total_capabilities > 0
                        else 0,
                        1,
                    ),
                    "by_phase": {
                        "immediate": len(roadmap_groups["immediate"]),
                        "short_term": len(roadmap_groups["short_term"]),
                        "medium_term": len(roadmap_groups["medium_term"]),
                        "long_term": len(roadmap_groups["long_term"]),
                    },
                },
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error getting roadmap capabilities: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@capability_map.route("/api/capabilities/<capability_id>/full-traceability")
@login_required
def api_capability_full_traceability(capability_id):
    """
    API endpoint for complete capability traceability chain.

    Returns: Capability → Processes → Applications with full gap analysis.
    This is the comprehensive view showing the complete value chain.
    """
    try:
        from app.models.application_layer import ApplicationComponent
        from app.models.apqc_process import APQCProcess
        from app.models.process_data import BusinessProcess
        from app.models.relationship_tables import ApplicationProcessSupport
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )
        from app.models.unified_capability import (
            BusinessDomain,
            UnifiedCapability,
            UnifiedCapabilityProcessMapping,
        )

        # Convert capability_id
        try:
            capability_id_int = int(str(capability_id).strip())
        except (ValueError, TypeError):
            return jsonify({"error": f"Invalid capability ID: {capability_id}"}), 400

        # Find capability
        capability = UnifiedCapability.query.get(capability_id_int)
        if not capability:
            return jsonify({"error": f"Capability not found: {capability_id}"}), 404

        domain = BusinessDomain.query.get(capability.domain_id) if capability.domain_id else None

        # Get direct application mappings (Application Capability Map)
        direct_app_mappings = UnifiedApplicationCapabilityMapping.query.filter_by(
            unified_capability_id=capability_id_int
        ).all()

        direct_applications = []
        for mapping in direct_app_mappings:
            app = ApplicationComponent.query.get(mapping.application_component_id)
            if app:
                direct_applications.append(
                    {
                        "id": str(app.id),
                        "name": app.name,
                        "component_type": app.component_type,
                        "lifecycle_status": app.lifecycle_status,
                        "business_criticality": app.business_criticality,
                        "mapping": {
                            "coverage_percentage": mapping.coverage_percentage,
                            "support_level": mapping.support_level,
                            "gap_status": mapping.gap_status,
                            "priority": mapping.priority,
                        },
                    }
                )

        # Get process chain: Capability → APQC Process → Business Process → Applications
        process_mappings = UnifiedCapabilityProcessMapping.query.filter_by(
            capability_id=capability_id_int
        ).all()

        process_chain = []
        all_process_apps = set()

        for pm in process_mappings:
            apqc_process = APQCProcess.query.get(pm.apqc_process_id)
            if not apqc_process:
                continue

            # Get business processes for this APQC process
            business_processes = BusinessProcess.query.filter_by(  # model-safety-ok
                apqc_process_id=apqc_process.id
            ).all()

            bp_data = []
            for bp in business_processes:
                # Get applications supporting this process
                app_supports = ApplicationProcessSupport.query.filter_by(  # model-safety-ok
                    business_process_id=bp.id, is_active=True
                ).all()

                apps = []
                for support in app_supports:
                    app = ApplicationComponent.query.get(support.application_component_id)
                    if app:
                        all_process_apps.add(app.id)
                        apps.append(
                            {
                                "id": str(app.id),
                                "name": app.name,
                                "support_type": support.support_type,
                                "automation_level": support.automation_level,
                                "is_system_of_record": support.is_system_of_record,
                            }
                        )

                bp_data.append(
                    {
                        "id": bp.id,
                        "name": bp.name,
                        "process_code": bp.process_code,
                        "automation_percentage": bp.automation_percentage,
                        "applications": apps,
                        "has_gap": len(apps) == 0,
                    }
                )

            process_chain.append(
                {
                    "apqc_process": {
                        "id": apqc_process.id,
                        "code": apqc_process.process_code,
                        "name": apqc_process.process_name,
                    },
                    "mapping": {
                        "relationship_type": pm.relationship_type,
                        "impact_level": pm.impact_level,
                    },
                    "business_processes": bp_data,
                }
            )

        # Gap Analysis
        total_processes = sum(len(pc["business_processes"]) for pc in process_chain)
        processes_with_apps = sum(
            1 for pc in process_chain for bp in pc["business_processes"] if not bp["has_gap"]
        )
        processes_with_gaps = total_processes - processes_with_apps

        # Identify gaps
        gaps = {
            "process_gaps": [
                {
                    "process_name": bp["name"],
                    "process_code": bp["process_code"],
                    "apqc_process": pc["apqc_process"]["name"],
                    "severity": "high" if pc["mapping"]["impact_level"] == "critical" else "medium",
                }
                for pc in process_chain
                for bp in pc["business_processes"]
                if bp["has_gap"]
            ],
            "low_automation": [
                {
                    "process_name": bp["name"],
                    "automation_percentage": bp["automation_percentage"],
                    "recommendation": "Increase automation coverage",
                }
                for pc in process_chain
                for bp in pc["business_processes"]
                if (bp["automation_percentage"] or 0) < 50 and not bp["has_gap"]
            ],
            "non_strategic_apps": [
                app
                for app in direct_applications
                if app.get("lifecycle_status") in ["phase_out", "retire", "end_of_life"]
            ],
        }

        return jsonify(
            {
                "capability": {
                    "id": str(capability.id),
                    "name": capability.name,
                    "code": capability.code,
                    "level": capability.level,
                    "domain": {
                        "name": domain.name if domain else "Unknown",
                        "code": domain.code if domain else "UNK",
                    },
                    "strategic_importance": capability.strategic_importance,
                    "current_maturity": capability.current_maturity_level,
                    "target_maturity": capability.target_maturity_level,
                },
                "direct_applications": direct_applications,
                "process_chain": process_chain,
                "gaps": gaps,
                "statistics": {
                    "direct_application_count": len(direct_applications),
                    "total_processes": total_processes,
                    "processes_with_applications": processes_with_apps,
                    "processes_with_gaps": processes_with_gaps,
                    "process_coverage_percentage": round(
                        (processes_with_apps / total_processes * 100) if total_processes > 0 else 0,
                        1,
                    ),
                    "unique_applications_via_processes": len(all_process_apps),
                    "total_gaps_identified": len(gaps["process_gaps"])
                    + len(gaps["non_strategic_apps"]),
                },
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error getting capability traceability: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def build_nodes_edges(catalog):
    """Build nodes and edges for network visualization"""
    nodes = []
    edges = []
    node_id = 0

    # Add capability nodes
    for capability in catalog:
        nodes.append(
            {
                "id": node_id,
                "name": capability["name"],
                "category": "capability",
                "level": capability.get("level", 1),
                "domain": capability.get("domain", "Unknown"),
                "type": capability.get("type", "capability"),
            }
        )
        node_id += 1

    # Add function nodes
    for capability in catalog:
        if "functions" in capability:
            for function in capability["functions"]:
                nodes.append(
                    {
                        "id": node_id,
                        "name": function["name"],
                        "category": "function",
                        "level": function.get("level", 2),
                        "domain": capability.get("domain", "Unknown"),
                        "type": "function",
                    }
                )
                node_id += 1

    return nodes, edges


@capability_map.route("/api/flow-sankey")
@login_required
def api_flow_sankey():
    """Capability → Application flow as D3 Sankey data.

    Returns nodes across three columns:
      Col 0 — Business Domain (L1 capability grouping, by business_domain field)
      Col 1 — Capability (L2/L3 capability)
      Col 2 — Application

    Links: Domain → Capability (via parent hierarchy) and Capability → Application
    (via application_capability_mapping).

    Compatible with _traceability_sankey.html partial when passed as sankey_api_url.
    """
    from sqlalchemy import text as sa_text

    try:
        # --- Capabilities with their domain grouping ---
        caps_sql = sa_text("""
            SELECT
                c.id,
                c.name,
                c.level,
                c.business_domain,
                c.parent_capability_id
            FROM business_capability c
            WHERE c.level IN (1, 2, 3)
            ORDER BY c.level, c.name
        """)
        caps_rows = db.session.execute(caps_sql).fetchall()

        # --- Capability → Application mappings ---
        mappings_sql = sa_text("""
            SELECT
                acm.business_capability_id,
                ac.id   AS app_id,
                ac.name AS app_name
            FROM application_capability_mapping acm
            JOIN application_components ac ON ac.id = acm.application_component_id
            WHERE ac.name IS NOT NULL
        """)
        mapping_rows = db.session.execute(mappings_sql).fetchall()

        if not mapping_rows:
            return jsonify({"nodes": [], "links": [], "has_code": False,
                            "synthesized": False, "column_labels": []})

        # Build capability lookup
        cap_by_id = {r.id: r for r in caps_rows}

        # Collect only capabilities that have application mappings (or are parents of those)
        mapped_cap_ids = {r.business_capability_id for r in mapping_rows}

        # Walk up to find L1 domain IDs for each mapped capability
        def get_l1_ancestor(cap_id):
            visited = set()
            while cap_id and cap_id not in visited:
                visited.add(cap_id)
                cap = cap_by_id.get(cap_id)
                if cap is None:
                    return None
                if cap.level == 1:
                    return cap_id
                cap_id = cap.parent_capability_id
            return None

        # --- Nodes ---
        nodes = []
        node_index = {}  # 'domain_{id}' | 'cap_{id}' | 'app_{id}' → index

        LAYER_COLORS = {
            "domain": "strategy",
            "capability": "business",
            "application": "application",
        }

        # Collect domains (L1 caps referenced by mapped caps)
        domain_ids = set()
        for cap_id in mapped_cap_ids:
            anc = get_l1_ancestor(cap_id)
            if anc:
                domain_ids.add(anc)

        for cap in caps_rows:
            if cap.level == 1 and cap.id in domain_ids:
                key = f"domain_{cap.id}"
                node_index[key] = len(nodes)
                nodes.append({
                    "id": key,
                    "name": cap.name,
                    "type": "BusinessDomain",
                    "layer": "strategy",
                    "column": 0,
                    "has_spec": False,
                    "has_code": False,
                })

        # Capabilities (L2/L3) that have mappings
        for cap_id in sorted(mapped_cap_ids):
            cap = cap_by_id.get(cap_id)
            if cap is None or cap.level == 1:
                continue
            key = f"cap_{cap_id}"
            if key in node_index:
                continue
            node_index[key] = len(nodes)
            nodes.append({
                "id": key,
                "name": cap.name,
                "type": "BusinessCapability",
                "layer": "business",
                "column": 1,
                "has_spec": False,
                "has_code": False,
            })

        # Applications
        app_seen = {}
        for row in mapping_rows:
            key = f"app_{row.app_id}"
            if key not in node_index:
                node_index[key] = len(nodes)
                app_seen[key] = True
                nodes.append({
                    "id": key,
                    "name": row.app_name,
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "column": 2,
                    "has_spec": False,
                    "has_code": False,
                })

        # --- Links ---
        links = []
        link_seen = set()

        # Domain → Capability links
        for cap_id in mapped_cap_ids:
            cap = cap_by_id.get(cap_id)
            if cap is None or cap.level == 1:
                continue
            anc_id = get_l1_ancestor(cap_id)
            if anc_id is None:
                continue
            src_key = f"domain_{anc_id}"
            tgt_key = f"cap_{cap_id}"
            if src_key not in node_index or tgt_key not in node_index:
                continue
            link_key = (node_index[src_key], node_index[tgt_key])
            if link_key not in link_seen:
                link_seen.add(link_key)
                links.append({"source": node_index[src_key], "target": node_index[tgt_key], "value": 1})

        # Capability → Application links
        for row in mapping_rows:
            cap = cap_by_id.get(row.business_capability_id)
            if cap is None:
                continue
            # L1 caps map directly to app (no middle column) — skip, they're domains
            if cap.level == 1:
                continue
            src_key = f"cap_{row.business_capability_id}"
            tgt_key = f"app_{row.app_id}"
            if src_key not in node_index or tgt_key not in node_index:
                continue
            link_key = (node_index[src_key], node_index[tgt_key])
            if link_key not in link_seen:
                link_seen.add(link_key)
                links.append({"source": node_index[src_key], "target": node_index[tgt_key], "value": 1})

        return jsonify({
            "nodes": nodes,
            "links": links,
            "has_code": False,
            "synthesized": False,
            "column_labels": [
                {"name": "Business Domain"},
                {"name": "Capability"},
                {"name": "Application"},
            ],
        })

    except Exception as e:
        current_app.logger.exception("capability flow sankey error")
        return jsonify({"error": str(e)}), 500
