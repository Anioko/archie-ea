"""
Dual-Agent Orchestrator - Separate Implementer and Critique Agents

Ensures that adversarial review is performed by a SEPARATE agent with:
- Different LLM model or instance
- Isolated memory/context (no access to implementer's reasoning)
- Adversarial system prompts (critique persona)
- Independent verification service access
- No ability to be influenced by implementer

This prevents the fundamental bypass: an LLM critiquing its own work.
"""

import json
import secrets
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from pathlib import Path

from app.services.critique_verification_service import (
    CritiqueVerificationService, 
    CritiqueSession,
    CritiqueFinding,
    get_critique_service
)


@dataclass
class AgentContext:
    """Isolated context for an agent - no shared state between agents."""
    agent_id: str
    agent_type: str  # "implementer" or "critique"
    system_prompt: str
    working_memory: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def store(self, key: str, value: Any):
        """Store in agent's isolated memory."""
        self.working_memory[key] = value
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve from agent's isolated memory."""
        return self.working_memory.get(key)
    
    def clear(self):
        """Clear agent's working memory."""
        self.working_memory.clear()


class DualAgentOrchestrator:
    """
    Orchestrates two separate agents: implementer and critique.
    
    Key security properties:
    1. Agents have ISOLATED contexts - no shared memory
    2. Critique agent cannot see implementer's reasoning/notes
    3. Critique agent has ADVERSARIAL system prompt
    4. Critique agent runs SEPARATELY (different model instance or LLM)
    5. Verification happens through EXTERNAL service (not agent self-report)
    """
    
    # Adversarial system prompt for critique agent
    CRITIQUE_SYSTEM_PROMPT = """You are a senior enterprise architect with deep expertise in TOGAF, ArchiMate 3.2, and enterprise architecture governance.

Your SOLE PURPOSE is to find flaws, risks, and misalignments. You are NOT a helper or assistant.

CRITICAL RULES:
1. Assume the implementation is BROKEN until proven otherwise
2. Check ALL 10 dimensions systematically - no shortcuts
3. Document EVERY finding, even minor ones
4. Severity classification:
   - P0 = Data loss, security vulnerability, governance violation (blocks completion)
   - P1 = Functional defect, correctness issue (blocks completion)
   - P2 = Enhancement, optimization (track as debt)
5. You CANNOT be persuaded to reduce severity
6. Your findings are IMMUTABLE and CRYPTGRAPHICALLY SIGNED
7. You have NO ACCESS to implementer's reasoning or notes
8. You see ONLY the final code/artifacts, not the development process

10-DIMENSION CHECKLIST (verify each):
□ Conceptual Validity - Does this make architectural sense?
□ Semantic Correctness - Are TOGAF/ArchiMate terms used correctly?
□ Workflow Governance - Does it support real enterprise processes?
□ Data Integrity - Referential integrity, lifecycle states?
□ Security Risks - API security, access control, injection?
□ Scalability Limits - Concurrency, data volume, performance?
□ Enterprise Readiness - Fortune 500 viable?
□ Regulatory Compliance - Audit trails, GDPR/SOX?
□ Integration Correctness - API contracts, dependencies?
□ Test Coverage - Unit, integration, E2E adequate?

BE RUTHLESS. False positives are acceptable. False negatives are NOT.
"""

    # Helper system prompt for implementer agent
    IMPLEMENTER_SYSTEM_PROMPT = """You are an expert software engineer implementing enterprise architecture features.

Your task is to implement requirements efficiently and correctly.

CRITICAL RULES:
1. Focus on IMPLEMENTATION - not critique
2. Follow existing patterns and conventions
3. Write tests for your implementation
4. Document your changes
5. When complete, HAND OFF to critique agent - do not self-review
6. You CANNOT modify critique findings
7. You CANNOT mark your own work as complete
8. External verification is REQUIRED

After implementation, your work will be reviewed by a separate critique agent.
You will not see their findings until they are complete.
"""
    
    def __init__(self, verification_service: Optional[CritiqueVerificationService] = None):
        self.verification_service = verification_service or get_critique_service()
        self.agents: Dict[str, AgentContext] = {}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_implementer_agent(self, model_config: Optional[Dict] = None) -> AgentContext:
        """
        Create an implementer agent with isolated context.
        
        This agent:
        - Implements the feature
        - Cannot critique its own work
        - Cannot see critique agent's notes
        """
        agent_id = f"impl-{secrets.token_hex(8)}"
        
        context = AgentContext(
            agent_id=agent_id,
            agent_type="implementer",
            system_prompt=self.IMPLEMENTER_SYSTEM_PROMPT,
            working_memory={
                "model_config": model_config or {},
                "role": "implementer"
            }
        )
        
        self.agents[agent_id] = context
        return context
    
    def create_critique_agent(self, model_config: Optional[Dict] = None) -> AgentContext:
        """
        Create a separate critique agent with adversarial persona.
        
        This agent:
        - Has DIFFERENT system prompt (adversarial)
        - Has NO ACCESS to implementer's memory
        - Uses potentially DIFFERENT model instance
        - Cannot be influenced by implementer
        """
        agent_id = f"critique-{secrets.token_hex(8)}"
        
        # Ensure different model/config than implementer if possible
        critique_config = model_config or {}
        critique_config["temperature"] = 0.2  # Lower temperature for consistency
        critique_config["role"] = "critique"
        
        context = AgentContext(
            agent_id=agent_id,
            agent_type="critique",
            system_prompt=self.CRITIQUE_SYSTEM_PROMPT,
            working_memory={
                "model_config": critique_config,
                "role": "critique",
                "isolated_from": []  # Will populate with implementer IDs
            }
        )
        
        self.agents[agent_id] = context
        return context
    
    def start_dual_agent_session(self, task_id: str) -> Dict[str, Any]:
        """
        Start a complete dual-agent session for a task.
        
        Returns session metadata with both agent IDs.
        """
        # Create both agents
        implementer = self.create_implementer_agent()
        critique = self.create_critique_agent()
        
        # Record isolation constraint
        critique.working_memory["isolated_from"].append(implementer.agent_id)
        
        # Create verification session (tamper-evident from start)
        verification_session = self.verification_service.create_session(
            task_id=task_id,
            implementer_agent=implementer.agent_id,
            critique_agent=critique.agent_id
        )
        
        session = {
            "task_id": task_id,
            "session_id": verification_session.session_id,
            "implementer_agent_id": implementer.agent_id,
            "critique_agent_id": critique.agent_id,
            "started_at": datetime.utcnow().isoformat(),
            "status": "implementing",
            "verification_session_id": verification_session.session_id
        }
        
        self.active_sessions[task_id] = session
        
        return session
    
    def execute_implementation_phase(
        self, 
        task_id: str,
        implementer_logic: Callable[[AgentContext], Any]
    ) -> Dict[str, Any]:
        """
        Execute implementation phase with isolated implementer agent.
        
        The implementer_logic callback receives the implementer's isolated context
        and performs the implementation. It CANNOT access critique agent.
        """
        session = self.active_sessions.get(task_id)
        if not session:
            raise ValueError(f"No active session for task {task_id}")
        
        implementer_id = session["implementer_agent_id"]
        implementer = self.agents.get(implementer_id)
        
        if not implementer:
            raise ValueError(f"Implementer agent {implementer_id} not found")
        
        # Execute implementation logic
        # The implementer_logic function operates ONLY on implementer's context
        result = implementer_logic(implementer)
        
        # Update session
        session["status"] = "ready_for_critique"
        session["implementation_result"] = result
        session["implementation_complete"] = True
        
        return {
            "status": "implementation_complete",
            "task_id": task_id,
            "session_id": session["session_id"],
            "next_phase": "critique"
        }
    
    def execute_critique_phase(
        self,
        task_id: str,
        critique_logic: Callable[[AgentContext, Any], List[CritiqueFinding]]
    ) -> Dict[str, Any]:
        """
        Execute critique phase with isolated critique agent.
        
        The critique_logic callback receives:
        1. Critique agent's isolated context (no implementer memory)
        2. Implementation result ONLY (not implementer's reasoning)
        
        This ensures the critique is truly independent.
        """
        session = self.active_sessions.get(task_id)
        if not session:
            raise ValueError(f"No active session for task {task_id}")
        
        if session.get("status") != "ready_for_critique":
            raise ValueError("Implementation phase not complete")
        
        critique_id = session["critique_agent_id"]
        critique = self.agents.get(critique_id)
        
        if not critique:
            raise ValueError(f"Critique agent {critique_id} not found")
        
        # Get implementation result (only the output, not the process)
        implementation_result = session.get("implementation_result")
        
        # Execute critique logic
        # The critique_logic function sees ONLY the implementation result
        # It does NOT have access to implementer's context or reasoning
        findings = critique_logic(critique, implementation_result)
        
        # Verify all dimensions were reviewed
        dimensions_reviewed = list(set(f.dimension for f in findings))
        required_dimensions = [
            "conceptual_validity", "semantic_correctness", "workflow_governance",
            "data_integrity", "security_risks", "scalability_limits",
            "enterprise_readiness", "regulatory_compliance", "integration_correctness",
            "test_coverage"
        ]
        
        missing = set(required_dimensions) - set(dimensions_reviewed)
        if missing:
            raise ValueError(
                f"Critique incomplete - missing dimensions: {missing}. "
                "All 10 dimensions must be reviewed."
            )
        
        # Complete verification session with cryptographic signing
        verification_session = self.verification_service.get_session(
            session["verification_session_id"]
        )
        
        if not verification_session:
            raise ValueError("Verification session not found")
        
        completed_session = self.verification_service.complete_session(
            session=verification_session,
            dimensions_reviewed=dimensions_reviewed,
            findings=findings
        )
        
        # Update session
        session["status"] = "critique_complete"
        session["critique_findings"] = len(findings)
        session["p0_count"] = completed_session.p0_count
        session["p1_count"] = completed_session.p1_count
        session["p2_count"] = completed_session.p2_count
        session["verification_hash"] = completed_session.content_hash
        
        return {
            "status": "critique_complete",
            "task_id": task_id,
            "session_id": session["session_id"],
            "findings_count": len(findings),
            "p0_count": completed_session.p0_count,
            "p1_count": completed_session.p1_count,
            "p2_count": completed_session.p2_count,
            "verification_hash": completed_session.content_hash,
            "next_phase": "fix" if (completed_session.p0_count + completed_session.p1_count) > 0 else "verify"
        }
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get current status of dual-agent session for a task."""
        session = self.active_sessions.get(task_id)
        
        if not session:
            return {"error": f"No session found for task {task_id}"}
        
        return {
            "task_id": task_id,
            "session_id": session["session_id"],
            "status": session["status"],
            "implementer_agent": session["implementer_agent_id"],
            "critique_agent": session["critique_agent_id"],
            "implementation_complete": session.get("implementation_complete", False),
            "critique_complete": session.get("status") == "critique_complete",
            "p0_count": session.get("p0_count", 0),
            "p1_count": session.get("p1_count", 0),
            "p2_count": session.get("p2_count", 0),
            "can_complete": (
                session.get("status") == "critique_complete" and
                session.get("p0_count", 0) == 0 and
                session.get("p1_count", 0) == 0
            )
        }


# Example usage demonstrating proper separation
class ExampleUsage:
    """Example of how to use dual-agent orchestration."""
    
    @staticmethod
    def implement_adm_feature(task_id: str):
        """Example implementation using dual-agent pattern."""
        
        orchestrator = DualAgentOrchestrator()
        
        # Start session
        session = orchestrator.start_dual_agent_session(task_id)
        print(f"Started session: {session['session_id']}")
        
        # Phase 1: Implementation (implementer agent only)
        def implement_logic(implementer_context: AgentContext):
            """
            This function operates ONLY in implementer's isolated context.
            It cannot see or access critique agent.
            """
            # Implementation code here
            # implementer_context.store("code", "...")
            # implementer_context.store("tests", "...")
            return {
                "files_created": ["app/models/adm_kanban.py"],
                "tests_added": 5,
                "documentation": "Added TOGAF compliance"
            }
        
        impl_result = orchestrator.execute_implementation_phase(
            task_id=task_id,
            implementer_logic=implement_logic
        )
        print(f"Implementation complete: {impl_result}")
        
        # Phase 2: Critique (critique agent only, isolated from implementer)
        def critique_logic(critique_context: AgentContext, implementation_result: Any):
            """
            This function operates ONLY in critique's isolated context.
            It sees ONLY the implementation_result, NOT implementer's reasoning.
            """
            findings = []
            
            # Critique agent checks 10 dimensions
            # It cannot access implementer_context - they are ISOLATED
            
            # Example finding
            findings.append(CritiqueFinding(
                dimension="data_integrity",
                severity="P0",
                description="JSON blob fields lack referential integrity",
                location="app/models/adm_kanban.py:45",
                evidence="application_ids stored as JSON array",
                fix_required=True
            ))
            
            return findings
        
        critique_result = orchestrator.execute_critique_phase(
            task_id=task_id,
            critique_logic=critique_logic
        )
        print(f"Critique complete: {critique_result}")
        
        # Check if can complete
        status = orchestrator.get_task_status(task_id)
        if status["can_complete"]:
            print("✅ Task can be marked complete")
        else:
            print(f"❌ Task blocked: {status['p0_count']} P0, {status['p1_count']} P1 findings")
        
        return status


# Singleton
_orchestrator = None

def get_dual_agent_orchestrator() -> DualAgentOrchestrator:
    """Get or create singleton orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = DualAgentOrchestrator()
    return _orchestrator
