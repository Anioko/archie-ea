"""Compile BA-readable test scenarios into Playwright action scripts.

Uses deterministic pattern matching for common actions (navigate, click, fill,
submit) and falls back to LLM for ambiguous steps. The compiled script is a
structured dict -- not executable Python code -- consumed by AcceptanceTestRunner.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

# Deterministic patterns: (regex, playwright_action, target_extractor)
_NAVIGATE_RE = re.compile(r"navigate\s+to\s+(.+?)(?:\s+page)?$", re.IGNORECASE)
_CLICK_NEW_RE = re.compile(r"click\s+['\"]?new\s+(.+?)['\"]?$", re.IGNORECASE)
_CLICK_SUBMIT_RE = re.compile(r"click\s+submit", re.IGNORECASE)
_CLICK_GENERIC_RE = re.compile(r"click\s+['\"]?(.+?)['\"]?$", re.IGNORECASE)
_FILL_RE = re.compile(r"(?:fill\s+in|enter|set)\s+['\"]?(\w+)['\"]?\s+(?:with|to|=)\s+(.+)", re.IGNORECASE)
_LEAVE_EMPTY_RE = re.compile(r"leave\s+['\"]?(\w+)['\"]?\s+empty", re.IGNORECASE)


class ScenarioToPlaywrightCompiler:
    """Compile scenario steps into Playwright action scripts."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def compile(self, scenario: dict) -> dict:
        """Compile a scenario into a Playwright action script.

        Args:
            scenario: Dict with id, title, steps [{number, action}], expected_outcome.

        Returns dict with: scenario_id, scenario_title, base_url,
        steps [{step_number, original_step, playwright_action, target, value}],
        expected_outcome.
        """
        compiled_steps = []
        unresolved_steps = []

        for step in scenario.get("steps", []):
            action_text = step.get("action", "")
            compiled = self._match_deterministic(action_text, step.get("number", 0))

            if compiled:
                compiled_steps.append(compiled)
            else:
                unresolved_steps.append(step)

        # Batch-resolve unresolved steps via LLM
        if unresolved_steps:
            llm_results = self._resolve_via_llm(unresolved_steps, scenario)
            compiled_steps.extend(llm_results)

        # Sort by step number
        compiled_steps.sort(key=lambda s: s.get("step_number", 0))

        return {
            "scenario_id": scenario.get("id"),
            "scenario_title": scenario.get("title", ""),
            "base_url": self.base_url,
            "steps": compiled_steps,
            "expected_outcome": scenario.get("expected_outcome", ""),
        }

    def _match_deterministic(self, action_text: str, step_number: int) -> dict | None:
        """Try to match an action string to a Playwright action deterministically."""

        # Navigate
        m = _NAVIGATE_RE.search(action_text)
        if m:
            entity = m.group(1).strip().lower().replace(" ", "-")
            return {
                "step_number": step_number,
                "original_step": action_text,
                "playwright_action": "goto",
                "target": f"{self.base_url}/{entity}",
                "value": None,
            }

        # Click Submit
        if _CLICK_SUBMIT_RE.search(action_text):
            return {
                "step_number": step_number,
                "original_step": action_text,
                "playwright_action": "click",
                "target": "button[type='submit'], button:has-text('Submit')",
                "value": None,
            }

        # Click New <Entity>
        m = _CLICK_NEW_RE.search(action_text)
        if m:
            entity = m.group(1).strip()
            return {
                "step_number": step_number,
                "original_step": action_text,
                "playwright_action": "click",
                "target": f"button:has-text('New {entity}'), a:has-text('New {entity}')",
                "value": None,
            }

        # Fill in field
        m = _FILL_RE.search(action_text)
        if m:
            field = m.group(1).strip()
            value = m.group(2).strip().strip("'\"")
            return {
                "step_number": step_number,
                "original_step": action_text,
                "playwright_action": "fill",
                "target": f"input[name='{field}'], input[data-field='{field}'], #{field}",
                "value": value if "test value" not in value.lower() else f"Test {field} value",
            }

        # Leave field empty
        m = _LEAVE_EMPTY_RE.search(action_text)
        if m:
            field = m.group(1).strip()
            return {
                "step_number": step_number,
                "original_step": action_text,
                "playwright_action": "fill",
                "target": f"input[name='{field}'], input[data-field='{field}'], #{field}",
                "value": "",
            }

        # Generic click
        m = _CLICK_GENERIC_RE.search(action_text)
        if m:
            target_text = m.group(1).strip()
            return {
                "step_number": step_number,
                "original_step": action_text,
                "playwright_action": "click",
                "target": f"button:has-text('{target_text}'), a:has-text('{target_text}')",
                "value": None,
            }

        return None

    def _resolve_via_llm(self, steps: list[dict], scenario: dict) -> list[dict]:
        """Use LLM to compile ambiguous steps into Playwright actions."""
        step_texts = "\n".join(f"  {s['number']}. {s['action']}" for s in steps)

        prompt = (
            "Convert these test steps into Playwright actions for a web application.\n\n"
            f"Application base URL: {self.base_url}\n"
            f"Scenario: {scenario.get('title', '')}\n"
            f"Steps to convert:\n{step_texts}\n\n"
            "Respond with a JSON array. Each element:\n"
            '{"playwright_action": "goto|click|fill|assert_text|assert_visible|wait|manual", '
            '"target": "<CSS selector or URL>", '
            '"value": "<value to fill or assert, or null>", '
            '"original_step": "<the step text>"}\n\n'
            'Use "manual" for steps that cannot be automated.'
        )

        response, error = self._call_llm(prompt)
        if error or not response:
            # Fallback: mark all as manual
            return [
                {
                    "step_number": s.get("number", 0),
                    "original_step": s.get("action", ""),
                    "playwright_action": "manual",
                    "target": None,
                    "value": None,
                }
                for s in steps
            ]

        try:
            cleaned = response.strip().strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            parsed = json.loads(cleaned)
            if not isinstance(parsed, list):
                raise ValueError("Expected array")

            results = []
            for i, item in enumerate(parsed):
                step = steps[i] if i < len(steps) else steps[-1]
                results.append({
                    "step_number": step.get("number", 0),
                    "original_step": item.get("original_step", step.get("action", "")),
                    "playwright_action": item.get("playwright_action", "manual"),
                    "target": item.get("target"),
                    "value": item.get("value"),
                })
            return results
        except (json.JSONDecodeError, ValueError):
            return [
                {
                    "step_number": s.get("number", 0),
                    "original_step": s.get("action", ""),
                    "playwright_action": "manual",
                    "target": None,
                    "value": None,
                }
                for s in steps
            ]

    def _call_llm(self, prompt: str) -> tuple:
        """Call LLM service. Returns (response_text, error_or_none)."""
        try:
            from app.modules.ai_chat.services.llm_service import LLMService
            svc = LLMService()
            response = svc.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
            if response and "content" in response:
                return response["content"], None
            return None, "Empty response"
        except Exception as e:
            logger.warning("ScenarioToPlaywrightCompiler LLM call failed: %s", e)
            return None, str(e)
