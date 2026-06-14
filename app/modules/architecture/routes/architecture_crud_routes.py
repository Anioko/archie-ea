"""
DEPRECATED: This file is migrated to app/modules/architecture/.
Registration is now centralized via app.modules.architecture.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

Architecture CRUD Routes - Complete Implementation
"""

import os

from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    current_app,
    send_file,
    after_this_request,
)
from flask_login import login_required
from sqlalchemy import func, or_

from app.decorators import audit_log, require_roles
from app.extensions import db
from app.models.archimate_core import (
    ArchiMateElement as ArchitectureElement,
    ArchiMateRelationship as Relationship,
)
from app.services.architecture_validation_service import ArchitectureValidator
from app.services.architecture_search_service import ArchitectureSearchService
from app.services.architecture_import_export_service import (
    ArchitectureImportExportService,
)

architecture_crud_bp = Blueprint(
    "architecture_crud",
    __name__,
    url_prefix="/architecture",
)

# Instantiate services
validator = ArchitectureValidator()
search_service = ArchitectureSearchService()
import_export_service = ArchitectureImportExportService()


# ==================== ELEMENT ROUTES ====================


@architecture_crud_bp.route("/elements", methods=["GET"])
@login_required
def list_elements():
    """Render ArchiMate elements list with server-side layer stats (ARC-002).

    URL params forwarded to the Alpine component:
      ?layer=<layer>    — pre-selects the layer filter
      ?q=<term>         — initial search term
    """
    _LAYER_ORDER = [
        "Motivation", "Strategy", "Business",
        "Application", "Technology", "Implementation",
    ]

    # Count per layer
    counts_q = (
        db.session.query(ArchitectureElement.layer, func.count(ArchitectureElement.id))
        .group_by(ArchitectureElement.layer)
        .all()
    )
    count_map = {(row[0] or "").lower(): row[1] for row in counts_q}

    # Top 3 element types per layer
    layer_stats = []
    for layer_name in _LAYER_ORDER:
        top_types_q = (
            db.session.query(
                ArchitectureElement.type,
                func.count(ArchitectureElement.id).label("cnt"),
            )
            .filter(func.lower(ArchitectureElement.layer) == layer_name.lower())
            .group_by(ArchitectureElement.type)
            .order_by(func.count(ArchitectureElement.id).desc())
            .limit(3)
            .all()
        )
        layer_stats.append({
            "name": layer_name,
            "count": count_map.get(layer_name.lower(), 0),
            "top_types": [{"type": t or "", "count": c} for t, c in top_types_q],
        })

    # ARC-005: Data quality counts
    no_desc_count = (
        ArchitectureElement.query.filter(
            or_(
                ArchitectureElement.description.is_(None),
                ArchitectureElement.description == "",
            )
        ).count()
    )

    # Elements with no relationships (neither source nor target) — use raw scalar subquery
    from sqlalchemy import text as _text
    total_count = ArchitectureElement.query.count()
    with_rels_count = db.session.execute(_text(
        "SELECT COUNT(DISTINCT id) FROM archimate_elements WHERE id IN "
        "(SELECT source_id FROM archimate_relationships WHERE source_id IS NOT NULL "
        "UNION SELECT target_id FROM archimate_relationships WHERE target_id IS NOT NULL)"
    )).scalar() or 0
    no_rels_count = max(0, total_count - with_rels_count)

    # Elements not linked to any solution
    with_solutions_count = db.session.execute(_text(
        "SELECT COUNT(DISTINCT element_id) FROM solution_archimate_elements WHERE element_id IS NOT NULL"
    )).scalar() or 0
    no_solutions_count = max(0, total_count - with_solutions_count)

    return render_template("architecture/elements.html",
                           layer_stats=layer_stats,
                           no_desc_count=no_desc_count,
                           no_rels_count=no_rels_count,
                           no_solutions_count=no_solutions_count)


@architecture_crud_bp.route("/elements/create", methods=["GET"])
@login_required
@require_roles("admin", "architect")
def create_element_form():
    """Show create element form."""
    return jsonify({"success": True, "message": "Use POST to create element"})


@architecture_crud_bp.route("/elements", methods=["POST"])
@login_required
@require_roles("admin", "architect")
@audit_log("architecture_element_create")
def create_element():
    """Create new architecture element."""
    data = request.get_json() or {}

    # Validate
    is_valid, errors = validator.validate_element(data)
    if not is_valid:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # Create
    element = ArchitectureElement(
        name=data["name"],
        element_type=data["element_type"],
        layer=data.get("layer"),
        description=data.get("description"),
    )

    db.session.add(element)
    db.session.commit()

    return jsonify(
        {
            "status": "success",
            "element_id": element.id,
            "message": f"Element '{element.name}' created",
        }
    ), 201


@architecture_crud_bp.route("/elements/<int:element_id>", methods=["GET"])
@login_required
def view_element(element_id):
    """View element details."""
    element = ArchitectureElement.query.get_or_404(element_id)

    # Get relationships
    incoming = Relationship.query.filter_by(target_id=element_id).all()
    outgoing = Relationship.query.filter_by(source_id=element_id).all()

    return render_template(
        "architecture/elements.html",
        element=element,
        incoming_relationships=incoming,
        outgoing_relationships=outgoing,
    )


@architecture_crud_bp.route("/elements/<int:element_id>/edit", methods=["GET"])
@login_required
@require_roles("admin", "architect")
def edit_element_form(element_id):
    """Show edit element form."""
    element = ArchitectureElement.query.get_or_404(element_id)
    return jsonify(
        {"success": True, "data": element.to_dict(), "message": "Use PUT to update"}
    )


@architecture_crud_bp.route("/elements/<int:element_id>", methods=["PUT"])
@login_required
@require_roles("admin", "architect")
@audit_log("architecture_element_update")
def update_element(element_id):
    """Update element."""
    element = ArchitectureElement.query.get_or_404(element_id)
    data = request.get_json() or {}

    # Validate
    is_valid, errors = validator.validate_element(data)
    if not is_valid:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # Update
    element.name = data.get("name", element.name)
    element.element_type = data.get("element_type", element.element_type)
    element.layer = data.get("layer", element.layer)
    element.description = data.get("description", element.description)

    db.session.commit()

    return jsonify(
        {
            "status": "success",
            "element": element.to_dict(),
            "message": f"Element '{element.name}' updated",
        }
    )


@architecture_crud_bp.route("/elements/<int:element_id>", methods=["DELETE"])
@login_required
@require_roles("admin", "architect")
@audit_log("architecture_element_delete")
def delete_element(element_id):
    """Delete element and all related relationships."""
    element = ArchitectureElement.query.get_or_404(element_id)
    element_name = element.name

    # Delete related relationships
    Relationship.query.filter(
        or_(
            Relationship.source_id == element_id,
            Relationship.target_id == element_id,
        )
    ).delete()

    db.session.delete(element)
    db.session.commit()

    return jsonify(
        {
            "status": "success",
            "message": f"Element '{element_name}' deleted",
        }
    )


# ==================== RELATIONSHIP ROUTES ====================


@architecture_crud_bp.route("/relationships", methods=["GET"])
@login_required
def list_relationships():
    """List all relationships."""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    relationships = Relationship.query.paginate(page=page, per_page=per_page)

    return render_template(
        "architecture/relationships.html",
        relationships=relationships.items,
        total=relationships.total,
    )


@architecture_crud_bp.route("/relationships", methods=["POST"])
@login_required
@require_roles("admin", "architect")
@audit_log("architecture_relationship_create")
def create_relationship():
    """Create relationship between elements."""
    data = request.get_json() or {}

    # Validate
    is_valid, errors = validator.validate_relationship(data)
    if not is_valid:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # Check for circular dependency
    if validator.would_create_cycle(data["source_id"], data["target_id"]):
        return jsonify({"error": "Would create circular dependency"}), 400

    relationship = Relationship(
        source_id=data["source_id"],
        target_id=data["target_id"],
        relationship_type=data["relationship_type"],
        description=data.get("description"),
    )

    db.session.add(relationship)
    db.session.commit()

    return jsonify(
        {
            "status": "success",
            "relationship_id": relationship.id,
            "message": "Relationship created",
        }
    ), 201


@architecture_crud_bp.route("/relationships/<int:rel_id>", methods=["PUT"])
@login_required
@require_roles("admin", "architect")
@audit_log("architecture_relationship_update")
def update_relationship(rel_id):
    """Update relationship."""
    relationship = Relationship.query.get_or_404(rel_id)
    data = request.get_json() or {}

    # Validate
    is_valid, errors = validator.validate_relationship(data)
    if not is_valid:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    relationship.relationship_type = data.get(
        "relationship_type", relationship.relationship_type
    )
    relationship.description = data.get("description", relationship.description)

    db.session.commit()

    return jsonify(
        {
            "status": "success",
            "relationship": relationship.to_dict(),
        }
    )


@architecture_crud_bp.route("/relationships/<int:rel_id>", methods=["DELETE"])
@login_required
@require_roles("admin", "architect")
@audit_log("architecture_relationship_delete")
def delete_relationship(rel_id):
    """Delete relationship."""
    relationship = Relationship.query.get_or_404(rel_id)

    db.session.delete(relationship)
    db.session.commit()

    return jsonify({"status": "success", "message": "Relationship deleted"})


# ==================== SEARCH & BROWSE ROUTES ====================


@architecture_crud_bp.route("/search", methods=["GET"])
@login_required
def search_elements():
    """Search elements by name, type, layer."""
    query = request.args.get("q", "")
    element_type = request.args.get("type")
    layer = request.args.get("layer")
    page = request.args.get("page", 1, type=int)

    results, total = search_service.search(
        query=query,
        element_type=element_type,
        layer=layer,
        page=page,
        per_page=20,
    )

    return render_template(
        "architecture/elements.html",
        results=results,
        total=total,
        query=query,
    )


@architecture_crud_bp.route("/by-layer/<layer>", methods=["GET"])
@login_required
def browse_by_layer(layer):
    """Browse elements by ArchiMate layer."""
    elements = ArchitectureElement.query.filter_by(layer=layer).limit(500).all()

    return render_template(
        "architecture/elements.html",
        layer=layer,
        elements=elements,
    )


# ==================== IMPORT/EXPORT ROUTES ====================


@architecture_crud_bp.route("/import", methods=["GET"])
@login_required
@require_roles("admin")
def import_form():
    """Show import form."""
    return jsonify({"success": True, "message": "Use POST to import architecture"})


@architecture_crud_bp.route("/import", methods=["POST"])
@login_required
@require_roles("admin")
def import_architecture():
    """Import architecture from file."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    file_type = request.args.get("format", "csv")

    try:
        result = import_export_service.import_data(file, file_type)
        return jsonify(
            {
                "status": "success",
                "imported": result["imported"],
                "skipped": result["skipped"],
                "errors": result["errors"],
            }
        )
    except Exception as e:
        current_app.logger.error(f"Architecture import failed: {str(e)}")
        return jsonify(
            {"error": "Import failed. Please check the file format and try again."}
        ), 400


@architecture_crud_bp.route("/export", methods=["GET"])
@login_required
@require_roles("admin")
def export_architecture():
    """Export architecture to file."""
    format_type = request.args.get("format", "csv")

    try:
        file_path, filename = import_export_service.export_data(format_type)

        # Schedule temp file cleanup after response is sent
        @after_this_request
        def _cleanup_export_file(response):
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as cleanup_err:
                current_app.logger.warning(
                    "Failed to clean up export temp file %s: %s",
                    file_path,
                    cleanup_err,
                )
            return response

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype="text/csv" if format_type == "csv" else "application/xml",
        )
    except Exception as e:
        current_app.logger.error(f"Architecture export failed: {str(e)}")
        return jsonify({"error": "Export failed. Please try again."}), 400


# ==================== API ENDPOINTS ====================


def _element_to_dict(e, rel_count=None, sol_count=None):
    """Serialize an ArchiMateElement to dict."""
    d = {
        "id": e.id,
        "name": e.name,
        "type": e.type,
        "layer": e.layer,
        "description": e.description,
        "scope": getattr(e, "scope", None),
        "parent_id": getattr(e, "parent_id", None),
        "architecture_id": getattr(e, "architecture_id", None),
    }
    if rel_count is not None:
        d["relationship_count"] = rel_count
    if sol_count is not None:
        d["solution_count"] = sol_count
    return d


def _relationship_to_dict(r):
    """Serialize an ArchiMateRelationship to dict."""
    return {
        "id": r.id,
        "type": r.type,
        "source_id": r.source_id,
        "target_id": r.target_id,
        "architecture_id": getattr(r, "architecture_id", None),
    }


@architecture_crud_bp.route("/api/elements", methods=["GET"])
@login_required
def api_list_elements():
    """API: List elements (JSON) with relationship + solution counts (ARCH-002)."""
    from sqlalchemy import func, or_

    # Subquery: count relationships where element is source or target
    rel_sub = (
        db.session.query(
            Relationship.source_id.label("eid"),
            func.count(Relationship.id).label("cnt"),
        )
        .group_by(Relationship.source_id)
        .subquery()
    )
    rel_sub_t = (
        db.session.query(
            Relationship.target_id.label("eid"),
            func.count(Relationship.id).label("cnt"),
        )
        .group_by(Relationship.target_id)
        .subquery()
    )

    # Subquery: count solutions linked to each element
    try:
        from app.models.solution_archimate_element import SolutionArchiMateElement
        sol_sub = (
            db.session.query(
                SolutionArchiMateElement.element_id.label("eid"),
                func.count(SolutionArchiMateElement.id).label("cnt"),
            )
            .group_by(SolutionArchiMateElement.element_id)
            .subquery()
        )
    except Exception:
        sol_sub = None

    elements = ArchitectureElement.query.limit(500).all()

    # Build count lookup dicts for efficiency
    rel_src = {r.eid: r.cnt for r in db.session.query(rel_sub).all()}
    rel_tgt = {r.eid: r.cnt for r in db.session.query(rel_sub_t).all()}
    sol_map = {}
    if sol_sub is not None:
        sol_map = {r.eid: r.cnt for r in db.session.query(sol_sub).all()}

    result = []
    for e in elements:
        rc = (rel_src.get(e.id) or 0) + (rel_tgt.get(e.id) or 0)
        sc = sol_map.get(e.id) or 0
        result.append(_element_to_dict(e, rel_count=rc, sol_count=sc))

    return jsonify({"status": "success", "elements": result})


@architecture_crud_bp.route("/api/relationships", methods=["GET"])
@login_required
def api_list_relationships():
    """API: List relationships (JSON)."""
    relationships = Relationship.query.limit(500).all()
    return jsonify(
        {
            "status": "success",
            "relationships": [_relationship_to_dict(r) for r in relationships],
        }
    )


@architecture_crud_bp.route(
    "/api/elements/<int:element_id>/relationships", methods=["GET"]
)
@login_required
def api_element_relationships(element_id):
    """API: Get relationships for an element."""
    ArchitectureElement.query.get_or_404(element_id)

    incoming = Relationship.query.filter_by(target_id=element_id).all()
    outgoing = Relationship.query.filter_by(source_id=element_id).all()

    return jsonify(
        {
            "status": "success",
            "incoming": [_relationship_to_dict(r) for r in incoming],
            "outgoing": [_relationship_to_dict(r) for r in outgoing],
        }
    )


@architecture_crud_bp.route("/api/validate/relationships", methods=["POST"])
@login_required
def api_validate_relationships():
    """API: Validate all relationships for integrity."""
    errors = validator.validate_relationships_integrity()

    return jsonify(
        {
            "status": "success" if not errors else "warning",
            "valid": len(errors) == 0,
            "errors": errors,
        }
    )
