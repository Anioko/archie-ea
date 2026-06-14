"""
DEPRECATED: This file is migrated to app/modules/architecture/.
Registration is now centralized via app.modules.architecture.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

ArchiMate API Routes
PRD - 009.2: ArchiMate Relationship Validation API

Provides API endpoints for:
- Relationship validation against ArchiMate 3.2 specification
- Valid relationship type queries
- Element type information
- Batch validation
- Relationship suggestions
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.utils.api_response import error_response, success_response, validation_error_response

logger = logging.getLogger(__name__)

# Create blueprint
archimate_api = Blueprint("archimate_api", __name__, url_prefix="/api/archimate")


@archimate_api.route("/validate-relationship", methods=["POST"])
@login_required
def validate_relationship():
    """
    Validate an ArchiMate relationship
    ---
    tags:
      - ArchiMate
    summary: Validate a relationship between two ArchiMate elements
    description: |
      Validates a relationship against the ArchiMate 3.2 specification.
      Returns validation status, errors, warnings, and suggestions for valid alternatives.
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - source_type
            - target_type
            - relationship_type
          properties:
            source_type:
              type: string
              description: Source ArchiMate element type
              example: ApplicationComponent
            target_type:
              type: string
              description: Target ArchiMate element type
              example: BusinessProcess
            relationship_type:
              type: string
              description: ArchiMate relationship type
              example: serving
    responses:
      200:
        description: Validation result
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
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
                suggestions:
                  type: array
                  items:
                    type: string
      400:
        description: Invalid request - missing required fields
    """
    from app.services.archimate.relationship_validator import get_relationship_validator

    try:
        data = request.get_json()
        if not data:
            return error_response(
                message="Request body is required", code="INVALID_REQUEST", status_code=400
            )

        source_type = data.get("source_type")
        target_type = data.get("target_type")
        relationship_type = data.get("relationship_type")

        # Validate required fields
        missing_fields = []
        if not source_type:
            missing_fields.append("source_type")
        if not target_type:
            missing_fields.append("target_type")
        if not relationship_type:
            missing_fields.append("relationship_type")

        if missing_fields:
            return validation_error_response(
                errors={"missing_fields": missing_fields},
                message=f"Missing required fields: {', '.join(missing_fields)}",
            )

        validator = get_relationship_validator()
        result = validator.validate_relationship(
            source_type=source_type, target_type=target_type, relationship_type=relationship_type
        )

        return success_response(
            {
                "valid": result.is_valid,
                "errors": result.errors,
                "warnings": result.warnings,
                "suggestions": result.suggestions,
                "source_type": source_type,
                "target_type": target_type,
                "relationship_type": relationship_type,
            }
        )

    except Exception as e:
        logger.error(f"Error validating relationship: {str(e)}", exc_info=True)
        return error_response(
            message=f"Validation failed: {str(e)}", code="VALIDATION_ERROR", status_code=500
        )


@archimate_api.route("/validate-batch", methods=["POST"])
@login_required
def validate_batch():
    """
    Validate multiple ArchiMate relationships
    ---
    tags:
      - ArchiMate
    summary: Batch validate multiple relationships
    description: |
      Validates multiple relationships at once and returns aggregated results.
      Useful for validating entire architecture models.
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - relationships
          properties:
            relationships:
              type: array
              items:
                type: object
                properties:
                  source_type:
                    type: string
                  target_type:
                    type: string
                  relationship_type:
                    type: string
    responses:
      200:
        description: Batch validation results
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                total:
                  type: integer
                valid_count:
                  type: integer
                invalid_count:
                  type: integer
                results:
                  type: array
                summary:
                  type: object
      400:
        description: Invalid request
    """
    from app.services.archimate.relationship_validator import get_relationship_validator

    try:
        data = request.get_json()
        if not data:
            return error_response(
                message="Request body is required", code="INVALID_REQUEST", status_code=400
            )

        relationships = data.get("relationships")
        if not relationships or not isinstance(relationships, list):
            return validation_error_response(
                errors={"relationships": "Must be a non-empty array"},
                message="'relationships' must be a non-empty array",
            )

        validator = get_relationship_validator()
        result = validator.validate_batch(relationships)

        return success_response(result.to_dict())

    except Exception as e:
        logger.error(f"Error in batch validation: {str(e)}", exc_info=True)
        return error_response(
            message=f"Batch validation failed: {str(e)}", code="VALIDATION_ERROR", status_code=500
        )


@archimate_api.route("/valid-relationships/<source_type>/<target_type>", methods=["GET"])
@login_required
def get_valid_relationships_endpoint(source_type: str, target_type: str):
    """
    Get valid relationship types between two element types
    ---
    tags:
      - ArchiMate
    summary: Get valid relationship types for element pair
    description: |
      Returns all valid ArchiMate relationship types that can connect
      the specified source and target element types.
    parameters:
      - name: source_type
        in: path
        type: string
        required: true
        description: Source ArchiMate element type
      - name: target_type
        in: path
        type: string
        required: true
        description: Target ArchiMate element type
    responses:
      200:
        description: List of valid relationship types
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                source_type:
                  type: string
                target_type:
                  type: string
                valid_relationship_types:
                  type: array
                  items:
                    type: string
    """
    from app.services.archimate.relationship_validator import get_relationship_validator

    try:
        validator = get_relationship_validator()
        valid_types = validator.get_valid_relationship_types(source_type, target_type)

        return success_response(
            {
                "source_type": source_type,
                "target_type": target_type,
                "valid_relationship_types": valid_types,
                "has_valid_relationships": len(valid_types) > 0,
            }
        )

    except Exception as e:
        logger.error(f"Error getting valid relationships: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to get valid relationships: {str(e)}",
            code="QUERY_ERROR",
            status_code=500,
        )


@archimate_api.route("/valid-targets/<source_type>/<relationship_type>", methods=["GET"])
@login_required
def get_valid_targets_endpoint(source_type: str, relationship_type: str):
    """
    Get valid target types for a source and relationship type
    ---
    tags:
      - ArchiMate
    summary: Get valid target types for source + relationship
    description: |
      Returns all ArchiMate element types that can be valid targets
      for the specified source type and relationship type.
    parameters:
      - name: source_type
        in: path
        type: string
        required: true
        description: Source ArchiMate element type
      - name: relationship_type
        in: path
        type: string
        required: true
        description: ArchiMate relationship type
    responses:
      200:
        description: List of valid target types
    """
    from app.services.archimate.relationship_validator import get_relationship_validator

    try:
        validator = get_relationship_validator()
        valid_targets = validator.get_valid_targets(source_type, relationship_type)

        return success_response(
            {
                "source_type": source_type,
                "relationship_type": relationship_type,
                "valid_targets": valid_targets,
                "count": len(valid_targets),
            }
        )

    except Exception as e:
        logger.error(f"Error getting valid targets: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to get valid targets: {str(e)}", code="QUERY_ERROR", status_code=500
        )


@archimate_api.route("/valid-sources/<target_type>/<relationship_type>", methods=["GET"])
@login_required
def get_valid_sources_endpoint(target_type: str, relationship_type: str):
    """
    Get valid source types for a target and relationship type
    ---
    tags:
      - ArchiMate
    summary: Get valid source types for target + relationship
    description: |
      Returns all ArchiMate element types that can be valid sources
      for the specified target type and relationship type.
    parameters:
      - name: target_type
        in: path
        type: string
        required: true
        description: Target ArchiMate element type
      - name: relationship_type
        in: path
        type: string
        required: true
        description: ArchiMate relationship type
    responses:
      200:
        description: List of valid source types
    """
    from app.services.archimate.relationship_validator import get_relationship_validator

    try:
        validator = get_relationship_validator()
        valid_sources = validator.get_valid_sources(target_type, relationship_type)

        return success_response(
            {
                "target_type": target_type,
                "relationship_type": relationship_type,
                "valid_sources": valid_sources,
                "count": len(valid_sources),
            }
        )

    except Exception as e:
        logger.error(f"Error getting valid sources: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to get valid sources: {str(e)}", code="QUERY_ERROR", status_code=500
        )


@archimate_api.route("/suggest-relationships", methods=["POST"])
@login_required
def suggest_relationships():
    """
    Suggest valid relationships and alternatives for an element pair
    ---
    tags:
      - ArchiMate
    summary: Get relationship suggestions for element pair
    description: |
      Provides comprehensive suggestions for relationships between two elements,
      including direct relationships, reverse direction, and alternatives.
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - source_type
            - target_type
          properties:
            source_type:
              type: string
            target_type:
              type: string
    responses:
      200:
        description: Relationship suggestions
    """
    from app.services.archimate.relationship_validator import get_relationship_validator

    try:
        data = request.get_json()
        if not data:
            return error_response(
                message="Request body is required", code="INVALID_REQUEST", status_code=400
            )

        source_type = data.get("source_type")
        target_type = data.get("target_type")

        if not source_type or not target_type:
            return validation_error_response(
                errors={"required": ["source_type", "target_type"]},
                message="Both source_type and target_type are required",
            )

        validator = get_relationship_validator()
        suggestions = validator.suggest_relationships(source_type, target_type)

        return success_response(suggestions)

    except Exception as e:
        logger.error(f"Error suggesting relationships: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to suggest relationships: {str(e)}",
            code="QUERY_ERROR",
            status_code=500,
        )


@archimate_api.route("/validate-cardinality", methods=["POST"])
@login_required
def validate_cardinality():
    """
    Validate cardinality constraints for a relationship
    ---
    tags:
      - ArchiMate
    summary: Validate relationship cardinality
    description: |
      Checks if adding a relationship would violate cardinality constraints
      defined in the ArchiMate specification.
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - source_element_id
            - relationship_type
            - existing_count
          properties:
            source_element_id:
              type: integer
            relationship_type:
              type: string
            existing_count:
              type: integer
    responses:
      200:
        description: Cardinality validation result
    """
    from app.services.archimate.relationship_validator import get_relationship_validator

    try:
        data = request.get_json()
        if not data:
            return error_response(
                message="Request body is required", code="INVALID_REQUEST", status_code=400
            )

        source_element_id = data.get("source_element_id")
        relationship_type = data.get("relationship_type")
        existing_count = data.get("existing_count", 0)

        if source_element_id is None or not relationship_type:
            return validation_error_response(
                errors={"required": ["source_element_id", "relationship_type"]},
                message="source_element_id and relationship_type are required",
            )

        validator = get_relationship_validator()
        result = validator.validate_cardinality(
            source_element_id=source_element_id,
            relationship_type=relationship_type,
            existing_count=existing_count,
        )

        return success_response(
            {
                "valid": result.is_valid,
                "errors": result.errors,
                "warnings": result.warnings,
                "suggestions": result.suggestions,
            }
        )

    except Exception as e:
        logger.error(f"Error validating cardinality: {str(e)}", exc_info=True)
        return error_response(
            message=f"Cardinality validation failed: {str(e)}",
            code="VALIDATION_ERROR",
            status_code=500,
        )


@archimate_api.route("/element-types", methods=["GET"])
@login_required
def get_element_types():
    """
    Get all ArchiMate element types by layer
    ---
    tags:
      - ArchiMate
    summary: Get element types organized by layer
    description: Returns all ArchiMate element types grouped by their layer
    parameters:
      - name: layer
        in: query
        type: string
        required: false
        description: Filter by specific layer (strategy, business, application, etc.)
    responses:
      200:
        description: Element types by layer
    """
    from app.config.archimate_relationship_matrix import (
        ALL_ELEMENTS,
        APPLICATION_ELEMENTS,
        BUSINESS_ELEMENTS,
        IMPLEMENTATION_ELEMENTS,
        MOTIVATION_ELEMENTS,
        PHYSICAL_ELEMENTS,
        STRATEGY_ELEMENTS,
        TECHNOLOGY_ELEMENTS,
    )
    from app.services.archimate.relationship_validator import get_relationship_validator

    try:
        layer_filter = request.args.get("layer", "").lower()

        all_layers = {
            "strategy": list(STRATEGY_ELEMENTS),
            "business": list(BUSINESS_ELEMENTS),
            "application": list(APPLICATION_ELEMENTS),
            "technology": list(TECHNOLOGY_ELEMENTS),
            "physical": list(PHYSICAL_ELEMENTS),
            "motivation": list(MOTIVATION_ELEMENTS),
            "implementation": list(IMPLEMENTATION_ELEMENTS),
        }

        if layer_filter:
            if layer_filter in all_layers:
                return success_response(
                    {
                        "layer": layer_filter,
                        "element_types": all_layers[layer_filter],
                        "count": len(all_layers[layer_filter]),
                    }
                )
            else:
                return error_response(
                    message=f"Unknown layer: '{layer_filter}'",
                    code="INVALID_LAYER",
                    details={"valid_layers": list(all_layers.keys())},
                    status_code=400,
                )

        return success_response(
            {
                "layers": all_layers,
                "total_element_types": len(ALL_ELEMENTS),
                "layer_counts": {layer: len(elements) for layer, elements in all_layers.items()},
            }
        )

    except Exception as e:
        logger.error(f"Error getting element types: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to get element types: {str(e)}", code="QUERY_ERROR", status_code=500
        )


@archimate_api.route("/relationship-types", methods=["GET"])
@login_required
def get_relationship_types():
    """
    Get all ArchiMate relationship types
    ---
    tags:
      - ArchiMate
    summary: Get all relationship types with metadata
    description: Returns all ArchiMate relationship types with descriptions and categories
    responses:
      200:
        description: Relationship types with metadata
    """
    from app.services.archimate.relationship_validator import get_relationship_validator

    try:
        validator = get_relationship_validator()
        relationship_types = validator.get_all_relationship_types()

        return success_response(
            {"relationship_types": relationship_types, "count": len(relationship_types)}
        )

    except Exception as e:
        logger.error(f"Error getting relationship types: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to get relationship types: {str(e)}",
            code="QUERY_ERROR",
            status_code=500,
        )


@archimate_api.route("/matrix-statistics", methods=["GET"])
@login_required
def get_matrix_statistics():
    """
    Get statistics about the ArchiMate relationship matrix
    ---
    tags:
      - ArchiMate
    summary: Get relationship matrix statistics
    description: Returns statistics about the ArchiMate relationship validation matrix
    responses:
      200:
        description: Matrix statistics
    """
    from app.config.archimate_relationship_matrix import get_matrix_statistics

    try:
        stats = get_matrix_statistics()

        return success_response({"statistics": stats})

    except Exception as e:
        logger.error(f"Error getting matrix statistics: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to get matrix statistics: {str(e)}",
            code="QUERY_ERROR",
            status_code=500,
        )


@archimate_api.route("/relationships/backfill", methods=["POST"])
@login_required
def backfill_relationships_endpoint():
    """
    Backfill ArchiMateRelationship records from existing junction tables.
    ---
    tags:
      - ArchiMate
    summary: Backfill relationships from junction tables
    description: |
      Scans all domain junction tables (ServiceRealization, ProcessRoleRaci,
      ApplicationProcessSupport, etc.) and creates corresponding ArchiMateRelationship
      records. Idempotent — safe to run multiple times without creating duplicates.
      Covers Waves 1-3 (9 ORM junction tables) plus db.Table associations.
    responses:
      200:
        description: Backfill results with per-table counts
    """
    try:
        from app.models.archimate_relationship_sync import backfill_relationships

        counts = backfill_relationships()
        total = sum(counts.values())

        return success_response(
            {
                "total_created": total,
                "by_table": counts,
            },
            meta={"description": "ArchiMate relationship backfill from junction tables"},
        )

    except Exception as e:
        logger.error(f"Error running relationship backfill: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to run relationship backfill: {str(e)}",
            code="BACKFILL_ERROR",
            status_code=500,
        )


@archimate_api.route("/relationships/coverage", methods=["GET"])
@login_required
def relationship_coverage():
    """
    ArchiMate relationship coverage report.
    ---
    tags:
      - ArchiMate
    summary: Get relationship coverage statistics
    description: |
      Returns per-layer and per-element-type statistics showing how many
      ArchiMateElement records have at least one relationship vs. orphans
      (elements with zero relationships).
    responses:
      200:
        description: Coverage statistics by layer and element type
    """
    from app import db
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship

    try:
        # Count elements per layer and type
        element_counts = (
            db.session.query(
                ArchiMateElement.layer,
                ArchiMateElement.type,
                db.func.count(ArchiMateElement.id),
            )
            .group_by(ArchiMateElement.layer, ArchiMateElement.type)
            .all()
        )

        # Elements with at least one relationship (as source OR target)
        from sqlalchemy import or_

        connected_subq = (
            db.session.query(ArchiMateElement.id)
            .filter(
                or_(
                    ArchiMateElement.id.in_(
                        db.session.query(ArchiMateRelationship.source_id)
                    ),
                    ArchiMateElement.id.in_(
                        db.session.query(ArchiMateRelationship.target_id)
                    ),
                )
            )
            .subquery()
        )

        connected_counts = (
            db.session.query(
                ArchiMateElement.layer,
                ArchiMateElement.type,
                db.func.count(ArchiMateElement.id),
            )
            .filter(ArchiMateElement.id.in_(db.session.query(connected_subq.c.id)))
            .group_by(ArchiMateElement.layer, ArchiMateElement.type)
            .all()
        )

        # Relationship counts by type
        rel_counts = (
            db.session.query(
                ArchiMateRelationship.type,
                db.func.count(ArchiMateRelationship.id),
            )
            .group_by(ArchiMateRelationship.type)
            .all()
        )

        # Build connected lookup
        connected_lookup = {}
        for layer, etype, count in connected_counts:
            connected_lookup[(layer, etype)] = count

        # Build per-type and per-layer results
        by_type = {}
        by_layer = {}
        total_elements = 0
        total_connected = 0

        for layer, etype, count in element_counts:
            connected = connected_lookup.get((layer, etype), 0)
            orphans = count - connected
            total_elements += count
            total_connected += connected

            by_type[etype] = {
                "layer": layer,
                "total": count,
                "with_relationships": connected,
                "orphans": orphans,
                "coverage_pct": round(connected / count * 100, 1) if count > 0 else 0,
            }

            if layer not in by_layer:
                by_layer[layer] = {"elements": 0, "with_relationships": 0, "orphans": 0}
            by_layer[layer]["elements"] += count
            by_layer[layer]["with_relationships"] += connected
            by_layer[layer]["orphans"] += orphans

        # Add coverage % to layer summaries
        for layer_data in by_layer.values():
            total = layer_data["elements"]
            layer_data["coverage_pct"] = (
                round(layer_data["with_relationships"] / total * 100, 1) if total > 0 else 0
            )

        return success_response(
            {
                "summary": {
                    "total_elements": total_elements,
                    "total_with_relationships": total_connected,
                    "total_orphans": total_elements - total_connected,
                    "overall_coverage_pct": (
                        round(total_connected / total_elements * 100, 1)
                        if total_elements > 0
                        else 0
                    ),
                    "total_relationships": sum(c for _, c in rel_counts),
                },
                "by_layer": by_layer,
                "by_element_type": by_type,
                "relationships_by_type": {rtype: count for rtype, count in rel_counts},
            }
        )

    except Exception as e:
        logger.error(f"Error getting relationship coverage: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to get relationship coverage: {str(e)}",
            code="QUERY_ERROR",
            status_code=500,
        )


# ── SA-002 — 8-layer traceability chain JSON API ────────────────────────────

@archimate_api.route("/traceability", methods=["GET"])
@login_required
def traceability_chain_api():
    """Return the 8-layer traceability chain as JSON.

    Query Parameters:
        solution_id (int): Optional — scope to a specific solution.
    """
    from app.services.archimate_traceability_service import get_traceability_chain

    solution_id = request.args.get("solution_id", type=int)
    return jsonify(get_traceability_chain(solution_id=solution_id))
