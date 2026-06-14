"""
Adversarial Review Scope Detection Service

Determines the appropriate level of adversarial review based on request characteristics.
Prevents over-enforcement on simple queries while ensuring critical changes are fully reviewed.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set
from pathlib import Path


class EnforcementLevel(str, Enum):
    """Levels of adversarial review enforcement."""
    FULL = "full"           # Cryptographic, CI/CD, dual-agent
    LIGHTWEIGHT = "lightweight"  # Quick validation, no crypto overhead
    NONE = "none"           # Informational only


@dataclass
class RequestCharacteristics:
    """Characteristics extracted from user request."""
    request_type: str  # "implementation", "explanation", "debug", "review"
    estimated_lines: int
    persistence_required: bool
    affects_database: bool
    affects_security: bool
    is_architecture_relevant: bool
    is_in_agent_plan: bool
    orchestration_pattern: Optional[str] = None
    target_files: List[str] = field(default_factory=list)
    keywords: Set[str] = field(default_factory=set)


@dataclass
class ScopeDecision:
    """Decision on enforcement level with reasoning."""
    level: EnforcementLevel
    reasons: List[str]
    required_checks: List[str]
    estimated_effort_minutes: int
    can_proceed: bool


class ScopeDetectionService:
    """
    Detects appropriate enforcement level for any LLM request.
    
    Uses heuristics and rules to determine:
    - FULL enforcement: Production code, schema changes, security-related
    - LIGHTWEIGHT: Small code snippets, configuration, minor edits
    - NONE: Explanations, Q&A, debugging help
    """
    
    # Keywords that indicate implementation work
    IMPLEMENTATION_KEYWORDS = {
        "implement", "create", "add", "build", "develop", "write",
        "generate", "produce", "make", "construct", "establish"
    }
    
    # Keywords that indicate explanation only
    EXPLANATION_KEYWORDS = {
        "explain", "describe", "what is", "how does", "why",
        "clarify", "help me understand", "tell me about"
    }
    
    # Keywords that indicate debugging
    DEBUG_KEYWORDS = {
        "debug", "fix", "troubleshoot", "error", "exception",
        "broken", "not working", "failing", "crash"
    }
    
    # Security-related keywords requiring full review
    SECURITY_KEYWORDS = {
        "auth", "authentication", "authorization", "login", "password",
        "encrypt", "decrypt", "hash", "token", "jwt", "oauth",
        "permission", "role", "access control", "csrf", "xss",
        "injection", "sanitize", "validate", "csrf_token"
    }
    
    # Database-related keywords
    DATABASE_KEYWORDS = {
        "migration", "schema", "table", "column", "index",
        "foreign key", "relationship", "model", "db", "database",
        "sql", "query", "transaction"
    }
    
    # Architecture keywords
    ARCHITECTURE_KEYWORDS = {
        "architecture", "archimate", "togaf", "pattern",
        "component", "service", "microservice", "layer",
        "repository", "service layer", "domain model"
    }
    
    def __init__(self):
        self.enforcement_thresholds = {
            "min_lines_for_full": 30,
            "min_files_for_full": 2,
        }
    
    def analyze_request(
        self,
        request_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RequestCharacteristics:
        """Extract characteristics from request text."""
        request_lower = request_text.lower()
        
        # Detect request type
        request_type = self._detect_request_type(request_lower)
        
        # Estimate scope
        estimated_lines = self._estimate_lines(request_text)
        
        # Check for keywords
        keywords = self._extract_keywords(request_lower)
        
        # Determine persistence
        persistence_required = self._check_persistence_required(
            request_type, keywords, context
        )
        
        # Check database impact
        affects_database = bool(
            keywords & self.DATABASE_KEYWORDS or
            "migration" in request_lower or
            "model" in request_lower
        )
        
        # Check security impact
        affects_security = bool(keywords & self.SECURITY_KEYWORDS)
        
        # Check architecture relevance
        is_architecture_relevant = bool(
            keywords & self.ARCHITECTURE_KEYWORDS or
            "architect" in request_lower
        )
        
        # Check if in agent plan
        is_in_agent_plan = self._check_in_agent_plan(context)
        orchestration_pattern = self._get_orchestration_pattern(context)
        
        # Extract target files
        target_files = self._extract_target_files(request_text, context)
        
        return RequestCharacteristics(
            request_type=request_type,
            estimated_lines=estimated_lines,
            persistence_required=persistence_required,
            affects_database=affects_database,
            affects_security=affects_security,
            is_architecture_relevant=is_architecture_relevant,
            is_in_agent_plan=is_in_agent_plan,
            orchestration_pattern=orchestration_pattern,
            target_files=target_files,
            keywords=keywords
        )
    
    def determine_enforcement_level(
        self,
        characteristics: RequestCharacteristics
    ) -> ScopeDecision:
        """Determine enforcement level based on characteristics."""
        
        reasons = []
        required_checks = []
        
        # ALWAYS full enforcement for PEV pattern tasks
        if characteristics.orchestration_pattern == "PEV":
            reasons.append("PEV orchestration pattern requires full adversarial review")
            required_checks.extend([
                "cryptographic_critique_signature",
                "ci_cd_gate_pass",
                "dual_agent_separation",
                "automated_analysis_pass",
                "p0_p1_findings_resolved"
            ])
            return ScopeDecision(
                level=EnforcementLevel.FULL,
                reasons=reasons,
                required_checks=required_checks,
                estimated_effort_minutes=45,
                can_proceed=True
            )
        
        # ALWAYS full enforcement for agent plan tasks with implementation
        if characteristics.is_in_agent_plan and characteristics.request_type == "implementation":
            reasons.append("Agent plan implementation task")
            required_checks.extend([
                "cryptographic_critique_signature",
                "p0_p1_findings_resolved"
            ])
            return ScopeDecision(
                level=EnforcementLevel.FULL,
                reasons=reasons,
                required_checks=required_checks,
                estimated_effort_minutes=45,
                can_proceed=True
            )
        
        # Security-related changes always get full review
        if characteristics.affects_security:
            reasons.append("Security-related changes require full review")
            required_checks.extend([
                "security_scan_bandit",
                "cryptographic_critique_signature",
                "security_expert_review"
            ])
            return ScopeDecision(
                level=EnforcementLevel.FULL,
                reasons=reasons,
                required_checks=required_checks,
                estimated_effort_minutes=30,
                can_proceed=True
            )
        
        # Database schema changes always get full review
        if characteristics.affects_database and characteristics.persistence_required:
            reasons.append("Database schema changes require full review")
            required_checks.extend([
                "migration_safety_check",
                "cryptographic_critique_signature",
                "data_integrity_review"
            ])
            return ScopeDecision(
                level=EnforcementLevel.FULL,
                reasons=reasons,
                required_checks=required_checks,
                estimated_effort_minutes=30,
                can_proceed=True
            )
        
        # Large implementations get full review
        if characteristics.estimated_lines >= self.enforcement_thresholds["min_lines_for_full"]:
            reasons.append(f"Estimated {characteristics.estimated_lines}+ lines of code")
            required_checks.extend([
                "cryptographic_critique_signature",
                "automated_analysis",
                "code_review"
            ])
            return ScopeDecision(
                level=EnforcementLevel.FULL,
                reasons=reasons,
                required_checks=required_checks,
                estimated_effort_minutes=30,
                can_proceed=True
            )
        
        # Multiple files get full review
        if len(characteristics.target_files) >= self.enforcement_thresholds["min_files_for_full"]:
            reasons.append(f"Changes span {len(characteristics.target_files)} files")
            required_checks.extend([
                "cross_file_impact_analysis",
                "lightweight_critique",
                "integration_test"
            ])
            return ScopeDecision(
                level=EnforcementLevel.FULL,
                reasons=reasons,
                required_checks=required_checks,
                estimated_effort_minutes=20,
                can_proceed=True
            )
        
        # Explanation-only requests get no enforcement
        if characteristics.request_type == "explanation":
            reasons.append("Informational request - no code changes")
            required_checks = ["none"]
            return ScopeDecision(
                level=EnforcementLevel.NONE,
                reasons=reasons,
                required_checks=required_checks,
                estimated_effort_minutes=0,
                can_proceed=True
            )
        
        # Debug help gets lightweight validation
        if characteristics.request_type == "debug":
            reasons.append("Debugging assistance - verification suggested")
            required_checks = [
                "quick_test_verification",
                "sanity_check"
            ]
            return ScopeDecision(
                level=EnforcementLevel.LIGHTWEIGHT,
                reasons=reasons,
                required_checks=required_checks,
                estimated_effort_minutes=5,
                can_proceed=True
            )
        
        # Small code changes get lightweight validation
        if characteristics.estimated_lines < 20 and not characteristics.persistence_required:
            reasons.append(f"Small change ({characteristics.estimated_lines} estimated lines)")
            required_checks = [
                "quick_adversarial_thinking",
                "test_if_applicable"
            ]
            return ScopeDecision(
                level=EnforcementLevel.LIGHTWEIGHT,
                reasons=reasons,
                required_checks=required_checks,
                estimated_effort_minutes=5,
                can_proceed=True
            )
        
        # Default to lightweight for everything else
        reasons.append("Standard code change - lightweight review recommended")
        required_checks = [
            "quick_adversarial_thinking",
            "automated_analysis_if_available"
        ]
        return ScopeDecision(
            level=EnforcementLevel.LIGHTWEIGHT,
            reasons=reasons,
            required_checks=required_checks,
            estimated_effort_minutes=10,
            can_proceed=True
        )
    
    def _detect_request_type(self, request_lower: str) -> str:
        """Detect the type of request."""
        # Check for explanation keywords
        if any(kw in request_lower for kw in self.EXPLANATION_KEYWORDS):
            return "explanation"
        
        # Check for debug keywords
        if any(kw in request_lower for kw in self.DEBUG_KEYWORDS):
            return "debug"
        
        # Check for review keywords
        if "review" in request_lower or "check" in request_lower:
            return "review"
        
        # Default to implementation if creating/building
        if any(kw in request_lower for kw in self.IMPLEMENTATION_KEYWORDS):
            return "implementation"
        
        return "unknown"
    
    def _estimate_lines(self, request_text: str) -> int:
        """Estimate lines of code based on request complexity."""
        # Simple heuristics
        indicators = {
            "model": 50,
            "service": 100,
            "migration": 30,
            "route": 40,
            "template": 80,
            "test": 50,
            "fix": 10,
            "update": 20,
            "add": 30,
            "create": 50,
        }
        
        total = 0
        request_lower = request_text.lower()
        
        for keyword, lines in indicators.items():
            if keyword in request_lower:
                total += lines
        
        # Count specific features requested
        features = len(re.findall(r'\d+\.', request_text))  # Numbered lists
        total += features * 20
        
        return max(total, 5)  # Minimum 5 lines
    
    def _extract_keywords(self, request_lower: str) -> Set[str]:
        """Extract relevant keywords from request."""
        all_keywords = (
            self.SECURITY_KEYWORDS |
            self.DATABASE_KEYWORDS |
            self.ARCHITECTURE_KEYWORDS |
            self.IMPLEMENTATION_KEYWORDS
        )
        
        found = set()
        for keyword in all_keywords:
            if keyword in request_lower:
                found.add(keyword)
        
        return found
    
    def _check_persistence_required(
        self,
        request_type: str,
        keywords: Set[str],
        context: Optional[Dict]
    ) -> bool:
        """Check if changes will be persisted."""
        if request_type == "explanation":
            return False
        
        if keywords & self.DATABASE_KEYWORDS:
            return True
        
        if context and context.get("creates_files"):
            return True
        
        return True  # Assume persistence for implementation
    
    def _check_in_agent_plan(self, context: Optional[Dict]) -> bool:
        """Check if request is part of agent plan."""
        if not context:
            return False
        
        return context.get("in_agent_plan", False) or bool(context.get("task_id"))
    
    def _get_orchestration_pattern(self, context: Optional[Dict]) -> Optional[str]:
        """Get orchestration pattern if available."""
        if not context:
            return None
        
        return context.get("orchestration_pattern")
    
    def _extract_target_files(
        self,
        request_text: str,
        context: Optional[Dict]
    ) -> List[str]:
        """Extract target files from request."""
        files = []
        
        # Look for file paths in request
        file_pattern = r'(?:app|tests|docs|scripts)/[\w/]+\.py'
        files = re.findall(file_pattern, request_text)
        
        # Also check context
        if context and context.get("target_files"):
            files.extend(context["target_files"])
        
        return list(set(files))  # Deduplicate


class ScopeEnforcer:
    """
    Enforces appropriate adversarial review based on scope decision.
    
    Provides different enforcement paths:
    - FULL: Uses dual-agent orchestration, cryptographic signing, CI/CD
    - LIGHTWEIGHT: Quick adversarial thinking, minimal overhead
    - NONE: Proceed without review
    """
    
    def __init__(self):
        self.scope_service = ScopeDetectionService()
    
    def enforce_for_request(
        self,
        request_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point - analyze request and return enforcement requirements.
        
        Returns dict with:
        - enforcement_level: full/lightweight/none
        - decision: ScopeDecision with reasoning
        - characteristics: RequestCharacteristics
        - next_steps: What to do next
        """
        # Analyze request
        characteristics = self.scope_service.analyze_request(request_text, context)
        
        # Determine enforcement
        decision = self.scope_service.determine_enforcement_level(characteristics)
        
        # Generate next steps
        next_steps = self._generate_next_steps(decision)
        
        return {
            "enforcement_level": decision.level.value,
            "decision": decision,
            "characteristics": characteristics,
            "next_steps": next_steps,
            "proceed": decision.can_proceed
        }
    
    def _generate_next_steps(self, decision: ScopeDecision) -> List[str]:
        """Generate actionable next steps based on decision."""
        steps = []
        
        if decision.level == EnforcementLevel.FULL:
            steps.extend([
                "1. Start dual-agent orchestration session",
                "2. Implementer agent completes implementation",
                "3. Critique agent performs adversarial review (30min)",
                "4. Fix all P0/P1 findings",
                "5. Cryptographic signing of critique",
                "6. CI/CD gate verification",
                "7. Mark complete only after all gates pass"
            ])
        
        elif decision.level == EnforcementLevel.LIGHTWEIGHT:
            steps.extend([
                "1. Apply adversarial thinking to implementation",
                "2. Run automated analysis if available",
                "3. Quick test verification",
                "4. Proceed with user confirmation"
            ])
        
        else:  # NONE
            steps.append("Proceed with response - no review required")
        
        return steps


# Singleton
_scope_service = None
_enforcer = None

def get_scope_service() -> ScopeDetectionService:
    """Get or create singleton scope service."""
    global _scope_service
    if _scope_service is None:
        _scope_service = ScopeDetectionService()
    return _scope_service

def get_scope_enforcer() -> ScopeEnforcer:
    """Get or create singleton enforcer."""
    global _enforcer
    if _enforcer is None:
        _enforcer = ScopeEnforcer()
    return _enforcer
