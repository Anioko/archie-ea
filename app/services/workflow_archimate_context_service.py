"""WorkflowArchiMateContextService — bridges EA workflow instances with ArchiMate elements."""

from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
from app.models.workflow_models import EAWorkflowInstance
from app import db


class WorkflowArchiMateContextService:

    def get_instance_elements(self, instance_id: int) -> list:
        """Return ArchiMate elements linked to a workflow instance via junction table.

        Falls back to legacy context JSON if the junction table has no rows for this instance,
        ensuring backward compatibility with pre-EAW-001 workflow runs.
        """
        try:
            # Primary path: query junction table (EAW-001)
            rows = db.session.execute(  # tenant-filtered: scoped via parent FK (instance_id)
                db.text(
                    "SELECT ae.id, ae.name, ae.type, ae.layer, w.element_role, w.adm_phase "
                    "FROM workflow_instance_archimate_elements w "
                    "JOIN archimate_elements ae ON ae.id = w.element_id "
                    "WHERE w.instance_id = :iid "
                    "ORDER BY w.adm_phase, ae.type, ae.name"
                ),
                {"iid": instance_id},
            ).fetchall()

            if rows:
                return [
                    {
                        "id": r[0],
                        "name": r[1],
                        "type": r[2],
                        "layer": r[3],
                        "element_role": r[4],
                        "adm_phase": r[5],
                    }
                    for r in rows
                ]

            # Fallback: legacy context JSON (pre-EAW-001 instances)
            instance = EAWorkflowInstance.query.get(instance_id)
            if not instance or not instance.context:
                return []
            context = instance.context or {}
            element_ids = context.get("archimate_scope", context.get("element_ids", []))
            app_ids = context.get("app_ids", [])
            if not element_ids and not app_ids:
                return []
            if element_ids:
                elements = ArchiMateElement.query.filter(ArchiMateElement.id.in_(element_ids)).all()
            else:
                elements = ArchiMateElement.query.filter(
                    ArchiMateElement.application_component_id.in_(app_ids)
                ).all()
            return [{"id": e.id, "name": e.name, "type": e.type, "layer": e.layer,
                     "element_role": "output", "adm_phase": None} for e in elements]
        except Exception:
            return []

    def get_phase_elements(self, phase_code: str) -> list:
        """Return all ArchiMate elements tagged with this ADM phase."""
        try:
            # properties is db.Text (JSON string); use LIKE for phase match, plateau as fallback
            elements = ArchiMateElement.query.filter(
                db.or_(
                    ArchiMateElement.properties.like('%"adm_phase": "' + phase_code + '"%'),
                    ArchiMateElement.plateau == phase_code,
                )
            ).all()
            return [
                {"id": e.id, "name": e.name, "type": e.type, "layer": e.layer, "plateau": e.plateau}
                for e in elements
            ]
        except Exception:
            return []

    def persist_derived_element(
        self,
        phase_code: str,
        name: str,
        element_type: str,
        layer: str,
        source_instance_id: int = None,
        element_role: str = "output",
        step_id: str = None,
    ) -> int:
        """Create a new ArchiMate element derived from an ADM phase workflow.

        Also inserts a row in workflow_instance_archimate_elements (EAW-001)
        so that get_instance_elements() can retrieve it via proper SQL join.
        """
        try:
            import json

            props = {"adm_phase": phase_code}
            if source_instance_id:
                props["source_workflow_instance_id"] = source_instance_id
            el = ArchiMateElement(
                name=name,
                type=element_type,
                layer=layer,
                plateau="Target",
                scope="enterprise",
                properties=json.dumps(props),
            )
            db.session.add(el)
            db.session.flush()  # obtain el.id before commit

            if source_instance_id:
                db.session.execute(  # tenant-filtered: scoped via parent FK (instance_id)
                    db.text(
                        "INSERT INTO workflow_instance_archimate_elements "
                        "(instance_id, element_id, element_role, adm_phase, step_id) "
                        "VALUES (:iid, :eid, :role, :phase, :step) "
                        "ON CONFLICT (instance_id, element_id, element_role) DO NOTHING"
                    ),
                    {
                        "iid": source_instance_id,
                        "eid": el.id,
                        "role": element_role,
                        "phase": phase_code,
                        "step": step_id,
                    },
                )

            db.session.commit()
            return el.id
        except Exception:
            db.session.rollback()
            return None

    def get_cross_phase_lineage(self, element_id: int) -> dict:
        """Trace upstream/downstream phase derivation chain (max 3 hops)."""
        try:
            element = ArchiMateElement.query.get(element_id)
            if not element:
                return {"element_id": element_id, "error": "not_found"}

            def get_phase(e):
                import json

                raw = e.properties
                if not raw:
                    return None
                try:
                    props = json.loads(raw) if isinstance(raw, str) else raw
                    return props.get("adm_phase") if isinstance(props, dict) else None
                except Exception:
                    return None

            upstream_rels = ArchiMateRelationship.query.filter_by(target_id=element_id).limit(20).all()
            upstream = []
            for r in upstream_rels:
                src = ArchiMateElement.query.get(r.source_id)
                if src:
                    upstream.append(
                        {
                            "element_id": src.id,
                            "name": src.name,
                            "type": src.type,
                            "phase": get_phase(src),
                            "relationship_type": r.type,
                        }
                    )

            downstream_rels = ArchiMateRelationship.query.filter_by(source_id=element_id).limit(20).all()
            downstream = []
            for r in downstream_rels:
                tgt = ArchiMateElement.query.get(r.target_id)
                if tgt:
                    downstream.append(
                        {
                            "element_id": tgt.id,
                            "name": tgt.name,
                            "type": tgt.type,
                            "phase": get_phase(tgt),
                            "relationship_type": r.type,
                        }
                    )

            return {
                "element_id": element_id,
                "element_name": element.name,
                "element_type": element.type,
                "origin_phase": get_phase(element),
                "upstream": upstream,
                "downstream": downstream,
            }
        except Exception:
            return {"element_id": element_id, "upstream": [], "downstream": []}
