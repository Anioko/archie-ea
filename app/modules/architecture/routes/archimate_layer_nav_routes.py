"""ArchiMate Layer Navigation Routes - North Star Phase 2

Provides layer-specific navigation entry points that filter the main
ArchiMate composer by layer and element type.

All routes redirect to /archimate/composer with appropriate filters.
This leverages the existing mature composer UI rather than duplicating code.

Routes:
- /architecture/motivation/* → Motivation Layer elements
- /architecture/strategy/* → Strategy Layer elements  
- /architecture/business/* → Business Layer elements
- /architecture/application/* → Application Layer elements
- /architecture/technology/* → Technology Layer elements
- /architecture/physical/* → Physical Layer elements
- /architecture/implementation/* → Implementation Layer elements
"""

from flask import Blueprint, redirect, url_for, request
from flask_login import login_required

archimate_layer_nav_bp = Blueprint('archimate_layers', __name__, url_prefix='/architecture')


# ============================================================================
# MOTIVATION LAYER (9 element types)
# ============================================================================

@archimate_layer_nav_bp.route('/motivation/stakeholders')
@login_required
def motivation_stakeholders():
    """Navigate to Stakeholders (Motivation Layer)."""
    return redirect(url_for('archimate.composer_page', layer='motivation', element_type='stakeholder'))

@archimate_layer_nav_bp.route('/motivation/drivers')
@login_required
def motivation_drivers():
    """Navigate to Drivers (Motivation Layer)."""
    return redirect(url_for('archimate.composer_page', layer='motivation', element_type='driver'))

@archimate_layer_nav_bp.route('/motivation/assessments')
@login_required
def motivation_assessments():
    """Navigate to Assessments (Motivation Layer)."""
    return redirect(url_for('archimate.composer_page', layer='motivation', element_type='assessment'))

@archimate_layer_nav_bp.route('/motivation/goals')
@login_required
def motivation_goals():
    """Navigate to Goals (Motivation Layer)."""
    return redirect(url_for('archimate.composer_page', layer='motivation', element_type='goal'))

@archimate_layer_nav_bp.route('/motivation/outcomes')
@login_required
def motivation_outcomes():
    """Navigate to Outcomes (Motivation Layer)."""
    return redirect(url_for('archimate.composer_page', layer='motivation', element_type='outcome'))

@archimate_layer_nav_bp.route('/motivation/principles')
@login_required
def motivation_principles():
    """Navigate to Principles (Motivation Layer)."""
    return redirect(url_for('archimate.composer_page', layer='motivation', element_type='principle'))

@archimate_layer_nav_bp.route('/motivation/requirements')
@login_required
def motivation_requirements():
    """Navigate to Requirements (Motivation Layer)."""
    return redirect(url_for('archimate.composer_page', layer='motivation', element_type='requirement'))

@archimate_layer_nav_bp.route('/motivation/constraints')
@login_required
def motivation_constraints():
    """Navigate to Constraints (Motivation Layer)."""
    return redirect(url_for('archimate.composer_page', layer='motivation', element_type='constraint'))

@archimate_layer_nav_bp.route('/motivation/meanings')
@login_required
def motivation_meanings():
    """Navigate to Meanings (Motivation Layer)."""
    return redirect(url_for('archimate.composer_page', layer='motivation', element_type='meaning'))


# ============================================================================
# STRATEGY LAYER (4 element types)
# ============================================================================

@archimate_layer_nav_bp.route('/strategy/capabilities/tree')
@login_required
def strategy_capabilities_tree():
    """Navigate to Capabilities tree view - redirects to existing capability map."""
    return redirect(url_for('capability_map.index', view='tree'))

@archimate_layer_nav_bp.route('/strategy/resources')
@login_required
def strategy_resources():
    """Navigate to Resources (Strategy Layer)."""
    return redirect(url_for('archimate.composer_page', layer='strategy', element_type='resource'))

@archimate_layer_nav_bp.route('/strategy/value-streams')
@login_required
def strategy_value_streams():
    """Navigate to Value Streams (Strategy Layer)."""
    return redirect(url_for('archimate.composer_page', layer='strategy', element_type='value_stream'))

@archimate_layer_nav_bp.route('/strategy/courses-of-action')
@login_required
def strategy_courses_of_action():
    """Navigate to Courses of Action (Strategy Layer)."""
    return redirect(url_for('archimate.composer_page', layer='strategy', element_type='course_of_action'))


# ============================================================================
# BUSINESS LAYER (13 element types)
# ============================================================================

@archimate_layer_nav_bp.route('/business/actors')
@login_required
def business_actors():
    """Navigate to Business Actors."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='business_actor'))

@archimate_layer_nav_bp.route('/business/roles')
@login_required
def business_roles():
    """Navigate to Business Roles."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='business_role'))

@archimate_layer_nav_bp.route('/business/collaborations')
@login_required
def business_collaborations():
    """Navigate to Business Collaborations."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='business_collaboration'))

@archimate_layer_nav_bp.route('/business/interfaces')
@login_required
def business_interfaces():
    """Navigate to Business Interfaces."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='business_interface'))

@archimate_layer_nav_bp.route('/business/processes')
@login_required
def business_processes():
    """Navigate to Business Processes (APQC)."""
    # Redirect to APQC process view if available, otherwise composer
    try:
        return redirect(url_for('apqc.process_list'))
    except:
        return redirect(url_for('archimate.composer_page', layer='business', element_type='business_process'))

@archimate_layer_nav_bp.route('/business/functions')
@login_required
def business_functions():
    """Navigate to Business Functions."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='business_function'))

@archimate_layer_nav_bp.route('/business/interactions')
@login_required
def business_interactions():
    """Navigate to Business Interactions."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='business_interaction'))

@archimate_layer_nav_bp.route('/business/events')
@login_required
def business_events():
    """Navigate to Business Events."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='business_event'))

@archimate_layer_nav_bp.route('/business/services')
@login_required
def business_services():
    """Navigate to Business Services."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='business_service'))

@archimate_layer_nav_bp.route('/business/objects')
@login_required
def business_objects():
    """Navigate to Business Objects."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='business_object'))

@archimate_layer_nav_bp.route('/business/contracts')
@login_required
def business_contracts():
    """Navigate to Contracts."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='contract'))

@archimate_layer_nav_bp.route('/business/representations')
@login_required
def business_representations():
    """Navigate to Representations."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='representation'))

@archimate_layer_nav_bp.route('/business/products')
@login_required
def business_products():
    """Navigate to Products."""
    return redirect(url_for('archimate.composer_page', layer='business', element_type='product'))


# ============================================================================
# APPLICATION LAYER (8 element types)
# ============================================================================

@archimate_layer_nav_bp.route('/application/components')
@login_required
def application_components():
    """Navigate to Application Components."""
    return redirect(url_for('archimate.composer_page', layer='application', element_type='application_component'))

@archimate_layer_nav_bp.route('/application/collaborations')
@login_required
def application_collaborations():
    """Navigate to Application Collaborations."""
    return redirect(url_for('archimate.composer_page', layer='application', element_type='application_collaboration'))

@archimate_layer_nav_bp.route('/application/interfaces')
@login_required
def application_interfaces():
    """Navigate to Application Interfaces."""
    return redirect(url_for('archimate.composer_page', layer='application', element_type='application_interface'))

@archimate_layer_nav_bp.route('/application/functions')
@login_required
def application_functions():
    """Navigate to Application Functions."""
    return redirect(url_for('archimate.composer_page', layer='application', element_type='application_function'))

@archimate_layer_nav_bp.route('/application/interactions')
@login_required
def application_interactions():
    """Navigate to Application Interactions."""
    return redirect(url_for('archimate.composer_page', layer='application', element_type='application_interaction'))

@archimate_layer_nav_bp.route('/application/processes')
@login_required
def application_processes():
    """Navigate to Application Processes."""
    return redirect(url_for('archimate.composer_page', layer='application', element_type='application_process'))

@archimate_layer_nav_bp.route('/application/events')
@login_required
def application_events():
    """Navigate to Application Events."""
    return redirect(url_for('archimate.composer_page', layer='application', element_type='application_event'))

@archimate_layer_nav_bp.route('/application/services')
@login_required
def application_services():
    """Navigate to Application Services."""
    return redirect(url_for('archimate.composer_page', layer='application', element_type='application_service'))

@archimate_layer_nav_bp.route('/application/data-objects')
@login_required
def application_data_objects():
    """Navigate to Data Objects."""
    return redirect(url_for('archimate.composer_page', layer='application', element_type='data_object'))


# ============================================================================
# TECHNOLOGY LAYER (11 element types)
# ============================================================================

@archimate_layer_nav_bp.route('/technology/nodes')
@login_required
def technology_nodes():
    """Navigate to Technology Nodes."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='node'))

@archimate_layer_nav_bp.route('/technology/devices')
@login_required
def technology_devices():
    """Navigate to Devices."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='device'))

@archimate_layer_nav_bp.route('/technology/system-software')
@login_required
def technology_system_software():
    """Navigate to System Software."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='system_software'))

@archimate_layer_nav_bp.route('/technology/collaborations')
@login_required
def technology_collaborations():
    """Navigate to Technology Collaborations."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='technology_collaboration'))

@archimate_layer_nav_bp.route('/technology/interfaces')
@login_required
def technology_interfaces():
    """Navigate to Technology Interfaces."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='technology_interface'))

@archimate_layer_nav_bp.route('/technology/paths')
@login_required
def technology_paths():
    """Navigate to Paths."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='path'))

@archimate_layer_nav_bp.route('/technology/networks')
@login_required
def technology_networks():
    """Navigate to Communication Networks."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='communication_network'))

@archimate_layer_nav_bp.route('/technology/functions')
@login_required
def technology_functions():
    """Navigate to Technology Functions."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='technology_function'))

@archimate_layer_nav_bp.route('/technology/processes')
@login_required
def technology_processes():
    """Navigate to Technology Processes."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='technology_process'))

@archimate_layer_nav_bp.route('/technology/interactions')
@login_required
def technology_interactions():
    """Navigate to Technology Interactions."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='technology_interaction'))

@archimate_layer_nav_bp.route('/technology/events')
@login_required
def technology_events():
    """Navigate to Technology Events."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='technology_event'))

@archimate_layer_nav_bp.route('/technology/services')
@login_required
def technology_services():
    """Navigate to Technology Services."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='technology_service'))

@archimate_layer_nav_bp.route('/technology/artifacts')
@login_required
def technology_artifacts():
    """Navigate to Artifacts."""
    return redirect(url_for('archimate.composer_page', layer='technology', element_type='artifact'))


# ============================================================================
# PHYSICAL LAYER (4 element types)
# ============================================================================

@archimate_layer_nav_bp.route('/physical/equipment')
@login_required
def physical_equipment():
    """Navigate to Equipment."""
    return redirect(url_for('archimate.composer_page', layer='physical', element_type='equipment'))

@archimate_layer_nav_bp.route('/physical/facilities')
@login_required
def physical_facilities():
    """Navigate to Facilities."""
    return redirect(url_for('archimate.composer_page', layer='physical', element_type='facility'))

@archimate_layer_nav_bp.route('/physical/distribution-networks')
@login_required
def physical_distribution_networks():
    """Navigate to Distribution Networks."""
    return redirect(url_for('archimate.composer_page', layer='physical', element_type='distribution_network'))

@archimate_layer_nav_bp.route('/physical/materials')
@login_required
def physical_materials():
    """Navigate to Materials."""
    return redirect(url_for('archimate.composer_page', layer='physical', element_type='material'))


# ============================================================================
# IMPLEMENTATION & MIGRATION LAYER (4 element types)
# ============================================================================

@archimate_layer_nav_bp.route('/implementation/work-packages')
@login_required
def implementation_work_packages():
    """Navigate to Work Packages."""
    return redirect(url_for('archimate.composer_page', layer='implementation', element_type='work_package'))

@archimate_layer_nav_bp.route('/implementation/deliverables')
@login_required
def implementation_deliverables():
    """Navigate to Deliverables."""
    return redirect(url_for('archimate.composer_page', layer='implementation', element_type='deliverable'))

@archimate_layer_nav_bp.route('/implementation/events')
@login_required
def implementation_events():
    """Navigate to Implementation Events."""
    return redirect(url_for('archimate.composer_page', layer='implementation', element_type='implementation_event'))

@archimate_layer_nav_bp.route('/implementation/plateaus')
@login_required
def implementation_plateaus():
    """Navigate to Plateaus."""
    return redirect(url_for('archimate.composer_page', layer='implementation', element_type='plateau'))
