"""
Data Architecture Routes

Provides REST API endpoints and dashboard views for data architecture models:
- ConceptualDataModel
- LogicalDataModel
- PhysicalDataModel
- DataLineage
- DataTransformation
"""

import logging

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import login_required

from app import db
from app.decorators import audit_log

from app.models import (
    ConceptualDataModel,
    DataLineage,
    DataTransformation,
    LogicalDataModel,
    PhysicalDataModel,
)

logger = logging.getLogger(__name__)

data_architecture_bp = Blueprint(
    "data_architecture", __name__, url_prefix="/architecture"
)


# ============================================================================
# Page Routes
# ============================================================================


@data_architecture_bp.route("/data-architecture")
@login_required
def data_architecture_dashboard():
    """Data architecture dashboard."""
    try:
        from app.models.capability_to_vendor_mapping import (
            TechnicalCapabilityVendorMapping,
        )
        from app.models.technical_capability import ACMDomain, TechnicalCapability

        # Filter for Data & Analytics domains (Pattern 4 from plan)
        data_domains = [ACMDomain.DATA_STORAGE, ACMDomain.AI_ANALYTICS]
        data_caps_objs = TechnicalCapability.query.filter(
            TechnicalCapability.acm_domain.in_(data_domains)
        ).all()

        data_platform_stack = []
        # Batch prefetch all vendor mappings for these capabilities
        cap_ids = [cap.id for cap in data_caps_objs]
        all_mappings = (
            TechnicalCapabilityVendorMapping.query.filter(
                TechnicalCapabilityVendorMapping.technical_capability_id.in_(cap_ids)
            ).all()
            if cap_ids
            else []
        )
        mappings_by_cap = {}
        for m in all_mappings:
            mappings_by_cap.setdefault(m.technical_capability_id, []).append(m)

        for cap in data_caps_objs:
            # Look up pre-fetched vendor mappings for this capability
            mappings = mappings_by_cap.get(cap.id, [])
            for m in mappings:
                if m.vendor_product:
                    data_platform_stack.append(
                        {
                            "capability": cap.name,
                            "domain": cap.domain,
                            "product": m.vendor_product.name,
                            "vendor": m.vendor_product.vendor.name
                            if m.vendor_product.vendor
                            else "Internal",
                            "maturity": m.maturity_level,
                            "fit": m.fit_score,
                        }
                    )

        # Query real data model counts
        conceptual_count = 0
        logical_count = 0
        physical_count = 0
        data_lineage_count = 0
        archimate_data_count = 0
        archimate_rel_count = 0
        try:
            # Re-importing inside try/except block as in original code to handle potential missing models
            # although in this file we imported them at top level.
            # We will use the top level imports for consistency unless they are truly optional/missing.
            # The original code imported from app.models.all_missing_models which suggests they might be stubs?
            # But line 21 of architecture_routes.py imported them from app.models.
            # I will stick to app.models imports which I did at the top.

            conceptual_count = ConceptualDataModel.query.count()
            logical_count = LogicalDataModel.query.count()
            physical_count = PhysicalDataModel.query.count()
            data_lineage_count = DataLineage.query.count()
        except Exception:
            logger.debug(
                "Failed to query data architecture model counts", exc_info=True
            )

        try:
            from app.models.archimate_core import (
                ArchiMateElement,
                ArchiMateRelationship,
            )

            archimate_data_count = ArchiMateElement.query.filter(
                ArchiMateElement.layer.in_(["Application", "Technology"])
            ).count()
            archimate_rel_count = ArchiMateRelationship.query.count()
        except Exception:
            logger.debug(
                "Failed to query ArchiMate element/relationship counts", exc_info=True
            )

        return render_template(
            "enterprise/data_architecture_dashboard.html",
            data_stack=data_platform_stack,
            data_cap_count=len(data_caps_objs),
            conceptual_count=conceptual_count,
            logical_count=logical_count,
            physical_count=physical_count,
            data_lineage_count=data_lineage_count,
            archimate_data_count=archimate_data_count,
            archimate_rel_count=archimate_rel_count,
        )
    except Exception as e:
        current_app.logger.error(f"Error loading data architecture dashboard: {e}")
        return render_template(
            "enterprise/data_architecture_dashboard.html",
            data_stack=[],
            data_cap_count=0,
            conceptual_count=0,
            logical_count=0,
            physical_count=0,
            data_lineage_count=0,
            archimate_data_count=0,
            archimate_rel_count=0,
        )


# ============================================================================
# Data Architecture API Endpoints
# ============================================================================


@data_architecture_bp.route("/api/data-models")
@login_required
def api_data_models():
    """Get all data architecture models."""
    try:
        conceptual_models = ConceptualDataModel.query.limit(500).all()
        logical_models = LogicalDataModel.query.limit(500).all()
        physical_models = PhysicalDataModel.query.limit(500).all()

        return jsonify(
            {
                "conceptual_models": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "description": m.description,
                        "business_domain": m.business_domain,
                        "scope": m.scope,
                        "created_at": m.created_at.isoformat()
                        if m.created_at
                        else None,
                    }
                    for m in conceptual_models
                ],
                "logical_models": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "description": m.description,
                        "normalization_level": m.normalization_level,
                        "design_pattern": m.design_pattern,
                        "conceptual_model_id": m.conceptual_model_id,
                        "created_at": m.created_at.isoformat()
                        if m.created_at
                        else None,
                    }
                    for m in logical_models
                ],
                "physical_models": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "description": m.description,
                        "database_type": m.database_type,
                        "deployment_environment": m.deployment_environment,
                        "logical_model_id": m.logical_model_id,
                        "created_at": m.created_at.isoformat()
                        if m.created_at
                        else None,
                    }
                    for m in physical_models
                ],
            }
        )
    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


@data_architecture_bp.route("/api/data-lineage")
@login_required
def api_data_lineage():
    """Get all data lineage models."""
    try:
        lineage_models = DataLineage.query.limit(500).all()
        return jsonify(
            [
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "lineage_type": m.lineage_type,
                    "data_domain": m.data_domain,
                    "source_system": m.source_system,
                    "target_system": m.target_system,
                    "frequency": m.frequency,
                    "data_classification": m.data_classification,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in lineage_models
            ]
        )
    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


@data_architecture_bp.route("/api/data-transformations")
@login_required
def api_data_transformations():
    """Get all data transformation models."""
    try:
        transformations = DataTransformation.query.limit(500).all()
        return jsonify(
            [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "transformation_type": t.transformation_type,
                    "processing_language": t.processing_language,
                    "source_format": t.source_format,
                    "target_format": t.target_format,
                    "lineage_id": t.lineage_id,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in transformations
            ]
        )
    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


@data_architecture_bp.route("/api/data-models", methods=["POST"])
@login_required
@audit_log("create_data_model")
def create_data_model():
    """Create a new data model."""
    try:
        data = request.get_json()
        model_type = data.get("model_type")  # 'conceptual', 'logical', 'physical'

        if model_type == "conceptual":
            model = ConceptualDataModel(
                name=data["name"],
                description=data.get("description", ""),
                business_domain=data.get("business_domain"),
                scope=data.get("scope"),
                version=data.get("version"),
                data_steward=data.get("data_steward"),
                business_owner=data.get("business_owner"),
            )
        elif model_type == "logical":
            model = LogicalDataModel(
                name=data["name"],
                description=data.get("description", ""),
                conceptual_model_id=data.get("conceptual_model_id"),
                normalization_level=data.get("normalization_level"),
                design_pattern=data.get("design_pattern"),
                supports_transactions=data.get("supports_transactions", True),
                supports_concurrency=data.get("supports_concurrency", True),
            )
        elif model_type == "physical":
            model = PhysicalDataModel(
                name=data["name"],
                description=data.get("description", ""),
                logical_model_id=data.get("logical_model_id"),
                database_type=data.get("database_type"),
                database_version=data.get("database_version"),
                deployment_environment=data.get("deployment_environment"),
                schema_name=data.get("schema_name"),
            )
        else:
            return jsonify({"error": "Invalid model_type"}), 400

        from app import db

        db.session.add(model)
        db.session.commit()

        return (
            jsonify(
                {
                    "id": model.id,
                    "name": model.name,
                    "message": f"{model_type.title()} data model created successfully",
                }
            ),
            201,
        )

    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


# ============================================================================
# Data Entity Catalog (REQ-DATA-001, REQ-DATA-002)
# ============================================================================


@data_architecture_bp.route("/data-entities")
@login_required
def data_entity_catalog():
    """Data entity catalog — browse, search, and filter data entities."""
    from app.models.process_data import DataDomain, DataEntity

    search = request.args.get("search", "").strip()
    classification = request.args.get("classification", "")
    domain_id = request.args.get("domain_id", "", type=str)
    entity_type = request.args.get("entity_type", "")

    query = DataEntity.query

    if search:
        query = query.filter(
            DataEntity.name.ilike(f"%{search}%")
            | DataEntity.business_name.ilike(f"%{search}%")
            | DataEntity.description.ilike(f"%{search}%")
        )
    if classification:
        query = query.filter(DataEntity.data_classification == classification)
    if domain_id:
        query = query.filter(DataEntity.domain_id == int(domain_id))
    if entity_type:
        query = query.filter(DataEntity.entity_type == entity_type)

    entities = query.order_by(DataEntity.name).all()
    domains = DataDomain.query.order_by(DataDomain.name).all()

    # Classification distribution for dashboard widget
    from sqlalchemy import func as sa_func
    classification_dist = dict(
        db.session.query(DataEntity.data_classification, sa_func.count(DataEntity.id))
        .group_by(DataEntity.data_classification)
        .all()
    )

    return render_template(
        "data_architecture/entity_catalog.html",
        entities=entities,
        domains=domains,
        search=search,
        classification=classification,
        domain_id=domain_id,
        entity_type=entity_type,
        classification_dist=classification_dist,
        total_count=len(entities),
    )


@data_architecture_bp.route("/data-entities/create", methods=["GET", "POST"])
@login_required
def create_data_entity():
    """Create a new data entity."""
    from flask import flash, redirect, url_for
    from app.models.process_data import DataDomain, DataEntity

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name is required.", "error")
            return redirect(request.url)

        domain_id = request.form.get("domain_id", type=int)
        if not domain_id:
            # Auto-create a default domain if none exists
            default_domain = DataDomain.query.filter_by(name="General").first()
            if not default_domain:
                default_domain = DataDomain(name="General", description="Default data domain")
                db.session.add(default_domain)
                db.session.flush()
            domain_id = default_domain.id

        entity = DataEntity(
            name=name,
            business_name=request.form.get("business_name", "").strip() or None,
            description=request.form.get("description", "").strip() or None,
            domain_id=domain_id,
            entity_type=request.form.get("entity_type") or None,
            data_classification=request.form.get("data_classification") or None,
            contains_pii="contains_pii" in request.form,
            system_of_record=request.form.get("system_of_record", "").strip() or None,
            is_master_data="is_master_data" in request.form,
        )
        db.session.add(entity)
        db.session.commit()
        flash(f"Data entity '{name}' created.", "success")
        return redirect(url_for("data_architecture.data_entity_catalog"))

    domains = DataDomain.query.order_by(DataDomain.name).all()
    return render_template("data_architecture/entity_form.html", entity=None, domains=domains, form_action="create")


@data_architecture_bp.route("/data-entities/<int:entity_id>/edit", methods=["GET", "POST"])
@login_required
def edit_data_entity(entity_id):
    """Edit an existing data entity."""
    from flask import flash, redirect, url_for
    from app.models.process_data import DataDomain, DataEntity

    entity = DataEntity.query.get_or_404(entity_id)

    if request.method == "POST":
        entity.name = request.form.get("name", "").strip() or entity.name
        entity.business_name = request.form.get("business_name", "").strip() or None
        entity.description = request.form.get("description", "").strip() or None
        entity.domain_id = request.form.get("domain_id", type=int) or entity.domain_id
        entity.entity_type = request.form.get("entity_type") or None
        entity.data_classification = request.form.get("data_classification") or None
        entity.contains_pii = "contains_pii" in request.form
        entity.system_of_record = request.form.get("system_of_record", "").strip() or None
        entity.is_master_data = "is_master_data" in request.form
        db.session.commit()
        flash(f"Data entity '{entity.name}' updated.", "success")
        return redirect(url_for("data_architecture.data_entity_catalog"))

    domains = DataDomain.query.order_by(DataDomain.name).all()
    return render_template("data_architecture/entity_form.html", entity=entity, domains=domains, form_action="edit")


@data_architecture_bp.route("/data-entities/<int:entity_id>/delete", methods=["POST"])
@login_required
def delete_data_entity(entity_id):
    """Delete a data entity."""
    from flask import flash, redirect, url_for
    from app.models.process_data import DataEntity

    entity = DataEntity.query.get_or_404(entity_id)
    name = entity.name
    db.session.delete(entity)
    db.session.commit()
    flash(f"Data entity '{name}' deleted.", "success")
    return redirect(url_for("data_architecture.data_entity_catalog"))


@data_architecture_bp.route("/api/data-entities")
@login_required
def api_data_entities():
    """JSON API for data entities — supports search and filtering."""
    from app.models.process_data import DataEntity

    search = request.args.get("search", "").strip()
    limit = request.args.get("limit", 50, type=int)

    query = DataEntity.query
    if search:
        query = query.filter(DataEntity.name.ilike(f"%{search}%"))

    entities = query.order_by(DataEntity.name).limit(min(limit, 200)).all()

    return jsonify([
        {
            "id": e.id,
            "name": e.name,
            "business_name": e.business_name,
            "entity_type": e.entity_type,
            "data_classification": e.data_classification,
            "contains_pii": e.contains_pii,
            "data_quality_score": e.data_quality_score,
            "system_of_record": e.system_of_record,
        }
        for e in entities
    ])
