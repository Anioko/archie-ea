"""
OpenApiDriftDetector
====================
Compares the generated ``openapi.yaml`` spec against the generated FastAPI route files
and flags endpoints that are in one but not the other (drift).

Drift happens when:
- A route is added in ``route.py.j2`` but the spec template isn't updated
- The spec is manually edited but templates regenerate without the new route

Usage::

    from app.modules.codegen.services.openapi_drift_detector import (
        OpenApiDriftDetector, DriftReport
    )

    report = OpenApiDriftDetector().detect(files_dict)
    if report.has_drift:
        logger.warning("OpenAPI drift: %d issues", len(report.issues))
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DriftIssue:
    severity: str       # "error" | "warning"
    code: str
    message: str
    endpoint: str = ""  # e.g. "GET /api/users"


@dataclass
class DriftReport:
    has_drift: bool
    spec_endpoints: list[str] = field(default_factory=list)
    code_endpoints: list[str] = field(default_factory=list)
    issues: list[DriftIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "has_drift": self.has_drift,
            "spec_endpoint_count": len(self.spec_endpoints),
            "code_endpoint_count": len(self.code_endpoints),
            "issue_count": len(self.issues),
            "issues": [
                {
                    "severity": i.severity,
                    "code": i.code,
                    "message": i.message,
                    "endpoint": i.endpoint,
                }
                for i in self.issues
            ],
        }


class OpenApiDriftDetector:
    """
    Parses a ``GeneratedCodeBundle.files`` dict (path → content) looking for:
    - ``openapi.yaml`` or ``openapi.json`` (the spec)
    - ``*.py`` files containing FastAPI ``@router.<method>`` decorators (the code)

    Returns a DriftReport comparing the two endpoint sets.
    """

    # Match FastAPI route decorators: @router.get("/path"), @app.post("/path"), etc.
    _ROUTE_DECORATOR_RE = re.compile(
        r'@(?:router|app)\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    def detect(self, files: dict[str, str]) -> DriftReport:
        """
        :param files: dict of path -> content from GeneratedCodeBundle
        """
        try:
            spec_endpoints = self._extract_spec_endpoints(files)
            code_endpoints = self._extract_code_endpoints(files)
        except Exception as exc:
            logger.warning("OpenApiDriftDetector failed to parse files: %s", exc)
            return DriftReport(
                has_drift=False,
                issues=[
                    DriftIssue(
                        severity="warning",
                        code="PARSE_ERROR",
                        message=f"Could not parse bundle for drift detection: {exc}",
                    )
                ],
            )

        issues: list[DriftIssue] = []

        if not spec_endpoints and not code_endpoints:
            return DriftReport(has_drift=False)

        if not spec_endpoints:
            issues.append(DriftIssue(
                severity="warning",
                code="NO_SPEC",
                message="No openapi.yaml/json found in bundle — cannot check for drift",
            ))
            return DriftReport(has_drift=False, code_endpoints=sorted(code_endpoints), issues=issues)

        spec_set = set(spec_endpoints)
        code_set = set(code_endpoints)

        in_code_not_spec = code_set - spec_set
        in_spec_not_code = spec_set - code_set

        for ep in sorted(in_code_not_spec):
            issues.append(DriftIssue(
                severity="error",
                code="ROUTE_NOT_IN_SPEC",
                message=f"Route {ep} is implemented in code but missing from openapi.yaml",
                endpoint=ep,
            ))

        for ep in sorted(in_spec_not_code):
            issues.append(DriftIssue(
                severity="error",
                code="SPEC_ROUTE_NOT_IN_CODE",
                message=f"Route {ep} is in openapi.yaml but not implemented in route files",
                endpoint=ep,
            ))

        return DriftReport(
            has_drift=len(issues) > 0,
            spec_endpoints=sorted(spec_endpoints),
            code_endpoints=sorted(code_endpoints),
            issues=issues,
        )

    # ------------------------------------------------------------------
    # Spec parser
    # ------------------------------------------------------------------

    def _extract_spec_endpoints(self, files: dict[str, str]) -> list[str]:
        """Extract method + path pairs from openapi.yaml/json."""
        spec_content: Optional[str] = None
        spec_format = "yaml"

        for path, content in files.items():
            basename = path.split("/")[-1].lower()
            if basename in ("openapi.yaml", "openapi.yml"):
                spec_content = content
                spec_format = "yaml"
                break
            if basename == "openapi.json":
                spec_content = content
                spec_format = "json"
                break

        if not spec_content:
            return []

        spec_data = self._parse_spec(spec_content, spec_format)
        if not spec_data or not isinstance(spec_data, dict):
            return []

        paths_section = spec_data.get("paths") or {}
        endpoints: list[str] = []

        for path, methods in paths_section.items():
            if not isinstance(methods, dict):
                continue
            for method in methods:
                if method.lower() in ("get", "post", "put", "patch", "delete", "head", "options"):
                    # Normalise: convert {param} to :param for comparison
                    normalised = self._normalise_path(path)
                    endpoints.append(f"{method.upper()} {normalised}")

        return endpoints

    def _parse_spec(self, content: str, fmt: str) -> Any:
        if fmt == "json":
            import json
            return json.loads(content)
        else:
            try:
                import yaml  # type: ignore
                return yaml.safe_load(content)
            except ImportError:
                # Fallback: naive regex extraction from YAML paths section
                return self._naive_yaml_paths(content)

    def _naive_yaml_paths(self, yaml_content: str) -> dict:
        """
        Very basic YAML paths extraction without a YAML parser.
        Looks for lines like ``  /api/users:`` inside the paths block.
        """
        in_paths = False
        current_path: Optional[str] = None
        paths: dict[str, dict] = {}

        for line in yaml_content.splitlines():
            stripped = line.strip()
            if stripped == "paths:":
                in_paths = True
                continue
            if in_paths:
                # Top-level key in paths block = a path
                m = re.match(r'^  (/[^\s:]+):\s*$', line)
                if m:
                    current_path = m.group(1)
                    paths[current_path] = {}
                    continue
                # HTTP method under a path
                if current_path:
                    mm = re.match(r'^    (get|post|put|patch|delete|head|options):\s*$', line, re.I)
                    if mm:
                        paths[current_path][mm.group(1)] = {}
                # End of paths block
                if stripped and not stripped.startswith("/") and not line.startswith("  ") and not line.startswith("    "):
                    in_paths = False

        return {"paths": paths}

    # ------------------------------------------------------------------
    # Code parser
    # ------------------------------------------------------------------

    def _extract_code_endpoints(self, files: dict[str, str]) -> list[str]:
        """Extract @router.<method>("/path") decorators from Python route files."""
        endpoints: list[str] = []
        for path, content in files.items():
            if not path.endswith(".py"):
                continue
            # Only scan route files
            basename = path.split("/")[-1]
            if not ("route" in basename or "router" in basename or "api" in basename):
                continue
            for m in self._ROUTE_DECORATOR_RE.finditer(content):
                method, route_path = m.group(1), m.group(2)
                normalised = self._normalise_path(route_path)
                endpoints.append(f"{method.upper()} {normalised}")

        return endpoints

    @staticmethod
    def _normalise_path(path: str) -> str:
        """Convert {param} → :param and strip trailing slash."""
        normalised = re.sub(r"\{([^}]+)\}", r":\1", path)
        return normalised.rstrip("/") or "/"
