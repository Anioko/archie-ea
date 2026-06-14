"""
Physical Layer Routes — sub-module extracted from routes.py (BE-054 wave-10).

Handles ArchiMate physical layer element management:
  * PhysicalEquipment, PhysicalFacility, PhysicalDistributionNetwork, PhysicalMaterial
  * Form-based layer update (physical-update)
  * Direct FK link/unlink and edit routes
"""

import json
import logging

from flask import current_app, flash, jsonify, redirect, request, session, url_for
from flask_login import login_required

logger = logging.getLogger(__name__)

from .. import db
from ..models.application_portfolio import ApplicationComponent
from ..models.physical_layer import (
    PhysicalDistributionNetwork,
    PhysicalEquipment,
    PhysicalFacility,
    PhysicalMaterial,
)
from . import application_mgmt
from .forms import PhysicalLayerForm


# Wave 10: Physical layer routes


@application_mgmt.route(
    "/applications/<int:id>/layers/physical-update", methods=["POST"]
)
@login_required
def update_physical_layer(id):
    """Update Physical Layer elements (Equipment, Facilities, Distribution Networks, Materials)"""
    app = ApplicationComponent.query.get_or_404(id)
    # csrf-ok: global CSRFProtect active
    try:
        form = PhysicalLayerForm(request.form)
        if not form.validate():

            def format_errors(errors_dict):
                formatted = []
                for field, msgs in errors_dict.items():
                    if isinstance(msgs, dict):
                        for sub_field, sub_msgs in msgs.items():
                            if isinstance(sub_msgs, list):
                                formatted.append(
                                    f"{field}.{sub_field}: {', '.join(str(m) for m in sub_msgs)}"
                                )
                            else:
                                formatted.append(f"{field}.{sub_field}: {sub_msgs}")
                    elif isinstance(msgs, list):
                        formatted.append(f"{field}: {', '.join(str(m) for m in msgs)}")
                    else:
                        formatted.append(f"{field}: {msgs}")
                return formatted

            errors = format_errors(form.errors)
            return jsonify({"success": False, "errors": errors}), 400
        changed_fields = []

        # Process physical equipment updates and deletions
        if form.equipment.data:
            from ..models.physical_layer import PhysicalEquipment

            for equip_data in form.equipment.data:
                equip_id = equip_data.get("id")
                equip_delete = equip_data.get("_delete")
                if equip_id and equip_delete:
                    equip_obj = PhysicalEquipment.query.get(int(equip_id))
                    if equip_obj:
                        db.session.delete(equip_obj)
                        changed_fields.append(f"equipment_{equip_id}_deleted")
                    continue
                equip_name = equip_data.get("name")
                equip_description = equip_data.get("description")
                if equip_id and equip_name:
                    equip_obj = PhysicalEquipment.query.get(int(equip_id))
                    if equip_obj:
                        has_changed = False
                        if equip_obj.name != equip_name:
                            equip_obj.name = equip_name
                            has_changed = True
                        if equip_obj.description != (equip_description or ""):
                            equip_obj.description = equip_description or ""
                            has_changed = True
                        if has_changed:
                            changed_fields.append(f"equipment_{equip_id}")
                            db.session.add(equip_obj)

        # Process physical facility updates and deletions
        if form.facilities.data:
            from ..models.physical_layer import PhysicalFacility

            for facility_data in form.facilities.data:
                facility_id = facility_data.get("id")
                facility_delete = facility_data.get("_delete")
                if facility_id and facility_delete:
                    facility_obj = PhysicalFacility.query.get(int(facility_id))
                    if facility_obj:
                        db.session.delete(facility_obj)
                        changed_fields.append(f"facility_{facility_id}_deleted")
                    continue
                facility_name = facility_data.get("name")
                facility_description = facility_data.get("description")
                if facility_id and facility_name:
                    facility_obj = PhysicalFacility.query.get(int(facility_id))
                    if facility_obj:
                        has_changed = False
                        if facility_obj.name != facility_name:
                            facility_obj.name = facility_name
                            has_changed = True
                        if facility_obj.description != (facility_description or ""):
                            facility_obj.description = facility_description or ""
                            has_changed = True
                        if has_changed:
                            changed_fields.append(f"facility_{facility_id}")
                            db.session.add(facility_obj)

        # Process physical distribution network updates and deletions
        if form.distribution_networks.data:
            from ..models.physical_layer import PhysicalDistributionNetwork

            for network_data in form.distribution_networks.data:
                network_id = network_data.get("id")
                network_delete = network_data.get("_delete")
                if network_id and network_delete:
                    network_obj = PhysicalDistributionNetwork.query.get(int(network_id))
                    if network_obj:
                        db.session.delete(network_obj)
                        changed_fields.append(f"network_{network_id}_deleted")
                    continue
                network_name = network_data.get("name")
                network_description = network_data.get("description")
                if network_id and network_name:
                    network_obj = PhysicalDistributionNetwork.query.get(int(network_id))
                    if network_obj:
                        has_changed = False
                        if network_obj.name != network_name:
                            network_obj.name = network_name
                            has_changed = True
                        if network_obj.description != (network_description or ""):
                            network_obj.description = network_description or ""
                            has_changed = True
                        if has_changed:
                            changed_fields.append(f"network_{network_id}")
                            db.session.add(network_obj)

        # Process physical material updates and deletions
        if form.materials.data:
            from ..models.physical_layer import PhysicalMaterial

            for material_data in form.materials.data:
                material_id = material_data.get("id")
                material_delete = material_data.get("_delete")
                if material_id and material_delete:
                    material_obj = PhysicalMaterial.query.get(int(material_id))
                    if material_obj:
                        db.session.delete(material_obj)
                        changed_fields.append(f"material_{material_id}_deleted")
                    continue
                material_name = material_data.get("name")
                material_description = material_data.get("description")
                if material_id and material_name:
                    material_obj = PhysicalMaterial.query.get(int(material_id))
                    if material_obj:
                        has_changed = False
                        if material_obj.name != material_name:
                            material_obj.name = material_name
                            has_changed = True
                        if material_obj.description != (material_description or ""):
                            material_obj.description = material_description or ""
                            has_changed = True
                        if has_changed:
                            changed_fields.append(f"material_{material_id}")
                            db.session.add(material_obj)

        db.session.commit()
        if changed_fields:
            try:
                session["physical_changes"] = json.dumps(changed_fields)
            except Exception as e:  # fabricated-values-ok
                logger.debug(f"Ignored: {e}")
        return jsonify(
            {
                "success": True,
                "message": f"Physical layer updated ({len(changed_fields)} changes)",
                "changed": changed_fields,
            }
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Error updating physical layer: {str(exc)}")
        return jsonify({"success": False, "error": str(exc)}), 500


@application_mgmt.route(
    "/applications/<int:id>/physical-equipment/<int:equipment_id>/delete",
    methods=["POST"],
)
@login_required
def physical_equipment_delete(id, equipment_id):
    """Unlink Physical Equipment from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    equipment = PhysicalEquipment.query.get_or_404(equipment_id)

    try:
        if equipment.application_component_id == app.id:
            equipment.application_component_id = None
            db.session.commit()
            flash(
                f'Physical equipment "{equipment.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Physical equipment "{equipment.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking physical equipment {equipment_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking physical equipment. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/physical-facilities/<int:facility_id>/delete",
    methods=["POST"],
)
@login_required
def physical_facility_delete(id, facility_id):
    """Unlink Physical Facility from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    facility = PhysicalFacility.query.get_or_404(facility_id)

    try:
        if facility.application_component_id == app.id:
            facility.application_component_id = None
            db.session.commit()
            flash(
                f'Physical facility "{facility.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Physical facility "{facility.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking physical facility {facility_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking physical facility. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/distribution-networks/<int:network_id>/delete",
    methods=["POST"],
)
@login_required
def distribution_network_delete(id, network_id):
    """Unlink Distribution Network from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    network = PhysicalDistributionNetwork.query.get_or_404(network_id)

    try:
        if network.application_component_id == app.id:
            network.application_component_id = None
            db.session.commit()
            flash(
                f'Distribution network "{network.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Distribution network "{network.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking distribution network {network_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking distribution network. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/physical-materials/<int:material_id>/delete",
    methods=["POST"],
)
@login_required
def physical_material_delete(id, material_id):
    """Unlink Physical Material from application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    material = PhysicalMaterial.query.get_or_404(material_id)

    try:
        if material.application_component_id == app.id:
            material.application_component_id = None
            db.session.commit()
            flash(
                f'Physical material "{material.name}" unlinked from application',
                "success",
            )
        else:
            flash(
                f'Physical material "{material.name}" is not linked to this application',
                "warning",
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error unlinking physical material {material_id} from app {id}: {str(e)}"
        )
        flash("Error unlinking physical material. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/physical-equipment/<int:equipment_id>/edit",
    methods=["POST"],
)
@login_required
def physical_equipment_edit(id, equipment_id):
    """Update Physical Equipment properties"""
    app = ApplicationComponent.query.get_or_404(id)
    equipment = PhysicalEquipment.query.get_or_404(equipment_id)

    try:
        if "name" in request.form:
            equipment.name = request.form.get("name").strip()
        if "description" in request.form:
            equipment.description = request.form.get("description").strip() or None
        if "equipment_type" in request.form:
            equipment.equipment_type = request.form.get("equipment_type") or None
        if "location" in request.form:
            equipment.location = request.form.get("location") or None

        db.session.commit()
        flash(f'Physical equipment "{equipment.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error updating physical equipment {equipment_id}: {e}"
        )
        flash("Error updating physical equipment. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/physical-facilities/<int:facility_id>/edit",
    methods=["POST"],
)
@login_required
def physical_facility_edit(id, facility_id):
    """Update Physical Facility properties"""
    app = ApplicationComponent.query.get_or_404(id)
    facility = PhysicalFacility.query.get_or_404(facility_id)

    try:
        if "name" in request.form:
            facility.name = request.form.get("name").strip()
        if "description" in request.form:
            facility.description = request.form.get("description").strip() or None
        if "facility_type" in request.form:
            facility.facility_type = request.form.get("facility_type") or None
        if "location" in request.form:
            facility.location = request.form.get("location") or None

        db.session.commit()
        flash(f'Physical facility "{facility.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating physical facility {facility_id}: {e}")
        flash("Error updating physical facility. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/distribution-networks/<int:network_id>/edit",
    methods=["POST"],
)
@login_required
def distribution_network_edit(id, network_id):
    """Update Distribution Network properties"""
    app = ApplicationComponent.query.get_or_404(id)
    network = PhysicalDistributionNetwork.query.get_or_404(network_id)

    try:
        if "name" in request.form:
            network.name = request.form.get("name").strip()
        if "description" in request.form:
            network.description = request.form.get("description").strip() or None
        if "network_type" in request.form:
            network.network_type = request.form.get("network_type") or None

        db.session.commit()
        flash(f'Distribution network "{network.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error updating distribution network {network_id}: {e}"
        )
        flash("Error updating distribution network. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/physical-materials/<int:material_id>/edit", methods=["POST"]
)
@login_required
def physical_material_edit(id, material_id):
    """Update Physical Material properties"""
    app = ApplicationComponent.query.get_or_404(id)
    material = PhysicalMaterial.query.get_or_404(material_id)

    try:
        if "name" in request.form:
            material.name = request.form.get("name").strip()
        if "description" in request.form:
            material.description = request.form.get("description").strip() or None
        if "material_type" in request.form:
            material.material_type = request.form.get("material_type") or None

        db.session.commit()
        flash(f'Physical material "{material.name}" updated successfully!', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating physical material {material_id}: {e}")
        flash("Error updating physical material. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/physical-equipment/add", methods=["POST"]
)
@login_required
def physical_equipment_add(id):
    """Link existing Physical Equipment to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    equipment_id = request.form.get("element_id")

    if not equipment_id:
        flash("No physical equipment selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    equipment = PhysicalEquipment.query.get(equipment_id)
    if not equipment:
        flash("Physical equipment not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Check if already linked to another application
    if (
        equipment.application_component_id
        and equipment.application_component_id != app.id
    ):
        other_app = ApplicationComponent.query.get(equipment.application_component_id)
        flash(
            f'Physical equipment "{equipment.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif equipment.application_component_id == app.id:
        flash(
            f'Physical equipment "{equipment.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            equipment.application_component_id = app.id
            db.session.commit()
            flash(
                f'Physical equipment "{equipment.name}" linked successfully!', "success"
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking physical equipment {equipment_id} to app {id}: {e}"
            )
            flash("Error linking physical equipment. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/physical-facilities/add", methods=["POST"]
)
@login_required
def physical_facility_add(id):
    """Link existing Physical Facility to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    facility_id = request.form.get("element_id")

    if not facility_id:
        flash("No physical facility selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    facility = PhysicalFacility.query.get(facility_id)
    if not facility:
        flash("Physical facility not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Check if already linked to another application
    if (
        facility.application_component_id
        and facility.application_component_id != app.id
    ):
        other_app = ApplicationComponent.query.get(facility.application_component_id)
        flash(
            f'Physical facility "{facility.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif facility.application_component_id == app.id:
        flash(
            f'Physical facility "{facility.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            facility.application_component_id = app.id
            db.session.commit()
            flash(
                f'Physical facility "{facility.name}" linked successfully!', "success"
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking physical facility {facility_id} to app {id}: {e}"
            )
            flash("Error linking physical facility. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/distribution-networks/add", methods=["POST"]
)
@login_required
def distribution_network_add(id):
    """Link existing Physical Distribution Network to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    network_id = request.form.get("element_id")

    if not network_id:
        flash("No distribution network selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    network = PhysicalDistributionNetwork.query.get(network_id)
    if not network:
        flash("Distribution network not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Check if already linked to another application
    if network.application_component_id and network.application_component_id != app.id:
        other_app = ApplicationComponent.query.get(network.application_component_id)
        flash(
            f'Distribution network "{network.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif network.application_component_id == app.id:
        flash(
            f'Distribution network "{network.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            network.application_component_id = app.id
            db.session.commit()
            flash(
                f'Distribution network "{network.name}" linked successfully!', "success"
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking distribution network {network_id} to app {id}: {e}"
            )
            flash("Error linking distribution network. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")


@application_mgmt.route(
    "/applications/<int:id>/physical-materials/add", methods=["POST"]
)
@login_required
def physical_material_add(id):
    """Link existing Physical Material to Application (direct FK)"""
    app = ApplicationComponent.query.get_or_404(id)
    material_id = request.form.get("element_id")

    if not material_id:
        flash("No physical material selected", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    material = PhysicalMaterial.query.get(material_id)
    if not material:
        flash("Physical material not found", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    # Check if already linked to another application
    if (
        material.application_component_id
        and material.application_component_id != app.id
    ):
        other_app = ApplicationComponent.query.get(material.application_component_id)
        flash(
            f'Physical material "{material.name}" is already linked to "{other_app.name if other_app else "another application"}"',
            "warning",
        )
    elif material.application_component_id == app.id:
        flash(
            f'Physical material "{material.name}" is already linked to this application',
            "warning",
        )
    else:
        try:
            material.application_component_id = app.id
            db.session.commit()
            flash(
                f'Physical material "{material.name}" linked successfully!', "success"
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error linking physical material {material_id} to app {id}: {e}"
            )
            flash("Error linking physical material. Please try again.", "error")

    return redirect(url_for("unified_applications.application_detail", id=id) + "#physical")
