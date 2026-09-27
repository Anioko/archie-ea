"""Deterministic, fail-closed validator for genome patches (ADR 0009 / 0010).

This is the guardrail that makes the LLM proposal safe: a patch that does not
match `GENOME_PATCH_SCHEMA` is REJECTED and never applied, never coerced, and
never given a fabricated default (CLAUDE.md: never invent data). The caller
gets the concrete list of errors back — the failure is surfaced, not swallowed.

It is a small self-contained interpreter of the JSON-Schema subset the schema
uses (see schema.py docstring), so the flow depends on nothing beyond the
standard library and is fully deterministic even though the *proposal* upstream
is produced by a language model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from app.modules.genome.patch.schema import GENOME_PATCH_SCHEMA


class GenomePatchValidationError(ValueError):
    """Raised by `validate_genome_patch_strict` when a patch is invalid.

    Carries the full list of human-readable errors so a caller that prefers an
    exception boundary (e.g. the applier's defence-in-depth re-check) does not
    have to reconstruct them.
    """

    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors) or "invalid genome patch")


@dataclass
class ValidationResult:
    """Outcome of validating a patch. Truthy iff valid."""

    valid: bool
    errors: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # so `if result:` reads naturally
        return self.valid


_JSON_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def _check(node: Any, schema: dict, path: str, errors: List[str]) -> None:
    """Recursively validate `node` against a JSON-Schema-subset `schema`.

    Appends a message to `errors` for every violation. Never raises, never
    mutates `node` — validation is read-only and side-effect-free.
    """
    expected = schema.get("type")
    if expected:
        py = _JSON_TYPES.get(expected)
        # bool is a subclass of int in Python; keep them distinct so a JSON
        # boolean is never accepted where an integer is required and vice versa.
        if expected in ("integer", "number") and isinstance(node, bool):
            errors.append(f"{path}: expected {expected}, got boolean")
            return
        if py is not None and not isinstance(node, py):
            got = type(node).__name__
            errors.append(f"{path}: expected {expected}, got {got}")
            return  # type wrong — deeper checks would be noise

    if "enum" in schema and node not in schema["enum"]:
        errors.append(f"{path}: {node!r} is not one of {schema['enum']}")

    if expected == "string" and isinstance(node, str):
        min_len = schema.get("minLength")
        if min_len is not None and len(node.strip()) < min_len:
            errors.append(f"{path}: must be a non-empty string (minLength {min_len})")

    if expected == "object" and isinstance(node, dict):
        for req in schema.get("required", []):
            if req not in node or node[req] is None:
                errors.append(f"{path}.{req}: required field missing")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in node:
                if key not in props:
                    errors.append(f"{path}.{key}: unexpected field")
        for key, subschema in props.items():
            if key in node and node[key] is not None:
                _check(node[key], subschema, f"{path}.{key}", errors)

    if expected == "array" and isinstance(node, list):
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(node):
                _check(item, item_schema, f"{path}[{i}]", errors)


def validate_genome_patch(patch: Any) -> ValidationResult:
    """Validate a candidate genome patch. Returns a ValidationResult.

    Fail-closed: anything that is not a dict, or does not satisfy the schema, is
    invalid. On `operation == "modify"` an `element.element_id` is additionally
    required (a modify with nothing to modify is meaningless). No value is ever
    filled in on the caller's behalf.
    """
    errors: List[str] = []

    if not isinstance(patch, dict):
        return ValidationResult(False, [f"$: expected object, got {type(patch).__name__}"])

    _check(patch, GENOME_PATCH_SCHEMA, "$", errors)

    # Conditional requirement the flat schema can't express.
    element = patch.get("element")
    if isinstance(element, dict) and patch.get("operation") == "modify":
        if not isinstance(element.get("element_id"), int) or isinstance(
            element.get("element_id"), bool
        ):
            errors.append(
                "$.element.element_id: required (integer) when operation is 'modify'"
            )

    return ValidationResult(not errors, errors)


def validate_genome_patch_strict(patch: Any) -> None:
    """Like `validate_genome_patch` but raises GenomePatchValidationError.

    Used at the apply boundary as defence-in-depth so an invalid patch can never
    reach a model write even if it somehow got queued.
    """
    result = validate_genome_patch(patch)
    if not result.valid:
        raise GenomePatchValidationError(result.errors)


__all__ = [
    "validate_genome_patch",
    "validate_genome_patch_strict",
    "GenomePatchValidationError",
    "ValidationResult",
]
