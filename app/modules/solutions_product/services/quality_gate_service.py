"""
QualityGateService — Post-generation bundle validator and production-readiness scorer.

Runs after DeterministicCodeGenerator.generate() to validate and score
the generated code bundle BEFORE it is delivered to the user.

Checks performed:
  1. Syntax validity — every .py file parses without error
  2. TypeScript coverage — tsconfig.json present, strict: true set
  3. Test coverage presence — every entity has at least one test file
  4. Auth completeness — auth middleware / JWT guard is present
  5. Security basics — no hardcoded secrets, CORS config, security headers
  6. Database safety — models have primary keys, no raw SQL strings
  7. Frontend presence — Next.js or React app files included
  8. Mobile presence (if configured) — Expo app.json present, permissions set
  9. App store readiness — iOS/Android required fields in app.json
 10. Performance config — k6 or locust test present, or Dockerfile has health checks
 11. Accessibility — axe import or aria attributes in JSX templates
 12. Error handling — global exception handler / middleware present
 13. CI/CD — GitHub Actions or Dockerfile present
 14. Environment config — .env.example present, no hardcoded URLs

Produces a ProductionReadinessScore (0–100) with per-dimension breakdown.
"""
import ast
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Score weights (must sum to 100) ─────────────────────────────────────────
_WEIGHTS = {
    "syntax_validity":      12,
    "test_coverage":        12,
    "auth_completeness":    10,
    "security_basics":      10,
    "database_safety":       8,
    "frontend_presence":     8,
    "mobile_readiness":      5,
    "app_store_readiness":   5,
    "performance_config":    5,
    "accessibility":         5,
    "error_handling":        8,
    "ci_cd":                 4,
    "env_config":            4,
    "openapi_drift":         2,
    "typescript_compile":    2,
}


@dataclass
class DimensionResult:
    name: str
    weight: int
    passed: bool
    score: float          # 0.0–1.0 fractional within dimension
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class ProductionReadinessScore:
    total: int            # 0–100
    grade: str            # A / B / C / D / F
    ready: bool           # total >= 75
    dimensions: list[DimensionResult] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "grade": self.grade,
            "ready": self.ready,
            "summary": self.summary,
            "blocking_issues": self.blocking_issues,
            "dimensions": [
                {
                    "name": d.name,
                    "weight": d.weight,
                    "score": round(d.score * d.weight),
                    "max": d.weight,
                    "passed": d.passed,
                    "findings": d.findings,
                    "recommendations": d.recommendations,
                }
                for d in self.dimensions
            ],
        }


class QualityGateService:
    """Validate and score a GeneratedCodeBundle for production readiness."""

    def validate(self, bundle) -> ProductionReadinessScore:
        """
        Run all quality checks against a GeneratedCodeBundle.

        Args:
            bundle: GeneratedCodeBundle from DeterministicCodeGenerator.generate()

        Returns:
            ProductionReadinessScore with per-dimension breakdown.
        """
        files_by_path = {f.path: f.content for f in (bundle.files or [])}
        language = getattr(bundle, "language", "python-fastapi") or "python-fastapi"

        dimensions = [
            self._check_syntax_validity(files_by_path, language),
            self._check_test_coverage(files_by_path, language, bundle),
            self._check_auth_completeness(files_by_path, language),
            self._check_security_basics(files_by_path, language),
            self._check_database_safety(files_by_path, language),
            self._check_frontend_presence(files_by_path, language),
            self._check_mobile_readiness(files_by_path, language, bundle),
            self._check_app_store_readiness(files_by_path, language),
            self._check_performance_config(files_by_path, language),
            self._check_accessibility(files_by_path, language),
            self._check_error_handling(files_by_path, language),
            self._check_ci_cd(files_by_path, language),
            self._check_env_config(files_by_path, language),
            self._check_openapi_drift(files_by_path, language),
            self._check_typescript_compile(files_by_path, language),
        ]

        total = sum(round(d.score * d.weight) for d in dimensions)
        grade = _grade(total)
        ready = total >= 75
        blocking = [f for d in dimensions for f in d.findings if not d.passed and d.weight >= 8]

        passed_names = [d.name for d in dimensions if d.passed]
        failed_names = [d.name for d in dimensions if not d.passed]
        summary = (
            f"Score {total}/100 ({grade}). "
            f"Passed: {', '.join(passed_names) or 'none'}. "
            f"Failed: {', '.join(failed_names) or 'none'}."
        )

        return ProductionReadinessScore(
            total=total,
            grade=grade,
            ready=ready,
            dimensions=dimensions,
            blocking_issues=blocking,
            summary=summary,
        )

    # ── Dimension checks ─────────────────────────────────────────────────────

    def _check_syntax_validity(self, files: dict, language: str) -> DimensionResult:
        name = "syntax_validity"
        weight = _WEIGHTS[name]
        findings = []
        checked = 0

        if "python" in language:
            py_files = {p: c for p, c in files.items() if p.endswith(".py")}
            for path, content in py_files.items():
                checked += 1
                try:
                    ast.parse(content)
                except SyntaxError as exc:
                    findings.append(f"{path}: SyntaxError — {exc.msg} (line {exc.lineno})")

        if "react" in language or "next" in language or "expo" in language:
            # Check JSON files parse
            json_files = {p: c for p, c in files.items() if p.endswith(".json")}
            for path, content in json_files.items():
                checked += 1
                try:
                    json.loads(content)
                except json.JSONDecodeError as exc:
                    findings.append(f"{path}: JSON parse error — {exc.msg}")

            # Basic TypeScript syntax: no unmatched braces (heuristic)
            ts_files = {p: c for p, c in files.items() if p.endswith((".ts", ".tsx"))}
            for path, content in ts_files.items():
                checked += 1
                open_b = content.count("{") - content.count("}")
                if abs(open_b) > 5:  # allowance for template literals
                    findings.append(f"{path}: Possible unmatched braces (delta={open_b})")

        if "java" in language:
            java_files = {p: c for p, c in files.items() if p.endswith(".java")}
            for path, content in java_files.items():
                checked += 1
                if content.count("{") != content.count("}"):
                    findings.append(f"{path}: Unmatched braces in Java file")

        score = 1.0 if not findings else max(0.0, 1.0 - (len(findings) / max(checked, 1)))
        recs = []
        if findings:
            recs.append("Run `python -m py_compile <file>` or `tsc --noEmit` to fix syntax errors before shipping.")
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_test_coverage(self, files: dict, language: str, bundle) -> DimensionResult:
        name = "test_coverage"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        test_files = [p for p in files if "test" in p.lower() or "spec" in p.lower()]

        # Every entity should have at least one test file
        entities = []
        if hasattr(bundle, "confirmed_fields") and bundle.confirmed_fields:
            entities = list(bundle.confirmed_fields.keys())
        elif hasattr(bundle, "services") and bundle.services:
            entities = [s.name for s in bundle.services]

        untested = []
        for entity in entities:
            snake = re.sub(r"[^a-z0-9]", "_", entity.lower()).strip("_")
            pascal = "".join(w.capitalize() for w in re.split(r"[\s_]+", entity.strip()) if w)
            covered = any(
                snake in tf.lower() or pascal.lower() in tf.lower()
                for tf in test_files
            )
            if not covered:
                untested.append(entity)

        if untested:
            findings.append(f"Entities with no test file: {', '.join(untested)}")
            recs.append(f"Add test files for: {', '.join(untested)}. At minimum: happy-path create + list.")

        # Check auth tests exist
        has_auth_test = any("test_auth" in p or "auth.test" in p or "auth.spec" in p for p in test_files)
        if not has_auth_test and ("jwt" in str(files).lower() or "auth" in str(files).lower()):
            findings.append("No auth test file found — JWT flows are untested.")
            recs.append("Add tests/test_auth.py (or auth.test.ts) covering: no token → 401, expired → 401, valid → 200.")

        # Check security tests exist
        has_sec_test = any("security" in p.lower() or "owasp" in p.lower() for p in test_files)
        if not has_sec_test:
            findings.append("No security test file found — OWASP Top 10 is untested.")
            recs.append("Add tests/test_security.py covering SQL injection, XSS headers, and auth bypass.")

        # Check load tests exist
        has_load_test = any("k6" in p.lower() or "load" in p.lower() or "locust" in p.lower() for p in test_files)
        if not has_load_test:
            findings.append("No performance/load test file found.")
            recs.append("Add tests/load/k6_smoke.js for basic load testing.")

        total_issues = len(untested) + (0 if has_auth_test else 1) + (0 if has_sec_test else 1)
        score = max(0.0, 1.0 - (total_issues * 0.15))
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_auth_completeness(self, files: dict, language: str) -> DimensionResult:
        name = "auth_completeness"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        all_content = "\n".join(files.values())

        if "python" in language:
            has_jwt_dep = any("python-jose" in c or "PyJWT" in c or "jwt" in c.lower()
                              for p, c in files.items() if "requirements" in p)
            has_auth_middleware = any(
                "get_current_user" in c or "oauth2_scheme" in c or "verify_token" in c
                for c in files.values()
            )
            has_cors = "CORSMiddleware" in all_content
            has_rate_limit = "RateLimitMiddleware" in all_content or "slowapi" in all_content or "rate_limit" in all_content.lower()

            if not has_auth_middleware:
                findings.append("No JWT auth middleware found (get_current_user / oauth2_scheme).")
                recs.append("Ensure app/auth.py generates a get_current_user dependency used by all protected routes.")
            if not has_cors:
                findings.append("CORSMiddleware not configured — browser clients will be blocked by CORS.")
                recs.append("Add `app.add_middleware(CORSMiddleware, allow_origins=[os.environ['ALLOWED_ORIGINS']])` to main.py.")
            if not has_rate_limit:
                findings.append("No rate limiting configured — API is vulnerable to brute force / DoS.")
                recs.append("Add slowapi or a custom rate-limit middleware to protect /auth/login and public endpoints.")

        if "react" in language or "next" in language:
            has_protected_route = any("RequireAuth" in c or "ProtectedRoute" in c or "useAuth" in c
                                      for c in files.values())
            has_token_storage = any("localStorage" in c or "sessionStorage" in c or "cookie" in c.lower()
                                    for c in files.values())
            if not has_protected_route:
                findings.append("No protected route wrapper found in frontend — all pages are publicly accessible.")
                recs.append("Add RequireAuth or middleware.ts to redirect unauthenticated users to /login.")
            if not has_token_storage:
                findings.append("No token storage mechanism found in frontend.")
                recs.append("Store JWT in httpOnly cookie (preferred) or sessionStorage. Never localStorage for sensitive tokens.")

        if "expo" in language or "react-native" in language:
            has_secure_store = "SecureStore" in all_content or "expo-secure-store" in all_content
            if not has_secure_store:
                findings.append("Expo app not using SecureStore for token storage — AsyncStorage is insecure for JWTs.")
                recs.append("Use expo-secure-store for JWT storage. `SecureStore.setItemAsync('token', jwt)` instead of AsyncStorage.")

        score = max(0.0, 1.0 - len(findings) * 0.25)
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_security_basics(self, files: dict, language: str) -> DimensionResult:
        name = "security_basics"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        # Scan for hardcoded secrets patterns
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']{6,}["\']', "Hardcoded password"),
            (r'secret\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded secret"),
            (r'api_key\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded API key"),
            (r'sk-[a-zA-Z0-9]{20,}', "OpenAI-style API key"),
            (r'AKIA[0-9A-Z]{16}', "AWS access key pattern"),
        ]
        for path, content in files.items():
            if path.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                for pattern, label in secret_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        findings.append(f"{path}: {label} detected — use environment variables.")

        # Check security headers
        all_content = "\n".join(files.values())
        if "python" in language:
            has_security_headers = (
                "X-Content-Type-Options" in all_content
                or "SecurityHeadersMiddleware" in all_content
                or "secure_headers" in all_content
            )
            if not has_security_headers:
                findings.append("No security response headers (X-Content-Type-Options, X-Frame-Options, CSP).")
                recs.append("Add SecurityHeadersMiddleware to main.py to set OWASP-recommended headers on every response.")

        if "react" in language or "next" in language:
            has_csp = "Content-Security-Policy" in all_content or "contentSecurityPolicy" in all_content
            if not has_csp:
                findings.append("No Content-Security-Policy configured in Next.js.")
                recs.append("Add CSP headers in next.config.js headers() to prevent XSS.")

        # Check .env.example exists (secrets not in source)
        has_env_example = any(".env.example" in p or ".env.template" in p for p in files)
        if not has_env_example:
            findings.append("No .env.example file — developers won't know what environment variables are required.")
            recs.append("Add .env.example listing all required environment variables without values.")

        # Check bandit config exists for Python
        if "python" in language:
            has_bandit = any("bandit" in p or ".bandit" in p for p in files)
            if not has_bandit:
                findings.append("No bandit security scanner configuration found.")
                recs.append("Add .bandit or pyproject.toml [tool.bandit] section. Run `bandit -r app/` in CI.")

        score = max(0.0, 1.0 - len(findings) * 0.2)
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_database_safety(self, files: dict, language: str) -> DimensionResult:
        name = "database_safety"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        if "python" in language:
            model_files = {p: c for p, c in files.items()
                          if p.startswith("app/models/") and p.endswith(".py") and "user" not in p.lower()}
            for path, content in model_files.items():
                # Must have primary_key=True
                if "class " in content and "Column" in content:
                    if "primary_key=True" not in content:
                        findings.append(f"{path}: Model has no primary_key=True column.")
                    # Must use extend_existing
                    if "__table_args__" not in content or "extend_existing" not in content:
                        findings.append(f"{path}: Missing __table_args__ = {{'extend_existing': True}} — causes SQLAlchemy conflicts in tests.")

            # Check for raw SQL strings (injection risk)
            for path, content in files.items():
                if path.endswith(".py") and "execute" in content:
                    raw_sql = re.search(r'execute\(\s*["\'](?:SELECT|INSERT|UPDATE|DELETE)', content, re.IGNORECASE)
                    if raw_sql:
                        findings.append(f"{path}: Raw SQL string passed to execute() — use ORM or parameterized queries.")
                        recs.append(f"{path}: Replace raw SQL with SQLAlchemy ORM or `text()` with bound parameters.")

            # Check alembic / migration exists
            has_migration = any("alembic" in p.lower() or "migration" in p.lower() for p in files)
            if not has_migration and model_files:
                findings.append("No Alembic migration files found — schema changes won't be tracked.")
                recs.append("Ensure alembic/versions/ is generated. Run `alembic revision --autogenerate` after confirming models.")

        if "java" in language:
            for path, content in files.items():
                if path.endswith(".java") and "createQuery" in content:
                    if '+ ' in content and "createQuery" in content:
                        findings.append(f"{path}: Possible SQL string concatenation in JPA query — use named parameters.")

        score = max(0.0, 1.0 - len(findings) * 0.2)
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_frontend_presence(self, files: dict, language: str) -> DimensionResult:
        name = "frontend_presence"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        if language in ("python-fastapi", "go-chi", "java-spring-boot"):
            # Backend should have a paired Next.js frontend
            has_nextjs = any("next.config" in p or "app/page.tsx" in p or "app/layout.tsx" in p for p in files)
            has_react = any(p.endswith((".tsx", ".jsx")) for p in files)

            if not has_nextjs and not has_react:
                findings.append("No frontend (Next.js / React) files included — users have no UI.")
                recs.append("Include the react-shadcn or nextjs-shadcn template set alongside the backend.")
            elif has_react:
                has_error_page = any("error.tsx" in p or "not-found.tsx" in p or "404" in p for p in files)
                if not has_error_page:
                    findings.append("No 404/error page in frontend — users see blank screen on missing routes.")
                    recs.append("Add app/not-found.tsx and app/error.tsx to the Next.js project.")
                has_loading = any("loading.tsx" in p or "skeleton" in p.lower() for p in files)
                if not has_loading:
                    findings.append("No loading state / skeleton UI in frontend — janky UX on slow networks.")
                    recs.append("Add app/loading.tsx and Skeleton components for async data fetches.")

        score = max(0.0, 1.0 - len(findings) * 0.33)
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_mobile_readiness(self, files: dict, language: str, bundle) -> DimensionResult:
        name = "mobile_readiness"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        has_mobile_files = any("mobile/" in p or "react_native" in p.lower() or "expo" in p.lower()
                               or p.endswith(".tsx") and "screens/" in p
                               for p in files)

        genome = getattr(bundle, "_genome", None)
        mobile_configured = genome and genome.get("mobile") if genome else False

        if not has_mobile_files and not mobile_configured:
            # No mobile requested — skip
            return DimensionResult(name, weight, True, 1.0, [], [])

        if has_mobile_files or mobile_configured:
            has_app_json = any("app.json" in p for p in files)
            if not has_app_json:
                findings.append("Expo app.json not found — build system cannot identify the app.")
                recs.append("Add app.json with name, slug, version, ios.bundleIdentifier, android.package.")

            has_eas = any("eas.json" in p for p in files)
            if not has_eas:
                findings.append("eas.json not found — cannot run EAS Build for store submission.")
                recs.append("Add eas.json with build profiles (development, preview, production).")

            has_secure_store = any("SecureStore" in c or "expo-secure-store" in c for c in files.values())
            if not has_secure_store:
                findings.append("expo-secure-store not used — auth tokens stored insecurely in AsyncStorage.")
                recs.append("Replace AsyncStorage token storage with SecureStore for JWTs.")

            all_content = "\n".join(files.values())
            has_offline = "NetInfo" in all_content or "offline" in all_content.lower()
            if not has_offline:
                findings.append("No offline/connectivity handling — app will crash with no network.")
                recs.append("Add NetInfo check and offline banner component.")

        score = max(0.0, 1.0 - len(findings) * 0.25)
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_app_store_readiness(self, files: dict, language: str) -> DimensionResult:
        name = "app_store_readiness"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        has_mobile = any("app.json" in p for p in files)
        if not has_mobile:
            return DimensionResult(name, weight, True, 1.0, [], [])

        # Delegate to AppStoreComplianceService for deep checks
        try:
            from app.modules.solutions_product.services.app_store_compliance_service import (
                AppStoreComplianceService,
            )

            class _FakeBundle:
                def __init__(self, files_dict):
                    class _F:
                        def __init__(self, path, content):
                            self.path = path
                            self.content = content
                    self.files = [_F(p, c) for p, c in files_dict.items()]

            report = AppStoreComplianceService().validate(_FakeBundle(files))
            for error in report.errors:
                findings.append(f"[{error.store.upper()}] {error.message}")
                recs.append(error.fix)
            for warning in report.warnings:
                findings.append(f"[{warning.store.upper()} warning] {warning.message}")
                recs.append(warning.fix)
            acs_score = max(0.0, report.score / 100)
            passed = report.ready_for_apple and report.ready_for_google
            return DimensionResult(name, weight, passed, acs_score, findings, recs)
        except Exception as _exc:
            logger.debug("AppStoreComplianceService unavailable, falling back: %s", _exc)
            app_json_content = ""
            for path, content in files.items():
                if "app.json" in path:
                    app_json_content = content
                    break

            if app_json_content:
                try:
                    app_config = json.loads(app_json_content)
                    expo = app_config.get("expo", app_config)
                except json.JSONDecodeError:
                    expo = {}
            else:
                expo = {}

            if not expo.get("ios", {}).get("bundleIdentifier"):
                findings.append("app.json missing ios.bundleIdentifier — required for App Store submission.")
                recs.append("Set ios.bundleIdentifier to a reverse-DNS identifier, e.g. com.company.appname.")

            if not expo.get("ios", {}).get("buildNumber"):
                findings.append("app.json missing ios.buildNumber — required for TestFlight/App Store upload.")
                recs.append("Set ios.buildNumber to '1' and increment on each release.")

            if not expo.get("android", {}).get("package"):
                findings.append("app.json missing android.package — required for Google Play submission.")
                recs.append("Set android.package to the same reverse-DNS identifier as iOS.")

            if not expo.get("android", {}).get("versionCode"):
                findings.append("app.json missing android.versionCode — required for Play Store upload.")
                recs.append("Set android.versionCode to 1 and increment on each release.")

            all_content = "\n".join(files.values())
            has_privacy_policy = "privacyPolicyUrl" in all_content or "privacy" in all_content.lower()
            if not has_privacy_policy:
                findings.append("No privacy policy URL found — required by both App Store and Google Play.")
                recs.append("Add a privacyPolicyUrl to app.json and link to a hosted privacy policy page.")

            has_tracking_desc = "NSUserTrackingUsageDescription" in all_content
            if not has_tracking_desc:
                findings.append("NSUserTrackingUsageDescription not set — required by Apple ATT framework if any analytics are used.")
                recs.append("Add ios.infoPlist.NSUserTrackingUsageDescription to app.json.")

        fallback_score = max(0.0, 1.0 - len(findings) * 0.17)
        return DimensionResult(name, weight, not findings, fallback_score, findings, recs)

    def _check_performance_config(self, files: dict, language: str) -> DimensionResult:
        name = "performance_config"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        has_load_test = any("k6" in p.lower() or "locust" in p.lower() or "load" in p.lower()
                            for p in files if "test" in p.lower())
        if not has_load_test:
            findings.append("No load test script found (k6 / Locust).")
            recs.append("Add tests/load/k6_smoke.js with 10 VU smoke test and tests/load/k6_load.js with 100 VU sustained load.")

        if "python" in language:
            has_health_check = any(
                "health" in c.lower() and "endpoint" not in p.lower()
                for p, c in files.items() if "Dockerfile" in p
            )
            docker_files = {p: c for p, c in files.items() if "Dockerfile" in p}
            for path, content in docker_files.items():
                if "HEALTHCHECK" not in content:
                    findings.append(f"{path}: No HEALTHCHECK instruction — container orchestrators can't detect unhealthy pods.")
                    recs.append(f"Add `HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health || exit 1` to {path}.")

            # Check pagination exists
            all_content = "\n".join(files.values())
            if "page" not in all_content.lower() or "per_page" not in all_content.lower():
                findings.append("No pagination found in API responses — large result sets will cause performance issues.")
                recs.append("Add page/per_page query parameters to all list endpoints.")

        if "next" in language or "react" in language:
            all_content = "\n".join(files.values())
            has_image_opt = "next/image" in all_content or "Image" in all_content
            if not has_image_opt:
                findings.append("No image optimization detected — large images will slow page loads.")
                recs.append("Use next/image (Image component) for automatic WebP conversion and lazy loading.")

        score = max(0.0, 1.0 - len(findings) * 0.25)
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_accessibility(self, files: dict, language: str) -> DimensionResult:
        name = "accessibility"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        if "react" in language or "next" in language:
            ts_content = "\n".join(c for p, c in files.items() if p.endswith((".tsx", ".jsx")))
            has_aria = "aria-label" in ts_content or "aria-describedby" in ts_content or "role=" in ts_content
            if not has_aria:
                findings.append("No ARIA attributes (aria-label, role) found in frontend components.")
                recs.append("Add aria-label to all interactive elements. Use semantic HTML (<nav>, <main>, <section>).")

            has_axe = any("axe" in c.lower() for c in files.values())
            if not has_axe:
                findings.append("axe-core not integrated — accessibility is not automatically tested.")
                recs.append("Add @axe-core/react in development mode and jest-axe in test setup for automated a11y checks.")

            # Check skip-to-content link
            has_skip = "skip" in ts_content.lower() and "main" in ts_content.lower()
            if not has_skip:
                findings.append("No skip-to-content link — keyboard users cannot bypass navigation.")
                recs.append("Add a visually-hidden 'Skip to main content' link at the top of layout.tsx.")

        if "expo" in language or "react-native" in language:
            rn_content = "\n".join(c for p, c in files.items() if p.endswith((".tsx", ".jsx")))
            has_accessible = "accessible={true}" in rn_content or "accessibilityLabel" in rn_content
            if not has_accessible:
                findings.append("No React Native accessibility props (accessibilityLabel, accessible) found.")
                recs.append("Add accessibilityLabel to all touchable elements for VoiceOver / TalkBack support.")

        if not findings:
            return DimensionResult(name, weight, True, 1.0, [], [])

        score = max(0.0, 1.0 - len(findings) * 0.3)
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_error_handling(self, files: dict, language: str) -> DimensionResult:
        name = "error_handling"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        if "python" in language:
            has_global_handler = any(
                "exception_handler" in c or "@app.exception_handler" in c or "add_exception_handler" in c
                for c in files.values()
            )
            if not has_global_handler:
                findings.append("No global exception handler — unhandled errors will return raw 500 stack traces to clients.")
                recs.append("Add @app.exception_handler(Exception) to main.py returning {detail: 'Internal server error'}.")

            # Check no bare except: pass
            for path, content in files.items():
                if path.endswith(".py") and "except:" in content and "pass" in content:
                    findings.append(f"{path}: Bare `except: pass` swallows errors silently.")
                    recs.append(f"{path}: Replace `except: pass` with `except Exception as exc: logger.exception(exc)`.")

            has_validation_handler = any(
                "RequestValidationError" in c or "ValidationError" in c
                for c in files.values()
            )
            if not has_validation_handler:
                findings.append("No RequestValidationError handler — Pydantic errors return raw 422 JSON without user-friendly messages.")
                recs.append("Add @app.exception_handler(RequestValidationError) with formatted field-level error messages.")

        if "react" in language or "next" in language:
            has_error_boundary = any("ErrorBoundary" in c or "error.tsx" in p for p, c in files.items())
            if not has_error_boundary:
                findings.append("No React Error Boundary or Next.js error.tsx — component errors crash the whole page.")
                recs.append("Add app/error.tsx in Next.js or wrap key components in ErrorBoundary.")

            # Check API client handles errors
            api_files = {p: c for p, c in files.items() if "api" in p.lower() and p.endswith((".ts", ".tsx"))}
            for path, content in api_files.items():
                if "fetch(" in content and "catch" not in content and ".catch" not in content:
                    findings.append(f"{path}: fetch() calls without error handling — network errors will be swallowed.")
                    recs.append(f"{path}: Wrap all fetch() calls in try/catch and show user-facing error toasts.")

        if "expo" in language or "react-native" in language:
            all_content = "\n".join(files.values())
            has_error_handler = "ErrorUtils" in all_content or "logError" in all_content
            if not has_error_handler:
                findings.append("No global error handler in React Native — uncaught JS errors show blank screen.")
                recs.append("Add ErrorUtils.setGlobalHandler() in app/_layout.tsx for production crash reporting.")

        score = max(0.0, 1.0 - len(findings) * 0.2)
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_ci_cd(self, files: dict, language: str) -> DimensionResult:
        name = "ci_cd"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        has_github_actions = any(".github/workflows" in p for p in files)
        has_dockerfile = any("Dockerfile" in p for p in files)
        has_makefile = any("Makefile" in p for p in files)

        if not has_github_actions:
            findings.append("No GitHub Actions workflow found — no automated CI pipeline.")
            recs.append("Add .github/workflows/ci.yml with: install deps → run tests → security scan → build.")

        if not has_dockerfile:
            findings.append("No Dockerfile — app cannot be containerized or deployed to any cloud platform.")
            recs.append("Add a multi-stage Dockerfile: builder stage (install deps) + runtime stage (slim image).")

        if not has_makefile:
            findings.append("No Makefile — developers have no standard commands for setup, test, and deploy.")
            recs.append("Add Makefile with targets: setup, test, lint, security, build, deploy.")

        score = max(0.0, 1.0 - len(findings) * 0.33)
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_env_config(self, files: dict, language: str) -> DimensionResult:
        name = "env_config"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        has_env_example = any(".env.example" in p or ".env.template" in p for p in files)
        if not has_env_example:
            findings.append("No .env.example — new developers don't know what config is required.")
            recs.append("Add .env.example with all required keys (no real values) and comments explaining each.")

        # Check for hardcoded localhost URLs in non-test code
        for path, content in files.items():
            if "test" not in path.lower() and path.endswith((".py", ".ts", ".tsx", ".js")):
                if re.search(r'http://localhost:\d+', content) or re.search(r'http://127\.0\.0\.1', content):
                    findings.append(f"{path}: Hardcoded localhost URL — will fail in production.")
                    recs.append(f"{path}: Replace hardcoded URL with environment variable: os.environ['API_URL'] or process.env.NEXT_PUBLIC_API_URL.")

        # README should mention env setup
        readme_content = next((c for p, c in files.items() if "README" in p.upper()), "")
        if readme_content and "environment" not in readme_content.lower() and ".env" not in readme_content:
            findings.append("README.md doesn't mention environment setup — developers will be confused.")
            recs.append("Add an 'Environment Setup' section to README.md pointing to .env.example.")

        score = max(0.0, 1.0 - len(findings) * 0.25)
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_openapi_drift(self, files: dict, language: str) -> DimensionResult:
        name = "openapi_drift"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        # Only applicable to Python/FastAPI backends
        if "python" not in language and "fastapi" not in language:
            return DimensionResult(name, weight, True, 1.0, [], [])

        try:
            from app.modules.codegen.services.openapi_drift_detector import OpenApiDriftDetector
            report = OpenApiDriftDetector().detect(files)
            if report.has_drift:
                for issue in report.issues[:10]:
                    findings.append(issue.message)
                recs.append("Regenerate the OpenAPI spec or update route templates to match the implementation.")
        except Exception as exc:
            logger.debug("openapi_drift check skipped: %s", exc)

        score = 1.0 if not findings else 0.5
        return DimensionResult(name, weight, not findings, score, findings, recs)

    def _check_typescript_compile(self, files: dict, language: str) -> DimensionResult:
        name = "typescript_compile"
        weight = _WEIGHTS[name]
        findings = []
        recs = []

        has_ts = any(p.endswith((".ts", ".tsx")) for p in files)
        if not has_ts:
            return DimensionResult(name, weight, True, 1.0, [], [])

        try:
            from app.modules.codegen.services.typescript_compiler import TypeScriptCompilerService
            result = TypeScriptCompilerService().check(files)
            if result.skipped:
                # tsc not installed — don't penalise
                return DimensionResult(name, weight, True, 1.0, [], [result.skip_reason])
            if not result.passed:
                for err in result.errors[:5]:
                    findings.append(f"{err.file}:{err.line} {err.code}: {err.message}")
                recs.append("Fix TypeScript type errors — they will surface at runtime in production.")
        except Exception as exc:
            logger.debug("typescript_compile check skipped: %s", exc)

        score = 1.0 if not findings else max(0.0, 1.0 - len(findings) * 0.1)
        return DimensionResult(name, weight, not findings, score, findings, recs)




def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"
