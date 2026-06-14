"""Workflow template library — pre-built patterns for the visual designer.

Each template provides a complete workflow_definition (steps + connections)
that can be loaded into the JointJS designer as a starting point. Templates
accept optional parameter overrides for entity names, fields, thresholds, etc.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


TEMPLATES: List[Dict[str, Any]] = [
    # -- Approval Flows -------------------------------------------------------
    {
        "id": "approval_flow",
        "name": "Threshold Approval",
        "category": "approval",
        "description": "Route records above a threshold for manual approval before processing.",
        "default_params": {
            "entity": "Order",
            "amount_field": "total_amount",
            "threshold": 10000,
            "approver_email": "approver@company.com",
        },
        "build": lambda p: {
            "name": f"{p['entity']} Approval Flow",
            "steps": [
                {"id": "s1", "type": "trigger", "entity": p["entity"], "event": "created",
                 "position": {"x": 100, "y": 200}},
                {"id": "s2", "type": "condition", "field": p["amount_field"], "operator": "gt",
                 "value": p["threshold"], "position": {"x": 350, "y": 200}},
                {"id": "s3", "type": "approval", "position": {"x": 600, "y": 100},
                 "properties": {"approver_role": "manager", "timeout_hours": 48}},
                {"id": "s4", "type": "email", "to": p.get("approver_email", ""),
                 "subject": f"Auto-approved: {p['entity']}", "position": {"x": 600, "y": 300}},
                {"id": "s5", "type": "update_field", "position": {"x": 850, "y": 100},
                 "properties": {"field": "status", "value": "approved"}},
            ],
            "connections": [
                {"from": "s1", "to": "s2"},
                {"from": "s2", "to": "s3", "label": "true"},
                {"from": "s2", "to": "s4", "label": "false"},
                {"from": "s3", "to": "s5"},
            ],
        },
    },
    {
        "id": "multi_stage_approval",
        "name": "Multi-Stage Approval",
        "category": "approval",
        "description": "Sequential approval through multiple levels (manager then director).",
        "default_params": {"entity": "Contract"},
        "build": lambda p: {
            "name": f"{p['entity']} Multi-Stage Approval",
            "steps": [
                {"id": "s1", "type": "trigger", "entity": p["entity"], "event": "created",
                 "position": {"x": 100, "y": 200}},
                {"id": "s2", "type": "approval", "position": {"x": 350, "y": 200},
                 "properties": {"approver_role": "manager", "timeout_hours": 24}},
                {"id": "s3", "type": "approval", "position": {"x": 600, "y": 200},
                 "properties": {"approver_role": "director", "timeout_hours": 48}},
                {"id": "s4", "type": "update_field", "position": {"x": 850, "y": 200},
                 "properties": {"field": "status", "value": "fully_approved"}},
            ],
            "connections": [
                {"from": "s1", "to": "s2"},
                {"from": "s2", "to": "s3"},
                {"from": "s3", "to": "s4"},
            ],
        },
    },
    # -- Notification Flows ----------------------------------------------------
    {
        "id": "status_notification",
        "name": "Status Change Notification",
        "category": "notification",
        "description": "Send email when a record status changes.",
        "default_params": {"entity": "Order", "status_field": "status", "recipient": "owner@company.com"},
        "build": lambda p: {
            "name": f"{p['entity']} Status Notification",
            "steps": [
                {"id": "s1", "type": "trigger", "entity": p["entity"], "event": "updated",
                 "position": {"x": 100, "y": 200}},
                {"id": "s2", "type": "email", "to": p.get("recipient", ""),
                 "subject": f"{p['entity']} status changed", "position": {"x": 350, "y": 200}},
            ],
            "connections": [{"from": "s1", "to": "s2"}],
        },
    },
    {
        "id": "escalation_notification",
        "name": "Overdue Escalation",
        "category": "notification",
        "description": "Wait for a deadline, then escalate via email if not resolved.",
        "default_params": {"entity": "Ticket", "wait_hours": 24, "escalation_email": "manager@company.com"},
        "build": lambda p: {
            "name": f"{p['entity']} Escalation",
            "steps": [
                {"id": "s1", "type": "trigger", "entity": p["entity"], "event": "created",
                 "position": {"x": 100, "y": 200}},
                {"id": "s2", "type": "delay", "position": {"x": 350, "y": 200},
                 "properties": {"amount": p.get("wait_hours", 24), "unit": "hours"}},
                {"id": "s3", "type": "condition", "field": "status", "operator": "neq",
                 "value": "resolved", "position": {"x": 600, "y": 200}},
                {"id": "s4", "type": "email", "to": p.get("escalation_email", ""),
                 "subject": f"Overdue {p['entity']} escalation", "position": {"x": 850, "y": 100}},
            ],
            "connections": [
                {"from": "s1", "to": "s2"},
                {"from": "s2", "to": "s3"},
                {"from": "s3", "to": "s4", "label": "true"},
            ],
        },
    },
    # -- Data Management -------------------------------------------------------
    {
        "id": "data_validation",
        "name": "Create with Validation",
        "category": "data_management",
        "description": "Validate fields on creation, block invalid records, notify on success.",
        "default_params": {"entity": "Customer", "required_field": "email"},
        "build": lambda p: {
            "name": f"{p['entity']} Validation Flow",
            "steps": [
                {"id": "s1", "type": "trigger", "entity": p["entity"], "event": "created",
                 "position": {"x": 100, "y": 200}},
                {"id": "s2", "type": "run_rule", "position": {"x": 350, "y": 200},
                 "properties": {"rule_name": f"validate_{p['entity'].lower()}"}},
                {"id": "s3", "type": "email", "to": "admin@company.com",
                 "subject": f"New {p['entity']} created", "position": {"x": 600, "y": 200}},
            ],
            "connections": [
                {"from": "s1", "to": "s2"},
                {"from": "s2", "to": "s3"},
            ],
        },
    },
    {
        "id": "sync_external",
        "name": "Sync to External System",
        "category": "data_management",
        "description": "On record change, call an external API to sync data.",
        "default_params": {"entity": "Product", "api_url": "https://external.api.com/sync"},
        "build": lambda p: {
            "name": f"{p['entity']} External Sync",
            "steps": [
                {"id": "s1", "type": "trigger", "entity": p["entity"], "event": "updated",
                 "position": {"x": 100, "y": 200}},
                {"id": "s2", "type": "call_api", "position": {"x": 350, "y": 200},
                 "properties": {"url": p.get("api_url", ""), "method": "POST"}},
            ],
            "connections": [{"from": "s1", "to": "s2"}],
        },
    },
    # -- Integration -----------------------------------------------------------
    {
        "id": "webhook_processor",
        "name": "Inbound Webhook Processor",
        "category": "integration",
        "description": "Receive external webhook, validate, create record, notify.",
        "default_params": {"entity": "Lead"},
        "build": lambda p: {
            "name": f"Inbound {p['entity']} Webhook",
            "steps": [
                {"id": "s1", "type": "trigger", "entity": p["entity"], "event": "webhook",
                 "position": {"x": 100, "y": 200}},
                {"id": "s2", "type": "run_rule", "position": {"x": 350, "y": 200},
                 "properties": {"rule_name": f"validate_{p['entity'].lower()}"}},
                {"id": "s3", "type": "create_record", "position": {"x": 600, "y": 200},
                 "properties": {"url": f"/api/{p['entity'].lower()}s"}},
                {"id": "s4", "type": "email", "to": "sales@company.com",
                 "subject": f"New {p['entity']} received", "position": {"x": 850, "y": 200}},
            ],
            "connections": [
                {"from": "s1", "to": "s2"},
                {"from": "s2", "to": "s3"},
                {"from": "s3", "to": "s4"},
            ],
        },
    },
    {
        "id": "scheduled_report",
        "name": "Scheduled Data Report",
        "category": "integration",
        "description": "Periodically call API and email results.",
        "default_params": {"entity": "Report", "api_url": "/api/reports/generate", "recipient": "admin@company.com"},
        "build": lambda p: {
            "name": f"Scheduled {p['entity']}",
            "steps": [
                {"id": "s1", "type": "trigger", "entity": p["entity"], "event": "webhook",
                 "position": {"x": 100, "y": 200}},
                {"id": "s2", "type": "call_api", "position": {"x": 350, "y": 200},
                 "properties": {"url": p.get("api_url", ""), "method": "GET"}},
                {"id": "s3", "type": "email", "to": p.get("recipient", ""),
                 "subject": f"{p['entity']} ready", "position": {"x": 600, "y": 200}},
            ],
            "connections": [
                {"from": "s1", "to": "s2"},
                {"from": "s2", "to": "s3"},
            ],
        },
    },
]

_TEMPLATE_INDEX = {t["id"]: t for t in TEMPLATES}


class WorkflowTemplateLibrary:
    """Pre-built workflow patterns for the visual designer."""

    def list_templates(self) -> List[Dict[str, Any]]:
        """Return all templates (without build functions)."""
        return [
            {k: v for k, v in t.items() if k not in ("build", "default_params")}
            for t in TEMPLATES
        ]

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Return a single template by ID, or None."""
        t = _TEMPLATE_INDEX.get(template_id)
        if t is None:
            return None
        return {k: v for k, v in t.items() if k not in ("build", "default_params")}

    def instantiate(self, template_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Instantiate a template with parameters, returning a workflow definition.

        Args:
            template_id: Template to instantiate.
            params: Parameter overrides. Missing params use template defaults.

        Returns:
            Workflow definition dict (steps + connections), ready for the designer.

        Raises:
            ValueError: If template_id is unknown.
        """
        t = _TEMPLATE_INDEX.get(template_id)
        if t is None:
            raise ValueError(f"Unknown template: {template_id}")

        merged = {**t.get("default_params", {}), **(params or {})}
        return t["build"](merged)
