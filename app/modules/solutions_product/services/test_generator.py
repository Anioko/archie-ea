"""
TestGenerator — Generate comprehensive tests from architecture specs.

Four test categories:
1. Behavioral tests — from business rules (state transitions, validations)
2. Edge case tests — from field constraints (null, max length, invalid types)
3. Load test config — from SLAs (target RPS, latency thresholds)
4. Security tests — from auth config and quality attributes

Pure deterministic transform — no LLM, no network.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)


def _snake(name):
    """Convert a display name to snake_case."""
    s = re.sub(r"[^a-zA-Z0-9]", "_", (name or "unknown").strip())
    return re.sub(r"_+", "_", s).strip("_").lower()


def _pascal(name):
    """Convert a display name to PascalCase."""
    sanitized = re.sub(r"[^a-zA-Z0-9\s_\-]", "", (name or "Unknown").strip())
    words = re.split(r"[\s_\-]+", sanitized)
    result = "".join(w.capitalize() for w in words if w)
    return result or "Unknown"


def _kebab(name):
    """Convert to kebab-case."""
    s = re.sub(r"[^a-zA-Z0-9\s_-]", "", (name or "unknown").strip())
    return re.sub(r"[\s_]+", "-", s).lower().strip("-")


# ── Field constraint type mapping for edge case generation ──

_FIELD_TYPE_EDGE_CASES = {
    "string": [
        {"suffix": "empty_string", "value": '""', "expect_status": 422, "description": "empty string"},
        {"suffix": "whitespace_only", "value": '"   "', "expect_status": 422, "description": "whitespace only"},
    ],
    "integer": [
        {"suffix": "string_value", "value": '"not_a_number"', "expect_status": 422, "description": "string instead of integer"},
        {"suffix": "float_value", "value": "3.14", "expect_status": 422, "description": "float instead of integer"},
        {"suffix": "null_value", "value": "null", "expect_status": 422, "description": "null value"},
    ],
    "number": [
        {"suffix": "string_value", "value": '"not_a_number"', "expect_status": 422, "description": "string instead of number"},
        {"suffix": "null_value", "value": "null", "expect_status": 422, "description": "null value"},
    ],
    "boolean": [
        {"suffix": "string_value", "value": '"yes"', "expect_status": 422, "description": "string instead of boolean"},
        {"suffix": "integer_value", "value": "1", "expect_status": 422, "description": "integer instead of boolean"},
    ],
    "email": [
        {"suffix": "invalid_format", "value": '"not-an-email"', "expect_status": 422, "description": "invalid email format"},
        {"suffix": "missing_at_sign", "value": '"testexample.com"', "expect_status": 422, "description": "missing @ sign"},
    ],
}


class TestGenerator:
    """Generate comprehensive tests from architecture specs.

    Four test categories:
    1. Behavioral tests -- from business rules (state transitions, validations)
    2. Edge case tests -- from field constraints (null, max length, invalid types)
    3. Load test config -- from SLAs (target RPS, latency thresholds)
    4. Security tests -- from auth config and quality attributes
    """

    def generate_behavioral_tests(self, entity_name, business_rules, fields):
        """Generate test cases from business rules.

        Args:
            entity_name: e.g. "Order"
            business_rules: list of business rule dicts from spec_data
            fields: list of field dicts for required field values in test setup

        Returns:
            list of test case dicts with keys:
                - class_name: PascalCase test class name
                - test_name: snake_case test function name
                - description: human-readable test description
                - setup_status: the initial entity state
                - action: the action to perform (kebab-case URL segment)
                - action_snake: snake_case for function names
                - expected_status_code: HTTP status to assert
                - expected_state: the expected state after action (or None)
                - payload: dict of test payload data (or None)
                - is_negative: whether this is a negative test case
                - rule_id: the business rule this tests
        """
        if not business_rules:
            return []

        test_cases = []
        required_fields = [f for f in (fields or []) if _get_field_attr(f, "required")]

        for rule in business_rules:
            rule_type = _get_rule_attr(rule, "type", "unknown")
            rule_id = _get_rule_attr(rule, "id", "unknown")
            trigger = _get_rule_attr(rule, "trigger", "handle")
            preconditions = _get_rule_attr(rule, "preconditions", [])
            postconditions = _get_rule_attr(rule, "postconditions", [])

            if rule_type == "state_transition":
                test_cases.extend(
                    self._generate_state_transition_tests(
                        entity_name, rule_id, trigger,
                        preconditions, postconditions,
                        required_fields,
                    )
                )
            elif rule_type == "validation":
                test_cases.extend(
                    self._generate_validation_tests(
                        entity_name, rule_id, trigger,
                        preconditions, postconditions,
                        required_fields,
                    )
                )
            elif rule_type == "authorization":
                test_cases.extend(
                    self._generate_authorization_tests(
                        entity_name, rule_id, trigger,
                        preconditions,
                    )
                )
            elif rule_type == "side_effect":
                test_cases.extend(
                    self._generate_side_effect_tests(
                        entity_name, rule_id, trigger,
                        preconditions, postconditions,
                    )
                )

        return test_cases

    def generate_edge_case_tests(self, entity_name, fields):
        """Generate edge case tests from field constraints.

        For each field:
        - Required field: test_create_without_{field}_returns_422
        - String with max_length: test_{field}_exceeding_max_length_rejected
        - Integer with min/max: test_{field}_below_minimum_rejected
        - Email format: test_invalid_email_format_rejected
        - Enum: test_invalid_{field}_value_rejected
        - FK: test_nonexistent_{fk}_returns_404

        Args:
            entity_name: e.g. "Order"
            fields: list of field dicts from confirmed_fields

        Returns:
            list of edge case test dicts
        """
        if not fields:
            return []

        entity_snake = _snake(entity_name)
        test_cases = []

        for field_def in fields:
            name = _get_field_attr(field_def, "name")
            ftype = _get_field_attr(field_def, "type", "string")
            required = _get_field_attr(field_def, "required", False)
            constraints = _get_field_attr(field_def, "constraints", {}) or {}
            enum_values = _get_field_attr(field_def, "enum")
            fmt = _get_field_attr(field_def, "format")

            field_snake = _snake(name)

            # Required field missing
            if required:
                test_cases.append({
                    "test_name": f"test_create_{entity_snake}_without_{field_snake}_returns_422",
                    "description": f"Creating {entity_name} without required field '{name}' should return 422",
                    "field_name": name,
                    "field_type": ftype,
                    "edge_type": "missing_required",
                    "expect_status": 422,
                })

            # Max length exceeded
            max_length = constraints.get("max_length") or constraints.get("maxLength")
            if max_length and ftype == "string":
                test_cases.append({
                    "test_name": f"test_{entity_snake}_{field_snake}_exceeding_max_length_rejected",
                    "description": f"Field '{name}' exceeding max length {max_length} should be rejected",
                    "field_name": name,
                    "field_type": ftype,
                    "edge_type": "max_length_exceeded",
                    "max_length": max_length,
                    "test_value": "x" * (int(max_length) + 1),
                    "expect_status": 422,
                })

            # Min length violated
            min_length = constraints.get("min_length") or constraints.get("minLength")
            if min_length and ftype == "string" and int(min_length) > 0:
                test_cases.append({
                    "test_name": f"test_{entity_snake}_{field_snake}_below_min_length_rejected",
                    "description": f"Field '{name}' below min length {min_length} should be rejected",
                    "field_name": name,
                    "field_type": ftype,
                    "edge_type": "min_length_violated",
                    "min_length": min_length,
                    "test_value": "x" * max(0, int(min_length) - 1),
                    "expect_status": 422,
                })

            # Integer min/max
            minimum = constraints.get("minimum") or constraints.get("min")
            if minimum is not None and ftype in ("integer", "number"):
                test_cases.append({
                    "test_name": f"test_{entity_snake}_{field_snake}_below_minimum_rejected",
                    "description": f"Field '{name}' below minimum {minimum} should be rejected",
                    "field_name": name,
                    "field_type": ftype,
                    "edge_type": "below_minimum",
                    "minimum": minimum,
                    "test_value": int(minimum) - 1 if ftype == "integer" else float(minimum) - 0.01,
                    "expect_status": 422,
                })

            maximum = constraints.get("maximum") or constraints.get("max")
            if maximum is not None and ftype in ("integer", "number"):
                test_cases.append({
                    "test_name": f"test_{entity_snake}_{field_snake}_above_maximum_rejected",
                    "description": f"Field '{name}' above maximum {maximum} should be rejected",
                    "field_name": name,
                    "field_type": ftype,
                    "edge_type": "above_maximum",
                    "maximum": maximum,
                    "test_value": int(maximum) + 1 if ftype == "integer" else float(maximum) + 0.01,
                    "expect_status": 422,
                })

            # Enum invalid value
            if enum_values:
                test_cases.append({
                    "test_name": f"test_{entity_snake}_invalid_{field_snake}_value_rejected",
                    "description": f"Field '{name}' with invalid enum value should be rejected",
                    "field_name": name,
                    "field_type": ftype,
                    "edge_type": "invalid_enum",
                    "valid_values": enum_values,
                    "test_value": "__INVALID_VALUE__",
                    "expect_status": 422,
                })

            # Email format
            if fmt == "email" or ftype == "email":
                for edge in _FIELD_TYPE_EDGE_CASES.get("email", []):
                    test_cases.append({
                        "test_name": f"test_{entity_snake}_{field_snake}_{edge['suffix']}",
                        "description": f"Field '{name}' with {edge['description']} should be rejected",
                        "field_name": name,
                        "field_type": ftype,
                        "edge_type": f"email_{edge['suffix']}",
                        "test_value": edge["value"],
                        "expect_status": edge["expect_status"],
                    })

            # Type mismatch tests
            type_edges = _FIELD_TYPE_EDGE_CASES.get(ftype, [])
            for edge in type_edges:
                test_cases.append({
                    "test_name": f"test_{entity_snake}_{field_snake}_{edge['suffix']}",
                    "description": f"Field '{name}' with {edge['description']} should be rejected",
                    "field_name": name,
                    "field_type": ftype,
                    "edge_type": edge["suffix"],
                    "test_value": edge["value"],
                    "expect_status": edge["expect_status"],
                })

            # FK reference
            if name.endswith("_id") and ftype == "integer":
                ref_entity = name[:-3]  # strip _id
                test_cases.append({
                    "test_name": f"test_{entity_snake}_nonexistent_{field_snake}_returns_404",
                    "description": f"Referencing nonexistent {ref_entity} should return 404",
                    "field_name": name,
                    "field_type": ftype,
                    "edge_type": "nonexistent_fk",
                    "test_value": 999999,
                    "expect_status": 404,
                })

        return test_cases

    def generate_load_test_config(self, service_name, slas, endpoints):
        """Generate k6 load test configuration from SLAs.

        Args:
            service_name: e.g. "order-service"
            slas: list of SLA dicts with metric, value, etc.
            endpoints: list of endpoint dicts with path, method, sample_payload

        Returns:
            dict with keys:
                - service_name: kebab-case service name
                - thresholds: list of k6 threshold dicts
                - scenarios: dict of k6 scenario configs
                - endpoints: list of endpoint configs for the test script
        """
        thresholds = []
        for sla in (slas or []):
            sla_name = sla.get("name", "")
            availability = sla.get("availability")
            response_time_ms = sla.get("response_time_ms")

            if response_time_ms:
                thresholds.append({
                    "metric": "latency",
                    "k6_metric": "http_req_duration",
                    "condition": f"p(99)<{response_time_ms}",
                    "value_ms": response_time_ms,
                    "source_sla": sla_name,
                })

            if availability:
                # Convert availability percentage to failure rate
                # e.g., 99.95% -> 0.0005
                try:
                    avail_pct = float(availability)
                    if avail_pct > 1:
                        avail_pct = avail_pct / 100.0
                    failure_rate = round(1 - avail_pct, 6)
                except (ValueError, TypeError):
                    failure_rate = 0.001
                thresholds.append({
                    "metric": "availability",
                    "k6_metric": "http_req_failed",
                    "condition": f"rate<{failure_rate}",
                    "value_pct": avail_pct * 100 if avail_pct <= 1 else avail_pct,
                    "source_sla": sla_name,
                })

        # Default thresholds if none from SLAs
        if not thresholds:
            thresholds = [
                {
                    "metric": "latency",
                    "k6_metric": "http_req_duration",
                    "condition": "p(99)<500",
                    "value_ms": 500,
                    "source_sla": "default",
                },
                {
                    "metric": "availability",
                    "k6_metric": "http_req_failed",
                    "condition": "rate<0.01",
                    "value_pct": 99.0,
                    "source_sla": "default",
                },
            ]

        # Standard k6 scenarios
        scenarios = {
            "smoke": {
                "executor": "constant-vus",
                "vus": 1,
                "duration": "30s",
            },
            "load": {
                "executor": "ramping-vus",
                "startVUs": 0,
                "stages": [
                    {"duration": "2m", "target": 50},
                    {"duration": "5m", "target": 50},
                    {"duration": "2m", "target": 0},
                ],
            },
            "stress": {
                "executor": "ramping-vus",
                "startVUs": 0,
                "stages": [
                    {"duration": "2m", "target": 200},
                    {"duration": "5m", "target": 200},
                    {"duration": "2m", "target": 0},
                ],
            },
            "spike": {
                "executor": "ramping-vus",
                "startVUs": 0,
                "stages": [
                    {"duration": "10s", "target": 500},
                    {"duration": "1m", "target": 500},
                    {"duration": "10s", "target": 0},
                ],
            },
        }

        # Build endpoint configs
        endpoint_configs = []
        for ep in (endpoints or []):
            endpoint_configs.append({
                "path": ep.get("path", "/"),
                "method": ep.get("method", "GET").upper(),
                "name_snake": _snake(ep.get("name", ep.get("path", "endpoint"))),
                "name_display": ep.get("name", ep.get("path", "endpoint")),
                "sample_payload": ep.get("sample_payload"),
            })

        return {
            "service_name": _kebab(service_name),
            "thresholds": thresholds,
            "scenarios": scenarios,
            "endpoints": endpoint_configs,
        }

    def generate_security_tests(self, auth_config, endpoints):
        """Generate security tests from auth config.

        Args:
            auth_config: dict with provider, issuer, audience, roles, etc.
            endpoints: list of endpoint dicts with path, method, roles_required

        Returns:
            list of security test case dicts
        """
        test_cases = []

        # Authentication tests
        test_cases.append({
            "test_name": "test_unauthenticated_request_returns_401",
            "description": "Request without auth token should return 401",
            "category": "authentication",
            "expect_status": 401,
        })
        test_cases.append({
            "test_name": "test_expired_token_returns_401",
            "description": "Request with expired JWT should return 401",
            "category": "authentication",
            "expect_status": 401,
        })
        test_cases.append({
            "test_name": "test_malformed_token_returns_401",
            "description": "Request with malformed token should return 401",
            "category": "authentication",
            "expect_status": 401,
        })

        # Authorization tests (per-endpoint role checks)
        for ep in (endpoints or []):
            roles_required = ep.get("roles_required", [])
            path_snake = _snake(ep.get("path", "endpoint"))
            if roles_required:
                test_cases.append({
                    "test_name": f"test_wrong_role_on_{path_snake}_returns_403",
                    "description": f"Request with wrong role to {ep.get('path', '/')} should return 403",
                    "category": "authorization",
                    "path": ep.get("path", "/"),
                    "method": ep.get("method", "GET"),
                    "required_roles": roles_required,
                    "expect_status": 403,
                })

        # Injection tests
        test_cases.append({
            "test_name": "test_sql_injection_in_query_params",
            "description": "SQL injection attempt in query parameters should be rejected",
            "category": "injection",
            "payload": "'; DROP TABLE users; --",
            "expect_status": 422,
        })
        test_cases.append({
            "test_name": "test_sql_injection_in_path_params",
            "description": "SQL injection attempt in path parameters should be rejected",
            "category": "injection",
            "payload": "1 OR 1=1",
            "expect_status": 422,
        })
        test_cases.append({
            "test_name": "test_xss_in_text_fields",
            "description": "XSS attempt in text fields should be sanitized or rejected",
            "category": "injection",
            "payload": '<script>alert("xss")</script>',
            "expect_status": 422,
        })

        # Rate limiting
        test_cases.append({
            "test_name": "test_rate_limiting_enforced",
            "description": "Excessive requests should be rate limited (429)",
            "category": "rate_limiting",
            "expect_status": 429,
            "requests_per_second": 100,
        })

        # CORS
        test_cases.append({
            "test_name": "test_cors_headers_present",
            "description": "CORS headers should be present on responses",
            "category": "cors",
            "expect_headers": [
                "Access-Control-Allow-Origin",
                "Access-Control-Allow-Methods",
            ],
        })

        # Auth config-specific tests
        if auth_config:
            provider = auth_config.get("provider", "")
            if provider in ("oidc", "oauth2", "azure_ad", "okta"):
                test_cases.append({
                    "test_name": "test_token_audience_validation",
                    "description": "Token with wrong audience should be rejected",
                    "category": "authentication",
                    "expect_status": 401,
                    "provider": provider,
                })
                test_cases.append({
                    "test_name": "test_token_issuer_validation",
                    "description": "Token with wrong issuer should be rejected",
                    "category": "authentication",
                    "expect_status": 401,
                    "provider": provider,
                })

        return test_cases

    def generate_all(self, bundle):
        """Generate all test categories from a ProductSpecBundle.

        Args:
            bundle: ProductSpecBundle

        Returns:
            dict with keys:
                - behavioral: dict of entity_name -> list of test cases
                - edge_cases: dict of entity_name -> list of test cases
                - load_test: load test config dict
                - security: list of security test cases
                - stats: summary counts
        """
        behavioral = {}
        edge_cases = {}

        confirmed_fields = getattr(bundle, "confirmed_fields", {}) or {}
        business_rules = getattr(bundle, "business_rules", {}) or {}

        # Behavioral tests from business rules
        for entity_name, rules in business_rules.items():
            fields = confirmed_fields.get(entity_name, [])
            tests = self.generate_behavioral_tests(entity_name, rules, fields)
            if tests:
                behavioral[entity_name] = tests

        # Edge case tests from field constraints
        for entity_name, fields in confirmed_fields.items():
            tests = self.generate_edge_case_tests(entity_name, fields)
            if tests:
                edge_cases[entity_name] = tests

        # Build endpoint list from services (used by load_test and security_tests)
        endpoints = []
        for svc in getattr(bundle, "services", []):
            for p in svc.paths:
                endpoints.append({
                    "path": p.path,
                    "method": p.method,
                    "name": p.operation_id,
                })

        # Load test config from SLAs
        # Priority: sla_load_config (populated from SolutionSLA DB rows) > infra_context.slas
        sla_load_config = getattr(bundle, "sla_load_config", None)
        if sla_load_config:
            load_test = sla_load_config
        else:
            slas = []
            infra = getattr(bundle, "infra_context", None)
            if infra:
                slas = getattr(infra, "slas", []) or []

            load_test = self.generate_load_test_config(
                bundle.solution_name, slas, endpoints,
            )

        # Security tests from auth config
        auth_config = getattr(bundle, "identity_provider", None) or {}
        security = self.generate_security_tests(auth_config, endpoints)

        total_behavioral = sum(len(v) for v in behavioral.values())
        total_edge = sum(len(v) for v in edge_cases.values())

        return {
            "behavioral": behavioral,
            "edge_cases": edge_cases,
            "load_test": load_test,
            "security": security,
            "stats": {
                "behavioral_tests": total_behavioral,
                "edge_case_tests": total_edge,
                "security_tests": len(security),
                "load_test_endpoints": len(load_test.get("endpoints", [])),
                "total": total_behavioral + total_edge + len(security),
            },
        }

    # ── Private helpers ──

    def _generate_state_transition_tests(self, entity_name, rule_id, trigger,
                                         preconditions, postconditions,
                                         required_fields):
        """Generate positive and negative tests for state transition rules."""
        tests = []
        entity_snake = _snake(entity_name)
        trigger_snake = _snake(trigger)

        # Extract from/to states from preconditions/postconditions
        from_state = None
        to_state = None
        for pc in preconditions:
            field = _get_cond_attr(pc, "field")
            if field == "status":
                from_state = _get_cond_attr(pc, "value")

        for post in postconditions:
            field = _get_cond_attr(post, "field")
            if field == "status":
                to_state = _get_cond_attr(post, "value")

        if from_state and to_state:
            from_snake = _snake(str(from_state))
            to_snake = _snake(str(to_state))

            # Happy path: valid transition
            tests.append({
                "class_name": f"Test{_pascal(trigger)}",
                "test_name": f"test_{trigger_snake}_from_{from_snake}_to_{to_snake}",
                "description": f"When {entity_name} is {from_state}, {trigger} should change status to {to_state}",
                "setup_status": from_state,
                "action": _kebab(trigger),
                "action_snake": trigger_snake,
                "expected_status_code": 200,
                "expected_state": to_state,
                "payload": None,
                "is_negative": False,
                "rule_id": rule_id,
                "required_fields": _build_required_field_values(required_fields),
            })

            # Negative: invalid source state
            invalid_states = ["completed", "cancelled", "deleted"]
            invalid_state = next(
                (s for s in invalid_states if s != from_state and s != to_state),
                "invalid",
            )
            tests.append({
                "class_name": f"Test{_pascal(trigger)}",
                "test_name": f"test_cannot_{trigger_snake}_from_{_snake(invalid_state)}_state",
                "description": f"{trigger} should fail when status is {invalid_state}",
                "setup_status": invalid_state,
                "action": _kebab(trigger),
                "action_snake": trigger_snake,
                "expected_status_code": 409,
                "expected_state": None,
                "payload": None,
                "is_negative": True,
                "rule_id": rule_id,
                "required_fields": _build_required_field_values(required_fields),
            })

            # Negative: idempotency — already in target state
            tests.append({
                "class_name": f"Test{_pascal(trigger)}",
                "test_name": f"test_cannot_{trigger_snake}_already_{to_snake}_{entity_snake}",
                "description": f"{trigger} should fail when {entity_name} is already {to_state}",
                "setup_status": to_state,
                "action": _kebab(trigger),
                "action_snake": trigger_snake,
                "expected_status_code": 409,
                "expected_state": None,
                "payload": None,
                "is_negative": True,
                "rule_id": rule_id,
                "required_fields": _build_required_field_values(required_fields),
            })

        # Tests for non-status preconditions
        for pc in preconditions:
            field = _get_cond_attr(pc, "field")
            if field == "status":
                continue
            operator = _get_cond_attr(pc, "operator", "==")
            value = _get_cond_attr(pc, "value")
            field_snake = _snake(field)

            tests.append({
                "class_name": f"Test{_pascal(trigger)}",
                "test_name": f"test_cannot_{trigger_snake}_without_{field_snake}",
                "description": f"{trigger} should fail when {field} precondition not met",
                "setup_status": from_state,
                "action": _kebab(trigger),
                "action_snake": trigger_snake,
                "expected_status_code": 409,
                "expected_state": None,
                "payload": None,
                "is_negative": True,
                "rule_id": rule_id,
                "precondition_field": field,
                "precondition_operator": operator,
                "precondition_value": value,
                "required_fields": _build_required_field_values(required_fields),
            })

        return tests

    def _generate_validation_tests(self, entity_name, rule_id, trigger,
                                   preconditions, postconditions,
                                   required_fields):
        """Generate tests for validation rules."""
        tests = []
        trigger_snake = _snake(trigger)

        # Positive: validation passes
        tests.append({
            "class_name": f"Test{_pascal(trigger)}Validation",
            "test_name": f"test_{trigger_snake}_passes_validation",
            "description": f"{trigger} should succeed when all validation rules pass",
            "setup_status": None,
            "action": _kebab(trigger),
            "action_snake": trigger_snake,
            "expected_status_code": 200,
            "expected_state": None,
            "payload": None,
            "is_negative": False,
            "rule_id": rule_id,
            "required_fields": _build_required_field_values(required_fields),
        })

        # Negative: validation fails for each precondition
        for pc in preconditions:
            field = _get_cond_attr(pc, "field")
            field_snake = _snake(field)
            tests.append({
                "class_name": f"Test{_pascal(trigger)}Validation",
                "test_name": f"test_{trigger_snake}_fails_when_{field_snake}_invalid",
                "description": f"{trigger} should fail when {field} validation fails",
                "setup_status": None,
                "action": _kebab(trigger),
                "action_snake": trigger_snake,
                "expected_status_code": 422,
                "expected_state": None,
                "payload": None,
                "is_negative": True,
                "rule_id": rule_id,
                "required_fields": _build_required_field_values(required_fields),
            })

        return tests

    def _generate_authorization_tests(self, entity_name, rule_id, trigger,
                                      preconditions):
        """Generate tests for authorization rules."""
        tests = []
        trigger_snake = _snake(trigger)

        tests.append({
            "class_name": f"Test{_pascal(trigger)}Authorization",
            "test_name": f"test_{trigger_snake}_authorized_user_succeeds",
            "description": f"Authorized user should be able to {trigger}",
            "setup_status": None,
            "action": _kebab(trigger),
            "action_snake": trigger_snake,
            "expected_status_code": 200,
            "expected_state": None,
            "payload": None,
            "is_negative": False,
            "rule_id": rule_id,
        })

        tests.append({
            "class_name": f"Test{_pascal(trigger)}Authorization",
            "test_name": f"test_{trigger_snake}_unauthorized_user_returns_403",
            "description": f"Unauthorized user should not be able to {trigger}",
            "setup_status": None,
            "action": _kebab(trigger),
            "action_snake": trigger_snake,
            "expected_status_code": 403,
            "expected_state": None,
            "payload": None,
            "is_negative": True,
            "rule_id": rule_id,
        })

        return tests

    def _generate_side_effect_tests(self, entity_name, rule_id, trigger,
                                    preconditions, postconditions):
        """Generate tests for side effect rules (events, notifications)."""
        tests = []
        trigger_snake = _snake(trigger)

        tests.append({
            "class_name": f"Test{_pascal(trigger)}SideEffects",
            "test_name": f"test_{trigger_snake}_triggers_side_effects",
            "description": f"{trigger} should trigger expected side effects",
            "setup_status": None,
            "action": _kebab(trigger),
            "action_snake": trigger_snake,
            "expected_status_code": 200,
            "expected_state": None,
            "payload": None,
            "is_negative": False,
            "rule_id": rule_id,
        })

        return tests


# ── Module-level helpers ──

def _get_rule_attr(rule, key, default=None):
    """Get attribute from rule dict or dataclass."""
    if isinstance(rule, dict):
        return rule.get(key, default)
    return getattr(rule, key, default)


def _get_field_attr(field_def, key, default=None):
    """Get attribute from field dict or dataclass."""
    if isinstance(field_def, dict):
        return field_def.get(key, default)
    return getattr(field_def, key, default)


def _get_cond_attr(cond, key, default=None):
    """Get attribute from condition dict or dataclass."""
    if isinstance(cond, dict):
        return cond.get(key, default)
    return getattr(cond, key, default)


def _build_required_field_values(required_fields):
    """Build a dict of required field name -> test value for entity creation."""
    values = {}
    for f in required_fields:
        name = _get_field_attr(f, "name")
        ftype = _get_field_attr(f, "type", "string")
        enum_vals = _get_field_attr(f, "enum")

        if enum_vals:
            values[name] = enum_vals[0]
        elif ftype == "string":
            values[name] = f"test_{name}"
        elif ftype == "integer":
            values[name] = 1
        elif ftype == "number":
            values[name] = 1.0
        elif ftype == "boolean":
            values[name] = True
        elif ftype == "email":
            values[name] = "test@example.com"
        else:
            values[name] = f"test_{name}"
    return values
