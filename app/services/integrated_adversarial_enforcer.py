"""
Integrated Adversarial Review Enforcement

Combines scope detection, lightweight validation, and full enforcement into a single
coordinated system. Automatically selects appropriate enforcement level based on request.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from app.services.adversarial_scope_service import (
    get_scope_service, 
    get_scope_enforcer,
    EnforcementLevel,
    RequestCharacteristics
)
from app.services.lightweight_adversarial_validator import (
    get_lightweight_validator,
    LightweightValidationResult
)
from app.services.critique_verification_service import (
    get_critique_service,
    CritiqueSession,
    CritiqueFinding
)
from app.services.dual_agent_orchestrator import (
    get_dual_agent_orchestrator,
    DualAgentOrchestrator,
    AgentContext
)


class ReviewEnforcementStatus(str, Enum):
    """Status of enforcement for a request."""
    NOT_REQUIRED = "not_required"
    LIGHTWEIGHT_PENDING = "lightweight_pending"
    LIGHTWEIGHT_PASSED = "lightweight_passed"
    FULL_PENDING = "full_pending"
    FULL_IN_PROGRESS = "full_in_progress"
    FULL_COMPLETE = "full_complete"
    BLOCKED = "blocked"


@dataclass
class EnforcementResult:
    """Result of enforcement check for a request."""
    status: ReviewEnforcementStatus
    enforcement_level: str
    can_proceed: bool
    message: str
    concerns: List[str]
    next_action: str
    session_id: Optional[str] = None


class IntegratedAdversarialEnforcer:
    """
    Unified enforcer that coordinates all adversarial review levels.
    
    Provides a single interface that automatically:
    1. Detects scope of request
    2. Applies appropriate enforcement level
    3. Tracks enforcement status
    4. Coordinates between lightweight and full review
    """
    
    def __init__(self):
        self.scope_enforcer = get_scope_enforcer()
        self.lightweight_validator = get_lightweight_validator()
        self.critique_service = get_critique_service()
        self.dual_agent_orchestrator = get_dual_agent_orchestrator()
        self.active_enforcements: Dict[str, Dict[str, Any]] = {}
    
    def evaluate_request(
        self,
        request_id: str,
        request_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> EnforcementResult:
        """
        Main entry point - evaluate any request and return enforcement requirements.
        
        This is called at the START of processing any user request.
        """
        # Determine scope and enforcement level
        scope_result = self.scope_enforcer.enforce_for_request(request_text, context)
        
        level = scope_result["enforcement_level"]
        decision = scope_result["decision"]
        
        if level == EnforcementLevel.NONE.value:
            # No enforcement needed
            return EnforcementResult(
                status=ReviewEnforcementStatus.NOT_REQUIRED,
                enforcement_level=level,
                can_proceed=True,
                message="Informational request - no adversarial review required",
                concerns=[],
                next_action="Proceed with response"
            )
        
        elif level == EnforcementLevel.LIGHTWEIGHT.value:
            # Lightweight validation
            return self._handle_lightweight_enforcement(
                request_id, request_text, scope_result
            )
        
        elif level == EnforcementLevel.FULL.value:
            # Full enforcement
            return self._handle_full_enforcement(
                request_id, request_text, scope_result, context
            )
        
        else:
            return EnforcementResult(
                status=ReviewEnforcementStatus.BLOCKED,
                enforcement_level="unknown",
                can_proceed=False,
                message=f"Unknown enforcement level: {level}",
                concerns=["System configuration error"],
                next_action="Contact system administrator"
            )
    
    def _handle_lightweight_enforcement(
        self,
        request_id: str,
        request_text: str,
        scope_result: Dict[str, Any]
    ) -> EnforcementResult:
        """Handle lightweight validation path."""
        
        # Check if we have code to validate
        characteristics = scope_result["characteristics"]
        
        concerns = []
        
        # If implementation request, validate code patterns
        if characteristics.request_type == "implementation":
            # Extract any code from request (user might provide snippet)
            # For now, we'll flag common patterns in the request text
            validation = self.lightweight_validator.validate_code_snippet(
                request_text, 
                language="python"
            )
            
            for concern in validation.concerns:
                concerns.append(f"[{concern.category}] {concern.message}")
        
        # If architecture guidance, validate terminology
        elif characteristics.is_architecture_relevant:
            validation = self.lightweight_validator.validate_architecture_guidance(
                request_text
            )
            
            for concern in validation.concerns:
                concerns.append(f"[{concern.category}] {concern.message}")
        
        # Determine if we can proceed
        strong_concerns = [c for c in concerns if "STRONGLY RECOMMEND" in c or "security" in c.lower()]
        
        if strong_concerns:
            return EnforcementResult(
                status=ReviewEnforcementStatus.LIGHTWEIGHT_PENDING,
                enforcement_level=EnforcementLevel.LIGHTWEIGHT.value,
                can_proceed=False,  # User should address strong concerns
                message="Lightweight validation identified significant concerns",
                concerns=concerns,
                next_action="Address concerns before proceeding, or escalate to full review"
            )
        
        # Store lightweight validation record
        self.active_enforcements[request_id] = {
            "level": EnforcementLevel.LIGHTWEIGHT.value,
            "concerns": concerns,
            "status": "passed"
        }
        
        return EnforcementResult(
            status=ReviewEnforcementStatus.LIGHTWEIGHT_PASSED,
            enforcement_level=EnforcementLevel.LIGHTWEIGHT.value,
            can_proceed=True,
            message="Lightweight validation passed",
            concerns=concerns,
            next_action="Proceed with implementation, apply adversarial thinking"
        )
    
    def _handle_full_enforcement(
        self,
        request_id: str,
        request_text: str,
        scope_result: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> EnforcementResult:
        """Handle full enforcement path with dual-agent orchestration."""
        
        # Check if this is a task in agent_plan.yaml
        task_id = context.get("task_id") if context else None
        
        if not task_id:
            # Generate task ID from request
            task_id = f"ADHOC-{request_id[:8]}"
        
        # Check if we already have an active session
        existing_session = self.active_enforcements.get(request_id)
        
        if existing_session and existing_session.get("dual_agent_session"):
            session = existing_session["dual_agent_session"]
            status = self.dual_agent_orchestrator.get_task_status(task_id)
            
            # Check current status
            if status.get("critique_complete"):
                if status.get("can_complete"):
                    return EnforcementResult(
                        status=ReviewEnforcementStatus.FULL_COMPLETE,
                        enforcement_level=EnforcementLevel.FULL.value,
                        can_proceed=True,
                        message="Full adversarial review complete - no blocking findings",
                        concerns=[],
                        next_action="Mark task as complete",
                        session_id=session["session_id"]
                    )
                else:
                    return EnforcementResult(
                        status=ReviewEnforcementStatus.FULL_IN_PROGRESS,
                        enforcement_level=EnforcementLevel.FULL.value,
                        can_proceed=False,
                        message=f"Critique complete but {status.get('p0_count', 0)} P0 and {status.get('p1_count', 0)} P1 findings unresolved",
                        concerns=[f"{status.get('p0_count', 0)} P0 findings", f"{status.get('p1_count', 0)} P1 findings"],
                        next_action="Fix P0/P1 findings before claiming completion",
                        session_id=session["session_id"]
                    )
            else:
                return EnforcementResult(
                    status=ReviewEnforcementStatus.FULL_IN_PROGRESS,
                    enforcement_level=EnforcementLevel.FULL.value,
                    can_proceed=False,
                    message="Implementation complete - ready for critique phase",
                    concerns=[],
                    next_action="Start adversarial review with separate critique agent",
                    session_id=session["session_id"]
                )
        
        # Start new dual-agent session
        session = self.dual_agent_orchestrator.start_dual_agent_session(task_id)
        
        self.active_enforcements[request_id] = {
            "level": EnforcementLevel.FULL.value,
            "task_id": task_id,
            "dual_agent_session": session,
            "status": "implementing"
        }
        
        return EnforcementResult(
            status=ReviewEnforcementStatus.FULL_PENDING,
            enforcement_level=EnforcementLevel.FULL.value,
            can_proceed=True,  # Can proceed with implementation
            message="Full adversarial review session initialized",
            concerns=[],
            next_action="Implement with awareness that critique will follow",
            session_id=session["session_id"]
        )
    
    def mark_implementation_complete(
        self,
        request_id: str,
        implementation_result: Any
    ) -> EnforcementResult:
        """Mark implementation phase complete and trigger critique."""
        
        enforcement = self.active_enforcements.get(request_id)
        if not enforcement:
            return EnforcementResult(
                status=ReviewEnforcementStatus.BLOCKED,
                enforcement_level="unknown",
                can_proceed=False,
                message="No active enforcement found for request",
                concerns=["Request must be evaluated first"],
                next_action="Call evaluate_request first"
            )
        
        if enforcement["level"] != EnforcementLevel.FULL.value:
            # Lightweight - just complete
            enforcement["status"] = "complete"
            return EnforcementResult(
                status=ReviewEnforcementStatus.LIGHTWEIGHT_PASSED,
                enforcement_level=EnforcementLevel.LIGHTWEIGHT.value,
                can_proceed=True,
                message="Implementation complete (lightweight validation)",
                concerns=[],
                next_action="Task complete"
            )
        
        # Full enforcement - trigger critique phase
        task_id = enforcement["task_id"]
        
        # Execute implementation phase
        self.dual_agent_orchestrator.execute_implementation_phase(
            task_id=task_id,
            implementer_logic=lambda ctx: implementation_result
        )
        
        # Now trigger critique (in real system, this would be async/separate process)
        return EnforcementResult(
            status=ReviewEnforcementStatus.FULL_IN_PROGRESS,
            enforcement_level=EnforcementLevel.FULL.value,
            can_proceed=False,
            message="Implementation complete - critique phase ready",
            concerns=[],
            next_action="Start critique phase with separate agent",
            session_id=enforcement["dual_agent_session"]["session_id"]
        )
    
    def execute_critique_phase(
        self,
        request_id: str,
        critique_logic: Optional[Callable] = None
    ) -> EnforcementResult:
        """Execute critique phase for full enforcement."""
        
        enforcement = self.active_enforcements.get(request_id)
        if not enforcement or enforcement["level"] != EnforcementLevel.FULL.value:
            return EnforcementResult(
                status=ReviewEnforcementStatus.BLOCKED,
                enforcement_level="unknown",
                can_proceed=False,
                message="Full enforcement not active for this request",
                concerns=[],
                next_action="Evaluate request first"
            )
        
        task_id = enforcement["task_id"]
        
        # Execute critique phase
        try:
            result = self.dual_agent_orchestrator.execute_critique_phase(
                task_id=task_id,
                critique_logic=critique_logic or self._default_critique_logic
            )
            
            # Check if can complete
            if result["p0_count"] == 0 and result["p1_count"] == 0:
                return EnforcementResult(
                    status=ReviewEnforcementStatus.FULL_COMPLETE,
                    enforcement_level=EnforcementLevel.FULL.value,
                    can_proceed=True,
                    message="Full adversarial review complete - no blocking findings",
                    concerns=[],
                    next_action="Mark task complete",
                    session_id=result["session_id"]
                )
            else:
                return EnforcementResult(
                    status=ReviewEnforcementStatus.FULL_IN_PROGRESS,
                    enforcement_level=EnforcementLevel.FULL.value,
                    can_proceed=False,
                    message=f"Critique found {result['p0_count']} P0 and {result['p1_count']} P1 findings",
                    concerns=[f"{result['p0_count']} P0 findings", f"{result['p1_count']} P1 findings"],
                    next_action="Fix all P0/P1 findings before completion",
                    session_id=result["session_id"]
                )
        
        except Exception as e:
            return EnforcementResult(
                status=ReviewEnforcementStatus.BLOCKED,
                enforcement_level=EnforcementLevel.FULL.value,
                can_proceed=False,
                message=f"Critique phase failed: {str(e)}",
                concerns=[str(e)],
                next_action="Resolve error and retry"
            )
    
    def _default_critique_logic(self, critique_context: AgentContext, implementation: Any) -> List[CritiqueFinding]:
        """Default critique logic if none provided."""
        # In production, this would use an actual LLM with adversarial persona
        # For now, return empty findings (user provides actual critique)
        return []
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate summary of all active enforcements."""
        return {
            "total_active": len(self.active_enforcements),
            "by_level": {
                "lightweight": sum(1 for e in self.active_enforcements.values() if e["level"] == "lightweight"),
                "full": sum(1 for e in self.active_enforcements.values() if e["level"] == "full")
            },
            "by_status": {
                "pending": sum(1 for e in self.active_enforcements.values() if e.get("status") == "pending"),
                "in_progress": sum(1 for e in self.active_enforcements.values() if e.get("status") == "in_progress"),
                "complete": sum(1 for e in self.active_enforcements.values() if e.get("status") == "complete")
            }
        }


# Singleton
_integrated_enforcer = None

def get_integrated_enforcer() -> IntegratedAdversarialEnforcer:
    """Get or create singleton integrated enforcer."""
    global _integrated_enforcer
    if _integrated_enforcer is None:
        _integrated_enforcer = IntegratedAdversarialEnforcer()
    return _integrated_enforcer


# Convenience function for direct use
def evaluate_request(
    request_id: str,
    request_text: str,
    context: Optional[Dict[str, Any]] = None
) -> EnforcementResult:
    """
    Convenience function to evaluate any request.
    
    Usage:
        result = evaluate_request("req-123", "Implement ADM Kanban models")
        if result.can_proceed:
            # Implement
        else:
            # Address concerns or start full review
    """
    enforcer = get_integrated_enforcer()
    return enforcer.evaluate_request(request_id, request_text, context)
