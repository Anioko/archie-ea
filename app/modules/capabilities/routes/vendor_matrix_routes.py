"""
Capability Map — Vendor-capability matrix & risk API.

Extracted from app/routes/capability_map_routes.py (lines 6094-6562).

Routes (7):
    - api_vendor_capability_matrix()                             GET "/api/vendor-capability-matrix"
    - api_vendor_application_mappings()                          POST "/api/vendors/application-mappings"
    - api_vendor_capability_risks()                              GET "/api/vendors/capability-risks"
    - api_create_vendor_capability_risk()                        POST "/api/vendors/capability-risks"
    - api_delete_vendor_capability_risk(risk_id)                 DELETE "/api/vendors/capability-risks/<int:risk_id>"
    - api_backfill_vendor_capability_risks()                     POST "/api/vendors/capability-risks/backfill"
    - api_suggest_vendors_for_capability(capability_id)          GET "/api/vendors/capability-suggestions/<int:capability_id>"
"""

from flask import current_app, jsonify, request
from flask_login import login_required

from app import db
from app.decorators import audit_log

from . import capability_map
import logging
logger = logging.getLogger(__name__)


# =============================================================================
# VENDOR-CAPABILITY MATRIX API
# =============================================================================


@capability_map.route("/api/vendor-capability-matrix")
@login_required
def api_vendor_capability_matrix():
    """
    Returns vendor-product-capability coverage data for the heatmap matrix.

    Query params:
        only_categories=1  Return just the sorted list of unique product categories.
        category=<value>   Filter results to this product category only.

    Response is a flat array of objects, one per (vendor, product, capability) triple.
    Used by vendor_capability_matrix.html template.
    """
    try:
        import json

        from app.models.business_capabilities import BusinessCapability
        from app.models.vendor.vendor_organization import (
            VendorOrganization,
            VendorProduct,
            VendorProductCapability,
        )

        # Lightweight categories-only response
        if request.args.get("only_categories") == "1":
            cats = (
                db.session.query(VendorProduct.product_type)
                .filter(VendorProduct.product_type.isnot(None))
                .distinct()
                .order_by(VendorProduct.product_type)
                .all()
            )
            return jsonify([c[0] for c in cats if c[0]])

        category_filter = request.args.get("category", "").strip()

        # Build query with optional category filter
        query = (
            db.session.query(VendorProductCapability, VendorProduct, BusinessCapability)
            .join(VendorProduct, VendorProductCapability.vendor_product_id == VendorProduct.id)
            .join(
                BusinessCapability,
                VendorProductCapability.business_capability_id == BusinessCapability.id,
            )
        )
        if category_filter:
            query = query.filter(VendorProduct.product_type == category_filter)

        # Query vendor-product-capability mappings
        mappings = query.all()

        # Pre-fetch vendor names
        vendor_ids = {m[1].vendor_organization_id for m in mappings}
        vendors = (
            VendorOrganization.query.filter(VendorOrganization.id.in_(vendor_ids)).all()
            if vendor_ids
            else []
        )
        vendor_names = {v.id: v.name for v in vendors}

        matrix_data = []
        for vpc, product, capability in mappings:
            # Parse JSON fields safely
            gaps_raw = vpc.gaps
            strengths_raw = vpc.strengths

            gaps = []
            if gaps_raw:
                try:
                    gaps = json.loads(gaps_raw) if isinstance(gaps_raw, str) else gaps_raw
                except (json.JSONDecodeError, TypeError):
                    logger.exception("Failed to JSON parsing")
                    pass

            strengths = []
            if strengths_raw:
                try:
                    strengths = (
                        json.loads(strengths_raw)
                        if isinstance(strengths_raw, str)
                        else strengths_raw
                    )
                except (json.JSONDecodeError, TypeError):
                    logger.exception("Failed to compute strengths")
                    pass

            matrix_data.append(
                {
                    "vendor_name": vendor_names.get(product.vendor_organization_id, "Unknown"),
                    "product_name": product.name,
                    "product_category": product.product_type or "General",
                    "capability_name": capability.name,
                    "capability_id": capability.id,
                    "capability_domain": capability.business_domain,
                    "coverage_percentage": vpc.coverage_percentage or 0,
                    "out_of_box_percentage": vpc.out_of_box_percentage or 0,
                    "maturity_level": vpc.maturity_level,
                    "fit_score": vpc.fit_score,
                    "implementation_complexity": vpc.implementation_complexity,
                    "customization_required": vpc.customization_required,
                    "customization_effort": vpc.customization_effort,
                    "gaps": gaps,
                    "strengths": strengths,
                    "evidence": {
                        "source": "vendor_assessment",
                        "verified_at": vpc.last_validated_at.isoformat()
                        if vpc.last_validated_at
                        else None,
                        "verified_by": None,
                    },
                }
            )

        return jsonify(matrix_data)

    except Exception as e:
        current_app.logger.error(f"Error loading vendor capability matrix: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@capability_map.route("/api/vendors/application-mappings", methods=["POST"])
@login_required
@audit_log("vendor_application_mapping_create")
def api_vendor_application_mappings():
    """
    Save vendor product to application mappings from the unified mapping modal.

    Request body:
    {
        "vendor_product_id": 123,
        "applications": [
            {
                "application_id": "456",
                "mapping_id": "789",
                "mapping": {
                    "implementation_status": "deployed",
                    "license_type": "subscription",
                    "deployment_model": "cloud",
                    "annual_cost": 50000,
                    "user_count": 100
                }
            }
        ],
        "context": "vendor"
    }
    """
    try:
        from app.models.application_layer import ApplicationComponent
        from app.models.vendor.vendor_organization import VendorProduct

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing request body"}), 400

        vendor_product_id = data.get("vendor_product_id")
        applications = data.get("applications", [])

        if not vendor_product_id:
            return jsonify({"error": "vendor_product_id is required"}), 400

        vendor_product_id = int(vendor_product_id)
        product = VendorProduct.query.get(vendor_product_id)
        if not product:
            return jsonify({"error": f"Vendor product not found: {vendor_product_id}"}), 404

        created = 0
        updated = 0

        from app.models.relationship_tables import application_component_vendor_products
        from sqlalchemy import and_

        # Batch-prefetch: validate application IDs and existing mappings to avoid N+1 queries
        _vendor_req_app_ids = []
        for ad in applications:
            _aid = ad.get("application_id")
            if _aid:
                try:
                    _vendor_req_app_ids.append(int(_aid))
                except (ValueError, TypeError):
                    logger.exception("Failed to operation")
                    pass

        _valid_vendor_app_ids = set()
        if _vendor_req_app_ids:
            _valid_vendor_apps = ApplicationComponent.query.filter(
                ApplicationComponent.id.in_(_vendor_req_app_ids)
            ).all()
            _valid_vendor_app_ids = {a.id for a in _valid_vendor_apps}

        # Prefetch existing mappings for this vendor product
        _existing_vendor_mappings = {}
        if _vendor_req_app_ids:
            _existing_vendor_rows = db.session.execute(  # tenant-filtered: scoped via parent FK (application_component_id, vendor_product_id)
                application_component_vendor_products.select().where(
                    and_(
                        application_component_vendor_products.c.application_component_id.in_(_vendor_req_app_ids),
                        application_component_vendor_products.c.vendor_product_id == vendor_product_id,
                    )
                )
            ).fetchall()
            for row in _existing_vendor_rows:
                _existing_vendor_mappings[row.application_component_id] = row

        for app_data in applications:
            app_id = app_data.get("application_id")
            if not app_id:
                continue

            app_id = int(app_id)

            # Validate ApplicationComponent exists using prefetched set
            if app_id not in _valid_vendor_app_ids:
                continue

            mapping_fields = app_data.get("mapping", {})

            # Check existing M:M relationship using prefetched data
            existing = _existing_vendor_mappings.get(app_id)

            if existing:
                # Update existing
                db.session.execute(  # tenant-filtered: scoped via parent FK (application_component_id, vendor_product_id)
                    application_component_vendor_products.update()
                    .where(
                        and_(
                            application_component_vendor_products.c.application_component_id
                            == app_id,
                            application_component_vendor_products.c.vendor_product_id
                            == vendor_product_id,
                        )
                    )
                    .values(
                        relationship_type=mapping_fields.get("relationship_type", "uses"),
                        deployment_type=mapping_fields.get("deployment_model", "production"),
                        criticality=mapping_fields.get("dependency_level", "important"),
                        usage_percentage=mapping_fields.get("coverage_percentage", 50),
                    )
                )
                updated += 1
            else:
                # Create new mapping
                db.session.execute(  # tenant-filtered: scoped via parent FK (application_component_id, vendor_product_id)
                    application_component_vendor_products.insert().values(
                        application_component_id=app_id,
                        vendor_product_id=vendor_product_id,
                        relationship_type=mapping_fields.get("relationship_type", "uses"),
                        deployment_type=mapping_fields.get("deployment_model", "production"),
                        criticality=mapping_fields.get("dependency_level", "important"),
                        usage_percentage=mapping_fields.get("coverage_percentage", 50),
                    )
                )
                created += 1

        db.session.commit()
        return jsonify({"success": True, "created": created, "updated": updated})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving vendor application mappings: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


# =============================================================================
# VENDOR-CAPABILITY RISK API
# =============================================================================


@capability_map.route("/api/vendors/capability-risks", methods=["GET"])
@login_required
def api_vendor_capability_risks():
    """
    List vendor-capability risk mappings.

    Query params:
    - vendor_id: filter by vendor
    - capability_id: filter by capability
    """
    try:
        from sqlalchemy import and_

        from app.models.business_capabilities import BusinessCapability
        from app.models.vendor.relationship_tables import vendor_capability_risks
        from app.models.vendor.vendor_organization import VendorOrganization

        vendor_id = request.args.get("vendor_id", type=int)
        capability_id = request.args.get("capability_id", type=int)

        query = vendor_capability_risks.select()
        if vendor_id:
            query = query.where(
                vendor_capability_risks.c.vendor_organization_id == vendor_id
            )
        if capability_id:
            query = query.where(
                vendor_capability_risks.c.business_capability_id == capability_id
            )

        # tenant-filtered: scoped via parent FK (vendor_organization_id, business_capability_id)
        rows = db.session.execute(query).fetchall()

        # Pre-fetch names
        vendor_ids = {r.vendor_organization_id for r in rows}
        cap_ids = {r.business_capability_id for r in rows}

        vendors = (
            {v.id: v.name for v in VendorOrganization.query.filter(VendorOrganization.id.in_(vendor_ids)).all()}
            if vendor_ids
            else {}
        )
        caps = (
            {c.id: c.name for c in BusinessCapability.query.filter(BusinessCapability.id.in_(cap_ids)).all()}
            if cap_ids
            else {}
        )

        risks = []
        for row in rows:
            risks.append(
                {
                    "id": row.id,
                    "vendor_organization_id": row.vendor_organization_id,
                    "vendor_name": vendors.get(row.vendor_organization_id, "Unknown"),
                    "business_capability_id": row.business_capability_id,
                    "capability_name": caps.get(row.business_capability_id, "Unknown"),
                    "risk_level": row.risk_level,
                    "risk_type": row.risk_type,
                    "risk_description": row.risk_description,
                    "mitigation_strategy": row.mitigation_strategy,
                    "likelihood": row.likelihood,
                    "impact": row.impact,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
            )

        return jsonify({"success": True, "risks": risks, "total": len(risks)})

    except Exception as e:
        current_app.logger.error(f"Error getting vendor capability risks: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@capability_map.route("/api/vendors/capability-risks", methods=["POST"])
@login_required
@audit_log("vendor_capability_risk_create")
def api_create_vendor_capability_risk():
    """
    Create or update a vendor-capability risk mapping.

    Request body:
    {
        "vendor_organization_id": 123,
        "business_capability_id": 456,
        "risk_level": "high",
        "risk_type": "vendor_dependency",
        "risk_description": "...",
        "mitigation_strategy": "..."
    }
    """
    try:
        from app.services.vendor_capability_link_service import VendorCapabilityLinkService

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing request body"}), 400

        vendor_id = data.get("vendor_organization_id")
        capability_id = data.get("business_capability_id")

        if not vendor_id or not capability_id:
            return jsonify({"error": "vendor_organization_id and business_capability_id required"}), 400

        service = VendorCapabilityLinkService()
        result = service.ensure_link(
            vendor=int(vendor_id),
            capability=int(capability_id),
            risk_level=data.get("risk_level"),
            risk_type=data.get("risk_type"),
            impact_description=data.get("risk_description"),
            mitigation_strategy=data.get("mitigation_strategy"),
            source="api",
        )

        return jsonify(
            {
                "success": True,
                "action": result.action,
                "vendor_id": result.vendor_id,
                "capability_id": result.capability_id,
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating vendor capability risk: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@capability_map.route("/api/vendors/capability-risks/<int:risk_id>", methods=["DELETE"])
@login_required
@audit_log("vendor_capability_risk_delete")
def api_delete_vendor_capability_risk(risk_id):
    """Delete a vendor-capability risk mapping by ID."""
    try:
        from app.models.vendor.relationship_tables import vendor_capability_risks

        result = db.session.execute(  # tenant-filtered: scoped via parent FK (vendor_organization_id, business_capability_id)
            vendor_capability_risks.delete().where(vendor_capability_risks.c.id == risk_id)
        )

        if result.rowcount == 0:
            return jsonify({"error": "Risk mapping not found"}), 404

        db.session.commit()
        return jsonify({"success": True, "deleted_id": risk_id})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting vendor capability risk: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@capability_map.route("/api/vendors/capability-risks/backfill", methods=["POST"])
@login_required
@audit_log("vendor_capability_risks_backfill")
def api_backfill_vendor_capability_risks():
    """
    Trigger backfill of vendor-capability risks from existing data sources.

    Optional body:
    {
        "min_coverage": 40,
        "include_initiatives": true,
        "include_products": true
    }
    """
    try:
        from app.services.vendor_capability_link_service import VendorCapabilityLinkService

        data = request.get_json() or {}
        service = VendorCapabilityLinkService()
        result = service.backfill_from_existing_sources(
            min_coverage=data.get("min_coverage", 40),
            include_initiatives=data.get("include_initiatives", True),
            include_products=data.get("include_products", True),
        )

        return jsonify({"success": True, "result": result})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error backfilling vendor capability risks: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@capability_map.route("/api/vendors/capability-suggestions/<int:capability_id>")
@login_required
def api_suggest_vendors_for_capability(capability_id):
    """
    Suggest vendors for a capability based on similarity scoring.

    Query params:
    - threshold: minimum similarity score (default 0.72)
    - limit: max results (default 5)
    """
    try:
        from app.models.business_capabilities import BusinessCapability
        from app.services.vendor_capability_link_service import VendorCapabilityLinkService

        capability = BusinessCapability.query.get(capability_id)
        if not capability:
            return jsonify({"error": f"Capability not found: {capability_id}"}), 404

        threshold = request.args.get("threshold", 0.72, type=float)
        limit = request.args.get("limit", 5, type=int)

        service = VendorCapabilityLinkService()
        suggestions = service.suggest_vendors_for_capability(
            capability=capability, threshold=threshold, limit=limit
        )

        return jsonify(
            {
                "success": True,
                "capability": {"id": capability.id, "name": capability.name},
                "suggestions": suggestions,
                "total": len(suggestions),
            }
        )

    except Exception as e:
        current_app.logger.error(
            f"Error suggesting vendors for capability {capability_id}: {e}", exc_info=True
        )
        return jsonify({"error": "An internal error occurred"}), 500
