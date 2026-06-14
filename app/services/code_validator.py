"""
Code Validation Service - Validates generated code for security and quality.

Adapted from MDD flask-base-master for archie integration.
Performs syntax checking, security scanning, and quality validation before
code artifacts are saved to the database.
"""
import ast
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of code validation."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metrics: Dict[str, any]

    def __str__(self):
        if self.is_valid:
            return f"✓ Valid ({len(self.warnings)} warnings)"
        return f"✗ Invalid ({len(self.errors)} errors, {len(self.warnings)} warnings)"


class CodeValidator:
    """Validates generated code for security, syntax, and quality."""

    SECURITY_PATTERNS = {
        "python": [
            (r"eval\s*\(", "Dangerous eval() call detected"),
            (r"exec\s*\(", "Dangerous exec() call detected"),
            (r"__import__\s*\(", "Dynamic import detected"),
            (r"pickle\.loads?\s*\(", "Unsafe pickle usage detected"),
            (r"subprocess\.call\s*\([^)]*shell\s*=\s*True", "Shell injection risk"),
            (r"os\.system\s*\(", "OS command execution detected"),
            (r'password\s*=\s*["\'][^"\']{3,}["\']', "Hardcoded password detected"),
            (r'api[_-]?key\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded API key detected"),
            (r'secret\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded secret detected"),
            (r"(?:SELECT|DELETE|UPDATE|INSERT)\s+.*\+.*", "Potential SQL injection"),
        ],
        "java": [
            (r"Runtime\.getRuntime\(\)\.exec", "Command execution detected"),
            (r"Class\.forName\(", "Dynamic class loading detected"),
            (r"new\s+ProcessBuilder\s*\(", "Process execution detected"),
            (r'password\s*=\s*"[^"]{3,}"', "Hardcoded password detected"),
            (r"Statement\.executeQuery\([^?]*\+", "Potential SQL injection"),
        ],
        "javascript": [
            (r"eval\s*\(", "Dangerous eval() call detected"),
            (r"innerHTML\s*=", "XSS risk with innerHTML"),
            (r"document\.write\s*\(", "Dangerous document.write detected"),
            (r'password\s*=\s*["\'][^"\']{3,}["\']', "Hardcoded password detected"),
        ],
        "typescript": [
            (r"eval\s*\(", "Dangerous eval() call detected"),
            (r"innerHTML\s*=", "XSS risk with innerHTML"),
            (r"any\s+\w+", 'Loose typing with "any" detected'),
        ],
        "salesforce": [
            (r"Database\.query\([^:]*\+", "Potential SOQL injection"),
            (r"without\s+sharing", "Security: class without sharing"),
            (r"PageReference\([^)]*\+", "Potential redirect vulnerability"),
        ],
    }

    @staticmethod
    def validate(code: str, language: str, filename: str = None) -> ValidationResult:
        """
        Validate generated code.

        Args:
            code: Source code to validate
            language: Programming language
            filename: Optional filename for context

        Returns:
            ValidationResult with errors, warnings, and metrics
        """
        logger.info(f"Validating {language} code ({len(code)} chars)")

        errors = []
        warnings = []
        metrics = {
            "lines": len(code.split("\n")),
            "size_bytes": len(code.encode("utf-8")),
            "language": language,
        }

        if not code or not code.strip():
            errors.append("Code is empty")
            return ValidationResult(False, errors, warnings, metrics)

        if len(code) > 1_000_000:
            errors.append(f"Code too large: {len(code)} chars (max 1MB)")

        syntax_valid, syntax_errors = CodeValidator._validate_syntax(code, language)
        if not syntax_valid:
            errors.extend(syntax_errors)

        security_issues = CodeValidator._scan_security(code, language)
        if security_issues:
            errors.extend(security_issues)

        quality_warnings = CodeValidator._check_quality(code, language)
        warnings.extend(quality_warnings)

        metrics.update(CodeValidator._calculate_metrics(code, language))

        is_valid = len(errors) == 0
        result = ValidationResult(is_valid, errors, warnings, metrics)

        if is_valid:
            logger.info(f"✓ Code validation passed: {filename or 'unnamed'}")
        else:
            logger.warning(f"✗ Code validation failed: {len(errors)} errors")

        return result

    @staticmethod
    def _validate_syntax(code: str, language: str) -> Tuple[bool, List[str]]:
        """Validate code syntax."""
        errors = []

        if language.lower() == "python":
            try:
                ast.parse(code)
                return True, []
            except SyntaxError as e:
                errors.append(f"Python syntax error at line {e.lineno}: {e.msg}")
                return False, errors
            except Exception as e:
                errors.append(f"Python parsing error: {str(e)}")
                return False, errors

        elif language.lower() in ["java", "javascript", "typescript", "salesforce"]:
            open_braces = code.count("{")
            close_braces = code.count("}")
            if open_braces != close_braces:
                errors.append(f"Unmatched braces: {open_braces} open, {close_braces} close")
                return False, errors

            open_parens = code.count("(")
            close_parens = code.count(")")
            if open_parens != close_parens:
                errors.append(f"Unmatched parentheses: {open_parens} open, {close_parens} close")
                return False, errors

        return True, []

    @staticmethod
    def _scan_security(code: str, language: str) -> List[str]:
        """Scan for security vulnerabilities."""
        issues = []
        patterns = CodeValidator.SECURITY_PATTERNS.get(language.lower(), [])

        for pattern, message in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"Security: {message}")

        return issues

    @staticmethod
    def _check_quality(code: str, language: str) -> List[str]:
        """Check code quality."""
        warnings = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                warnings.append(f"Line {i} exceeds 120 characters")

        if language.lower() == "python":
            if "TODO" in code or "FIXME" in code:
                warnings.append("Contains TODO/FIXME comments")

            if code.count("import *") > 0:
                warnings.append("Wildcard imports detected")

        return warnings

    @staticmethod
    def _calculate_metrics(code: str, language: str) -> Dict:
        """Calculate code metrics."""
        lines = code.split("\n")

        metrics = {
            "total_lines": len(lines),
            "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith("#")]),
            "comment_lines": len([l for l in lines if l.strip().startswith("#")]),
            "blank_lines": len([l for l in lines if not l.strip()]),
        }

        if language.lower() == "python":
            metrics["functions"] = code.count("def ")
            metrics["classes"] = code.count("class ")
        elif language.lower() in ["java", "javascript", "typescript"]:
            metrics["functions"] = code.count("function ") + code.count(") {")
            metrics["classes"] = code.count("class ")

        return metrics


def validate_code_artifact(code: str, language: str, filename: str = None) -> ValidationResult:
    """
    Convenience function for validating code artifacts.

    Args:
        code: Source code to validate
        language: Programming language
        filename: Optional filename

    Returns:
        ValidationResult

    Raises:
        ValueError: If validation fails
    """
    result = CodeValidator.validate(code, language, filename)

    if not result.is_valid:
        error_msg = f"Code validation failed: {', '.join(result.errors)}"
        raise ValueError(error_msg)

    return result
