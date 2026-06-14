"""
ACM technical capability operations within capability map.

Extracted from capability_map_routes.py (lines 3418-4073).
Routes registered on the shared ``capability_map`` blueprint.
"""

from datetime import datetime

from flask import current_app, jsonify, request
from flask_login import login_required

from app.decorators import audit_log
from app.extensions.cache import cached

from app import db

from . import capability_map


# =============================================================================
# ACM Technical Capability Endpoints
# =============================================================================


@capability_map.route("/api/acm/domains")
@login_required
@cached(ttl=300, key_prefix="capability_map:acm_domains")
def api_acm_domains():
    """
    Get ACM technical capability domains with statistics for capability-map Technical tab.

    ---
    tags:
      - ACM
      - Technical Capabilities
    responses:
      200:
        description: List of ACM domains with coverage statistics
    """
    try:
        from app.models.application_portfolio import ApplicationComponent
        from app.models.technical_capability import ACMDomain, TechnicalCapability

        domains_data = []

        # Batch-prefetch all tech capabilities grouped by domain to avoid N+1 queries
        all_tech_caps = TechnicalCapability.query.all()
        tech_caps_by_domain = {}
        for tc in all_tech_caps:
            tech_caps_by_domain.setdefault(tc.acm_domain, []).append(tc)

        # Batch-prefetch application counts per capability via the join table
        from app.models.technical_capability import application_technical_capability_mapping
        from sqlalchemy import func
        tech_cap_app_counts = dict(
            db.session.query(
                application_technical_capability_mapping.c.technical_capability_id,
                func.count(application_technical_capability_mapping.c.application_id),
            ).group_by(application_technical_capability_mapping.c.technical_capability_id).all()
        )

        # Batch-prefetch application counts per ACM domain
        acm_domain_app_counts = dict(
            db.session.query(
                ApplicationComponent.acm_primary_domain,
                func.count(ApplicationComponent.id),
            ).group_by(ApplicationComponent.acm_primary_domain).all()
        )

        for domain in ACMDomain.ALL_DOMAINS:
            # Get capabilities for this domain from prefetched data
            capabilities = tech_caps_by_domain.get(domain, [])

            # Count by level
            l1_count = len([c for c in capabilities if c.level == "L1"])
            l2_count = len([c for c in capabilities if c.level == "L2"])
            l3_count = len([c for c in capabilities if c.level == "L3"])
            l4_count = len([c for c in capabilities if c.level == "L4"])

            # Count mapped capabilities using prefetched counts
            mapped_count = sum(1 for cap in capabilities if tech_cap_app_counts.get(cap.id, 0) > 0)

            # Count applications in this domain using prefetched counts
            apps_in_domain = acm_domain_app_counts.get(domain, 0)

            total = len(capabilities)
            coverage = round((mapped_count / total) * 100, 1) if total > 0 else 0

            domains_data.append(
                {
                    "domain": domain,
                    "name": domain.replace("-", " ").title(),
                    "description": ACMDomain.DOMAIN_DESCRIPTIONS.get(domain, ""),
                    "total_capabilities": total,
                    "mapped_capabilities": mapped_count,
                    "unmapped_capabilities": total - mapped_count,
                    "coverage_percentage": coverage,
                    "applications_count": apps_in_domain,
                    "by_level": {
                        "L1": l1_count,
                        "L2": l2_count,
                        "L3": l3_count,
                        "L4": l4_count,
                    },
                    "status": "covered" if coverage >= 50 else "partial" if coverage > 0 else "gap",
                }
            )

        # Overall statistics
        total_caps = sum(d["total_capabilities"] for d in domains_data)
        mapped_caps = sum(d["mapped_capabilities"] for d in domains_data)

        return jsonify(
            {
                "domains": domains_data,
                "statistics": {
                    "total_domains": len(domains_data),
                    "total_capabilities": total_caps,
                    "mapped_capabilities": mapped_caps,
                    "unmapped_capabilities": total_caps - mapped_caps,
                    "overall_coverage": round((mapped_caps / total_caps) * 100, 1)
                    if total_caps > 0
                    else 0,
                },
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error getting ACM domains: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred", "domains": [], "statistics": {}}), 500


@capability_map.route("/api/acm/capabilities")
@login_required
def api_acm_capabilities():
    """
    Get ACM technical capabilities with application mappings for capability-map.

    ---
    tags:
      - ACM
      - Technical Capabilities
    parameters:
      - name: domain
        in: query
        type: string
        required: false
        description: Filter by ACM domain
      - name: level
        in: query
        type: string
        required: false
        description: Filter by level (L1, L2, L3, L4)
    responses:
      200:
        description: List of technical capabilities with mapping status
    """
    try:
        from app.models.technical_capability import TechnicalCapability

        domain_filter = request.args.get("domain")
        level_filter = request.args.get("level")

        query = TechnicalCapability.query

        if domain_filter:
            query = query.filter_by(acm_domain=domain_filter)
        if level_filter:
            query = query.filter_by(level=level_filter)

        capabilities = query.order_by(
            TechnicalCapability.acm_domain, TechnicalCapability.code
        ).all()

        # Batch-prefetch application counts to avoid N+1 queries
        from app.models.technical_capability import application_technical_capability_mapping
        from sqlalchemy import func
        cap_ids = [c.id for c in capabilities]
        if cap_ids:
            _cap_app_counts = dict(
                db.session.query(
                    application_technical_capability_mapping.c.technical_capability_id,
                    func.count(application_technical_capability_mapping.c.application_id),
                ).filter(
                    application_technical_capability_mapping.c.technical_capability_id.in_(cap_ids)
                ).group_by(application_technical_capability_mapping.c.technical_capability_id).all()
            )
        else:
            _cap_app_counts = {}

        capabilities_data = []
        for cap in capabilities:
            app_count = _cap_app_counts.get(cap.id, 0)
            capabilities_data.append(
                {
                    "id": cap.id,
                    "name": cap.name,
                    "code": cap.code,
                    "description": cap.description,
                    "acm_domain": cap.acm_domain,
                    "level": cap.level,
                    "level_number": cap.level_number,
                    "parent_id": cap.parent_id,
                    "capability_type": cap.capability_type,
                    "is_foundational": cap.is_foundational,
                    "is_differentiating": cap.is_differentiating,
                    "applications_count": app_count,
                    "status": "mapped" if app_count > 0 else "unmapped",
                    "full_path": cap.get_full_path(),
                }
            )

        return jsonify(
            {
                "capabilities": capabilities_data,
                "total": len(capabilities_data),
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error getting ACM capabilities: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred", "capabilities": [], "total": 0}), 500


@capability_map.route("/api/acm/gap-analysis")
@login_required
def api_acm_gap_analysis():
    """
    Get ACM technical capability gap analysis for capability-map Gap Analysis tab.

    ---
    tags:
      - ACM
      - Gap Analysis
    responses:
      200:
        description: Technical capability gap analysis data
    """
    try:
        from app.services.acm_technical_capability_service import ACMTechnicalCapabilityService

        analysis = ACMTechnicalCapabilityService.analyze_capability_gaps()

        # Format for capability-map display (Matching what capability_roadmap.html expects)
        gap_data = {
            "success": True,
            "capabilities": analysis.get("uncovered_capabilities", []),
            "domain_gaps": [
                {
                    "domain": domain,
                    "name": domain.replace("-", " ").title(),
                    "total": stats["total"],
                    "covered": stats["covered"],
                    "uncovered": stats["uncovered"],
                    "coverage_percentage": stats["coverage_percentage"],
                }
                for domain, stats in analysis.get("by_domain", {}).items()
            ],
            "statistics": {
                "total": analysis["total_capabilities"],
                "unmapped": analysis["uncovered"],
                "partial": 0,  # Could be calculated if needed
                "coverage_rate": analysis["coverage_percentage"],
            },
            "summary": {
                "total_capabilities": analysis["total_capabilities"],
                "covered": analysis["covered"],
                "uncovered": analysis["uncovered"],
                "coverage_percentage": analysis["coverage_percentage"],
            },
        }

        return jsonify(gap_data)
    except Exception as e:
        current_app.logger.error(f"Error getting ACM gap analysis: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@capability_map.route("/api/acm/hierarchy")
@login_required
def api_acm_hierarchy():
    """
    Get ACM technical capability hierarchy tree for visualization.

    ---
    tags:
      - ACM
      - Technical Capabilities
    parameters:
      - name: domain
        in: query
        type: string
        required: false
        description: Filter by ACM domain
    responses:
      200:
        description: Hierarchical tree of technical capabilities
    """
    try:
        from app.models.technical_capability import ACMDomain, TechnicalCapability

        domain_filter = request.args.get("domain")

        # Build hierarchy
        hierarchy = []

        domains_to_process = [domain_filter] if domain_filter else ACMDomain.ALL_DOMAINS

        # Batch-prefetch all tech capabilities for requested domains to avoid N+1 queries
        if domain_filter:
            all_domain_caps = TechnicalCapability.query.filter_by(acm_domain=domain_filter).all()
        else:
            all_domain_caps = TechnicalCapability.query.all()

        # Build lookup structures
        _l1_by_domain = {}
        _children_by_parent = {}
        for tc in all_domain_caps:
            if tc.level == "L1":
                _l1_by_domain.setdefault(tc.acm_domain, []).append(tc)
            if tc.parent_id is not None:
                _children_by_parent.setdefault(tc.parent_id, []).append(tc)

        # Sort L1 caps by code
        for domain_key in _l1_by_domain:
            _l1_by_domain[domain_key].sort(key=lambda x: x.code or "")

        # Batch-prefetch application counts per capability
        from app.models.technical_capability import application_technical_capability_mapping
        from sqlalchemy import func
        _all_cap_ids = [tc.id for tc in all_domain_caps]
        if _all_cap_ids:
            _hier_app_counts = dict(
                db.session.query(
                    application_technical_capability_mapping.c.technical_capability_id,
                    func.count(application_technical_capability_mapping.c.application_id),
                ).filter(
                    application_technical_capability_mapping.c.technical_capability_id.in_(_all_cap_ids)
                ).group_by(application_technical_capability_mapping.c.technical_capability_id).all()
            )
        else:
            _hier_app_counts = {}

        for domain in domains_to_process:
            # Get L1 capabilities from prefetched data
            l1_caps = _l1_by_domain.get(domain, [])

            domain_node = {
                "id": f"domain-{domain}",
                "name": domain.replace("-", " ").title(),
                "code": domain,
                "level": "L0",
                "type": "domain",
                "children": [],
                "applications_count": 0,
            }

            for l1 in l1_caps:
                l1_app_count = _hier_app_counts.get(l1.id, 0)
                l1_node = {
                    "id": l1.id,
                    "name": l1.name,
                    "code": l1.code,
                    "level": "L1",
                    "type": "capability_area",
                    "applications_count": l1_app_count,
                    "children": [],
                }

                # Get L2 children from prefetched data
                for l2 in _children_by_parent.get(l1.id, []):
                    l2_app_count = _hier_app_counts.get(l2.id, 0)
                    l2_node = {
                        "id": l2.id,
                        "name": l2.name,
                        "code": l2.code,
                        "level": "L2",
                        "type": "capability_group",
                        "applications_count": l2_app_count,
                        "children": [],
                    }

                    # Get L3 children from prefetched data
                    for l3 in _children_by_parent.get(l2.id, []):
                        l3_app_count = _hier_app_counts.get(l3.id, 0)
                        l3_node = {
                            "id": l3.id,
                            "name": l3.name,
                            "code": l3.code,
                            "level": "L3",
                            "type": "specific_capability",
                            "applications_count": l3_app_count,
                            "children": [],
                        }
                        l2_node["children"].append(l3_node)

                    l1_node["children"].append(l2_node)

                domain_node["children"].append(l1_node)
                domain_node["applications_count"] += l1_node["applications_count"]

            hierarchy.append(domain_node)

        return jsonify(
            {
                "hierarchy": hierarchy,
                "total_domains": len(hierarchy),
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error getting ACM hierarchy: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred", "hierarchy": []}), 500


@capability_map.route("/api/acm/capability/<int:capability_id>/applications")
@login_required
def api_acm_capability_applications(capability_id):
    """
    Get all applications with their mapping status to a specific technical capability.
    Used by the ACM mapping modal to show which apps are mapped/unmapped.

    ---
    tags:
      - ACM
      - Technical Capabilities
    parameters:
      - name: capability_id
        in: path
        type: integer
        required: true
        description: Technical Capability ID
    responses:
      200:
        description: List of applications with mapping status
    """
    try:
        from app.models.application_portfolio import ApplicationComponent
        from app.models.technical_capability import (
            TechnicalCapability,
            application_technical_capability_mapping,
        )

        # Check capability exists
        capability = TechnicalCapability.query.get(capability_id)
        if not capability:
            return jsonify({"error": "Technical capability not found"}), 404

        # Single SQL LEFT OUTER JOIN: fetch all non-retired applications with their
        # mapping row for this capability (NULL columns when not mapped).  # noqa: raw-sql
        atcm = application_technical_capability_mapping
        rows = (
            db.session.query(ApplicationComponent, atcm)
            .outerjoin(
                atcm,
                (atcm.c.application_id == ApplicationComponent.id)
                & (atcm.c.technical_capability_id == capability_id),
            )
            .filter(ApplicationComponent.lifecycle_status != "retired")
            .order_by(ApplicationComponent.name)
            .all()
        )

        # Build applications list and count mapped rows directly from JOIN result
        applications = []
        mapped_count = 0
        for app, mapping_row in rows:
            is_mapped = mapping_row is not None and mapping_row.id is not None
            if is_mapped:
                mapped_count += 1
            applications.append(
                {
                    "id": app.id,
                    "name": app.name,
                    "type": app.application_type or "Unknown",
                    "domain": app.business_domain or "Not specified",
                    "description": app.description or "",
                    "is_mapped": is_mapped,
                    "mapping_id": mapping_row.id if is_mapped else None,
                    "capability_coverage": mapping_row.capability_coverage if is_mapped else None,
                    "maturity_level": mapping_row.maturity_level if is_mapped else None,
                    "notes": mapping_row.notes if is_mapped else None,
                }
            )

        return jsonify(
            {
                "success": True,
                "capability_id": capability_id,
                "capability_name": capability.name,
                "applications": applications,
                "total_count": len(applications),
                "mapped_count": mapped_count,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error getting ACM capability applications: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@capability_map.route("/api/acm/mapping/<int:mapping_id>", methods=["DELETE"])
@login_required
@audit_log("acm_mapping_delete")
def api_acm_delete_mapping(mapping_id):
    """
    Delete an ACM technical capability mapping.

    ---
    tags:
      - ACM
      - Technical Capabilities
    parameters:
      - name: mapping_id
        in: path
        type: integer
        required: true
        description: Mapping ID to delete
    responses:
      200:
        description: Mapping deleted successfully
      404:
        description: Mapping not found
    """
    try:
        from app.models.technical_capability import application_technical_capability_mapping

        # Check mapping exists
        mapping = (
            db.session.query(application_technical_capability_mapping)
            .filter(application_technical_capability_mapping.c.id == mapping_id)
            .first()
        )

        if not mapping:
            return jsonify({"success": False, "error": "Mapping not found"}), 404

        # Delete the mapping
        db.session.execute(  # tenant-filtered: scoped via parent FK
            application_technical_capability_mapping.delete().where(
                application_technical_capability_mapping.c.id == mapping_id
            )
        )
        db.session.commit()

        return jsonify({"success": True, "message": "Mapping deleted successfully"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting ACM mapping: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_map.route("/api/acm/mappings/bulk", methods=["POST"])
@login_required
@audit_log("acm_bulk_mappings_create")
def api_acm_bulk_mappings():
    """
    Create or update multiple ACM technical capability mappings in bulk.

    ---
    tags:
      - ACM
      - Technical Capabilities
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            mappings:
              type: array
              items:
                type: object
                properties:
                  application_id:
                    type: integer
                  technical_capability_id:
                    type: integer
                  capability_coverage:
                    type: string
                  maturity_level:
                    type: string
                  notes:
                    type: string
    responses:
      200:
        description: Mappings saved successfully
    """
    try:
        from datetime import datetime

        from app.models.technical_capability import application_technical_capability_mapping

        data = request.get_json()
        mappings = data.get("mappings", [])

        if not mappings:
            return jsonify({"success": False, "error": "No mappings provided"}), 400

        created_count = 0
        updated_count = 0

        # Batch-prefetch existing mappings to avoid N+1 queries
        _requested_pairs = set()
        for md in mappings:
            a_id = md.get("application_id")
            c_id = md.get("technical_capability_id")
            if a_id and c_id:
                _requested_pairs.add((a_id, c_id))

        _existing_acm_mappings = {}
        if _requested_pairs:
            _req_app_ids = [p[0] for p in _requested_pairs]
            _req_cap_ids = [p[1] for p in _requested_pairs]
            _existing_rows = db.session.query(application_technical_capability_mapping).filter(
                application_technical_capability_mapping.c.application_id.in_(_req_app_ids),
                application_technical_capability_mapping.c.technical_capability_id.in_(_req_cap_ids),
            ).all()
            for row in _existing_rows:
                _existing_acm_mappings[(row.application_id, row.technical_capability_id)] = row

        for mapping_data in mappings:
            app_id = mapping_data.get("application_id")
            cap_id = mapping_data.get("technical_capability_id")

            if not app_id or not cap_id:
                continue

            # Check if mapping already exists using prefetched data
            existing = _existing_acm_mappings.get((app_id, cap_id))

            if existing:
                # Update existing mapping
                db.session.execute(  # tenant-filtered: scoped via parent FK
                    application_technical_capability_mapping.update()
                    .where(application_technical_capability_mapping.c.id == existing.id)
                    .values(
                        capability_coverage=mapping_data.get("capability_coverage", "partial"),
                        maturity_level=mapping_data.get("maturity_level", "defined"),
                        notes=mapping_data.get("notes", ""),
                    )
                )
                updated_count += 1
            else:
                # Create new mapping
                db.session.execute(  # tenant-filtered: scoped via parent FK
                    application_technical_capability_mapping.insert().values(
                        application_id=app_id,
                        technical_capability_id=cap_id,
                        capability_coverage=mapping_data.get("capability_coverage", "partial"),
                        maturity_level=mapping_data.get("maturity_level", "defined"),
                        notes=mapping_data.get("notes", ""),
                        created_at=datetime.utcnow(),
                    )
                )
                created_count += 1

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "created": created_count,
                "updated": updated_count,
                "message": f"Successfully saved {created_count + updated_count} mappings",
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving ACM bulk mappings: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
