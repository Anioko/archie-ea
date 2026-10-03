"""
Applicability rule engine for regulatory frameworks.

Evaluates which systems (nodes, applications) are in scope for a given
regulatory framework based on rules over data classification, hosting
location, and business function.  Results are stored for audit.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models.compliance_models import ComplianceControl, RegulatoryFramework
from app.models.regulatory_change import RegulatoryChange, RegulatoryChangeImpact
from app.models.regulatory_framework import AdoptedControl, FrameworkAdoption
from app.models.technology_layer import Node

logger = logging.getLogger(__name__)


class ApplicabilityService:
    """Evaluates which elements are in scope for a regulatory framework."""

    # Framework-specific applicability rules.
    # Each rule is a dict with:
    #   field: the model attribute to check
    #   operator: 'eq', 'contains', 'in'
    #   value: the value to match
    FRAMEWORK_RULES: Dict[str, List[Dict[str, Any]]] = {
        "ISO-27001": [
            {"field": "node_type", "operator": "in",
             "value": ["Virtual Machine", "Cloud Instance", "Physical Server", "Container"]},
        ],
        "SOC-2": [
            {"field": "deployment_model", "operator": "in",
             "value": ["Cloud", "Hybrid"]},
        ],
        "DORA": [
            {"field": "compliance_tags", "operator": "contains", "value": "DORA"},
        ],
    }

    @classmethod
    def evaluate_node(cls, node: Node, framework_code: str) -> bool:
        """Return True if *node* is in scope for *framework_code*."""
        rules = cls.FRAMEWORK_RULES.get(framework_code, [])
        if not rules:
            return True  # no rules = everything in scope

        for rule in rules:
            field_val = getattr(node, rule["field"], None)
            if field_val is None:
                return False
            op = rule["operator"]
            if op == "eq" and field_val != rule["value"]:
                return False
            if op == "in" and field_val not in rule["value"]:
                return False
            if op == "contains":
                # compliance_tags is a JSON text field
                import json
                try:
                    tags = json.loads(field_val) if isinstance(field_val, str) else field_val
                except (json.JSONDecodeError, TypeError):
                    tags = []
                if rule["value"] not in tags:
                    return False
        return True

    @classmethod
    def get_in_scope_nodes(
        cls, organization_id: int, framework_code: str
    ) -> List[Dict[str, Any]]:
        """Return nodes in scope for *framework_code* within *organization_id*."""
        nodes = Node.query.filter_by(organization_id=organization_id).all()
        in_scope = []
        for node in nodes:
            if cls.evaluate_node(node, framework_code):
                in_scope.append({
                    "id": node.id,
                    "name": node.name,
                    "node_type": node.node_type,
                    "deployment_model": node.deployment_model,
                    "rule_applied": str(cls.FRAMEWORK_RULES.get(framework_code, [])),
                })
        return in_scope

    @classmethod
    def adopt_framework(
        cls, organization_id: int, framework_id: int, adopted_by_id: int
    ) -> FrameworkAdoption:
        """Adopt a framework for an organisation, copying its controls.

        Returns the new FrameworkAdoption row.
        """
        framework = RegulatoryFramework.query.get(framework_id)
        if framework is None:
            raise ValueError(f"Framework {framework_id} not found")

        existing = FrameworkAdoption.query.filter_by(
            organization_id=organization_id, framework_id=framework_id
        ).first()
        if existing:
            raise ValueError(f"Framework {framework.code} already adopted")

        adoption = FrameworkAdoption(
            organization_id=organization_id,
            scope="tenant",
            framework_id=framework_id,
            adopted_by_id=adopted_by_id,
            adopted_at=datetime.utcnow(),
            status="active",
        )
        db.session.add(adoption)
        db.session.flush()

        for control in framework.controls:
            adopted = AdoptedControl(
                organization_id=organization_id,
                scope="tenant",
                adoption_id=adoption.id,
                control_id=control.id,
                implementation_status="planned",
            )
            db.session.add(adopted)

        db.session.commit()
        return adoption

    @classmethod
    def propose_harmonization(
        cls, control_id: int, target_control_id: int, notes: str = None
    ) -> ComplianceControl:
        """Propose a cross-framework harmonisation between two controls."""
        control = ComplianceControl.query.get(control_id)
        if control is None:
            raise ValueError(f"Control {control_id} not found")
        target = ComplianceControl.query.get(target_control_id)
        if target is None:
            raise ValueError(f"Target control {target_control_id} not found")

        control.harmonized_control_id = target_control_id
        control.harmonization_status = "proposed"
        control.harmonization_notes = notes
        db.session.commit()
        return control

    @classmethod
    def confirm_harmonization(cls, control_id: int) -> ComplianceControl:
        """Confirm a proposed harmonisation."""
        control = ComplianceControl.query.get(control_id)
        if control is None:
            raise ValueError(f"Control {control_id} not found")
        if control.harmonization_status != "proposed":
            raise ValueError("Only proposed harmonisations can be confirmed")
        control.harmonization_status = "confirmed"
        db.session.commit()
        return control

    @classmethod
    def record_regulatory_change(
        cls,
        organization_id: int,
        framework_id: int,
        title: str,
        description: str,
        change_type: str = "amendment",
        effective_date: Optional[datetime] = None,
        recorded_by_id: Optional[int] = None,
    ) -> RegulatoryChange:
        """Record a regulatory amendment and compute affected elements."""
        change = RegulatoryChange(
            organization_id=organization_id,
            framework_id=framework_id,
            change_type=change_type,
            title=title,
            description=description,
            effective_date=effective_date,
            recorded_by_id=recorded_by_id,
        )
        db.session.add(change)
        db.session.flush()

        # Re-run applicability: find affected controls and element owners
        framework = RegulatoryFramework.query.get(framework_id)
        if framework:
            for control in framework.controls:
                impact = RegulatoryChangeImpact(
                    organization_id=organization_id,
                    change_id=change.id,
                    element_type="control",
                    element_id=control.id,
                    element_name=f"{control.control_code}: {control.title}",
                    impact_assessment=f"Control may be affected by regulatory change: {title}",
                )
                db.session.add(impact)

        db.session.commit()
        return change

    @classmethod
    def get_affected_elements(
        cls, change_id: int, organization_id: int
    ) -> List[RegulatoryChangeImpact]:
        """Return elements affected by a regulatory change."""
        return RegulatoryChangeImpact.query.filter_by(
            change_id=change_id, organization_id=organization_id
        ).all()