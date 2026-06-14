"""Acceptance test runner for generated solutions.

Takes scenarios from ScenarioGenerator, compiles them to Playwright scripts
via ScenarioToPlaywrightCompiler, executes them against the deployed app,
and produces a structured test report with screenshots.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AcceptanceTestRunner:
    """Run acceptance tests against generated solutions."""

    def run_all(
        self,
        solution_id: int,
        scenarios: list[dict] | None = None,
        persist: bool = False,
        trigger: str = "manual",
    ) -> dict:
        """Execute all acceptance test scenarios for a solution.

        Args:
            solution_id: The solution to test.
            scenarios: Pre-generated scenarios. If None, generates them.
            persist: If True, persist results to TestRun/TestRunStep models.
            trigger: What triggered this run (manual, post_deploy, nightly).

        Returns dict with: solution_id, run_id, timestamp, results (list),
        summary (pass/fail/pending counts).
        """
        if scenarios is None:
            scenarios = self._generate_scenarios(solution_id)

        run_id = f"run-{solution_id}-{int(datetime.now(timezone.utc).timestamp())}"
        results = []

        for scenario in scenarios:
            result = self._execute_scenario(scenario, solution_id)
            results.append(result)

        summary = self._build_summary(results)

        report = {
            "solution_id": solution_id,
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": results,
            "summary": summary,
        }

        if persist:
            self._persist_run(solution_id, report, trigger)

        return report

    def _generate_scenarios(self, solution_id: int) -> list[dict]:
        """Generate scenarios from solution data using ScenarioGenerator."""
        try:
            from app.models.solution_models import Solution
            solution = Solution.query.get(solution_id)
            if not solution:
                return []

            from app.modules.codegen.services.scenario_generator import ScenarioGenerator
            gen = ScenarioGenerator()

            model_entities = {}
            if hasattr(solution, "data_model") and solution.data_model:
                dm = solution.data_model
                if isinstance(dm, dict):
                    for entity_name, entity_def in dm.get("entities", {}).items():
                        fields = []
                        if isinstance(entity_def, dict):
                            fields = list(entity_def.get("fields", {}).keys())
                        elif isinstance(entity_def, list):
                            fields = entity_def
                        model_entities[entity_name] = fields

            rules = []
            if hasattr(solution, "business_rules") and solution.business_rules:
                if isinstance(solution.business_rules, list):
                    rules = solution.business_rules

            problem = ""
            if hasattr(solution, "problem_clarification") and solution.problem_clarification:
                if isinstance(solution.problem_clarification, dict):
                    problem = solution.problem_clarification.get("problem_statement", "")
                else:
                    problem = str(solution.problem_clarification)

            return gen.generate(
                problem_statement=problem,
                model_entities=model_entities,
                rules=rules,
            )
        except Exception as e:
            logger.warning("Failed to generate scenarios for solution %s: %s", solution_id, e)
            return []

    def _execute_scenario(self, scenario: dict, solution_id: int) -> dict:
        """Execute a single test scenario.

        Compiles scenario to Playwright actions, then executes them.
        Falls back to pending status if Playwright is unavailable.
        """
        deployment_url = self._get_deployment_url(solution_id)

        if deployment_url:
            try:
                from app.modules.codegen.services.scenario_playwright_compiler import ScenarioToPlaywrightCompiler
                compiler = ScenarioToPlaywrightCompiler(base_url=deployment_url)
                compiled = compiler.compile(scenario)

                playwright_result = self._run_playwright_script(compiled)
                return {
                    "scenario_id": scenario.get("id"),
                    "title": scenario.get("title", ""),
                    "status": playwright_result.get("status", "error"),
                    "steps": playwright_result.get("steps", []),
                    "expected_outcome": scenario.get("expected_outcome", ""),
                    "actual_outcome": playwright_result.get("actual_outcome"),
                    "source": scenario.get("source", ""),
                }
            except Exception as e:
                logger.warning("Playwright execution failed for scenario %s: %s", scenario.get("id"), e)

        # Fallback: return pending status
        steps_results = []
        for step in scenario.get("steps", []):
            steps_results.append({
                "step_number": step.get("number", 0),
                "action": step.get("action", ""),
                "status": "pending",
                "screenshot": None,
                "error": None,
            })

        return {
            "scenario_id": scenario.get("id"),
            "title": scenario.get("title", ""),
            "status": "pending",
            "steps": steps_results,
            "expected_outcome": scenario.get("expected_outcome", ""),
            "actual_outcome": None,
            "source": scenario.get("source", ""),
        }

    def _run_playwright_script(self, compiled_script: dict) -> dict:
        """Execute a compiled Playwright script against the deployed app.

        Uses synchronous Playwright API. Takes screenshots at each step.

        Returns dict with: status, steps [{step_number, status, screenshot, error}],
        actual_outcome.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright not installed -- returning pending results")
            return {
                "status": "pending",
                "steps": [],
                "actual_outcome": "Playwright not available",
            }

        steps_results = []
        overall_status = "pass"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                for step in compiled_script.get("steps", []):
                    step_result = self._execute_playwright_step(page, step)
                    steps_results.append(step_result)

                    if step_result["status"] == "fail":
                        overall_status = "fail"
                    elif step_result["status"] == "error" and overall_status != "fail":
                        overall_status = "error"

                try:
                    actual_outcome = page.title()
                except Exception:
                    actual_outcome = "Could not capture page state"

                browser.close()
        except Exception as e:
            logger.warning("Playwright browser launch failed: %s", e)
            return {
                "status": "error",
                "steps": steps_results,
                "actual_outcome": f"Browser launch failed: {e}",
            }

        return {
            "status": overall_status,
            "steps": steps_results,
            "actual_outcome": actual_outcome,
        }

    def _execute_playwright_step(self, page, step: dict) -> dict:
        """Execute a single compiled Playwright step."""
        action = step.get("playwright_action", "manual")
        target = step.get("target", "")
        value = step.get("value")
        screenshot = None

        try:
            if action == "goto":
                page.goto(target, wait_until="domcontentloaded", timeout=15000)
            elif action == "click":
                page.click(target, timeout=10000)
            elif action == "fill":
                page.fill(target, value or "", timeout=10000)
            elif action == "assert_text":
                element = page.wait_for_selector(target, timeout=10000)
                text = element.text_content() or ""
                if value and value not in text:
                    return {
                        "step_number": step.get("step_number", 0),
                        "status": "fail",
                        "screenshot": None,
                        "error": f"Expected '{value}' in element text, got '{text[:200]}'",
                    }
            elif action == "assert_visible":
                page.wait_for_selector(target, state="visible", timeout=10000)
            elif action == "wait":
                page.wait_for_timeout(int(value) if value else 2000)
            elif action == "manual":
                return {
                    "step_number": step.get("step_number", 0),
                    "status": "skipped",
                    "screenshot": None,
                    "error": "Manual step -- cannot automate",
                }

            # Take screenshot after successful step
            try:
                import tempfile
                import os
                screenshot_dir = os.path.join(tempfile.gettempdir(), "archie_test_screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(
                    screenshot_dir,
                    f"step_{step.get('step_number', 0)}_{int(datetime.now(timezone.utc).timestamp())}.png",
                )
                page.screenshot(path=screenshot_path)
                screenshot = screenshot_path
            except Exception as exc:
                logger.debug("suppressed error in AcceptanceTestRunner._execute_playwright_step (app/modules/codegen/services/acceptance_test_runner.py): %s", exc)  # Screenshot failure is not a test failure

            return {
                "step_number": step.get("step_number", 0),
                "status": "pass",
                "screenshot": screenshot,
                "error": None,
            }
        except Exception as e:
            return {
                "step_number": step.get("step_number", 0),
                "status": "fail",
                "screenshot": None,
                "error": str(e),
            }

    def _get_deployment_url(self, solution_id: int) -> str | None:
        """Get the deployment URL for a solution from SolutionInstance."""
        try:
            from app.modules.codegen.models import SolutionInstance
            instance = SolutionInstance.query.filter_by(
                solution_id=solution_id, health_status="healthy"
            ).first()
            if instance and instance.deployment_url:
                return instance.deployment_url
        except Exception as e:
            logger.debug("Could not get deployment URL for solution %s: %s", solution_id, e)
        return None

    def _persist_run(self, solution_id: int, report: dict, trigger: str) -> None:
        """Persist test run results to the database."""
        try:
            from app.extensions import db
            from app.modules.codegen.models import TestRun, TestRunStep

            run = TestRun(
                solution_id=solution_id,
                trigger=trigger,
                status=self._overall_status(report["summary"]),
                summary=report["summary"],
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db.session.add(run)
            db.session.flush()

            for result in report.get("results", []):
                for step in result.get("steps", []):
                    run_step = TestRunStep(
                        test_run_id=run.id,
                        scenario_id=result.get("scenario_id", 0),
                        step_number=step.get("step_number", 0),
                        action=step.get("action", step.get("original_step", "")),
                        status=step.get("status", "pending"),
                        screenshot_path=step.get("screenshot"),
                        error_message=step.get("error"),
                    )
                    db.session.add(run_step)

            db.session.commit()
        except Exception as e:
            logger.warning("Failed to persist test run for solution %s: %s", solution_id, e)

    def _overall_status(self, summary: dict) -> str:
        """Determine overall run status from summary counts."""
        if summary.get("fail", 0) > 0:
            return "fail"
        if summary.get("error", 0) > 0:
            return "error"
        if summary.get("pass", 0) > 0 and summary.get("pending", 0) == 0:
            return "pass"
        return "pending"

    def _build_summary(self, results: list[dict]) -> dict:
        """Build summary counts from results."""
        counts = {"pass": 0, "fail": 0, "pending": 0, "error": 0, "skipped": 0}
        for r in results:
            status = r.get("status", "pending")
            if status in counts:
                counts[status] += 1
            else:
                counts["error"] += 1
        counts["total"] = len(results)
        return counts
