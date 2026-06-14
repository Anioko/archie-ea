"""Generate test scenarios from problem statement, data model, and business rules.

Produces deterministic base scenarios (CRUD per entity) plus rule-specific
scenarios. Each scenario is a BA-readable test case with numbered steps.
"""
import json
import logging

logger = logging.getLogger(__name__)


class ScenarioGenerator:
    """Generate test scenarios for BA validation."""

    def generate(
        self,
        problem_statement: str,
        model_entities: dict[str, list[str]],
        rules: list[dict],
    ) -> list[dict]:
        """Generate scenarios from model + rules.

        Returns list of scenario dicts with: id, title, goal, steps, expected_outcome, source.
        """
        scenarios = []
        scenario_id = 0

        # 1. CRUD scenarios per entity
        for entity, fields in model_entities.items():
            scenario_id += 1
            scenarios.append({
                "id": scenario_id,
                "title": f"Create a new {entity}",
                "goal": f"Verify basic {entity} creation works end-to-end",
                "steps": [
                    {"number": 1, "action": f"Navigate to {entity} list page"},
                    {"number": 2, "action": f"Click 'New {entity}'"},
                    *[
                        {"number": i + 3, "action": f"Fill in '{field}' with a test value"}
                        for i, field in enumerate(fields[:5])
                    ],
                    {"number": len(fields[:5]) + 3, "action": "Click Submit"},
                ],
                "expected_outcome": f"New {entity} appears in the list with correct values",
                "source": "crud",
                "entity": entity,
            })

        # 2. Rule-specific scenarios
        for rule in rules:
            rule_def = rule.get("rule_definition", {})
            trigger = rule_def.get("trigger", {})
            entity = trigger.get("entity", "Record")
            conditions = rule_def.get("conditions", [])
            actions = rule_def.get("actions", [])

            # Happy path: condition met
            scenario_id += 1
            scenarios.append({
                "id": scenario_id,
                "title": f"Rule: {rule.get('name', 'Business rule')} — trigger condition",
                "goal": "Verify that the rule fires when conditions are met",
                "steps": self._rule_steps(entity, conditions, "trigger"),
                "expected_outcome": self._rule_outcome(actions, "trigger"),
                "source": "rule",
                "rule_name": rule.get("name"),
            })

            # Negative path: condition not met
            scenario_id += 1
            scenarios.append({
                "id": scenario_id,
                "title": f"Rule: {rule.get('name', 'Business rule')} — bypass condition",
                "goal": "Verify that the rule does NOT fire when conditions are not met",
                "steps": self._rule_steps(entity, conditions, "bypass"),
                "expected_outcome": f"{entity} is created/updated normally without rule intervention",
                "source": "rule",
                "rule_name": rule.get("name"),
            })

        return scenarios

    def _rule_steps(self, entity: str, conditions: list, mode: str) -> list[dict]:
        """Generate steps that trigger or bypass rule conditions."""
        steps = [
            {"number": 1, "action": f"Navigate to {entity} creation form"},
        ]
        for i, cond in enumerate(conditions):
            field = cond.get("field", "field")
            op = cond.get("operator", "")
            val = cond.get("value", "")
            if mode == "trigger":
                if op == "greater_than":
                    steps.append({"number": i + 2, "action": f"Enter {field} = {int(val) + 1000} (above threshold {val})"})
                elif op == "is_empty":
                    steps.append({"number": i + 2, "action": f"Leave {field} empty"})
                else:
                    steps.append({"number": i + 2, "action": f"Set {field} to match condition ({op} {val})"})
            else:  # bypass
                if op == "greater_than":
                    steps.append({"number": i + 2, "action": f"Enter {field} = {int(val) - 1} (below threshold {val})"})
                elif op == "is_empty":
                    steps.append({"number": i + 2, "action": f"Fill in {field} with a valid value"})
                else:
                    steps.append({"number": i + 2, "action": f"Set {field} to NOT match condition"})
        steps.append({"number": len(conditions) + 2, "action": "Click Submit"})
        return steps

    def _rule_outcome(self, actions: list, mode: str) -> str:
        """Describe expected outcome based on rule actions."""
        outcomes = []
        for action in actions:
            atype = action.get("type", "")
            if atype == "block":
                outcomes.append(f"Error shown: '{action.get('message', 'Blocked')}'")
            elif atype == "require_approval":
                outcomes.append(f"Approval request sent to {action.get('role', 'approver')}")
            elif atype == "notify":
                outcomes.append(f"Notification sent via {action.get('channel', 'email')}")
        return "; ".join(outcomes) if outcomes else "Rule action triggered"

    def generate_edge_cases(
        self,
        problem_statement: str,
        model_entities: dict[str, list[str]],
        rules: list[dict],
        existing_scenarios: list[dict],
    ) -> list[dict]:
        """Use LLM to generate edge case scenarios not covered by deterministic generation.

        Returns list of scenario dicts matching the same schema as generate().
        On LLM failure, returns empty list (deterministic scenarios still valid).
        """
        existing_titles = [s.get("title", "") for s in existing_scenarios]

        prompt = (
            "You are generating edge case test scenarios for a business application.\n\n"
            f"Problem: {problem_statement}\n"
            f"Entities: {list(model_entities.keys())}\n"
            f"Rules: {len(rules)} business rules defined\n"
            f"Already covered: {existing_titles}\n\n"
            "Generate 3-5 edge case scenarios NOT already covered. Focus on:\n"
            "- Boundary values (zero, negative, max)\n"
            "- Empty/null inputs\n"
            "- Concurrent operations\n"
            "- Permission edge cases\n\n"
            "Respond with a JSON array of scenario objects:\n"
            '[{"title": "...", "goal": "...", '
            '"steps": [{"number": 1, "action": "..."}], '
            '"expected_outcome": "...", "source": "edge_case"}]'
        )

        response, error = self._call_llm(prompt)
        if error or not response:
            logger.warning("Edge case generation failed: %s", error)
            return []

        try:
            cleaned = response.strip().strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            scenarios = json.loads(cleaned)
            if not isinstance(scenarios, list):
                return []
            # Ensure source is set
            for s in scenarios:
                s["source"] = "edge_case"
            return scenarios
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse edge case scenarios from LLM response")
            return []

    def generate_from_acceptance_criteria(self, solution_id: int) -> list[dict]:
        """Generate scenarios directly from AcceptanceCriteriaGenerator output.

        Each AC becomes one scenario. Business rule ACs already have positive + negative
        cases, so no duplication needed. This is the preferred path — more precise than
        generating from raw rules + model.
        """
        try:
            from app.modules.codegen.services.acceptance_criteria_generator import AcceptanceCriteriaGenerator
            ac_gen = AcceptanceCriteriaGenerator()
            criteria = ac_gen.generate(solution_id)
        except Exception as exc:
            logger.warning("AC generator failed, falling back to rule-based scenarios: %s", exc)
            return []

        scenarios = []
        for ac in criteria:
            scenarios.append({
                "id": ac["id"],
                "title": ac["title"],
                "goal": f"Verify: {ac['title']}",
                "steps": [
                    {"number": 1, "action": f"GIVEN: {ac['given']}"},
                    {"number": 2, "action": f"WHEN: {ac['when']}"},
                    {"number": 3, "action": f"THEN: {ac['then']}"},
                ],
                "expected_outcome": ac["then"],
                "verification": ac.get("verification", ""),
                "source": "acceptance_criteria",
                "priority": ac.get("priority", "MUST"),
                "category": ac.get("category", "business_rule"),
                "ac_source": ac.get("source", {}),
            })

        return scenarios

    def _call_llm(self, prompt: str) -> tuple:
        """Call LLM service. Returns (response_text, error_or_none)."""
        try:
            from app.modules.ai_chat.services.llm_service import LLMService
            svc = LLMService()
            response = svc.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
            )
            if response and "content" in response:
                return response["content"], None
            return None, "Empty response"
        except Exception as e:
            logger.warning("ScenarioGenerator LLM call failed: %s", e)
            return None, str(e)
