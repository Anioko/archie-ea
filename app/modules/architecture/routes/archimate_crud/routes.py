"""
Architecture CRUD Routes
Unified dashboard for managing Motivation, Strategy, and Business layer elements
"""

import json
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
from flask_login import login_required
from sqlalchemy import or_

from app import db
from . import archimate_crud
from .services.ai_generation_service import AIGenerationService
from .services.field_configs import get_element_config, create_empty_form_data

# Application Layer imports
from app.models.application_layer import (
    ApplicationCollaboration,
    ApplicationComponent,
    ApplicationEvent,
    ApplicationFunction,
    ApplicationInteraction,
    ApplicationInterface,
    ApplicationProcess,
    ApplicationService,
    DataObject,
)
from app.models.archimate_business import Contract
from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
from app.models.archimate_missing_elements import (
    MissingBusinessCollaboration,
    MissingBusinessInteraction,
    MissingBusinessInterface,
    Product,
    Stakeholder,
)
from app.models.business_capabilities import BusinessCapability, BusinessFunction
from app.models.business_layer import (
    BusinessActor,
    BusinessEvent,
    BusinessObject,
    BusinessRole,
    BusinessService,
)

# Implementation Layer imports
from app.models.implementation_migration import Deliverable as PlanningDeliverable
from app.models.implementation_migration import Gap
from app.models.implementation_migration import Plateau
from app.models.implementation_migration import WorkPackage
from app.models.models import ConstraintElement, Outcome, Principle, Requirement
from app.models.motivation import Assessment, Driver, Goal, Meaning, Value
from app.models.process_data import BusinessProcess
from app.models.representation import Representation
from app.models.strategy_layer import CourseOfAction, StrategyResource

# Technology Layer imports
from app.models.technology_layer import (
    CommunicationNetwork,
    Device,
    Node,
    Path,
    SystemSoftware,
    TechnologyInterface,
    TechnologyService,
)
from app.models.unified_capability import ValueStream
import logging

logger = logging.getLogger(__name__)

# Model registry mapping element types to model classes
MODEL_REGISTRY = {
    # Motivation Layer
    "Stakeholder": Stakeholder,
    "Driver": Driver,
    "Assessment": Assessment,
    "Goal": Goal,
    "Outcome": Outcome,
    "Principle": Principle,
    "Requirement": Requirement,
    "Constraint": ConstraintElement,
    "Meaning": Meaning,
    "Value": Value,
    # Strategy Layer
    "Resource": StrategyResource,
    "Capability": BusinessCapability,  # BusinessCapability is the Strategy layer capability model
    "ValueStream": ValueStream,
    "CourseOfAction": CourseOfAction,
    # Business Layer
    "BusinessActor": BusinessActor,
    "BusinessRole": BusinessRole,
    "BusinessCollaboration": MissingBusinessCollaboration,
    "BusinessInterface": MissingBusinessInterface,
    "BusinessProcess": BusinessProcess,
    "BusinessFunction": BusinessFunction,
    "BusinessInteraction": MissingBusinessInteraction,
    "BusinessEvent": BusinessEvent,
    "BusinessService": BusinessService,
    "BusinessObject": BusinessObject,
    "Contract": Contract,
    "Representation": Representation,
    "Product": Product,
    # Application Layer
    "ApplicationComponent": ApplicationComponent,
    "ApplicationInterface": ApplicationInterface,
    "ApplicationService": ApplicationService,
    "ApplicationFunction": ApplicationFunction,
    "ApplicationProcess": ApplicationProcess,
    "ApplicationInteraction": ApplicationInteraction,
    "ApplicationEvent": ApplicationEvent,
    "ApplicationCollaboration": ApplicationCollaboration,
    "DataObject": DataObject,
    # Technology Layer
    "Node": Node,
    "Device": Device,
    "SystemSoftware": SystemSoftware,
    "TechnologyService": TechnologyService,
    "TechnologyInterface": TechnologyInterface,
    "Path": Path,
    "CommunicationNetwork": CommunicationNetwork,
    # Implementation & Migration Layer
    "WorkPackage": WorkPackage,
    "Deliverable": PlanningDeliverable,
    "Plateau": Plateau,
    "Gap": Gap,
}

# Layer configuration
LAYER_CONFIG = {
    "motivation": {
        "name": "Motivation Layer",
        "elements": [
            "Stakeholder",
            "Driver",
            "Assessment",
            "Goal",
            "Outcome",
            "Principle",
            "Requirement",
            "Constraint",
            "Meaning",
            "Value",
        ],
        "icon": "🎯",
    },
    "strategy": {
        "name": "Strategy Layer",
        "elements": ["Resource", "Capability", "ValueStream", "CourseOfAction"],
        "icon": "📊",
    },
    "business": {
        "name": "Business Layer",
        "elements": [
            "BusinessActor",
            "BusinessRole",
            "BusinessCollaboration",
            "BusinessInterface",
            "BusinessProcess",
            "BusinessFunction",
            "BusinessInteraction",
            "BusinessEvent",
            "BusinessService",
            "BusinessObject",
            "Contract",
            "Representation",
            "Product",
        ],
        "icon": "💼",
    },
    "application": {
        "name": "Application Layer",
        "elements": [
            "ApplicationComponent",
            "ApplicationInterface",
            "ApplicationService",
            "ApplicationFunction",
            "ApplicationProcess",
            "ApplicationInteraction",
            "ApplicationEvent",
            "ApplicationCollaboration",
            "DataObject",
        ],
        "icon": "🖥️",
    },
    "technology": {
        "name": "Technology Layer",
        "elements": [
            "Node",
            "Device",
            "SystemSoftware",
            "TechnologyService",
            "TechnologyInterface",
            "Path",
            "CommunicationNetwork",
        ],
        "icon": "⚙️",
    },
    "implementation": {
        "name": "Implementation & Migration Layer",
        "elements": ["WorkPackage", "Deliverable", "Plateau", "Gap"],
        "icon": "🚀",
    },
}


# Fields to skip when auto-discovering displayable attributes
_SKIP_FIELDS = frozenset(
    {
        "id",
        "name",
        "title",
        "description",
        "created_at",
        "updated_at",
        "archimate_element_id",
        "architecture_id",
        "canonical_capability_id",
        "parent_capability_id",
        "deprecated_in_favor_of_id",
        "goal_id",
        "master_system_id",
        "parent_id",
        # ArchiMate identity — shown in header/identity card
        "type",
        "layer",
        "scope",
        "building_block_type",
        "plateau",
        "status",
        "organization_id",
    }
)


def _get_display_fields(element, model_class):
    """Introspect a model instance and return a list of (label, value) tuples
    for all non-empty, non-private, non-FK columns worth displaying."""
    from sqlalchemy import inspect as sa_inspect

    fields = []
    try:
        mapper = sa_inspect(model_class)
    except Exception:
        return fields

    for col in mapper.columns:
        col_name = col.key
        # Skip internal / already-displayed fields
        if col_name in _SKIP_FIELDS or col_name.startswith("_"):
            continue
        # Skip foreign keys (except those with domain meaning)
        if col.foreign_keys and col_name not in ("goal_id",):
            continue

        value = getattr(
            element, col_name, None
        )  # model-safety-ok: dynamic column iteration via sa_inspect mapper
        if value is None or value == "":
            continue
        # Skip 0 for numeric types only (not booleans)
        if not isinstance(value, bool) and value == 0:
            continue

        # Build a human-readable label from snake_case
        label = col_name.replace("_", " ").title()

        # Format special types
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        elif hasattr(value, "strftime"):
            value = value.strftime("%Y-%m-%d %H:%M")
        elif isinstance(value, float):
            value = f"{value:.2f}" if value != int(value) else str(int(value))

        fields.append({"label": label, "value": str(value)})

    return fields


@archimate_crud.route("/")
@archimate_crud.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard with tabs for each layer"""
    return render_template("archimate_crud/dashboard.html", layer_config=LAYER_CONFIG)


@archimate_crud.route("/api/layer/<layer>/count")
@login_required
def api_layer_count(layer):
    """Return the total element count for a layer using SQL COUNT — fast path
    used by the dashboard tab badges.  Avoids loading all rows into Python.

    Counts from both dedicated per-type tables (portfolio source) and
    archimate_elements (architecture source) to match the elements endpoint
    behaviour.  Dedicated-table rows and archimate_elements rows for the same
    logical element are counted once each (they have different numeric IDs in
    different tables, so an exact dedup requires a full scan — we accept the
    small over-count here in favour of O(1) SQL COUNT queries that never hang).
    """
    if layer not in LAYER_CONFIG:
        return jsonify({"success": False, "error": f"Unknown layer: {layer}"}), 404

    layer_types = LAYER_CONFIG[layer]["elements"]
    total = 0
    # Count from dedicated per-type tables
    for etype in layer_types:
        model_class = MODEL_REGISTRY.get(etype)
        if not model_class:
            continue
        try:
            total += model_class.query.count()
        except Exception as e:
            current_app.logger.warning(f"api_layer_count: count failed for {etype}: {e}")

    # Count from archimate_elements for this layer
    try:
        ae_count = ArchiMateElement.query.filter(
            db.func.lower(ArchiMateElement.layer) == layer.lower(),
        ).count()
        total += ae_count
    except Exception as e:
        current_app.logger.warning(f"api_layer_count: archimate_elements count failed for {layer}: {e}")

    return jsonify({"layer": layer, "total": total})


@archimate_crud.route("/api/layer/<layer>/elements")
@login_required
def api_layer_elements(layer):
    """Return all elements for a layer (all types combined) as JSON.

    Supports: search, element_type filter, pagination, sorting.
    """
    import math

    if layer not in LAYER_CONFIG:
        return jsonify({"success": False, "error": f"Unknown layer: {layer}"}), 404

    search = request.args.get("search", "").strip()
    type_filter = request.args.get("element_type", "").strip()
    source_filter = request.args.get("source", "").strip()  # "portfolio", "architecture", or ""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "name")
    sort_order = request.args.get("sort_order", "asc")

    layer_types = LAYER_CONFIG[layer]["elements"]
    if type_filter:
        # Support comma-separated list of types (viewpoint filter) or single type
        requested_types = [t.strip() for t in type_filter.split(",") if t.strip()]
        query_types = [t for t in requested_types if t in layer_types] or layer_types
    else:
        query_types = layer_types

    all_elements = []
    if source_filter != "architecture":  # skip dedicated tables when filtering to architecture-only
        for etype in query_types:
            model_class = MODEL_REGISTRY.get(etype)
            if not model_class:
                continue
            try:
                q = model_class.query
                if search:
                    safe_search = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                    filters = []
                    if hasattr(
                        model_class, "name"
                    ):  # model-safety-ok: polymorphic ArchiMate elements
                        filters.append(model_class.name.ilike(f"%{safe_search}%", escape="\\"))
                    if hasattr(
                        model_class, "description"
                    ):  # model-safety-ok: polymorphic ArchiMate elements
                        filters.append(model_class.description.ilike(f"%{safe_search}%", escape="\\"))
                    if filters:
                        q = q.filter(or_(*filters))
                for (
                    elem
                ) in q.all():  # model-safety-ok: small fixed set (max 10 layer types)
                    name = getattr(elem, "name", None) or getattr(
                        elem, "title", "Unnamed"
                    )  # model-safety-ok: polymorphic ArchiMate elements
                    status = getattr(elem, "status", None) or getattr(
                        elem, "operational_status", None
                    )  # model-safety-ok: polymorphic ArchiMate elements
                    all_elements.append(
                        {
                            "id": elem.id,
                            "name": name,
                            "description": getattr(elem, "description", "")
                            or "",  # model-safety-ok: polymorphic ArchiMate elements
                            "element_type": etype,
                            "status": status,
                            "layer": layer,
                            "source": "portfolio",
                            "properties": getattr(elem, "properties", None) or "",
                            "rel_count": None,
                        }
                    )
            except Exception as e:
                current_app.logger.warning(f"Error querying {etype}: {e}")

    # Supplement: also pull from archimate_elements for any elements not already
    # found in dedicated tables (handles data imported via other paths).
    if source_filter != "portfolio":  # skip archimate_elements when filtering to portfolio-only
        try:
            seen_pairs = {(el["element_type"], el["id"]) for el in all_elements}
            ae_q = ArchiMateElement.query.filter(
                db.func.lower(ArchiMateElement.layer) == layer.lower(),
                ArchiMateElement.type.in_(query_types),
            )
            if search:
                safe_s = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                ae_q = ae_q.filter(
                    or_(
                        ArchiMateElement.name.ilike(f"%{safe_s}%", escape="\\"),
                        ArchiMateElement.description.ilike(f"%{safe_s}%", escape="\\"),
                    )
                )
            for ae in ae_q.all():
                if (ae.type, ae.id) not in seen_pairs:
                    _rel_count = ArchiMateRelationship.query.filter(
                        db.or_(
                            ArchiMateRelationship.source_id == ae.id,
                            ArchiMateRelationship.target_id == ae.id,
                        )
                    ).count()
                    all_elements.append(
                        {
                            "id": ae.id,
                            "name": ae.name or "",
                            "description": ae.description or "",
                            "element_type": ae.type,
                            "status": None,
                            "layer": layer,
                            "source": "architecture",
                            "properties": ae.properties or "",
                            "rel_count": _rel_count,
                        }
                    )
        except Exception as e:
            current_app.logger.warning(f"Error supplementing from archimate_elements: {e}")

    reverse = sort_order == "desc"
    if sort_by in ("name", "element_type", "description", "status"):
        all_elements.sort(key=lambda x: (x.get(sort_by) or "").lower(), reverse=reverse)

    total = len(all_elements)
    pages = math.ceil(total / per_page) if per_page > 0 else 1
    start = (page - 1) * per_page
    end = start + per_page
    page_elements = all_elements[start:end]

    return jsonify(
        {
            "elements": page_elements,
            "pagination": {
                "page": page,
                "pages": pages,
                "per_page": per_page,
                "total": total,
                "has_next": page < pages,
                "has_prev": page > 1,
            },
            "layer": layer,
            "element_types": layer_types,
        }
    )


@archimate_crud.route("/<layer>/<element_type>")
@login_required
def list_elements(layer, element_type):
    """List all elements of a specific type"""
    model_class = MODEL_REGISTRY.get(element_type)

    if not model_class:
        flash(f"Element type {element_type} is not yet supported", "warning")
        return redirect(url_for("archimate_crud.dashboard"))

    # Get search/filter parameters
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    view_mode = request.args.get("view", "table", type=str)  # table or card

    # Build query
    query = model_class.query

    # Apply search filter (escape LIKE wildcards to prevent injection)
    if search:
        safe_search = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        if hasattr(model_class, "name"):
            query = query.filter(model_class.name.ilike(f"%{safe_search}%", escape="\\"))
        if hasattr(model_class, "description"):
            query = query.filter(
                or_(
                    model_class.description.ilike(f"%{safe_search}%", escape="\\"),
                    model_class.name.ilike(f"%{safe_search}%", escape="\\"),
                )
            )

    # Order by name
    if hasattr(model_class, "name"):
        query = query.order_by(model_class.name)
    elif hasattr(model_class, "title"):
        query = query.order_by(model_class.title)

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    elements = pagination.items

    # Convert to dict for JSON serialization
    elements_data = []
    for elem in elements:
        elem_dict = {
            "id": elem.id,
            "name": getattr(
                elem, "name", getattr(elem, "title", "Unnamed")
            ),  # model-safety-ok: polymorphic ArchiMate elements
            "description": getattr(
                elem, "description", ""
            ),  # model-safety-ok: polymorphic ArchiMate elements
            "archimate_element_id": getattr(
                elem, "archimate_element_id", None
            ),  # model-safety-ok: polymorphic ArchiMate elements
        }
        # Add layer-specific fields
        if hasattr(elem, "status"):  # model-safety-ok: polymorphic ArchiMate elements
            elem_dict["status"] = elem.status
        if hasattr(
            elem, "operational_status"
        ):  # model-safety-ok: polymorphic ArchiMate elements
            elem_dict["status"] = elem.operational_status
        elements_data.append(elem_dict)

    # If AJAX request, return JSON
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(
            {
                "elements": elements_data,
                "pagination": {
                    "page": page,
                    "pages": pagination.pages,
                    "per_page": per_page,
                    "total": pagination.total,
                    "has_next": pagination.has_next,
                    "has_prev": pagination.has_prev,
                },
            }
        )

    return render_template(
        "archimate_crud/dashboard.html",
        layer=layer,
        element_type=element_type,
        elements=elements,
        pagination=pagination,
        search=search,
        view_mode=view_mode,
        layer_config=LAYER_CONFIG,
    )


@archimate_crud.route("/<layer>/<element_type>/new", methods=["GET", "POST"])
@login_required
def create_element(layer, element_type):
    """Create a new element"""
    model_class = MODEL_REGISTRY.get(element_type)

    if not model_class:
        flash(f"Element type {element_type} is not yet supported", "warning")
        return redirect(url_for("archimate_crud.dashboard"))

    if request.method == "POST":
        try:
            data = request.get_json() if request.is_json else request.form.to_dict()

            # Create model instance
            element = model_class()

            # Set basic fields
            if hasattr(
                element, "name"
            ):  # model-safety-ok: polymorphic ArchiMate elements
                element.name = data.get("name", "").strip()
            elif hasattr(
                element, "title"
            ):  # model-safety-ok: polymorphic ArchiMate elements
                element.title = data.get("name", "").strip()

            if hasattr(
                element, "description"
            ):  # model-safety-ok: polymorphic ArchiMate elements
                element.description = data.get("description", "").strip()

            # Set layer-specific fields based on model
            _set_model_fields(element, data, model_class)

            # Auto-create ArchiMateElement if not provided
            if not element.archimate_element_id:
                archimate_element = ArchiMateElement(
                    name=element.name
                    if hasattr(element, "name")
                    else element.title,  # model-safety-ok: polymorphic ArchiMate elements
                    type=element_type,
                    layer=layer.capitalize(),
                    description=getattr(
                        element, "description", ""
                    ),  # model-safety-ok: polymorphic ArchiMate elements
                )
                db.session.add(archimate_element)
                db.session.flush()
                element.archimate_element_id = archimate_element.id

            db.session.add(element)
            db.session.commit()

            if request.is_json:
                return jsonify(
                    {
                        "success": True,
                        "id": element.id,
                        "message": f"{element_type} created successfully",
                    }
                )

            flash(f"{element_type} created successfully", "success")
            return redirect(
                url_for(
                    "archimate_crud.detail_element",
                    layer=layer,
                    element_type=element_type,
                    element_id=element.id,
                )
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error creating {element_type}: {str(e)}", exc_info=True
            )

            if request.is_json:
                return jsonify(
                    {"success": False, "error": "Invalid request parameters"}
                ), 400

            flash("Error creating {element_type}. Please try again.", "error")
            return render_template(
                "archimate_crud/dashboard.html",
                layer=layer,
                element_type=element_type,
                layer_config=LAYER_CONFIG,
                field_config=get_element_config(element_type),
                form_data=create_empty_form_data(element_type),
            )

    return render_template(
        "archimate_crud/dashboard.html",
        layer=layer,
        element_type=element_type,
        layer_config=LAYER_CONFIG,
        field_config=get_element_config(element_type),
        form_data=create_empty_form_data(element_type),
    )


@archimate_crud.route("/<layer>/<element_type>/<int:element_id>")
@login_required
def detail_element(layer, element_type, element_id):
    """View/edit element details"""
    # Unknown layer (e.g. a malformed URL) would otherwise crash the template that
    # indexes layer_config by layer name; return 404 for an invalid layer.
    if layer not in LAYER_CONFIG:
        abort(404)
    model_class = MODEL_REGISTRY.get(element_type)

    element = None
    if model_class:
        element = model_class.query.get(element_id)

    # Fall back to archimate_elements table (native ArchiMate elements)
    if element is None:
        element = ArchiMateElement.query.get_or_404(element_id)
        model_class = ArchiMateElement

    # Get relationships
    relationships = _get_element_relationships(element, element_id)

    # Auto-discover displayable fields from the model
    display_fields = _get_display_fields(element, model_class)

    return render_template(
        "archimate_crud/detail.html",
        layer=layer,
        element_type=element_type,
        element=element,
        relationships=relationships,
        display_fields=display_fields,
        layer_config=LAYER_CONFIG,
    )


@archimate_crud.route(
    "/<layer>/<element_type>/<int:element_id>/edit", methods=["GET", "POST"]
)
@login_required
def update_element(layer, element_type, element_id):
    """Update an element"""
    model_class = MODEL_REGISTRY.get(element_type)

    if not model_class:
        flash(f"Element type {element_type} is not yet supported", "warning")
        return redirect(url_for("archimate_crud.dashboard"))

    element = model_class.query.get(element_id)
    # Fall back to archimate_elements for elements stored there directly
    _from_ae = False
    if element is None:
        element = ArchiMateElement.query.get(element_id)
        _from_ae = True
    if element is None:
        if request.is_json:
            return jsonify({"success": False, "error": "Element not found"}), 404
        from flask import abort
        abort(404)

    if request.method == "POST":
        try:
            data = request.get_json() if request.is_json else request.form.to_dict()

            # Update basic fields
            if hasattr(
                element, "name"
            ):  # model-safety-ok: polymorphic ArchiMate elements
                element.name = data.get("name", "").strip()
            elif hasattr(
                element, "title"
            ):  # model-safety-ok: polymorphic ArchiMate elements
                element.title = data.get("name", "").strip()

            if hasattr(
                element, "description"
            ):  # model-safety-ok: polymorphic ArchiMate elements
                element.description = data.get("description", "").strip()

            if not _from_ae:
                # Update layer-specific fields only for dedicated model instances
                _set_model_fields(element, data, model_class)

                # Update ArchiMateElement if linked
                if getattr(element, "archimate_element_id", None):
                    archimate_element = ArchiMateElement.query.get(
                        element.archimate_element_id
                    )
                    if archimate_element:
                        archimate_element.name = (
                            element.name
                            if hasattr(element, "name")
                            else element.title  # model-safety-ok: polymorphic ArchiMate elements
                        )
                        archimate_element.description = getattr(
                            element, "description", ""
                        )  # model-safety-ok: polymorphic ArchiMate elements

            db.session.commit()

            if request.is_json:
                return jsonify(
                    {"success": True, "message": f"{element_type} updated successfully"}
                )

            flash(f"{element_type} updated successfully", "success")
            return redirect(
                url_for(
                    "archimate_crud.detail_element",
                    layer=layer,
                    element_type=element_type,
                    element_id=element.id,
                )
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error updating {element_type}: {str(e)}", exc_info=True
            )

            if request.is_json:
                return jsonify(
                    {"success": False, "error": "Invalid request parameters"}
                ), 400

            flash("Error updating {element_type}. Please try again.", "error")

    return render_template(
        "archimate_crud/dashboard.html",
        layer=layer,
        element_type=element_type,
        element=element,
        layer_config=LAYER_CONFIG,
    )


@archimate_crud.route(
    "/<layer>/<element_type>/<int:element_id>/delete", methods=["POST"]
)
@login_required
def delete_element(layer, element_type, element_id):
    """Delete an element"""
    model_class = MODEL_REGISTRY.get(element_type)

    if not model_class:
        if request.is_json:
            return jsonify(
                {"success": False, "error": "Element type not supported"}
            ), 400
        flash(f"Element type {element_type} is not yet supported", "warning")
        return redirect(url_for("archimate_crud.dashboard"))

    element = model_class.query.get(element_id)
    # Fall back to archimate_elements for elements stored there directly
    _from_ae = False
    if element is None:
        element = ArchiMateElement.query.get(element_id)
        _from_ae = True
    if element is None:
        if request.is_json:
            return jsonify({"success": False, "error": "Element not found"}), 404
        from flask import abort
        abort(404)

    try:
        if not _from_ae:
            # Delete linked ArchiMateElement if exists in dedicated model
            if getattr(element, "archimate_element_id", None):
                archimate_element = ArchiMateElement.query.get(element.archimate_element_id)
                if archimate_element:
                    db.session.delete(archimate_element)

        db.session.delete(element)
        db.session.commit()

        if request.is_json:
            return jsonify(
                {"success": True, "message": f"{element_type} deleted successfully"}
            )

        flash(f"{element_type} deleted successfully", "success")
        return redirect(
            url_for(
                "archimate_crud.list_elements", layer=layer, element_type=element_type
            )
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error deleting {element_type}: {str(e)}", exc_info=True
        )

        if request.is_json:
            return jsonify(
                {"success": False, "error": "Invalid request parameters"}
            ), 400

        flash("Error deleting {element_type}. Please try again.", "error")
        return redirect(
            url_for(
                "archimate_crud.detail_element",
                layer=layer,
                element_type=element_type,
                element_id=element_id,
            )
        )


@archimate_crud.route("/api/archimate/validate", methods=["POST"])
@login_required
def validate_archimate_model():
    """Run full ArchiMate 3.2 metamodel validation across all elements and relationships."""
    from app.modules.architecture.services.archimate_validation_service import ArchiMateValidationService
    service = ArchiMateValidationService()
    results = service.validate_all()
    return jsonify(results)


@archimate_crud.route("/api/archimate/elements/<int:element_id>/validate", methods=["GET"])
@login_required
def validate_archimate_element(element_id):
    """Validate a single ArchiMate element against ArchiMate 3.2 metamodel rules."""
    from app.modules.architecture.services.archimate_validation_service import ArchiMateValidationService
    element = ArchiMateElement.query.get_or_404(element_id)
    service = ArchiMateValidationService()
    issues = service.validate_element(element)
    return jsonify({'issues': issues, 'valid': len(issues) == 0})


@archimate_crud.route("/<layer>/<element_type>/bulk-delete", methods=["POST"])
@login_required
def bulk_delete(layer, element_type):
    """Bulk delete elements"""
    model_class = MODEL_REGISTRY.get(element_type)

    if not model_class:
        return jsonify({"success": False, "error": "Element type not supported"}), 400

    data = request.get_json()
    element_ids = data.get("ids", [])

    if not element_ids:
        return jsonify({"success": False, "error": "No elements selected"}), 400

    try:
        deleted_count = 0
        for element_id in element_ids:
            element = model_class.query.get(element_id)
            if element:
                # Delete linked ArchiMateElement
                if element.archimate_element_id:
                    archimate_element = ArchiMateElement.query.get(
                        element.archimate_element_id
                    )
                    if archimate_element:
                        db.session.delete(archimate_element)

                db.session.delete(element)
                deleted_count += 1

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": f"{deleted_count} {element_type}(s) deleted successfully",
                "deleted_count": deleted_count,
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error bulk deleting {element_type}: {str(e)}", exc_info=True
        )
        return jsonify({"success": False, "error": "Invalid request parameters"}), 400


@archimate_crud.route("/<layer>/<element_type>/export", methods=["GET"])
@login_required
def export_elements(layer, element_type):
    """Export elements to JSON/CSV"""
    model_class = MODEL_REGISTRY.get(element_type)

    if not model_class:
        flash(f"Element type {element_type} is not yet supported", "warning")
        return redirect(url_for("archimate_crud.dashboard"))

    format_type = request.args.get("format", "json")
    element_ids = request.args.getlist("ids")

    if element_ids:
        elements = model_class.query.filter(model_class.id.in_(element_ids)).all()
    else:
        elements = model_class.query.limit(5000).all()

    if format_type == "json":
        data = []
        for elem in elements:
            elem_dict = _element_to_dict(elem)
            data.append(elem_dict)

        response = jsonify(data)
        response.headers["Content-Disposition"] = (
            f"attachment; filename={element_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        return response

    # CSV export
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    if elements:
        first_elem = elements[0]
        headers = ["id", "name"]
        if hasattr(
            first_elem, "description"
        ):  # model-safety-ok: polymorphic ArchiMate elements
            headers.append("description")
        writer.writerow(headers)

        # Write data
        for elem in elements:
            row = [
                elem.id,
                getattr(elem, "name", getattr(elem, "title", "")),
            ]  # model-safety-ok: polymorphic ArchiMate elements
            if hasattr(
                elem, "description"
            ):  # model-safety-ok: polymorphic ArchiMate elements
                row.append(
                    getattr(elem, "description", "")
                )  # model-safety-ok: polymorphic ArchiMate elements
            writer.writerow(row)

    output.seek(0)
    response = current_app.response_class(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = (
        f"attachment; filename={element_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    return response


@archimate_crud.route("/<layer>/<element_type>/ai-generate", methods=["POST"])
@login_required
def ai_generate(layer, element_type):
    """AI-powered element generation from documents/internet"""
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        context = data.get("context", {})

        if not prompt:
            return jsonify({"success": False, "error": "Prompt is required"}), 400

        # Use AI generation service
        ai_service = AIGenerationService()
        result = ai_service.generate_element(
            layer=layer, element_type=element_type, prompt=prompt, context=context
        )

        return jsonify({"success": True, "data": result})

    except Exception as e:
        current_app.logger.error(f"Error in AI generation: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Invalid request parameters"}), 400


@archimate_crud.route("/<layer>/<element_type>/<int:element_id>/relationships")
@login_required
def element_relationships(layer, element_type, element_id):
    """Get relationships for an element"""
    model_class = MODEL_REGISTRY.get(element_type)

    if not model_class:
        return jsonify({"success": False, "error": "Element type not supported"}), 400

    element = model_class.query.get_or_404(element_id)
    relationships = _get_element_relationships(element, element_id)

    return jsonify({"success": True, "relationships": relationships})


@archimate_crud.route("/api/elements/<int:element_id>/detail")
@login_required
def api_element_detail(element_id):
    """ARC-006: Return full detail JSON for a single ArchiMate element.

    Returns element fields, outgoing/incoming relationships, and solution linkages.
    """
    element = ArchiMateElement.query.get_or_404(element_id)

    outgoing = []
    for rel in ArchiMateRelationship.query.filter_by(source_id=element_id).limit(50).all():
        target = ArchiMateElement.query.get(rel.target_id)
        outgoing.append({
            "id": rel.id,
            "type": rel.type or "",
            "target_id": rel.target_id,
            "target_name": target.name if target else f"#{rel.target_id}",
            "target_type": target.type if target else "",
            "target_layer": target.layer if target else "",
        })

    incoming = []
    for rel in ArchiMateRelationship.query.filter_by(target_id=element_id).limit(50).all():
        source = ArchiMateElement.query.get(rel.source_id)
        incoming.append({
            "id": rel.id,
            "type": rel.type or "",
            "source_id": rel.source_id,
            "source_name": source.name if source else f"#{rel.source_id}",
            "source_type": source.type if source else "",
            "source_layer": source.layer if source else "",
        })

    solutions = []
    try:
        from app.models.solution_archimate_element import SolutionArchiMateElement
        from app.models.solution_models import Solution
        for sae in SolutionArchiMateElement.query.filter_by(element_id=element_id).limit(20).all():
            sol = Solution.query.get(sae.solution_id) if sae.solution_id else None
            solutions.append({
                "solution_id": sae.solution_id,
                "solution_name": sol.name if sol else f"Solution #{sae.solution_id}",
                "element_role": sae.element_role or "",
                "created_at": sae.created_at.isoformat() if sae.created_at else None,
            })
    except Exception as e:
        current_app.logger.warning(f"Could not load solution linkages for element {element_id}: {e}")

    return jsonify({
        "id": element.id,
        "name": element.name,
        "type": element.type,
        "layer": element.layer,
        "description": element.description or "",
        "building_block_type": element.building_block_type or "",
        "outgoing": outgoing,
        "incoming": incoming,
        "solutions": solutions,
    })


@archimate_crud.route("/api/elements/<int:element_id>", methods=["PATCH"])
@login_required
def api_element_patch(element_id):
    """ARC-006: Partial update of an ArchiMate element's core fields."""
    element = ArchiMateElement.query.get_or_404(element_id)
    data = request.get_json() or {}

    allowed = {"name", "type", "layer", "description", "element_type"}
    for field in allowed:
        if field == "element_type":
            if "element_type" in data:
                element.type = data["element_type"]
        elif field in data and hasattr(element, field):
            setattr(element, field, data[field])

    try:
        db.session.commit()
        return jsonify({"success": True, "id": element.id})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"PATCH element {element_id} failed: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500




def _set_model_fields(element, data, model_class):
    """Set model-specific fields from data"""
    # Common fields
    common_fields = ["description", "status", "operational_status"]
    for field in common_fields:
        if (
            hasattr(element, field) and field in data
        ):  # model-safety-ok: polymorphic ArchiMate elements - not all models have all common fields
            setattr(element, field, data[field])

    # Model-specific field mapping
    field_mappings = {
        Driver: [
            "driver_type",
            "source",
            "urgency",
            "impact_scope",
            "impact_magnitude",
        ],
        Goal: [
            "goal_type",
            "category",
            "time_horizon",
            "target_value",
            "current_value",
        ],
        BusinessActor: ["actor_type", "location", "headcount", "cost_center"],
        BusinessRole: ["role_type", "authorization_level", "experience_years_required"],
        BusinessService: [
            "service_type",
            "business_criticality",
            "sla_availability_target",
        ],
        BusinessObject: ["data_classification", "contains_pii", "gdpr_scope"],
        StrategyResource: ["resource_type", "strategic_value", "competitive_advantage"],
        CourseOfAction: [
            "action_type",
            "strategic_theme",
            "risk_level",
            "progress_percentage",
        ],
        Stakeholder: [
            "stakeholder_type",
            "role",
            "department",
            "power_level",
            "interest_level",
        ],
        MissingBusinessCollaboration: [
            "collaboration_type",
            "purpose",
            "scope",
            "meeting_frequency",
        ],
        MissingBusinessInterface: [
            "interface_type",
            "access_method",
            "availability",
            "authentication_method",
        ],
        MissingBusinessInteraction: [
            "interaction_type",
            "trigger",
            "outcome",
            "frequency",
        ],
        Product: ["product_type", "product_category", "target_market", "pricing_model"],
    }

    if model_class in field_mappings:
        for field in field_mappings[model_class]:
            if (
                hasattr(element, field) and field in data
            ):  # model-safety-ok: polymorphic ArchiMate elements
                setattr(element, field, data[field])


def _get_element_relationships(element, element_id):
    """Get all relationships for an element"""
    relationships = []

    # Resolve the archimate_element_id to use for relationship lookup
    ae_id = None
    if hasattr(element, "archimate_element_id") and element.archimate_element_id:
        ae_id = element.archimate_element_id  # dedicated model linked to archimate_elements
    elif element.__class__.__name__ == "ArchiMateElement":
        ae_id = element.id  # element IS the archimate_elements row

    # Get ArchiMate relationships
    if ae_id:  # model-safety-ok: polymorphic ArchiMate elements
        # Outgoing relationships
        outgoing = ArchiMateRelationship.query.filter_by(
            source_id=ae_id
        ).all()
        for rel in outgoing:
            target_element = ArchiMateElement.query.get(rel.target_id)
            if target_element:
                relationships.append(
                    {
                        "type": rel.type,
                        "direction": "outgoing",
                        "target": {
                            "id": target_element.id,
                            "name": target_element.name,
                            "type": target_element.type,
                            "layer": target_element.layer,
                        },
                    }
                )

        # Incoming relationships
        incoming = ArchiMateRelationship.query.filter_by(
            target_id=ae_id
        ).all()
        for rel in incoming:
            source_element = ArchiMateElement.query.get(rel.source_id)
            if source_element:
                relationships.append(
                    {
                        "type": rel.type,
                        "direction": "incoming",
                        "source": {
                            "id": source_element.id,
                            "name": source_element.name,
                            "type": source_element.type,
                            "layer": source_element.layer,
                        },
                    }
                )

    return relationships


def _element_to_dict(element):
    """Convert element to dictionary"""
    elem_dict = {
        "id": element.id,
        "name": getattr(
            element, "name", getattr(element, "title", "Unnamed")
        ),  # model-safety-ok: polymorphic ArchiMate elements
    }

    # Add all attributes
    for key in element.__table__.columns.keys():
        if key != "id":
            value = getattr(
                element, key, None
            )  # model-safety-ok: dynamic column iteration via __table__.columns
            if value is not None:
                # Handle datetime
                if isinstance(value, datetime):
                    elem_dict[key] = value.isoformat()
                # Handle Decimal
                elif hasattr(value, "__float__"):
                    elem_dict[key] = float(value)
                else:
                    elem_dict[key] = value

    return elem_dict


# ---------------------------------------------------------------------------
# Architecture Repository Health Scorecard  (ENT-115)
# ---------------------------------------------------------------------------

@archimate_crud.route("/health")
@login_required
def repository_health():
    """Redirect to dashboard with health panel open."""
    return redirect(url_for("archimate_crud.dashboard", panel="health"), code=302)


@archimate_crud.route("/api/traceability/sankey")
@login_required
def api_traceability_sankey():
    """Return traceability data shaped for D3 Sankey diagram.

    Queries archimate_relationships directly (not the traceability service)
    to show real cross-layer element connections.
    """
    try:
        return _build_traceability_sankey_response()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Traceability sankey API error: %s", e)
        return jsonify({"nodes": [], "links": [], "layer_counts": {}, "error": str(e)}), 200


def _build_traceability_sankey_response():
    from app.models.archimate_core import ArchiMateRelationship

    # Load all relationships with their source and target elements
    rels = db.session.query(
        ArchiMateRelationship.source_id,
        ArchiMateRelationship.target_id,
        ArchiMateRelationship.type,
    ).all()

    if not rels:
        return jsonify({"nodes": [], "links": [], "layer_counts": {}})

    # Collect all element IDs
    elem_ids = set()
    for src_id, tgt_id, _ in rels:
        elem_ids.add(src_id)
        elem_ids.add(tgt_id)

    # Load element details
    elements = {
        e.id: e
        for e in ArchiMateElement.query.filter(ArchiMateElement.id.in_(elem_ids)).all()
    }

    # Build nodes
    nodes_map = {}
    for eid, e in elements.items():
        layer = (e.layer or "application").lower()
        nodes_map[eid] = {
            "id": eid,
            "name": e.name or "",
            "element_type": e.type or "",
            "layer": layer,
        }

    # Build links (only between elements in DIFFERENT layers for Sankey flow)
    links = []
    seen = set()
    for src_id, tgt_id, rel_type in rels:
        src = elements.get(src_id)
        tgt = elements.get(tgt_id)
        if not src or not tgt:
            continue
        src_layer = (src.layer or "").lower()
        tgt_layer = (tgt.layer or "").lower()
        if src_layer == tgt_layer:
            continue  # Skip same-layer relationships for Sankey
        pair = (src_id, tgt_id)
        if pair in seen:
            continue
        seen.add(pair)
        links.append({"source": src_id, "target": tgt_id, "value": 1})

    # Layer counts
    layer_counts = {}
    for node in nodes_map.values():
        l = node["layer"]
        layer_counts[l] = layer_counts.get(l, 0) + 1

    return jsonify({
        "nodes": list(nodes_map.values()),
        "links": links,
        "layer_counts": layer_counts,
    })


@archimate_crud.route("/api/health-scorecard")
@login_required
def api_health_scorecard():
    """
    Return a JSON health scorecard for the ArchiMate repository.

    7 measurable tests that assess whether the repository is genuinely usable
    for architecture governance — not just populated with orphaned elements.
    """
    try:
        from sqlalchemy import func, text
        from app.models.application_portfolio import ApplicationComponent as AppComponent
        from app.models.architecture_inference_relationship import ArchitectureInferenceRelationship as InfRel

        # ------------------------------------------------------------------ #
        # Fetch raw counts (union of legacy + inference relationship tables)  #
        # ------------------------------------------------------------------ #
        total_elements = db.session.query(func.count(ArchiMateElement.id)).scalar() or 0
        legacy_rels = db.session.query(func.count(ArchiMateRelationship.id)).scalar() or 0
        inference_rels = db.session.query(func.count(InfRel.id)).scalar() or 0
        total_rels = legacy_rels + inference_rels

        # Elements per layer
        layer_rows = (
            db.session.query(ArchiMateElement.layer, func.count(ArchiMateElement.id))
            .group_by(ArchiMateElement.layer)
            .all()
        )
        layer_counts = {(r[0] or "unknown"): r[1] for r in layer_rows}

        EXPECTED_LAYERS = ["motivation", "strategy", "business", "application", "technology", "implementation"]
        # Also count PascalCase layers from newer elements
        for lay in ["Motivation", "Strategy", "Business", "Application", "Technology", "Implementation"]:
            if lay in layer_counts:
                lower_lay = lay.lower()
                layer_counts[lower_lay] = layer_counts.get(lower_lay, 0) + layer_counts.pop(lay)

        LAYER_THRESHOLD = 20

        # Elements that have any relationship (source or target) — check both tables
        legacy_ids = set()
        for row in db.session.query(ArchiMateRelationship.source_id).all():
            legacy_ids.add(row[0])
        for row in db.session.query(ArchiMateRelationship.target_id).all():
            legacy_ids.add(row[0])
        for row in db.session.query(InfRel.source_id).all():
            legacy_ids.add(row[0])
        for row in db.session.query(InfRel.target_id).all():
            legacy_ids.add(row[0])
        connected_count = (
            db.session.query(func.count(ArchiMateElement.id))
            .filter(ArchiMateElement.id.in_(legacy_ids))
            .scalar() or 0
        ) if legacy_ids else 0

        # Relationship types — union both tables
        rel_type_rows = (
            db.session.query(ArchiMateRelationship.type, func.count(ArchiMateRelationship.id))
            .group_by(ArchiMateRelationship.type)
            .all()
        )
        inf_type_rows = (
            db.session.query(InfRel.rel_type, func.count(InfRel.id))
            .group_by(InfRel.rel_type)
            .all()
        )
        rel_by_type = {}
        for r in rel_type_rows:
            rel_by_type[r[0] or "unknown"] = rel_by_type.get(r[0] or "unknown", 0) + r[1]
        for r in inf_type_rows:
            rel_by_type[r[0] or "unknown"] = rel_by_type.get(r[0] or "unknown", 0) + r[1]
        STRUCTURAL_TYPES = {"composition", "aggregation", "association"}
        semantic_rels = sum(v for k, v in rel_by_type.items() if (k or "").lower() not in STRUCTURAL_TYPES)

        # Cross-layer relationship pairs (excluding composition/aggregation within same layer)
        cross_layer_raw = (
            db.session.query(
                ArchiMateElement.layer.label("src_layer"),
                func.count(ArchiMateRelationship.id).label("cnt"),
            )
            .join(ArchiMateRelationship, ArchiMateRelationship.source_id == ArchiMateElement.id)
            .join(
                ArchiMateElement.__table__.alias("tgt"),
                ArchiMateRelationship.target_id == db.literal_column("tgt.id"),
            )
            .filter(
                ArchiMateElement.layer != db.literal_column("tgt.layer"),
                ArchiMateRelationship.type.notin_(["composition", "aggregation"]),
            )
            .group_by(ArchiMateElement.layer)
            .all()
        )
        # Fallback: count relationships crossing layers via raw SQL for reliability
        try:
            _cross_sql = """
                SELECT src_layer, tgt_layer, SUM(cnt) AS cnt FROM (
                    SELECT LOWER(COALESCE(src.layer,'?')) AS src_layer,
                           LOWER(COALESCE(tgt.layer,'?')) AS tgt_layer,
                           COUNT(*) AS cnt
                    FROM archimate_relationships r
                    JOIN archimate_elements src ON r.source_id = src.id
                    JOIN archimate_elements tgt ON r.target_id = tgt.id
                    WHERE LOWER(COALESCE(src.layer,'?')) <> LOWER(COALESCE(tgt.layer,'?'))
                      AND LOWER(COALESCE(r.type,'')) NOT IN ('composition','aggregation')
                    GROUP BY 1, 2
                    UNION ALL
                    SELECT LOWER(COALESCE(src.layer,'?')) AS src_layer,
                           LOWER(COALESCE(tgt.layer,'?')) AS tgt_layer,
                           COUNT(*) AS cnt
                    FROM architecture_inference_relationship r
                    JOIN archimate_elements src ON r.source_id = src.id
                    JOIN archimate_elements tgt ON r.target_id = tgt.id
                    WHERE LOWER(COALESCE(src.layer,'?')) <> LOWER(COALESCE(tgt.layer,'?'))
                      AND LOWER(COALESCE(r.rel_type,'')) NOT IN ('composition','aggregation')
                    GROUP BY 1, 2
                ) combined
                GROUP BY src_layer, tgt_layer
                ORDER BY cnt DESC
            """
            cross_pairs_rows = db.session.execute(text(_cross_sql)).fetchall()
            cross_pairs = [{"from": row[0] or "?", "to": row[1] or "?", "count": row[2]} for row in cross_pairs_rows]
        except Exception:
            db.session.rollback()
            cross_pairs = []

        # Portfolio integration: how many app names appear as archimate elements
        try:
            app_names = [r[0].lower() for r in db.session.query(AppComponent.name).limit(500).all() if r[0]]
            archimate_names = [r[0].lower() for r in db.session.query(ArchiMateElement.name).all() if r[0]]
            matched = sum(1 for n in app_names if n in archimate_names)
            total_apps = len(app_names)
        except Exception:
            db.session.rollback()
            app_names, archimate_names, matched, total_apps = [], [], 0, 0

        # FK links (applications with archimate element references)
        try:
            fk_linked = (
                db.session.query(func.count(AppComponent.id))
                .filter(AppComponent.archimate_element_id.isnot(None))
                .scalar() or 0
            ) if hasattr(AppComponent, "archimate_element_id") else 0
        except Exception:
            db.session.rollback()
            fk_linked = 0

        # Motivation integrity: Driver→Goal linkage, Goal→Requirement linkage
        # Uses ArchiMateElement type filter (Driver/Goal models may not exist)
        # Checks BOTH legacy ArchiMateRelationship AND inference relationships
        try:
            driver_ids_q = db.session.query(ArchiMateElement.id).filter(
                ArchiMateElement.type.in_(["Driver", "driver"])
            )
            goal_ids_q = db.session.query(ArchiMateElement.id).filter(
                ArchiMateElement.type.in_(["Goal", "goal"])
            )
            driver_count = driver_ids_q.count()
            goal_count = goal_ids_q.count()

            driver_ids = driver_ids_q
            goal_ids = goal_ids_q

            # Drivers linked to Goals via legacy table
            dg_legacy = (
                db.session.query(func.count(func.distinct(ArchiMateRelationship.source_id)))
                .filter(ArchiMateRelationship.source_id.in_(driver_ids))
                .filter(ArchiMateRelationship.target_id.in_(goal_ids))
                .scalar() or 0
            )
            # Also check inference table (source_id links to Goal elements)
            dg_inference = (
                db.session.query(func.count(func.distinct(InfRel.source_id)))
                .filter(InfRel.source_id.in_(driver_ids))
                .filter(InfRel.target_id.in_(goal_ids))
                .scalar() or 0
            )
            drivers_linked = dg_legacy + dg_inference

            # Goals linked to Requirements
            req_elements = db.session.query(ArchiMateElement.id).filter(
                ArchiMateElement.type.ilike("%requirement%")
            )
            # Also include Outcome and Capability as valid downstream (engine creates these)
            outcome_cap = db.session.query(ArchiMateElement.id).filter(
                ArchiMateElement.type.in_(["Outcome", "Capability", "outcome", "capability"])
            )
            valid_targets = req_elements.union(outcome_cap)

            gr_legacy = (
                db.session.query(func.count(func.distinct(ArchiMateRelationship.source_id)))
                .filter(ArchiMateRelationship.source_id.in_(goal_ids))
                .filter(ArchiMateRelationship.target_id.in_(valid_targets))
                .scalar() or 0
            )
            gr_inference = (
                db.session.query(func.count(func.distinct(InfRel.source_id)))
                .filter(InfRel.source_id.in_(goal_ids))
                .filter(InfRel.target_id.in_(valid_targets))
                .scalar() or 0
            )
            goals_linked = gr_legacy + gr_inference
        except Exception:
            db.session.rollback()
            driver_count, goal_count, drivers_linked, goals_linked = 0, 0, 0, 0

        # Implementation & Migration layer element types
        im_types = ["WorkPackage", "Plateau", "Gap", "Deliverable"]
        im_counts = {}
        for etype in im_types:
            try:
                im_counts[etype] = (
                    db.session.query(func.count(ArchiMateElement.id))
                    .filter(ArchiMateElement.type.ilike(f"%{etype}%"))
                    .scalar() or 0
                )
            except Exception:
                db.session.rollback()
                im_counts[etype] = 0

        # Elements with plateau/lifecycle field set (used as lifecycle status proxy).
        # The query string was previously built but never executed, so has_plateau
        # was undefined -> NameError at the Test 2 computation below.
        from sqlalchemy import text as _sa_text

        has_plateau = 0
        try:
            has_plateau = (
                db.session.execute(
                    _sa_text(
                        "SELECT COUNT(*) FROM archimate_elements "
                        "WHERE plateau IS NOT NULL AND plateau != ''"
                    )
                ).scalar()
                or 0
            )
        except Exception as exc:
            db.session.rollback()
            has_plateau = 0
            logger.debug("plateau count unavailable in api_health_scorecard: %s", exc)

        # ------------------------------------------------------------------ #
        # Compute tests                                                        #
        # ------------------------------------------------------------------ #

        # Test 1: Element Coverage — 5 of 6 layers must have 20+ elements
        layer_detail = []
        layers_passing = 0
        for lay in EXPECTED_LAYERS:
            cnt = layer_counts.get(lay, 0)
            passes = cnt >= LAYER_THRESHOLD
            if passes:
                layers_passing += 1
            layer_detail.append({"layer": lay, "count": cnt, "pass": passes})
        t1_pass = layers_passing >= 5
        t1 = {
            "pass": t1_pass,
            "metric": f"{layers_passing}/6",
            "total_elements": total_elements,
            "detail": layer_detail,
        }

        # Test 2: Lifecycle Status — 80% of elements with plateau assigned
        lifecycle_pct = round(has_plateau / total_elements * 100) if total_elements else 0
        t2_pass = lifecycle_pct >= 80
        t2 = {
            "pass": t2_pass,
            "metric": f"{lifecycle_pct}%",
            "value": lifecycle_pct,
            "detail": {"has_status": has_plateau, "total": total_elements},
        }

        # Test 3: Relationship Density — <30% orphans AND >30% semantic rels
        orphan_count = total_elements - connected_count
        orphan_pct = round(orphan_count / total_elements * 100) if total_elements else 100
        semantic_pct = round(semantic_rels / total_rels * 100) if total_rels else 0
        avg_per_elem = round(total_rels / total_elements, 1) if total_elements else 0
        sub_orphan = {"value": orphan_pct, "pass": orphan_pct < 30}
        sub_semantic = {"value": semantic_pct, "pass": semantic_pct > 30}
        t3_pass = sub_orphan["pass"] and sub_semantic["pass"]
        t3 = {
            "pass": t3_pass,
            "metric": f"{avg_per_elem} rels/elem",
            "detail": {
                "total_relationships": total_rels,
                "avg_per_element": avg_per_elem,
                "sub_tests": {"orphan_rate": sub_orphan, "semantic_ratio": sub_semantic},
            },
        }

        # Test 4: Cross-Layer Traceability — 4+ semantic cross-layer pairs
        t4_pass = len(cross_pairs) >= 4
        t4 = {
            "pass": t4_pass,
            "metric": f"{len(cross_pairs)} pairs",
            "detail": {"pairs": cross_pairs},
        }

        # Test 5: Portfolio Integration — 50% of apps matched in ArchiMate
        portf_pct = round(matched / total_apps * 100) if total_apps else 0
        t5_pass = portf_pct >= 50
        t5 = {
            "pass": t5_pass,
            "metric": f"{portf_pct}%",
            "value": portf_pct,
            "detail": {
                "total_apps": total_apps,
                "matched_by_name": matched,
                "linked_by_fk": fk_linked,
            },
        }

        # Test 6: Motivation Integrity — Driver→Goal ≥70%, Goal→Req ≥50%
        dg_pct = round(drivers_linked / driver_count * 100) if driver_count else 0
        gr_pct = round(goals_linked / goal_count * 100) if goal_count else 0
        sub_dg = {"linked": drivers_linked, "drivers": driver_count, "pct": dg_pct, "pass": dg_pct >= 70}
        sub_gr = {"linked": goals_linked, "goals": goal_count, "pct": gr_pct, "pass": gr_pct >= 50}
        t6_pass = sub_dg["pass"] and sub_gr["pass"]
        t6 = {
            "pass": t6_pass,
            "metric": f"{dg_pct}% / {gr_pct}%",
            "detail": {"sub_tests": {"driver_goal": sub_dg, "goal_req": sub_gr}},
        }

        # Test 7: Implementation & Migration — 10+ IM elements
        im_total = sum(im_counts.values())
        t7_pass = im_total >= 10
        t7 = {
            "pass": t7_pass,
            "metric": f"{im_total} elements",
            "detail": {
                "type_counts": im_counts,
                "required": {"workpackage": 2, "plateau": 2, "gap": 1, "deliverable": 2},
            },
        }

        # ------------------------------------------------------------------ #
        # Overall grade                                                        #
        # ------------------------------------------------------------------ #
        tests_passing = sum(1 for t in [t1, t2, t3, t4, t5, t6, t7] if t["pass"])
        if tests_passing == 7:
            grade, grade_label = "solid", "Solid Foundation"
        elif tests_passing >= 5:
            grade, grade_label = "usable", "Usable"
        elif tests_passing >= 3:
            grade, grade_label = "foundation", "Foundation Only"
        else:
            grade, grade_label = "not_ready", "Not Yet Ready"

        return jsonify({
            "score": tests_passing,
            "total": 7,
            "grade": grade,
            "grade_label": grade_label,
            "tests": {
                "element_coverage": t1,
                "lifecycle_status": t2,
                "relationship_density": t3,
                "cross_layer_trace": t4,
                "portfolio_integration": t5,
                "motivation_integrity": t6,
                "im_layer": t7,
            },
        })

    except Exception as e:
        current_app.logger.error("Health scorecard error: %s", e, exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Failed to compute health scorecard", "detail": str(e)}), 500


@archimate_crud.route("/api/health-scorecard/repair", methods=["POST"])
@login_required
def api_health_scorecard_repair():
    """Run inference engine repair for a specific health test failure.

    Request JSON: {"test": "motivation_integrity"|"relationship_density"|"cross_layer_trace"|...}
    Response: {"repaired": int, "elements_created": [...], "before": {...}, "after": {...}}
    """
    try:
        from app.modules.architecture.services.inference_engine_service import (
            ArchiMateInferenceEngine,
        )

        data = request.get_json(silent=True) or {}
        test_name = data.get("test", "")
        dry_run = data.get("dry_run", False)

        engine = ArchiMateInferenceEngine(0)
        snap_before = engine.take_snapshot()

        created = []
        repaired_count = 0

        if test_name == "motivation_integrity":
            # Repair Goals missing Outcomes/Requirements, Drivers missing Goals
            goals = ArchiMateElement.query.filter(
                ArchiMateElement.type.in_(["Goal", "goal"])
            ).limit(50).all()
            for goal in goals:
                node = engine.graph.get_node(goal.id)
                if node and not dry_run:
                    result = engine.repair(goal.id)
                    created.extend([
                        {"type": e.element_type, "name": e.name, "id": e.id}
                        for e in result.elements_created
                    ])
                    repaired_count += len(result.elements_created)

        elif test_name == "relationship_density":
            # Repair orphan elements — give them chain connections
            all_elements = engine.graph.find_nodes(element_type=None, filters={})
            orphans = [
                e for e in all_elements
                if not engine.graph.get_neighbors(e.id, direction="both")
            ]
            for orphan in orphans[:30]:
                if not dry_run:
                    result = engine.repair(orphan.id)
                    created.extend([
                        {"type": e.element_type, "name": e.name, "id": e.id}
                        for e in result.elements_created
                    ])
                    repaired_count += len(result.elements_created)

        elif test_name == "cross_layer_trace":
            # Generate chains from root elements to create cross-layer links
            roots = engine._find_roots()
            for root in roots[:20]:
                if not dry_run:
                    result = engine.repair(root.id)
                    created.extend([
                        {"type": e.element_type, "name": e.name, "id": e.id}
                        for e in result.elements_created
                    ])
                    repaired_count += len(result.elements_created)

        elif test_name == "im_layer":
            # Generate WorkPackages/Deliverables from existing Gaps
            gaps = ArchiMateElement.query.filter(
                ArchiMateElement.type.in_(["Gap", "gap"])
            ).limit(20).all()
            for gap in gaps:
                node = engine.graph.get_node(gap.id)
                if node and not dry_run:
                    result = engine.repair(gap.id)
                    created.extend([
                        {"type": e.element_type, "name": e.name, "id": e.id}
                        for e in result.elements_created
                    ])
                    repaired_count += len(result.elements_created)

        else:
            return jsonify({
                "error": "Test '%s' does not support automated repair" % test_name,
                "repairable_tests": [
                    "motivation_integrity", "relationship_density",
                    "cross_layer_trace", "im_layer",
                ],
            }), 400

        if not dry_run:
            db.session.commit()

        snap_after = engine.take_snapshot()
        diff = engine.diff_snapshots(snap_before, snap_after)

        return jsonify({
            "test": test_name,
            "dry_run": dry_run,
            "repaired": repaired_count,
            "elements_created": created[:50],
            "diff": {
                "added_nodes": len(diff["added_nodes"]),
                "added_relationships": len(diff["added_relationships"]),
            },
        })

    except Exception as e:
        current_app.logger.error("Health repair error: %s", e, exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Repair failed", "detail": str(e)}), 500
