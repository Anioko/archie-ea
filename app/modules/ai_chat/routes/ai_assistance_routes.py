"""
API routes for context-aware AI assistance.

Provides REST API endpoints for:
- Field suggestions
- Content validation
- Inline help
- Context loading
- Content safety (scan, mask, validate)

Blueprint: ai_assistance (url_prefix="/api/ai-assistance")
Routes: 7 + 2 error handlers
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.decorators import audit_log
from app.services.content_safety_filter import get_content_safety_filter
from app.services.context_aware_ai_helper import ContextType, get_ai_helper
from app.services.rate_limiter import rate_limit

logger = logging.getLogger(__name__)

# Create blueprint
ai_assistance_bp = Blueprint("ai_assistance", __name__, url_prefix="/api/ai-assistance")


@ai_assistance_bp.route("/suggest", methods=["POST"])
@login_required
@audit_log("ai_assistance_suggest_field_value")
@rate_limit(30, "1h")
def suggest_field_value():
    """
    Get AI-powered field suggestions
    ---
    tags:
      - AI Assistance
    summary: Get intelligent field value suggestions
    description: Provides context-aware suggestions for form fields based on historical data and AI analysis
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - field_name
            - context_type
          properties:
            field_name:
              type: string
              example: "status"
              description: Name of the field to get suggestions for
            context_type:
              type: string
              example: "application_form"
              description: Type of context (application_form, capability_mapping, vendor_selection, etc.)
            partial_value:
              type: string
              example: "act"
              description: Optional partial user input
            context:
              type: object
              description: Additional context information
    responses:
      200:
        description: Suggestions retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            field:
              type: string
            suggestions:
              type: array
              items:
                type: object
                properties:
                  value:
                    type: string
                  confidence:
                    type: number
                  source:
                    type: string
                  reason:
                    type: string
      400:
        description: Invalid request
      401:
        description: Unauthorized
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        field_name = data.get("field_name")
        context_type = data.get("context_type", ContextType.GENERAL)
        partial_value = data.get("partial_value")
        context_data = data.get("context", {})

        if not field_name:
            return jsonify({"success": False, "error": "field_name is required"}), 400

        # Get AI helper
        ai_helper = get_ai_helper(
            user_id=current_user.id if current_user.is_authenticated else None
        )

        # Load context
        full_context = ai_helper.load_context(context_type, **context_data)

        # Get suggestions
        suggestions = ai_helper.suggest_field_value(
            field_name=field_name, context=full_context, partial_value=partial_value
        )

        return jsonify({"success": True, **suggestions})

    except Exception as e:
        logger.error(f"Error getting suggestions: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_assistance_bp.route("/validate", methods=["POST"])
@login_required
@audit_log("ai_assistance_validate_field")
@rate_limit(30, "1h")
def validate_field():
    """
    Validate field value with AI
    ---
    tags:
      - AI Assistance
    summary: Validate field value using AI reasoning
    description: Performs AI-enhanced validation on field values
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - field_name
            - value
          properties:
            field_name:
              type: string
              example: "name"
            value:
              type: string
              example: "My Application"
            context:
              type: object
              description: Validation context
    responses:
      200:
        description: Validation result
        schema:
          type: object
          properties:
            success:
              type: boolean
            valid:
              type: boolean
            errors:
              type: array
              items:
                type: string
            warnings:
              type: array
              items:
                type: string
      400:
        description: Invalid request
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        field_name = data.get("field_name")
        value = data.get("value")
        context = data.get("context", {})

        if field_name is None or value is None:
            return jsonify({"success": False, "error": "field_name and value are required"}), 400

        # Get AI helper
        ai_helper = get_ai_helper(
            user_id=current_user.id if current_user.is_authenticated else None
        )

        # Validate
        validation_result = ai_helper.validate_with_ai(
            field_name=field_name, value=value, context=context
        )

        return jsonify({"success": True, **validation_result})

    except Exception as e:
        logger.error(f"Error validating field: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_assistance_bp.route("/help", methods=["POST"])
@login_required
@audit_log("ai_assistance_get_field_help")
@rate_limit(30, "1h")
def get_field_help():
    """
    Get contextual help for a field
    ---
    tags:
      - AI Assistance
    summary: Get inline help for form fields
    description: Provides contextual help text, examples, and best practices for fields
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - field_name
          properties:
            field_name:
              type: string
              example: "description"
            context:
              type: object
    responses:
      200:
        description: Help information retrieved
        schema:
          type: object
          properties:
            success:
              type: boolean
            field:
              type: string
            help_text:
              type: string
            examples:
              type: array
              items:
                type: string
            best_practices:
              type: array
              items:
                type: string
            related_fields:
              type: array
              items:
                type: string
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        field_name = data.get("field_name")
        context = data.get("context", {})

        if not field_name:
            return jsonify({"success": False, "error": "field_name is required"}), 400

        # Get AI helper
        ai_helper = get_ai_helper(
            user_id=current_user.id if current_user.is_authenticated else None
        )

        # Get help
        help_info = ai_helper.get_inline_help(field_name=field_name, context=context)

        return jsonify({"success": True, **help_info})

    except Exception as e:
        logger.error(f"Error getting field help: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_assistance_bp.route("/context", methods=["POST"])
@login_required
@audit_log("ai_assistance_load_context")
@rate_limit(30, "1h")
def load_context():
    """
    Load context for AI assistance
    ---
    tags:
      - AI Assistance
    summary: Load contextual information
    description: Loads relevant context for the current workflow
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - context_type
          properties:
            context_type:
              type: string
              example: "application_form"
              enum: [application_form, capability_mapping, vendor_selection, archimate_element, apqc_mapping, general]
            params:
              type: object
              description: Additional context parameters
    responses:
      200:
        description: Context loaded successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            context:
              type: object
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        context_type = data.get("context_type", ContextType.GENERAL)
        params = data.get("params", {})

        # Get AI helper
        ai_helper = get_ai_helper(
            user_id=current_user.id if current_user.is_authenticated else None
        )

        # Load context
        context = ai_helper.load_context(context_type, **params)

        return jsonify({"success": True, "context": context})

    except Exception as e:
        logger.error(f"Error loading context: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_assistance_bp.route("/safety/scan", methods=["POST"])
@login_required
@audit_log("ai_assistance_scan_content")
@rate_limit(30, "1h")
def scan_content():
    """
    Scan content for PII and safety issues
    ---
    tags:
      - Content Safety
    summary: Scan content for PII and toxicity
    description: Scans text content for PII, toxic content, and sensitive topics
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - content
          properties:
            content:
              type: string
              example: "This is sample content"
            scan_pii:
              type: boolean
              default: true
            scan_toxicity:
              type: boolean
              default: true
            scan_sensitive:
              type: boolean
              default: true
    responses:
      200:
        description: Scan results
        schema:
          type: object
          properties:
            success:
              type: boolean
            safe:
              type: boolean
            risk_level:
              type: string
            pii:
              type: object
            toxicity:
              type: object
            sensitive_topics:
              type: object
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        content = data.get("content")

        if not content:
            return jsonify({"success": False, "error": "content is required"}), 400

        scan_pii = data.get("scan_pii", True)
        scan_toxicity = data.get("scan_toxicity", True)
        scan_sensitive = data.get("scan_sensitive", True)

        # Get content safety filter
        safety_filter = get_content_safety_filter()

        # Scan content
        scan_results = safety_filter.scan_content(
            content=content,
            scan_pii=scan_pii,
            scan_toxicity=scan_toxicity,
            scan_sensitive=scan_sensitive,
        )

        return jsonify({"success": True, **scan_results})

    except Exception as e:
        logger.error(f"Error scanning content: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_assistance_bp.route("/safety/mask", methods=["POST"])
@login_required
@audit_log("ai_assistance_mask_content")
@rate_limit(30, "1h")
def mask_content():
    """
    Mask PII in content
    ---
    tags:
      - Content Safety
    summary: Mask sensitive data in content
    description: Masks PII and sensitive data in text content
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - content
          properties:
            content:
              type: string
              example: "Email me at john.doe@example.com"
            mask_pii:
              type: boolean
              default: true
            mask_sensitive:
              type: boolean
              default: false
    responses:
      200:
        description: Masked content
        schema:
          type: object
          properties:
            success:
              type: boolean
            masked_content:
              type: string
            report:
              type: object
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        content = data.get("content")

        if not content:
            return jsonify({"success": False, "error": "content is required"}), 400

        mask_pii = data.get("mask_pii", True)
        mask_sensitive = data.get("mask_sensitive", False)

        # Get content safety filter
        safety_filter = get_content_safety_filter()

        # Mask content
        masked_content, report = safety_filter.mask_content(
            content=content, mask_pii=mask_pii, mask_sensitive=mask_sensitive
        )

        return jsonify({"success": True, "masked_content": masked_content, "report": report})

    except Exception as e:
        logger.error(f"Error masking content: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_assistance_bp.route("/safety/validate-ai-output", methods=["POST"])
@login_required
@audit_log("ai_assistance_validate_ai_output")
@rate_limit(30, "1h")
def validate_ai_output():
    """
    Validate AI-generated output for safety
    ---
    tags:
      - Content Safety
    summary: Validate AI output before presenting to user
    description: Validates AI-generated content for safety and PII issues
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - ai_output
          properties:
            ai_output:
              type: string
              example: "AI generated response text"
    responses:
      200:
        description: Validation result
        schema:
          type: object
          properties:
            success:
              type: boolean
            valid:
              type: boolean
            safe_for_user:
              type: boolean
            requires_review:
              type: boolean
            scan_results:
              type: object
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        ai_output = data.get("ai_output")

        if not ai_output:
            return jsonify({"success": False, "error": "ai_output is required"}), 400

        # Get content safety filter
        safety_filter = get_content_safety_filter()

        # Validate output
        validation_result = safety_filter.validate_ai_output(ai_output)

        return jsonify({"success": True, **validation_result})

    except Exception as e:
        logger.error(f"Error validating AI output: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# Error handlers
@ai_assistance_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"success": False, "error": "Endpoint not found"}), 404


@ai_assistance_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}", exc_info=True)
    return jsonify({"success": False, "error": "Internal server error"}), 500
