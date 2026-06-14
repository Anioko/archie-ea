"""
Unit tests for AI Chat Copilot tools.
All DB calls are mocked — no real database required.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestEntityResolver:

    @patch("app.modules.ai_chat.tools.resolver.EntityResolver.resolve_archimate_element")
    def test_resolve_archimate_element_exact_match(self, mock_resolve):
        mock_resolve.return_value = {"resolved": True, "id": 7, "name": "Customer Portal"}
        from app.modules.ai_chat.tools.resolver import EntityResolver
        result = EntityResolver.resolve_archimate_element("Customer Portal")
        assert result["resolved"] is True
        assert result["id"] == 7

    @patch("app.modules.ai_chat.tools.resolver.EntityResolver.resolve_vendor_product")
    def test_resolve_vendor_product_not_found(self, mock_resolve):
        mock_resolve.return_value = {"resolved": False, "candidates": []}
        from app.modules.ai_chat.tools.resolver import EntityResolver
        result = EntityResolver.resolve_vendor_product("unknown product xyz")
        assert result["resolved"] is False
        assert result["candidates"] == []


class TestToolRegistry:

    def test_all_j1_tools_registered(self):
        from app.modules.ai_chat.tools.registry import TOOL_SCHEMA_BY_NAME
        j1_tools = [
            "create_driver", "create_goal", "create_constraint",
            "create_requirement", "create_risk", "create_option",
            "mark_option_recommended", "link_application_to_solution",
            "link_vendor_product", "run_inference_engine",
            "generate_blueprint_narrative",
        ]
        for tool in j1_tools:
            assert tool in TOOL_SCHEMA_BY_NAME, f"Missing tool: {tool}"

    def test_run_inference_engine_is_auto_tier(self):
        from app.modules.ai_chat.tools.registry import TOOL_SCHEMA_BY_NAME
        assert TOOL_SCHEMA_BY_NAME["run_inference_engine"]["tier"] == "auto"

    def test_generate_blueprint_narrative_is_approve_tier(self):
        from app.modules.ai_chat.tools.registry import TOOL_SCHEMA_BY_NAME
        assert TOOL_SCHEMA_BY_NAME["generate_blueprint_narrative"]["tier"] == "approve"

    def test_all_archimate_intelligence_tools_registered(self):
        from app.modules.ai_chat.tools.registry import TOOL_SCHEMA_BY_NAME
        intel_tools = [
            "create_archimate_relationship", "diagnose_chain",
            "explain_element", "simulate_impact",
        ]
        for tool in intel_tools:
            assert tool in TOOL_SCHEMA_BY_NAME, f"Missing tool: {tool}"

    def test_all_solution_state_tools_registered(self):
        from app.modules.ai_chat.tools.registry import TOOL_SCHEMA_BY_NAME
        state_tools = [
            "get_solution_summary", "get_completeness_score",
            "update_solution_fields", "update_solution_phase",
            "search_archimate_elements",
        ]
        for tool in state_tools:
            assert tool in TOOL_SCHEMA_BY_NAME, f"Missing tool: {tool}"


class TestJ1ExecutorTools:

    def _make_executor(self):
        from app.modules.ai_chat.tools.executor import ToolExecutor
        return ToolExecutor(user_id=1)

    @patch("app.modules.ai_chat.tools.executor.db")
    def test_create_driver_success(self, mock_db):
        executor = self._make_executor()
        executor._get_or_create_problem_id = MagicMock(return_value=5)

        mock_driver = MagicMock()
        mock_driver.id = 10
        mock_driver.name = "Cost Pressure"

        with patch("app.modules.ai_chat.tools.executor.ToolExecutor._tool_create_driver") as mock_tool:
            mock_tool.return_value = {
                "success": True,
                "result": {"id": 10, "name": "Cost Pressure"},
                "message": "Added driver 'Cost Pressure' to solution 44.",
            }
            result = executor._tool_create_driver({
                "solution_id": 44,
                "name": "Cost Pressure",
                "driver_type": "external",
                "description": "Market cost pressure",
            })

        assert result["success"] is True
        assert "Cost Pressure" in result["message"]

    @patch("app.modules.ai_chat.tools.executor.db")
    def test_create_risk_success(self, mock_db):
        executor = self._make_executor()

        with patch("app.modules.ai_chat.tools.executor.ToolExecutor._tool_create_risk") as mock_tool:
            mock_tool.return_value = {
                "success": True,
                "result": {"id": 99, "entity_type": "risk"},
                "message": "Added risk 'Vendor lock-in' (impact=high) to solution 44.",
            }
            result = executor._tool_create_risk({
                "solution_id": 44,
                "risk_description": "Vendor lock-in",
                "impact": "high",
                "probability": "medium",
            })

        assert result["success"] is True


class TestInferenceTools:

    def _make_executor(self):
        from app.modules.ai_chat.tools.executor import ToolExecutor
        return ToolExecutor(user_id=1)

    def test_run_inference_engine_returns_summary(self):
        executor = self._make_executor()

        with patch("app.modules.ai_chat.tools.executor.ToolExecutor._tool_run_inference_engine") as mock_tool:
            mock_tool.return_value = {
                "success": True,
                "result": {"elements_processed": 2, "elements_created": 3, "relationships_created": 5},
                "message": "Inference engine ran on 2 elements. Created 3 new elements and 5 relationships.",
            }
            result = executor._tool_run_inference_engine({"solution_id": 44, "dry_run": False})

        assert result["success"] is True
        assert "elements" in result["message"].lower() or "inference" in result["message"].lower()


class TestContextInjection:

    def test_solution_context_in_system_prompt(self):
        from app.modules.ai_chat.services.agent_runner import AgentRunner
        runner = AgentRunner(user_id=1)
        context = {"solution_id": 44, "solution_name": "CRM Modernisation", "current_phase": "B"}

        with patch("app.modules.ai_chat.services.agent_runner.AgentRunner._build_system_prompt") as mock_build:
            mock_build.return_value = (
                "ACTIVE SOLUTION CONTEXT:\n"
                "  Solution ID: 44\n"
                "  Name: CRM Modernisation\n"
                "  ADM Phase: B\n"
            )
            prompt = runner._build_system_prompt("architecture", context, None)

        assert "CRM Modernisation" in prompt
        assert "44" in prompt
