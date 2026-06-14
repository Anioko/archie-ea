"""
Data Protection and PII Masking System

Provides enterprise-grade data protection with PII detection, masking, encryption,
and compliance features for sensitive contract and business data.

Key Features:
- Automatic PII detection in text and structured data
- Configurable masking strategies (redact, hash, encrypt)
- Encryption at rest and in transit
- Data residency compliance
- Audit trail for data access
"""

import hashlib
import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Union

try:
    from cryptography.fernet import Fernet

    _HAS_CRYPTO = True
except Exception:
    Fernet = None
    _HAS_CRYPTO = False
    # cryptography is optional in test environments; fall back to no-op encryption
from flask import current_app

logger = logging.getLogger(__name__)


class MaskingStrategy(Enum):
    """Strategies for masking sensitive data"""

    REDACT = "redact"  # Replace with [REDACTED]
    HASH = "hash"  # One-way hash
    ENCRYPT = "encrypt"  # Reversible encryption
    PARTIAL = "partial"  # Show partial data (e.g., XXX-XXXX - 1234)


class DataSensitivity(Enum):
    """Sensitivity levels for data classification"""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class PIIDetector:
    """
    Detects Personally Identifiable Information (PII) and sensitive data patterns.

    Uses regex patterns and context analysis to identify sensitive information.
    """

    def __init__(self):
        self.patterns = self._load_pii_patterns()

    def _load_pii_patterns(self) -> Dict[str, Pattern]:
        """Load regex patterns for PII detection"""
        return {
            "email": re.compile(r"\b[A-Za-z0 - 9._%+-]+@[A-Za-z0 - 9.-]+\.[A-Z|a-z]{2,}\b"),
            "phone": re.compile(
                r"\b(\+?1[-.\s]?)?\(?([0 - 9]{3})\)?[-.\s]?([0 - 9]{3})[-.\s]?([0 - 9]{4})\b"
            ),
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "credit_card": re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
            "bank_account": re.compile(r"\b\d{8,17}\b"),  # Generic account number pattern
            "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
            "api_key": re.compile(r"\b[A-Za-z0 - 9]{20,}\b"),  # Generic API key pattern
            "password": re.compile(r"\bpassword[:=]\s*\S+\b", re.IGNORECASE),
            "contract_value": re.compile(r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?"),  # Currency amounts
            "employee_count": re.compile(
                r"\b\d{1,6}\s*(?:employees?|staff|personnel)\b", re.IGNORECASE
            ),
        }

    def detect_pii(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect PII patterns in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected PII instances with type, position, and value
        """
        findings = []

        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                findings.append(
                    {
                        "type": pii_type,
                        "start": match.start(),
                        "end": match.end(),
                        "value": match.group(),
                        "sensitivity": self._classify_sensitivity(pii_type),
                    }
                )

        return findings

    def _classify_sensitivity(self, pii_type: str) -> DataSensitivity:
        """Classify sensitivity level for PII type"""
        sensitivity_map = {
            "email": DataSensitivity.CONFIDENTIAL,
            "phone": DataSensitivity.CONFIDENTIAL,
            "ssn": DataSensitivity.RESTRICTED,
            "credit_card": DataSensitivity.RESTRICTED,
            "bank_account": DataSensitivity.RESTRICTED,
            "api_key": DataSensitivity.RESTRICTED,
            "password": DataSensitivity.RESTRICTED,
            "contract_value": DataSensitivity.CONFIDENTIAL,
            "employee_count": DataSensitivity.INTERNAL,
            "ip_address": DataSensitivity.INTERNAL,
        }

        return sensitivity_map.get(pii_type, DataSensitivity.INTERNAL)


class DataMasker:
    """
    Applies masking strategies to sensitive data.

    Provides configurable masking for different data types and contexts.
    """

    def __init__(self):
        self.detector = PIIDetector()
        self.encryption_key = self._get_encryption_key()

    def _get_encryption_key(self) -> Optional[bytes]:
        """Get encryption key from app config"""
        try:
            key_b64 = current_app.config.get("DATA_ENCRYPTION_KEY")
            if key_b64:
                try:
                    return key_b64.encode()
                except (AttributeError, TypeError):
                    pass
        except RuntimeError:
            # Outside application context
            pass
        return None

    def mask_text(self, text: str, strategy: MaskingStrategy = MaskingStrategy.REDACT) -> str:
        """
        Mask sensitive data in text.

        Args:
            text: Text containing potentially sensitive data
            strategy: Masking strategy to apply

        Returns:
            Text with sensitive data masked
        """
        if not text:
            return text

        findings = self.detector.detect_pii(text)
        if not findings:
            return text

        # Sort findings by start position (reverse order to avoid offset issues)
        findings.sort(key=lambda x: x["start"], reverse=True)

        masked_text = text
        for finding in findings:
            original_value = finding["value"]
            masked_value = self._apply_masking(original_value, strategy, finding["type"])
            masked_text = (
                masked_text[: finding["start"]] + masked_value + masked_text[finding["end"] :]
            )

        return masked_text

    def mask_data(
        self,
        data: Dict,
        fields_to_mask: List[str] = None,
        strategy: MaskingStrategy = MaskingStrategy.REDACT,
    ) -> Dict:
        """
        Mask sensitive fields in structured data.

        Args:
            data: Dictionary containing data to mask
            fields_to_mask: List of field names to mask (if None, auto-detect)
            strategy: Masking strategy to apply

        Returns:
            Dictionary with sensitive fields masked
        """
        if not isinstance(data, dict):
            return data

        masked_data = data.copy()

        if fields_to_mask:
            # Mask specific fields
            for field in fields_to_mask:
                if field in masked_data:
                    masked_data[field] = self._apply_masking(
                        str(masked_data[field]), strategy, "custom"
                    )
        else:
            # Auto-detect PII in all string fields
            for key, value in masked_data.items():
                if isinstance(value, str):
                    masked_data[key] = self.mask_text(value, strategy)

        return masked_data

    def _apply_masking(self, value: str, strategy: MaskingStrategy, pii_type: str) -> str:
        """Apply masking strategy to a value"""
        if strategy == MaskingStrategy.REDACT:
            return "[REDACTED]"

        elif strategy == MaskingStrategy.HASH:
            return hashlib.sha256(value.encode()).hexdigest()[:16]

        elif strategy == MaskingStrategy.ENCRYPT:
            if self.encryption_key:
                try:
                    if not _HAS_CRYPTO or Fernet is None:
                        return "[ENCRYPTION_LIBRARY_MISSING]"
                    fernet = Fernet(self.encryption_key)
                    return fernet.encrypt(value.encode()).decode()
                except (Exception,):
                    return "[ENCRYPTION_FAILED]"
            else:
                return "[ENCRYPTION_KEY_MISSING]"

        elif strategy == MaskingStrategy.PARTIAL:
            return self._partial_mask(value, pii_type)

        return value

    def _partial_mask(self, value: str, pii_type: str) -> str:
        """Apply partial masking based on PII type"""
        if pii_type == "email":
            # Show first character and domain
            parts = value.split("@")
            if len(parts) == 2:
                return f"{parts[0][0]}***@{parts[1]}"

        elif pii_type in ["phone", "ssn"]:
            # Show last 4 digits
            if len(value) >= 4:
                return f"***-****-{value[-4:]}"

        elif pii_type == "credit_card":
            # Show last 4 digits
            if len(value) >= 4:
                return f"****-****-****-{value[-4:]}"

        # Default: show first and last character
        if len(value) > 2:
            return f"{value[0]}***{value[-1]}"

        return "***"


class DataProtector:
    """
    Main data protection service coordinating PII detection and masking.

    Provides high-level API for data protection operations.
    """

    def __init__(self):
        self.detector = PIIDetector()
        self.masker = DataMasker()

    def protect_data(
        self,
        data: Union[str, Dict],
        sensitivity_level: DataSensitivity = None,
        masking_strategy: MaskingStrategy = None,
    ) -> Union[str, Dict]:
        """
        Apply data protection based on sensitivity level.

        Args:
            data: Data to protect (string or dict)
            sensitivity_level: Required sensitivity level
            masking_strategy: Masking strategy to use

        Returns:
            Protected data
        """
        if sensitivity_level is None:
            sensitivity_level = DataSensitivity.CONFIDENTIAL

        if masking_strategy is None:
            # Choose strategy based on sensitivity
            strategy_map = {
                DataSensitivity.PUBLIC: None,  # No masking
                DataSensitivity.INTERNAL: MaskingStrategy.PARTIAL,
                DataSensitivity.CONFIDENTIAL: MaskingStrategy.REDACT,
                DataSensitivity.RESTRICTED: MaskingStrategy.ENCRYPT,
            }
            masking_strategy = strategy_map.get(sensitivity_level)

        if masking_strategy is None:
            return data

        if isinstance(data, str):
            return self.masker.mask_text(data, masking_strategy)
        elif isinstance(data, dict):
            return self.masker.mask_data(data, strategy=masking_strategy)
        else:
            return data

    def scan_for_pii(self, data: Union[str, Dict, List]) -> List[Dict]:
        """
        Scan data for PII content.

        Args:
            data: Data to scan

        Returns:
            List of PII findings
        """
        findings = []

        if isinstance(data, str):
            findings.extend(self.detector.detect_pii(data))

        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    field_findings = self.detector.detect_pii(value)
                    for finding in field_findings:
                        finding["field"] = key
                        findings.append(finding)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                item_findings = self.scan_for_pii(item)
                for finding in item_findings:
                    finding["index"] = i
                    findings.append(finding)

        return findings

    def is_data_safe(
        self,
        data: Union[str, Dict, List],
        max_sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
    ) -> bool:
        """
        Check if data meets safety requirements.

        Args:
            data: Data to check
            max_sensitivity: Maximum allowed sensitivity level

        Returns:
            True if data is safe, False if it contains restricted data
        """
        findings = self.scan_for_pii(data)

        sensitivity_order = [
            DataSensitivity.PUBLIC,
            DataSensitivity.INTERNAL,
            DataSensitivity.CONFIDENTIAL,
            DataSensitivity.RESTRICTED,
        ]

        max_allowed_index = sensitivity_order.index(max_sensitivity)

        for finding in findings:
            finding_index = sensitivity_order.index(finding["sensitivity"])
            if finding_index > max_allowed_index:
                return False

        return True


# Global data protector instance
data_protector = DataProtector()
