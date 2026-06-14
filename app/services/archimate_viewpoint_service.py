"""
ArchiMate 3.2 Role-based Viewpoint Service

Provides 16 standard viewpoints mapped to architect roles for filtering
elements in the CRUD dashboard, model viewer, and Composer.

Invariants enforced by get_viewpoint_data():
1. Scope required — no solution_id returns scope_required flag
2. Element type filtering via allowed_types
3. Relationship type filtering via allowed_relationships
4. Relationships with hidden endpoints are hidden
"""

import logging

logger = logging.getLogger(__name__)


def _normalize_rel_type(rel_type):
    """Normalize relationship type for comparison.

    DB has mixed formats: 'serving', 'ServingRelationship', 'Realization'.
    Viewpoint definitions use lowercase: 'serving', 'realization'.
    """
    if not rel_type:
        return 'association'
    t = rel_type.lower()
    if t.endswith('relationship'):
        t = t[:-len('relationship')]
    return t


STANDARD_VIEWPOINTS = {
    'basic': {
        'name': 'Basic',
        'description': 'Shows all elements and relationships',
        'layers': ['Business', 'Application', 'Technology', 'Strategy', 'Motivation', 'Implementation', 'Physical'],
        'element_types': [],  # empty = all types
        'allowed_relationships': [],  # empty = all types
        'roles': ['Enterprise', 'Business', 'Application', 'Data', 'Integrations', 'Technical', 'Technology'],
        'category': 'basic',
    },
    'layered': {
        'name': 'Layered',
        'description': 'All elements organised in horizontal layer bands: strategy, motivation, business, '
                       'application, technology, physical, implementation',
        'layers': ['Strategy', 'Motivation', 'Business', 'Application', 'Technology', 'Physical', 'Implementation'],
        'layer_order': ['strategy', 'motivation', 'business', 'application', 'technology', 'physical',
                        'implementation'],
        'element_types': [],  # all types, grouped by layer
        'allowed_relationships': [],
        'roles': ['Enterprise'],
        'category': 'composite',
    },
    'stakeholder': {
        'name': 'Stakeholder',
        'description': 'Stakeholder → Driver → Goal → Assessment motivation chain',
        'layers': ['Motivation'],
        'element_types': ['Stakeholder', 'Driver', 'Goal', 'Assessment'],
        'allowed_relationships': ['association', 'influence', 'realization', 'aggregation', 'composition'],
        'roles': ['Enterprise', 'Business'],
        'category': 'motivation',
    },
    'actor_cooperation': {
        'name': 'Actor Cooperation',
        'description': 'Shows business actors, roles, and collaborations',
        'layers': ['Business'],
        'element_types': ['BusinessActor', 'BusinessRole', 'BusinessCollaboration', 'BusinessInterface'],
        'allowed_relationships': ['composition', 'aggregation', 'assignment', 'association'],
        'roles': ['Business', 'Enterprise'],
        'category': 'basic',
    },
    'business_process': {
        'name': 'Business Process Cooperation',
        'description': 'Shows business processes, functions, and services',
        'layers': ['Business'],
        'element_types': ['BusinessProcess', 'BusinessFunction', 'BusinessEvent', 'BusinessService', 'BusinessObject'],
        'allowed_relationships': ['triggering', 'flow', 'access', 'serving', 'realization', 'assignment',
                                  'composition', 'aggregation'],
        'roles': ['Business', 'Enterprise'],
        'category': 'basic',
    },
    'application_usage': {
        'name': 'Application Usage',
        'description': 'Shows how applications support business processes',
        'layers': ['Business', 'Application'],
        'element_types': ['BusinessProcess', 'BusinessFunction', 'BusinessService', 'ApplicationComponent',
                          'ApplicationService', 'ApplicationInterface', 'DataObject'],
        'allowed_relationships': ['serving', 'access', 'realization', 'flow', 'triggering'],
        'roles': ['Application', 'Integrations'],
        'category': 'application',
    },
    'application_cooperation': {
        'name': 'Application Cooperation',
        'description': 'Shows relationships between application components',
        'layers': ['Application'],
        'element_types': ['ApplicationComponent', 'ApplicationInterface', 'ApplicationService',
                          'ApplicationCollaboration', 'DataObject'],
        'allowed_relationships': ['serving', 'flow', 'realization', 'composition', 'aggregation',
                                  'triggering', 'access'],
        'roles': ['Application', 'Integrations'],
        'category': 'application',
    },
    'technology': {
        'name': 'Technology',
        'description': 'Shows the technology infrastructure',
        'layers': ['Technology'],
        'element_types': ['Node', 'Device', 'SystemSoftware', 'TechnologyService', 'TechnologyInterface',
                          'Path', 'CommunicationNetwork', 'Artifact'],
        'allowed_relationships': ['composition', 'aggregation', 'assignment', 'serving', 'realization', 'flow'],
        'roles': ['Technical', 'Technology'],
        'category': 'technology',
    },
    'technology_usage': {
        'name': 'Technology Usage',
        'description': 'Shows how technology supports applications',
        'layers': ['Application', 'Technology'],
        'element_types': ['ApplicationComponent', 'ApplicationService', 'Node', 'Device', 'SystemSoftware',
                          'TechnologyService', 'TechnologyInterface', 'Artifact'],
        'allowed_relationships': ['serving', 'assignment', 'realization', 'access'],
        'roles': ['Technical', 'Technology', 'Application'],
        'category': 'technology',
    },
    'implementation_deployment': {
        'name': 'Implementation & Deployment',
        'description': 'Shows deployment of application components on technology',
        'layers': ['Application', 'Technology', 'Implementation'],
        'element_types': ['ApplicationComponent', 'Node', 'Device', 'SystemSoftware', 'Artifact',
                          'WorkPackage', 'Deliverable'],
        'allowed_relationships': ['association', 'realization', 'triggering', 'composition', 'aggregation',
                                  'assignment'],
        'roles': ['Technical', 'Technology'],
        'category': 'implementation',
    },
    'information_structure': {
        'name': 'Information Structure',
        'description': 'Shows the structure of information used by the enterprise',
        'layers': ['Business', 'Application'],
        'element_types': ['BusinessObject', 'DataObject', 'Representation', 'Contract'],
        'allowed_relationships': ['composition', 'aggregation', 'association', 'realization', 'access'],
        'roles': ['Data', 'Business'],
        'category': 'information',
    },
    'service_realization': {
        'name': 'Service Realization',
        'description': 'Shows how services are realized by underlying components',
        'layers': ['Business', 'Application', 'Technology'],
        'element_types': ['BusinessService', 'BusinessProcess', 'ApplicationService', 'ApplicationComponent',
                          'TechnologyService', 'Node'],
        'allowed_relationships': ['realization', 'serving', 'composition', 'aggregation', 'access'],
        'roles': ['Application', 'Technical'],
        'category': 'service',
    },
    'motivation': {
        'name': 'Motivation',
        'description': 'Shows drivers, goals, principles, and requirements',
        'layers': ['Motivation'],
        'element_types': ['Stakeholder', 'Driver', 'Assessment', 'Goal', 'Outcome', 'Principle',
                          'Requirement', 'Constraint'],
        'allowed_relationships': ['association', 'influence', 'realization', 'aggregation', 'composition'],
        'roles': ['Enterprise', 'Business'],
        'category': 'motivation',
    },
    'strategy': {
        'name': 'Strategy',
        'description': 'Shows strategic capabilities and courses of action',
        'layers': ['Strategy', 'Business'],
        'element_types': ['Resource', 'Capability', 'CourseOfAction', 'ValueStream',
                          'BusinessProcess', 'BusinessFunction'],
        'allowed_relationships': ['realization', 'association', 'assignment', 'triggering', 'flow',
                                  'composition', 'aggregation', 'influence'],
        'roles': ['Enterprise'],
        'category': 'strategy',
    },
    'capability': {
        'name': 'Capability Map',
        'description': 'Shows the capability landscape of the enterprise',
        'layers': ['Strategy'],
        'element_types': ['Capability', 'Resource', 'CourseOfAction'],
        'allowed_relationships': ['composition', 'aggregation', 'assignment', 'realization', 'serving'],
        'roles': ['Enterprise', 'Business'],
        'category': 'strategy',
    },
    'migration': {
        'name': 'Migration & Implementation',
        'description': 'Shows work packages, plateaus, and gaps for migration',
        'layers': ['Implementation'],
        'element_types': ['WorkPackage', 'Deliverable', 'Plateau', 'Gap', 'ImplementationEvent'],
        'allowed_relationships': ['association', 'triggering', 'realization', 'composition', 'aggregation'],
        'roles': ['Enterprise', 'Technical'],
        'category': 'implementation',
    },
}

ROLE_DEFAULT_VIEWPOINT = {
    'Enterprise': 'strategy',
    'Business': 'business_process',
    'Application': 'application_usage',
    'Data': 'information_structure',
    'Integrations': 'application_cooperation',
    'Technical': 'technology_usage',
    'Technology': 'technology',
}


class ArchiMateViewpointService:
    """Service for role-based ArchiMate viewpoint filtering."""

    def get_viewpoints(self) -> dict:
        return STANDARD_VIEWPOINTS

    def get_viewpoint(self, key: str) -> dict:
        return STANDARD_VIEWPOINTS.get(key, STANDARD_VIEWPOINTS['basic'])

    def get_default_for_role(self, role: str) -> str:
        return ROLE_DEFAULT_VIEWPOINT.get(role, 'basic')

    def filter_elements_by_viewpoint(self, elements: list, viewpoint_key: str) -> list:
        vp = self.get_viewpoint(viewpoint_key)
        layers = [l.lower() for l in vp.get('layers', [])]
        types = vp.get('element_types', [])
        return [e for e in elements
                if (not layers or (e.get('layer') or '').lower() in layers)
                and (not types or e.get('element_type') in types)]


# ── SA-007 module-level helpers ───────────────────────────────────────────────

def get_available_viewpoints() -> list:
    """Return list of all viewpoint definitions for the SA-007 UI."""
    result = []
    for vp_id, vp in STANDARD_VIEWPOINTS.items():
        result.append({
            'id': vp_id,
            'name': vp['name'],
            'description': vp.get('description', ''),
            'layers': vp.get('layers', []),
            'element_types': vp.get('element_types', []),
            'category': vp.get('category', 'other'),
        })
    return result


def get_viewpoint_counts(solution_id: int) -> dict:
    """Return element counts per viewpoint for a given solution.

    Keys match STANDARD_VIEWPOINTS keys (used by dropdown template).
    Returns: {'application_cooperation': 12, 'motivation': 15, ...}
    """
    if not solution_id:
        return {}

    try:
        from app.models.archimate_core import ArchiMateElement
        from app.models.solution_models import SolutionArchiMateElement
        from app import db

        # Get all element IDs for this solution
        junctions = SolutionArchiMateElement.query.filter_by(solution_id=solution_id).all()
        element_ids = [j.element_id for j in junctions if j.element_id]

        if not element_ids:
            try:
                from app.models.archimate_core import ArchitectureModel
                sol_arch = ArchitectureModel.query.filter_by(solution_id=solution_id).first()
                if sol_arch:
                    element_ids = [e.id for e in ArchiMateElement.query.filter_by(
                        architecture_id=sol_arch.id).all()]
            except Exception as e:
                logger.warning('ArchitectureModel fallback failed in viewpoint counts: %s', e)

        if not element_ids:
            return {vp_id: 0 for vp_id in STANDARD_VIEWPOINTS}

        # Single query: get (id, type) for all solution elements
        elements_with_types = ArchiMateElement.query.filter(
            ArchiMateElement.id.in_(element_ids)
        ).with_entities(ArchiMateElement.id, ArchiMateElement.type).all()

        # Count matching elements per viewpoint
        counts = {}
        for vp_id, vp in STANDARD_VIEWPOINTS.items():
            allowed = set(vp.get('element_types', []))
            if not allowed:  # empty = wildcard
                counts[vp_id] = len(elements_with_types)
            else:
                counts[vp_id] = sum(1 for _, t in elements_with_types if t in allowed)
        return counts
    except Exception as e:
        logger.warning('Failed to compute viewpoint counts: %s', e)
        return {}


def get_viewpoint_data(viewpoint_id: str, solution_id: int = None) -> dict:
    """Return elements filtered for this viewpoint, grouped for layout.

    Enforces 4 invariants:
    1. Scope required — no solution_id returns scope_required flag
    2. Element type filtering via viewpoint's element_types
    3. Relationship type filtering via viewpoint's allowed_relationships
    4. Relationships with hidden endpoints are hidden (no dangling arrows)
    """
    vp = STANDARD_VIEWPOINTS.get(viewpoint_id, STANDARD_VIEWPOINTS['basic'])
    layers = [la.lower() for la in vp.get('layers', [])]
    allowed_types = vp.get('element_types', [])
    allowed_rels = set(vp.get('allowed_relationships', []))

    # ── Invariant 1: Scope required ──
    if not solution_id:
        return {
            'viewpoint_id': viewpoint_id,
            'viewpoint_name': vp['name'],
            'scope_required': True,
            'elements': [],
            'relationships': [],
            'total': 0,
            'layer_order': vp.get('layer_order', layers or ['business']),
            'groups': {},
        }

    serialised = []
    relationships_out = []

    try:
        from app.models.archimate_core import ArchiMateElement
        from app import db

        # Get solution's element IDs (junction + fallback)
        from app.models.solution_models import SolutionArchiMateElement
        junctions = (
            SolutionArchiMateElement.query
            .filter_by(solution_id=solution_id)
            .all()
        )
        element_ids = [j.element_id for j in junctions if j.element_id]

        # Fallback: if junction is empty, try ArchitectureModel path
        if not element_ids:
            try:
                from app.models.archimate_core import ArchitectureModel
                sol_arch = ArchitectureModel.query.filter_by(solution_id=solution_id).first()
                if sol_arch:
                    arch_elements = ArchiMateElement.query.filter_by(architecture_id=sol_arch.id).all()
                    element_ids = [e.id for e in arch_elements]
                    logger.info('Solution %s: loaded %d elements via ArchitectureModel fallback', solution_id, len(element_ids))
            except Exception as e:
                logger.warning('ArchitectureModel fallback failed for solution %s: %s', solution_id, e)

        if element_ids:
            # ── Invariant 2: Element type filtering ──
            query = ArchiMateElement.query.filter(ArchiMateElement.id.in_(element_ids))
            if allowed_types:
                query = query.filter(ArchiMateElement.type.in_(allowed_types))
            elements = query.limit(500).all()
        else:
            elements = []

        # Build FILTERED element ID set (for Invariant 4 — hidden endpoints)
        filtered_ids = set(e.id for e in elements)

        serialised = [
            {
                'id': e.id,
                'name': e.name,
                'type': e.type or '',
                'layer': (e.layer or '').lower(),
                'description': e.description or '',
            }
            for e in elements
        ]

        # Query relationships from BOTH tables
        if element_ids:
            raw_rels = []
            try:
                from app.models.archimate_core import ArchiMateRelationship
                user_rels = (
                    ArchiMateRelationship.query
                    .filter(
                        ArchiMateRelationship.source_id.in_(element_ids),
                        ArchiMateRelationship.target_id.in_(element_ids),
                    )
                    .all()
                )
                for r in user_rels:
                    raw_rels.append({
                        'id': r.id,
                        'source_id': r.source_id,
                        'target_id': r.target_id,
                        'type': _normalize_rel_type(r.type),
                    })
            except Exception as e:
                logger.warning('Failed to load user relationships for solution %s: %s', solution_id, e)

            try:
                from app.models.architecture_inference_relationship import ArchitectureInferenceRelationship
                inf_rels = (
                    ArchitectureInferenceRelationship.query
                    .filter(
                        ArchitectureInferenceRelationship.source_id.in_(element_ids),
                        ArchitectureInferenceRelationship.target_id.in_(element_ids),
                    )
                    .all()
                )
                existing_pairs = {(r['source_id'], r['target_id'], r['type']) for r in raw_rels}
                for r in inf_rels:
                    rel_type = _normalize_rel_type(r.rel_type)
                    key = (r.source_id, r.target_id, rel_type)
                    if key not in existing_pairs:
                        raw_rels.append({
                            'id': r.id,
                            'source_id': r.source_id,
                            'target_id': r.target_id,
                            'type': rel_type,
                        })
                        existing_pairs.add(key)
            except Exception as e:
                logger.warning('Failed to load inference relationships for solution %s: %s', solution_id, e)

            # ── Invariant 3: Relationship type filtering ──
            # ── Invariant 4: Hide relationships with hidden endpoints ──
            for r in raw_rels:
                if r['source_id'] not in filtered_ids or r['target_id'] not in filtered_ids:
                    continue
                if allowed_rels and r['type'] not in allowed_rels:
                    continue
                relationships_out.append(r)

    except Exception:  # noqa: BLE001 — DB may not be initialised in fast-init
        serialised = []

    # Group by layer for the layered viewpoint
    grouped: dict = {}
    layer_order = vp.get('layer_order', layers or ['business'])
    for layer in layer_order:
        grouped[layer] = [el for el in serialised if el['layer'] == layer]
    for el in serialised:
        if el['layer'] not in grouped:
            grouped[el['layer']] = grouped.get(el['layer'], []) + [el]

    return {
        'viewpoint_id': viewpoint_id,
        'viewpoint_name': vp['name'],
        'layer_order': layer_order,
        'groups': grouped,
        'elements': serialised,
        'relationships': relationships_out,
        'total': len(serialised),
    }
