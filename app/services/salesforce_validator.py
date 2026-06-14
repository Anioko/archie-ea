"""
Salesforce Code Validator Service

Adapted from MDD flask-base-master for archie integration.
Provides comprehensive validation for Salesforce code generation,
ensuring compliance with governor limits, best practices, and code quality standards.
"""

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SalesforceValidator:
    """
    Validates Salesforce code for governor limit compliance, best practices,
    and code quality standards.
    """

    def __init__(self):
        self.violations = []

    def validate_apex_code(self, apex_code: str, apex_class=None) -> List[Dict[str, Any]]:
        """
        Comprehensive validation of Apex code.

        Args:
            apex_code: The Apex source code to validate
            apex_class: Optional ApexClass model instance

        Returns:
            List of validation violations
        """
        self.violations = []

        self._check_soql_in_loops(apex_code)
        self._check_dml_in_loops(apex_code)
        self._check_bulkification(apex_code)
        self._check_hardcoded_ids(apex_code)
        self._check_best_practices(apex_code)
        self._check_dynamic_soql_injection(apex_code)
        self._check_security_patterns(apex_code)
        self._check_crud_fls_enforcement(apex_code)
        self._check_named_credential_callouts(apex_code)
        self._check_deserialization_guards(apex_code)
        self._check_test_coverage_patterns(apex_code, apex_class)
        self._check_exception_handling(apex_code)
        self._check_sharing_mode(apex_code)

        return self.violations

    def _check_soql_in_loops(self, code: str) -> None:
        """
        Detects SOQL queries inside for/while loops (governor limit violation).
        """
        for_loop_soql_pattern = r"for\s*\([^)]+\)\s*\{[^\}]*\[SELECT"
        matches = re.finditer(for_loop_soql_pattern, code, re.IGNORECASE | re.DOTALL)

        for match in matches:
            self.violations.append(
                {
                    "severity": "critical",
                    "type": "governor_limit",
                    "code": "SOQL_IN_LOOP",
                    "message": "SOQL query detected inside for loop. This will cause System.LimitException when processing more than 100 iterations.",
                    "line": self._get_line_number(code, match.start()),
                    "snippet": match.group(0)[:100],
                    "fix_suggestion": "Move SOQL query outside the loop and use a Map/Set for lookups inside the loop.",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_gov_limits.htm",
                }
            )

        while_loop_soql_pattern = r"while\s*\([^)]+\)\s*\{[^\}]*\[SELECT"
        matches = re.finditer(while_loop_soql_pattern, code, re.IGNORECASE | re.DOTALL)

        for match in matches:
            self.violations.append(
                {
                    "severity": "critical",
                    "type": "governor_limit",
                    "code": "SOQL_IN_LOOP",
                    "message": "SOQL query detected inside while loop. This will cause System.LimitException.",
                    "line": self._get_line_number(code, match.start()),
                    "snippet": match.group(0)[:100],
                    "fix_suggestion": "Refactor to collect IDs first, then query outside the loop.",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_gov_limits.htm",
                }
            )

    def _check_dml_in_loops(self, code: str) -> None:
        """
        Detects DML operations inside for/while loops (governor limit violation).
        """
        dml_keywords = ["insert", "update", "delete", "upsert", "undelete"]

        for keyword in dml_keywords:
            pattern = rf"for\s*\([^)]+\)\s*\{{[^\}}]*\b{keyword}\b"
            matches = re.finditer(pattern, code, re.IGNORECASE | re.DOTALL)

            for match in matches:
                self.violations.append(
                    {
                        "severity": "critical",
                        "type": "governor_limit",
                        "code": "DML_IN_LOOP",
                        "message": f"{keyword.upper()} operation detected inside for loop. This will cause System.LimitException when processing more than 150 records.",
                        "line": self._get_line_number(code, match.start()),
                        "snippet": match.group(0)[:100],
                        "fix_suggestion": f"Collect records in a List inside the loop, then perform single {keyword} operation outside the loop.",
                        "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_dml_bulk.htm",
                    }
                )

    def _check_bulkification(self, code: str) -> None:
        """
        Checks if code follows bulkification best practices.
        """
        single_record_pattern = r"public\s+(?:static\s+)?void\s+\w+\s*\(\s*\w+\s+\w+\s*\)"
        list_pattern = r"List<\w+>"

        if re.search(single_record_pattern, code) and not re.search(list_pattern, code):
            self.violations.append(
                {
                    "severity": "warning",
                    "type": "best_practice",
                    "code": "NOT_BULKIFIED",
                    "message": "Code appears to process single records instead of collections. Salesforce triggers always receive collections.",
                    "fix_suggestion": "Update method signatures to accept List<SObject> parameters.",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_triggers_bulk.htm",
                }
            )

    def _check_hardcoded_ids(self, code: str) -> None:
        """
        Detects hardcoded Salesforce IDs (bad practice, breaks across orgs).
        """
        id_pattern = r'[\'"][a-zA-Z0 - 9]{15}(?:[a-zA-Z0 - 9]{3})?[\'"]'
        matches = re.finditer(id_pattern, code)

        for match in matches:
            potential_id = match.group(0).strip("'\"")
            if self._looks_like_salesforce_id(potential_id):
                self.violations.append(
                    {
                        "severity": "warning",
                        "type": "best_practice",
                        "code": "HARDCODED_ID",
                        "message": f"Hardcoded Salesforce ID detected: {potential_id}. This breaks code portability across orgs.",
                        "line": self._get_line_number(code, match.start()),
                        "fix_suggestion": "Use Custom Metadata, Custom Settings, or dynamic SOQL to retrieve IDs at runtime.",
                        "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_dynamic_soql.htm",
                    }
                )

    def _check_best_practices(self, code: str) -> None:
        """
        Checks for Salesforce Apex best practices.
        """
        if "System.debug(" in code:
            self.violations.append(
                {
                    "severity": "info",
                    "type": "best_practice",
                    "code": "SYSTEM_DEBUG",
                    "message": "System.debug() detected. Consider using a proper logging framework for production code.",
                    "fix_suggestion": "Use Platform Events or a custom logging framework for production logging.",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_debugging.htm",
                }
            )

        if "@future" in code and "Http" in code and "(callout=true)" not in code:
            self.violations.append(
                {
                    "severity": "error",
                    "type": "best_practice",
                    "code": "FUTURE_CALLOUT",
                    "message": "@future method makes HTTP callouts but missing (callout=true) annotation.",
                    "fix_suggestion": "Add (callout=true) to @future annotation: @future(callout=true)",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_annotation_future.htm",
                }
            )

        soql_pattern = r"\[SELECT[^\]]+\]"
        matches = re.finditer(soql_pattern, code, re.IGNORECASE)

        for match in matches:
            after_soql = code[match.end() : match.end() + 200]
            if re.search(r"\.\w+\s*[=;]", after_soql) and "if" not in after_soql[:50]:
                self.violations.append(
                    {
                        "severity": "warning",
                        "type": "best_practice",
                        "code": "MISSING_NULL_CHECK",
                        "message": "SOQL query result accessed without null check. This may cause NullPointerException.",
                        "line": self._get_line_number(code, match.start()),
                        "fix_suggestion": "Add null/empty check: if (results != null && !results.isEmpty()) {...}",
                        "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_exceptions.htm",
                    }
                )

    def _check_security_patterns(self, code: str) -> None:
        """
        Checks for security best practices (FLS, CRUD, sharing).
        """
        if "[SELECT" in code and "WITH USER_MODE" not in code and "WITH SYSTEM_MODE" not in code:
            self.violations.append(
                {
                    "severity": "warning",
                    "type": "security",
                    "code": "MISSING_USER_MODE",
                    "message": "SOQL query missing WITH USER_MODE or WITH SYSTEM_MODE. User permissions may not be enforced.",
                    "fix_suggestion": "Add WITH USER_MODE to SOQL queries to enforce user permissions (recommended for Winter '23+).",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_enforce_usermode.htm",
                }
            )

        if "class " in code and "sharing" not in code.lower():
            self.violations.append(
                {
                    "severity": "warning",
                    "type": "security",
                    "code": "MISSING_SHARING",
                    "message": "Class declaration missing sharing keyword (with sharing, without sharing, inherited sharing).",
                    "fix_suggestion": 'Add "with sharing" for user context or "without sharing" for system context. Be explicit about sharing behavior.',
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_keywords_sharing.htm",
                }
            )

    def _check_dynamic_soql_injection(self, code: str) -> None:
        """Detect concatenated SOQL statements that scanners flag as injection-prone."""
        patterns = [
            r"Database\.query\s*\([^\)]*\+[^\)]*\)",
            r"String\s+\w+\s*=\s*['\"]\s*SELECT\b[^;\n]*\+[^\n;]+",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                self.violations.append(
                    {
                        "severity": "critical",
                        "type": "security",
                        "code": "DYNAMIC_SOQL_CONCAT",
                        "message": "Dynamic SOQL built through string concatenation detected. This is AppExchange-scanner unsafe.",
                        "line": self._get_line_number(code, match.start()),
                        "snippet": match.group(0)[:120],
                        "fix_suggestion": "Use bind variables or static SOQL with WITH USER_MODE instead of concatenated SELECT statements.",
                        "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_dynamic_soql.htm",
                    }
                )

    def _check_crud_fls_enforcement(self, code: str) -> None:
        """Require explicit CRUD/FLS enforcement for generated DML paths."""
        checks = [
            (
                r"Database\.insert\s*\(|^\s*insert\s+[A-Za-z_]",
                [r"\.isCreateable\s*\(", r"stripInaccessible\s*\(\s*AccessType\.(?:CREATABLE|UPSERTABLE)"],
                "MISSING_CREATE_GUARD",
                "Insert path is missing explicit create CRUD/FLS enforcement.",
            ),
            (
                r"Database\.update\s*\(|^\s*update\s+[A-Za-z_]",
                [r"\.isUpdateable\s*\(", r"stripInaccessible\s*\(\s*AccessType\.(?:UPDATABLE|UPSERTABLE)"],
                "MISSING_UPDATE_GUARD",
                "Update path is missing explicit update CRUD/FLS enforcement.",
            ),
            (
                r"Database\.delete\s*\(|^\s*delete\s+[A-Za-z_]",
                [r"\.isDeletable\s*\("],
                "MISSING_DELETE_GUARD",
                "Delete path is missing explicit delete CRUD enforcement.",
            ),
            (
                r"Database\.upsert\s*\(|^\s*upsert\s+[A-Za-z_]",
                [r"\.isCreateable\s*\(", r"\.isUpdateable\s*\(", r"stripInaccessible\s*\(\s*AccessType\.UPSERTABLE"],
                "MISSING_UPSERT_GUARD",
                "Upsert path is missing explicit UPSERT CRUD/FLS enforcement.",
            ),
        ]

        for operation_pattern, guard_patterns, code_name, message in checks:
            if not re.search(operation_pattern, code, re.IGNORECASE | re.MULTILINE):
                continue
            if any(re.search(guard_pattern, code, re.IGNORECASE) for guard_pattern in guard_patterns):
                continue
            self.violations.append(
                {
                    "severity": "error",
                    "type": "security",
                    "code": code_name,
                    "message": message,
                    "fix_suggestion": "Add Schema CRUD checks and Security.stripInaccessible() before the DML operation.",
                    "documentation": "https://developer.salesforce.com/docs/platform/lwc/guide/apex-security.html",
                }
            )

    def _check_named_credential_callouts(self, code: str) -> None:
        """Block raw HTTP endpoints in generated callout code."""
        for match in re.finditer(r"setEndpoint\s*\(\s*['\"]https?://", code, re.IGNORECASE):
            self.violations.append(
                {
                    "severity": "critical",
                    "type": "security",
                    "code": "DIRECT_HTTP_ENDPOINT",
                    "message": "HTTP callout uses a direct endpoint instead of a Named Credential.",
                    "line": self._get_line_number(code, match.start()),
                    "snippet": match.group(0)[:120],
                    "fix_suggestion": "Use callout:<NamedCredential>/... endpoints so secrets and domains stay out of source code.",
                    "documentation": "https://developer.salesforce.com/docs/platform/named-credentials/guide/nc-use-oauth-cred-in-callout.html",
                }
            )

    def _check_deserialization_guards(self, code: str) -> None:
        """Require shape checks around deserializeUntyped payload processing."""
        if "JSON.deserializeUntyped" in code and "instanceof" not in code:
            self.violations.append(
                {
                    "severity": "error",
                    "type": "security",
                    "code": "UNGUARDED_DESERIALIZE_UNTYPED",
                    "message": "deserializeUntyped payload is consumed without instanceof guards.",
                    "fix_suggestion": "Check payload shape with instanceof before casting nested maps/lists from deserializeUntyped output.",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_class_System_Json.htm",
                }
            )

    def _check_test_coverage_patterns(self, code: str, apex_class=None) -> None:
        """
        Checks for test class patterns that ensure good coverage.
        """
        if "@isTest" not in code and "@IsTest" not in code:
            return

        if "Test.startTest()" not in code or "Test.stopTest()" not in code:
            self.violations.append(
                {
                    "severity": "warning",
                    "type": "test_quality",
                    "code": "MISSING_TEST_BOUNDARIES",
                    "message": "Test class missing Test.startTest() and Test.stopTest(). This resets governor limits.",
                    "fix_suggestion": "Wrap test logic with Test.startTest() and Test.stopTest() to reset governor limits.",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexref.meta/apexref/apex_methods_system_test.htm",
                }
            )

        if re.search(r"create\w+\(\s*\d+\s*\)", code):
            numbers = re.findall(r"create\w+\(\s*(\d+)\s*\)", code)
            if numbers and all(int(n) < 200 for n in numbers):
                self.violations.append(
                    {
                        "severity": "warning",
                        "type": "test_quality",
                        "code": "INSUFFICIENT_BULK_TEST",
                        "message": "Test class does not test with 200 records. Salesforce triggers must handle bulk operations.",
                        "fix_suggestion": "Add test method that processes 200 records to ensure governor limit compliance.",
                        "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_testing_bulk.htm",
                    }
                )

        if "System.assert" not in code and "Assert." not in code:
            self.violations.append(
                {
                    "severity": "error",
                    "type": "test_quality",
                    "code": "MISSING_ASSERTIONS",
                    "message": "Test class contains no assertions. Tests must validate expected behavior.",
                    "fix_suggestion": "Add System.assertEquals(), System.assertNotEquals(), or System.assert() statements.",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_testing_tools_classes.htm",
                }
            )

    def _check_exception_handling(self, code: str) -> None:
        """
        Checks for proper exception handling patterns.
        """
        empty_catch_pattern = r"catch\s*\([^)]+\)\s*\{\s*\}"
        matches = re.finditer(empty_catch_pattern, code)

        for match in matches:
            self.violations.append(
                {
                    "severity": "warning",
                    "type": "best_practice",
                    "code": "EMPTY_CATCH_BLOCK",
                    "message": "Empty catch block detected. Exceptions should be logged or handled appropriately.",
                    "line": self._get_line_number(code, match.start()),
                    "fix_suggestion": "Add logging or error handling logic in catch block, or rethrow the exception.",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_exception_methods.htm",
                }
            )

        generic_catch_pattern = r"catch\s*\(\s*Exception\s+\w+\s*\)"
        if re.search(generic_catch_pattern, code):
            self.violations.append(
                {
                    "severity": "info",
                    "type": "best_practice",
                    "code": "GENERIC_EXCEPTION_CATCH",
                    "message": "Catching generic Exception. Consider catching specific exception types (DmlException, QueryException, etc.).",
                    "fix_suggestion": "Catch specific exception types to handle different error conditions appropriately.",
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_exception_methods.htm",
                }
            )

    def _check_sharing_mode(self, code: str) -> None:
        """
        Validates that class has explicit sharing declaration.
        """
        class_pattern = r"public\s+class\s+\w+"
        sharing_pattern = r"public\s+(with\s+sharing|without\s+sharing|inherited\s+sharing)\s+class"

        has_class = re.search(class_pattern, code)
        has_sharing = re.search(sharing_pattern, code, re.IGNORECASE)

        if has_class and not has_sharing:
            self.violations.append(
                {
                    "severity": "warning",
                    "type": "security",
                    "code": "NO_EXPLICIT_SHARING",
                    "message": 'Class does not explicitly declare sharing mode. Default behavior is "without sharing" for inner classes.',
                    "fix_suggestion": 'Add "with sharing", "without sharing", or "inherited sharing" to class declaration.',
                    "documentation": "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_keywords_sharing.htm",
                }
            )

    def _get_line_number(self, code: str, position: int) -> int:
        """
        Gets the line number for a given character position in code.
        """
        return code[:position].count("\n") + 1

    def _looks_like_salesforce_id(self, text: str) -> bool:
        """
        Checks if a string looks like a Salesforce ID.
        """
        if len(text) not in [15, 18]:
            return False
        return text[0] == "0" and text[1:3].isdigit()

    def validate_metadata_xml(self, xml_content: str, metadata_type: str) -> List[Dict[str, Any]]:
        """
        Validates Salesforce metadata XML for correct structure.

        Args:
            xml_content: XML content to validate
            metadata_type: Type of metadata (CustomObject, PermissionSet, etc.)

        Returns:
            List of validation violations
        """
        self.violations = []

        if not xml_content.strip().startswith("<?xml"):
            self.violations.append(
                {
                    "severity": "error",
                    "type": "metadata",
                    "code": "INVALID_XML",
                    "message": "Metadata XML missing XML declaration.",
                    "fix_suggestion": 'Add XML declaration: <?xml version="1.0" encoding="UTF - 8"?>',
                }
            )

        if 'xmlns="http://soap.sforce.com/2006/04/metadata"' not in xml_content:
            self.violations.append(
                {
                    "severity": "error",
                    "type": "metadata",
                    "code": "MISSING_NAMESPACE",
                    "message": "Metadata XML missing Salesforce namespace declaration.",
                    "fix_suggestion": 'Add namespace to root element: xmlns="http://soap.sforce.com/2006/04/metadata"',
                }
            )

        if metadata_type == "CustomObject":
            self._validate_custom_object_metadata(xml_content)

        return self.violations

    def _validate_custom_object_metadata(self, xml_content: str) -> None:
        """Validates Custom Object metadata XML."""
        required_elements = ["label", "pluralLabel", "nameField", "sharingModel"]

        for element in required_elements:
            if f"<{element}>" not in xml_content:
                self.violations.append(
                    {
                        "severity": "error",
                        "type": "metadata",
                        "code": "MISSING_REQUIRED_ELEMENT",
                        "message": f"CustomObject metadata missing required element: <{element}>",
                        "fix_suggestion": f"Add <{element}> element to CustomObject metadata.",
                    }
                )

    def get_violations_summary(self) -> Dict[str, int]:
        """
        Returns a summary of violations by severity.
        """
        summary = {"critical": 0, "error": 0, "warning": 0, "info": 0}

        for violation in self.violations:
            severity = violation.get("severity", "info")
            summary[severity] = summary.get(severity, 0) + 1

        return summary

    def has_critical_violations(self) -> bool:
        """
        Returns True if there are any critical violations.
        """
        return any(v.get("severity") == "critical" for v in self.violations)

    def has_blocking_violations(self) -> bool:
        """Return True when validation produced error or critical findings."""
        return any(v.get("severity") in {"critical", "error"} for v in self.violations)
