"""
Relationship add/edit/delete routes for Application Management.
"""
# mass-deletion-ok — BE-179 removes 16 manual CSRF blocks replaced by global CSRFProtect

from flask import current_app, flash, jsonify, redirect, request, url_for
from flask_login import login_required
from werkzeug.exceptions import BadRequest

from .. import db
from ..models.application_layer import ApplicationInterface, ApplicationService, DataObject
from ..models.application_portfolio import ApplicationComponent
from ..models.business_capabilities import BusinessFunction
from ..models.business_layer import (
    BusinessActor,
    BusinessObject,
    BusinessRole,
    BusinessService,
)
from ..models.implementation_migration import Deliverable, Plateau, WorkPackage
from ..models.models import ArchiMateElement, ArchiMateRelationship, Requirement
from ..models.motivation import Driver, Goal
from ..models.physical_layer import (
    PhysicalDistributionNetwork,
    PhysicalEquipment,
    PhysicalFacility,
    PhysicalMaterial,
)
from ..models.process_data import BusinessProcess
from ..models.relationship_tables import (
    ApplicationBusinessActorMapping,
    ApplicationProcessSupport,
    DataObjectStorage,
)
from ..models.strategy_layer import CourseOfAction, ValueStream
from ..models.technology_layer import Device, Node, SystemSoftware
from . import application_mgmt
from .routes import _add_archimate_element, _delete_archimate_element

# Aliases to match names used in bulk link/unlink/update route maps
TechnologyNode = Node
TechnologyDevice = Device


@application_mgmt.route("/applications/bulk-delete", methods=["POST"])
@login_required
def application_bulk_delete():
    """Handle bulk deletion of application components."""
    data = request.get_json(silent=True) or {}
    raw_ids = data.get("ids") if isinstance(data, dict) else []

    if not isinstance(raw_ids, list) or not raw_ids:
        raise BadRequest("No application ids supplied.")

    normalized_ids = []
    for raw_id in raw_ids:
        try:
            normalized = int(raw_id)
        except (TypeError, ValueError):
            continue
        if normalized < 1:
            continue
        normalized_ids.append(normalized)

    if not normalized_ids:
        raise BadRequest("No valid application ids supplied.")

    applications = ApplicationComponent.query.filter(
        ApplicationComponent.id.in_(normalized_ids)
    ).all()

    if not applications:
        raise BadRequest("No matching applications found.")

    deleted_count = 0
    try:
        for application in applications:
            db.session.delete(application)
            deleted_count += 1
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500

    return jsonify({"success": True, "deleted": deleted_count})


# ============================================================================
# ArchiMate Element Management - Generic Inline CRUD
# ============================================================================


# --- Strategy Layer ---
@application_mgmt.route("/applications/<int:app_id>/capabilities", methods=["POST"])
@login_required
def add_capability(app_id):
    return _add_archimate_element(app_id, "strategy", "Capability", request.json)


@application_mgmt.route(
    "/applications/<int:app_id>/capabilities/<int:id>", methods=["DELETE"]
)
@login_required
def delete_capability(app_id, id):
    return _delete_archimate_element(id, "realization")


@application_mgmt.route("/applications/<int:app_id>/resources", methods=["POST"])
@login_required
def add_resource(app_id):
    return _add_archimate_element(app_id, "strategy", "Resource", request.json)


@application_mgmt.route(
    "/applications/<int:app_id>/resources/<int:id>", methods=["DELETE"]
)
@login_required
def delete_resource(app_id, id):
    return _delete_archimate_element(id, "realization")


@application_mgmt.route("/applications/<int:app_id>/value-streams", methods=["POST"])
@login_required
def add_value_stream(app_id):
    return _add_archimate_element(app_id, "strategy", "ValueStream", request.json)


@application_mgmt.route(
    "/applications/<int:app_id>/value-streams/<int:id>", methods=["DELETE"]
)
@login_required
def delete_value_stream(app_id, id):
    return _delete_archimate_element(id, "realization")


@application_mgmt.route(
    "/applications/<int:app_id>/courses-of-action", methods=["POST"]
)
@login_required
def add_course_of_action(app_id):
    return _add_archimate_element(app_id, "strategy", "CourseOfAction", request.json)


@application_mgmt.route(
    "/applications/<int:app_id>/courses-of-action/<int:id>", methods=["DELETE"]
)
@login_required
def delete_course_of_action(app_id, id):
    return _delete_archimate_element(id, "realization")


# ============================================================================
# DELETE ROUTES - Application Layer
# ============================================================================


@application_mgmt.route(
    "/applications/<int:id>/interfaces/<int:interface_id>/delete", methods=["POST"]
)
@login_required
def application_interface_delete(id, interface_id):
    """Unlink application interface from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    interface = ApplicationInterface.query.get_or_404(interface_id)

    try:
        # Set FK to NULL, don't delete the interface
        if interface.application_component_id == app.id:
            interface.application_component_id = None
            db.session.commit()
            flash(
                f'Application interface "{interface.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Application interface "{interface.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking application interface {interface_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking application interface. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#application"
    )


@application_mgmt.route(
    "/applications/<int:id>/services/<int:service_id>/delete", methods=["POST"]
)
@login_required
def application_service_delete(id, service_id):
    """Unlink application service from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    service = ApplicationService.query.get_or_404(service_id)

    try:
        # Set FK to NULL, don't delete the service
        if service.application_component_id == app.id:
            service.application_component_id = None
            db.session.commit()
            flash(
                f'Application service "{service.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Application service "{service.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking application service {service_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking application service. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#application"
    )


@application_mgmt.route(
    "/applications/<int:id>/data-objects/<int:data_object_id>/delete", methods=["POST"]
)
@login_required
def data_object_delete(id, data_object_id):
    """Unlink data object from application (many-to-many relationship)"""
    app = ApplicationComponent.query.get_or_404(id)
    data_object = DataObject.query.get_or_404(data_object_id)

    try:
        # Delete junction table entry, NOT the data object itself
        link = DataObjectStorage.query.filter_by(
            business_object_id=data_object.id, application_component_id=app.id
        ).first()

        if link:
            db.session.delete(link)
            db.session.commit()
            flash(
                f'Data object "{data_object.name}" unlinked from application', "success"
            )
        else:
            flash(
                f'Data object "{data_object.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking data object {data_object_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking data object. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#application"
    )


# ============================================================================
# DELETE ROUTES - Business Layer
# ============================================================================


@application_mgmt.route(
    "/applications/<int:id>/business-processes/<int:process_id>/delete",
    methods=["POST"],
)
@login_required
def application_business_process_delete(id, process_id):
    """Unlink business process from application (many-to-many relationship)"""
    app = ApplicationComponent.query.get_or_404(id)
    process = BusinessProcess.query.get_or_404(process_id)

    try:
        # Delete junction table entry, NOT the process itself
        link = ApplicationProcessSupport.query.filter_by(
            application_component_id=app.id, business_process_id=process.id
        ).first()

        if link:
            db.session.delete(link)
            db.session.commit()
            flash(
                f'Business process "{process.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Business process "{process.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking business process {process_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking business process. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#business")


@application_mgmt.route(
    "/applications/<int:id>/business-actors/<int:actor_id>/delete", methods=["POST"]
)
@login_required
def application_business_actor_delete(id, actor_id):
    """Unlink business actor from application (many-to-many relationship)"""
    app = ApplicationComponent.query.get_or_404(id)
    actor = BusinessActor.query.get_or_404(actor_id)

    try:
        # Delete junction table entry, NOT the actor itself
        link = ApplicationBusinessActorMapping.query.filter_by(
            application_component_id=app.id, business_actor_id=actor.id
        ).first()

        if link:
            db.session.delete(link)
            db.session.commit()
            flash(f'Business actor "{actor.name}" unlinked from application', "success")
        else:
            flash(
                f'Business actor "{actor.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking business actor {actor_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking business actor. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#business")


@application_mgmt.route(
    "/applications/<int:id>/business-services/<int:service_id>/delete", methods=["POST"]
)
@login_required
def application_business_service_delete(id, service_id):
    """Unlink business service from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    service = BusinessService.query.get_or_404(service_id)

    try:
        # Set FK to NULL, don't delete the service
        if service.application_component_id == app.id:
            service.application_component_id = None
            db.session.commit()
            flash(
                f'Business service "{service.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Business service "{service.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking business service {service_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking business service. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#business")


@application_mgmt.route(
    "/applications/<int:id>/business-roles/<int:role_id>/delete", methods=["POST"]
)
@login_required
def application_business_role_delete(id, role_id):
    """Unlink business role from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    role = BusinessRole.query.get_or_404(role_id)

    try:
        # Set FK to NULL, don't delete the role
        if role.application_component_id == app.id:
            role.application_component_id = None
            db.session.commit()
            flash(f'Business role "{role.name}" unlinked from application', "success")
        else:
            flash(
                f'Business role "{role.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking business role {role_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking business role. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#business")


@application_mgmt.route(
    "/applications/<int:id>/business-functions/<int:function_id>/delete",
    methods=["POST"],
)
@login_required
def application_business_function_delete(id, function_id):
    """Unlink business function from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    function = BusinessFunction.query.get_or_404(function_id)

    try:
        # Set FK to NULL, don't delete the function
        if function.application_component_id == app.id:
            function.application_component_id = None
            db.session.commit()
            flash(
                f'Business function "{function.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Business function "{function.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking business function {function_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking business function. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#business")


@application_mgmt.route(
    "/applications/<int:id>/business-objects/<int:object_id>/delete", methods=["POST"]
)
@login_required
def application_business_object_delete(id, object_id):
    """Unlink business object from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    business_obj = BusinessObject.query.get_or_404(object_id)

    try:
        # Set FK to NULL, don't delete the object
        if business_obj.application_component_id == app.id:
            business_obj.application_component_id = None
            db.session.commit()
            flash(
                f'Business object "{business_obj.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Business object "{business_obj.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking business object {object_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking business object. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#business")


# ============================================================================
# DELETE ROUTES - Technology Layer
# ============================================================================


@application_mgmt.route(
    "/applications/<int:id>/technology-nodes/<int:node_id>/delete", methods=["POST"]
)
@login_required
def technology_node_delete(id, node_id):
    """Unlink technology node from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    node = Node.query.get_or_404(node_id)

    try:
        # Set FK to NULL, don't delete the node
        if node.application_component_id == app.id:
            node.application_component_id = None
            db.session.commit()
            flash(f'Technology node "{node.name}" unlinked from application', "success")
        else:
            flash(
                f'Technology node "{node.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking technology node {node_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking technology node. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


@application_mgmt.route(
    "/applications/<int:id>/technology-devices/<int:device_id>/delete", methods=["POST"]
)
@login_required
def technology_device_delete(id, device_id):
    """Unlink technology device from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    device = Device.query.get_or_404(device_id)

    try:
        # Set FK to NULL, don't delete the device
        if device.application_component_id == app.id:
            device.application_component_id = None
            db.session.commit()
            flash(
                f'Technology device "{device.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Technology device "{device.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking technology device {device_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking technology device. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


@application_mgmt.route(
    "/applications/<int:id>/system-software/<int:software_id>/delete", methods=["POST"]
)
@login_required
def system_software_delete(id, software_id):
    """Unlink system software from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    software = SystemSoftware.query.get_or_404(software_id)

    try:
        # Set FK to NULL, don't delete the software
        if software.application_component_id == app.id:
            software.application_component_id = None
            db.session.commit()
            flash(
                f'System software "{software.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'System software "{software.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking system software {software_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking system software. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


# ============================================================================
# DELETE ROUTES - Motivation Layer
# ============================================================================


@application_mgmt.route(
    "/applications/<int:id>/goals/<int:goal_id>/delete", methods=["POST"]
)
@login_required
def goal_delete(id, goal_id):
    """Delete a goal from application"""
    app = ApplicationComponent.query.get_or_404(id)
    goal = Goal.query.get_or_404(goal_id)

    try:
        db.session.delete(goal)
        db.session.commit()
        flash(f'Goal "{goal.name}" deleted successfully', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting goal {goal_id}: {str(e)}")
        flash("Error deleting goal. Please try again.", "danger")

    return redirect(url_for("unified_applications.application_detail", id=id))


@application_mgmt.route(
    "/applications/<int:id>/drivers/<int:driver_id>/delete", methods=["POST"]
)
@login_required
def driver_delete(id, driver_id):
    """Delete a driver from application"""
    app = ApplicationComponent.query.get_or_404(id)
    driver = Driver.query.get_or_404(driver_id)

    try:
        db.session.delete(driver)
        db.session.commit()
        flash(f'Driver "{driver.name}" deleted successfully', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting driver {driver_id}: {str(e)}")
        flash("Error deleting driver. Please try again.", "danger")

    return redirect(url_for("unified_applications.application_detail", id=id))


@application_mgmt.route(
    "/applications/<int:id>/requirements/<int:requirement_id>/delete", methods=["POST"]
)
@login_required
def application_requirement_delete(id, requirement_id):
    """Delete a requirement from application"""
    app = ApplicationComponent.query.get_or_404(id)
    requirement = Requirement.query.get_or_404(requirement_id)

    try:
        db.session.delete(requirement)
        db.session.commit()
        flash(
            f'Requirement "{requirement.display_title}" deleted successfully', "success"
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error deleting requirement {requirement_id}: {str(e)}"
        )
        flash("Error deleting requirement. Please try again.", "danger")

    return redirect(url_for("unified_applications.application_detail", id=id))


# ============================================================================
# DELETE ROUTES - Strategy Layer
# ============================================================================


@application_mgmt.route(
    "/applications/<int:id>/courses-of-action/<int:coa_id>/delete", methods=["POST"]
)
@login_required
def course_of_action_delete(id, coa_id):
    """Unlink Course of Action from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    coa = CourseOfAction.query.get_or_404(coa_id)

    try:
        # Set FK to NULL, don't delete the course of action
        if coa.application_component_id == app.id:
            coa.application_component_id = None
            db.session.commit()
            flash(f'Course of action "{coa.name}" unlinked from application', "success")
        else:
            flash(
                f'Course of action "{coa.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking course of action {coa_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking course of action. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#strategy")


@application_mgmt.route(
    "/applications/<int:id>/value-streams/<int:stream_id>/delete", methods=["POST"]
)
@login_required
def value_stream_delete(id, stream_id):
    """Unlink Value Stream from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    stream = ValueStream.query.get_or_404(stream_id)

    try:
        # Set FK to NULL, don't delete the value stream
        if stream.application_component_id == app.id:
            stream.application_component_id = None
            db.session.commit()
            flash(f'Value stream "{stream.name}" unlinked from application', "success")
        else:
            flash(
                f'Value stream "{stream.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking value stream {stream_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking value stream. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#strategy")


# ============================================================================
# EDIT/UPDATE ROUTES - All ArchiMate Layers
# ============================================================================


@application_mgmt.route(
    "/applications/<int:id>/business-actors/<int:actor_id>/edit", methods=["POST"]
)
@login_required
def business_actor_edit(id, actor_id):
    """Update Business Actor properties"""
    app = ApplicationComponent.query.get_or_404(id)
    actor = BusinessActor.query.get_or_404(actor_id)

    try:
        # Update editable fields from form
        if "name" in request.form:
            actor.name = request.form.get("name").strip()
        if "description" in request.form:
            actor.description = request.form.get("description").strip() or None
        if "actor_type" in request.form:
            actor.actor_type = request.form.get("actor_type") or None
        if "location" in request.form:
            actor.location = request.form.get("location") or None
        if "headcount" in request.form:
            headcount_str = request.form.get("headcount")
            actor.headcount = int(headcount_str) if headcount_str else None

        db.session.commit()
        flash(f'Business actor "{actor.name}" updated successfully!', "success")
    except ValueError as e:
        db.session.rollback()
        flash("Invalid input. Please try again.", "error")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating business actor {actor_id}: {e}")
        flash("Error updating business actor. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#business")


@application_mgmt.route(
    "/applications/<int:id>/business-processes/<int:process_id>/edit", methods=["POST"]
)
@login_required
def business_process_edit(id, process_id):
    """Update Business Process properties"""
    app = ApplicationComponent.query.get_or_404(id)
    process = BusinessProcess.query.get_or_404(process_id)

    try:
        if "name" in request.form:
            process.name = request.form.get("name").strip()
        if "description" in request.form:
            process.description = request.form.get("description").strip() or None
        if "process_type" in request.form:
            process.process_type = request.form.get("process_type") or None

        db.session.commit()
        flash(f'Business process "{process.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating business process {process_id}: {e}")
        flash("Error updating business process. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#business")


@application_mgmt.route(
    "/applications/<int:id>/business-services/<int:service_id>/edit", methods=["POST"]
)
@login_required
def business_service_edit(id, service_id):
    """Update Business Service properties"""
    app = ApplicationComponent.query.get_or_404(id)
    service = BusinessService.query.get_or_404(service_id)

    try:
        if "name" in request.form:
            service.name = request.form.get("name").strip()
        if "description" in request.form:
            service.description = request.form.get("description").strip() or None
        if "service_type" in request.form:
            service.service_type = request.form.get("service_type") or None

        db.session.commit()
        flash(f'Business service "{service.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating business service {service_id}: {e}")
        flash("Error updating business service. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#business")


@application_mgmt.route(
    "/applications/<int:id>/interfaces/<int:interface_id>/edit", methods=["POST"]
)
@login_required
def application_interface_edit(id, interface_id):
    """Update Application Interface properties"""
    app = ApplicationComponent.query.get_or_404(id)
    interface = ApplicationInterface.query.get_or_404(interface_id)

    try:
        if "name" in request.form:
            interface.name = request.form.get("name").strip()
        if "description" in request.form:
            interface.description = request.form.get("description").strip() or None
        if "interface_type" in request.form:
            interface.interface_type = request.form.get("interface_type") or None
        if "protocol" in request.form:
            interface.protocol = request.form.get("protocol") or None

        db.session.commit()
        flash(
            f'Application interface "{interface.name}" updated successfully!', "success"
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error updating application interface {interface_id}: {e}"
        )
        flash("Error updating application interface. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#application"
    )


@application_mgmt.route(
    "/applications/<int:id>/services/<int:service_id>/edit", methods=["POST"]
)
@login_required
def application_service_edit(id, service_id):
    """Update Application Service properties"""
    app = ApplicationComponent.query.get_or_404(id)
    service = ApplicationService.query.get_or_404(service_id)

    try:
        if "name" in request.form:
            service.name = request.form.get("name").strip()
        if "description" in request.form:
            service.description = request.form.get("description").strip() or None
        if "service_type" in request.form:
            service.service_type = request.form.get("service_type") or None

        db.session.commit()
        flash(f'Application service "{service.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error updating application service {service_id}: {e}"
        )
        flash("Error updating application service. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#application"
    )


@application_mgmt.route(
    "/applications/<int:id>/technology-nodes/<int:node_id>/edit", methods=["POST"]
)
@login_required
def technology_node_edit(id, node_id):
    """Update Technology Node properties"""
    app = ApplicationComponent.query.get_or_404(id)
    node = Node.query.get_or_404(node_id)

    try:
        if "name" in request.form:
            node.name = request.form.get("name").strip()
        if "description" in request.form:
            node.description = request.form.get("description").strip() or None
        if "node_type" in request.form:
            node.node_type = request.form.get("node_type") or None
        if "location" in request.form:
            node.location = request.form.get("location") or None

        db.session.commit()
        flash(f'Technology node "{node.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating technology node {node_id}: {e}")
        flash("Error updating technology node. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


@application_mgmt.route(
    "/applications/<int:id>/technology-devices/<int:device_id>/edit", methods=["POST"]
)
@login_required
def technology_device_edit(id, device_id):
    """Update Technology Device properties"""
    app = ApplicationComponent.query.get_or_404(id)
    device = Device.query.get_or_404(device_id)

    try:
        if "name" in request.form:
            device.name = request.form.get("name").strip()
        if "description" in request.form:
            device.description = request.form.get("description").strip() or None
        if "device_type" in request.form:
            device.device_type = request.form.get("device_type") or None

        db.session.commit()
        flash(f'Technology device "{device.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating technology device {device_id}: {e}")
        flash("Error updating technology device. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


@application_mgmt.route(
    "/applications/<int:id>/goals/<int:goal_id>/edit", methods=["POST"]
)
@login_required
def goal_edit(id, goal_id):
    """Update Goal properties"""
    app = ApplicationComponent.query.get_or_404(id)
    goal = Goal.query.get_or_404(goal_id)

    try:
        if "name" in request.form:
            goal.name = request.form.get("name").strip()
        if "description" in request.form:
            goal.description = request.form.get("description").strip() or None
        if "goal_type" in request.form:
            goal.goal_type = request.form.get("goal_type") or None
        if "priority" in request.form:
            goal.priority = request.form.get("priority") or None

        db.session.commit()
        flash(f'Goal "{goal.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating goal {goal_id}: {e}")
        flash("Error updating goal. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#motivation"
    )


@application_mgmt.route(
    "/applications/<int:id>/drivers/<int:driver_id>/edit", methods=["POST"]
)
@login_required
def driver_edit(id, driver_id):
    """Update Driver properties"""
    app = ApplicationComponent.query.get_or_404(id)
    driver = Driver.query.get_or_404(driver_id)

    try:
        if "name" in request.form:
            driver.name = request.form.get("name").strip()
        if "description" in request.form:
            driver.description = request.form.get("description").strip() or None
        if "driver_type" in request.form:
            driver.driver_type = request.form.get("driver_type") or None

        db.session.commit()
        flash(f'Driver "{driver.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating driver {driver_id}: {e}")
        flash("Error updating driver. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#motivation"
    )


@application_mgmt.route(
    "/applications/<int:id>/courses-of-action/<int:coa_id>/edit", methods=["POST"]
)
@login_required
def course_of_action_edit(id, coa_id):
    """Update Course of Action properties"""
    app = ApplicationComponent.query.get_or_404(id)
    coa = CourseOfAction.query.get_or_404(coa_id)

    try:
        if "name" in request.form:
            coa.name = request.form.get("name").strip()
        if "description" in request.form:
            coa.description = request.form.get("description").strip() or None
        if "action_type" in request.form:
            coa.action_type = request.form.get("action_type") or None

        db.session.commit()
        flash(f'Course of action "{coa.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating course of action {coa_id}: {e}")
        flash("Error updating course of action. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#strategy")


@application_mgmt.route(
    "/applications/<int:id>/value-streams/<int:stream_id>/edit", methods=["POST"]
)
@login_required
def value_stream_edit(id, stream_id):
    """Update Value Stream properties"""
    app = ApplicationComponent.query.get_or_404(id)
    stream = ValueStream.query.get_or_404(stream_id)

    try:
        if "name" in request.form:
            stream.name = request.form.get("name").strip()
        if "description" in request.form:
            stream.description = request.form.get("description").strip() or None
        if "stream_type" in request.form:
            stream.stream_type = request.form.get("stream_type") or None

        db.session.commit()
        flash(f'Value stream "{stream.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating value stream {stream_id}: {e}")
        flash("Error updating value stream. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#strategy")


# ============================================================================
# ADD/CREATE ROUTES - All ArchiMate Layers
# ============================================================================

@application_mgmt.route("/applications/<int:id>/interfaces/add", methods=["POST"])
@login_required
def application_interface_add(id):
    """Link existing Application Interface to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    interface_id = request.form.get("element_id")

    if not interface_id:
        flash("No application interface selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    interface = ApplicationInterface.query.get(interface_id)
    if not interface:
        flash("Application interface not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Check if already linked to another application
    if (
        interface.application_component_id
        and interface.application_component_id != app.id
    ):
        other_app = ApplicationComponent.query.get(interface.application_component_id)
        flash(
            f'Application interface "{interface.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif interface.application_component_id == app.id:
        flash(
            f'Application interface "{interface.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            # Update direct FK
            interface.application_component_id = app.id
            db.session.commit()
            flash(
                f'Application interface "{interface.name}" linked successfully!',
                "success",
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking application interface {interface_id} to app {id}: {e}"
            )
            flash("Error linking application interface. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#application"
    )


@application_mgmt.route("/applications/<int:id>/services/add", methods=["POST"])
@login_required
def application_service_add(id):
    """Link existing Application Service to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    service_id = request.form.get("element_id")

    if not service_id:
        flash("No application service selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    service = ApplicationService.query.get(service_id)
    if not service:
        flash("Application service not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Check if already linked to another application
    if service.application_component_id and service.application_component_id != app.id:
        other_app = ApplicationComponent.query.get(service.application_component_id)
        flash(
            f'Application service "{service.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif service.application_component_id == app.id:
        flash(
            f'Application service "{service.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            # Update direct FK
            service.application_component_id = app.id
            db.session.commit()
            flash(
                f'Application service "{service.name}" linked successfully!', "success"
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking application service {service_id} to app {id}: {e}"
            )
            flash("Error linking application service. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#application"
    )


@application_mgmt.route("/applications/<int:id>/data-objects/add", methods=["POST"])
@login_required
def data_object_add(id):
    """Link existing Data Object to Application (many-to-many)"""
    app = ApplicationComponent.query.get_or_404(id)
    object_id = request.form.get("element_id")

    if not object_id:
        flash("No data object selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    data_obj = DataObject.query.get(object_id)
    if not data_obj:
        flash("Data object not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Check if relationship already exists
    existing = DataObjectStorage.query.filter_by(
        business_object_id=data_obj.id, application_component_id=app.id
    ).first()

    if existing:
        flash(
            f'Data object "{data_obj.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            # Create many-to-many relationship
            link = DataObjectStorage(
                business_object_id=data_obj.id,
                application_component_id=app.id,
                is_master_source=False,
                storage_type="Database",
            )
            db.session.add(link)
            db.session.commit()
            flash(f'Data object "{data_obj.name}" linked successfully!', "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking data object {object_id} to app {id}: {e}"
            )
            flash("Error linking data object. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#application"
    )


# ============================================================================
# ADD ROUTES - Strategy Layer
# ============================================================================


@application_mgmt.route(
    "/applications/<int:id>/courses-of-action/add", methods=["POST"]
)
@login_required
def course_of_action_add(id):
    """Link existing Course of Action to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    coa_id = request.form.get("element_id")

    if not coa_id:
        flash("No course of action selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    coa = CourseOfAction.query.get(coa_id)
    if not coa:
        flash("Course of action not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    if coa.application_component_id and coa.application_component_id != app.id:
        other_app = ApplicationComponent.query.get(coa.application_component_id)
        flash(
            f'Course of action "{coa.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif coa.application_component_id == app.id:
        flash(
            f'Course of action "{coa.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            coa.application_component_id = app.id
            db.session.commit()
            flash(f'Course of action "{coa.name}" linked successfully!', "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking course of action {coa_id} to app {id}: {e}"
            )
            flash("Error linking course of action. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#strategy")


@application_mgmt.route("/applications/<int:id>/value-streams/add", methods=["POST"])
@login_required
def value_stream_add(id):
    """Link existing Value Stream to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    value_stream_id = request.form.get("element_id")

    if not value_stream_id:
        flash("No value stream selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    value_stream = ValueStream.query.get(value_stream_id)
    if not value_stream:
        flash("Value stream not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    if (
        value_stream.application_component_id
        and value_stream.application_component_id != app.id
    ):
        other_app = ApplicationComponent.query.get(
            value_stream.application_component_id
        )
        flash(
            f'Value stream "{value_stream.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif value_stream.application_component_id == app.id:
        flash(
            f'Value stream "{value_stream.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            value_stream.application_component_id = app.id
            db.session.commit()
            flash(f'Value stream "{value_stream.name}" linked successfully!', "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking value stream {value_stream_id} to app {id}: {e}"
            )
            flash("Error linking value stream. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#strategy")


# ============================================================================
# BULK OPERATIONS ROUTES
# ============================================================================


@application_mgmt.route("/applications/<int:id>/bulk-link", methods=["POST"])
@login_required
def bulk_link_elements(id):
    """Link multiple elements to application at once"""
    app = ApplicationComponent.query.get_or_404(id)

    # Get element type and IDs from form or JSON
    element_type = request.form.get("element_type") or (
        request.json.get("element_type") if request.is_json else None
    )
    element_ids = request.form.getlist("element_ids[]") or (
        request.json.get("element_ids", []) if request.is_json else []
    )

    if not element_type or not element_ids:
        if request.is_json:
            return {
                "success": False,
                "error": "Missing element_type or element_ids",
            }, 400
        flash("No elements selected for bulk linking", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Map element types to models
    element_models = {
        "business-actor": BusinessActor,
        "business-role": BusinessRole,
        "business-service": BusinessService,
        "business-function": BusinessFunction,
        "business-object": BusinessObject,
        "application-interface": ApplicationInterface,
        "application-service": ApplicationService,
        "data-object": DataObject,
        "technology-node": TechnologyNode,
        "technology-device": TechnologyDevice,
        "system-software": SystemSoftware,
        "goal": Goal,
        "driver": Driver,
        "requirement": Requirement,
        "work-package": WorkPackage,
        "deliverable": Deliverable,
        "plateau": Plateau,
        "course-of-action": CourseOfAction,
        "value-stream": ValueStream,
        "physical-equipment": PhysicalEquipment,
        "physical-facility": PhysicalFacility,
        "distribution-network": PhysicalDistributionNetwork,
        "physical-material": PhysicalMaterial,
    }

    model = element_models.get(element_type)
    if not model:
        if request.is_json:
            return {
                "success": False,
                "error": f"Invalid element type: {element_type}",
            }, 400
        flash(f"Invalid element type: {element_type}", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Process bulk linking
    linked = 0
    already_linked = 0
    errors = []

    try:
        for element_id in element_ids:
            element = model.query.get(element_id)
            if not element:
                errors.append(f"Element {element_id} not found")
                continue

            # Check if already linked
            if element.application_component_id is not None:
                if element.application_component_id == app.id:
                    already_linked += 1
                    continue
                elif element.application_component_id:
                    errors.append(
                        f"{element.name} already linked to another application"
                    )
                    continue

                # Link element
                element.application_component_id = app.id
                linked += 1
            else:
                errors.append(f"{element_type} does not support direct linking")

        db.session.commit()

        # Prepare response
        message = f"Linked {linked} element(s) successfully"
        if already_linked > 0:
            message += f", {already_linked} already linked"
        if errors:
            message += f", {len(errors)} error(s)"

        if request.is_json:
            return {
                "success": True,
                "linked": linked,
                "already_linked": already_linked,
                "errors": errors,
                "message": message,
            }

        if linked > 0:
            flash(message, "success")
        if errors:
            for error in errors[:5]:  # Show first 5 errors
                flash(error, "warning")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk link: {e}")
        if request.is_json:
            return {"success": False, "error": str(e)}, 500
        flash("Error linking elements. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id))


@application_mgmt.route("/applications/<int:id>/bulk-unlink", methods=["POST"])
@login_required
def bulk_unlink_elements(id):
    """Unlink multiple elements from application at once"""
    app = ApplicationComponent.query.get_or_404(id)

    # Get element type and IDs from form or JSON
    element_type = request.form.get("element_type") or (
        request.json.get("element_type") if request.is_json else None
    )
    element_ids = request.form.getlist("element_ids[]") or (
        request.json.get("element_ids", []) if request.is_json else []
    )

    if not element_type or not element_ids:
        if request.is_json:
            return {
                "success": False,
                "error": "Missing element_type or element_ids",
            }, 400
        flash("No elements selected for bulk unlinking", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Map element types to models
    element_models = {
        "business-actor": BusinessActor,
        "business-role": BusinessRole,
        "business-service": BusinessService,
        "business-function": BusinessFunction,
        "business-object": BusinessObject,
        "application-interface": ApplicationInterface,
        "application-service": ApplicationService,
        "data-object": DataObject,
        "technology-node": TechnologyNode,
        "technology-device": TechnologyDevice,
        "system-software": SystemSoftware,
        "goal": Goal,
        "driver": Driver,
        "requirement": Requirement,
        "work-package": WorkPackage,
        "deliverable": Deliverable,
        "plateau": Plateau,
        "course-of-action": CourseOfAction,
        "value-stream": ValueStream,
        "physical-equipment": PhysicalEquipment,
        "physical-facility": PhysicalFacility,
        "distribution-network": PhysicalDistributionNetwork,
        "physical-material": PhysicalMaterial,
    }

    model = element_models.get(element_type)
    if not model:
        if request.is_json:
            return {
                "success": False,
                "error": f"Invalid element type: {element_type}",
            }, 400
        flash(f"Invalid element type: {element_type}", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Process bulk unlinking
    unlinked = 0
    not_linked = 0
    errors = []

    try:
        for element_id in element_ids:
            element = model.query.get(element_id)
            if not element:
                errors.append(f"Element {element_id} not found")
                continue

            # Check if linked to this application
            if element.application_component_id is not None:
                if element.application_component_id != app.id:
                    not_linked += 1
                    continue

                # Unlink element
                element.application_component_id = None
                unlinked += 1
            else:
                errors.append(f"{element_type} does not support direct unlinking")

        db.session.commit()

        # Prepare response
        message = f"Unlinked {unlinked} element(s) successfully"
        if not_linked > 0:
            message += f", {not_linked} not linked to this application"
        if errors:
            message += f", {len(errors)} error(s)"

        if request.is_json:
            return {
                "success": True,
                "unlinked": unlinked,
                "not_linked": not_linked,
                "errors": errors,
                "message": message,
            }

        if unlinked > 0:
            flash(message, "success")
        if errors:
            for error in errors[:5]:  # Show first 5 errors
                flash(error, "warning")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk unlink: {e}")
        if request.is_json:
            return {"success": False, "error": str(e)}, 500
        flash("Error unlinking elements. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id))


@application_mgmt.route("/applications/<int:id>/bulk-update", methods=["POST"])
@login_required
def bulk_update_elements(id):
    """Update properties on multiple elements at once"""
    app = ApplicationComponent.query.get_or_404(id)

    # Get element type, IDs, and update data from form or JSON
    element_type = request.form.get("element_type") or (
        request.json.get("element_type") if request.is_json else None
    )
    element_ids = request.form.getlist("element_ids[]") or (
        request.json.get("element_ids", []) if request.is_json else []
    )
    update_data = request.json.get("update_data", {}) if request.is_json else {}

    # For form submissions, get individual fields
    if not request.is_json:
        update_data = {
            key: value
            for key, value in request.form.items()
            if key not in ["element_type", "element_ids[]", "csrf_token"]
        }

    if not element_type or not element_ids or not update_data:
        if request.is_json:
            return {
                "success": False,
                "error": "Missing element_type, element_ids, or update_data",
            }, 400
        flash("Missing required data for bulk update", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Map element types to models
    element_models = {
        "business-actor": BusinessActor,
        "business-role": BusinessRole,
        "business-service": BusinessService,
        "business-function": BusinessFunction,
        "business-object": BusinessObject,
        "application-interface": ApplicationInterface,
        "application-service": ApplicationService,
        "data-object": DataObject,
        "technology-node": TechnologyNode,
        "technology-device": TechnologyDevice,
        "system-software": SystemSoftware,
        "goal": Goal,
        "driver": Driver,
        "requirement": Requirement,
        "work-package": WorkPackage,
        "deliverable": Deliverable,
        "plateau": Plateau,
        "course-of-action": CourseOfAction,
        "value-stream": ValueStream,
        "physical-equipment": PhysicalEquipment,
        "physical-facility": PhysicalFacility,
        "distribution-network": PhysicalDistributionNetwork,
        "physical-material": PhysicalMaterial,
    }

    model = element_models.get(element_type)
    if not model:
        if request.is_json:
            return {
                "success": False,
                "error": f"Invalid element type: {element_type}",
            }, 400
        flash(f"Invalid element type: {element_type}", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Process bulk update
    updated = 0
    errors = []

    try:
        for element_id in element_ids:
            element = model.query.get(element_id)
            if not element:
                errors.append(f"Element {element_id} not found")
                continue

            # Update allowed fields
            for field, value in update_data.items():
                if hasattr(element, field):
                    # Handle empty strings as None for optional fields
                    if field == "description" and value == "":
                        setattr(element, field, None)
                    elif value:
                        setattr(
                            element,
                            field,
                            value.strip() if isinstance(value, str) else value,
                        )
                    updated += 1

        db.session.commit()

        # Prepare response
        message = f"Updated {len(element_ids)} element(s) successfully"
        if errors:
            message += f", {len(errors)} error(s)"

        if request.is_json:
            return {
                "success": True,
                "updated": len(element_ids) - len(errors),
                "errors": errors,
                "message": message,
            }

        flash(message, "success")
        if errors:
            for error in errors[:5]:  # Show first 5 errors
                flash(error, "warning")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk update: {e}")
        if request.is_json:
            return {"success": False, "error": str(e)}, 500
        flash("Error updating elements. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id))
