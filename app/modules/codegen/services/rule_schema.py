"""Rule definition schema -- shared contract between all business rules services."""
from __future__ import annotations
from typing import Any, Dict, List

VALID_TRIGGER_EVENTS = frozenset({
    "before_create", "after_create",
    "before_update", "after_update",
    "on_schedule", "on_webhook",
})

VALID_CONDITION_TYPES = frozenset({
    "field_check", "aggregate", "existence", "temporal", "cross_entity",
})

VALID_ACTION_TYPES = frozenset({
    "block", "notify", "update_field", "create_record",
    "call_api", "assign_role", "log",
})

VALID_SIDE_EFFECT_TYPES = frozenset({
    "create_role", "add_field", "create_entity",
})

VALID_OPERATORS = frozenset({
    "eq", "ne", "gt", "gte", "lt", "lte",
    "in", "not_in", "contains", "not_contains",
    "is_null", "is_not_null",
})


def validate_rule_definition(rule_def: Dict[str, Any]) -> List[str]:
    """Validate a structured rule definition. Returns list of error strings (empty = valid)."""
    errors: List[str] = []

    trigger = rule_def.get("trigger")
    if not isinstance(trigger, dict):
        errors.append("Missing or invalid 'trigger' (must be an object)")
    else:
        event = trigger.get("event")
        if event not in VALID_TRIGGER_EVENTS:
            errors.append(f"Invalid trigger event '{event}'. Valid: {sorted(VALID_TRIGGER_EVENTS)}")
        if not trigger.get("entity"):
            errors.append("trigger.entity is required")

    conditions = rule_def.get("conditions")
    if not isinstance(conditions, list):
        errors.append("Missing or invalid 'conditions' (must be a list)")
    else:
        for i, cond in enumerate(conditions):
            ctype = cond.get("type") if isinstance(cond, dict) else None
            if ctype not in VALID_CONDITION_TYPES:
                errors.append(f"Invalid condition type '{ctype}' at index {i}. Valid: {sorted(VALID_CONDITION_TYPES)}")

    actions = rule_def.get("actions")
    if not isinstance(actions, list) or len(actions) == 0:
        errors.append("'actions' must be a non-empty list")
    else:
        for i, act in enumerate(actions):
            atype = act.get("type") if isinstance(act, dict) else None
            if atype not in VALID_ACTION_TYPES:
                errors.append(f"Invalid action type '{atype}' at index {i}. Valid: {sorted(VALID_ACTION_TYPES)}")

    side_effects = rule_def.get("side_effects")
    if not isinstance(side_effects, list):
        errors.append("Missing or invalid 'side_effects' (must be a list)")
    else:
        for i, se in enumerate(side_effects):
            stype = se.get("type") if isinstance(se, dict) else None
            if stype not in VALID_SIDE_EFFECT_TYPES:
                errors.append(f"Invalid side_effect type '{stype}' at index {i}. Valid: {sorted(VALID_SIDE_EFFECT_TYPES)}")

    confidence = rule_def.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
            errors.append("'confidence' must be a number between 0.0 and 1.0")

    return errors
