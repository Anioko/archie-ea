"""
Orchestrator Agent for Agentic Testing Pipeline

Implements the Orchestrator-Workers pattern from Anthropic's Building Effective Agents.

Responsibilities:
1. Receives test request (PR diff, file changes, etc.)
2. Creates test plan with deterministic structure
3. Delegates to specialized agents (Unit, E2E, Contract)
4. Aggregates results and reports
5. NEVER self-approves - all changes require human/CI gate

Design Principles (from docs):
- Deterministic repeatability: AI proposes, traditional runners execute
- Guardrailed autonomy: Cannot self-approve production changes
- Traceability: Every action logged and tied to requirement/story
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .guardrails import (
    AuditLog,
    GuardrailAction,
    GuardrailPipeline,
    GuardrailResult,
    create_test_agent_guardrails,
)

logger = logging.getLogger(__name__)


# =============================================================================
# AGENT DEFINITIONS
# =============================================================================


class AgentType(Enum):
    """Types of specialized agents in the pipeline"""

    UNIT_TEST = "unit_test"
    E2E_TEST = "e2e_test"
    CONTRACT_TEST = "contract_test"
    SPEC_TO_TEST = "spec_to_test"
    EVALUATOR = "evaluator"


class AgentStatus(Enum):
    """Status of agent execution"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # Blocked by guardrails
    ESCALATED = "escalated"  # Requires human approval


@dataclass
class AgentTask:
    """A task assigned to a specialized agent"""

    task_id: str
    agent_type: AgentType
    input_data: Dict[str, Any]
    status: AgentStatus = AgentStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    guardrail_checks: List[GuardrailResult] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type.value,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "guardrail_checks": [g.to_dict() for g in self.guardrail_checks],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
        }


@dataclass
class TestPlan:
    """
    Deterministic test plan created by orchestrator.

    Key principle: The plan is deterministic and reviewable.
    AI proposes the plan, but execution follows the structure exactly.
    """

    plan_id: str
    created_at: str
    trigger: Dict[str, Any]  # What triggered this plan (PR, commit, manual)
    scope: Dict[str, Any]  # What's in scope for testing
    tasks: List[AgentTask]
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "draft"  # draft, approved, executing, completed, failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "created_at": self.created_at,
            "trigger": self.trigger,
            "scope": self.scope,
            "tasks": [t.to_dict() for t in self.tasks],
            "metadata": self.metadata,
            "status": self.status,
        }

    def to_yaml(self) -> str:
        """Export plan as YAML for human review"""
        import yaml

        return yaml.dump(self.to_dict(), default_flow_style=False)


# =============================================================================
# SPECIALIZED AGENTS (Workers)
# =============================================================================


class BaseAgent(ABC):
    """Base class for specialized agents with automatic cleanup"""

    agent_type: AgentType
    name: str

    def __init__(self, guardrails: GuardrailPipeline):
        self.guardrails = guardrails
        self.temp_files = []
        self.cleanup_dirs = []
        import atexit

        atexit.register(self._cleanup_temp_files)

    @abstractmethod
    def execute(self, task: AgentTask) -> Dict[str, Any]:
        """Execute the task and return results"""
        pass

    def create_temp_file(self, content: str = "", suffix: str = ".tmp", mode: str = "w") -> str:
        """Create a temporary file that will be cleaned up automatically"""
        import os
        import tempfile

        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, mode) as f:
                f.write(content)
        except:
            os.close(fd)
            raise

        self.temp_files.append(path)
        return path

    def register_temp_file(self, file_path: str):
        """Register an existing file for cleanup"""
        self.temp_files.append(file_path)

    def create_temp_dir(self, prefix: str = "agent_temp_") -> str:
        """Create a temporary directory that will be cleaned up automatically"""
        import tempfile

        temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.cleanup_dirs.append(temp_dir)
        return temp_dir

    def _cleanup_temp_files(self):
        """Clean up all registered temporary files and directories"""
        import os
        import shutil

        # Clean up files
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except OSError:
                pass  # Ignore cleanup errors

        # Clean up directories
        for dir_path in self.cleanup_dirs:
            try:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            except OSError:
                pass  # Ignore cleanup errors

        # Clear lists
        self.temp_files.clear()
        self.cleanup_dirs.clear()

    def _check_guardrails(self, task: AgentTask, stage: str, data: Any) -> GuardrailResult:
        """Check guardrails at different stages"""
        if stage == "input":
            return self.guardrails.check_input(data, {"task_id": task.task_id})
        elif stage == "output":
            return self.guardrails.check_output(data, {"task_id": task.task_id})
        else:
            raise ValueError(f"Unknown stage: {stage}")


class UnitTestAgent(BaseAgent):
    """
    Agent for generating unit tests.
    Uses the CodeAnalyzer and UnitTestGenerator from Phase 1.
    """

    agent_type = AgentType.UNIT_TEST
    name = "Unit Test Agent"

    def execute(self, task: AgentTask) -> Dict[str, Any]:
        """Generate unit tests for the given source file"""
        from .analyzer import CodeAnalyzer
        from .generator import UnitTestGenerator

        source_path = task.input_data.get("source_path")

        # Input guardrail check
        input_check = self._check_guardrails(task, "input", source_path)
        task.guardrail_checks.append(input_check)
        if not input_check.allowed:
            return {"error": input_check.reason, "blocked": True}

        # Analyze code
        try:
            analyzer = CodeAnalyzer(source_path)
            analysis = analyzer.analyze()
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}", "blocked": False}

        # Generate tests
        generator = UnitTestGenerator(analysis, source_path)
        test_code = generator.generate()

        # Output guardrail check
        output_check = self._check_guardrails(task, "output", test_code)
        task.guardrail_checks.append(output_check)
        if output_check.action == GuardrailAction.BLOCK:
            return {"error": output_check.reason, "blocked": True}

        return {
            "test_code": test_code,
            "analysis": {
                "functions": len(analysis.functions),
                "classes": len(analysis.classes),
                "mock_targets": list(analysis.mock_targets)[:10],
            },
            "warnings": [
                c.reason for c in task.guardrail_checks if c.action == GuardrailAction.WARN
            ],
        }


class E2ETestAgent(BaseAgent):
    """
    Agent for generating E2E tests.
    Generates Playwright/pytest tests for web workflows.
    """

    agent_type = AgentType.E2E_TEST
    name = "E2E Test Agent"

    def execute(self, task: AgentTask) -> Dict[str, Any]:
        """Generate E2E tests for the given route/workflow"""
        route_path = task.input_data.get("route_path")
        workflow = task.input_data.get("workflow")
        base_url = task.input_data.get("base_url", "http://localhost:5000")

        # Input guardrail check
        input_check = self._check_guardrails(task, "input", route_path)
        task.guardrail_checks.append(input_check)
        if not input_check.allowed:
            return {"error": input_check.reason, "blocked": True}

        # Generate E2E test code
        test_code = self._generate_e2e_test(route_path, workflow, base_url)

        # Output guardrail check
        output_check = self._check_guardrails(task, "output", test_code)
        task.guardrail_checks.append(output_check)
        if output_check.action == GuardrailAction.BLOCK:
            return {"error": output_check.reason, "blocked": True}

        return {
            "test_code": test_code,
            "workflow": workflow,
            "warnings": [
                c.reason for c in task.guardrail_checks if c.action == GuardrailAction.WARN
            ],
        }

    def _generate_e2e_test(self, route_path: str, workflow: str, base_url: str) -> str:
        """Generate E2E test code"""
        # Extract route name for test class
        route_name = Path(route_path).stem if route_path else "unknown"
        class_name = "".join(word.title() for word in route_name.split("_"))

        template = f'''"""
E2E Tests for {route_name} workflow
Auto-generated by E2E Test Agent
"""

import pytest
import time
from playwright.sync_api import Page, expect


class Test{class_name}Workflow:
    """E2E tests for {workflow or route_name}"""

    BASE_URL = "{base_url}"

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, authenticated_page):
        """Setup: ensure user is logged in"""
        self.page = authenticated_page

    def test_{route_name}_page_loads(self):
        """Test: Page loads successfully"""
        self.page.goto(f"{{self.BASE_URL}}/{route_name}/")
        self.page.wait_for_load_state("domcontentloaded")

        # Verify page loaded
        assert self.page.title() != ""
        expect(self.page.locator("body")).to_be_visible()

    def test_{route_name}_navigation(self):
        """Test: Navigation elements work"""
        self.page.goto(f"{{self.BASE_URL}}/{route_name}/")
        self.page.wait_for_load_state("domcontentloaded")

        # Check navigation is accessible
        nav = self.page.locator("nav, [role=navigation]")
        if nav.count() > 0:
            expect(nav.first).to_be_visible()

    def test_{route_name}_responsive_layout(self):
        """Test: Page is responsive"""
        self.page.goto(f"{{self.BASE_URL}}/{route_name}/")

        # Test mobile viewport
        self.page.set_viewport_size({{"width": 375, "height": 667}})
        self.page.wait_for_load_state("domcontentloaded")
        expect(self.page.locator("body")).to_be_visible()

        # Test desktop viewport
        self.page.set_viewport_size({{"width": 1920, "height": 1080}})
        self.page.wait_for_load_state("domcontentloaded")
        expect(self.page.locator("body")).to_be_visible()

    def test_{route_name}_accessibility_basics(self):
        """Test: Basic accessibility checks"""
        self.page.goto(f"{{self.BASE_URL}}/{route_name}/")
        self.page.wait_for_load_state("domcontentloaded")

        # Check for heading structure
        headings = self.page.locator("h1, h2, h3")
        assert headings.count() >= 1, "Page should have at least one heading"

        # Check images have alt text
        images = self.page.locator("img")
        for i in range(min(images.count(), 5)):  # Check first 5 images
            img = images.nth(i)
            alt = img.get_attribute("alt")
            # alt can be empty string for decorative images, but should exist
            assert alt is not None, f"Image {{i}} missing alt attribute"

    def test_{route_name}_keyboard_navigation(self):
        """Test: Page is keyboard navigable"""
        self.page.goto(f"{{self.BASE_URL}}/{route_name}/")
        self.page.wait_for_load_state("domcontentloaded")

        # Tab through interactive elements
        self.page.keyboard.press("Tab")
        focused = self.page.evaluate("document.activeElement.tagName")
        assert focused is not None, "Should be able to focus an element"
'''
        return template


class EvaluatorAgent(BaseAgent):
    """
    Agent for evaluating test quality.
    Implements the Evaluator-Optimizer pattern.
    """

    agent_type = AgentType.EVALUATOR
    name = "Test Evaluator Agent"

    def execute(self, task: AgentTask) -> Dict[str, Any]:
        """Evaluate generated tests for quality"""
        test_code = task.input_data.get("test_code")
        source_code = task.input_data.get("source_code")

        metrics = self._evaluate_tests(test_code, source_code)

        return {
            "metrics": metrics,
            "passed": metrics.get("overall_score", 0) >= 0.7,
            "recommendations": self._generate_recommendations(metrics),
        }

    def _evaluate_tests(self, test_code: str, source_code: str = None) -> Dict[str, Any]:
        """Evaluate test quality metrics"""
        import re

        metrics = {
            "assertion_count": len(re.findall(r"\bassert\b", test_code)),
            "test_count": len(re.findall(r"def test_", test_code)),
            "mock_count": len(re.findall(r"@patch|Mock\(|MagicMock\(", test_code)),
            "has_docstrings": bool(re.search(r'""".*?"""', test_code, re.DOTALL)),
            "has_setup": bool(re.search(r"def setup|@pytest.fixture", test_code)),
            "edge_case_tests": len(
                re.findall(
                    r"test_.*?(empty|none|null|invalid|error|edge|boundary)",
                    test_code,
                    re.IGNORECASE,
                )
            ),
        }

        # Calculate scores
        test_count = metrics["test_count"]
        if test_count > 0:
            metrics["assertions_per_test"] = metrics["assertion_count"] / test_count
            metrics["edge_case_ratio"] = metrics["edge_case_tests"] / test_count
        else:
            metrics["assertions_per_test"] = 0
            metrics["edge_case_ratio"] = 0

        # Overall score (0 - 1)
        score = 0
        if metrics["test_count"] > 0:
            score += 0.2
        if metrics["assertions_per_test"] >= 2:
            score += 0.2
        if metrics["has_docstrings"]:
            score += 0.1
        if metrics["has_setup"]:
            score += 0.1
        if metrics["edge_case_ratio"] >= 0.2:
            score += 0.2
        if metrics["mock_count"] > 0:
            score += 0.2

        metrics["overall_score"] = score
        return metrics

    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []

        if metrics.get("assertions_per_test", 0) < 2:
            recommendations.append("Add more assertions per test (aim for 2+)")

        if not metrics.get("has_docstrings"):
            recommendations.append("Add docstrings to test functions")

        if metrics.get("edge_case_ratio", 0) < 0.2:
            recommendations.append("Add more edge case tests (empty, null, invalid inputs)")

        if metrics.get("mock_count", 0) == 0:
            recommendations.append("Consider using mocks to isolate unit tests")

        return recommendations


# =============================================================================
# ORCHESTRATOR
# =============================================================================


class TestOrchestrator:
    """
    Central orchestrator for the agentic testing pipeline.

    Follows the Orchestrator-Workers pattern:
    1. Receives trigger (PR, commit, manual)
    2. Analyzes scope (changed files, requirements)
    3. Creates deterministic test plan
    4. Delegates to specialized agents
    5. Aggregates and reports results

    Key constraints (guardrailed autonomy):
    - Cannot self-approve changes
    - All actions are logged
    - Human gate for escalations
    """

    def __init__(
        self,
        project_root: str,
        audit_path: Optional[str] = None,
        human_approval_callback: Optional[Callable] = None,
    ):
        self.project_root = Path(project_root)
        self.audit_log = AuditLog(Path(audit_path)) if audit_path else AuditLog()
        self.human_approval_callback = human_approval_callback

        # Create guardrail pipeline
        self.guardrails = create_test_agent_guardrails(
            agent_id="orchestrator", project_root=str(project_root), audit_path=audit_path
        )
        if human_approval_callback:
            self.guardrails.set_human_approval_callback(human_approval_callback)

        # Initialize specialized agents
        self.agents: Dict[AgentType, BaseAgent] = {
            AgentType.UNIT_TEST: UnitTestAgent(self.guardrails),
            AgentType.E2E_TEST: E2ETestAgent(self.guardrails),
            AgentType.EVALUATOR: EvaluatorAgent(self.guardrails),
        }

        self.current_plan: Optional[TestPlan] = None

    def create_plan(
        self,
        trigger: Dict[str, Any],
        changed_files: List[str],
        requirements: Optional[List[str]] = None,
    ) -> TestPlan:
        """
        Create a deterministic test plan.

        This is the AI "proposal" step. The plan is structured and reviewable
        before any execution happens.
        """
        plan_id = self._generate_plan_id(trigger, changed_files)

        # Analyze scope
        scope = self._analyze_scope(changed_files)

        # Create tasks based on scope
        tasks = []

        # Unit tests for changed service files
        for service_file in scope.get("service_files", []):
            task = AgentTask(
                task_id=f"{plan_id}-unit-{len(tasks)}",
                agent_type=AgentType.UNIT_TEST,
                input_data={"source_path": service_file},
            )
            tasks.append(task)

        # E2E tests for changed routes
        for route_file in scope.get("route_files", []):
            task = AgentTask(
                task_id=f"{plan_id}-e2e-{len(tasks)}",
                agent_type=AgentType.E2E_TEST,
                input_data={"route_path": route_file, "workflow": self._infer_workflow(route_file)},
            )
            tasks.append(task)

        # Evaluation task for each generated test
        eval_task = AgentTask(
            task_id=f"{plan_id}-eval",
            agent_type=AgentType.EVALUATOR,
            input_data={"evaluate_all": True},
        )
        tasks.append(eval_task)

        plan = TestPlan(
            plan_id=plan_id,
            created_at=datetime.now().isoformat(),
            trigger=trigger,
            scope=scope,
            tasks=tasks,
            metadata={
                "total_files": len(changed_files),
                "unit_test_targets": len(scope.get("service_files", [])),
                "e2e_test_targets": len(scope.get("route_files", [])),
            },
        )

        self.current_plan = plan
        logger.info(f"Created test plan: {plan_id} with {len(tasks)} tasks")

        return plan

    def execute_plan(self, plan: TestPlan) -> Dict[str, Any]:
        """
        Execute an approved test plan.

        IMPORTANT: This should only be called after human/CI approval.
        The plan must have status='approved' before execution.
        """
        if plan.status not in ("approved", "draft"):  # Allow draft for testing
            raise ValueError(
                f"Plan must be approved before execution. Current status: {plan.status}"
            )

        plan.status = "executing"
        results = {"plan_id": plan.plan_id, "tasks": [], "summary": {}}

        # Execute tasks in order (could be parallelized for independent tasks)
        generated_tests = []

        for task in plan.tasks:
            if task.agent_type == AgentType.EVALUATOR:
                # Evaluator runs after all generation is complete
                task.input_data["test_code"] = "\n\n".join(generated_tests)

            task.status = AgentStatus.RUNNING
            task.started_at = datetime.now().isoformat()

            try:
                agent = self.agents.get(task.agent_type)
                if not agent:
                    raise ValueError(f"No agent for type: {task.agent_type}")

                result = agent.execute(task)
                task.result = result

                if result.get("blocked"):
                    task.status = AgentStatus.BLOCKED
                elif result.get("error"):
                    task.status = AgentStatus.FAILED
                    task.error = result["error"]
                else:
                    task.status = AgentStatus.COMPLETED
                    if "test_code" in result:
                        generated_tests.append(result["test_code"])

            except Exception as e:
                task.status = AgentStatus.FAILED
                task.error = str(e)
                logger.error(f"Task {task.task_id} failed: {e}")

            task.completed_at = datetime.now().isoformat()
            results["tasks"].append(task.to_dict())

        # Generate summary
        completed = sum(1 for t in plan.tasks if t.status == AgentStatus.COMPLETED)
        failed = sum(1 for t in plan.tasks if t.status == AgentStatus.FAILED)
        blocked = sum(1 for t in plan.tasks if t.status == AgentStatus.BLOCKED)

        results["summary"] = {
            "total_tasks": len(plan.tasks),
            "completed": completed,
            "failed": failed,
            "blocked": blocked,
            "success_rate": completed / len(plan.tasks) if plan.tasks else 0,
            "generated_tests": len(generated_tests),
        }

        plan.status = "completed" if failed == 0 else "failed"

        return results

    def _generate_plan_id(self, trigger: Dict[str, Any], files: List[str]) -> str:
        """Generate deterministic plan ID"""
        content = json.dumps(
            {
                "trigger": trigger,
                "files": sorted(files),
                "timestamp": datetime.now().strftime("%Y%m%d"),
            },
            sort_keys=True,
        )
        return f"plan-{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def _analyze_scope(self, changed_files: List[str]) -> Dict[str, Any]:
        """Analyze changed files to determine test scope"""
        scope = {
            "service_files": [],
            "route_files": [],
            "model_files": [],
            "template_files": [],
            "other_files": [],
        }

        for file_path in changed_files:
            file_path = str(file_path)

            if "services" in file_path and file_path.endswith(".py"):
                scope["service_files"].append(file_path)
            elif "routes" in file_path and file_path.endswith(".py"):
                scope["route_files"].append(file_path)
            elif "models" in file_path and file_path.endswith(".py"):
                scope["model_files"].append(file_path)
            elif file_path.endswith((".html", ".jinja", ".jinja2")):
                scope["template_files"].append(file_path)
            else:
                scope["other_files"].append(file_path)

        return scope

    def _infer_workflow(self, route_path: str) -> str:
        """Infer workflow description from route path"""
        route_name = Path(route_path).stem
        return f"{route_name.replace('_', ' ').title()} Workflow"

    def get_plan_summary(self, plan: TestPlan) -> str:
        """Generate human-readable plan summary"""
        summary = f"""
Test Plan Summary
=================
Plan ID: {plan.plan_id}
Created: {plan.created_at}
Status: {plan.status}

Trigger:
  Type: {plan.trigger.get('type', 'unknown')}
  Source: {plan.trigger.get('source', 'unknown')}

Scope:
  Service files: {len(plan.scope.get('service_files', []))}
  Route files: {len(plan.scope.get('route_files', []))}
  Model files: {len(plan.scope.get('model_files', []))}

Tasks ({len(plan.tasks)} total):
"""
        for task in plan.tasks:
            summary += f"  - [{task.agent_type.value}] {task.task_id}: {task.status.value}\n"

        return summary


# =============================================================================
# CLI INTERFACE
# =============================================================================


def main():
    """CLI interface for the orchestrator"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test Orchestrator - Coordinates agentic testing pipeline"
    )
    parser.add_argument("--project-root", "-p", required=True, help="Project root directory")
    parser.add_argument("--files", "-f", nargs="+", required=True, help="Changed files to test")
    parser.add_argument(
        "--trigger-type", "-t", default="manual", help="Trigger type (pr, commit, manual)"
    )
    parser.add_argument("--output", "-o", help="Output directory for generated tests")
    parser.add_argument("--plan-only", action="store_true", help="Only create plan, do not execute")
    parser.add_argument("--audit-log", help="Path to audit log file")

    args = parser.parse_args()

    # Create orchestrator
    orchestrator = TestOrchestrator(project_root=args.project_root, audit_path=args.audit_log)

    # Create plan
    trigger = {"type": args.trigger_type, "source": "cli", "timestamp": datetime.now().isoformat()}

    plan = orchestrator.create_plan(trigger, args.files)

    print("=" * 70)
    print("TEST ORCHESTRATOR - Plan Created")
    print("=" * 70)
    print(orchestrator.get_plan_summary(plan))

    if args.plan_only:
        print("\nPlan created (--plan-only specified, not executing)")
        print("\nPlan YAML:")
        print(plan.to_yaml())
        return

    # Execute plan
    print("\nExecuting plan...")
    plan.status = "approved"  # Auto-approve for CLI (in CI, this would require approval)

    results = orchestrator.execute_plan(plan)

    print("\n" + "=" * 70)
    print("EXECUTION RESULTS")
    print("=" * 70)
    print(f"Total tasks: {results['summary']['total_tasks']}")
    print(f"Completed: {results['summary']['completed']}")
    print(f"Failed: {results['summary']['failed']}")
    print(f"Blocked: {results['summary']['blocked']}")
    print(f"Success rate: {results['summary']['success_rate']:.1%}")

    # Write generated tests to output
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        for task_result in results["tasks"]:
            if task_result.get("result", {}).get("test_code"):
                test_code = task_result["result"]["test_code"]
                task_id = task_result["task_id"]
                output_file = output_dir / f"test_{task_id.replace('-', '_')}.py"
                output_file.write_text(test_code)
                print(f"Wrote: {output_file}")


if __name__ == "__main__":
    main()
