"""
GenomeValidationService
=======================
Validates a genome dict produced by GenomeExtractionService before it is fed into
DeterministicCodeGenerator.  A broken genome produces broken code regardless of how
good the templates are — this is the single highest-leverage quality gate.

Usage::

    from app.modules.codegen.services.genome_validation_service import (
        GenomeValidationService, GenomeValidationResult
    )

    result = GenomeValidationService().validate(genome)
    if not result.is_valid:
        return jsonify({"error": "Invalid genome", "issues": result.issues}), 422
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class GenomeIssue:
    severity: str       # "error" | "warning" | "info"
    code: str           # machine-readable e.g. "MISSING_ENTITIES"
    message: str
    path: str = ""      # dot-path into genome dict, e.g. "entities[0].fields"


@dataclass
class GenomeValidationResult:
    is_valid: bool
    score: int          # 0-100
    grade: str          # A-F
    issues: list[GenomeIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[GenomeIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[GenomeIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "grade": self.grade,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [
                {
                    "severity": i.severity,
                    "code": i.code,
                    "message": i.message,
                    "path": i.path,
                }
                for i in self.issues
            ],
        }


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class GenomeValidationService:
    """Validates a genome dict for structural correctness and production-readiness."""

    # Allowed tech stack values so we can warn on unknown stacks early
    KNOWN_BACKENDS = {"fastapi", "django", "flask", "express", "rails", "spring"}
    KNOWN_FRONTENDS = {"nextjs", "react", "vue", "angular", "svelte", "nuxt"}
    KNOWN_MOBILE = {"expo", "react-native", "flutter", "swift", "kotlin"}
    KNOWN_DATABASES = {"postgresql", "mysql", "sqlite", "mongodb", "dynamodb", "supabase"}
    KNOWN_AUTH = {"jwt-local", "oauth2", "auth0", "supabase", "firebase", "clerk", "none"}

    # Fields that must be present on every entity
    REQUIRED_ENTITY_KEYS = {"name"}
    # Every entity must have at least one field (otherwise it's an empty table)
    MIN_ENTITY_FIELDS = 1
    # Max sane entities before we warn about scope creep
    MAX_ENTITY_WARN = 40

    # Slug pattern: lowercase, letters/digits/hyphens only
    _SLUG_RE = re.compile(r'^[a-z][a-z0-9-]{0,62}$')
    # Python identifier
    _IDENT_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,63}$')

    def validate(self, genome: dict[str, Any]) -> GenomeValidationResult:
        issues: list[GenomeIssue] = []

        if not isinstance(genome, dict):
            issues.append(GenomeIssue(
                severity="error",
                code="NOT_A_DICT",
                message="Genome must be a dict; got %s" % type(genome).__name__,
            ))
            return self._build_result(issues)

        self._check_app_metadata(genome, issues)
        self._check_tech_stack(genome, issues)
        self._check_entities(genome, issues)
        self._check_services(genome, issues)
        self._check_auth(genome, issues)
        self._check_nfrs(genome, issues)
        self._check_coherence(genome, issues)

        return self._build_result(issues)

    # ------------------------------------------------------------------
    # Section checkers
    # ------------------------------------------------------------------

    def _check_app_metadata(self, genome: dict, issues: list) -> None:
        name = genome.get("app_name") or genome.get("name")
        if not name:
            issues.append(GenomeIssue(
                severity="error",
                code="MISSING_APP_NAME",
                message="genome.app_name is required",
                path="app_name",
            ))
        elif not isinstance(name, str) or len(name.strip()) < 2:
            issues.append(GenomeIssue(
                severity="error",
                code="INVALID_APP_NAME",
                message="app_name must be a non-empty string (got %r)" % name,
                path="app_name",
            ))

        desc = genome.get("description", "")
        if not desc or len(str(desc).strip()) < 10:
            issues.append(GenomeIssue(
                severity="warning",
                code="SHORT_DESCRIPTION",
                message="genome.description is absent or very short — generated CLAUDE.md will lack context",
                path="description",
            ))

    def _check_tech_stack(self, genome: dict, issues: list) -> None:
        ts = genome.get("tech_stack") or genome.get("stack") or {}
        if not ts:
            issues.append(GenomeIssue(
                severity="error",
                code="MISSING_TECH_STACK",
                message="genome.tech_stack is required (e.g. {'backend': 'fastapi', 'frontend': 'nextjs'})",
                path="tech_stack",
            ))
            return

        backend = (ts.get("backend") or "").lower().strip()
        if not backend:
            issues.append(GenomeIssue(
                severity="error",
                code="MISSING_BACKEND",
                message="tech_stack.backend is required",
                path="tech_stack.backend",
            ))
        elif backend not in self.KNOWN_BACKENDS:
            issues.append(GenomeIssue(
                severity="warning",
                code="UNKNOWN_BACKEND",
                message="tech_stack.backend=%r is not a known value %s" % (backend, sorted(self.KNOWN_BACKENDS)),
                path="tech_stack.backend",
            ))

        database = (ts.get("database") or "").lower().strip()
        if not database:
            issues.append(GenomeIssue(
                severity="warning",
                code="MISSING_DATABASE",
                message="tech_stack.database not specified; generator will default to PostgreSQL",
                path="tech_stack.database",
            ))
        elif database not in self.KNOWN_DATABASES:
            issues.append(GenomeIssue(
                severity="warning",
                code="UNKNOWN_DATABASE",
                message="tech_stack.database=%r is not a known value %s" % (database, sorted(self.KNOWN_DATABASES)),
                path="tech_stack.database",
            ))

    def _check_entities(self, genome: dict, issues: list) -> None:
        entities = genome.get("entities") or []
        if not entities:
            issues.append(GenomeIssue(
                severity="error",
                code="MISSING_ENTITIES",
                message="genome.entities is empty — no data model, no code can be generated",
                path="entities",
            ))
            return

        if len(entities) > self.MAX_ENTITY_WARN:
            issues.append(GenomeIssue(
                severity="warning",
                code="TOO_MANY_ENTITIES",
                message="%d entities is a very large scope; consider splitting into multiple solutions" % len(entities),
                path="entities",
            ))

        seen_names: set[str] = set()
        for idx, entity in enumerate(entities):
            path = f"entities[{idx}]"
            if not isinstance(entity, dict):
                issues.append(GenomeIssue(
                    severity="error",
                    code="ENTITY_NOT_DICT",
                    message=f"Entity at index {idx} is not a dict",
                    path=path,
                ))
                continue

            name = entity.get("name", "")
            if not name:
                issues.append(GenomeIssue(
                    severity="error",
                    code="ENTITY_MISSING_NAME",
                    message=f"Entity at index {idx} has no name",
                    path=f"{path}.name",
                ))
                continue

            if not self._IDENT_RE.match(str(name)):
                issues.append(GenomeIssue(
                    severity="error",
                    code="ENTITY_INVALID_NAME",
                    message=f"Entity name {name!r} is not a valid Python identifier",
                    path=f"{path}.name",
                ))

            if name in seen_names:
                issues.append(GenomeIssue(
                    severity="error",
                    code="DUPLICATE_ENTITY_NAME",
                    message=f"Duplicate entity name {name!r}",
                    path=f"{path}.name",
                ))
            seen_names.add(name)

            fields = entity.get("fields") or []
            if len(fields) < self.MIN_ENTITY_FIELDS:
                issues.append(GenomeIssue(
                    severity="error",
                    code="ENTITY_NO_FIELDS",
                    message=f"Entity {name!r} has no fields — would generate an empty table",
                    path=f"{path}.fields",
                ))
            else:
                seen_field_names: set[str] = set()
                for fidx, f in enumerate(fields):
                    fpath = f"{path}.fields[{fidx}]"
                    if not isinstance(f, dict):
                        issues.append(GenomeIssue(
                            severity="error",
                            code="FIELD_NOT_DICT",
                            message=f"Field at {fpath} is not a dict",
                            path=fpath,
                        ))
                        continue
                    fname = f.get("name", "")
                    if not fname:
                        issues.append(GenomeIssue(
                            severity="error",
                            code="FIELD_MISSING_NAME",
                            message=f"Field at {fpath} has no name",
                            path=f"{fpath}.name",
                        ))
                    elif fname in seen_field_names:
                        issues.append(GenomeIssue(
                            severity="error",
                            code="DUPLICATE_FIELD_NAME",
                            message=f"Duplicate field {fname!r} in entity {name!r}",
                            path=f"{fpath}.name",
                        ))
                    seen_field_names.add(fname)

                    python_type = f.get("python_type") or f.get("type")
                    if not python_type:
                        issues.append(GenomeIssue(
                            severity="warning",
                            code="FIELD_MISSING_TYPE",
                            message=f"Field {name}.{fname} has no python_type — generator will default to str",
                            path=f"{fpath}.python_type",
                        ))

    def _check_services(self, genome: dict, issues: list) -> None:
        services = genome.get("services") or []
        # Services are optional but warn if completely absent for non-trivial entity counts
        entities = genome.get("entities") or []
        if len(entities) >= 3 and not services:
            issues.append(GenomeIssue(
                severity="warning",
                code="NO_SERVICES_DECLARED",
                message="No services declared for a %d-entity genome; consider adding service layer for business logic" % len(entities),
                path="services",
            ))

        seen_service_names: set[str] = set()
        for idx, svc in enumerate(services):
            path = f"services[{idx}]"
            if not isinstance(svc, dict):
                continue
            name = svc.get("name", "")
            if name in seen_service_names:
                issues.append(GenomeIssue(
                    severity="warning",
                    code="DUPLICATE_SERVICE_NAME",
                    message=f"Duplicate service name {name!r}",
                    path=f"{path}.name",
                ))
            seen_service_names.add(name)

    def _check_auth(self, genome: dict, issues: list) -> None:
        auth = genome.get("auth") or genome.get("authentication") or {}
        if not auth:
            issues.append(GenomeIssue(
                severity="warning",
                code="MISSING_AUTH",
                message="genome.auth not specified; generator will skip auth scaffolding",
                path="auth",
            ))
            return

        if isinstance(auth, str):
            auth_type = auth.lower()
        elif isinstance(auth, dict):
            auth_type = (auth.get("type") or auth.get("method") or "").lower()
        else:
            auth_type = ""

        if auth_type and auth_type not in self.KNOWN_AUTH:
            issues.append(GenomeIssue(
                severity="warning",
                code="UNKNOWN_AUTH_TYPE",
                message="auth type %r is not in known values %s" % (auth_type, sorted(self.KNOWN_AUTH)),
                path="auth.type",
            ))

    def _check_nfrs(self, genome: dict, issues: list) -> None:
        nfrs = genome.get("nfrs") or genome.get("non_functional_requirements") or []
        if not nfrs:
            issues.append(GenomeIssue(
                severity="info",
                code="NO_NFRS",
                message="No NFRs declared — quality gates will use default thresholds",
                path="nfrs",
            ))

    def _check_coherence(self, genome: dict, issues: list) -> None:
        """Cross-field consistency checks."""
        entities = genome.get("entities") or []
        entity_names = {e.get("name") for e in entities if isinstance(e, dict) and e.get("name")}

        # Foreign keys referencing nonexistent entities
        for idx, entity in enumerate(entities):
            if not isinstance(entity, dict):
                continue
            for fidx, f in enumerate(entity.get("fields") or []):
                if not isinstance(f, dict):
                    continue
                ref = f.get("foreign_key") or f.get("references")
                if ref:
                    # ref may be "EntityName.id" or just "EntityName"
                    ref_entity = str(ref).split(".")[0]
                    if ref_entity and ref_entity not in entity_names:
                        issues.append(GenomeIssue(
                            severity="warning",
                            code="DANGLING_FK",
                            message=f"entities[{idx}].fields[{fidx}] references {ref_entity!r} which is not in entities",
                            path=f"entities[{idx}].fields[{fidx}].foreign_key",
                        ))

        # State machines referencing nonexistent fields
        for idx, entity in enumerate(entities):
            if not isinstance(entity, dict):
                continue
            sm = entity.get("state_machine") or {}
            if sm and isinstance(sm, dict):
                sm_field = sm.get("field") or "status"
                field_names = {
                    f.get("name") for f in (entity.get("fields") or [])
                    if isinstance(f, dict)
                }
                if sm_field not in field_names:
                    issues.append(GenomeIssue(
                        severity="warning",
                        code="STATE_MACHINE_FIELD_MISSING",
                        message=f"entities[{idx}].state_machine.field={sm_field!r} not found in entity fields",
                        path=f"entities[{idx}].state_machine.field",
                    ))

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _build_result(self, issues: list[GenomeIssue]) -> GenomeValidationResult:
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")

        # Scoring: start at 100, deduct per issue
        score = 100 - (error_count * 20) - (warning_count * 5)
        score = max(0, min(100, score))

        if score >= 90:
            grade = "A"
        elif score >= 75:
            grade = "B"
        elif score >= 60:
            grade = "C"
        elif score >= 40:
            grade = "D"
        else:
            grade = "F"

        is_valid = error_count == 0

        return GenomeValidationResult(
            is_valid=is_valid,
            score=score,
            grade=grade,
            issues=issues,
        )
