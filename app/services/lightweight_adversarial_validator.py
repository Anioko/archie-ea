"""
Lightweight Adversarial Validation

Quick adversarial thinking for ad-hoc queries without cryptographic overhead.
Provides sanity checks without the 30-minute full review process.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum


class ConcernSeverity(str, Enum):
    """Severity of lightweight concerns."""
    SUGGEST = "suggest"      # Nice to verify
    RECOMMEND = "recommend"  # Should verify
    STRONGLY_RECOMMEND = "strongly_recommend"  # Important to verify


@dataclass
class LightweightConcern:
    """A lightweight concern identified during quick validation."""
    category: str
    severity: ConcernSeverity
    message: str
    suggested_action: str


@dataclass
class LightweightValidationResult:
    """Result of lightweight adversarial validation."""
    concerns: List[LightweightConcern] = field(default_factory=list)
    quick_checks_passed: bool = True
    estimated_risk: str = "low"  # low, medium, high
    recommendation: str = "proceed"


class LightweightAdversarialValidator:
    """
    Quick adversarial thinking for ad-hoc queries.
    
    Uses heuristics and pattern matching to identify potential issues
    without the overhead of full dual-agent orchestration.
    
    Typical time: 5-10 seconds vs 30-45 minutes for full review.
    """
    
    # Patterns that suggest potential issues
    RISK_PATTERNS = {
        "sql_injection": {
            "patterns": [r'\.format\s*\([^)]*%s', r'f["\'].*\{.*\}.*["\'].*%s', r'execute\s*\([^)]*%'],
            "message": "Possible SQL injection risk - use parameterized queries",
            "severity": ConcernSeverity.STRONGLY_RECOMMEND
        },
        "hardcoded_secret": {
            "patterns": [r'password\s*=\s*["\'][^"\']+', r'secret\s*=\s*["\'][^"\']+', r'api_key\s*=\s*["\'][^"\']+'],
            "message": "Potential hardcoded secret detected",
            "severity": ConcernSeverity.STRONGLY_RECOMMEND
        },
        "bare_except": {
            "patterns": [r'except\s*:', r'except\s+Exception\s*:'],
            "message": "Bare except clause - catch specific exceptions",
            "severity": ConcernSeverity.RECOMMEND
        },
        "print_debugging": {
            "patterns": [r'print\s*\([^)]*\)'],
            "message": "Print statement found - consider using logging",
            "severity": ConcernSeverity.SUGGEST
        },
        "todo_without_ticket": {
            "patterns": [r'#\s*TODO\s*(?!\[)', r'#\s*FIXME\s*(?!\[)'],
            "message": "TODO/FIXME without ticket reference",
            "severity": ConcernSeverity.SUGGEST
        },
        "mutable_default": {
            "patterns": [r'def\s+\w+\s*\([^)]*=\s*\[\s*\]', r'def\s+\w+\s*\([^)]*=\s*\{\s*\}'],
            "message": "Mutable default argument - use None and initialize in body",
            "severity": ConcernSeverity.RECOMMEND
        },
    }
    
    # Architecture guidance patterns
    ARCHITECTURE_PATTERNS = {
        "togaf_violation": {
            "keywords": ["skip phase", "bypass approval", "direct deploy"],
            "message": "Possible TOGAF governance bypass - verify with architecture team",
            "severity": ConcernSeverity.STRONGLY_RECOMMEND
        },
        "archimate_misuse": {
            "keywords": ["capability.*process", "process.*capability", "application.*business"],
            "message": "Possible ArchiMate layer confusion - verify element types",
            "severity": ConcernSeverity.RECOMMEND
        },
        "json_blobs": {
            "keywords": ["json", "jsonb", "json column"],
            "context": ["database", "model", "migration"],
            "message": "JSON column may indicate missing relational model - consider normalization",
            "severity": ConcernSeverity.RECOMMEND
        },
    }
    
    # Security quick checks
    SECURITY_PATTERNS = {
        "csrf_exempt": {
            "patterns": [r'csrf\.exempt', r'@csrf_exempt'],
            "message": "CSRF protection disabled - verify this is intentional",
            "severity": ConcernSeverity.STRONGLY_RECOMMEND
        },
        "no_validation": {
            "patterns": [r'request\.form\[', r'request\.args\[', r'request\.json\s*\['],
            "context_exclude": [r'validate', r'check', r'schema'],
            "message": "Direct request data access without validation",
            "severity": ConcernSeverity.RECOMMEND
        },
    }
    
    def validate_code_snippet(
        self,
        code: str,
        language: str = "python",
        context: Optional[Dict[str, Any]] = None
    ) -> LightweightValidationResult:
        """
        Quick validation of a code snippet.
        
        Typical use: User asks "help me write X" - validate before providing.
        """
        concerns = []
        
        # Check risk patterns
        for risk_name, risk_config in self.RISK_PATTERNS.items():
            for pattern in risk_config["patterns"]:
                if re.search(pattern, code, re.IGNORECASE):
                    concerns.append(LightweightConcern(
                        category="code_quality",
                        severity=risk_config["severity"],
                        message=risk_config["message"],
                        suggested_action="Review and fix the identified pattern"
                    ))
                    break  # One concern per risk type is enough
        
        # Check security patterns
        for sec_name, sec_config in self.SECURITY_PATTERNS.items():
            for pattern in sec_config["patterns"]:
                if re.search(pattern, code, re.IGNORECASE):
                    # Check for exclusion context
                    excluded = False
                    for exclude_pattern in sec_config.get("context_exclude", []):
                        if re.search(exclude_pattern, code, re.IGNORECASE):
                            excluded = True
                            break
                    
                    if not excluded:
                        concerns.append(LightweightConcern(
                            category="security",
                            severity=sec_config["severity"],
                            message=sec_config["message"],
                            suggested_action="Add proper validation or security controls"
                        ))
                    break
        
        # Determine overall risk
        high_count = sum(1 for c in concerns if c.severity == ConcernSeverity.STRONGLY_RECOMMEND)
        medium_count = sum(1 for c in concerns if c.severity == ConcernSeverity.RECOMMEND)
        
        if high_count > 0:
            estimated_risk = "high"
            recommendation = "review_before_proceeding"
        elif medium_count > 1:
            estimated_risk = "medium"
            recommendation = "review_suggested"
        else:
            estimated_risk = "low"
            recommendation = "proceed_with_caution"
        
        return LightweightValidationResult(
            concerns=concerns,
            quick_checks_passed=len(concerns) == 0,
            estimated_risk=estimated_risk,
            recommendation=recommendation
        )
    
    def validate_architecture_guidance(
        self,
        guidance_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> LightweightValidationResult:
        """
        Quick validation of architecture guidance.
        
        Checks for common TOGAF/ArchiMate misalignments.
        """
        concerns = []
        text_lower = guidance_text.lower()
        
        for pattern_name, pattern_config in self.ARCHITECTURE_PATTERNS.items():
            # Check if keywords are present
            keywords_found = all(
                kw in text_lower 
                for kw in pattern_config["keywords"]
            )
            
            if keywords_found:
                # Check context if specified
                if "context" in pattern_config:
                    context_found = any(
                        ctx in text_lower 
                        for ctx in pattern_config["context"]
                    )
                    if not context_found:
                        continue
                
                concerns.append(LightweightConcern(
                    category="architecture",
                    severity=pattern_config["severity"],
                    message=pattern_config["message"],
                    suggested_action="Verify against TOGAF/ArchiMate standards"
                ))
        
        return LightweightValidationResult(
            concerns=concerns,
            quick_checks_passed=len(concerns) == 0,
            estimated_risk="medium" if concerns else "low",
            recommendation="review_suggested" if concerns else "proceed"
        )
    
    def validate_explanation(
        self,
        explanation: str,
        topic: str,
        context: Optional[Dict[str, Any]] = None
    ) -> LightweightValidationResult:
        """
        Lightweight validation of explanations.
        
        Checks for confident but potentially incorrect claims.
        """
        concerns = []
        
        # Check for absolute statements that might be wrong
        absolute_patterns = [
            r'always\s+',
            r'never\s+',
            r'impossible\s+to',
            r'guaranteed\s+to',
        ]
        
        for pattern in absolute_patterns:
            if re.search(pattern, explanation, re.IGNORECASE):
                concerns.append(LightweightConcern(
                    category="accuracy",
                    severity=ConcernSeverity.SUGGEST,
                    message=f"Absolute statement found ('{pattern.replace('\\s+', ' ')}') - verify this is correct",
                    suggested_action="Consider adding caveats or context"
                ))
        
        # Check for specific technical claims that might need verification
        if "architecture" in topic.lower():
            # Verify ArchiMate claims
            if "capability" in explanation.lower() and "business process" in explanation.lower():
                concerns.append(LightweightConcern(
                    category="architecture",
                    severity=ConcernSeverity.RECOMMEND,
                    message="Capability vs Business Process distinction - verify layer assignment",
                    suggested_action="Check ArchiMate 3.2 metamodel for correct element type"
                ))
        
        return LightweightValidationResult(
            concerns=concerns,
            quick_checks_passed=len(concerns) == 0,
            estimated_risk="low",
            recommendation="proceed"
        )
    
    def generate_quick_report(
        self,
        result: LightweightValidationResult,
        verbose: bool = False
    ) -> str:
        """Generate human-readable validation report."""
        lines = []
        
        if not result.concerns:
            lines.append("✅ Quick validation passed - no concerns identified")
            return "\n".join(lines)
        
        # Group by severity
        strong = [c for c in result.concerns if c.severity == ConcernSeverity.STRONGLY_RECOMMEND]
        recommend = [c for c in result.concerns if c.severity == ConcernSeverity.RECOMMEND]
        suggest = [c for c in result.concerns if c.severity == ConcernSeverity.SUGGEST]
        
        if strong:
            lines.append("⚠️  STRONGLY RECOMMEND addressing these issues:")
            for concern in strong:
                lines.append(f"  • [{concern.category}] {concern.message}")
                if verbose:
                    lines.append(f"    → {concern.suggested_action}")
            lines.append("")
        
        if recommend:
            lines.append("💡 RECOMMEND reviewing these items:")
            for concern in recommend:
                lines.append(f"  • [{concern.category}] {concern.message}")
                if verbose:
                    lines.append(f"    → {concern.suggested_action}")
            lines.append("")
        
        if suggest and verbose:
            lines.append("ℹ️  SUGGEST considering these improvements:")
            for concern in suggest:
                lines.append(f"  • [{concern.category}] {concern.message}")
            lines.append("")
        
        lines.append(f"Overall risk: {result.estimated_risk.upper()}")
        lines.append(f"Recommendation: {result.recommendation.replace('_', ' ')}")
        
        return "\n".join(lines)


class AdversarialThinkingPrompts:
    """
    Quick adversarial thinking prompts for LLM self-reflection.
    
    These are lightweight - no cryptographic signing, just quick sanity checks.
    """
    
    CODE_REVIEW_QUICK = """
Before finalizing this code, quickly check:
1. Am I using any patterns that could cause SQL injection or XSS?
2. Are there any hardcoded secrets or credentials?
3. Am I handling errors properly (no bare except clauses)?
4. Could this fail with large data volumes (N+1 queries)?
5. Am I mutating any shared state unexpectedly?

If any are YES, flag them for the user.
"""
    
    ARCHITECTURE_QUICK = """
Before providing this architecture guidance, verify:
1. Are my TOGAF/ArchiMate terms used correctly?
2. Would this bypass any governance requirements?
3. Does this maintain proper separation of concerns?
4. Would this scale to enterprise data volumes?

If uncertain, qualify your response.
"""
    
    SECURITY_QUICK = """
Security quick check:
1. Am I suggesting to disable any security controls?
2. Am I accessing user input without validation?
3. Am I generating code that might expose sensitive data?
4. Are my authentication/authorization suggestions sound?

If any concerns, flag them immediately.
"""
    
    EXPLANATION_QUICK = """
Accuracy check:
1. Am I making any absolute claims ("always", "never")?
2. Do I need to qualify any statements with "typically" or "usually"?
3. Am I confident in the technical details I'm providing?
4. Should I suggest verifying any claims?

Add appropriate caveats if needed.
"""


# Singleton
_validator = None

def get_lightweight_validator() -> LightweightAdversarialValidator:
    """Get or create singleton validator."""
    global _validator
    if _validator is None:
        _validator = LightweightAdversarialValidator()
    return _validator
