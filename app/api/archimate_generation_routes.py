"""
ArchiMate Generation API Routes

REST API endpoints for automated ArchiMate 3.2 element generation and relationship management.
Provides comprehensive API for enterprise architecture modeling from vendor and capability data.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional  # dead-code-ok: used by type hints in docstrings

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app import db
from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel
from app.models.archimate import ElementType, Layer, RelationshipType
from app.models.solution_archimate_element import SolutionArchiMateElement
from app.models.solution_models import Solution
from app.modules.architecture.services.archimate_core_service import ArchiMateService

logger = logging.getLogger(__name__)

# Create blueprint
archimate_generation_bp = Blueprint('archimate_generation', __name__, url_prefix='/api/archimate')

# Initialize service
archimate_service = ArchiMateService()


# =============================================================================
# Architecture Generation Endpoints
# =============================================================================

@archimate_generation_bp.route('/generate/from-vendors', methods=['POST'])
@login_required
def generate_from_vendors():
    """
    Generate ArchiMate architecture from vendor data.

    POST /api/archimate/generate/from-vendors
    Body: {"vendor_ids": [1, 2, 3]} or {} for all vendors
    """
    try:
        data = request.get_json() or {}
        vendor_ids = data.get('vendor_ids')

        result = archimate_service.generate_architecture_from_vendors(vendor_ids)

        return jsonify({
            "success": True,
            "message": f"Generated ArchiMate architecture from {result['vendors_processed']} vendors",
            "data": result
        }), 200

    except Exception as e:
        logger.error(f"Failed to generate architecture from vendors: {e}")
        return jsonify({
            "success": False,
            "error": "An internal error occurred"
        }), 500


@archimate_generation_bp.route('/generate/from-capabilities', methods=['POST'])
@login_required
def generate_from_capabilities():
    """
    Generate ArchiMate elements from business capabilities.

    POST /api/archimate/generate/from-capabilities
    Body: {"capability_ids": [1, 2, 3], "solution_id": 5}
    - capability_ids: optional list of IDs, or omit for all capabilities
    - solution_id: optional — if provided, generated elements are linked to the solution
      via the solution_archimate_elements junction table with deduplication
    """
    try:
        data = request.get_json() or {}
        capability_ids = data.get('capability_ids')
        solution_id = data.get('solution_id')

        # Validate solution_id if provided
        if solution_id is not None:
            solution = Solution.query.get(solution_id)
            if not solution:
                return jsonify({
                    "success": False,
                    "error": f"Solution with id {solution_id} not found"
                }), 404

        result = archimate_service.generate_architecture_from_capabilities(capability_ids)

        # Link generated elements to solution if solution_id was provided
        linked_count = 0
        if solution_id is not None and result.get('commit_success'):
            linked_count = _link_elements_to_solution(
                solution_id, result.get('created_elements', [])
            )

        # Remove non-serializable created_elements from response data
        response_data = {k: v for k, v in result.items() if k != 'created_elements'}
        response_data['linked_to_solution'] = linked_count

        return jsonify({
            "success": True,
            "message": f"Generated ArchiMate elements from {result['capabilities_processed']} capabilities",
            "data": response_data
        }), 200

    except Exception as e:
        logger.error(f"Failed to generate elements from capabilities: {e}")
        return jsonify({
            "success": False,
            "error": "An internal error occurred"
        }), 500


# Map ArchiMate element types to relationship roles for junction records
_ELEMENT_TYPE_RELATIONSHIP_MAP = {
    'application_function': 'realizes',
    'application_service': 'serves',
    'data_object': 'accesses',
    'business_object': 'accesses',
    'business_service': 'realizes',
    'business_process': 'realizes',
    'application_component': 'realizes',
    'application_interface': 'serves',
    'technology_service': 'serves',
}


def _link_elements_to_solution(solution_id, elements):
    """
    Create SolutionArchiMateElement junction records for each element,
    skipping duplicates where the same solution_id + element_id already exists.

    Returns the count of newly created junction records.
    """
    from app import db as app_db

    linked = 0
    for element in elements:
        if element.id is None:
            continue
        # Check for existing junction record (deduplication)
        existing = SolutionArchiMateElement.query.filter_by(  # model-safety-ok: small result set from generation
            solution_id=solution_id,
            element_id=element.id,
        ).first()  # model-safety-ok
        if existing:
            continue

        # Determine element_role from the element type
        relationship_type = _ELEMENT_TYPE_RELATIONSHIP_MAP.get(
            element.type, 'associated'
        )

        junction = SolutionArchiMateElement(
            solution_id=solution_id,
            element_id=element.id,
            element_role=relationship_type,
        )
        app_db.session.add(junction)
        linked += 1

    if linked > 0:
        app_db.session.commit()

    return linked


@archimate_generation_bp.route('/generate/relationships', methods=['POST'])
@login_required
def generate_relationships():
    """
    Create ArchiMate relationships from capability-to-vendor mappings.

    POST /api/archimate/generate/relationships
    Body: [{"business_capability_id": 1, "vendor_product_id": 2, "mapping_strength": "high"}, ...]
    """
    try:
        mappings = request.get_json()

        if not mappings or not isinstance(mappings, list):
            return jsonify({
                "success": False,
                "error": "Request body must be a list of mapping objects"
            }), 400

        result = archimate_service.create_relationships_from_mappings(mappings)

        return jsonify({
            "success": True,
            "message": f"Created {result['relationships_created']} relationships from {result['mappings_processed']} mappings",
            "data": result
        }), 200

    except Exception as e:
        logger.error(f"Failed to generate relationships: {e}")
        return jsonify({
            "success": False,
            "error": "An internal error occurred"
        }), 500


# =============================================================================
# Element Management Endpoints
# =============================================================================

@archimate_generation_bp.route('/elements', methods=['GET'])
@login_required
def get_elements():
    """
    Get ArchiMate elements with optional filtering.

    GET /api/archimate/elements?type=business_actor&layer=business
    GET /api/archimate/elements?q=payment&types=ApplicationComponent,ApplicationService&limit=25
    """
    try:
        element_type = request.args.get('type')
        layer = request.args.get('layer')
        # Text search + multi-type filter (used by blueprint Link Elements picker)
        q = request.args.get('q', '').strip()
        types_param = request.args.get('types', '').strip()
        limit = min(int(request.args.get('limit', 25)), 100)

        if q or types_param:
            # Free-text search path
            query = ArchiMateElement.query
            if q:
                query = query.filter(ArchiMateElement.name.ilike(f'%{q}%'))
            if types_param:
                type_list = [t.strip() for t in types_param.split(',') if t.strip()]
                if type_list:
                    query = query.filter(ArchiMateElement.type.in_(type_list))
            if layer:
                query = query.filter(ArchiMateElement.layer == layer)
            elements = query.order_by(ArchiMateElement.name).limit(limit).all()
        elif element_type:
            try:
                element_type_enum = ElementType(element_type)
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": f"Invalid element type: {element_type}"
                }), 400

            layer_enum = None
            if layer:
                try:
                    layer_enum = Layer(layer)
                except ValueError:
                    return jsonify({
                        "success": False,
                        "error": f"Invalid layer: {layer}"
                    }), 400

            elements = archimate_service.get_elements_by_type(element_type_enum, layer_enum)
        else:
            # No filter — cap to avoid returning all 3k+ elements
            elements = ArchiMateElement.query.order_by(ArchiMateElement.name).limit(limit).all()

        # Convert to dict format
        element_data = []
        for element in elements:
            created_at = getattr(element, 'created_at', None)
            updated_at = getattr(element, 'updated_at', None)
            element_data.append({
                "id": element.id,
                "name": element.name,
                "type": element.type,
                "layer": element.layer,
                "description": element.description,
                "properties": getattr(element, 'properties', None),
                "source_entity_id": getattr(element, 'source_entity_id', None),
                "source_entity_type": getattr(element, 'source_entity_type', None),
                "created_at": created_at.isoformat() if created_at else None,
                "updated_at": updated_at.isoformat() if updated_at else None
            })

        return jsonify({
            "success": True,
            "data": element_data,
            "count": len(element_data)
        }), 200

    except Exception as e:
        logger.error(f"Failed to get elements: {e}")
        return jsonify({
            "success": False,
            "error": "An internal error occurred"
        }), 500


@archimate_generation_bp.route('/elements/<int:element_id>', methods=['GET'])
@login_required
def get_element(element_id):
    """
    Get a specific ArchiMate element by ID.

    GET /api/archimate/elements/123
    """
    try:
        element = ArchiMateElement.query.get(element_id)

        if not element:
            return jsonify({
                "success": False,
                "error": "Element not found"
            }), 404

        # Get relationships for this element
        relationships = archimate_service.get_element_relationships(element_id)
        relationship_data = []

        # Resolve related element names in one bulk query (no ORM relationship exists).
        rel_elem_ids = {r.source_id for r in relationships} | {r.target_id for r in relationships}
        rel_elem_ids.discard(None)
        rel_names = dict(
            db.session.query(ArchiMateElement.id, ArchiMateElement.name)
            .filter(ArchiMateElement.id.in_(rel_elem_ids)).all()
        ) if rel_elem_ids else {}

        for rel in relationships:
            relationship_data.append({
                "id": rel.id,
                "relationship_type": rel.type,
                "source_element_id": rel.source_id,
                "target_element_id": rel.target_id,
                "source_element_name": rel_names.get(rel.source_id),
                "target_element_name": rel_names.get(rel.target_id),
                "name": getattr(rel, "custom_label", None) or getattr(rel, "flow_label", None),
                "description": rel.description
            })

        element_data = {
            "id": element.id,
            "name": element.name,
            "type": element.type,
            "layer": element.layer,
            "description": element.description,
            "properties": element.properties,
            "source_entity_id": getattr(element, "source_product_id", None),
            "source_entity_type": getattr(element, "acm_source", None),
            "relationships": relationship_data,
            "created_at": getattr(element, "created_at", None).isoformat() if getattr(element, "created_at", None) else None,
            "updated_at": getattr(element, "last_reviewed_date", None).isoformat() if getattr(element, "last_reviewed_date", None) else None
        }

        return jsonify({
            "success": True,
            "data": element_data
        }), 200

    except Exception as e:
        logger.error(f"Failed to get element {element_id}: {e}")
        return jsonify({
            "success": False,
            "error": "An internal error occurred"
        }), 500


# =============================================================================
# Relationship Management Endpoints
# =============================================================================

@archimate_generation_bp.route('/relationships', methods=['GET'])
@login_required
def get_relationships():
    """
    Get ArchiMate relationships with optional filtering.

    GET /api/archimate/relationships?type=serving
    """
    try:
        relationship_type = request.args.get('type')

        query = ArchiMateRelationship.query

        if relationship_type:
            try:
                RelationshipType(relationship_type)  # Validate enum
                query = query.filter_by(type=relationship_type)
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": f"Invalid relationship type: {relationship_type}"
                }), 400

        relationships = query.all()

        # ArchiMateRelationship has no source_element/target_element relationships
        # (only source_id/target_id); resolve element names in one bulk query.
        elem_ids = {r.source_id for r in relationships} | {r.target_id for r in relationships}
        elem_ids.discard(None)
        names = dict(
            db.session.query(ArchiMateElement.id, ArchiMateElement.name)
            .filter(ArchiMateElement.id.in_(elem_ids)).all()
        ) if elem_ids else {}

        # Convert to dict format
        relationship_data = []
        for rel in relationships:
            relationship_data.append({
                "id": rel.id,
                "relationship_type": rel.type,
                "source_element_id": rel.source_id,
                "target_element_id": rel.target_id,
                "source_element_name": names.get(rel.source_id),
                "target_element_name": names.get(rel.target_id),
                "name": getattr(rel, "custom_label", None) or getattr(rel, "flow_label", None),
                "description": rel.description,
                "created_at": rel.created_at.isoformat() if rel.created_at else None,
                "updated_at": rel.updated_at.isoformat() if rel.updated_at else None
            })

        return jsonify({
            "success": True,
            "data": relationship_data,
            "count": len(relationship_data)
        }), 200

    except Exception as e:
        logger.error(f"Failed to get relationships: {e}")
        return jsonify({
            "success": False,
            "error": "An internal error occurred"
        }), 500


# =============================================================================
# Architecture Model Management Endpoints
# =============================================================================

@archimate_generation_bp.route('/models', methods=['GET'])
@login_required
def get_models():
    """
    Get all architecture models.

    GET /api/archimate/models
    """
    try:
        models = ArchitectureModel.query.all()

        model_data = []
        for model in models:
            model_data.append({
                "id": model.id,
                "name": model.name,
                "version": model.version,
                "description": getattr(model, 'description', None),
                "model_type": getattr(model, 'model_type', None),
                "status": getattr(model, 'status', None),
                "created_at": getattr(model, 'created_at', None).isoformat() if getattr(model, 'created_at', None) else None,
                "updated_at": getattr(model, 'updated_at', None).isoformat() if getattr(model, 'updated_at', None) else None
            })

        return jsonify({
            "success": True,
            "data": model_data,
            "count": len(model_data)
        }), 200

    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        return jsonify({
            "success": False,
            "error": "An internal error occurred"
        }), 500


@archimate_generation_bp.route('/models', methods=['POST'])
@login_required
def create_model():
    """
    Create a new architecture model.

    POST /api/archimate/models
    Body: {"name": "Enterprise Architecture", "description": "...", "model_type": "enterprise"}
    """
    try:
        data = request.get_json()

        if not data or not data.get('name'):
            return jsonify({
                "success": False,
                "error": "Model name is required"
            }), 400

        model = archimate_service.create_architecture_model(
            name=data['name'],
            description=data.get('description'),
            model_type=data.get('model_type', 'enterprise')
        )

        return jsonify({
            "success": True,
            "message": f"Created architecture model: {model.name}",
            "data": {
                "id": model.id,
                "name": model.name,
                "version": model.version,
                "model_type": getattr(model, 'model_type', None),
                "status": getattr(model, 'status', None)
            }
        }), 201

    except Exception as e:
        logger.error(f"Failed to create model: {e}")
        return jsonify({
            "success": False,
            "error": "An internal error occurred"
        }), 500


# =============================================================================
# Validation and Statistics Endpoints
# =============================================================================

@archimate_generation_bp.route('/validate', methods=['GET'])
@login_required
def validate_compliance():
    """
    Validate ArchiMate 3.2 compliance of the current model.

    GET /api/archimate/validate
    """
    try:
        result = archimate_service.validate_archimate_compliance()

        return jsonify({
            "success": True,
            "data": result
        }), 200

    except Exception as e:
        logger.error(f"Failed to validate compliance: {e}")
        return jsonify({
            "success": False,
            "error": "An internal error occurred"
        }), 500


@archimate_generation_bp.route('/statistics', methods=['GET'])
@login_required
def get_statistics():
    """
    Get comprehensive architecture statistics.

    GET /api/archimate/statistics
    """
    try:
        stats = archimate_service.get_architecture_statistics()

        return jsonify({
            "success": True,
            "data": stats
        }), 200

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        return jsonify({
            "success": False,
            "error": "An internal error occurred"
        }), 500


# =============================================================================
# Health Check Endpoint
# =============================================================================

@archimate_generation_bp.route('/health', methods=['GET'])
@login_required
def health_check():
    """
    ArchiMate generation service health check.

    GET /api/archimate/health
    """
    try:
        # Basic health check
        element_count = ArchiMateElement.query.count()
        relationship_count = ArchiMateRelationship.query.count()
        model_count = ArchitectureModel.query.count()

        return jsonify({
            "success": True,
            "status": "healthy",
            "data": {
                "elements": element_count,
                "relationships": relationship_count,
                "models": model_count,
                "timestamp": datetime.utcnow().isoformat()
            }
        }), 200

    except Exception as e:
        logger.error(f"ArchiMate health check failed: {e}")
        return jsonify({
            "success": False,
            "status": "unhealthy",
            "error": "An internal error occurred"
        }), 500
