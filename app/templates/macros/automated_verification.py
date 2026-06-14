# AUTOMATED VERIFICATION SCRIPT FOR LLM FIXES
#
# This script automatically runs the complete verification process
# to ensure LLMs cannot claim success without proper testing.

import json
import os
import sys
from datetime import datetime

# Add the macros directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "macros"))

try:
    from flask_test_verifier import FlaskTestVerifier
    from llm_compliance_enforcer import LLMComplianceEnforcer
    from verification_enforcer import VerificationEnforcer
except ImportError as e:
    print(f"[ERROR] Cannot import verification modules: {e}")
    sys.exit(1)


class AutomatedVerificationSystem:
    """Complete automated verification system for LLM fixes"""

    def __init__(self):
        self.enforcer = VerificationEnforcer()
        self.tester = FlaskTestVerifier()
        self.compliance = LLMComplianceEnforcer()

    def verify_fix(self, llm_id, error_message, traceback=None, fix_details=None):
        """Complete automated verification process"""

        print(f"[AUTOMATED VERIFICATION] Starting verification for LLM: {llm_id}")
        print(f"[ERROR] {error_message}")

        verification_report = {
            "llm_id": llm_id,
            "timestamp": datetime.now().isoformat(),
            "error_message": error_message,
            "traceback": traceback,
            "fix_details": fix_details,
            "verification_status": "IN_PROGRESS",
            "steps_completed": [],
            "final_result": None,
        }

        try:
            # STEP 1: Mandatory Error Analysis
            print("\n[STEP 1] ERROR ANALYSIS")
            error_analysis = self.enforcer.mandatory_error_analysis(error_message, traceback)
            verification_report["steps_completed"].append("error_analysis")
            verification_report["error_analysis"] = error_analysis

            # STEP 2: Solution Design
            print("\n[STEP 2] SOLUTION DESIGN")
            solution_design = self.enforcer.mandatory_solution_design(error_analysis)
            verification_report["steps_completed"].append("solution_design")
            verification_report["solution_design"] = solution_design

            # STEP 3: Implementation
            print("\n[STEP 3] IMPLEMENTATION")
            if fix_details:
                implementation_results = self.enforcer.mandatory_implementation(solution_design)
                verification_report["steps_completed"].append("implementation")
                verification_report["implementation_results"] = implementation_results
            else:
                print("[WARNING] No implementation details provided")
                verification_report["implementation_results"] = None

            # STEP 4: Testing
            print("\n[STEP 4] COMPREHENSIVE TESTING")
            test_results = self.tester.run_comprehensive_tests(
                error_analysis["type"], fix_details or {}
            )
            verification_report["steps_completed"].append("testing")
            verification_report["test_results"] = test_results

            # STEP 5: Compliance Check
            print("\n[STEP 5] COMPLIANCE CHECK")
            compliance_check = self.compliance.check_compliance_before_claim(
                llm_id,
                fix_details or {},
                {
                    "error_analysis": error_analysis,
                    "solution_design": solution_design,
                    "implementation_steps": verification_report.get("implementation_results"),
                    "test_results": test_results,
                    "change_verification": fix_details,
                },
            )
            verification_report["steps_completed"].append("compliance_check")
            verification_report["compliance_check"] = compliance_check

            # STEP 6: Final Success Confirmation
            print("\n[STEP 6] FINAL VERIFICATION")
            if compliance_check["compliance_status"] == "COMPLIANT":
                success_confirmation = self.enforcer.mandatory_success_confirmation(
                    verification_report
                )
                verification_report["steps_completed"].append("success_confirmation")
                verification_report["final_result"] = "SUCCESS"
                verification_report["verification_status"] = "COMPLETED"

                print("\n[SUCCESS] VERIFICATION COMPLETED SUCCESSFULLY")
                print(f"[EVIDENCE] {len(verification_report['steps_completed'])} steps completed")
                print(f"[EVIDENCE] All tests passed: {test_results['summary']}")

            else:
                verification_report["final_result"] = "FAILED_COMPLIANCE"
                verification_report["verification_status"] = "FAILED"

                print(
                    f"\n[FAILED] COMPLIANCE VIOLATIONS: {', '.join(compliance_check['violations'])}"
                )
                print("[FAILED] LLM VIOLATED MANDATORY VERIFICATION PROTOCOL")

        except Exception as e:
            verification_report["final_result"] = "ERROR"
            verification_report["verification_status"] = "ERROR"
            verification_report["error"] = str(e)

            print(f"\n[ERROR] Verification failed: {e}")

        # Save verification report
        self._save_verification_report(verification_report)

        return verification_report

    def _save_verification_report(self, report):
        """Save verification report to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"verification_report_{report['llm_id']}_{timestamp}.json"

        try:
            with open(filename, "w") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"[REPORT] Verification report saved: {filename}")
        except Exception as e:
            print(f"[ERROR] Could not save report: {e}")


# MANDATORY USAGE PROTOCOL
#
# ALL LLMs MUST USE THIS SYSTEM FOR EVERY FIX CLAIM:
#
# 1. Call verify_fix() with complete error details
# 2. Provide fix_details with all changes made
# 3. Wait for complete verification results
# 4. Only claim success if verification_report["final_result"] == "SUCCESS"
# 5. Include verification evidence in success claim
#
# NO EXCEPTIONS - THIS IS MANDATORY
#
# EXAMPLE USAGE:
#
# verifier = AutomatedVerificationSystem()
# result = verifier.verify_fix(
#     llm_id="cascade_ai",
#     error_message="TemplateNotFound: macros/profile_components.html",
#     traceback="...",
#     fix_details={
#         "created_file": "macros/profile_components.html",
#         "changes": ["Created missing macro file"],
#         "verification": "File exists and can be imported"
#     }
# )
#
# if result["final_result"] == "SUCCESS":
#     print("FIX VERIFIED AND CONFIRMED")
# else:
#     print("FIX FAILED VERIFICATION - CANNOT CLAIM SUCCESS")

if __name__ == "__main__":
    print("[AUTOMATED VERIFICATION SYSTEM] Ready for use")
    print("[USAGE] Import and use AutomatedVerificationSystem.verify_fix()")
