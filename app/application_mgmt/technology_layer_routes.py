"""
Technology Layer Routes — sub-module extracted from routes.py (BE-054 wave-8).

Handles ArchiMate technology-layer element management:
  * Inline CRUD (nodes, system-software, technology-services) via helpers
  * Form-based linking of Node, Device, SystemSoftware, TechnologyInterface,
    Path, CommunicationNetwork, TechnologyService to ApplicationComponents
"""

from flask import current_app, flash, redirect, request, url_for
from flask_login import login_required

from .. import db
from ..models.application_portfolio import ApplicationComponent
from ..models.technology_layer import (
    CommunicationNetwork,
    Device,
    Node,
    Path,
    SystemSoftware,
    TechnologyInterface,
    TechnologyService,
)
from . import application_mgmt
from .routes import _add_archimate_element, _delete_archimate_element

# --- Technology Layer ---
@application_mgmt.route("/applications/<int:app_id>/nodes", methods=["POST"])
@login_required
def add_node(app_id):
    # Application is DEPLOYED ON Node (assignment or association? ArchiMate says 'Realization' for strict serving, but usually 'Serving' from Tech to App.
    # Let's use 'serving' (reverse of realization sort of) or just 'association' for now, but typically Tech SERVES App.
    # Actually for simplicity I will use 'association' or check the service relationship direction.
    # Standard: Node SERVES ApplicationComponent.
    # So Source=Node, Target=App. But here we are adding Node FROM App context.
    # Let's keep using _add_archimate_element which assumes App -> Element (Realizes/Composes).
    # IF we want Node -> App (Serving), we need to swap.
    # For now, let's assume 'association' for Technology linkage or 'serving' (Target=App).
    # I'll stick to generic helper for now and fix direction if needed, but let's use 'serving' from Tech to App.
    # WAIT, the helper performs Source=App, Target=Element.
    # App 'depends on' Node. Node 'serves' App.
    # So simple 'association' is safest for now, or 'serving' where Source=Element(Node), Target=App.
    # I'll update the helper to handle relationship types.
    return _add_archimate_element(
        app_id, "technology", "Node", request.json, rel_type="serving", reverse_rel=True
    )


@application_mgmt.route("/applications/<int:app_id>/nodes/<int:id>", methods=["DELETE"])
@login_required
def delete_node(app_id, id):
    return _delete_archimate_element(id, "serving")


@application_mgmt.route("/applications/<int:app_id>/system-software", methods=["POST"])
@login_required
def add_system_software(app_id):
    return _add_archimate_element(
        app_id,
        "technology",
        "SystemSoftware",
        request.json,
        rel_type="serving",
        reverse_rel=True,
    )


@application_mgmt.route(
    "/applications/<int:app_id>/system-software/<int:id>", methods=["DELETE"]
)
@login_required
def delete_system_software(app_id, id):
    return _delete_archimate_element(id, "serving")


@application_mgmt.route(
    "/applications/<int:app_id>/technology-services", methods=["POST"]
)
@login_required
def add_technology_service(app_id):
    return _add_archimate_element(
        app_id,
        "technology",
        "TechnologyService",
        request.json,
        rel_type="serving",
        reverse_rel=True,
    )


@application_mgmt.route(
    "/applications/<int:app_id>/technology-services/<int:id>", methods=["DELETE"]
)
@login_required
def delete_technology_service(app_id, id):
    return _delete_archimate_element(id, "serving")

@application_mgmt.route("/applications/<int:id>/technology-nodes/add", methods=["POST"])
@login_required
def technology_node_add(id):
    """Link existing Technology Node to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    node_id = request.form.get("element_id")

    if not node_id:
        flash("No technology node selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    node = Node.query.get(node_id)
    if not node:
        flash("Technology node not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Check if already linked to another application
    if node.application_component_id and node.application_component_id != app.id:
        other_app = ApplicationComponent.query.get(node.application_component_id)
        flash(
            f'Technology node "{node.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif node.application_component_id == app.id:
        flash(
            f'Technology node "{node.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            # Update direct FK
            node.application_component_id = app.id
            db.session.commit()
            flash(f'Technology node "{node.name}" linked successfully!', "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking technology node {node_id} to app {id}: {e}"
            )
            flash("Error linking technology node. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


@application_mgmt.route(
    "/applications/<int:id>/technology-devices/add", methods=["POST"]
)
@login_required
def technology_device_add(id):
    """Link existing Technology Device to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    device_id = request.form.get("element_id")

    if not device_id:
        flash("No technology device selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    device = Device.query.get(device_id)
    if not device:
        flash("Technology device not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Check if already linked to another application
    if device.application_component_id and device.application_component_id != app.id:
        other_app = ApplicationComponent.query.get(device.application_component_id)
        flash(
            f'Technology device "{device.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif device.application_component_id == app.id:
        flash(
            f'Technology device "{device.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            # Update direct FK
            device.application_component_id = app.id
            db.session.commit()
            flash(f'Technology device "{device.name}" linked successfully!', "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking technology device {device_id} to app {id}: {e}"
            )
            flash("Error linking technology device. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


@application_mgmt.route("/applications/<int:id>/system-software/add", methods=["POST"])
@login_required
def system_software_add(id):
    """Link existing System Software to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    software_id = request.form.get("element_id")

    if not software_id:
        flash("No system software selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    software = SystemSoftware.query.get(software_id)
    if not software:
        flash("System software not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Check if already linked to another application
    if (
        software.application_component_id
        and software.application_component_id != app.id
    ):
        other_app = ApplicationComponent.query.get(software.application_component_id)
        flash(
            f'System software "{software.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif software.application_component_id == app.id:
        flash(
            f'System software "{software.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            # Update direct FK
            software.application_component_id = app.id
            db.session.commit()
            flash(f'System software "{software.name}" linked successfully!', "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking system software {software_id} to app {id}: {e}"
            )
            flash("Error linking system software. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )

# ============================================================================
# ADD ROUTES - Technology Layer (Additional Elements)
# ============================================================================


@application_mgmt.route(
    "/applications/<int:id>/technology-interfaces/add", methods=["POST"]
)
@login_required
def technology_interface_add(id):
    """Link existing Technology Interface to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    interface_id = request.form.get("element_id")

    if not interface_id:
        flash("No technology interface selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    interface = TechnologyInterface.query.get(interface_id)
    if not interface:
        flash("Technology interface not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    if (
        interface.application_component_id
        and interface.application_component_id != app.id
    ):
        other_app = ApplicationComponent.query.get(interface.application_component_id)
        flash(
            f'Technology interface "{interface.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif interface.application_component_id == app.id:
        flash(
            f'Technology interface "{interface.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            interface.application_component_id = app.id
            db.session.commit()
            flash(
                f'Technology interface "{interface.name}" linked successfully!',
                "success",
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking technology interface {interface_id} to app {id}: {e}"
            )
            flash("Error linking technology interface. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


@application_mgmt.route("/applications/<int:id>/technology-paths/add", methods=["POST"])
@login_required
def technology_path_add(id):
    """Link existing Technology Path to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    path_id = request.form.get("element_id")

    if not path_id:
        flash("No technology path selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    path = Path.query.get(path_id)
    if not path:
        flash("Technology path not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    if path.application_component_id and path.application_component_id != app.id:
        other_app = ApplicationComponent.query.get(path.application_component_id)
        flash(
            f'Technology path "{path.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif path.application_component_id == app.id:
        flash(
            f'Technology path "{path.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            path.application_component_id = app.id
            db.session.commit()
            flash(f'Technology path "{path.name}" linked successfully!', "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking technology path {path_id} to app {id}: {e}"
            )
            flash("Error linking technology path. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


@application_mgmt.route(
    "/applications/<int:id>/communication-networks/add", methods=["POST"]
)
@login_required
def communication_network_add(id):
    """Link existing Communication Network to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    network_id = request.form.get("element_id")

    if not network_id:
        flash("No communication network selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    network = CommunicationNetwork.query.get(network_id)
    if not network:
        flash("Communication network not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    if network.application_component_id and network.application_component_id != app.id:
        other_app = ApplicationComponent.query.get(network.application_component_id)
        flash(
            f'Communication network "{network.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif network.application_component_id == app.id:
        flash(
            f'Communication network "{network.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            network.application_component_id = app.id
            db.session.commit()
            flash(
                f'Communication network "{network.name}" linked successfully!',
                "success",
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking communication network {network_id} to app {id}: {e}"
            )
            flash("Error linking communication network. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


@application_mgmt.route(
    "/applications/<int:id>/technology-services/add", methods=["POST"]
)
@login_required
def technology_service_add(id):
    """Link existing Technology Service to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    service_id = request.form.get("element_id")

    if not service_id:
        flash("No technology service selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    service = TechnologyService.query.get(service_id)
    if not service:
        flash("Technology service not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    if service.application_component_id and service.application_component_id != app.id:
        other_app = ApplicationComponent.query.get(service.application_component_id)
        flash(
            f'Technology service "{service.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif service.application_component_id == app.id:
        flash(
            f'Technology service "{service.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            service.application_component_id = app.id
            db.session.commit()
            flash(
                f'Technology service "{service.name}" linked successfully!', "success"
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking technology service {service_id} to app {id}: {e}"
            )
            flash("Error linking technology service. Please try again.", "error")

    return redirect(
        url_for("unified_applications.application_detail", id=id) + "#technology"
    )


