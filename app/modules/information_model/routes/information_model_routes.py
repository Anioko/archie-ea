"""Business information model routes — the BIZBOK information map.

Blueprint: ``information_model``, url_prefix ``/information-model``.

Pages
    GET  /information-model/                    domains and the objects under them
    GET  /information-model/objects/<id>        one object: definition, stewardship,
                                                relationships, capability CRUD, apps
    GET  /information-model/crud-matrix         capability x object CRUD grid

Form posts (redirect back to the page they came from)
    POST /information-model/domains
    POST /information-model/domains/<id>/edit
    POST /information-model/domains/<id>/delete
    POST /information-model/objects
    POST /information-model/objects/<id>/edit
    POST /information-model/objects/<id>/delete

JSON API
    GET    /information-model/api/capabilities            capability picker
    GET    /information-model/api/objects                 object picker
    GET    /information-model/api/crud-matrix             grid data
    POST   /information-model/api/crud                    upsert a CRUD cell
    PUT    /information-model/api/crud                    upsert a CRUD cell
    DELETE /information-model/api/crud                    clear a CRUD cell
    POST   /information-model/api/relationships           relate two objects
    DELETE /information-model/api/relationships/<id>      unrelate them
    POST   /information-model/api/applications            set an application's role
    DELETE /information-model/api/applications/<id>       remove the link

Reads are ``@login_required``; every write additionally carries
``@require_roles("admin", "architect", "business_architect")`` — modelling the
information map is a business architect's job, and before this a plain
authenticated user could have rewritten another team's system of record.
"""

import logging

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.decorators import require_roles
from app.modules.information_model.services import information_model_service as im_service

logger = logging.getLogger(__name__)

information_model = Blueprint(
    "information_model", __name__, url_prefix="/information-model"
)

_WRITE_ROLES = ("admin", "architect", "business_architect")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@information_model.route("/")
@login_required
def index():
    """The information map: data domains and the business objects under them."""
    try:
        info_map = im_service.build_information_map()
        load_error = False
    except Exception:
        logger.error("Failed to build the information map", exc_info=True)
        info_map = {"domains": [], "unfiled": [], "object_count": 0}
        load_error = True

    return render_template(
        "information_model/index.html",
        info_map=info_map,
        load_error=load_error,
        classifications=im_service.DATA_CLASSIFICATIONS,
        object_types=im_service.OBJECT_TYPES,
    )


@information_model.route("/objects/<int:object_id>")
@login_required
def object_detail(object_id):
    """One business object, with everything the architecture says about it."""
    detail = im_service.get_object_detail(object_id)
    if not detail:
        return (
            render_template(
                "information_model/index.html",
                info_map={"domains": [], "unfiled": [], "object_count": 0},
                load_error=False,
                not_found=True,
                classifications=im_service.DATA_CLASSIFICATIONS,
                object_types=im_service.OBJECT_TYPES,
            ),
            404,
        )

    return render_template(
        "information_model/detail.html",
        obj=detail,
        domains=im_service.list_domains(),
        classifications=im_service.DATA_CLASSIFICATIONS,
        object_types=im_service.OBJECT_TYPES,
        relationship_types=im_service.OBJECT_RELATIONSHIP_TYPES,
        system_roles=im_service.SYSTEM_ROLES,
        system_role_labels=im_service.SYSTEM_ROLE_LABELS,
    )


@information_model.route("/crud-matrix")
@login_required
def crud_matrix():
    """Capability x business-object CRUD grid."""
    domain_id = request.args.get("domain_id", type=int)
    return render_template(
        "information_model/crud_matrix.html",
        domains=im_service.list_domains(),
        selected_domain_id=domain_id,
    )


# ---------------------------------------------------------------------------
# Data domain form posts
# ---------------------------------------------------------------------------


@information_model.route("/domains", methods=["POST"])
@login_required
@require_roles(*_WRITE_ROLES)
def create_domain():
    try:
        im_service.create_domain(request.form.to_dict())
    except Exception:
        db.session.rollback()
        logger.error("Failed to create data domain", exc_info=True)
    return redirect(url_for("information_model.index"))


@information_model.route("/domains/<int:domain_id>/edit", methods=["POST"])
@login_required
@require_roles(*_WRITE_ROLES)
def edit_domain(domain_id):
    try:
        im_service.update_domain(domain_id, request.form.to_dict())
    except Exception:
        db.session.rollback()
        logger.error("Failed to update data domain %s", domain_id, exc_info=True)
    return redirect(url_for("information_model.index"))


@information_model.route("/domains/<int:domain_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_domain(domain_id):
    try:
        im_service.delete_domain(domain_id)
    except Exception:
        db.session.rollback()
        logger.error("Failed to delete data domain %s", domain_id, exc_info=True)
    return redirect(url_for("information_model.index"))


# ---------------------------------------------------------------------------
# Business object form posts
# ---------------------------------------------------------------------------


@information_model.route("/objects", methods=["POST"])
@login_required
@require_roles(*_WRITE_ROLES)
def create_object():
    try:
        obj = im_service.create_object(request.form.to_dict())
        return redirect(url_for("information_model.object_detail", object_id=obj.id))
    except Exception:
        db.session.rollback()
        logger.error("Failed to create business object", exc_info=True)
        return redirect(url_for("information_model.index"))


@information_model.route("/objects/<int:object_id>/edit", methods=["POST"])
@login_required
@require_roles(*_WRITE_ROLES)
def edit_object(object_id):
    try:
        im_service.update_object(object_id, request.form.to_dict())
    except Exception:
        db.session.rollback()
        logger.error("Failed to update business object %s", object_id, exc_info=True)
    return redirect(url_for("information_model.object_detail", object_id=object_id))


@information_model.route("/objects/<int:object_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_object(object_id):
    try:
        im_service.delete_object(object_id)
    except Exception:
        db.session.rollback()
        logger.error("Failed to delete business object %s", object_id, exc_info=True)
    return redirect(url_for("information_model.index"))


# ---------------------------------------------------------------------------
# JSON API — pickers
# ---------------------------------------------------------------------------


@information_model.route("/api/capabilities")
@login_required
def api_capabilities():
    try:
        capabilities = im_service.search_capabilities(
            request.args.get("q", ""), request.args.get("limit", 25, type=int)
        )
    except Exception:
        logger.error("Capability search failed", exc_info=True)
        return jsonify({"error": "Capability search failed"}), 500
    return jsonify({"success": True, "capabilities": capabilities})


@information_model.route("/api/objects")
@login_required
def api_objects():
    try:
        objects = im_service.search_objects(
            request.args.get("q", ""),
            request.args.get("limit", 25, type=int),
            exclude_id=request.args.get("exclude_id", type=int),
        )
    except Exception:
        logger.error("Business object search failed", exc_info=True)
        return jsonify({"error": "Business object search failed"}), 500
    return jsonify({"success": True, "objects": objects})


# ---------------------------------------------------------------------------
# JSON API — CRUD matrix
# ---------------------------------------------------------------------------


@information_model.route("/api/crud-matrix")
@login_required
def api_crud_matrix():
    try:
        matrix = im_service.build_crud_matrix(request.args.get("domain_id", type=int))
    except Exception:
        logger.error("Failed to build the CRUD matrix", exc_info=True)
        return jsonify({"error": "Failed to build the CRUD matrix"}), 500
    return jsonify({"success": True, **matrix})


@information_model.route("/api/crud", methods=["POST", "PUT"])
@login_required
@require_roles(*_WRITE_ROLES)
def api_upsert_crud():
    """Create or update one capability x object CRUD cell.

    Body: {"capability_id": 1, "business_object_id": 2, "creates": true,
           "reads": true, "updates": false, "deletes": false,
           "is_owning_capability": false, "notes": null}
    """
    data = request.get_json(silent=True) or {}
    try:
        capability_id = int(data.get("capability_id"))
        business_object_id = int(data.get("business_object_id"))
    except (TypeError, ValueError):
        return (
            jsonify({"error": "capability_id and business_object_id must be integers"}),
            400,
        )

    try:
        row = im_service.upsert_crud_cell(capability_id, business_object_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        logger.error("Failed to upsert a CRUD cell", exc_info=True)
        return jsonify({"error": "Failed to save the CRUD cell"}), 500

    return jsonify(
        {
            "success": True,
            "cell": {
                "id": row.id,
                "capability_id": row.capability_id,
                "business_object_id": row.business_object_id,
                "creates": bool(row.creates),
                "reads": bool(row.reads),
                "updates": bool(row.updates),
                "deletes": bool(row.deletes),
                "is_owning_capability": bool(row.is_owning_capability),
                "letters": row.crud_letters,
                "notes": row.notes,
            },
        }
    )


@information_model.route("/api/crud", methods=["DELETE"])
@login_required
@require_roles(*_WRITE_ROLES)
def api_delete_crud():
    data = request.get_json(silent=True) or {}
    try:
        capability_id = int(data.get("capability_id"))
        business_object_id = int(data.get("business_object_id"))
    except (TypeError, ValueError):
        return (
            jsonify({"error": "capability_id and business_object_id must be integers"}),
            400,
        )

    try:
        deleted = im_service.delete_crud_cell(capability_id, business_object_id)
    except Exception:
        db.session.rollback()
        logger.error("Failed to delete a CRUD cell", exc_info=True)
        return jsonify({"error": "Failed to clear the CRUD cell"}), 500
    return jsonify({"success": True, "deleted": deleted})


# ---------------------------------------------------------------------------
# JSON API — object relationships
# ---------------------------------------------------------------------------


@information_model.route("/api/relationships", methods=["POST"])
@login_required
@require_roles(*_WRITE_ROLES)
def api_create_relationship():
    """Relate two business objects. Body: source_object_id, target_object_id,
    relationship_type, description."""
    data = request.get_json(silent=True) or {}
    try:
        source_object_id = int(data.get("source_object_id"))
        target_object_id = int(data.get("target_object_id"))
    except (TypeError, ValueError):
        return (
            jsonify({"error": "source_object_id and target_object_id must be integers"}),
            400,
        )

    try:
        rel = im_service.create_object_relationship(
            source_object_id,
            target_object_id,
            data.get("relationship_type", ""),
            data.get("description"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        logger.error("Failed to relate two business objects", exc_info=True)
        return jsonify({"error": "Failed to save the relationship"}), 500

    return jsonify({"success": True, "relationship": {"id": rel.id, "type": rel.type}})


@information_model.route("/api/relationships/<int:relationship_id>", methods=["DELETE"])
@login_required
@require_roles(*_WRITE_ROLES)
def api_delete_relationship(relationship_id):
    try:
        deleted = im_service.delete_object_relationship(relationship_id)
    except Exception:
        db.session.rollback()
        logger.error("Failed to delete relationship %s", relationship_id, exc_info=True)
        return jsonify({"error": "Failed to delete the relationship"}), 500
    if not deleted:
        return jsonify({"error": "Relationship not found"}), 404
    return jsonify({"success": True, "deleted": True})


# ---------------------------------------------------------------------------
# JSON API — application mastering
# ---------------------------------------------------------------------------


@information_model.route("/api/applications", methods=["POST", "PUT"])
@login_required
@require_roles(*_WRITE_ROLES)
def api_set_application():
    """Record which part an application plays for an object.

    Body: business_object_id, application_id, system_role, storage_type, notes.
    """
    data = request.get_json(silent=True) or {}
    try:
        business_object_id = int(data.get("business_object_id"))
        application_id = int(data.get("application_id"))
    except (TypeError, ValueError):
        return (
            jsonify({"error": "business_object_id and application_id must be integers"}),
            400,
        )

    try:
        row = im_service.set_object_application(business_object_id, application_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        logger.error("Failed to record an application link", exc_info=True)
        return jsonify({"error": "Failed to save the application link"}), 500

    return jsonify(
        {
            "success": True,
            "link": {
                "id": row.id,
                "application_id": row.application_id,
                "system_role": row.system_role,
                "system_role_label": im_service.SYSTEM_ROLE_LABELS.get(row.system_role),
            },
        }
    )


@information_model.route("/api/applications/<int:link_id>", methods=["DELETE"])
@login_required
@require_roles(*_WRITE_ROLES)
def api_delete_application(link_id):
    try:
        deleted = im_service.delete_object_application(link_id)
    except Exception:
        db.session.rollback()
        logger.error("Failed to delete application link %s", link_id, exc_info=True)
        return jsonify({"error": "Failed to delete the application link"}), 500
    if not deleted:
        return jsonify({"error": "Application link not found"}), 404
    return jsonify({"success": True, "deleted": True})
