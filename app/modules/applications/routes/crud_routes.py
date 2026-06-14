"""CRUD routes for the Applications module.

Extracted from app/routes/unified_applications_routes.py (lines 647-3030, 3691-3807).
Contains: application_create, application_detail, generate_application_archimate,
application_edit, application_delete, bulk_delete_applications,
api_delete_application, api_bulk_consolidate.
"""

import json
import logging
from datetime import datetime

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_  # dead-code-ok
from sqlalchemy.orm import joinedload  # dead-code-ok

from app import db
from app.models.application_capability import ApplicationCapabilityMapping  # dead-code-ok
from app.models.application_layer import (
    ApplicationCollaboration,
    ApplicationEvent,
    ApplicationFunction,
    ApplicationInteraction,
    ApplicationInterface,
    ApplicationProcess,
    ApplicationService,
    DataObject,
)
from app.models.application_portfolio import ApplicationComponent
from app.models.archimate_core import ArchiMateElement
from app.models.business_capabilities import (  # dead-code-ok
    BusinessCapability,
)
from app.models.business_layer import (  # dead-code-ok
    BusinessActor,
)
from app.models.implementation_migration import (  # dead-code-ok
    Deliverable,
    Gap,
    ImplementationEvent,
    Plateau,
    WorkPackage,
)
from app.models.models import (  # dead-code-ok
    ArchiMateElement,
    ArchiMateRelationship,
    ArchitectureModel,
    Requirement,
)
from app.models.motivation import Driver, Goal  # dead-code-ok
from app.models.physical_layer import (  # dead-code-ok
    PhysicalDistributionNetwork,
    PhysicalEquipment,
    PhysicalFacility,
    PhysicalMaterial,
)
from app.models.relationship_tables import (  # dead-code-ok
    ApplicationBusinessActorMapping,
    ApplicationProcessSupport,
)
from app.models.unified_application_capability_mapping import (  # dead-code-ok
    UnifiedApplicationCapabilityMapping,
)
from app.models.unified_capability import BusinessDomain, UnifiedCapability  # dead-code-ok
from app.models.vendor.vendor_organization import (  # dead-code-ok
    VendorOrganization,
    VendorProduct,
    application_vendor_products,
)
from app.services.archimate.archimate_llm_service import ArchiMateLLMService
from app.decorators import audit_log, require_roles
from app.services.rate_limiter import rate_limit
from app.utils.validators import (
    sanitize_html,
    validate_application_name,
    validate_description,
    validate_integer,
    validate_string,
    validation_error_response,
)

from app.schemas.api_schemas import ApplicationCreateSchema, _load_and_validate

from . import unified_applications_bp
from ._constants import (  # dead-code-ok
    ARCHIMATE_RELATIONSHIP_CHOICES,
    CAPABILITY_MATURITY_CHOICES,
    CAPABILITY_SUPPORT_LEVEL_CHOICES,
    VENDOR_CRITICALITY_CHOICES,
    VENDOR_DEPLOYMENT_CHOICES,
    VENDOR_HOSTING_CHOICES,
)
from ._helpers import (  # dead-code-ok
    _cleanup_application_relationships,
    _format_date,
    _load_domain_model_elements,
    _query_archimate_by_layer,
)

logger = logging.getLogger(__name__)


@unified_applications_bp.route("/create", methods=["GET", "POST"])
@login_required
@audit_log("application_create")
def application_create():
    """Create Application — modal handles creation inline; POST supports JSON."""
    if request.method == "GET":
        return redirect(url_for("unified_applications.application_list"))

    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Support both JSON and form-encoded POST
    if request.is_json:
        json_data = request.get_json() or {}
        # T-031: marshmallow schema validation for JSON requests
        _schema = ApplicationCreateSchema()
        validated, err_response = _load_and_validate(_schema, json_data)
        if err_response is not None:
            return err_response
        # Map validated keys onto request.form-compatible dict via a simple proxy
        class _DataProxy:
            def get(self, key, default=None):
                return validated.get(key, default)
        data = _DataProxy()
    else:
        data = request.form

    # POST handling with input validation
    validation_errors = []

    # Validate required fields
    name = data.get("name")
    is_valid, validated_name, error = validate_application_name(name)
    if not is_valid:
        validation_errors.append(error)
    else:
        # Plain-text field: do NOT HTML-sanitize. sanitize_html() entity-escapes
        # ('&' -> '&amp;') and Jinja autoescapes again on render, which double-
        # escapes the displayed name (e.g. "Billing & Invoicing" -> "Billing &amp;
        # Invoicing"). Validation above + template autoescape already make it safe.
        name = validated_name

    # Validate optional string fields
    description = data.get("description")
    is_valid, validated_desc, error = validate_description(description)
    if not is_valid:
        validation_errors.append(error)
    else:
        description = validated_desc or None

    application_code = data.get("application_code")
    is_valid, validated_code, error = validate_string(
        application_code, max_length=50, field_name="application_code"
    )
    if not is_valid:
        validation_errors.append(error)
    else:
        application_code = validated_code or None

    component_type = data.get("application_type")
    is_valid, validated_type, error = validate_string(
        component_type, max_length=100, field_name="application_type"
    )
    if not is_valid:
        validation_errors.append(error)

    criticality = data.get("criticality")
    is_valid, validated_crit, error = validate_string(
        criticality, max_length=50, field_name="criticality"
    )
    if not is_valid:
        validation_errors.append(error)

    technology_stack = data.get("technology_stack")
    is_valid, validated_tech, error = validate_string(
        technology_stack, max_length=500, field_name="technology_stack"
    )
    if not is_valid:
        validation_errors.append(error)
    else:
        technology_stack = sanitize_html(validated_tech) if validated_tech else None

    deployment_status = data.get("deployment_status")
    is_valid, validated_status, error = validate_string(
        deployment_status, max_length=50, field_name="deployment_status"
    )
    if not is_valid:
        validation_errors.append(error)

    business_owner = data.get("business_owner")
    is_valid, validated_owner, error = validate_string(
        business_owner, max_length=255, field_name="business_owner"
    )
    if not is_valid:
        validation_errors.append(error)
    else:
        business_owner = sanitize_html(validated_owner) if validated_owner else None

    technical_owner = data.get("technical_owner")
    is_valid, validated_tech_owner, error = validate_string(
        technical_owner, max_length=255, field_name="technical_owner"
    )
    if not is_valid:
        validation_errors.append(error)
    else:
        technical_owner = (
            sanitize_html(validated_tech_owner) if validated_tech_owner else None
        )

    business_purpose = data.get("business_purpose")
    is_valid, validated_purpose, error = validate_string(
        business_purpose, max_length=2000, field_name="business_purpose"
    )
    if not is_valid:
        validation_errors.append(error)
    else:
        business_purpose = (
            sanitize_html(validated_purpose) if validated_purpose else None
        )

    # Return validation errors if any
    if validation_errors:
        if is_json:
            return jsonify({"success": False, "errors": validation_errors}), 400
        for error in validation_errors:
            flash(error, "error")
        return redirect(url_for("unified_applications.application_list"))

    try:
        app = ApplicationComponent(
            name=name,
            description=description,
            application_code=application_code,
            component_type=validated_type,
            criticality=validated_crit,
            technology_stack=technology_stack,
            deployment_status=validated_status,
            business_owner=business_owner,
            technical_owner=technical_owner,
            business_purpose=business_purpose,
        )

        # Capture additional fields if submitted (API calls, expanded forms)
        # Reference: app/applications/routes.py has 90+ field assignments
        optional_fields = [
            "architecture_style",
            "deployment_model",
            "business_domain",
            "application_category",
            "programming_languages",
            "frameworks",
            "primary_database",
            "repository_type",
            "version_control_url",
            "cloud_provider",
            "license_type",
            "integration_pattern",
            "authentication_method",
            "data_classification",
        ]
        for field in optional_fields:
            value = data.get(field)
            if value and hasattr(app, field):
                setattr(app, field, sanitize_html(value))

        # Capture numeric cost fields if submitted
        cost_fields = [
            "license_cost_annual",
            "infrastructure_cost_monthly",
            "maintenance_cost_annual",
            "total_cost_of_ownership",
        ]
        for field in cost_fields:
            value = data.get(field)
            if value and hasattr(app, field):
                try:
                    setattr(app, field, float(value))
                except (ValueError, TypeError):
                    logger.exception("Failed to operation")
                    pass

        db.session.add(app)
        db.session.commit()

        if is_json:
            return jsonify({"success": True, "id": app.id, "name": app.name}), 201

        flash("Application created successfully!", "success")
        return redirect(
            url_for(
                "unified_applications.application_detail", id=app.id, tab="architecture"
            )
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Error creating application: %s", e, exc_info=True)
        if is_json:
            return jsonify({"success": False, "errors": ["An internal error occurred. Please try again."]}), 500
        flash("Error creating application. Please try again.", "error")
        return redirect(url_for("unified_applications.application_list"))


@unified_applications_bp.route("/<int:id>")
@login_required
def application_detail(id):
    """Application Detail — canonical URL at /applications/<id>."""
    from app.application_mgmt.routes import render_application_detail

    return render_application_detail(id)


@unified_applications_bp.route("/<int:id>/generate-archimate", methods=["POST"])
@login_required
@rate_limit(10, "1h")  # LLM-003: Limit expensive AI operations to 10/hour
def generate_application_archimate(id):
    """
    Generate ArchiMate 3.2 application-layer elements for an application using existing AI service.
    Reuses ArchiMateLLMService.generate_archimate_from_requirements (target_layer='application').
    """
    # Check LLM availability before attempting generation (LLM-002: Graceful degradation)
    from app.services.llm_service import LLMService

    if not LLMService.is_available():
        flash(
            "AI features are temporarily unavailable. LLM provider is not configured. "
            "Please contact your administrator to configure an AI provider.",
            "warning",
        )
        return redirect(url_for("unified_applications.application_detail", id=id))

    app_obj = ApplicationComponent.query.get_or_404(id)

    try:
        app_arch_element = None
        arch_model = None

        if app_obj.archimate_element_id:
            app_arch_element = db.session.get(
                ArchiMateElement, app_obj.archimate_element_id
            )
            arch_model = (
                db.session.get(ArchitectureModel, app_arch_element.architecture_id)
                if app_arch_element
                else None
            )

        if arch_model is None:
            arch_model = ArchitectureModel(
                name=f"{app_obj.name} Architecture",
                model_data=json.dumps(
                    {
                        "generated_for": app_obj.name,
                        "generated_at": datetime.utcnow().isoformat(),
                    }
                ),
            )
            db.session.add(arch_model)
            db.session.flush()

        if app_arch_element is None:
            app_arch_element = ArchiMateElement(
                name=app_obj.name,
                type="ApplicationComponent",
                layer="application",
                description=app_obj.description or "",
                architecture_id=arch_model.id,
            )
            db.session.add(app_arch_element)
            db.session.flush()
            app_obj.archimate_element_id = app_arch_element.id
        else:
            if not app_arch_element.architecture_id:
                app_arch_element.architecture_id = arch_model.id
                db.session.add(app_arch_element)

        requirement_lines = [
            f"Application: {app_obj.name}",
            f"Description: {app_obj.description or 'N/A'}",
            f"Component Type: {app_obj.component_type or 'N/A'}",
            f"Business Domain: {app_obj.business_domain or 'N/A'}",
            f"Technology Stack: {app_obj.technology_stack or 'N/A'}",
            f"Deployment Status: {app_obj.deployment_status or 'N/A'}",
        ]
        requirements_text = "\n".join(requirement_lines)

        llm_service = ArchiMateLLMService()
        model_data, _ = llm_service.generate_archimate_from_requirements(
            requirements=requirements_text,
            context="Generate ArchiMate 3.2 application layer elements for this single application.",
            model_name=f"{app_obj.name} Application Layer",
            validate=True,
            target_layer="application",
        )

        if model_data.get("error"):
            db.session.rollback()
            flash(f"AI ArchiMate generation failed: {model_data.get('error')}", "error")
            return redirect(url_for("unified_applications.application_detail", id=id))

        elements = model_data.get("elements", []) or []
        relationships = model_data.get("relationships", []) or []

        element_id_map = {}

        for elem in elements:
            elem_type = elem.get("type")
            if elem_type == "ApplicationComponent":
                continue

            arch_elem = ArchiMateElement(
                name=elem.get("name"),
                type=elem_type,
                layer=elem.get("layer", "application"),
                description=elem.get("description", ""),
                properties=json.dumps(elem.get("properties", {}))
                if elem.get("properties")
                else None,
                architecture_id=arch_model.id,
            )
            db.session.add(arch_elem)
            db.session.flush()

            element_id_map[elem.get("name")] = arch_elem.id

            db.session.add(
                ArchiMateRelationship(
                    type="composition",
                    source_id=app_arch_element.id,
                    target_id=arch_elem.id,
                    architecture_id=arch_model.id,
                )
            )

            if elem_type == "ApplicationService":
                db.session.add(
                    ApplicationService(
                        name=arch_elem.name,
                        description=arch_elem.description,
                        application_component_id=app_obj.id,
                        archimate_element_id=arch_elem.id,
                    )
                )
            elif elem_type == "ApplicationFunction":
                db.session.add(
                    ApplicationFunction(
                        name=arch_elem.name,
                        description=arch_elem.description,
                        application_component_id=app_obj.id,
                        archimate_element_id=arch_elem.id,
                    )
                )
            elif elem_type == "ApplicationProcess":
                db.session.add(
                    ApplicationProcess(
                        name=arch_elem.name,
                        description=arch_elem.description,
                        application_component_id=app_obj.id,
                        archimate_element_id=arch_elem.id,
                    )
                )
            elif elem_type == "ApplicationInteraction":
                db.session.add(
                    ApplicationInteraction(
                        name=arch_elem.name,
                        description=arch_elem.description,
                        application_component_id=app_obj.id,
                        archimate_element_id=arch_elem.id,
                    )
                )
            elif elem_type == "ApplicationEvent":
                db.session.add(
                    ApplicationEvent(
                        name=arch_elem.name,
                        description=arch_elem.description,
                        application_component_id=app_obj.id,
                        archimate_element_id=arch_elem.id,
                    )
                )
            elif elem_type == "ApplicationCollaboration":
                db.session.add(
                    ApplicationCollaboration(
                        name=arch_elem.name,
                        description=arch_elem.description,
                        application_component_id=app_obj.id,
                        archimate_element_id=arch_elem.id,
                    )
                )
            elif elem_type == "ApplicationInterface":
                db.session.add(
                    ApplicationInterface(
                        name=arch_elem.name,
                        description=arch_elem.description,
                        application_component_id=app_obj.id,
                        archimate_element_id=arch_elem.id,
                    )
                )
            elif elem_type == "DataObject":
                db.session.add(
                    DataObject(
                        name=arch_elem.name,
                        description=arch_elem.description,
                        application_component_id=app_obj.id,
                        archimate_element_id=arch_elem.id,
                    )
                )

        for rel in relationships:
            source_name = rel.get("source_name") or rel.get("source")
            target_name = rel.get("target_name") or rel.get("target")
            rel_type = rel.get("type")
            source_id = element_id_map.get(source_name) or (
                app_arch_element.id if source_name == app_arch_element.name else None
            )
            target_id = element_id_map.get(target_name) or (
                app_arch_element.id if target_name == app_arch_element.name else None
            )

            if source_id and target_id and rel_type:
                db.session.add(
                    ArchiMateRelationship(
                        type=rel_type,
                        source_id=source_id,
                        target_id=target_id,
                        architecture_id=arch_model.id,
                    )
                )

        db.session.commit()
        flash("AI ArchiMate application-layer elements generated.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            f"Error generating ArchiMate elements for application {id}: {exc}"
        )
        flash(f"Unable to generate ArchiMate elements: {exc}", "error")

    return redirect(url_for("unified_applications.application_detail", id=id))


@unified_applications_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@audit_log("application_update")
def application_edit(id):
    """Edit Application - ALWAYS returns HTML"""
    try:
        app = ApplicationComponent.query.get_or_404(id)

        if request.method == "POST":
            # Optimistic locking: check if another user modified the record
            submitted_timestamp = request.form.get("updated_at")
            if submitted_timestamp and app.updated_at:
                if app.updated_at.isoformat() != submitted_timestamp:
                    flash(
                        "This record was modified by another user. "
                        "Please reload and try again.",
                        "warning",
                    )
                    return redirect(
                        url_for("unified_applications.application_edit", id=id)
                    )

            # Update application with input validation (matching create route)
            validation_errors = []

            # Validate name
            name = request.form.get("name")
            if name is not None:
                is_valid, validated_name, error = validate_application_name(name)
                if not is_valid:
                    validation_errors.append(error)
                else:
                    app.name = sanitize_html(validated_name)

            # Validate description
            description = request.form.get("description")
            if description is not None:
                is_valid, validated_desc, error = validate_description(description)
                if not is_valid:
                    validation_errors.append(error)
                else:
                    app.description = (
                        sanitize_html(validated_desc) if validated_desc else None
                    )

            # Validate application_code
            application_code = request.form.get("application_code")
            if application_code is not None:
                is_valid, validated_code, error = validate_string(
                    application_code, max_length=50, field_name="application_code"
                )
                if not is_valid:
                    validation_errors.append(error)
                else:
                    app.application_code = (
                        sanitize_html(validated_code) if validated_code else None
                    )

            # Validate application_type
            component_type = request.form.get("application_type")
            if component_type is not None:
                is_valid, validated_type, error = validate_string(
                    component_type, max_length=100, field_name="application_type"
                )
                if not is_valid:
                    validation_errors.append(error)
                else:
                    app.component_type = validated_type

            # Validate criticality
            criticality = request.form.get("criticality")
            if criticality is not None:
                is_valid, validated_crit, error = validate_string(
                    criticality, max_length=50, field_name="criticality"
                )
                if not is_valid:
                    validation_errors.append(error)
                else:
                    app.business_criticality = validated_crit

            # Validate technology_stack
            technology_stack = request.form.get("technology_stack")
            if technology_stack is not None:
                is_valid, validated_tech, error = validate_string(
                    technology_stack, max_length=500, field_name="technology_stack"
                )
                if not is_valid:
                    validation_errors.append(error)
                else:
                    app.technology_stack = (
                        sanitize_html(validated_tech) if validated_tech else None
                    )

            # Validate deployment_status
            deployment_status = request.form.get("deployment_status")
            if deployment_status is not None:
                is_valid, validated_status, error = validate_string(
                    deployment_status, max_length=50, field_name="deployment_status"
                )
                if not is_valid:
                    validation_errors.append(error)
                else:
                    app.deployment_status = validated_status

            # Validate business_owner
            business_owner = request.form.get("business_owner")
            if business_owner is not None:
                is_valid, validated_owner, error = validate_string(
                    business_owner, max_length=255, field_name="business_owner"
                )
                if not is_valid:
                    validation_errors.append(error)
                else:
                    app.business_owner = (
                        sanitize_html(validated_owner) if validated_owner else None
                    )

            # Validate technical_owner
            technical_owner = request.form.get("technical_owner")
            if technical_owner is not None:
                is_valid, validated_tech_owner, error = validate_string(
                    technical_owner, max_length=255, field_name="technical_owner"
                )
                if not is_valid:
                    validation_errors.append(error)
                else:
                    app.technical_owner = (
                        sanitize_html(validated_tech_owner)
                        if validated_tech_owner
                        else None
                    )

            # Validate business_purpose
            business_purpose = request.form.get("business_purpose")
            if business_purpose is not None:
                is_valid, validated_purpose, error = validate_string(
                    business_purpose, max_length=2000, field_name="business_purpose"
                )
                if not is_valid:
                    validation_errors.append(error)
                else:
                    app.business_purpose = (
                        sanitize_html(validated_purpose) if validated_purpose else None
                    )

            # Return validation errors if any
            if validation_errors:
                for error in validation_errors:
                    flash(error, "error")
                return render_template("applications/edit.html", application=app), 400

            # Capture additional fields if submitted (API calls, expanded forms)
            optional_fields = [
                "architecture_style",
                "deployment_model",
                "business_domain",
                "application_category",
                "programming_languages",
                "frameworks",
                "primary_database",
                "repository_type",
                "version_control_url",
                "cloud_provider",
                "license_type",
                "integration_pattern",
                "authentication_method",
                "data_classification",
            ]
            for field in optional_fields:
                value = request.form.get(field)
                if value is not None and hasattr(app, field):
                    setattr(app, field, sanitize_html(value))

            cost_fields = [
                "license_cost_annual",
                "infrastructure_cost_monthly",
                "maintenance_cost_annual",
                "total_cost_of_ownership",
            ]
            for field in cost_fields:
                value = request.form.get(field)
                if value is not None and hasattr(app, field):
                    try:
                        setattr(app, field, float(value) if value else None)
                    except (ValueError, TypeError):
                        logger.exception("Failed to operation")
                        pass

            app.updated_by = current_user.id

            db.session.commit()

            flash("Application updated successfully!", "success")
            return redirect(
                url_for(
                    "unified_applications.application_detail",
                    id=app.id,
                    tab="architecture",
                )
            )

        return render_template("applications/edit.html", application=app)

    except Exception as e:
        db.session.rollback()
        flash("Error updating application. Please try again.", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))


@unified_applications_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
@require_roles("admin", "architect")
@audit_log("application_delete")
def application_delete(id):
    """Delete Application - returns JSON for AJAX requests, HTML redirect otherwise"""
    is_ajax = request.is_json or request.content_type == "application/json"
    try:
        app = ApplicationComponent.query.get_or_404(id)
        app_name = app.name

        # Clean up related records first to avoid FK constraint errors
        _cleanup_application_relationships(id)
        db.session.delete(app)
        db.session.commit()

        if is_ajax:
            return jsonify(
                {"success": True, "message": f"Application '{app_name}' deleted"}
            ), 200

        flash("Application deleted successfully!", "success")
        return redirect(url_for("unified_applications.application_list"))

    except Exception as e:
        db.session.rollback()
        if is_ajax:
            return jsonify(
                {"success": False, "error": "An internal error occurred"}
            ), 500

        flash("Error deleting application. Please try again.", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))


@unified_applications_bp.route("/bulk-delete", methods=["POST"])
@login_required
@require_roles("admin")
@audit_log("application_bulk_delete")
@rate_limit(5, "1m")
def bulk_delete_applications():
    """Bulk delete multiple applications - Returns JSON"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Accept both 'ids' and 'app_ids' for flexibility
        ids = data.get("ids") or data.get("app_ids", [])
        if not ids:
            return jsonify(
                {"success": False, "error": "No application IDs provided"}
            ), 400

        deleted_count = 0
        errors = []

        # OPTIMIZATION: Batch-prefetch application objects to avoid N+1 queries
        _bulk_apps = ApplicationComponent.query.filter(
            ApplicationComponent.id.in_(ids)
        ).all()
        _bulk_apps_by_id = {a.id: a for a in _bulk_apps}

        for app_id in ids:
            try:
                app = _bulk_apps_by_id.get(app_id)
                if app:
                    # Clean up related records first to avoid FK constraint errors
                    _cleanup_application_relationships(app_id)
                    db.session.delete(app)
                    db.session.commit()
                    deleted_count += 1
                else:
                    errors.append(f"Application {app_id} not found")
            except Exception as e:
                db.session.rollback()
                errors.append(f"Error deleting application {app_id}")
                current_app.logger.error(f"Error deleting app {app_id}: {e}")

        all_failed = deleted_count == 0 and len(errors) > 0
        return jsonify(
            {
                "success": not all_failed,
                "deleted": deleted_count,
                "deleted_count": deleted_count,  # Alias for compatibility
                "errors": errors,
                "message": f"Successfully deleted {deleted_count} application(s)",
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Bulk delete error: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_applications_bp.route("/api/<int:app_id>", methods=["DELETE"])
@login_required
@require_roles("admin", "architect")
@audit_log("application_delete")
def api_delete_application(app_id):
    """API endpoint for deleting an application"""
    try:
        app = ApplicationComponent.query.get_or_404(app_id)

        # Clean up related records first to avoid FK constraint errors
        _cleanup_application_relationships(app_id)
        db.session.delete(app)
        db.session.commit()

        return jsonify(
            {"success": True, "message": f"Application {app.name} deleted successfully"}
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting application {app_id}: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_applications_bp.route("/api/bulk-consolidate", methods=["POST"])
@login_required
@require_roles("admin", "architect")
@audit_log("application_consolidate")
def api_bulk_consolidate():
    """API endpoint for bulk consolidating applications"""
    try:
        data = request.get_json()

        # Validate JSON payload
        if data is None:
            return validation_error_response("Request body is required")

        # Validate application_ids field
        application_ids = data.get("application_ids", [])

        # Validate it's a list
        if not isinstance(application_ids, list):
            return validation_error_response("application_ids must be a list")

        if not application_ids:
            return validation_error_response("No application IDs provided")

        # Validate each ID is a positive integer
        validated_ids = []
        for idx, app_id in enumerate(application_ids):
            is_valid, validated_id, error = validate_integer(
                app_id, min_val=1, field_name=f"application_ids[{idx}]"
            )
            if not is_valid:
                return validation_error_response(error)
            validated_ids.append(validated_id)

        # Limit maximum number of IDs to prevent abuse
        if len(validated_ids) > 1000:
            return validation_error_response(
                "Cannot consolidate more than 1000 applications at once"
            )

        # Get applications to consolidate
        applications = ApplicationComponent.query.filter(
            ApplicationComponent.id.in_(validated_ids)
        ).all()

        if not applications:
            return jsonify(
                {"success": False, "error": "No valid applications found"}
            ), 404

        # Add applications to the consolidation list
        from app.models.consolidation_list import ConsolidationListEntry

        # Batch prefetch existing pending consolidation entries for all apps
        app_ids = [a.id for a in applications]
        existing_pending_entries = set()
        if app_ids:
            existing_entries = ConsolidationListEntry.query.filter(
                ConsolidationListEntry.application_id.in_(app_ids),
                ConsolidationListEntry.status == "pending",
            ).all()
            existing_pending_entries = {e.application_id for e in existing_entries}

        added_count = 0
        skipped_count = 0
        for app in applications:
            # Check if already in consolidation list (using prefetched data)
            if app.id in existing_pending_entries:
                skipped_count += 1
                continue

            entry = ConsolidationListEntry(
                application_id=app.id,
                source_type="bulk_consolidation",
                recommended_action="pending_review",
                priority="medium",
                added_by=current_user.username
                if current_user.is_authenticated
                else "system",
            )
            db.session.add(entry)
            added_count += 1

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": f"Added {added_count} applications to consolidation list ({skipped_count} already listed)",
                "consolidated_count": added_count,
                "skipped_count": skipped_count,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error in bulk consolidate: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# ═══════════════════════════════════════════════════════════════════
# AI-Suggested Capability Mappings
# Pattern-matches from 410 existing verified mappings — no LLM needed
# ═══════════════════════════════════════════════════════════════════


@unified_applications_bp.route("/<int:id>/suggest-capabilities", methods=["GET"])
@login_required
def suggest_capabilities(id):
    """Suggest capability mappings for an application based on existing verified mappings.

    Strategy:
    1. Domain match — apps in the same business_domain share capabilities
    2. Name/description keyword overlap with capability names
    3. Vendor match — apps from the same vendor share capabilities

    Returns ranked suggestions with confidence scores and evidence.
    """
    from sqlalchemy import func
    from app.models.application_capability import ApplicationCapabilityMapping
    from app.models.business_capabilities import BusinessCapability

    app_obj = ApplicationComponent.query.get_or_404(id)

    # Get capabilities already mapped to this app (exclude from suggestions)
    existing_cap_ids = set(
        r[0] for r in db.session.query(ApplicationCapabilityMapping.business_capability_id)
        .filter_by(application_component_id=id).all()
    )

    # ── Signal 1: Domain match ────────────────────────────────────
    # Find capabilities mapped to OTHER apps in the same business_domain
    domain_scores = {}
    if app_obj.business_domain:
        domain_apps = ApplicationComponent.query.filter(
            ApplicationComponent.business_domain == app_obj.business_domain,
            ApplicationComponent.id != id,
        ).with_entities(ApplicationComponent.id).all()
        domain_app_ids = [a[0] for a in domain_apps]

        if domain_app_ids:
            domain_mappings = (
                db.session.query(
                    ApplicationCapabilityMapping.business_capability_id,
                    func.count().label("cnt"),
                )
                .filter(ApplicationCapabilityMapping.application_component_id.in_(domain_app_ids))
                .group_by(ApplicationCapabilityMapping.business_capability_id)
                .all()
            )
            for cap_id, cnt in domain_mappings:
                if cap_id not in existing_cap_ids:
                    domain_scores[cap_id] = {
                        "domain_count": cnt,
                        "domain_total": len(domain_app_ids),
                    }

    # ── Signal 2: Name/description keyword overlap ────────────────
    # Extract keywords from app name + description, match against capability names
    keyword_scores = {}
    app_text = ((app_obj.name or "") + " " + (app_obj.description or "")).lower()
    app_words = set(w for w in app_text.split() if len(w) > 4 and w not in {
        "saint", "gobain", "sgbd", "application", "system", "platform", "module",
        "service", "which", "their", "about", "other", "these", "being", "there",
    })

    if app_words:
        all_capabilities = BusinessCapability.query.limit(2000).all()
        for cap in all_capabilities:
            if cap.id in existing_cap_ids:
                continue
            cap_text = ((cap.name or "") + " " + (cap.description or "")).lower()
            matches = [w for w in app_words if w in cap_text]
            if matches:
                keyword_scores[cap.id] = {
                    "keyword_matches": matches[:5],
                    "keyword_count": len(matches),
                }

    # ── Signal 3: Vendor match ────────────────────────────────────
    # Find capabilities mapped to apps from the same vendor
    vendor_scores = {}
    vendor_name = getattr(app_obj, "vendor_name", None) or ""
    if vendor_name:
        vendor_apps = ApplicationComponent.query.filter(
            ApplicationComponent.vendor_name == vendor_name,
            ApplicationComponent.id != id,
        ).with_entities(ApplicationComponent.id).all()
        vendor_app_ids = [a[0] for a in vendor_apps]

        if vendor_app_ids:
            vendor_mappings = (
                db.session.query(
                    ApplicationCapabilityMapping.business_capability_id,
                    func.count().label("cnt"),
                )
                .filter(ApplicationCapabilityMapping.application_component_id.in_(vendor_app_ids))
                .group_by(ApplicationCapabilityMapping.business_capability_id)
                .all()
            )
            for cap_id, cnt in vendor_mappings:
                if cap_id not in existing_cap_ids:
                    vendor_scores[cap_id] = {
                        "vendor_count": cnt,
                        "vendor_name": vendor_name,
                    }

    # ── Combine signals and rank ──────────────────────────────────
    all_cap_ids = set(domain_scores) | set(keyword_scores) | set(vendor_scores)

    suggestions = []
    for cap_id in all_cap_ids:
        cap = BusinessCapability.query.get(cap_id)
        if not cap:
            continue

        signals = []
        score = 0

        d = domain_scores.get(cap_id)
        if d:
            pct = round(d["domain_count"] / max(d["domain_total"], 1) * 100)
            signals.append(f"{d['domain_count']} of {d['domain_total']} apps in '{app_obj.business_domain}' domain map here ({pct}%)")
            score += min(d["domain_count"], 5) * 2  # max 10 from domain

        k = keyword_scores.get(cap_id)
        if k:
            signals.append(f"Keywords match: {', '.join(k['keyword_matches'])}")
            score += min(k["keyword_count"], 3) * 2  # max 6 from keywords

        v = vendor_scores.get(cap_id)
        if v:
            signals.append(f"{v['vendor_count']} other {v['vendor_name']} apps map here")
            score += min(v["vendor_count"], 3) * 2  # max 6 from vendor

        # Normalize to 0-100 confidence
        confidence = min(score * 5, 95)  # Cap at 95 — human verification always needed

        suggestions.append({
            "capability_id": cap.id,
            "capability_name": cap.name,
            "capability_level": getattr(cap, "level", None),
            "capability_domain": getattr(cap, "domain", None),
            "confidence": confidence,
            "signals": signals,
            "signal_count": len(signals),
        })

    # Sort by confidence descending, limit to top 10
    suggestions.sort(key=lambda s: -s["confidence"])
    suggestions = suggestions[:10]

    return jsonify({
        "success": True,
        "application_id": id,
        "application_name": app_obj.name,
        "existing_mappings": len(existing_cap_ids),
        "suggestions": suggestions,
    })


@unified_applications_bp.route("/<int:id>/accept-capability-suggestion", methods=["POST"])
@login_required
def accept_capability_suggestion(id):
    """Accept an AI-suggested capability mapping — creates the ApplicationCapabilityMapping record."""
    from flask_login import current_user
    from app.models.application_capability import ApplicationCapabilityMapping

    app_obj = ApplicationComponent.query.get_or_404(id)
    data = request.get_json() or {}
    cap_id = data.get("capability_id")
    confidence = data.get("confidence", 0)

    if not cap_id:
        return jsonify({"success": False, "error": "capability_id required"}), 400

    # Check if already mapped
    existing = ApplicationCapabilityMapping.query.filter_by(
        application_component_id=id, business_capability_id=cap_id
    ).first()
    if existing:
        return jsonify({"success": False, "error": "Already mapped"}), 409

    mapping = ApplicationCapabilityMapping(
        application_component_id=id,
        business_capability_id=cap_id,
        support_level="partial",
        relationship_type="supports",
        discovered_by_ai=True,
        discovery_confidence=confidence / 100.0,
        discovery_source="pattern_matching",
        confidence_score=confidence,
        assessment_status="draft",
        is_active=True,
        created_by_id=getattr(current_user, "id", None),
    )
    db.session.add(mapping)
    db.session.commit()

    return jsonify({
        "success": True,
        "mapping_id": mapping.id,
        "message": f"Mapped to capability #{cap_id}",
    })
