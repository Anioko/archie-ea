"""Canonical prefills for TOGAF deliverable authoring."""

import json
from typing import Any, Mapping

from app.services.togaf_deliverable_template_service import togaf_deliverable_template_service


def _attr(obj, name, default=None):  # model-safety-ok
    """Safe attribute access for optional context objects (not necessarily ORM models)."""
    if obj is None:
        return default
    return obj.__dict__.get(name, default) if hasattr(obj, "__dict__") else default  # model-safety-ok


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_listish(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_normalize_text(item) for item in value if _normalize_text(item)]
    if isinstance(value, dict):
        return [f"{_normalize_text(key)}: {_normalize_text(item)}" for key, item in value.items() if _normalize_text(key) and _normalize_text(item)]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("[") or raw.startswith("{"):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                return _normalize_listish(parsed)
        parts = []
        normalized = raw.replace(";", ",").replace("\r", "\n")
        for chunk in normalized.split("\n"):
            for part in chunk.split(","):
                text = part.strip()
                if text:
                    parts.append(text)
        return parts
    return [_normalize_text(value)] if _normalize_text(value) else []


def _join_items(items: list[str], *, limit: int | None = None) -> str:
    usable = [item for item in items if item]
    if limit is not None:
        usable = usable[:limit]
    return "; ".join(usable)


class TOGAFDeliverablePrefillService:
    """Build prefilled TOGAF content from canonical workflow and application context."""

    @staticmethod
    def list_templates() -> list[dict[str, Any]]:
        return togaf_deliverable_template_service.list_templates()

    def build_architecture_vision_content(
        self,
        *,
        workflow_definition: Any | None = None,
        application: Any | None = None,
        extra_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context_type = "application" if application else "workflow_definition"
        context_id = _attr(application, "id", None) or _attr(workflow_definition, "id", None)
        content = togaf_deliverable_template_service.build_initial_content(
            "architecture_vision",
            context_type=context_type,
            context_id=context_id,
        )
        source_refs: list[dict[str, Any]] = []
        sections = {section["key"]: section for section in content["sections"]}
        extras = dict(extra_context or {})

        workflow_ref_id = None
        workflow_steps_ref_id = None
        if workflow_definition is not None:
            workflow_ref_id = self._add_source_ref(
                source_refs,
                source_type="workflow_definition",
                source_id=_attr(workflow_definition, "id", None),
                label=_attr(workflow_definition, "workflow_name", "Workflow Definition"),
                metadata={"workflow_code": _attr(workflow_definition, "workflow_code", None)},
            )
            workflow_steps_ref_id = self._add_source_ref(
                source_refs,
                source_type="workflow_steps",
                source_id=_attr(workflow_definition, "id", None),
                label=f"{_attr(workflow_definition, 'workflow_name', 'Workflow')} step plan",
                metadata={"step_names": self._workflow_step_names(workflow_definition)},
            )

        app_profile_ref_id = None
        app_owner_ref_id = None
        app_risk_ref_id = None
        if application is not None:
            app_profile_ref_id = self._add_source_ref(
                source_refs,
                source_type="application_component",
                source_id=_attr(application, "id", None),
                label=_attr(application, "name", "Application"),
                metadata={"business_domain": _attr(application, "business_domain", None)},
            )
            app_owner_ref_id = self._add_source_ref(
                source_refs,
                source_type="application_ownership",
                source_id=_attr(application, "id", None),
                label=f"{_attr(application, 'name', 'Application')} ownership",
                metadata=self._owner_map(application),
            )
            app_risk_ref_id = self._add_source_ref(
                source_refs,
                source_type="application_governance",
                source_id=_attr(application, "id", None),
                label=f"{_attr(application, 'name', 'Application')} governance",
                metadata={"compliance_requirements": _normalize_listish(_attr(application, "compliance_requirements", None))},
            )

        sections["vision_statement"] = self._prefill_section(
            sections["vision_statement"],
            fields={
                "summary": self._vision_summary(workflow_definition, application),
                "business_value": self._business_value(application),
            },
            narrative=self._vision_summary(workflow_definition, application),
            source_ref_ids=[workflow_ref_id, app_profile_ref_id],
        )
        sections["scope"] = self._prefill_section(
            sections["scope"],
            fields={
                "in_scope": self._scope_in(application, workflow_definition),
                "out_of_scope": _join_items(_normalize_listish((extras.get("solution_summary") or {}).get("out_of_scope"))) or "Detailed implementation design; Final approval workflow",
                "assumptions": self._scope_assumptions(application, workflow_definition),
            },
            narrative=self._scope_in(application, workflow_definition),
            source_ref_ids=[workflow_ref_id, workflow_steps_ref_id, app_profile_ref_id],
        )
        sections["stakeholders"] = self._prefill_section(
            sections["stakeholders"],
            fields={
                "stakeholder_map": self._stakeholder_map(application),
                "concerns": self._stakeholder_concerns(application, workflow_definition),
            },
            narrative=self._stakeholder_concerns(application, workflow_definition),
            source_ref_ids=[app_owner_ref_id, app_risk_ref_id, workflow_steps_ref_id],
        )
        sections["drivers_goals_constraints"] = self._prefill_section(
            sections["drivers_goals_constraints"],
            fields={
                "drivers": self._drivers(application, workflow_definition),
                "goals": self._goals(application),
                "constraints": self._constraints(application),
            },
            narrative=self._drivers(application, workflow_definition),
            source_ref_ids=[app_profile_ref_id, app_risk_ref_id, workflow_ref_id],
        )
        sections["summary_views"] = self._prefill_section(
            sections["summary_views"],
            fields={
                "value_chain_view": self._value_chain_view(application),
                "solution_concept_view": self._solution_concept_view(application, workflow_definition),
            },
            narrative=self._solution_concept_view(application, workflow_definition),
            source_ref_ids=[app_profile_ref_id, workflow_steps_ref_id],
        )

        content["sections"] = list(sections.values())
        content["source_refs"] = source_refs
        return content

    @staticmethod
    def _add_source_ref(source_refs: list[dict[str, Any]], *, source_type: str, source_id: Any, label: str, metadata: Mapping[str, Any] | None = None) -> str:
        ref_id = f"src-{len(source_refs) + 1}"
        source_refs.append({"id": ref_id, "source_type": source_type, "source_id": source_id, "label": label, "metadata": dict(metadata or {})})
        return ref_id

    @staticmethod
    def _workflow_step_names(workflow_definition: Any | None) -> list[str]:
        step_names = []
        for step in _attr(workflow_definition, "steps", []) or []:
            name = _normalize_text(step.get("step_name") or step.get("name") or step.get("step_type"))
            if name:
                step_names.append(name)
        return step_names

    @staticmethod
    def _owner_map(application: Any | None) -> dict[str, str]:
        if application is None:
            return {}
        owners = {
            "application_owner": _normalize_text(_attr(application, "application_owner", None)),
            "business_owner": _normalize_text(_attr(application, "business_owner", None)),
            "technical_owner": _normalize_text(_attr(application, "technical_owner", None)),
            "technical_lead": _normalize_text(_attr(application, "technical_lead", None)),
        }
        return {key: value for key, value in owners.items() if value}

    def _prefill_section(self, section: dict[str, Any], *, fields: Mapping[str, str], narrative: str, source_ref_ids: list[str | None]) -> dict[str, Any]:
        populated_fields = {key: value for key, value in fields.items() if _normalize_text(value)}
        if not populated_fields and not _normalize_text(narrative):
            return section
        section["fields"].update(populated_fields)
        section["generated_narrative"] = _normalize_text(narrative)
        section["status"] = "prefilled"
        section["source_ref_ids"] = [ref_id for ref_id in source_ref_ids if ref_id]
        section["readiness"] = {
            "state": "prefilled_from_sources",
            "blocking_issues": [],
            "warnings": ["Review the prefilled content and confirm it still matches the intended scope."],
        }
        return section

    def _vision_summary(self, workflow_definition: Any | None, application: Any | None) -> str:
        items = [
            _normalize_text(_attr(workflow_definition, "workflow_name", None)),
            _normalize_text(_attr(workflow_definition, "workflow_description", None)),
            _normalize_text(_attr(application, "name", None)),
            _normalize_text(_attr(application, "business_purpose", None)),
        ]
        return " ".join(item for item in items if item).strip()

    def _business_value(self, application: Any | None) -> str:
        return _join_items(
            [
                _normalize_text(_attr(application, "business_purpose", None)),
                _normalize_text(_attr(application, "strategic_importance", None)),
                _normalize_text(_attr(application, "business_value", None)),
            ],
            limit=4,
        )

    def _scope_in(self, application: Any | None, workflow_definition: Any | None) -> str:
        return _join_items(
            [
                _normalize_text(_attr(application, "name", None)),
                _normalize_text(_attr(application, "business_domain", None)),
                _normalize_text(_attr(workflow_definition, "workflow_name", None)),
                _normalize_text(_attr(workflow_definition, "adm_phase_name", None)),
            ],
            limit=5,
        )

    def _scope_assumptions(self, application: Any | None, workflow_definition: Any | None) -> str:
        return _join_items(
            [
                f"Deployment model: {_normalize_text(_attr(application, 'deployment_model', None))}" if _normalize_text(_attr(application, "deployment_model", None)) else "",
                f"Lifecycle status: {_normalize_text(_attr(application, 'lifecycle_status', None))}" if _normalize_text(_attr(application, "lifecycle_status", None)) else "",
                f"Trigger types: {_join_items(_normalize_listish(_attr(workflow_definition, 'trigger_types', None)))}" if _normalize_listish(_attr(workflow_definition, "trigger_types", None)) else "",
            ],
            limit=5,
        )

    def _stakeholder_map(self, application: Any | None) -> str:
        owners = self._owner_map(application)
        return _join_items(
            [
                f"Application Owner: {owners['application_owner']}" if owners.get("application_owner") else "",
                f"Business Owner: {owners['business_owner']}" if owners.get("business_owner") else "",
                f"Technical Owner: {owners['technical_owner']}" if owners.get("technical_owner") else "",
                f"Technical Lead: {owners['technical_lead']}" if owners.get("technical_lead") else "",
            ],
            limit=6,
        )

    def _stakeholder_concerns(self, application: Any | None, workflow_definition: Any | None) -> str:
        approval_steps = sum(1 for step in _attr(workflow_definition, "steps", []) or [] if step.get("requires_approval") or step.get("step_type") == "approval")
        return _join_items(
            [
                f"Criticality: {_normalize_text(_attr(application, 'criticality', None))}" if _normalize_text(_attr(application, "criticality", None)) else "",
                f"Data classification: {_normalize_text(_attr(application, 'data_classification', None))}" if _normalize_text(_attr(application, "data_classification", None)) else "",
                f"Approval gates: {approval_steps}" if approval_steps else "",
            ],
            limit=5,
        )

    def _drivers(self, application: Any | None, workflow_definition: Any | None) -> str:
        return _join_items(
            [
                _normalize_text(_attr(application, "business_purpose", None)),
                _normalize_text(_attr(application, "strategic_importance", None)),
                _normalize_text(_attr(application, "criticality", None)),
                _normalize_text(_attr(workflow_definition, "workflow_description", None)),
            ],
            limit=5,
        )

    def _goals(self, application: Any | None) -> str:
        return _join_items(
            [
                _normalize_text(_attr(application, "business_value", None)),
                _normalize_text(_attr(application, "strategic_importance", None)),
            ],
            limit=4,
        )

    def _constraints(self, application: Any | None) -> str:
        return _join_items(
            [
                _normalize_text(_attr(application, "deployment_model", None)),
                _normalize_text(_attr(application, "lifecycle_status", None)),
                _normalize_text(_attr(application, "integration_pattern", None)),
                _normalize_text(_attr(application, "data_classification", None)),
                *_normalize_listish(_attr(application, "compliance_requirements", None)),
            ],
            limit=6,
        )

    def _value_chain_view(self, application: Any | None) -> str:
        return _join_items(
            [
                _normalize_text(_attr(application, "business_domain", None)),
                _join_items(_normalize_listish(_attr(application, "business_functions", None)), limit=3),
            ],
            limit=4,
        )

    def _solution_concept_view(self, application: Any | None, workflow_definition: Any | None) -> str:
        return _join_items(
            [
                _normalize_text(_attr(application, "architecture_style", None)),
                _normalize_text(_attr(application, "deployment_model", None)),
                _normalize_text(_attr(application, "primary_database", None)),
                _normalize_text(_attr(application, "integration_pattern", None)),
                _normalize_text(_attr(workflow_definition, "workflow_name", None)),
            ],
            limit=5,
        )


togaf_deliverable_prefill_service = TOGAFDeliverablePrefillService()
