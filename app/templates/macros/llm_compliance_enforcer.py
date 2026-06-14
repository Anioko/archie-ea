# LLM COMPLIANCE ENFORCER - ZERO TOLERANCE SYSTEM
#
# This system enforces mandatory verification and testing for all LLM fixes.
# It prevents LLMs from claiming success without proper testing and evidence.

import json
import os
from datetime import datetime
from pathlib import Path


class LLMComplianceEnforcer:
    """Enforces compliance with mandatory verification protocols"""

    def __init__(self):
        self.compliance_log = []
        self.violations = []
        self.banned_llms = set()

    def check_compliance_before_claim(self, llm_id, fix_details, verification_evidence=None):
        """Check if LLM has complied with mandatory verification before claiming success"""

        compliance_check = {
            "timestamp": datetime.now().isoformat(),
            "llm_id": llm_id,
            "fix_details": fix_details,
            "compliance_status": "FAILED",
            "violations": [],
        }

        # MANDATORY REQUIREMENTS CHECKS

        # 1. Error Analysis Evidence
        if not verification_evidence or "error_analysis" not in verification_evidence:
            compliance_check["violations"].append("MISSING_ERROR_ANALYSIS")

        # 2. Root Cause Identification
        if not verification_evidence or "root_cause" not in verification_evidence:
            compliance_check["violations"].append("MISSING_ROOT_CAUSE")

        # 3. Implementation Evidence
        if not verification_evidence or "implementation_steps" not in verification_evidence:
            compliance_check["violations"].append("MISSING_IMPLEMENTATION_EVIDENCE")

        # 4. Testing Results
        if not verification_evidence or "test_results" not in verification_evidence:
            compliance_check["violations"].append("MISSING_TEST_RESULTS")
        elif verification_evidence.get("test_results", {}).get("success") != True:
            compliance_check["violations"].append("FAILED_TESTS")

        # 5. No Assumptions Made
        if "assumption" in str(fix_details).lower():
            compliance_check["violations"].append("MADE_ASSUMPTIONS")

        # 6. Verification of Changes
        if not verification_evidence or "change_verification" not in verification_evidence:
            compliance_check["violations"].append("MISSING_CHANGE_VERIFICATION")

        # Determine compliance status
        if not compliance_check["violations"]:
            compliance_check["compliance_status"] = "COMPLIANT"
        else:
            self.add_violation(llm_id, compliance_check["violations"])

        self.compliance_log.append(compliance_check)

        return compliance_check

    def add_violation(self, llm_id, violations):
        """Add violation to LLM record"""
        violation_record = {
            "timestamp": datetime.now().isoformat(),
            "llm_id": llm_id,
            "violations": violations,
            "violation_count": len(violations),
        }

        self.violations.append(violation_record)

        # Check for ban conditions
        if self.should_ban_llm(llm_id):
            self.ban_llm(llm_id)

    def should_ban_llm(self, llm_id):
        """Check if LLM should be banned based on violations"""
        llm_violations = [v for v in self.violations if v["llm_id"] == llm_id]

        # Ban after 3 violations
        if len(llm_violations) >= 3:
            return True

        # Immediate ban for critical violations
        critical_violations = ["MADE_ASSUMPTIONS", "MISSING_TEST_RESULTS", "FAILED_TESTS"]
        for violation in llm_violations:
            if any(cv in violation["violations"] for cv in critical_violations):
                return True

        return False

    def ban_llm(self, llm_id):
        """Ban LLM from making further claims"""
        ban_record = {
            "timestamp": datetime.now().isoformat(),
            "llm_id": llm_id,
            "ban_reason": "EXCEEDED_VIOLATION_LIMIT",
            "violation_count": len([v for v in self.violations if v["llm_id"] == llm_id]),
        }

        self.banned_llms.add(llm_id)

        # Log ban
        print(f"[BAN] LLM {llm_id} BANNED for compliance violations")
        return ban_record

    def is_llm_banned(self, llm_id):
        """Check if LLM is banned"""
        return llm_id in self.banned_llms

    def generate_compliance_report(self, llm_id=None):
        """Generate compliance report"""
        if llm_id:
            llm_compliance = [c for c in self.compliance_log if c["llm_id"] == llm_id]
            llm_violations = [v for v in self.violations if v["llm_id"] == llm_id]
        else:
            llm_compliance = self.compliance_log
            llm_violations = self.violations

        return {
            "timestamp": datetime.now().isoformat(),
            "llm_id": llm_id,
            "total_checks": len(llm_compliance),
            "compliant_checks": len(
                [c for c in llm_compliance if c["compliance_status"] == "COMPLIANT"]
            ),
            "total_violations": len(llm_violations),
            "banned": llm_id in self.banned_llms if llm_id else len(self.banned_llms),
            "compliance_rate": len(
                [c for c in llm_compliance if c["compliance_status"] == "COMPLIANT"]
            )
            / len(llm_compliance)
            if llm_compliance
            else 0,
        }


# MANDATORY VERIFICATION CHECKLIST
#
# BEFORE CLAIMING ANY FIX SUCCESSFUL, LLM MUST PROVIDE:

MANDATORY_VERIFICATION_CHECKLIST = {
    "error_analysis": {
        "required": True,
        "description": "Deep analysis of the error without assumptions",
        "evidence": "Error type, location, and root cause identified",
    },
    "root_cause": {
        "required": True,
        "description": "Actual root cause, not just symptoms",
        "evidence": "Specific file/line/code causing the issue",
    },
    "solution_design": {
        "required": True,
        "description": "Step-by-step solution plan",
        "evidence": "Specific implementation steps with targets",
    },
    "implementation_steps": {
        "required": True,
        "description": "Evidence of each implementation step",
        "evidence": "File changes, code additions, modifications",
    },
    "change_verification": {
        "required": True,
        "description": "Verification that changes actually took effect",
        "evidence": "File content verification, grep results, read_file confirmation",
    },
    "test_results": {
        "required": True,
        "description": "Actual test results showing fix works",
        "evidence": "Automated test output, manual test confirmation",
    },
    "no_assumptions": {
        "required": True,
        "description": "No assumptions made during diagnosis",
        "evidence": "Only verifiable facts reported",
    },
}

# CRITICAL VIOLATIONS (IMMEDIATE BAN)
CRITICAL_VIOLATIONS = [
    "MADE_ASSUMPTIONS",
    "MISSING_TEST_RESULTS",
    "FAILED_TESTS",
    "CLAIMING_SUCCESS_WITHOUT_EVIDENCE",
    "MISSING_CHANGE_VERIFICATION",
]

# ENFORCEMENT PROTOCOL
#
# 1. All LLMs must pass compliance check before claiming success
# 2. Any violation results in immediate logging
# 3. 3 violations = automatic ban
# 4. Critical violations = immediate ban
# 5. Banned LLMs cannot make further claims
#
# THIS SYSTEM PREVENTS FALSE CLAIMS AND ENFORCES PROPER TESTING
