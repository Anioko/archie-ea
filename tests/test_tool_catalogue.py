"""Tool catalogue contract tests (TB-0088) and fail-closed confirmation (TB-0091).

TB-0088:
  Every registry schema carries surfaces, route, fenced and risk_class fields.
  Each field is validated for type and internal consistency.

TB-0091:
  With the approval switch OFF (auto_execute=False), every mutating tool still
  requires confirmation, closing the 17 tier="auto" mutating tools that would
  otherwise run unconfirmed.
"""

import pytest

from app.modules.ai_chat.tools.registry import TOOL_SCHEMAS, TOOL_SCHEMA_BY_NAME


# --------------------------------------------------------------------------- #
# TB-0088 — every tool carries surfaces, route, fenced, risk_class           #
# --------------------------------------------------------------------------- #


VALID_RISK_CLASSES = {"read", "propose", "write", "external_action"}
VALID_SURFACES = {"chat", "blueprint"}


class TestEveryToolHasNewFields:
    """Every schema in the catalogue must declare the four new fields
    explicitly. A tool that omits any of them is a contract break."""

    def test_every_tool_has_surfaces(self):
        missing = [t["name"] for t in TOOL_SCHEMAS if "surfaces" not in t]
        assert missing == [], f"tools missing 'surfaces': {missing}"

    def test_every_tool_has_route(self):
        missing = [t["name"] for t in TOOL_SCHEMAS if "route" not in t]
        assert missing == [], f"tools missing 'route': {missing}"

    def test_every_tool_has_fenced(self):
        missing = [t["name"] for t in TOOL_SCHEMAS if "fenced" not in t]
        assert missing == [], f"tools missing 'fenced': {missing}"

    def test_every_tool_has_risk_class(self):
        missing = [t["name"] for t in TOOL_SCHEMAS if "risk_class" not in t]
        assert missing == [], f"tools missing 'risk_class': {missing}"

    def test_fields_have_correct_types(self):
        bad = []
        for t in TOOL_SCHEMAS:
            name = t["name"]
            if not isinstance(t.get("surfaces"), list):
                bad.append(f"{name}: surfaces is not a list")
            elif not all(isinstance(s, str) for s in t.get("surfaces", [])):
                bad.append(f"{name}: surfaces items are not strings")
            if not isinstance(t.get("route"), str):
                bad.append(f"{name}: route is not a string")
            if not isinstance(t.get("fenced"), bool):
                bad.append(f"{name}: fenced is not a bool")
            if t.get("risk_class") not in VALID_RISK_CLASSES:
                bad.append(f"{name}: risk_class '{t.get('risk_class')}' not in {VALID_RISK_CLASSES}")
        assert bad == [], "\n".join(bad)

    def test_surfaces_contain_only_valid_values(self):
        bad = []
        for t in TOOL_SCHEMAS:
            invalid = set(t.get("surfaces", [])) - VALID_SURFACES
            if invalid:
                bad.append(f"{t['name']}: invalid surfaces {invalid}")
        assert bad == [], "\n".join(bad)

    def test_surfaces_list_is_non_empty(self):
        empty = [t["name"] for t in TOOL_SCHEMAS if not t.get("surfaces")]
        assert empty == [], f"tools with empty surfaces: {empty}"

    def test_route_matches_tool_name(self):
        """Each tool's route should match its tool name."""
        mismatched = [
            t["name"] for t in TOOL_SCHEMAS
            if t.get("route") not in (t["name"], None)
        ]
        # Allow generated element tools whose route is the full candidate_name
        # (which equals the tool name by construction).
        assert not mismatched, f"tools where route != name: {mismatched}"


class TestRiskClassConsistency:
    """risk_class must be consistent with the mutates flag and the tier."""

    def test_write_tools_mutate(self):
        """Every risk_class='write' tool must declare mutates=True."""
        bad = [
            t["name"] for t in TOOL_SCHEMAS
            if t.get("risk_class") == "write" and t.get("mutates") is not True
        ]
        assert bad == [], f"write-classified tools not flagged mutating: {bad}"

    def test_read_tools_do_not_mutate(self):
        """Every risk_class='read' tool must declare mutates=False."""
        bad = [
            t["name"] for t in TOOL_SCHEMAS
            if t.get("risk_class") == "read" and t.get("mutates") is not False
        ]
        assert bad == [], f"read-classified tools flagged mutating: {bad}"

    def test_propose_tools_do_not_mutate(self):
        """risk_class='propose' tools queue changes but don't directly write."""
        bad = [
            t["name"] for t in TOOL_SCHEMAS
            if t.get("risk_class") == "propose" and t.get("mutates") is not False
        ]
        assert bad == [], f"propose-classified tools flagged mutating: {bad}"

    def test_external_action_tools_mutate(self):
        """risk_class='external_action' tools trigger side effects."""
        bad = [
            t["name"] for t in TOOL_SCHEMAS
            if t.get("risk_class") == "external_action" and t.get("mutates") is not True
        ]
        assert bad == [], f"external_action tools not flagged mutating: {bad}"

    def test_external_action_tools_always_approve_tier(self):
        """risk_class='external_action' tools must be tier='approve'."""
        bad = [
            t["name"] for t in TOOL_SCHEMAS
            if t.get("risk_class") == "external_action" and t.get("tier") != "approve"
        ]
        assert bad == [], f"external_action tools not tier='approve': {bad}"


class TestFencedConsistency:
    """fenced=True indicates LLM-generated output that should be fenced."""

    def test_fenced_tools_are_not_write(self):
        """fenced=True tools generate content (LLM-produced), not direct writes."""
        for t in TOOL_SCHEMAS:
            if t.get("fenced") and t.get("risk_class") == "write":
                # generate_blueprint_narrative is fenced AND write — the narrative
                # is LLM-generated (fenced) but overwrites section text (write).
                # This is the known exception.
                if t["name"] != "generate_blueprint_narrative":
                    pytest.fail(f"{t['name']}: fenced=True but risk_class='write'")

    def test_fenced_is_always_a_bool(self):
        bad = [t["name"] for t in TOOL_SCHEMAS if not isinstance(t.get("fenced"), bool)]
        assert bad == [], f"tools with non-bool fenced: {bad}"


# --------------------------------------------------------------------------- #
# TB-0091 — fail-closed confirmation                                          #
# --------------------------------------------------------------------------- #


class TestFailClosedConfirmation:
    """With the approval switch OFF (auto_execute=False), every mutating tool
    must require confirmation regardless of its tier.

    The 17 hand-written tools with tier='auto' and mutates=True are the ones
    most at risk of running unconfirmed — this test pins each one.
    """

    # The 17 hand-written tools with tier='auto' and mutates=True that
    # would run unconfirmed if _should_queue only checked tier.
    MUTATING_AUTO_TOOLS = sorted([
        name for name, schema in TOOL_SCHEMA_BY_NAME.items()
        if schema.get("mutates") is True
        and schema.get("tier") == "auto"
    ])

    def test_seventeen_mutating_auto_tools_exist(self):
        """Assert exactly 17 hand-written tier='auto' mutating tools exist, not
        counting the 54 generated element tools which are all tier='approve'."""
        assert len(self.MUTATING_AUTO_TOOLS) == 17, (
            f"Expected 17 mutating auto tools, got {len(self.MUTATING_AUTO_TOOLS)}: "
            f"{self.MUTATING_AUTO_TOOLS}"
        )

    @pytest.mark.parametrize("name", MUTATING_AUTO_TOOLS)
    def test_mutating_auto_tool_queues_when_auto_execute_off(self, name):
        """Each of the 17 tools queues for confirmation when auto_execute=False,
        using the same _should_queue logic AgentRunner relies on."""
        from app.modules.ai_chat.services.agent_runner import AgentRunner

        schema = TOOL_SCHEMA_BY_NAME[name]
        assert AgentRunner._should_queue(schema, auto_execute=False) is True, (
            f"{name} must queue when auto_execute=False"
        )

    @pytest.mark.parametrize("name", MUTATING_AUTO_TOOLS)
    def test_mutating_auto_tool_queues_even_when_auto_execute_on(self, name):
        """Each of the 17 tools queues for confirmation even when auto_execute=True,
        because _should_queue returns True for any tool with mutates=True or
        risk_class in {'write', 'external_action'} regardless of auto_execute.

        This is the TB-0091 guard: with the approval switch off, every mutating
        tool still requires confirmation, closing the 17 tier='auto' mutating
        tools that would otherwise run unconfirmed.
        """
        from app.modules.ai_chat.services.agent_runner import AgentRunner

        schema = TOOL_SCHEMA_BY_NAME[name]
        assert AgentRunner._should_queue(schema, auto_execute=True) is True, (
            f"{name} must queue even when auto_execute=True"
        )

    def test_approve_tier_tools_always_queue(self):
        """Tools with tier='approve' always queue regardless of auto_execute."""
        from app.modules.ai_chat.services.agent_runner import AgentRunner

        approve_tools = [
            t for t in TOOL_SCHEMAS if t.get("tier") == "approve"
        ]
        for t in approve_tools:
            assert AgentRunner._should_queue(t, auto_execute=True) is True, (
                f"{t['name']}: approve-tier tool must queue even with auto_execute on"
            )
            assert AgentRunner._should_queue(t, auto_execute=False) is True, (
                f"{t['name']}: approve-tier tool must queue with auto_execute off"
            )

    def test_read_tools_never_queue(self):
        """Read-tools must never queue regardless of auto_execute."""
        from app.modules.ai_chat.services.agent_runner import AgentRunner

        read_tools = [
            t for t in TOOL_SCHEMAS if t.get("risk_class") == "read"
        ]
        for t in read_tools:
            assert AgentRunner._should_queue(t, auto_execute=True) is False, (
                f"{t['name']}: read tool must not queue with auto_execute on"
            )
            assert AgentRunner._should_queue(t, auto_execute=False) is False, (
                f"{t['name']}: read tool must not queue with auto_execute off"
            )


# --------------------------------------------------------------------------- #
# Per-tool contract tests — every tool's exact field values                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name,expected",
    [
        ("build_architecture_plan", {"surfaces": ["chat"], "route": "build_architecture_plan", "fenced": False, "risk_class": "read"}),
        ("bulk_update_application_status", {"surfaces": ["chat", "blueprint"], "route": "bulk_update_application_status", "fenced": False, "risk_class": "write"}),
        ("create_adr", {"surfaces": ["chat", "blueprint"], "route": "create_adr", "fenced": False, "risk_class": "write"}),
        ("create_archimate_element", {"surfaces": ["chat", "blueprint"], "route": "create_archimate_element", "fenced": False, "risk_class": "write"}),
        ("create_archimate_relationship", {"surfaces": ["chat", "blueprint"], "route": "create_archimate_relationship", "fenced": False, "risk_class": "write"}),
        ("create_constraint", {"surfaces": ["chat", "blueprint"], "route": "create_constraint", "fenced": False, "risk_class": "write"}),
        ("create_contract", {"surfaces": ["chat"], "route": "create_contract", "fenced": False, "risk_class": "write"}),
        ("create_driver", {"surfaces": ["chat", "blueprint"], "route": "create_driver", "fenced": False, "risk_class": "write"}),
        ("create_goal", {"surfaces": ["chat", "blueprint"], "route": "create_goal", "fenced": False, "risk_class": "write"}),
        ("create_option", {"surfaces": ["chat", "blueprint"], "route": "create_option", "fenced": False, "risk_class": "write"}),
        ("create_programme", {"surfaces": ["chat", "blueprint"], "route": "create_programme", "fenced": False, "risk_class": "write"}),
        ("create_requirement", {"surfaces": ["chat", "blueprint"], "route": "create_requirement", "fenced": False, "risk_class": "write"}),
        ("create_risk", {"surfaces": ["chat", "blueprint"], "route": "create_risk", "fenced": False, "risk_class": "write"}),
        ("create_solution", {"surfaces": ["chat", "blueprint"], "route": "create_solution", "fenced": False, "risk_class": "write"}),
        ("create_vendor", {"surfaces": ["chat"], "route": "create_vendor", "fenced": False, "risk_class": "write"}),
        ("diagnose_chain", {"surfaces": ["chat"], "route": "diagnose_chain", "fenced": False, "risk_class": "read"}),
        ("explain_element", {"surfaces": ["chat"], "route": "explain_element", "fenced": False, "risk_class": "read"}),
        ("extract_contract_from_document", {"surfaces": ["chat"], "route": "extract_contract_from_document", "fenced": True, "risk_class": "read"}),
        ("find_applications", {"surfaces": ["chat"], "route": "find_applications", "fenced": False, "risk_class": "read"}),
        ("find_applications_by_capability", {"surfaces": ["chat", "blueprint"], "route": "find_applications_by_capability", "fenced": False, "risk_class": "read"}),
        ("find_technical_capabilities", {"surfaces": ["chat"], "route": "find_technical_capabilities", "fenced": False, "risk_class": "read"}),
        ("generate_blueprint_narrative", {"surfaces": ["chat", "blueprint"], "route": "generate_blueprint_narrative", "fenced": True, "risk_class": "write"}),
        ("get_arb_status", {"surfaces": ["chat"], "route": "get_arb_status", "fenced": False, "risk_class": "read"}),
        ("get_completeness_score", {"surfaces": ["chat", "blueprint"], "route": "get_completeness_score", "fenced": False, "risk_class": "read"}),
        ("get_executive_dashboard", {"surfaces": ["chat"], "route": "get_executive_dashboard", "fenced": False, "risk_class": "read"}),
        ("get_investment_priorities", {"surfaces": ["chat"], "route": "get_investment_priorities", "fenced": False, "risk_class": "read"}),
        ("get_solution_summary", {"surfaces": ["chat", "blueprint"], "route": "get_solution_summary", "fenced": False, "risk_class": "read"}),
        ("infer_schema", {"surfaces": ["chat", "blueprint"], "route": "infer_schema", "fenced": True, "risk_class": "read"}),
        ("link_application_to_capability", {"surfaces": ["chat", "blueprint"], "route": "link_application_to_capability", "fenced": False, "risk_class": "write"}),
        ("link_application_to_solution", {"surfaces": ["chat", "blueprint"], "route": "link_application_to_solution", "fenced": False, "risk_class": "write"}),
        ("link_capability_to_solution", {"surfaces": ["chat", "blueprint"], "route": "link_capability_to_solution", "fenced": False, "risk_class": "write"}),
        ("link_vendor_product", {"surfaces": ["chat", "blueprint"], "route": "link_vendor_product", "fenced": False, "risk_class": "write"}),
        ("mark_option_recommended", {"surfaces": ["chat", "blueprint"], "route": "mark_option_recommended", "fenced": False, "risk_class": "write"}),
        ("merge_capabilities", {"surfaces": ["chat", "blueprint"], "route": "merge_capabilities", "fenced": False, "risk_class": "write"}),
        ("poll_infrastructure", {"surfaces": ["chat"], "route": "poll_infrastructure", "fenced": False, "risk_class": "read"}),
        ("propose_genome_patch", {"surfaces": ["chat"], "route": "propose_genome_patch", "fenced": False, "risk_class": "propose"}),
        ("propose_rationalization", {"surfaces": ["chat"], "route": "propose_rationalization", "fenced": False, "risk_class": "read"}),
        ("query_capability_gaps", {"surfaces": ["chat"], "route": "query_capability_gaps", "fenced": False, "risk_class": "read"}),
        ("record_capability_maturity", {"surfaces": ["chat", "blueprint"], "route": "record_capability_maturity", "fenced": False, "risk_class": "write"}),
        ("run_inference_engine", {"surfaces": ["chat", "blueprint"], "route": "run_inference_engine", "fenced": False, "risk_class": "write"}),
        ("score_rationalization", {"surfaces": ["chat", "blueprint"], "route": "score_rationalization", "fenced": False, "risk_class": "write"}),
        ("search_archimate_elements", {"surfaces": ["chat", "blueprint"], "route": "search_archimate_elements", "fenced": False, "risk_class": "read"}),
        ("search_capabilities_by_problem", {"surfaces": ["chat"], "route": "search_capabilities_by_problem", "fenced": False, "risk_class": "read"}),
        ("simulate_impact", {"surfaces": ["chat"], "route": "simulate_impact", "fenced": False, "risk_class": "read"}),
        ("submit_for_arb_review", {"surfaces": ["chat", "blueprint"], "route": "submit_for_arb_review", "fenced": False, "risk_class": "external_action"}),
        ("update_application_status", {"surfaces": ["chat", "blueprint"], "route": "update_application_status", "fenced": False, "risk_class": "write"}),
        ("update_solution_fields", {"surfaces": ["chat", "blueprint"], "route": "update_solution_fields", "fenced": False, "risk_class": "write"}),
        ("update_solution_phase", {"surfaces": ["chat", "blueprint"], "route": "update_solution_phase", "fenced": False, "risk_class": "write"}),
        ("upsert_license", {"surfaces": ["chat"], "route": "upsert_license", "fenced": False, "risk_class": "write"}),
        ("validate_sap_clean_core", {"surfaces": ["chat", "blueprint"], "route": "validate_sap_clean_core", "fenced": False, "risk_class": "read"}),
        ("verify_codegen", {"surfaces": ["chat", "blueprint"], "route": "verify_codegen", "fenced": False, "risk_class": "read"}),
    ],
)
def test_hand_written_tool_contract(name, expected):
    """Every hand-written tool's surfaces, route, fenced and risk_class match
    the pinned values."""
    schema = TOOL_SCHEMA_BY_NAME.get(name)
    assert schema is not None, f"{name} is not registered"
    for field, expected_value in expected.items():
        assert schema[field] == expected_value, (
            f"{name}.{field}: expected {expected_value!r}, got {schema[field]!r}"
        )


def test_generated_element_tools_have_contract():
    """Every generated element tool has the expected field values."""
    from app.modules.ai_chat.tools.archimate_specs import ELEMENT_SPECS

    # Get element tool schemas by iterating TOOL_SCHEMAS and filtering for
    # archimate_layer (which only generated element tools carry).
    element_tools = {s["name"]: s for s in TOOL_SCHEMAS if "archimate_layer" in s}

    assert len(element_tools) == len(ELEMENT_SPECS), (
        f"Expected {len(ELEMENT_SPECS)} element tools, got {len(element_tools)}"
    )

    for name, schema in sorted(element_tools.items()):
        assert schema["surfaces"] == ["chat", "blueprint"], (
            f"{name}.surfaces: expected ['chat', 'blueprint']"
        )
        assert schema["route"] == name, (
            f"{name}.route: expected {name}"
        )
        assert schema["fenced"] is False, f"{name}.fenced must be False"
        assert schema["risk_class"] == "write", (
            f"{name}.risk_class must be 'write'"
        )