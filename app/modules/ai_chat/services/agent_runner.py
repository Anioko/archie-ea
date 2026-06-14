"""
AgentRunner: ReAct loop for AI Chat tool use.

Flow per turn:
  1. Build system prompt (agent framing + live domain context)
  2. Call LLM with tool schemas
  3. If response has tool_calls → execute each → feed results back → repeat
  4. If response is text-only → return final response
  5. Cap at MAX_ITERATIONS to prevent runaway chains

Supports Anthropic (Claude) and OpenAI providers.
Tools marked 'approve' tier are queued for user confirmation — not executed.
"""

import json
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 8

# Agent-mode system prompt prefix injected before domain context.
_AGENT_PREFIX = """You are an Enterprise Architecture Copilot with DIRECT WRITE ACCESS
to the architecture repository. You do not give advice for humans to act on — you act.

WHAT YOU CAN DO (27 tools available):
Phase A — Motivation: create_driver, create_goal, create_constraint
Phase B-D — Architecture: create_requirement, link_application_to_solution, link_vendor_product,
             link_capability_to_solution, create_archimate_element, create_archimate_relationship
Phase D — ArchiMate: run_inference_engine, diagnose_chain, explain_element, simulate_impact
Phase E — Options: create_option, mark_option_recommended
Phase G — Governance: submit_for_arb_review (requires confirmation)
Solution state: get_solution_summary, get_completeness_score, update_solution_fields,
                update_solution_phase, search_archimate_elements, find_applications,
                query_capability_gaps
Portfolio: update_application_status (requires confirmation)
Blueprint: generate_blueprint_narrative (requires confirmation)

HOW TO OPERATE:
1. When the user asks to create, link, map, update, or submit — CALL THE TOOL. Do not describe it.
2. If an entity name is ambiguous, ask the user to clarify BEFORE calling a write tool.
3. After each successful tool call, confirm what was done in plain English.
4. For 'approve' tier tools, state exactly what you will do and let the confirmation card handle it.
5. Never fabricate IDs. Always use names — the system resolves them to IDs.
6. If solution_id is in the ACTIVE SOLUTION CONTEXT below, pass it to all tools automatically.

LIVE ARCHITECTURE CONTEXT:
"""


class AgentRunner:
    """
    Orchestrates the LLM tool-use loop for a single user turn.

    Parameters
    ----------
    user_id : int
        The current user's DB ID (used for ownership/audit on writes).
    yield_event : callable, optional
        SSE event callback: yield_event({"type": "...", "data": ...}).
        If None, events are discarded (non-streaming mode).
    """

    def __init__(self, user_id: int, yield_event: Optional[Callable] = None):
        self.user_id = user_id
        self._emit = yield_event or (lambda _e: None)

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    def run(
        self,
        user_message: str,
        domain: str = "general",
        context: Optional[dict] = None,
        persona: Optional[str] = None,
        requested_model: Optional[str] = None,
        stream_mode: bool = False,
    ) -> dict:
        """
        Execute the full ReAct loop for one user message.

        Returns
        -------
        dict with keys:
          response         : str   — final LLM text to show the user
          actions_taken    : list  — successfully executed tool calls
          pending_approvals: list  — 'approve' tier tools queued for confirmation
          error            : str   — set only on fatal failure
        """
        from app.modules.ai_chat.services.llm_service_impl import LLMService
        from app.modules.ai_chat.tools.executor import ToolCall, ToolExecutor
        from app.modules.ai_chat.tools.registry import TOOL_SCHEMAS, TOOL_SCHEMA_BY_NAME

        # Build system prompt with live domain context
        system_prompt = self._build_system_prompt(domain, context, persona, user_message=user_message)

        # Get provider, model, and first available API key
        try:
            provider, model = LLMService._get_configured_provider()
            if requested_model:
                model = requested_model
            api_keys = LLMService._get_all_api_keys(provider)
            if not api_keys:
                return self._fallback("No API keys configured for provider: " + provider)
            api_key = api_keys[0]
        except Exception as e:
            logger.warning("AgentRunner: provider selection failed: %s", e)
            return self._fallback(str(e))

        # Verify provider supports tool use
        # openrouter and deepseek use OpenAI-compatible API with tool calling
        OPENAI_COMPAT_PROVIDERS = {"openrouter", "deepseek"}
        if provider not in ("anthropic", "openai") and provider not in OPENAI_COMPAT_PROVIDERS:
            logger.info(
                "AgentRunner: provider '%s' does not support tool use — falling back to text mode",
                provider,
            )
            return self._text_only_fallback(
                user_message, system_prompt, provider, model, api_key, LLMService
            )

        # Resolve base_url for OpenAI-compatible third-party providers
        _PROVIDER_BASE_URLS = {
            "openrouter": "https://openrouter.ai/api/v1",
            "deepseek": "https://api.deepseek.com/v1",
        }
        base_url = _PROVIDER_BASE_URLS.get(provider)

        # Build tool schemas for the provider
        tool_schemas = self._build_tool_schemas(provider, TOOL_SCHEMAS)

        # Initialise message history
        messages = [{"role": "user", "content": user_message}]
        executor = ToolExecutor(self.user_id)
        actions_taken = []
        pending_approvals = []

        for iteration in range(MAX_ITERATIONS):
            # Call LLM
            try:
                llm_resp = self._call_llm(
                    provider, model, api_key, system_prompt, messages, tool_schemas,
                    stream=stream_mode,
                    base_url=base_url,
                )
            except Exception as e:
                logger.exception("AgentRunner LLM call failed (iteration %d)", iteration)
                return self._fallback(f"LLM call failed: {e}")

            # Text-only response — we're done
            if not llm_resp.get("tool_calls"):
                return {
                    "response": llm_resp.get("text", ""),
                    "actions_taken": actions_taken,
                    "pending_approvals": pending_approvals,
                }

            # Process each tool call
            tool_results = []
            for tc_raw in llm_resp["tool_calls"]:
                tc = ToolCall(
                    id=tc_raw["id"],
                    name=tc_raw["name"],
                    arguments=tc_raw["arguments"],
                )
                schema = TOOL_SCHEMA_BY_NAME.get(tc.name, {})

                if schema.get("tier") == "approve":
                    # Queue for user approval — destructive operations always need confirmation
                    approval_id = self._queue_approval(tc)
                    pending_approvals.append({
                        "approval_id": approval_id,
                        "tool": tc.name,
                        "arguments": tc.arguments,
                        "summary": self._approval_summary(tc),
                    })
                    result = {
                        "success": False,
                        "pending_approval": True,
                        "approval_id": approval_id,
                        "message": (
                            f"Action queued for confirmation (approval #{approval_id}). "
                            "The user must approve before this executes."
                        ),
                    }
                    self._emit({"type": "approval_queued", "tool": tc.name, "approval_id": approval_id})
                else:
                    # Auto-execute
                    self._emit({"type": "tool_start", "tool": tc.name, "args": tc.arguments})
                    result = executor.execute(tc)
                    self._emit({"type": "tool_result", "tool": tc.name, "result": result})

                    if result.get("success"):
                        actions_taken.append({
                            "tool": tc.name,
                            "arguments": tc.arguments,
                            "result": result.get("result"),
                            "message": result.get("message"),
                        })

                tool_results.append((tc_raw, result))

            # Feed results back into messages for next iteration
            messages = self._append_tool_results(provider, messages, llm_resp, tool_results)

        # Hit iteration cap
        logger.warning("AgentRunner hit MAX_ITERATIONS=%d for user_id=%s", MAX_ITERATIONS, self.user_id)
        return {
            "response": (
                "I've completed the available steps. Here's what was done:\n"
                + "\n".join(f"- {a['message']}" for a in actions_taken)
                if actions_taken
                else "I reached the action limit without completing all steps. Please try again with a simpler request."
            ),
            "actions_taken": actions_taken,
            "pending_approvals": pending_approvals,
        }

    # ------------------------------------------------------------------ #
    # System prompt construction                                           #
    # ------------------------------------------------------------------ #

    def _build_system_prompt(self, domain: str, context: Optional[dict], persona: Optional[str], user_message: str = "") -> str:
        """Build agent system prompt: agent prefix + solution context + live domain context."""
        # Inject solution context if present (blueprint panel provides this)
        solution_block = ""
        if context and context.get("solution_id"):
            solution_block = (
                f"\nACTIVE SOLUTION CONTEXT:\n"
                f"  Solution ID: {context['solution_id']}\n"
                f"  Name: {context.get('solution_name', 'Unknown')}\n"
                f"  ADM Phase: {context.get('current_phase', 'A')}\n"
                f"All create/link tools default to solution_id={context['solution_id']} "
                f"unless the user specifies otherwise.\n"
            )

        # Portfolio context — compact snapshot of related solutions
        portfolio_block = ""
        if context and context.get("solution_id"):
            try:
                from app.modules.ai_chat.services.portfolio_context import PortfolioContextBuilder
                portfolio_block = "\n" + PortfolioContextBuilder().build(
                    solution_id=context["solution_id"],
                    user_id=self.user_id,
                    question=user_message,
                )
            except Exception as _pb_err:
                logger.debug("AgentRunner: portfolio context failed: %s", _pb_err)

        ctx_block = ""
        try:
            from app.modules.ai_chat.services.multi_domain_chat_service import MultiDomainChatService
            svc = MultiDomainChatService()
            ctx_result = svc.get_domain_context(domain, context or {})
            if ctx_result.get("success"):
                raw_ctx = ctx_result.get("context", {})
                # Compact serialisation — don't dump the full context blob
                ctx_block = json.dumps(raw_ctx, default=str)[:6000]
        except Exception as e:
            logger.debug("AgentRunner: context build failed: %s", e)

        persona_note = ""
        if persona:
            persona_note = f"\nYou are operating as: {persona.replace('_', ' ').title()}.\n"

        return _AGENT_PREFIX + solution_block + portfolio_block + ctx_block + persona_note

    # ------------------------------------------------------------------ #
    # Provider-specific tool schema conversion                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_tool_schemas(provider: str, schemas: list) -> list:
        if provider == "anthropic":
            return [
                {
                    "name": s["name"],
                    "description": s["description"],
                    "input_schema": s["parameters"],
                }
                for s in schemas
            ]
        else:  # openai
            return [
                {
                    "type": "function",
                    "function": {
                        "name": s["name"],
                        "description": s["description"],
                        "parameters": s["parameters"],
                    },
                }
                for s in schemas
            ]

    # ------------------------------------------------------------------ #
    # LLM call (tool-enabled)                                             #
    # ------------------------------------------------------------------ #

    def _call_llm(
        self,
        provider: str,
        model: str,
        api_key: str,
        system_prompt: str,
        messages: list,
        tools: list,
        stream: bool = False,
        base_url: str = None,
    ) -> dict:
        """
        Call the LLM with tool schemas.  Returns normalised dict:
          {"text": str|None, "tool_calls": list, "raw": raw_response}
        """
        if provider == "anthropic":
            if stream:
                return self._call_anthropic_streaming(model, api_key, system_prompt, messages, tools)
            return self._call_anthropic(model, api_key, system_prompt, messages, tools)
        else:
            if stream:
                return self._call_openai_streaming(model, api_key, system_prompt, messages, tools, base_url=base_url)
            return self._call_openai(model, api_key, system_prompt, messages, tools, base_url=base_url)

    def _call_anthropic(self, model, api_key, system_prompt, messages, tools) -> dict:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
        max_tokens = 8192 if "sonnet" in model or "opus" in model else 4096

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
            tools=tools,
            tool_choice={"type": "auto"},
        )

        text = None
        tool_calls = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })
            elif block.type == "text":
                text = block.text

        return {"text": text, "tool_calls": tool_calls, "raw": response}

    def _call_anthropic_streaming(self, model, api_key, system_prompt, messages, tools) -> dict:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
        max_tokens = 8192 if "sonnet" in model or "opus" in model else 4096

        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
            tools=tools,
            tool_choice={"type": "auto"},
        ) as stream:
            for text in stream.text_stream:
                self._emit({"type": "token", "text": text})
            final = stream.get_final_message()

        text = None
        tool_calls = []
        for block in final.content:
            if block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })
            elif block.type == "text":
                text = block.text

        return {"text": text, "tool_calls": tool_calls, "raw": final}

    def _call_openai(self, model, api_key, system_prompt, messages, tools, base_url=None) -> dict:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=90.0)
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        # Newer OpenAI models (o1, o3, gpt-5.x) require max_completion_tokens; all other models
        # accept it too (it supersedes the deprecated max_tokens parameter).
        _token_limit = 8192 if ("gpt-4" in model or "gpt-5" in model) else 4096
        response = client.chat.completions.create(
            model=model,
            messages=full_messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.0,
            max_completion_tokens=_token_limit,
        )

        msg = response.choices[0].message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

        return {"text": msg.content, "tool_calls": tool_calls, "raw": response}

    def _call_openai_streaming(self, model, api_key, system_prompt, messages, tools, base_url=None) -> dict:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=90.0)
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        text_acc = ""
        tool_calls_acc: dict = {}

        # Newer OpenAI models (o1, o3, gpt-5.x) require max_completion_tokens.
        _token_limit = 8192 if ("gpt-4" in model or "gpt-5" in model) else 4096
        with client.chat.completions.create(
            model=model,
            messages=full_messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.0,
            max_completion_tokens=_token_limit,
            stream=True,
        ) as stream:
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    text_acc += delta.content
                    self._emit({"type": "token", "text": delta.content})
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.id:
                            tool_calls_acc[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls_acc[idx]["name"] += tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc.function.arguments

        tool_calls = []
        for idx in sorted(tool_calls_acc.keys()):
            tc = tool_calls_acc[idx]
            try:
                arguments = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append({"id": tc["id"], "name": tc["name"], "arguments": arguments})

        return {"text": text_acc or None, "tool_calls": tool_calls, "raw": None}

    # ------------------------------------------------------------------ #
    # Message history management                                          #
    # ------------------------------------------------------------------ #

    def _append_tool_results(
        self, provider: str, messages: list, llm_resp: dict, tool_results: list
    ) -> list:
        """Append assistant tool-use blocks and tool results into message history."""
        messages = list(messages)

        if provider == "anthropic":
            # Append the full raw content blocks from the assistant
            messages.append({
                "role": "assistant",
                "content": llm_resp["raw"].content,
            })
            # Append tool results as a user message
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tc_raw["id"],
                        "content": json.dumps(result, default=str),
                    }
                    for tc_raw, result in tool_results
                ],
            })
        else:  # openai
            # raw is None in streaming mode — reconstruct assistant message from accumulated fields
            if llm_resp.get("raw") is not None:
                raw_msg = llm_resp["raw"].choices[0].message
                assistant_content = raw_msg.content
            else:
                assistant_content = llm_resp.get("text")
            messages.append({
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": [
                    {
                        "id": tc_raw["id"],
                        "type": "function",
                        "function": {
                            "name": tc_raw["name"],
                            "arguments": json.dumps(tc_raw["arguments"]),
                        },
                    }
                    for tc_raw, _ in tool_results
                ],
            })
            for tc_raw, result in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_raw["id"],
                    "content": json.dumps(result, default=str),
                })

        return messages

    # ------------------------------------------------------------------ #
    # Approval queue                                                       #
    # ------------------------------------------------------------------ #

    def _queue_approval(self, tc: "ToolCall") -> int:
        """Write a pending AIChatCRUDApproval record and return its ID."""
        from datetime import datetime, timedelta
        from app.models.ai_chat_crud_approval import AIChatCRUDApproval, ApprovalStatus
        from app import db

        record = AIChatCRUDApproval(
            user_id=self.user_id,
            operation_type="tool_use",
            entity_type=tc.name,
            original_command=tc.name,
            operation_payload=json.dumps(tc.arguments),
            summary=self._approval_summary(tc),
            status=ApprovalStatus.PENDING,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.session.add(record)
        db.session.commit()
        return record.id

    @staticmethod
    def _approval_summary(tc: "ToolCall") -> str:
        summaries = {
            "update_application_status": (
                "Change application '{application_name}' status to '{new_status}'. Reason: {rationale}"
            ),
            "submit_for_arb_review": (
                "Submit solution '{solution_name}' for ARB review at {phase} phase."
            ),
            "generate_blueprint_narrative": (
                "Generate AI narrative for section '{section_id}' of solution {solution_id}. "
                "This will overwrite any existing text in that section."
            ),
        }
        template = summaries.get(tc.name, f"Execute {tc.name} with args: {tc.arguments}")
        try:
            return template.format(**tc.arguments)
        except KeyError:
            return template

    # ------------------------------------------------------------------ #
    # Fallbacks                                                           #
    # ------------------------------------------------------------------ #

    def _fallback(self, reason: str) -> dict:
        return {
            "response": (
                "I couldn't complete that action due to a configuration issue. "
                "Please contact your administrator."
            ),
            "actions_taken": [],
            "pending_approvals": [],
            "error": reason,
        }

    def _text_only_fallback(
        self, message: str, system_prompt: str, provider: str, model: str, api_key: str, LLMService
    ) -> dict:
        """Run a plain text call (no tools) for unsupported providers."""
        try:
            prompt = system_prompt + "\n\nUser: " + message
            text, _ = LLMService._call_llm_with_failover(
                prompt=prompt, model=model, provider=provider
            )
            return {
                "response": text,
                "actions_taken": [],
                "pending_approvals": [],
            }
        except Exception as e:
            return self._fallback(str(e))
