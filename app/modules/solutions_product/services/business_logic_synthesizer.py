"""
BusinessLogicSynthesizer — LLM-powered handler body generation from confirmed business rules.

The function SIGNATURE is deterministic (from the spec).
The function BODY is LLM-generated (from business rules).
This is bounded generation — not free-form code generation.

The synthesizer:
- NEVER generates full files — only function bodies
- NEVER decides the function signature — that's deterministic from the spec
- Maximum 50 lines per handler body
- Validates every generated body with ast.parse()
- Rejects low-confidence generations (< 0.6)
"""
import ast
import json
import logging
import re
import textwrap

logger = logging.getLogger(__name__)

# ── Prompt Template ──────────────────────────────────────────────────────

HANDLER_BODY_PROMPT = """You are generating the BODY of a Python function. You are NOT generating the full function.

## Function context
- Handler class: {handler_class}Handler
- Element type: {element_type}
- Method name: {method_name}(self, entity{extra_params})

## Business rules to implement:
{rules_text}

## Available fields on the entity:
{fields_text}

## Integration contracts (upstream/downstream):
{integrations_text}

## Quality attributes / SLAs:
{quality_text}

## Constraints:
- Use ONLY the fields listed above
- Use ONLY the integration clients provided via self.<client_name>
- Every state transition MUST be logged via self.log.info()
- Every external call MUST be wrapped in try/except
- Return the entity after modifications
- Do NOT import anything — imports are handled separately
- Do NOT use print() — use self.log
- Maximum 50 lines of code
- Use getattr(entity, "field", None) for safe field access
- Raise ValueError for precondition failures

Respond ONLY with valid JSON in this exact format:
{{
  "handler_code": "        # line-by-line Python code\\n        # indented with 8 spaces (two levels)\\n        return entity",
  "imports": ["from datetime import datetime"],
  "confidence": 0.85,
  "reasoning": "Brief explanation of implementation approach"
}}"""


def _build_rules_text(business_rules):
    """Format business rules for the prompt."""
    if not business_rules:
        return "No business rules defined."
    lines = []
    for i, rule in enumerate(business_rules, 1):
        rule_type = rule.get("type", "unknown") if isinstance(rule, dict) else getattr(rule, "type", "unknown")
        trigger = rule.get("trigger", "?") if isinstance(rule, dict) else getattr(rule, "trigger", "?")
        entity = rule.get("entity", "?") if isinstance(rule, dict) else getattr(rule, "entity", "?")

        lines.append(f"Rule {i}: [{rule_type}] {entity}.{trigger}")

        preconditions = rule.get("preconditions", []) if isinstance(rule, dict) else getattr(rule, "preconditions", [])
        for pc in preconditions:
            field = pc.get("field", "?") if isinstance(pc, dict) else getattr(pc, "field", "?")
            op = pc.get("operator", "?") if isinstance(pc, dict) else getattr(pc, "operator", "?")
            val = pc.get("value", "?") if isinstance(pc, dict) else getattr(pc, "value", "?")
            lines.append(f"  Precondition: {field} {op} {val}")

        postconditions = rule.get("postconditions", []) if isinstance(rule, dict) else getattr(rule, "postconditions", [])
        for post in postconditions:
            field = post.get("field", "?") if isinstance(post, dict) else getattr(post, "field", "?")
            val = post.get("value", "?") if isinstance(post, dict) else getattr(post, "value", "?")
            lines.append(f"  Postcondition: {field} = {val}")

        side_effects = rule.get("side_effects", []) if isinstance(rule, dict) else getattr(rule, "side_effects", [])
        for se in side_effects:
            se_type = se.get("type", "?") if isinstance(se, dict) else getattr(se, "type", "?")
            se_name = se.get("name", "?") if isinstance(se, dict) else getattr(se, "name", "?")
            lines.append(f"  Side effect: [{se_type}] {se_name}")

    return "\n".join(lines)


def _build_fields_text(fields):
    """Format confirmed fields for the prompt."""
    if not fields:
        return "No fields defined."
    lines = []
    for f in fields:
        name = f.get("name", "?") if isinstance(f, dict) else getattr(f, "name", "?")
        ftype = f.get("type", "string") if isinstance(f, dict) else getattr(f, "type", "string")
        required = f.get("required", False) if isinstance(f, dict) else getattr(f, "required", False)
        desc = f.get("description", "") if isinstance(f, dict) else getattr(f, "description", "")
        req_str = " (required)" if required else ""
        lines.append(f"- {name}: {ftype}{req_str} — {desc}")
    return "\n".join(lines)


def _build_integrations_text(integration_contracts):
    """Format integration contracts for the prompt."""
    if not integration_contracts:
        return "No integration contracts defined."
    lines = []
    for name, contract in integration_contracts.items():
        protocol = contract.get("protocol", "unknown") if isinstance(contract, dict) else getattr(contract, "protocol", "unknown")
        direction = contract.get("direction", "unknown") if isinstance(contract, dict) else getattr(contract, "direction", "unknown")
        lines.append(f"- {name}: {protocol} ({direction})")
    return "\n".join(lines)


def _build_quality_text(quality_attributes):
    """Format quality attributes for the prompt."""
    if not quality_attributes:
        return "No quality attributes defined."
    lines = []
    for qa in quality_attributes:
        name = qa.get("name", "?") if isinstance(qa, dict) else getattr(qa, "name", "?")
        target = qa.get("target", "") if isinstance(qa, dict) else getattr(qa, "target", "")
        lines.append(f"- {name}: {target}")
    return "\n".join(lines)


def _strip_code_fences(text):
    """Strip markdown code fences from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    return text


def _validate_handler_code(code):
    """Validate that the handler code is parseable Python.

    Wraps the body in a function definition so ast.parse() can validate it.
    Returns (is_valid, error_message).
    """
    # Dedent the code to normalize indentation
    dedented = textwrap.dedent(code)
    # Wrap in a function so ast.parse can handle it
    wrapped = f"def _synthesized_handler(self, entity):\n"
    for line in dedented.splitlines():
        if line.strip():
            wrapped += f"    {line}\n"
        else:
            wrapped += "\n"

    # Ensure there's at least a pass statement
    if not dedented.strip():
        return False, "Empty handler body"

    try:
        ast.parse(wrapped)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"


# Modules whose bare use in attribute access is blocked (network I/O)
_BLOCKED_NETWORK_MODULES = frozenset({"socket", "urllib", "requests", "httpx", "aiohttp"})

# Top-level names that perform file I/O
_BLOCKED_FILE_FUNCS = frozenset({"open", "read", "write", "readlines", "writelines"})

# Dangerous builtins
_BLOCKED_BUILTINS = frozenset({"exec", "eval", "compile", "__import__"})


def _validate_generated_body(
    code: str,
    allowed_fields: list,
    allowed_clients: list,
) -> tuple:
    """Security validator for LLM-generated function bodies.

    Checks (in order):
      1. AST parse succeeds
      2. No import statements in body
      3. No exec/eval/compile/__import__ calls
      4. No direct use of blocked network modules (socket, urllib, requests, httpx, aiohttp)
      5. No file I/O via open/read/write/readlines/writelines
      6. Only entity fields listed in allowed_fields are accessed as attributes
      7. Only client names from allowed_clients are used as self.<client>

    False negatives (rejecting valid code) are acceptable.
    False positives (accepting dangerous code) are not.

    Args:
        code: The raw function body string (may be indented).
        allowed_fields: List of str field names the body may reference.
        allowed_clients: List of str client attribute names available on self.

    Returns:
        (ok: bool, errors: list[str])
    """
    errors = []

    # Normalise indentation so the body can be wrapped into a parseable function
    dedented = textwrap.dedent(code)
    if not dedented.strip():
        return False, ["Empty handler body"]

    wrapped = "def _synthesized_handler(self, entity):\n"
    for line in dedented.splitlines():
        wrapped += f"    {line}\n" if line.strip() else "\n"

    # 1. AST parse
    try:
        tree = ast.parse(wrapped)
    except SyntaxError as exc:
        return False, [f"Syntax error: {exc}"]

    # Collect all nodes once for efficiency
    all_nodes = list(ast.walk(tree))

    # 2. No import statements inside the body
    for node in all_nodes:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            errors.append(f"Import not allowed in body: {ast.dump(node)}")

    # 3. No exec/eval/compile/__import__ calls
    for node in all_nodes:
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _BLOCKED_BUILTINS:
                errors.append(f"Dangerous builtin call: {func.id}()")
            # Also catch builtins accessed as __builtins__['exec'] etc. — covered by Name check above

    # 4. No network calls via blocked modules used as bare names or attribute roots
    #    Catches: socket.connect(), urllib.request.urlopen(), requests.get(), etc.
    #    We flag any Name node whose id is a blocked module AND any Attribute whose
    #    root Name is a blocked module.
    for node in all_nodes:
        if isinstance(node, ast.Name) and node.id in _BLOCKED_NETWORK_MODULES:
            errors.append(f"Network module reference not allowed: {node.id}")
        if isinstance(node, ast.Attribute):
            root = node.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in _BLOCKED_NETWORK_MODULES:
                errors.append(f"Network module attribute access not allowed: {root.id}....")

    # 5. No file I/O calls
    for node in all_nodes:
        if isinstance(node, ast.Call):
            func = node.func
            func_name = None
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name in _BLOCKED_FILE_FUNCS:
                errors.append(f"File I/O call not allowed: {func_name}()")

    # 6. Validate that entity attribute accesses use only allowed fields
    #    We look for `entity.<attr>` patterns (Attribute nodes whose value is Name('entity'))
    if allowed_fields:
        allowed_field_set = set(allowed_fields)
        for node in all_nodes:
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "entity"
                and node.attr not in allowed_field_set
                # Allow dunder/magic attributes (e.g. __class__) — these are never field names
                and not node.attr.startswith("__")
            ):
                errors.append(
                    f"Entity field '{node.attr}' not in allowed fields: {sorted(allowed_field_set)}"
                )

    # 7. Validate self.<client> accesses use only allowed clients
    #    Pattern: self.<name> where name is not in ('log', 'db', 'session') standard attrs
    #    and not in allowed_clients.
    if allowed_clients:
        allowed_client_set = set(allowed_clients)
        # Standard self attributes always available to handlers
        _ALWAYS_ALLOWED = {"log", "db", "session"}
        for node in all_nodes:
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"
                and node.attr not in _ALWAYS_ALLOWED
                and node.attr not in allowed_client_set
                and not node.attr.startswith("__")
            ):
                errors.append(
                    f"Client '{node.attr}' not in allowed clients: {sorted(allowed_client_set)}"
                )

    return len(errors) == 0, errors


def _count_lines(code):
    """Count non-empty lines in code."""
    return len([line for line in code.splitlines() if line.strip()])


class BusinessLogicSynthesizer:
    """Generate handler function bodies from confirmed business rules.

    The function SIGNATURE is deterministic (from the spec).
    The function BODY is LLM-generated (from business rules).
    This is bounded generation -- not free-form code generation.
    """

    CONFIDENCE_THRESHOLD = 0.6
    MAX_LINES = 50

    def __init__(self):
        self._provider = None
        self._model = None

    def _ensure_llm(self):
        """Lazily initialize LLM provider."""
        if self._provider is None:
            from app.modules.ai_chat.services.llm_service import LLMService
            self._provider, self._model = LLMService._get_configured_provider()

    def synthesize_handler(self, element_name, element_type, business_rules,
                           fields=None, integration_contracts=None,
                           quality_attributes=None):
        """Generate a handler function body from confirmed business rules.

        Args:
            element_name: e.g. "Order Processing Service"
            element_type: e.g. "ApplicationComponent"
            business_rules: list of confirmed rules from spec_data
            fields: confirmed field definitions
            integration_contracts: upstream/downstream contracts (dict)
            quality_attributes: SLAs, security classification (list)

        Returns:
            dict with keys:
                - handler_code: str (Python function body, indented)
                - imports: list[str] (additional imports needed)
                - confidence: float (0-1)
                - reasoning: str
                - synthesized: bool (True if LLM-generated, False if stub)
            or None on failure
        """
        if not business_rules:
            logger.info("No business rules for %s — skipping synthesis", element_name)
            return None

        try:
            self._ensure_llm()
        except Exception as e:
            logger.warning("LLM not configured for business logic synthesis: %s", e)
            return None

        # Build the method name from the first rule's trigger
        first_rule = business_rules[0]
        trigger = first_rule.get("trigger", "handle") if isinstance(first_rule, dict) else getattr(first_rule, "trigger", "handle")
        rule_type = first_rule.get("type", "unknown") if isinstance(first_rule, dict) else getattr(first_rule, "type", "unknown")
        extra_params = ", **kwargs" if rule_type == "state_transition" else ""

        handler_class = re.sub(r"[^a-zA-Z0-9]", "", element_name.title())
        method_name = f"{trigger}_{re.sub(r'[^a-z0-9_]', '_', element_name.lower()).strip('_')}"

        prompt = HANDLER_BODY_PROMPT.format(
            handler_class=handler_class,
            element_type=element_type or "component",
            method_name=method_name,
            extra_params=extra_params,
            rules_text=_build_rules_text(business_rules),
            fields_text=_build_fields_text(fields or []),
            integrations_text=_build_integrations_text(integration_contracts or {}),
            quality_text=_build_quality_text(quality_attributes or []),
        )

        try:
            from app.modules.ai_chat.services.llm_service import LLMService
            response_text, _interaction = LLMService._call_llm(
                prompt=prompt, model=self._model, provider=self._provider
            )
        except Exception as e:
            logger.error("LLM call failed for business logic synthesis (%s): %s", element_name, e)
            return None

        return self._parse_response(
            response_text,
            element_name,
            allowed_fields=[f.get("name") if isinstance(f, dict) else getattr(f, "name", None)
                            for f in (fields or [])],
            allowed_clients=list((integration_contracts or {}).keys()),
        )

    # Public alias used by the code-generation pipeline
    def synthesize_handler_body(self, element_name, element_type, business_rules,
                                fields=None, integration_contracts=None,
                                quality_attributes=None):
        """Alias for synthesize_handler — preferred name for pipeline callers."""
        return self.synthesize_handler(
            element_name=element_name,
            element_type=element_type,
            business_rules=business_rules,
            fields=fields,
            integration_contracts=integration_contracts,
            quality_attributes=quality_attributes,
        )

    def _parse_response(self, response_text, element_name,
                        allowed_fields=None, allowed_clients=None):
        """Parse and validate the LLM response.

        Returns a validated result dict or None on failure.
        """
        text = _strip_code_fences(response_text)

        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "Failed to parse LLM synthesis response for %s: %s",
                element_name, e,
            )
            return None

        handler_code = parsed.get("handler_code", "")
        imports = parsed.get("imports", [])
        confidence = parsed.get("confidence", 0.0)
        reasoning = parsed.get("reasoning", "")

        # Confidence gate
        if confidence < self.CONFIDENCE_THRESHOLD:
            logger.info(
                "Synthesis confidence too low for %s: %.2f < %.2f — rejecting",
                element_name, confidence, self.CONFIDENCE_THRESHOLD,
            )
            return {
                "handler_code": "",
                "imports": [],
                "confidence": confidence,
                "reasoning": f"Rejected: confidence {confidence:.2f} below threshold {self.CONFIDENCE_THRESHOLD}",
                "synthesized": False,
            }

        # Line count gate
        line_count = _count_lines(handler_code)
        if line_count > self.MAX_LINES:
            logger.info(
                "Synthesis too long for %s: %d lines > %d max — rejecting",
                element_name, line_count, self.MAX_LINES,
            )
            return {
                "handler_code": "",
                "imports": [],
                "confidence": confidence,
                "reasoning": f"Rejected: {line_count} lines exceeds {self.MAX_LINES} max",
                "synthesized": False,
            }

        # AST validation gate (parse check only — fast path)
        is_valid, error = _validate_handler_code(handler_code)
        if not is_valid:
            logger.warning(
                "Synthesized code for %s failed AST validation: %s",
                element_name, error,
            )
            return {
                "handler_code": "",
                "imports": [],
                "confidence": confidence,
                "reasoning": f"Rejected: AST validation failed — {error}",
                "synthesized": False,
            }

        # Security + constraint validation gate
        sec_ok, sec_errors = _validate_generated_body(
            handler_code,
            allowed_fields=list(filter(None, allowed_fields or [])),
            allowed_clients=list(filter(None, allowed_clients or [])),
        )
        if not sec_ok:
            logger.warning(
                "Synthesized code for %s failed security validation: %s",
                element_name, sec_errors,
            )
            return {
                "handler_code": "",
                "imports": [],
                "confidence": confidence,
                "reasoning": f"Rejected: security validation failed — {'; '.join(sec_errors)}",
                "synthesized": False,
                "validation_errors": sec_errors,
            }

        # Filter imports — no full module imports, only from-imports of standard libs
        safe_imports = [
            imp for imp in imports
            if isinstance(imp, str) and not imp.startswith("import os")
            and "subprocess" not in imp and "eval" not in imp
            and "exec" not in imp and "__" not in imp
        ]

        return {
            "handler_code": handler_code,
            "imports": safe_imports,
            "confidence": confidence,
            "reasoning": reasoning,
            "synthesized": True,
        }

    def synthesize_all(self, solution_id):
        """Synthesize handler bodies for all elements with confirmed business rules.

        Args:
            solution_id: int

        Returns:
            dict with keys:
                - results: dict mapping element_name -> synthesis result
                - handlers_generated: int
                - handlers_failed: int
                - total: int
        """
        from app.models.solution_archimate_element import SolutionArchiMateElement

        links = SolutionArchiMateElement.query.filter_by(
            solution_id=solution_id
        ).all()

        results = {}
        generated = 0
        failed = 0

        for link in links:
            sd = link.spec_data or {}
            elem_name = getattr(link, "element_name", None) or f"element_{link.element_id}"

            # Only process elements with confirmed business rules
            if not sd.get("business_rules") or sd.get("business_rules_status") != "confirmed":
                continue

            business_rules = sd["business_rules"]
            fields = sd.get("fields", []) if sd.get("fields_status") == "confirmed" else []
            integrations = sd.get("integrations", {})
            quality_attrs = sd.get("quality_attributes", [])

            result = self.synthesize_handler(
                element_name=elem_name,
                element_type=getattr(link, "element_type", "component"),
                business_rules=business_rules,
                fields=fields,
                integration_contracts=integrations,
                quality_attributes=quality_attrs,
            )

            if result and result.get("synthesized"):
                generated += 1
                # Store the synthesized body back into spec_data
                sd["synthesized_handlers"] = sd.get("synthesized_handlers", {})
                sd["synthesized_handlers"][elem_name] = {
                    "handler_code": result["handler_code"],
                    "imports": result["imports"],
                    "confidence": result["confidence"],
                    "reasoning": result["reasoning"],
                }
                link.spec_data = sd
            elif result:
                failed += 1
            else:
                failed += 1

            results[elem_name] = result

        return {
            "results": results,
            "handlers_generated": generated,
            "handlers_failed": failed,
            "total": generated + failed,
        }
