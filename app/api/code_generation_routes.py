"""
Code Generation API Routes

Provides REST API endpoints for MDD code generation functionality.
"""
import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.decorators import audit_log
from app.models import Application, ApplicationComponent
from app.services.mdd_code_generation_service import (
    MDDCodeGenerationService,
    TechnologyStack,
    UMLElement,
)

logger = logging.getLogger(__name__)

code_generation_bp = Blueprint("code_generation", __name__, url_prefix="/code-generation")


@code_generation_bp.route("/dashboard")
@login_required
def dashboard():
    """
    Main code generation dashboard.
    ---
    tags:
      - Code Generation
    summary: Code generation dashboard
    description: Main UI for MDD code generation
    parameters:
      - name: mode
        in: query
        type: string
        enum: [enhancement, architecture]
        description: Generation mode
      - name: app_id
        in: query
        type: integer
        description: Application ID for enhancement mode
      - name: view_id
        in: query
        type: integer
        description: ArchiMate view ID for architecture mode
    responses:
      200:
        description: Dashboard page
    """
    mode = request.args.get("mode", "enhancement")
    app_id = request.args.get("app_id", type=int)
    view_id = request.args.get("view_id", type=int)

    context = {"mode": mode, "app_id": app_id, "view_id": view_id}

    return render_template("code_generation/dashboard.html", **context)


@code_generation_bp.route("/api/generate", methods=["POST"])
@login_required
@audit_log("code_generate")
def generate_code():
    """
    Generate code from UML/model.
    ---
    tags:
      - Code Generation
    summary: Generate code artifacts
    description: Generate code from UML elements using hybrid template + LLM approach
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            elements:
              type: array
              items:
                type: object
              description: UML elements to generate code from
            technology_stack:
              type: object
              properties:
                primary_language:
                  type: string
                  enum: [python, java, typescript, javascript, salesforce]
                framework:
                  type: string
                primary_database:
                  type: string
              description: Technology stack configuration
            mode:
              type: string
              enum: [enhancement, architecture]
              description: Generation mode
            context_id:
              type: integer
              description: Application or View ID for context
    responses:
      200:
        description: Generated code artifacts
        schema:
          type: object
          properties:
            success:
              type: boolean
            artifacts:
              type: array
              items:
                type: object
            message:
              type: string
      400:
        description: Invalid input
      500:
        description: Generation failed
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Extract parameters
        elements_data = data.get("elements", [])
        tech_stack_data = data.get("technology_stack", {})
        mode = data.get("mode", "enhancement")
        context_id = data.get("context_id")

        # Validate required fields
        if not elements_data:
            return jsonify({"success": False, "error": "No UML elements provided"}), 400

        if not tech_stack_data.get("primary_language"):
            return jsonify({"success": False, "error": "Primary language is required"}), 400

        # Create UML elements
        uml_elements = []
        for elem_data in elements_data:
            element = UMLElement(
                name=elem_data.get("name", "UnnamedElement"),
                element_type=elem_data.get("element_type", "class"),
                stereotype=elem_data.get("stereotype"),
                package=elem_data.get("package"),
                description=elem_data.get("description"),
            )

            # Add attributes
            for attr in elem_data.get("attributes", []):
                element.add_attribute(
                    name=attr.get("name"),
                    data_type=attr.get("data_type", "String"),
                    visibility=attr.get("visibility", "private"),
                    default_value=attr.get("default_value"),
                )

            # Add methods
            for method in elem_data.get("methods", []):
                element.add_method(
                    name=method.get("name"),
                    return_type=method.get("return_type", "void"),
                    parameters=method.get("parameters", ""),
                    visibility=method.get("visibility", "public"),
                    is_constructor=method.get("is_constructor", False),
                )

            uml_elements.append(element)

        # Create technology stack
        technology_stack = TechnologyStack(
            primary_language=tech_stack_data.get("primary_language"),
            framework=tech_stack_data.get("framework"),
            primary_database=tech_stack_data.get("primary_database", "postgresql"),
        )

        # Generate code
        artifacts = MDDCodeGenerationService.generate_from_uml(
            uml_elements=uml_elements,
            technology_stack=technology_stack,
            architecture_context={"mode": mode, "context_id": context_id},
        )

        # Format response
        artifacts_data = []
        for artifact in artifacts:
            artifacts_data.append(
                {
                    "name": artifact.name,
                    "type": artifact.type,
                    "language": artifact.language,
                    "content": artifact.content,
                    "metadata": artifact.metadata,
                    "created_at": artifact.created_at.isoformat(),
                }
            )

        logger.info(f"Generated {len(artifacts)} code artifacts for user {current_user.id}")

        return (
            jsonify(
                {
                    "success": True,
                    "artifacts": artifacts_data,
                    "message": f"Successfully generated {len(artifacts)} code artifacts",
                }
            ),
            200,
        )

    except ValueError as e:
        logger.error(f"Validation error in code generation: {str(e)}")
        return jsonify({"success": False, "error": "Invalid request parameters"}), 400
    except Exception as e:
        logger.error(f"Code generation failed: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@code_generation_bp.route("/api/validate", methods=["POST"])
@login_required
@audit_log("code_validate")
def validate_code():
    """
    Validate generated code.
    ---
    tags:
      - Code Generation
    summary: Validate code artifacts
    description: Validate generated code for syntax and quality
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            code:
              type: string
              description: Code content to validate
            language:
              type: string
              description: Programming language
            filename:
              type: string
              description: File name
    responses:
      200:
        description: Validation results
        schema:
          type: object
          properties:
            success:
              type: boolean
            valid:
              type: boolean
            errors:
              type: array
            warnings:
              type: array
            metrics:
              type: object
      400:
        description: Invalid input
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        code = data.get("code")
        language = data.get("language")
        filename = data.get("filename", "unknown")

        if not code or not language:
            return jsonify({"success": False, "error": "Code and language are required"}), 400

        # Import validation service
        from app.services.code_validator import validate_code_artifact

        # Validate code
        validation_result = validate_code_artifact(code, language, filename)

        return (
            jsonify(
                {
                    "success": True,
                    "valid": validation_result.is_valid,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "metrics": validation_result.metrics,
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Code validation failed: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@code_generation_bp.route("/api/templates")
@login_required
def list_templates():
    """
    List available code templates.
    ---
    tags:
      - Code Generation
    summary: List available templates
    description: Get list of available code generation templates by language
    parameters:
      - name: language
        in: query
        type: string
        description: Filter by programming language
    responses:
      200:
        description: List of templates
        schema:
          type: object
          properties:
            success:
              type: boolean
            templates:
              type: object
              additionalProperties:
                type: array
                items:
                  type: string
    """
    try:
        import os

        from flask import current_app

        language_filter = request.args.get("language")

        templates_base = os.path.join(current_app.root_path, "services", "code_templates")

        templates = {}

        # Scan template directories
        if os.path.exists(templates_base):
            for language_dir in os.listdir(templates_base):
                language_path = os.path.join(templates_base, language_dir)

                if os.path.isdir(language_path):
                    if language_filter and language_dir != language_filter:
                        continue

                    template_files = [f for f in os.listdir(language_path) if f.endswith(".j2")]

                    templates[language_dir] = template_files

        return jsonify({"success": True, "templates": templates}), 200

    except Exception as e:
        logger.error(f"Failed to list templates: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@code_generation_bp.route("/api/context/application/<int:app_id>")
@login_required
def get_application_context(app_id):
    """
    Get application context for code generation.
    ---
    tags:
      - Code Generation
    summary: Get application context
    description: Load application data for enhancement mode
    parameters:
      - name: app_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Application context
      404:
        description: Application not found
    """
    try:
        application = Application.query.get(app_id)
        if not application:
            return jsonify({"success": False, "error": "Application not found"}), 404

        # Application and ApplicationComponent map to the same table
        # (application_components); there is no application_id FK / sub-component
        # decomposition, so the closest real breakdown is the app's software modules.
        components = list(getattr(application, "software_modules", []) or [])

        context = {
            "success": True,
            "application": {
                "id": application.id,
                "name": application.name,
                "description": application.description,
                "technology_stack": getattr(application, "technology_stack", None),
                "components": [
                    {
                        "id": comp.id,
                        "name": getattr(comp, "name", None),
                        "type": getattr(comp, "component_type", None) or getattr(comp, "module_type", None),
                        "description": getattr(comp, "description", None),
                    }
                    for comp in components
                ],
            },
        }

        return jsonify(context), 200

    except Exception as e:
        logger.error(f"Failed to get application context: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@code_generation_bp.route("/api/context/architecture/<int:view_id>")
@login_required
def get_architecture_context(view_id):
    """
    Get architecture context for code generation.
    ---
    tags:
      - Code Generation
    summary: Get architecture context
    description: Load ArchiMate view data for architecture mode
    parameters:
      - name: view_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Architecture context
      404:
        description: View not found
    """
    try:
        # Import ArchiMate models
        from app.models.archimate import ArchiMateView

        view = ArchiMateView.query.get(view_id)
        if not view:
            return jsonify({"success": False, "error": "ArchiMate view not found"}), 404

        context = {
            "success": True,
            "view": {
                "id": view.id,
                "name": view.name,
                "viewpoint": view.viewpoint,
                "description": view.description,
                "elements": [],
            },
        }

        return jsonify(context), 200

    except Exception as e:
        logger.error(f"Failed to get architecture context: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@code_generation_bp.route("/api/health")
@login_required
def health_check():
    """
    Health check endpoint.
    ---
    tags:
      - Code Generation
    summary: Health check
    description: Check if code generation service is available
    responses:
      200:
        description: Service is healthy
    """
    return jsonify({"success": True, "service": "code_generation", "status": "healthy"}), 200
