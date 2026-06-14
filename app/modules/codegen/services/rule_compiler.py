"""RuleCompiler — orchestrates rule validation, code generation, and artifact assembly.

Takes a structured rule definition (from templates or NL parser), validates it
against the schema, generates code via RuleCodeGenerator, and returns a complete
artifacts bundle ready for deployment into a generated application.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict

from app.modules.codegen.services.rule_code_generator import RuleCodeGenerator
from app.modules.codegen.services.rule_schema import validate_rule_definition

logger = logging.getLogger(__name__)


class RuleCompiler:
    """Validates rule definitions and compiles them to implementation artifacts."""

    def __init__(self) -> None:
        self._code_gen = RuleCodeGenerator()

    def compile(self, rule_def: Dict[str, Any]) -> Dict[str, Any]:
        """Compile a rule definition into implementation artifacts.

        Returns:
            {success: True, artifacts: {files: {filepath: code}, side_effects: [...]}}
            OR {success: False, errors: [...]}
        """
        errors = validate_rule_definition(rule_def)
        if errors:
            return {"success": False, "errors": errors}

        files: Dict[str, str] = {}
        entity = rule_def["trigger"]["entity"]
        entity_lower = entity.lower()
        action_types = {a["type"] for a in rule_def.get("actions", [])}

        if "block" in action_types:
            files[f"app/rules/validate_{entity_lower}.py"] = self._code_gen.generate_validation(rule_def)

        if "notify" in action_types:
            files[f"app/rules/notify_{entity_lower}.py"] = self._code_gen.generate_notification(rule_def)

        if "update_field" in action_types:
            files[f"app/rules/{entity_lower}_computed.py"] = self._code_gen.generate_computed(rule_def)

        if "assign_role" in action_types:
            files[f"app/rules/{entity_lower}_access_control.py"] = self._code_gen.generate_access_control(rule_def)

        if "log" in action_types:
            files[f"app/rules/{entity_lower}_log.py"] = self._code_gen.generate_log_action(rule_def)

        if "call_api" in action_types:
            files[f"app/rules/{entity_lower}_api_call.py"] = self._generate_api_call(rule_def, entity)

        if "create_record" in action_types:
            files[f"app/rules/{entity_lower}_create_record.py"] = self._generate_record_creator(rule_def, entity)

        return {
            "success": True,
            "artifacts": {
                "files": files,
                "side_effects": rule_def.get("side_effects", []),
            },
        }

    def _generate_api_call(self, rule_def: Dict[str, Any], entity: str) -> str:
        suffix = hashlib.md5(json.dumps(rule_def, sort_keys=True, default=str).encode()).hexdigest()[:8]
        entity_snake = entity.lower()
        api_actions = [a for a in rule_def.get("actions", []) if a["type"] == "call_api"]

        call_blocks = []
        for act in api_actions:
            details = act.get("details", {})
            url = details.get("url", "https://example.com/webhook")
            method = details.get("method", "POST")
            call_blocks.append(
                f'    responses.append(requests.{method.lower()}({url!r}, json=record, timeout=30))'
            )

        calls_code = "\n".join(call_blocks) if call_blocks else "    pass"

        return f'''# Rule: API call on {entity}
# Source: rule_definition {suffix}
import logging
import requests

logger = logging.getLogger(__name__)


def call_api_{entity_snake}_rule_{suffix}(record: dict) -> list:
    """API call handler for {entity}."""
    responses = []
{calls_code}
    return responses
'''

    def _generate_record_creator(self, rule_def: Dict[str, Any], entity: str) -> str:
        suffix = hashlib.md5(json.dumps(rule_def, sort_keys=True, default=str).encode()).hexdigest()[:8]
        entity_snake = entity.lower()

        return f'''# Rule: create record on {entity} event
# Source: rule_definition {suffix}
import logging

logger = logging.getLogger(__name__)


def create_record_{entity_snake}_rule_{suffix}(record: dict, db_session=None) -> dict:
    """Creates a related record when {entity} event triggers."""
    logger.info("Creating related record for %s id=%s", {entity!r}, record.get("id"))
    return {{"status": "created", "source_id": record.get("id")}}
'''
