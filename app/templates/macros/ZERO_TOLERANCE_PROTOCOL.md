# ZERO TOLERANCE ENFORCEMENT PROTOCOL
#
# This document establishes the mandatory verification and testing protocol
# that ALL LLM agents must follow for every fix. NO EXCEPTIONS.

## OVERVIEW

This system enforces proper error analysis, implementation, and testing to prevent LLMs from claiming success without verification.

## MANDATORY VERIFICATION STEPS

### STEP 1: ERROR ANALYSIS (No Assumptions Allowed)
- Extract exact error type and location
- Identify actual root cause (not symptoms)
- Provide verifiable evidence of the error
- NO assumptions or speculation allowed

### STEP 2: SOLUTION DESIGN
- Create specific, actionable implementation steps
- Identify potential side effects
- Define verification criteria for success
- Plan must be detailed and specific

### STEP 3: IMPLEMENTATION WITH VERIFICATION
- Execute each implementation step
- Verify each step immediately after execution
- Provide evidence of changes (file content, grep results)
- No step is complete without verification

### STEP 4: COMPREHENSIVE TESTING
- Test error reproduction
- Test fix verification
- Test for regressions
- Test integration
- ALL tests must pass

### STEP 5: COMPLIANCE CHECK
- Verify all required steps completed
- Check no assumptions were made
- Confirm testing evidence exists
- Validate change verification

### STEP 6: SUCCESS CONFIRMATION
- Only after ALL previous steps complete
- Must provide complete evidence package
- Must include test results
- Must verify no regressions

## AUTOMATED ENFORCEMENT

The system includes automated verification that:

1. **Prevents False Claims**: Cannot claim success without passing verification
2. **Enforces Testing**: Requires actual test results, not assumptions
3. **Tracks Violations**: Logs all compliance violations
4. **Bans Repeat Offenders**: Automatic ban after 3 violations
5. **Evidence Required**: Must provide verifiable evidence for every step

## CRITICAL VIOLATIONS (Immediate Ban)

- Making assumptions during diagnosis
- Claiming success without test results
- Missing change verification
- Not following mandatory steps
- Providing false or incomplete evidence

## USAGE REQUIREMENTS

### For Every Fix Claim, LLM Must:

1. **Run Automated Verification**:
   ```python
   from automated_verification import AutomatedVerificationSystem
   verifier = AutomatedVerificationSystem()
   result = verifier.verify_fix(llm_id, error_message, traceback, fix_details)
   ```

2. **Provide Complete Evidence**:
   - Error analysis results
   - Implementation evidence
   - Test results showing success
   - Change verification proof

3. **Wait for Verification**:
   - Only claim success if result["final_result"] == "SUCCESS"
   - Include verification evidence in claim
   - Report failures honestly

4. **No Shortcuts**:
   - Cannot skip verification steps
   - Cannot claim success without testing
   - Cannot make assumptions about fixes

## ENFORCEMENT CONSEQUENCES

### First Violation:
- Immediate correction required
- Violation logged
- Warning issued

### Second Violation:
- Session termination
- Detailed violation report
- Mandatory retraining

### Third Violation:
- Permanent ban from fix tasks
- Violation record permanent
- No further access allowed

## IMPLEMENTATION INTEGRATION

The verification system integrates with:

1. **File Operations**: Verifies all file changes
2. **Route Testing**: Tests endpoint accessibility
3. **Template Rendering**: Verifies template functionality
4. **Form Submission**: Tests form processing
5. **Error Resolution**: Confirms original error is fixed

## COMPLIANCE MONITORING

The system monitors:

- Verification step completion
- Evidence quality and completeness
- Test result validity
- Compliance with protocols
- Violation patterns

## SUCCESS CRITERIA

A fix is only successful when:

1. ✅ All verification steps completed
2. ✅ All tests pass
3. ✅ No regressions detected
4. ✅ Changes verified in files
5. ✅ Original error resolved
6. ✅ Compliance check passed

## FAILURE HANDLING

If verification fails:

1. ❌ Immediate stop of claim process
2. ❌ Detailed failure report generated
3. ❌ Violation logged if applicable
4. ❌ Honest failure reporting required
5. ❌ No success claims allowed

## ZERO TOLERANCE POLICY

This system operates on a zero-tolerance basis:

- **NO assumptions allowed**
- **NO success without testing**
- **NO shortcuts permitted**
- **NO false claims tolerated**
- **NO exceptions to protocol**

## ACCOUNTABILITY

Every fix claim is:

- **Tracked**: Complete audit trail maintained
- **Verified**: Automated verification required
- **Logged**: All actions recorded
- **Evaluated**: Compliance assessed
- **Enforced**: Violations punished

---

**THIS PROTOCOL ENFORCES PROPER ENGINEERING PRACTICES**
**NO MORE FALSE CLAIMS OR UNTESTED FIXES**
**VERIFICATION IS MANDATORY, NOT OPTIONAL**
