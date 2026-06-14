"""RuleCodeGenerator — deterministic code generation from structured rule definitions.

Converts validated rule definitions into Python code strings for FastAPI applications.
Each method produces syntactically valid Python that can be injected into generated apps.

Deterministic: same input always produces same output. No LLM calls.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

_OPERATOR_MAP = {
    "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
    "eq": "==", "ne": "!=", "in": "in", "not_in": "not in",
    "is_null": "is None", "is_not_null": "is not None",
}


def _rule_hash(rule_def: Dict[str, Any]) -> str:
    raw = json.dumps(rule_def, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:8]


def _snake(name: str) -> str:
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class RuleCodeGenerator:
    """Generates Python code from structured rule definitions."""

    def generate_validation(self, rule_def: Dict[str, Any]) -> str:
        entity = rule_def["trigger"]["entity"]
        entity_snake = _snake(entity)
        suffix = _rule_hash(rule_def)
        conditions = rule_def.get("conditions", [])
        actions = [a for a in rule_def.get("actions", []) if a["type"] == "block"]
        message = actions[0]["details"].get("message", "Validation failed") if actions else "Validation failed"

        condition_checks = []
        for cond in conditions:
            field = cond.get("field", "")
            op = cond.get("operator", "eq")
            value = cond.get("value")

            if op in ("is_null", "is_not_null"):
                condition_checks.append(f"    if data.get({field!r}) {_OPERATOR_MAP[op]}:")
            elif op in ("contains", "not_contains"):
                negate = "not " if op == "not_contains" else ""
                condition_checks.append(f"    if {negate}{value!r} in str(data.get({field!r}, '')):")
            else:
                py_op = _OPERATOR_MAP.get(op, "==")
                condition_checks.append(f"    if data.get({field!r}) is not None and data.get({field!r}) {py_op} {value!r}:")

        if not condition_checks:
            condition_checks.append("    if True:")

        checks_block = "\n".join(
            f"{check}\n        raise HTTPException(status_code=422, detail={message!r})"
            for check in condition_checks
        )

        return f'''# Rule: {message}
# Source: rule_definition {suffix}
from fastapi import HTTPException


def validate_{entity_snake}_rule_{suffix}(data: dict) -> None:
    """Validation rule for {entity}: {message}"""
{checks_block}
'''

    def generate_notification(self, rule_def: Dict[str, Any]) -> str:
        entity = rule_def["trigger"]["entity"]
        entity_snake = _snake(entity)
        suffix = _rule_hash(rule_def)
        event = rule_def["trigger"]["event"]
        notify_actions = [a for a in rule_def.get("actions", []) if a["type"] == "notify"]

        notify_blocks = []
        for act in notify_actions:
            details = act.get("details", {})
            channel = details.get("channel", "email")
            recipient_field = details.get("recipient_field", "email")
            subject = details.get("subject", f"{entity} notification")
            message = details.get("message", subject)
            notify_blocks.append(
                f'    notifications.append({{\n'
                f'        "channel": {channel!r},\n'
                f'        "to": record.get({recipient_field!r}),\n'
                f'        "subject": {subject!r},\n'
                f'        "body": {message!r},\n'
                f'    }})'
            )

        notify_code = "\n".join(notify_blocks) if notify_blocks else '    notifications.append({"channel": "log", "body": "notification triggered"})'

        condition_code = ""
        for cond in rule_def.get("conditions", []):
            field = cond.get("field", "")
            op = cond.get("operator", "eq")
            value = cond.get("value")
            if op == "ne" and value == "__previous__":
                condition_code += f'    if record.get({field!r}) == previous.get({field!r}):\n        return notifications  # no change\n'

        return f'''# Rule: {entity} {event} notification
# Source: rule_definition {suffix}
import logging

logger = logging.getLogger(__name__)


def notify_{entity_snake}_rule_{suffix}(record: dict, previous: dict = None) -> list:
    """Notification handler for {entity} on {event}."""
    previous = previous or {{}}
    notifications = []
{condition_code}{notify_code}
    return notifications
'''

    def generate_computed(self, rule_def: Dict[str, Any]) -> str:
        trigger_entity = rule_def["trigger"]["entity"]
        entity_snake = _snake(trigger_entity)
        suffix = _rule_hash(rule_def)
        update_actions = [a for a in rule_def.get("actions", []) if a["type"] == "update_field"]

        update_blocks = []
        for act in update_actions:
            details = act.get("details", {})
            field = details.get("field", "computed_field")
            expression = details.get("expression")
            value = details.get("value")

            if value is not None:
                update_blocks.append(f'    updates[{field!r}] = {value!r}')
            else:
                update_blocks.append(f'    # Expression: {expression}')
                update_blocks.append(f'    updates[{field!r}] = {expression!r}  # resolve at runtime via ORM query')

        updates_code = "\n".join(update_blocks) if update_blocks else "    pass"

        return f'''# Rule: compute fields on {trigger_entity}
# Source: rule_definition {suffix}


def compute_{entity_snake}_rule_{suffix}(record: dict, db_session=None) -> dict:
    """Computed field hook triggered by {trigger_entity} changes."""
    updates = {{}}
{updates_code}
    return updates
'''

    def generate_access_control(self, rule_def: Dict[str, Any]) -> str:
        entity = rule_def["trigger"]["entity"]
        entity_snake = _snake(entity)
        suffix = _rule_hash(rule_def)
        role_actions = [a for a in rule_def.get("actions", []) if a["type"] == "assign_role"]

        roles = []
        for act in role_actions:
            details = act.get("details", {})
            if "roles" in details:
                roles.extend(details["roles"])
            elif "role" in details:
                roles.append(details["role"])

        scope = "read"
        for act in role_actions:
            scope = act.get("details", {}).get("scope", "read")
            break

        roles_repr = repr(sorted(set(roles))) if roles else "[]"

        return f'''# Rule: access control for {entity}
# Source: rule_definition {suffix}
from fastapi import HTTPException


ALLOWED_ROLES = {roles_repr}


def guard_{entity_snake}_rule_{suffix}(current_user_roles: list, action: str = {scope!r}) -> None:
    """Access control guard for {entity}. Checks user has required role."""
    if not any(role in ALLOWED_ROLES for role in current_user_roles):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to {scope} this {entity}",
        )
'''

    def generate_log_action(self, rule_def: Dict[str, Any]) -> str:
        entity = rule_def["trigger"]["entity"]
        entity_snake = _snake(entity)
        suffix = _rule_hash(rule_def)
        event = rule_def["trigger"]["event"]
        log_actions = [a for a in rule_def.get("actions", []) if a["type"] == "log"]
        message = log_actions[0].get("details", {}).get("message", "Event triggered") if log_actions else "Event triggered"

        return f'''# Rule: log on {entity} {event}
# Source: rule_definition {suffix}
import logging

logger = logging.getLogger(__name__)


def log_{entity_snake}_rule_{suffix}(record: dict) -> None:
    """Log action for {entity} on {event}."""
    logger.info({message!r} + " | record_id=%s", record.get("id"))
'''
