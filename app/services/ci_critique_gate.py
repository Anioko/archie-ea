"""
CI/CD Critique Gate - External Enforcement

This module provides CI/CD pipeline integration that LLM cannot bypass.
The CI system is EXTERNAL to the LLM - it runs in GitHub Actions, GitLab CI,
or other CI/CD infrastructure that the implementing agent has no control over.
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.critique_verification_service import get_critique_service
from app.services.automated_code_analyzer import get_code_analyzer


@dataclass
class CritiqueGateResult:
    """Result of CI/CD critique gate check."""
    passed: bool
    blocking_reasons: List[str]
    warnings: List[str]
    session_id: Optional[str] = None
    verification_hash: Optional[str] = None


class CICDCritiqueGate:
    """
    CI/CD gate that enforces adversarial review before allowing deployment.
    
    This runs in the CI/CD pipeline (GitHub Actions, GitLab CI) and:
    1. Verifies cryptographic critique signatures
    2. Runs automated code analysis
    3. Checks for unresolved P0/P1 findings
    4. FAILS the build if requirements not met
    
    The implementing LLM CANNOT bypass this because:
    - It runs in external CI/CD infrastructure
    - Requires cryptographically signed critique records
    - Uses objective code analysis tools (Bandit, MyPy, etc.)
    - CI/CD pipeline blocks merge/deploy if gate fails
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.critique_service = get_critique_service()
        self.code_analyzer = get_code_analyzer()
    
    def check_critique_gate(self, task_id: str, changed_files: List[str]) -> CritiqueGateResult:
        """
        Run complete critique gate check.
        
        This is called by CI/CD pipeline and cannot be bypassed.
        """
        blocking_reasons = []
        warnings = []
        session_id = None
        verification_hash = None
        
        # 1. Verify cryptographic critique record exists
        is_valid, details = self.critique_service.verify_task_critique(task_id)
        
        if not is_valid:
            blocking_reasons.append(
                f"Critique verification failed: {details.get('error', 'Unknown error')}"
            )
            return CritiqueGateResult(
                passed=False,
                blocking_reasons=blocking_reasons,
                warnings=warnings,
                session_id=None,
                verification_hash=None
            )
        
        session_id = details.get("session_id")
        verification_hash = details.get("content_hash")
        
        # Check for unresolved P0/P1
        if details.get("p0_count", 0) > 0:
            blocking_reasons.append(
                f"Unresolved P0 findings: {details['p0_count']} critical issues must be fixed"
            )
        
        if details.get("p1_count", 0) > 0:
            blocking_reasons.append(
                f"Unresolved P1 findings: {details['p1_count']} high issues must be fixed"
            )
        
        # 2. Run automated code analysis (objective, cannot be faked)
        analysis_results = self.code_analyzer.analyze_implementation(task_id, changed_files)
        
        # Security issues are P0
        if analysis_results["analyses"].get("security", {}).get("high_count", 0) > 0:
            blocking_reasons.append(
                f"Security scan found {analysis_results['analyses']['security']['high_count']} HIGH severity issues"
            )
        
        # Type errors are P1
        if analysis_results["analyses"].get("type_check", {}).get("error_count", 0) > 0:
            blocking_reasons.append(
                f"Type check found {analysis_results['analyses']['type_check']['error_count']} errors"
            )
        
        # Coverage gaps are warnings (P2)
        coverage = analysis_results["analyses"].get("coverage", {})
        if coverage and coverage.get("percent", 0) < 80:
            warnings.append(
                f"Test coverage at {coverage['percent']:.1f}% (recommended: 80%+)"
            )
        
        # 3. Check that critique agent was different from implementer
        # This prevents self-critique (same model reviewing its own work)
        ledger_path = self.critique_service.ledger_path
        session_file = ledger_path / f"{session_id}.json"
        
        if session_file.exists():
            with open(session_file) as f:
                session_data = json.load(f)
            
            implementer = session_data.get("implementer_agent", "unknown")
            critique_agent = session_data.get("critique_agent", "unknown")
            
            if implementer == critique_agent:
                blocking_reasons.append(
                    "Critique agent same as implementer - self-review not allowed. "
                    "Must use separate critique agent."
                )
        
        # Gate passes only if no blocking reasons
        passed = len(blocking_reasons) == 0
        
        return CritiqueGateResult(
            passed=passed,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
            session_id=session_id,
            verification_hash=verification_hash
        )
    
    def generate_report(self, result: CritiqueGateResult) -> str:
        """Generate human-readable gate report for CI/CD logs."""
        lines = [
            "=" * 70,
            "MANDATORY ADVERSARIAL REVIEW GATE",
            "=" * 70,
            "",
        ]
        
        if result.passed:
            lines.extend([
                "✅ GATE PASSED",
                "",
                f"Session ID: {result.session_id}",
                f"Verification Hash: {result.verification_hash[:16]}...",
                "",
                "All requirements met. Proceeding with deployment.",
            ])
        else:
            lines.extend([
                "❌ GATE FAILED - DEPLOYMENT BLOCKED",
                "",
                "Blocking Issues:",
            ])
            
            for reason in result.blocking_reasons:
                lines.append(f"  • {reason}")
            
            lines.extend([
                "",
                "Required Actions:",
                "  1. Run adversarial critique with separate critique agent",
                "  2. Fix all P0 (critical) and P1 (high) findings",
                "  3. Ensure security scan passes (Bandit)",
                "  4. Ensure type checking passes (MyPy)",
                "  5. Re-trigger CI/CD after fixes",
            ])
        
        if result.warnings:
            lines.extend([
                "",
                "Warnings (non-blocking):",
            ])
            for warning in result.warnings:
                lines.append(f"  ⚠️  {warning}")
        
        lines.extend([
            "",
            "=" * 70,
        ])
        
        return "\n".join(lines)


def main():
    """
    Main entry point for CI/CD execution.
    
    Usage in GitHub Actions:
    
    - name: Mandatory Adversarial Review Gate
      run: python -m app.services.ci_critique_gate
      env:
        TASK_ID: ${{ github.event.pull_request.title }}
        CHANGED_FILES: ${{ steps.changed-files.outputs.all_changed_files }}
    """
    task_id = os.environ.get("TASK_ID")
    changed_files_str = os.environ.get("CHANGED_FILES", "")
    
    if not task_id:
        print("❌ ERROR: TASK_ID environment variable not set")
        sys.exit(1)
    
    changed_files = changed_files_str.split() if changed_files_str else []
    
    gate = CICDCritiqueGate()
    result = gate.check_critique_gate(task_id, changed_files)
    
    # Print report
    report = gate.generate_report(result)
    print(report)
    
    # Exit with appropriate code
    if result.passed:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
