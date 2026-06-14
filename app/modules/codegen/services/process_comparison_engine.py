"""Compare old (manual) process with new (generated solution) capabilities.

Presentation-only service: produces a step-by-step before/after comparison
with estimated time savings. No runtime code generation.
"""
import json
import logging

logger = logging.getLogger(__name__)


class ProcessComparisonEngine:
    """Compare problem statement process with generated solution capabilities."""

    def compare(self, solution_id: int) -> dict:
        """Generate old-vs-new process comparison for a solution.

        Loads the solution's problem_clarification (old process) and
        generated capabilities (new process), then uses LLM to produce
        a step-by-step comparison with time savings estimates.

        Returns dict with: solution_id, steps (list of comparison dicts),
        total_time_savings_estimate, summary.
        """
        problem_statement, capabilities = self._load_solution_context(solution_id)

        if not problem_statement:
            return {
                "solution_id": solution_id,
                "steps": [],
                "total_time_savings_estimate": "N/A",
                "summary": "No problem statement found for this solution.",
            }

        prompt = (
            "You are comparing an old manual business process with a new automated solution.\n\n"
            f"OLD PROCESS (problem statement):\n{problem_statement}\n\n"
            f"NEW SOLUTION (capabilities):\n{capabilities}\n\n"
            "Create a step-by-step comparison. Respond with JSON:\n"
            '{"steps": [\n'
            '  {"step_number": 1, "process_step": "<what happens>", '
            '"old_method": "<how it was done manually>", '
            '"new_method": "<how the solution handles it>", '
            '"time_before": "<estimated time>", '
            '"time_after": "<estimated time>", '
            '"improvement": "<what changed>"}\n'
            '], "total_time_savings_estimate": "<overall saving>", '
            '"summary": "<1-2 sentence summary>"}'
        )

        response, error = self._call_llm(prompt)
        if error:
            return {
                "solution_id": solution_id,
                "steps": [],
                "total_time_savings_estimate": "N/A",
                "summary": f"Comparison generation failed: {error}",
            }

        try:
            cleaned = response.strip().strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            result = json.loads(cleaned)
            result["solution_id"] = solution_id
            return result
        except json.JSONDecodeError:
            return {
                "solution_id": solution_id,
                "steps": [],
                "total_time_savings_estimate": "N/A",
                "summary": response[:500] if response else "Failed to parse comparison",
            }

    def _load_solution_context(self, solution_id: int) -> tuple:
        """Load problem statement and capabilities from the solution.

        Returns (problem_statement, capabilities_text).
        """
        try:
            from app.models.solution_models import Solution
            solution = Solution.query.get(solution_id)
            if not solution:
                return None, None

            problem = ""
            if hasattr(solution, "problem_clarification") and solution.problem_clarification:
                if isinstance(solution.problem_clarification, dict):
                    problem = solution.problem_clarification.get("problem_statement", "")
                else:
                    problem = str(solution.problem_clarification)
            elif hasattr(solution, "description") and solution.description:
                problem = solution.description

            capabilities = ""
            if hasattr(solution, "generated_capabilities") and solution.generated_capabilities:
                if isinstance(solution.generated_capabilities, list):
                    capabilities = "\n".join(
                        f"- {c.get('name', c)}: {c.get('description', '')}"
                        if isinstance(c, dict) else f"- {c}"
                        for c in solution.generated_capabilities
                    )
                else:
                    capabilities = str(solution.generated_capabilities)

            return problem, capabilities
        except Exception as e:
            logger.warning("Failed to load solution %s context: %s", solution_id, e)
            return None, None

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
            logger.warning("ProcessComparisonEngine LLM call failed: %s", e)
            return None, str(e)
