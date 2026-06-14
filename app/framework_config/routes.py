"""
Framework Configuration UI Component

shadcn/ui compliant interface for framework configuration management.
Provides configuration-driven capability management with industry extensions.

Features:
- Framework configuration wizard
- Extension management interface
- Template selection and deployment
- Configuration validation
- Migration support
"""

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import login_required

from app import db
from app.models.framework_configuration import (
    CapabilityFrameworkConfiguration,
    FrameworkConfigurationTemplate,
    FrameworkExtension,
    FrameworkInstance,
    FrameworkMigrationMapping,
)
from app.services.framework_configuration_service import (
    FrameworkConfigurationService,
    FrameworkExtensionService,
    FrameworkValidationService,
)

framework_config_ui_bp = Blueprint(
    "framework_config_ui", __name__, url_prefix="/framework-config"
)


@framework_config_ui_bp.route("/")
@login_required
def framework_config_dashboard():
    """Framework configuration dashboard"""
    try:
        # Get active configuration
        active_config = FrameworkConfigurationService.get_active_configuration()

        # Get available templates
        templates = FrameworkConfigurationTemplate.query.filter_by(
            status="active"
        ).all()

        # Get available extensions
        extensions = FrameworkExtension.query.filter_by(status="active").all()

        # Get recent configurations
        recent_configs = (
            CapabilityFrameworkConfiguration.query.order_by(
                CapabilityFrameworkConfiguration.created_at.desc()
            )
            .limit(10)
            .all()
        )

        return render_template(
            "framework_config/dashboard.html",
            active_config=active_config,
            templates=templates,
            extensions=extensions,
            recent_configs=recent_configs,
        )

    except Exception as e:
        current_app.logger.error(f"Error loading framework config dashboard: {str(e)}")
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/configuration/new")
@login_required
def new_configuration():
    """Create new configuration — modal on dashboard handles creation inline"""
    from flask import redirect, url_for

    return redirect(url_for("framework_config_ui.framework_config_dashboard"))


@framework_config_ui_bp.route("/configuration/<int:config_id>")
@login_required
def view_configuration(config_id):
    """View framework configuration details"""
    try:
        configuration = FrameworkConfigurationService.get_configuration_by_id(config_id)

        if not configuration:
            return render_template("framework_config/not_found.html"), 404

        # Get validation results
        validation_result = FrameworkValidationService.validate_configuration(config_id)

        # Get framework instances
        instances = FrameworkInstance.query.filter_by(configuration_id=config_id).all()

        # Get enabled extensions
        enabled_extensions = configuration.get_enabled_extensions()
        extension_details = []
        for ext_code in enabled_extensions:
            extension = FrameworkExtensionService.get_extension_by_code(ext_code)
            if extension:
                extension_details.append(extension)

        return render_template(
            "framework_config/dashboard.html",
            configuration=configuration,
            validation_result=validation_result,
            instances=instances,
            enabled_extensions=extension_details,
        )

    except Exception as e:
        current_app.logger.error(f"Error viewing configuration {config_id}: {str(e)}")
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/configuration/<int:config_id>/edit")
@login_required
def edit_configuration(config_id):
    """Edit framework configuration"""
    try:
        configuration = FrameworkConfigurationService.get_configuration_by_id(config_id)

        if not configuration:
            return render_template("framework_config/not_found.html"), 404

        # Get available extensions
        extensions = FrameworkExtension.query.filter_by(status="active").all()

        return render_template(
            "framework_config/dashboard.html",
            configuration=configuration,
            extensions=extensions,
        )

    except Exception as e:
        current_app.logger.error(f"Error editing configuration {config_id}: {str(e)}")
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/extensions")
@login_required
def extensions():
    """Framework extensions management"""
    try:
        # Get available extensions
        extensions = FrameworkExtension.query.filter_by(status="active").all()

        # Group by category
        extensions_by_category = {}
        for extension in extensions:
            category = extension.extension_category or "other"
            if category not in extensions_by_category:
                extensions_by_category[category] = []
            extensions_by_category[category].append(extension)

        return render_template(
            "framework_config/dashboard.html",
            extensions_by_category=extensions_by_category,
        )

    except Exception as e:
        current_app.logger.error(f"Error loading extensions page: {str(e)}")
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/extensions/<extension_code>")
@login_required
def extension_details(extension_code):
    """Extension details page"""
    try:
        extension = FrameworkExtensionService.get_extension_by_code(extension_code)

        if not extension:
            return render_template("framework_config/not_found.html"), 404

        # Parse additional data
        additional_capabilities = []
        if extension.additional_capabilities:
            import json

            additional_capabilities = json.loads(extension.additional_capabilities)

        additional_kpis = []
        if extension.additional_kpis:
            additional_kpis = json.loads(extension.additional_kpis)

        return render_template(
            "framework_config/dashboard.html",
            extension=extension,
            additional_capabilities=additional_capabilities,
            additional_kpis=additional_kpis,
        )

    except Exception as e:
        current_app.logger.error(
            f"Error loading extension details {extension_code}: {str(e)}"
        )
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/templates")
@login_required
def templates():
    """Framework configuration templates"""
    try:
        # Get available templates
        templates = FrameworkConfigurationTemplate.query.filter_by(
            status="active"
        ).all()

        # Group by type
        templates_by_type = {}
        for template in templates:
            template_type = template.template_type or "other"
            if template_type not in templates_by_type:
                templates_by_type[template_type] = []
            templates_by_type[template_type].append(template)

        return render_template(
            "framework_config/dashboard.html", templates_by_type=templates_by_type
        )

    except Exception as e:
        current_app.logger.error(f"Error loading templates page: {str(e)}")
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/templates/<int:template_id>")
@login_required
def template_details(template_id):
    """Template details page"""
    try:
        template = FrameworkConfigurationTemplate.query.get(template_id)

        if not template:
            return render_template("framework_config/not_found.html"), 404

        # Parse template configuration
        template_config = {}
        if template.template_configuration:
            import json

            template_config = json.loads(template.template_configuration)

        return render_template(
            "framework_config/dashboard.html",
            template=template,
            template_config=template_config,
        )

    except Exception as e:
        current_app.logger.error(
            f"Error loading template details {template_id}: {str(e)}"
        )
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/instances")
@login_required
def instances():
    """Framework instances management"""
    try:
        # Get framework instances
        instances = FrameworkInstance.query.order_by(
            FrameworkInstance.created_at.desc()
        ).all()

        return render_template("framework_config/instances.html", instances=instances)

    except Exception as e:
        current_app.logger.error(f"Error loading instances page: {str(e)}")
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/instances/<int:instance_id>")
@login_required
def instance_details(instance_id):
    """Instance details page"""
    try:
        instance = FrameworkInstance.query.get(instance_id)

        if not instance:
            return render_template("framework_config/not_found.html"), 404

        return render_template(
            "framework_config/instance_details.html", instance=instance
        )

    except Exception as e:
        current_app.logger.error(
            f"Error loading instance details {instance_id}: {str(e)}"
        )
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/migration")
@login_required
def migration():
    """Framework migration management"""
    try:
        # Get migration mappings
        migrations = FrameworkMigrationMapping.query.order_by(
            FrameworkMigrationMapping.created_at.desc()
        ).all()

        return render_template("framework_config/migration.html", migrations=migrations)

    except Exception as e:
        current_app.logger.error(f"Error loading migration page: {str(e)}")
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/wizard")
@login_required
def configuration_wizard():
    """Configuration wizard step-by-step interface"""
    try:
        # Get available templates
        templates = FrameworkConfigurationTemplate.query.filter_by(
            status="active"
        ).all()

        return render_template(
            "framework_config/dashboard.html",
            templates=templates,
            step=1,
        )

    except Exception as e:
        current_app.logger.error(f"Error loading configuration wizard: {str(e)}")
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/validation")
@login_required
def validation():
    """Framework validation dashboard"""
    try:
        # Get all configurations
        configurations = CapabilityFrameworkConfiguration.query.all()

        # Get validation results for each configuration
        validation_results = {}
        for config in configurations:
            validation_results[config.id] = (
                FrameworkValidationService.validate_configuration(config.id)
            )

        return render_template(
            "framework_config/dashboard.html",
            configurations=configurations,
            validation_results=validation_results,
        )

    except Exception as e:
        current_app.logger.error(f"Error loading validation page: {str(e)}")
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/help")
@login_required
def help():
    """Help and documentation"""
    try:
        return render_template("framework_config/help.html")

    except Exception as e:
        current_app.logger.error(f"Error loading help page: {str(e)}")
        return render_template(
            "framework_config/error.html",
            error="An unexpected error occurred. Please try again.",
        ), 500


@framework_config_ui_bp.route("/api/instances", methods=["GET"])
@login_required
def api_list_framework_instances():
    """List framework instances with pagination, search and sort."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 25, type=int), 100)
    search = request.args.get("q") or request.args.get("search", "")
    sort_by = request.args.get("sort", "instance_name")
    sort_dir = request.args.get("dir", "asc")

    ALLOWED_SORT = {
        "id",
        "instance_name",
        "organization_unit",
        "current_maturity_level",
        "implementation_percentage",
        "status",
        "created_at",
    }
    if sort_by not in ALLOWED_SORT:
        sort_by = "instance_name"

    query = FrameworkInstance.query
    if search:
        term = f"%{search}%"
        query = query.filter(
            FrameworkInstance.instance_name.ilike(term)
            | FrameworkInstance.organization_unit.ilike(term)
        )

    sort_col = getattr(FrameworkInstance, sort_by, FrameworkInstance.instance_name)
    if sort_dir == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    items = []
    for idx, inst in enumerate(paginated.items):
        items.append(
            {
                "id": inst.id,
                "row_number": (page - 1) * per_page + idx + 1,
                "instance_name": inst.instance_name or "",
                "instance_description": inst.instance_description or "",
                "organization_unit": inst.organization_unit or "",
                "current_maturity_level": inst.current_maturity_level or "",
                "implementation_percentage": inst.implementation_percentage or 0,
                "status": inst.status or "",
                "created_at": str(inst.created_at) if inst.created_at else None,
            }
        )

    return jsonify(
        {
            "instances": items,
            "total": paginated.total,
            "page": page,
            "pages": paginated.pages,
            "per_page": per_page,
        }
    )


@framework_config_ui_bp.route("/api/instances/bulk", methods=["DELETE"])
@login_required
def api_bulk_delete_framework_instances():
    """Bulk delete framework instances by ID list."""
    data = request.get_json() or {}
    ids = data.get("ids", [])
    if not ids or not isinstance(ids, list):
        return jsonify({"error": "ids list required"}), 400
    deleted = FrameworkInstance.query.filter(FrameworkInstance.id.in_(ids)).delete(
        synchronize_session=False
    )
    db.session.commit()
    return jsonify({"deleted": deleted})
