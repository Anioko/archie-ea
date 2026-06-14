"""RuleTemplateEngine -- parameterised business rule templates.

Provides a catalog of ~30 rule templates across 7 categories. Templates are
instantiated with BA-provided parameters to produce a validated rule definition
(the shared JSON schema from rule_schema.py).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# -- Hint tables: field name patterns that suggest specific templates ----------

_AMOUNT_HINTS = frozenset({"amount", "total", "price", "cost", "value", "salary", "budget", "revenue"})
_STATUS_HINTS = frozenset({"status", "state", "phase", "stage"})
_EMAIL_HINTS = frozenset({"email", "mail"})
_DATE_HINTS = frozenset({"date", "deadline", "due", "expires", "created_at", "updated_at"})
_BOOL_HINTS = frozenset({"is_active", "is_approved", "is_verified", "enabled", "active"})


# -- Template definitions ------------------------------------------------------
# 30 templates across 7 categories: approval(4), notification(5), validation(6),
# scheduled(4), computed(4), access_control(4), integration(3)

TEMPLATES: List[Dict[str, Any]] = [
    # -- Approval (4) ----------------------------------------------------------
    {
        "id": "threshold_approval",
        "name": "Threshold Approval",
        "category": "approval",
        "description": "Block creation when a numeric field exceeds a threshold, requiring manager approval.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True, "description": "Entity name (e.g. Order)"},
            {"name": "field", "type": "string", "required": True, "description": "Numeric field to check"},
            {"name": "threshold", "type": "number", "required": True, "description": "Threshold value"},
            {"name": "message", "type": "string", "required": False, "description": "Rejection message"},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [{"type": "field_check", "field": p["field"], "operator": "gt", "value": p["threshold"]}],
            "actions": [{"type": "block", "details": {"message": p.get("message", f"{p['field']} exceeds {p['threshold']}")}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _AMOUNT_HINTS,
    },
    {
        "id": "multi_level_approval",
        "name": "Multi-Level Approval",
        "category": "approval",
        "description": "Route for approval through multiple levels based on value tiers.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "field", "type": "string", "required": True},
            {"name": "tier1_threshold", "type": "number", "required": True},
            {"name": "tier2_threshold", "type": "number", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [{"type": "field_check", "field": p["field"], "operator": "gt", "value": p["tier1_threshold"]}],
            "actions": [
                {"type": "block", "details": {"message": f"{p['field']} over {p['tier1_threshold']} requires L1 approval; over {p['tier2_threshold']} requires L2"}},
                {"type": "assign_role", "details": {"role": "approver_l1", "tier2_threshold": p["tier2_threshold"], "tier2_role": "approver_l2"}},
            ],
            "side_effects": [
                {"type": "create_role", "details": {"role_name": "approver_l1"}},
                {"type": "create_role", "details": {"role_name": "approver_l2"}},
            ],
            "confidence": 1.0,
        },
        "hint_fields": _AMOUNT_HINTS,
    },
    {
        "id": "peer_review",
        "name": "Peer Review",
        "category": "approval",
        "description": "Require peer review before a record can be finalized.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "status_field", "type": "string", "required": False},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_update", "entity": p["entity"]},
            "conditions": [{"type": "field_check", "field": p.get("status_field", "status"), "operator": "eq", "value": "pending_review"}],
            "actions": [{"type": "block", "details": {"message": "Record must be peer-reviewed before finalization"}}],
            "side_effects": [{"type": "create_role", "details": {"role_name": "peer_reviewer"}}],
            "confidence": 1.0,
        },
        "hint_fields": _STATUS_HINTS,
    },
    {
        "id": "time_bound_approval",
        "name": "Time-Bound Approval",
        "category": "approval",
        "description": "Auto-escalate if approval is not completed within a time window.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "hours", "type": "number", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "on_schedule", "entity": p["entity"]},
            "conditions": [{"type": "temporal", "field": "created_at", "operator": "gt", "value": p["hours"], "unit": "hours"}],
            "actions": [{"type": "notify", "details": {"channel": "email", "template": "escalation", "message": f"Pending approval exceeded {p['hours']}h"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _DATE_HINTS,
    },

    # -- Notification (5) ------------------------------------------------------
    {
        "id": "status_change_email",
        "name": "Status Change Email",
        "category": "notification",
        "description": "Send email when a status field changes.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "field", "type": "string", "required": True},
            {"name": "recipient_field", "type": "string", "required": True},
            {"name": "subject_template", "type": "string", "required": False},
        ],
        "build": lambda p: {
            "trigger": {"event": "after_update", "entity": p["entity"]},
            "conditions": [{"type": "field_check", "field": p["field"], "operator": "ne", "value": "__previous__"}],
            "actions": [{"type": "notify", "details": {"channel": "email", "recipient_field": p["recipient_field"], "subject": p.get("subject_template", f"{p['entity']} {p['field']} changed")}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _STATUS_HINTS,
    },
    {
        "id": "pending_action_reminder",
        "name": "Pending Action Reminder",
        "category": "notification",
        "description": "Notify assigned user about pending actions after N hours.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "hours", "type": "number", "required": True},
            {"name": "assignee_field", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "on_schedule", "entity": p["entity"]},
            "conditions": [{"type": "temporal", "field": "updated_at", "operator": "gt", "value": p["hours"], "unit": "hours"}],
            "actions": [{"type": "notify", "details": {"channel": "email", "recipient_field": p["assignee_field"], "message": f"You have a pending {p['entity']} action"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _DATE_HINTS,
    },
    {
        "id": "daily_digest",
        "name": "Daily Digest",
        "category": "notification",
        "description": "Send a daily summary of new/changed records to a role.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "recipient_role", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "on_schedule", "entity": p["entity"]},
            "conditions": [{"type": "temporal", "field": "created_at", "operator": "lt", "value": 24, "unit": "hours"}],
            "actions": [{"type": "notify", "details": {"channel": "email", "recipient_role": p["recipient_role"], "template": "daily_digest"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": frozenset(),
    },
    {
        "id": "sla_breach_alert",
        "name": "SLA Breach Alert",
        "category": "notification",
        "description": "Alert when a record exceeds its SLA deadline.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "deadline_field", "type": "string", "required": True},
            {"name": "recipient_role", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "on_schedule", "entity": p["entity"]},
            "conditions": [{"type": "temporal", "field": p["deadline_field"], "operator": "lt", "value": 0, "unit": "hours"}],
            "actions": [{"type": "notify", "details": {"channel": "email", "recipient_role": p["recipient_role"], "message": f"SLA breached on {p['entity']}"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _DATE_HINTS,
    },
    {
        "id": "escalation_chain",
        "name": "Escalation Chain",
        "category": "notification",
        "description": "Escalate to next level if action not taken within time limit.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "hours_l1", "type": "number", "required": True},
            {"name": "hours_l2", "type": "number", "required": True},
            {"name": "l1_role", "type": "string", "required": True},
            {"name": "l2_role", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "on_schedule", "entity": p["entity"]},
            "conditions": [{"type": "temporal", "field": "created_at", "operator": "gt", "value": p["hours_l1"], "unit": "hours"}],
            "actions": [
                {"type": "notify", "details": {"channel": "email", "recipient_role": p["l1_role"], "message": f"Escalation L1: pending {p['entity']}"}},
                {"type": "notify", "details": {"channel": "email", "recipient_role": p["l2_role"], "condition": f"age_hours > {p['hours_l2']}", "message": f"Escalation L2: pending {p['entity']}"}},
            ],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _DATE_HINTS,
    },

    # -- Validation (6) --------------------------------------------------------
    {
        "id": "required_field",
        "name": "Required Field",
        "category": "validation",
        "description": "Block creation/update if a required field is empty.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "field", "type": "string", "required": True},
            {"name": "message", "type": "string", "required": False},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [{"type": "field_check", "field": p["field"], "operator": "is_null"}],
            "actions": [{"type": "block", "details": {"message": p.get("message", f"{p['field']} is required")}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": frozenset(),
    },
    {
        "id": "format_check",
        "name": "Format Check",
        "category": "validation",
        "description": "Validate field matches a regex pattern.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "field", "type": "string", "required": True},
            {"name": "pattern", "type": "string", "required": True},
            {"name": "message", "type": "string", "required": False},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [{"type": "field_check", "field": p["field"], "operator": "not_contains", "value": p["pattern"]}],
            "actions": [{"type": "block", "details": {"message": p.get("message", f"{p['field']} does not match required format")}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _EMAIL_HINTS,
    },
    {
        "id": "range_check",
        "name": "Range Check",
        "category": "validation",
        "description": "Validate a numeric field is within min/max bounds.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "field", "type": "string", "required": True},
            {"name": "min_value", "type": "number", "required": False},
            {"name": "max_value", "type": "number", "required": False},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [
                c for c in [
                    {"type": "field_check", "field": p["field"], "operator": "lt", "value": p["min_value"]} if p.get("min_value") is not None else None,
                    {"type": "field_check", "field": p["field"], "operator": "gt", "value": p["max_value"]} if p.get("max_value") is not None else None,
                ] if c is not None
            ],
            "actions": [{"type": "block", "details": {"message": f"{p['field']} out of range"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _AMOUNT_HINTS,
    },
    {
        "id": "uniqueness_check",
        "name": "Uniqueness Check",
        "category": "validation",
        "description": "Ensure a field value is unique across all records.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "field", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [{"type": "existence", "field": p["field"], "operator": "eq", "value": "__current__"}],
            "actions": [{"type": "block", "details": {"message": f"{p['field']} must be unique"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": frozenset({"code", "sku", "slug", "email", "username"}),
    },
    {
        "id": "cross_field_validation",
        "name": "Cross-Field Validation",
        "category": "validation",
        "description": "Validate a relationship between two fields (e.g., end_date > start_date).",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "field_a", "type": "string", "required": True},
            {"name": "operator", "type": "string", "required": True},
            {"name": "field_b", "type": "string", "required": True},
            {"name": "message", "type": "string", "required": False},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [{"type": "cross_entity", "field": p["field_a"], "operator": p["operator"], "value": f"__field__{p['field_b']}"}],
            "actions": [{"type": "block", "details": {"message": p.get("message", f"{p['field_a']} must be {p['operator']} {p['field_b']}")}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _DATE_HINTS,
    },
    {
        "id": "conditional_required",
        "name": "Conditional Required",
        "category": "validation",
        "description": "Require a field only when another field has a specific value.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "when_field", "type": "string", "required": True},
            {"name": "when_value", "type": "string", "required": True},
            {"name": "then_required_field", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [
                {"type": "field_check", "field": p["when_field"], "operator": "eq", "value": p["when_value"]},
                {"type": "field_check", "field": p["then_required_field"], "operator": "is_null"},
            ],
            "actions": [{"type": "block", "details": {"message": f"{p['then_required_field']} is required when {p['when_field']} is {p['when_value']}"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _STATUS_HINTS | _BOOL_HINTS,
    },

    # -- Scheduled (4) ---------------------------------------------------------
    {
        "id": "archive_old_records",
        "name": "Archive Old Records",
        "category": "scheduled",
        "description": "Automatically archive records older than N days.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "days", "type": "number", "required": True},
            {"name": "date_field", "type": "string", "required": False},
        ],
        "build": lambda p: {
            "trigger": {"event": "on_schedule", "entity": p["entity"]},
            "conditions": [{"type": "temporal", "field": p.get("date_field", "created_at"), "operator": "gt", "value": p["days"] * 24, "unit": "hours"}],
            "actions": [{"type": "update_field", "details": {"field": "status", "value": "archived"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _DATE_HINTS,
    },
    {
        "id": "generate_report",
        "name": "Generate Report",
        "category": "scheduled",
        "description": "Generate a periodic summary report and notify stakeholders.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "frequency", "type": "string", "required": True},
            {"name": "recipient_role", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "on_schedule", "entity": p["entity"]},
            "conditions": [],
            "actions": [
                {"type": "log", "details": {"message": f"Generating {p['frequency']} report for {p['entity']}"}},
                {"type": "notify", "details": {"channel": "email", "recipient_role": p["recipient_role"], "template": "report"}},
            ],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": frozenset(),
    },
    {
        "id": "sync_data",
        "name": "Sync Data",
        "category": "scheduled",
        "description": "Trigger a data sync from an external source on schedule.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "source_url", "type": "string", "required": True},
            {"name": "frequency", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "on_schedule", "entity": p["entity"]},
            "conditions": [],
            "actions": [{"type": "call_api", "details": {"url": p["source_url"], "method": "GET"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": frozenset(),
    },
    {
        "id": "cleanup_expired",
        "name": "Cleanup Expired",
        "category": "scheduled",
        "description": "Delete or archive records past their expiry date.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "expiry_field", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "on_schedule", "entity": p["entity"]},
            "conditions": [{"type": "temporal", "field": p["expiry_field"], "operator": "lt", "value": 0, "unit": "hours"}],
            "actions": [{"type": "update_field", "details": {"field": "status", "value": "expired"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _DATE_HINTS,
    },

    # -- Computed (4) ----------------------------------------------------------
    {
        "id": "auto_calculate_total",
        "name": "Auto-Calculate Total",
        "category": "computed",
        "description": "Automatically compute a total field from line items.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "target_field", "type": "string", "required": True},
            {"name": "source_field", "type": "string", "required": True},
            {"name": "child_entity", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "after_create", "entity": p["child_entity"]},
            "conditions": [],
            "actions": [{"type": "update_field", "details": {"entity": p["entity"], "field": p["target_field"], "expression": f"SUM({p['child_entity']}.{p['source_field']})"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _AMOUNT_HINTS,
    },
    {
        "id": "status_derivation",
        "name": "Status Derivation",
        "category": "computed",
        "description": "Derive status from business conditions.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "target_field", "type": "string", "required": True},
            {"name": "condition_field", "type": "string", "required": True},
            {"name": "threshold", "type": "number", "required": True},
            {"name": "derived_value", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "after_update", "entity": p["entity"]},
            "conditions": [{"type": "field_check", "field": p["condition_field"], "operator": "gt", "value": p["threshold"]}],
            "actions": [{"type": "update_field", "details": {"field": p["target_field"], "value": p["derived_value"]}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _STATUS_HINTS | _AMOUNT_HINTS,
    },
    {
        "id": "priority_scoring",
        "name": "Priority Scoring",
        "category": "computed",
        "description": "Auto-calculate a priority score from weighted fields.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "target_field", "type": "string", "required": True},
            {"name": "factors", "type": "list", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "after_update", "entity": p["entity"]},
            "conditions": [],
            "actions": [{"type": "update_field", "details": {"field": p["target_field"], "expression": " + ".join(f"{f['weight']}*{f['field']}" for f in p["factors"])}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _AMOUNT_HINTS,
    },
    {
        "id": "running_balance",
        "name": "Running Balance",
        "category": "computed",
        "description": "Maintain a running balance field updated on each transaction.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "balance_field", "type": "string", "required": True},
            {"name": "amount_field", "type": "string", "required": True},
            {"name": "account_entity", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "after_create", "entity": p["entity"]},
            "conditions": [],
            "actions": [{"type": "update_field", "details": {"entity": p["account_entity"], "field": p["balance_field"], "expression": f"{p['balance_field']} + {p['entity']}.{p['amount_field']}"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _AMOUNT_HINTS,
    },

    # -- Access Control (4) ----------------------------------------------------
    {
        "id": "role_based_visibility",
        "name": "Role-Based Visibility",
        "category": "access_control",
        "description": "Restrict record visibility to specific roles.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "allowed_roles", "type": "list", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [],
            "actions": [{"type": "assign_role", "details": {"roles": p["allowed_roles"], "scope": "read"}}],
            "side_effects": [{"type": "create_role", "details": {"role_name": r}} for r in p["allowed_roles"]],
            "confidence": 1.0,
        },
        "hint_fields": frozenset(),
    },
    {
        "id": "field_level_permissions",
        "name": "Field-Level Permissions",
        "category": "access_control",
        "description": "Hide or make read-only specific fields for certain roles.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "field", "type": "string", "required": True},
            {"name": "restricted_roles", "type": "list", "required": True},
            {"name": "permission", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [],
            "actions": [{"type": "assign_role", "details": {"field": p["field"], "restricted_roles": p["restricted_roles"], "permission": p["permission"]}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": frozenset(),
    },
    {
        "id": "row_level_security",
        "name": "Row-Level Security",
        "category": "access_control",
        "description": "Users can only see records they own or are assigned to.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "owner_field", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_create", "entity": p["entity"]},
            "conditions": [],
            "actions": [{"type": "assign_role", "details": {"scope": "row", "owner_field": p["owner_field"]}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": frozenset({"owner", "assigned_to", "created_by", "user_id"}),
    },
    {
        "id": "time_based_access",
        "name": "Time-Based Access",
        "category": "access_control",
        "description": "Allow access only during specific hours or until a deadline.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "deadline_field", "type": "string", "required": False},
        ],
        "build": lambda p: {
            "trigger": {"event": "before_update", "entity": p["entity"]},
            "conditions": [{"type": "temporal", "field": p.get("deadline_field", "updated_at"), "operator": "lt", "value": 0, "unit": "hours"}] if p.get("deadline_field") else [],
            "actions": [{"type": "block", "details": {"message": "Access window has closed"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": _DATE_HINTS,
    },

    # -- Integration (3) -------------------------------------------------------
    {
        "id": "webhook_on_event",
        "name": "Webhook on Event",
        "category": "integration",
        "description": "Fire a webhook to an external URL when a record is created/updated.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "event", "type": "string", "required": True},
            {"name": "url", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": p["event"], "entity": p["entity"]},
            "conditions": [],
            "actions": [{"type": "call_api", "details": {"url": p["url"], "method": "POST"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": frozenset(),
    },
    {
        "id": "sync_on_change",
        "name": "Sync on Change",
        "category": "integration",
        "description": "Push updated record to an external system when it changes.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "target_url", "type": "string", "required": True},
            {"name": "field", "type": "string", "required": False},
        ],
        "build": lambda p: {
            "trigger": {"event": "after_update", "entity": p["entity"]},
            "conditions": [{"type": "field_check", "field": p["field"], "operator": "ne", "value": "__previous__"}] if p.get("field") else [],
            "actions": [{"type": "call_api", "details": {"url": p["target_url"], "method": "PUT"}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": frozenset(),
    },
    {
        "id": "external_lookup_on_create",
        "name": "External Lookup on Create",
        "category": "integration",
        "description": "Enrich a new record by calling an external API for additional data.",
        "parameters": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "lookup_url", "type": "string", "required": True},
            {"name": "lookup_field", "type": "string", "required": True},
            {"name": "target_field", "type": "string", "required": True},
        ],
        "build": lambda p: {
            "trigger": {"event": "after_create", "entity": p["entity"]},
            "conditions": [],
            "actions": [{"type": "call_api", "details": {"url": p["lookup_url"], "method": "GET", "params": {"key_field": p["lookup_field"]}, "target_field": p["target_field"]}}],
            "side_effects": [],
            "confidence": 1.0,
        },
        "hint_fields": frozenset(),
    },
]

_TEMPLATE_INDEX = {t["id"]: t for t in TEMPLATES}


class RuleTemplateEngine:
    """Catalog of parameterised business rule templates with context-aware suggestions."""

    def list_templates(self) -> List[Dict[str, Any]]:
        """Return all templates (without build functions -- those are internal)."""
        return [
            {k: v for k, v in t.items() if k not in ("build", "hint_fields")}
            for t in TEMPLATES
        ]

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Return a single template by ID, or None."""
        t = _TEMPLATE_INDEX.get(template_id)
        if t is None:
            return None
        return {k: v for k, v in t.items() if k not in ("build", "hint_fields")}

    def instantiate(self, template_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Instantiate a template with parameters, returning a validated rule definition."""
        template = _TEMPLATE_INDEX.get(template_id)
        if template is None:
            raise ValueError(f"Unknown template: {template_id}")

        for p in template["parameters"]:
            if p.get("required") and p["name"] not in params:
                raise ValueError(f"Missing required parameter: {p['name']}")

        return template["build"](params)

    def suggest_templates(self, data_model: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Suggest templates based on data model field names and types."""
        suggestions: List[Dict[str, Any]] = []
        seen: set = set()

        for cls in data_model.get("classes", []):
            entity_name = cls.get("name", "")
            field_names = {f.get("name", "").lower() for f in cls.get("fields", [])}

            for template in TEMPLATES:
                hint_fields = template.get("hint_fields", frozenset())
                if not hint_fields:
                    continue

                matching_fields = []
                for fname in field_names:
                    for hint in hint_fields:
                        if hint in fname:
                            matching_fields.append(fname)
                            break

                if matching_fields:
                    key = (template["id"], entity_name)
                    if key not in seen:
                        seen.add(key)
                        suggestions.append({
                            "template_id": template["id"],
                            "template_name": template["name"],
                            "entity": entity_name,
                            "matching_fields": matching_fields,
                            "reason": f"Entity '{entity_name}' has fields matching {template['name']}: {', '.join(matching_fields)}",
                        })

        return suggestions
