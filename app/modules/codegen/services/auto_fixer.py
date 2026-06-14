"""LLM-powered diagnosis, fix generation, and verification loop.

Confidence thresholds are TUNABLE, not final. Calibrate after first 50
real fix attempts by measuring auto-fix success rate vs false positive rate.
"""
import json
import logging

logger = logging.getLogger(__name__)

# --- TUNABLE THRESHOLDS (module-level defaults) ---
# Calibrate after real usage data (target: 50+ fix attempts).
# AUTO_FIX_THRESHOLD: confidence at which fix is applied without BA confirmation
# ATTEMPT_FIX_THRESHOLD: confidence at which fix is suggested for BA review
AUTO_FIX_THRESHOLD = 0.80
ATTEMPT_FIX_THRESHOLD = 0.50
MAX_RETRY_ATTEMPTS = 3


class AutoFixer:
    """Diagnose test failures, generate code fixes, and verify in a loop."""

    def __init__(self, auto_fix_threshold: float | None = None, attempt_fix_threshold: float | None = None):
        """Initialize with optional custom thresholds.

        Args:
            auto_fix_threshold: Override AUTO_FIX_THRESHOLD for this instance.
            attempt_fix_threshold: Override ATTEMPT_FIX_THRESHOLD for this instance.
        """
        self._auto_fix_threshold = auto_fix_threshold if auto_fix_threshold is not None else AUTO_FIX_THRESHOLD
        self._attempt_fix_threshold = attempt_fix_threshold if attempt_fix_threshold is not None else ATTEMPT_FIX_THRESHOLD

    def diagnose(self, failure_description: str, solution_id: int) -> dict:
        """Analyze a test failure and identify root cause.

        Returns dict with: root_cause, confidence (0.0-1.0), fix_suggestion.
        On error: confidence=0.0, error=<message>.
        """
        prompt = (
            f"A business analyst reported this issue with their deployed "
            f"application (solution {solution_id}):\n\n"
            f"Failure: {failure_description}\n\n"
            f"Analyze this and respond with JSON:\n"
            f'{{"root_cause": "<what is wrong>", '
            f'"confidence": <0.0-1.0>, '
            f'"fix_suggestion": "<how to fix>"}}'
        )

        response, error = self._call_llm(prompt)
        if error:
            return {"root_cause": "Diagnosis failed", "confidence": 0.0, "error": error}
        try:
            cleaned = response.strip().strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"root_cause": response, "confidence": 0.5, "raw": True}

    def should_auto_fix(self, confidence: float) -> bool:
        """Decide whether to apply fix automatically (high confidence)."""
        return confidence >= self._auto_fix_threshold

    def should_attempt_fix(self, confidence: float) -> bool:
        """Decide whether to suggest fix for BA review (medium confidence)."""
        return confidence >= self._attempt_fix_threshold

    def generate_fix(self, diagnosis: dict, generated_code: dict) -> dict:
        """Generate a code fix based on diagnosis.

        Returns dict with: file, old_code, new_code.
        On error: error=<message>.
        """
        prompt = (
            f"Root cause: {diagnosis.get('root_cause', '')}\n"
            f"Fix suggestion: {diagnosis.get('fix_suggestion', '')}\n\n"
            f"Generate a minimal code fix. Respond with JSON:\n"
            f'{{"file": "<filepath>", "old_code": "<exact code to replace>", '
            f'"new_code": "<replacement code>"}}'
        )

        response, error = self._call_llm(prompt)
        if error:
            return {"error": error}
        try:
            cleaned = response.strip().strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"error": "Failed to parse fix", "raw": response}

    def verify(self, fix: dict, scenario_id: int) -> dict:
        """Verify that a fix resolves the original test failure.

        In production, this would re-run the specific scenario against the
        patched code. For now, uses LLM to evaluate whether the fix addresses
        the root cause.

        Returns dict with: success (bool), output (str).
        """
        prompt = (
            f"A code fix was applied to resolve a test failure (scenario {scenario_id}).\n\n"
            f"Fix applied:\n"
            f"  File: {fix.get('file', 'unknown')}\n"
            f"  Old code: {fix.get('old_code', '')}\n"
            f"  New code: {fix.get('new_code', '')}\n\n"
            f"Evaluate whether this fix likely resolves the issue. Respond with JSON:\n"
            f'{{"success": true/false, "output": "<reasoning>"}}'
        )

        response, error = self._call_llm(prompt)
        if error:
            return {"success": False, "error": error}
        try:
            cleaned = response.strip().strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"success": False, "error": "Failed to parse verification result", "raw": response}

    def fix_loop(
        self,
        diagnosis: dict,
        solution_id: int,
        scenario_id: int,
        generated_code: dict,
    ) -> dict:
        """Execute the diagnose -> fix -> verify loop.

        Confidence-based behavior:
        - >= auto_fix_threshold: auto-fix, auto-deploy, verify
        - >= attempt_fix_threshold: try fix, escalate if fails after MAX_RETRY_ATTEMPTS
        - < attempt_fix_threshold: escalate immediately

        Returns dict with: success, attempts, fix (if successful),
        escalate (bool), reason (if escalated).
        """
        confidence = diagnosis.get("confidence", 0.0)

        # Low confidence: escalate immediately
        if not self.should_attempt_fix(confidence):
            return {
                "success": False,
                "attempts": 0,
                "escalate": True,
                "reason": f"Confidence too low ({confidence:.0%}) for auto-fix. Threshold: {self._attempt_fix_threshold:.0%}.",
                "diagnosis": diagnosis,
            }

        # Medium or high confidence: attempt fix loop
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            fix = self.generate_fix(diagnosis, generated_code)
            if "error" in fix:
                logger.warning("Fix generation failed on attempt %d: %s", attempt, fix["error"])
                continue

            verification = self.verify(fix, scenario_id)
            if verification.get("success"):
                return {
                    "success": True,
                    "attempts": attempt,
                    "fix": fix,
                    "escalate": False,
                    "auto_applied": self.should_auto_fix(confidence),
                }

            logger.info(
                "Fix attempt %d/%d failed verification for scenario %d",
                attempt, MAX_RETRY_ATTEMPTS, scenario_id,
            )

        # All attempts exhausted
        return {
            "success": False,
            "attempts": MAX_RETRY_ATTEMPTS,
            "escalate": True,
            "reason": f"Fix failed after {MAX_RETRY_ATTEMPTS} attempts. Manual intervention required.",
            "diagnosis": diagnosis,
        }

    def _call_llm(self, prompt: str) -> tuple:
        """Call LLM service. Returns (response_text, error_or_none)."""
        try:
            from app.modules.ai_chat.services.llm_service import LLMService
            svc = LLMService()
            response = svc.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
            if response and "content" in response:
                return response["content"], None
            return None, "Empty response"
        except Exception as e:
            logger.warning("AutoFixer LLM call failed: %s", e)
            return None, str(e)
