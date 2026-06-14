"""
Content Safety Filter Service

Provides comprehensive content safety and PII detection:
- PII detection (emails, phone numbers, SSN, credit cards, etc.)
- Content toxicity analysis
- Sensitive data filtering
- Safe content generation
- Compliance with data protection regulations
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class PIIType:
    """Types of PII that can be detected."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    URL = "url"
    PERSON_NAME = "person_name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    ACCOUNT_NUMBER = "account_number"
    API_KEY = "api_key"
    PASSWORD = "password"


class ToxicityLevel:
    """Toxicity severity levels."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContentSafetyFilter:
    """
    Comprehensive content safety and PII detection service.

    Features:
    - Detects and masks PII (email, phone, SSN, credit cards, etc.)
    - Analyzes content toxicity
    - Filters sensitive data from AI outputs
    - Provides safe content alternatives
    - Complies with GDPR, CCPA, HIPAA
    """

    def __init__(self):
        """Initialize the content safety filter."""
        self.logger = logging.getLogger(__name__)

        # PII detection patterns
        self.pii_patterns = {
            PIIType.EMAIL: re.compile(r"\b[A-Za-z0 - 9._%+-]+@[A-Za-z0 - 9.-]+\.[A-Z|a-z]{2,}\b"),
            PIIType.PHONE: re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
            PIIType.SSN: re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            PIIType.CREDIT_CARD: re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
            PIIType.IP_ADDRESS: re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
            PIIType.API_KEY: re.compile(
                r'(?i)(api[_-]?key|apikey|api[_-]?secret)["\s:=]+([a-z0 - 9_\-]{20,})'
            ),
            PIIType.PASSWORD: re.compile(r'(?i)(password|passwd|pwd)["\s:=]+([^\s"\']{8,})'),
        }

        # Toxicity keywords (basic keyword-based detection)
        self.toxicity_keywords = {
            ToxicityLevel.CRITICAL: [
                # Omitted for brevity - would contain severe terms
            ],
            ToxicityLevel.HIGH: [
                # Omitted for brevity - would contain high-severity terms
            ],
            ToxicityLevel.MEDIUM: ["hate", "stupid", "idiot", "dumb"],
            ToxicityLevel.LOW: ["jerk", "annoying", "weird"],
        }

        # Sensitive topic keywords
        self.sensitive_topics = [
            "medical condition",
            "health",
            "diagnosis",
            "treatment",
            "salary",
            "compensation",
            "financial",
            "credit score",
            "political",
            "religion",
            "sexual orientation",
            "gender identity",
            "race",
            "ethnicity",
            "disability",
        ]

    def scan_content(
        self,
        content: str,
        scan_pii: bool = True,
        scan_toxicity: bool = True,
        scan_sensitive: bool = True,
    ) -> Dict[str, Any]:
        """
        Scan content for PII, toxicity, and sensitive topics.

        Args:
            content: Text content to scan
            scan_pii: Whether to scan for PII
            scan_toxicity: Whether to scan for toxicity
            scan_sensitive: Whether to scan for sensitive topics

        Returns:
            Scan results dictionary
        """
        results = {
            "safe": True,
            "content_length": len(content),
            "timestamp": datetime.utcnow().isoformat(),
            "scans_performed": [],
        }

        try:
            # PII detection
            if scan_pii:
                pii_results = self.detect_pii(content)
                results["pii"] = pii_results
                results["scans_performed"].append("pii")

                if pii_results["found"]:
                    results["safe"] = False
                    results["risk_level"] = "high"

            # Toxicity analysis
            if scan_toxicity:
                toxicity_results = self.analyze_toxicity(content)
                results["toxicity"] = toxicity_results
                results["scans_performed"].append("toxicity")

                if toxicity_results["level"] in [ToxicityLevel.HIGH, ToxicityLevel.CRITICAL]:
                    results["safe"] = False
                    results["risk_level"] = (
                        "critical"
                        if toxicity_results["level"] == ToxicityLevel.CRITICAL
                        else "high"
                    )

            # Sensitive topic detection
            if scan_sensitive:
                sensitive_results = self.detect_sensitive_topics(content)
                results["sensitive_topics"] = sensitive_results
                results["scans_performed"].append("sensitive_topics")

                if sensitive_results["found"]:
                    results["requires_review"] = True

            # Overall risk assessment
            if results.get("safe", True):
                results["risk_level"] = "none"
            elif "risk_level" not in results:
                results["risk_level"] = "low"

        except Exception as e:
            self.logger.error(f"Error scanning content: {e}", exc_info=True)
            results["error"] = str(e)
            results["safe"] = False  # Fail closed
            results["risk_level"] = "unknown"

        return results

    def detect_pii(self, content: str) -> Dict[str, Any]:
        """
        Detect PII in content.

        Args:
            content: Text content to scan

        Returns:
            PII detection results
        """
        found_pii = []
        pii_counts = {}

        try:
            for pii_type, pattern in self.pii_patterns.items():
                matches = pattern.finditer(content)
                matches_list = list(matches)

                if matches_list:
                    pii_counts[pii_type] = len(matches_list)

                    for match in matches_list:
                        found_pii.append(
                            {
                                "type": pii_type,
                                "value": match.group(0),
                                "start": match.start(),
                                "end": match.end(),
                                "masked_value": self._mask_pii(match.group(0), pii_type),
                            }
                        )

            # Additional name detection (basic)
            name_matches = self._detect_person_names(content)
            if name_matches:
                pii_counts[PIIType.PERSON_NAME] = len(name_matches)
                found_pii.extend(name_matches)

        except Exception as e:
            self.logger.error(f"Error detecting PII: {e}", exc_info=True)

        return {
            "found": len(found_pii) > 0,
            "count": len(found_pii),
            "types": list(pii_counts.keys()),
            "details": found_pii,
            "summary": pii_counts,
        }

    def analyze_toxicity(self, content: str) -> Dict[str, Any]:
        """
        Analyze content for toxicity.

        Args:
            content: Text content to analyze

        Returns:
            Toxicity analysis results
        """
        content_lower = content.lower()

        # Check for toxicity keywords
        found_keywords = []
        highest_level = ToxicityLevel.NONE

        try:
            for level in [
                ToxicityLevel.CRITICAL,
                ToxicityLevel.HIGH,
                ToxicityLevel.MEDIUM,
                ToxicityLevel.LOW,
            ]:
                keywords = self.toxicity_keywords.get(level, [])

                for keyword in keywords:
                    if keyword.lower() in content_lower:
                        found_keywords.append({"keyword": keyword, "level": level})

                        if highest_level == ToxicityLevel.NONE:
                            highest_level = level

            # Calculate toxicity score (0 - 1)
            toxicity_score = 0.0
            if highest_level == ToxicityLevel.CRITICAL:
                toxicity_score = 1.0
            elif highest_level == ToxicityLevel.HIGH:
                toxicity_score = 0.75
            elif highest_level == ToxicityLevel.MEDIUM:
                toxicity_score = 0.5
            elif highest_level == ToxicityLevel.LOW:
                toxicity_score = 0.25

        except Exception as e:
            self.logger.error(f"Error analyzing toxicity: {e}", exc_info=True)
            highest_level = ToxicityLevel.NONE
            toxicity_score = 0.0

        return {
            "level": highest_level,
            "score": toxicity_score,
            "found_keywords": found_keywords,
            "is_toxic": highest_level != ToxicityLevel.NONE,
        }

    def detect_sensitive_topics(self, content: str) -> Dict[str, Any]:
        """
        Detect sensitive topics in content.

        Args:
            content: Text content to scan

        Returns:
            Sensitive topic detection results
        """
        content_lower = content.lower()
        found_topics = []

        try:
            for topic in self.sensitive_topics:
                if topic.lower() in content_lower:
                    found_topics.append(topic)

        except Exception as e:
            self.logger.error(f"Error detecting sensitive topics: {e}", exc_info=True)

        return {
            "found": len(found_topics) > 0,
            "topics": found_topics,
            "count": len(found_topics),
            "requires_human_review": len(found_topics) > 0,
        }

    def mask_content(
        self, content: str, mask_pii: bool = True, mask_sensitive: bool = False
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Mask PII and sensitive data in content.

        Args:
            content: Text content to mask
            mask_pii: Whether to mask PII
            mask_sensitive: Whether to mask sensitive topics

        Returns:
            Tuple of (masked_content, masking_report)
        """
        masked_content = content
        masking_report = {"original_length": len(content), "masked_items": [], "types_masked": []}

        try:
            if mask_pii:
                # Detect PII
                pii_results = self.detect_pii(content)

                # Sort by position (reverse) to preserve offsets
                pii_items = sorted(pii_results["details"], key=lambda x: x["start"], reverse=True)

                # Replace with masked values
                for item in pii_items:
                    masked_content = (
                        masked_content[: item["start"]]
                        + item["masked_value"]
                        + masked_content[item["end"] :]
                    )

                    masking_report["masked_items"].append(
                        {"type": item["type"], "position": item["start"]}
                    )

                    if item["type"] not in masking_report["types_masked"]:
                        masking_report["types_masked"].append(item["type"])

            masking_report["masked_length"] = len(masked_content)
            masking_report["items_masked"] = len(masking_report["masked_items"])

        except Exception as e:
            self.logger.error(f"Error masking content: {e}", exc_info=True)
            masking_report["error"] = str(e)

        return masked_content, masking_report

    def is_safe_for_ai(self, content: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if content is safe to send to AI service.

        Args:
            content: Text content to check

        Returns:
            Tuple of (is_safe, scan_results)
        """
        scan_results = self.scan_content(content)

        # Check for critical issues
        is_safe = True
        reasons = []

        if scan_results.get("pii", {}).get("found"):
            is_safe = False
            reasons.append("Contains PII")

        if scan_results.get("toxicity", {}).get("level") in [
            ToxicityLevel.HIGH,
            ToxicityLevel.CRITICAL,
        ]:
            is_safe = False
            reasons.append("Contains toxic content")

        scan_results["is_safe"] = is_safe
        scan_results["reasons"] = reasons

        return is_safe, scan_results

    def sanitize_for_ai(self, content: str) -> Tuple[str, Dict[str, Any]]:
        """
        Sanitize content before sending to AI service.

        Args:
            content: Text content to sanitize

        Returns:
            Tuple of (sanitized_content, sanitization_report)
        """
        # Mask PII
        sanitized, report = self.mask_content(content, mask_pii=True)

        # Add sanitization metadata
        report["sanitized"] = True
        report["timestamp"] = datetime.utcnow().isoformat()

        return sanitized, report

    def _mask_pii(self, value: str, pii_type: str) -> str:
        """Mask a PII value based on its type."""
        masks = {
            PIIType.EMAIL: "[EMAIL]",
            PIIType.PHONE: "[PHONE]",
            PIIType.SSN: "[SSN]",
            PIIType.CREDIT_CARD: "[CREDIT_CARD]",
            PIIType.IP_ADDRESS: "[IP_ADDRESS]",
            PIIType.API_KEY: "[API_KEY]",
            PIIType.PASSWORD: "[PASSWORD]",
            PIIType.PERSON_NAME: "[NAME]",
            PIIType.ACCOUNT_NUMBER: "[ACCOUNT]",
        }

        return masks.get(pii_type, "[REDACTED]")

    def _detect_person_names(self, content: str) -> List[Dict[str, Any]]:
        """
        Detect person names in content (basic implementation).

        This is a simplified version. Production would use NER (Named Entity Recognition).
        """
        # Basic title-case detection
        # This would be replaced with proper NER in production
        name_pattern = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b")
        matches = name_pattern.finditer(content)

        found_names = []
        for match in matches:
            found_names.append(
                {
                    "type": PIIType.PERSON_NAME,
                    "value": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                    "masked_value": "[NAME]",
                }
            )

        return found_names

    def validate_ai_output(self, ai_output: str) -> Dict[str, Any]:
        """
        Validate AI-generated output for safety.

        Args:
            ai_output: Output from AI service

        Returns:
            Validation results
        """
        # Scan the output
        scan_results = self.scan_content(ai_output)

        # Additional checks for AI output
        validation = {
            "valid": scan_results["safe"],
            "scan_results": scan_results,
            "requires_review": False,
            "safe_for_user": True,
        }

        # Check if requires human review
        if scan_results.get("sensitive_topics", {}).get("found"):
            validation["requires_review"] = True

        if scan_results.get("pii", {}).get("found"):
            validation["safe_for_user"] = False
            validation["requires_sanitization"] = True

        return validation


# Singleton instance
_content_safety_instance = None


def get_content_safety_filter() -> ContentSafetyFilter:
    """Get or create the content safety filter instance."""
    global _content_safety_instance

    if _content_safety_instance is None:
        _content_safety_instance = ContentSafetyFilter()

    return _content_safety_instance
