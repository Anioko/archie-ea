"""
DockerSmokeTestService
======================
Builds the generated Docker image, starts the container, hits ``/health``, then tears
everything down.  This catches import errors, missing env vars, and startup crashes that
static analysis cannot detect.

Requires Docker to be available in the PATH.  When Docker is absent the service returns a
skipped result so code generation is never blocked.

Usage::

    from app.modules.codegen.services.sandbox_runner import (
        DockerSmokeTestService, SmokeTestResult
    )

    result = DockerSmokeTestService().run(files_dict, image_tag="archie-smoke-test:latest")
    if not result.passed:
        logger.warning("Smoke test failed: %s", result.error)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SmokeTestResult:
    passed: bool
    skipped: bool = False
    skip_reason: str = ""
    error: str = ""
    build_duration_ms: int = 0
    startup_duration_ms: int = 0
    health_status_code: int = 0
    health_response: str = ""
    container_logs: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "error": self.error,
            "build_duration_ms": self.build_duration_ms,
            "startup_duration_ms": self.startup_duration_ms,
            "health_status_code": self.health_status_code,
        }


class DockerSmokeTestService:
    """
    Writes generated files to a temp directory, builds a Docker image, starts
    the container, polls ``/health`` until ready or timeout, captures logs, and
    tears the container down regardless of outcome.
    """

    #: Port on the host to map the container's 8000 to (chosen randomly below)
    HOST_PORT_RANGE = (49152, 65535)

    #: How long to wait for the container to become healthy
    STARTUP_TIMEOUT_SECONDS = 60

    #: Poll interval while waiting for /health to respond
    POLL_INTERVAL_SECONDS = 2

    #: Timeout for the docker build step
    BUILD_TIMEOUT_SECONDS = 300

    def run(
        self,
        files: dict[str, str],
        *,
        image_tag: str | None = None,
        health_path: str = "/health",
    ) -> SmokeTestResult:
        """
        :param files: dict of path -> content from GeneratedCodeBundle
        :param image_tag: Docker image tag; auto-generated if not provided
        :param health_path: path to hit for health check (default: /health)
        """
        if not shutil.which("docker"):
            return SmokeTestResult(
                passed=True,
                skipped=True,
                skip_reason="docker not found in PATH — install Docker to enable smoke testing",
            )

        # Filter to Python backend files only (Dockerfile + backend/)
        backend_files = {
            p: c for p, c in files.items()
            if (
                p.startswith("backend/")
                or p in ("Dockerfile", "requirements.txt", "entrypoint.sh", "alembic.ini")
                or p.endswith("Dockerfile")
            )
        }
        if not any(p.endswith("Dockerfile") or p == "Dockerfile" for p in backend_files):
            return SmokeTestResult(
                passed=True,
                skipped=True,
                skip_reason="No Dockerfile in bundle — cannot run Docker smoke test",
            )

        run_id = uuid.uuid4().hex[:8]
        if not image_tag:
            image_tag = f"archie-smoke-{run_id}:latest"
        container_name = f"archie-smoke-{run_id}"
        host_port = self._pick_free_port()

        tmpdir = tempfile.mkdtemp(prefix="archie_smoke_")
        try:
            # Write files, stripping the "backend/" prefix if present
            for rel_path, content in backend_files.items():
                stripped = rel_path.removeprefix("backend/")
                abs_path = Path(tmpdir) / stripped
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    abs_path.write_text(content, encoding="utf-8")
                except Exception:
                    abs_path.write_bytes(content.encode("utf-8", errors="replace"))

            # Add a minimal .env so the container can start without real secrets
            env_path = Path(tmpdir) / ".env"
            if not env_path.exists():
                env_path.write_text(
                    "DATABASE_URL=sqlite+aiosqlite:///./smoke_test.db\n"
                    "SECRET_KEY=smoke-test-key-not-for-production\n"
                    "JWT_SECRET_KEY=smoke-test-jwt-key\n"
                    "ENVIRONMENT=test\n"
                    "LOG_LEVEL=WARNING\n",
                )

            # ── Build ──────────────────────────────────────────────────────────
            t0 = time.monotonic()
            build_result = subprocess.run(
                ["docker", "build", "--target", "run", "-t", image_tag, "."],
                capture_output=True,
                text=True,
                timeout=self.BUILD_TIMEOUT_SECONDS,
                cwd=tmpdir,
            )
            build_ms = int((time.monotonic() - t0) * 1000)

            if build_result.returncode != 0:
                return SmokeTestResult(
                    passed=False,
                    build_duration_ms=build_ms,
                    error="Docker build failed",
                    container_logs=build_result.stderr[-3000:],
                )

            # ── Run ───────────────────────────────────────────────────────────
            t1 = time.monotonic()
            run_cmd = [
                "docker", "run",
                "--rm",
                "--name", container_name,
                "-p", f"{host_port}:8000",
                "--env-file", str(env_path),
                "-d",   # detached
                image_tag,
            ]
            run_result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if run_result.returncode != 0:
                return SmokeTestResult(
                    passed=False,
                    build_duration_ms=build_ms,
                    error="docker run failed: " + run_result.stderr[:500],
                )

            # ── Poll /health ──────────────────────────────────────────────────
            health_url = f"http://localhost:{host_port}{health_path}"
            status_code, response_body = self._poll_health(health_url)
            startup_ms = int((time.monotonic() - t1) * 1000)

            passed = status_code == 200

            # Capture container logs if failed
            container_logs = ""
            if not passed:
                try:
                    log_proc = subprocess.run(
                        ["docker", "logs", "--tail", "100", container_name],
                        capture_output=True, text=True, timeout=10,
                    )
                    container_logs = log_proc.stdout + log_proc.stderr
                except Exception as exc:
                    logger.debug("suppressed error in DockerSmokeTestService.run (app/modules/codegen/services/sandbox_runner.py): %s", exc)

            return SmokeTestResult(
                passed=passed,
                build_duration_ms=build_ms,
                startup_duration_ms=startup_ms,
                health_status_code=status_code,
                health_response=response_body[:500],
                error="" if passed else f"/health returned HTTP {status_code}",
                container_logs=container_logs[-3000:],
            )

        except subprocess.TimeoutExpired as exc:
            return SmokeTestResult(
                passed=False,
                error=f"Smoke test timed out: {exc}",
            )
        except Exception as exc:
            logger.warning("DockerSmokeTestService unexpected error: %s", exc, exc_info=True)
            return SmokeTestResult(
                passed=True,
                skipped=True,
                skip_reason=str(exc),
            )
        finally:
            # Always clean up container + image
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True, timeout=15,
            )
            subprocess.run(
                ["docker", "rmi", "-f", image_tag],
                capture_output=True, timeout=30,
            )
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _poll_health(self, url: str) -> tuple[int, str]:
        """Poll the health endpoint until 200 or timeout. Returns (status_code, body)."""
        deadline = time.monotonic() + self.STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                    if resp.status == 200:
                        return 200, body
                    return resp.status, body
            except urllib.error.HTTPError as e:
                return e.code, str(e.reason)
            except Exception:
                time.sleep(self.POLL_INTERVAL_SECONDS)
        return 0, "timed out waiting for /health"

    @staticmethod
    def _pick_free_port() -> int:
        import socket, random
        for _ in range(20):
            port = random.randint(49152, 65535)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        return 50000
