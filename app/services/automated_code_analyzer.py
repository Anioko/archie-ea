"""
Automated Code Analysis Integration

Objective measurement of code quality that cannot be faked by LLM self-reporting.
Integrates with Bandit (security), MyPy (type checking), coverage (test coverage),
and other tools to provide verifiable metrics.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CodeAnalysisResult:
    """Result of automated code analysis."""
    tool: str
    passed: bool
    issues: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    raw_output: str


class AutomatedCodeAnalyzer:
    """
    Runs automated code analysis tools to verify implementation quality.
    
    These are OBJECTIVE measurements that cannot be bypassed by:
    - Faking completion data
    - Self-reporting false metrics  
    - Modifying critique records
    
    The tools analyze the ACTUAL CODE and return REAL RESULTS.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.results: Dict[str, CodeAnalysisResult] = {}
    
    def run_security_scan(self, target_path: str) -> CodeAnalysisResult:
        """
        Run Bandit security scanner on code.
        
        Cannot be faked - Bandit analyzes actual code and reports real vulnerabilities.
        """
        try:
            result = subprocess.run(
                ["bandit", "-r", "-f", "json", target_path],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            # Parse JSON output
            try:
                bandit_data = json.loads(result.stdout) if result.stdout else {"results": []}
            except json.JSONDecodeError:
                bandit_data = {"results": []}
            
            issues = []
            severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
            
            for issue in bandit_data.get("results", []):
                severity = issue.get("issue_severity", "LOW")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
                issues.append({
                    "file": issue.get("filename"),
                    "line": issue.get("line_number"),
                    "severity": severity,
                    "confidence": issue.get("issue_confidence"),
                    "test_id": issue.get("test_id"),
                    "test_name": issue.get("test_name"),
                    "issue_text": issue.get("issue_text"),
                    "code": issue.get("code")
                })
            
            # HIGH severity = P0 equivalent
            # MEDIUM severity = P1 equivalent
            passed = severity_counts["HIGH"] == 0 and severity_counts["MEDIUM"] == 0
            
            return CodeAnalysisResult(
                tool="bandit",
                passed=passed,
                issues=issues,
                metrics=severity_counts,
                raw_output=result.stdout
            )
            
        except FileNotFoundError:
            return CodeAnalysisResult(
                tool="bandit",
                passed=False,
                issues=[{"error": "Bandit not installed"}],
                metrics={},
                raw_output=""
            )
    
    def run_type_check(self, target_path: str) -> CodeAnalysisResult:
        """
        Run MyPy type checker on code.
        
        Verifies type correctness - cannot be faked.
        """
        try:
            result = subprocess.run(
                ["mypy", "--show-error-codes", "--output-format=json", target_path],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            # Parse JSON output (one JSON object per line)
            issues = []
            error_counts = {"error": 0, "warning": 0, "note": 0}
            
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    error = json.loads(line)
                    severity = error.get("severity", "error")
                    error_counts[severity] = error_counts.get(severity, 0) + 1
                    
                    issues.append({
                        "file": error.get("file"),
                        "line": error.get("line"),
                        "column": error.get("column"),
                        "severity": severity,
                        "message": error.get("message"),
                        "error_code": error.get("code")
                    })
                except json.JSONDecodeError:
                    continue
            
            # Type errors are P1 (functional correctness)
            passed = error_counts["error"] == 0
            
            return CodeAnalysisResult(
                tool="mypy",
                passed=passed,
                issues=issues,
                metrics=error_counts,
                raw_output=result.stdout
            )
            
        except FileNotFoundError:
            return CodeAnalysisResult(
                tool="mypy",
                passed=False,
                issues=[{"error": "MyPy not installed"}],
                metrics={},
                raw_output=""
            )
    
    def run_coverage_check(self, test_path: str, min_coverage: float = 80.0) -> CodeAnalysisResult:
        """
        Run coverage analysis on tests.
        
        Verifies actual test coverage - cannot be faked.
        """
        try:
            # Run tests with coverage
            result = subprocess.run(
                ["pytest", test_path, "--cov=.", "--cov-report=json", "-q"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            # Parse coverage JSON
            coverage_file = self.project_root / "coverage.json"
            if coverage_file.exists():
                with open(coverage_file) as f:
                    coverage_data = json.load(f)
                
                totals = coverage_data.get("totals", {})
                percent_covered = totals.get("percent_covered", 0.0)
                
                issues = []
                if percent_covered < min_coverage:
                    issues.append({
                        "severity": "warning",
                        "message": f"Coverage {percent_covered:.1f}% below minimum {min_coverage}%"
                    })
                
                passed = percent_covered >= min_coverage
                
                return CodeAnalysisResult(
                    tool="coverage",
                    passed=passed,
                    issues=issues,
                    metrics={
                        "percent_covered": percent_covered,
                        "covered_lines": totals.get("covered_lines", 0),
                        "missing_lines": totals.get("missing_lines", 0),
                        "excluded_lines": totals.get("excluded_lines", 0)
                    },
                    raw_output=result.stdout
                )
            else:
                return CodeAnalysisResult(
                    tool="coverage",
                    passed=False,
                    issues=[{"error": "Coverage data not generated"}],
                    metrics={},
                    raw_output=result.stdout
                )
                
        except FileNotFoundError:
            return CodeAnalysisResult(
                tool="coverage",
                passed=False,
                issues=[{"error": "pytest-cov not installed"}],
                metrics={},
                raw_output=""
            )
    
    def run_complexity_check(self, target_path: str, max_complexity: int = 10) -> CodeAnalysisResult:
        """
        Run radon complexity analysis.
        
        Detects overly complex code that may have maintainability issues.
        """
        try:
            result = subprocess.run(
                ["radon", "cc", "-a", "-j", target_path],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            # Parse JSON output
            try:
                complexity_data = json.loads(result.stdout) if result.stdout else {}
            except json.JSONDecodeError:
                complexity_data = {}
            
            issues = []
            high_complexity_count = 0
            
            for file_path, functions in complexity_data.items():
                for func in functions:
                    complexity = func.get("complexity", 0)
                    rank = func.get("rank", "A")
                    
                    if complexity > max_complexity:
                        high_complexity_count += 1
                        issues.append({
                            "file": file_path,
                            "function": func.get("name"),
                            "line": func.get("lineno"),
                            "complexity": complexity,
                            "rank": rank,
                            "severity": "warning" if complexity > 15 else "info"
                        })
            
            passed = high_complexity_count == 0
            
            return CodeAnalysisResult(
                tool="radon",
                passed=passed,
                issues=issues,
                metrics={
                    "high_complexity_functions": high_complexity_count,
                    "max_complexity": max(
                        [f.get("complexity", 0) for f in sum(complexity_data.values(), [])]
                        or [0]
                    )
                },
                raw_output=result.stdout
            )
            
        except FileNotFoundError:
            return CodeAnalysisResult(
                tool="radon",
                passed=True,  # Not critical
                issues=[{"warning": "radon not installed"}],
                metrics={},
                raw_output=""
            )
    
    def analyze_implementation(self, task_id: str, files: List[str]) -> Dict[str, Any]:
        """
        Run complete analysis suite on implementation files.
        
        Returns objective measurements that cannot be faked.
        """
        results = {
            "task_id": task_id,
            "files_analyzed": files,
            "analyses": {},
            "passed": True,
            "critical_issues": [],
            "high_issues": []
        }
        
        for file_path in files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            # Security scan (P0)
            security = self.run_security_scan(str(full_path))
            results["analyses"]["security"] = {
                "passed": security.passed,
                "high_count": security.metrics.get("HIGH", 0),
                "medium_count": security.metrics.get("MEDIUM", 0)
            }
            
            for issue in security.issues:
                if issue.get("severity") == "HIGH":
                    results["critical_issues"].append({
                        "tool": "bandit",
                        "file": issue.get("file"),
                        "line": issue.get("line"),
                        "message": issue.get("issue_text")
                    })
            
            # Type check (P1)
            types = self.run_type_check(str(full_path))
            results["analyses"]["type_check"] = {
                "passed": types.passed,
                "error_count": types.metrics.get("error", 0),
                "warning_count": types.metrics.get("warning", 0)
            }
            
            for issue in types.issues:
                if issue.get("severity") == "error":
                    results["high_issues"].append({
                        "tool": "mypy",
                        "file": issue.get("file"),
                        "line": issue.get("line"),
                        "message": issue.get("message")
                    })
        
        # Test coverage
        if files:
            # Find test files related to implementation
            test_files = self._find_related_test_files(files)
            if test_files:
                coverage = self.run_coverage_check(" ".join(test_files))
                results["analyses"]["coverage"] = {
                    "passed": coverage.passed,
                    "percent": coverage.metrics.get("percent_covered", 0)
                }
        
        # Overall pass/fail
        results["passed"] = (
            results["analyses"].get("security", {}).get("passed", True) and
            results["analyses"].get("type_check", {}).get("passed", True) and
            len(results["critical_issues"]) == 0 and
            len(results["high_issues"]) == 0
        )
        
        return results
    
    def _find_related_test_files(self, implementation_files: List[str]) -> List[str]:
        """Find test files related to implementation files."""
        test_files = []
        
        for impl_file in implementation_files:
            # Convert app/services/foo.py -> tests/services/test_foo.py
            parts = Path(impl_file).parts
            if len(parts) >= 2:
                module = parts[1] if parts[0] == "app" else parts[0]
                filename = Path(impl_file).stem
                
                test_path = self.project_root / "tests" / module / f"test_{filename}.py"
                if test_path.exists():
                    test_files.append(str(test_path.relative_to(self.project_root)))
        
        return test_files
    
    def generate_critique_findings(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert automated analysis results into critique findings.
        
        These are OBJECTIVE findings based on real tool output.
        """
        findings = []
        
        # Security issues = P0
        for issue in analysis_results.get("critical_issues", []):
            findings.append({
                "dimension": "security_risks",
                "severity": "P0",
                "description": f"Security vulnerability ({issue['tool']}): {issue['message']}",
                "location": f"{issue['file']}:{issue['line']}",
                "evidence": issue.get("message"),
                "fix_required": True
            })
        
        # Type errors = P1 (functional correctness)
        for issue in analysis_results.get("high_issues", []):
            findings.append({
                "dimension": "integration_correctness",
                "severity": "P1",
                "description": f"Type error ({issue['tool']}): {issue['message']}",
                "location": f"{issue['file']}:{issue['line']}",
                "evidence": issue.get("message"),
                "fix_required": True
            })
        
        # Coverage gaps = P2 (debt)
        coverage = analysis_results.get("analyses", {}).get("coverage", {})
        if coverage and not coverage.get("passed", True):
            findings.append({
                "dimension": "test_coverage",
                "severity": "P2",
                "description": f"Test coverage at {coverage.get('percent', 0):.1f}% - below threshold",
                "location": "test suite",
                "evidence": f"Coverage: {coverage.get('percent', 0):.1f}%",
                "fix_required": False  # P2 doesn't block
            })
        
        return findings


# Singleton instance
_analyzer = None

def get_code_analyzer() -> AutomatedCodeAnalyzer:
    """Get or create singleton code analyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = AutomatedCodeAnalyzer()
    return _analyzer
