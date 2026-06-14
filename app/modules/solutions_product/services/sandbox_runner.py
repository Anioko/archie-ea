"""
SandboxRunner — Build and test generated code in a Docker sandbox.

Wave 1: Writes files to temp dir, builds Docker image, runs pytest, parses output.
Security: --network=none, hard timeouts, cleanup after run.
"""
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TestFailure:
    test_name: str
    error: str
    expected_in_wave1: bool
    logs: str = ""


@dataclass
class SandboxRunResult:
    bundle_id: str
    status: str  # "passed" | "failed" | "build_error" | "timeout"
    build_log: str | None = None
    test_summary: dict = field(default_factory=lambda: {"passed": 0, "failed": 0, "errors": 0})
    failures: list[TestFailure] = field(default_factory=list)
    duration_seconds: float = 0.0


def _docker_available():
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _parse_pytest_output(output):
    """Parse pytest --tb=short -q output into summary and failures."""
    summary = {"passed": 0, "failed": 0, "errors": 0}
    failures = []

    lines = output.split("\n")

    # Parse summary line: "18 passed, 3 failed in 2.5s"
    for line in reversed(lines):
        match = re.search(r"(\d+) passed", line)
        if match:
            summary["passed"] = int(match.group(1))
        match = re.search(r"(\d+) failed", line)
        if match:
            summary["failed"] = int(match.group(1))
        match = re.search(r"(\d+) error", line)
        if match:
            summary["errors"] = int(match.group(1))
        if "passed" in line or "failed" in line or "error" in line:
            break

    # Parse FAILED lines
    current_test = None
    current_logs = []
    for line in lines:
        if line.startswith("FAILED "):
            if current_test:
                error_text = "\n".join(current_logs)
                failures.append(TestFailure(
                    test_name=current_test,
                    error=error_text,
                    expected_in_wave1="501" in error_text,
                    logs=error_text,
                ))
            # Extract test name: "FAILED tests/test_contracts.py::test_foo - AssertionError"
            parts = line.split(" - ", 1)
            test_path = parts[0].replace("FAILED ", "").strip()
            current_test = test_path.split("::")[-1] if "::" in test_path else test_path
            current_logs = [parts[1]] if len(parts) > 1 else []
        elif current_test and line.strip():
            current_logs.append(line)

    # Don't forget the last test
    if current_test:
        error_text = "\n".join(current_logs)
        failures.append(TestFailure(
            test_name=current_test,
            error=error_text,
            expected_in_wave1="501" in error_text,
            logs=error_text,
        ))

    return summary, failures


class SandboxRunner:
    """Run generated code in a Docker sandbox.

    Two modes:
    - test: build → run pytest → parse results → cleanup (stateless)
    - preview: build → run uvicorn → return URL → auto-stop after TTL (stateful)

    Writes files → docker build → docker run pytest → parse results → cleanup.
    """

    BUILD_TIMEOUT = 120  # seconds
    TEST_TIMEOUT = 60    # seconds
    PREVIEW_TTL = 600    # 10 minutes
    PREVIEW_PORT_START = 9100  # dynamic port range for previews
    PREVIEW_PORT_END = 9199

    # Track active preview containers
    _active_previews = {}  # bundle_id → {container_id, port, started_at}

    def run(self, bundle):
        """Run the generated code bundle in a sandbox.

        Args:
            bundle: GeneratedCodeBundle with files to build and test.

        Returns:
            SandboxRunResult with test results.
        """
        start = time.monotonic()

        if not _docker_available():
            return SandboxRunResult(
                bundle_id=bundle.bundle_id,
                status="build_error",
                build_log="Docker not available",
                duration_seconds=time.monotonic() - start,
            )

        image_tag = f"archie-product-{bundle.solution_id}:{bundle.bundle_id}".lower()
        # Docker tags can't have certain chars
        image_tag = re.sub(r"[^a-z0-9:._-]", "-", image_tag)

        tmpdir = tempfile.mkdtemp(prefix="archie-sandbox-")
        try:
            # Write all files
            for f in bundle.files:
                fpath = os.path.join(tmpdir, f.path)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "w", encoding="utf-8") as fp:
                    fp.write(f.content)

            # Docker build (test target)
            build_result = subprocess.run(
                ["docker", "build", "-t", image_tag, "--target", "test", "."],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=self.BUILD_TIMEOUT,
            )

            if build_result.returncode != 0:
                return SandboxRunResult(
                    bundle_id=bundle.bundle_id,
                    status="build_error",
                    build_log=build_result.stderr[-2000:] if build_result.stderr else build_result.stdout[-2000:],
                    duration_seconds=time.monotonic() - start,
                )

            # Docker run (--network=none for security)
            try:
                run_result = subprocess.run(
                    ["docker", "run", "--rm", "--network=none", image_tag],
                    capture_output=True,
                    text=True,
                    timeout=self.TEST_TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                return SandboxRunResult(
                    bundle_id=bundle.bundle_id,
                    status="timeout",
                    duration_seconds=time.monotonic() - start,
                )

            output = run_result.stdout + "\n" + run_result.stderr
            summary, failures = _parse_pytest_output(output)

            status = "passed" if summary["failed"] == 0 and summary["errors"] == 0 else "failed"

            return SandboxRunResult(
                bundle_id=bundle.bundle_id,
                status=status,
                test_summary=summary,
                failures=failures,
                duration_seconds=time.monotonic() - start,
            )

        except subprocess.TimeoutExpired:
            return SandboxRunResult(
                bundle_id=bundle.bundle_id,
                status="timeout",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as e:
            logger.exception("Sandbox run failed")
            return SandboxRunResult(
                bundle_id=bundle.bundle_id,
                status="build_error",
                build_log=str(e),
                duration_seconds=time.monotonic() - start,
            )
        finally:
            # Cleanup temp dir
            shutil.rmtree(tmpdir, ignore_errors=True)
            # Cleanup Docker image
            try:
                subprocess.run(
                    ["docker", "rmi", image_tag],
                    capture_output=True,
                    timeout=30,
                )
            except Exception as e:
                logger.debug("Docker image cleanup failed: %s", e)

    def preview(self, bundle):
        """Start the generated service and return a preview URL.

        Builds the Docker image (run target, not test), starts uvicorn on a
        dynamic port, returns the URL. Container auto-stops after PREVIEW_TTL.

        Args:
            bundle: GeneratedCodeBundle with files to build and run.

        Returns:
            dict with: url, container_id, port, bundle_id, status
        """
        if not _docker_available():
            return {"status": "error", "error": "Docker not available"}

        # Stop existing preview for this bundle if any
        self.stop_preview(bundle.bundle_id)

        # Find available port
        port = self._find_available_port()
        if not port:
            return {"status": "error", "error": "No available preview ports (all 9100-9199 in use)"}

        image_tag = f"archie-preview-{bundle.solution_id}:{bundle.bundle_id}".lower()
        image_tag = re.sub(r"[^a-z0-9:._-]", "-", image_tag)
        container_name = f"archie-preview-{bundle.solution_id}-{bundle.bundle_id}".lower()
        container_name = re.sub(r"[^a-z0-9_.-]", "-", container_name)

        tmpdir = tempfile.mkdtemp(prefix="archie-preview-")
        try:
            # Write all files
            for f in bundle.files:
                fpath = os.path.join(tmpdir, f.path)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "w", encoding="utf-8") as fp:
                    fp.write(f.content)

            # Docker build (run target = production image with uvicorn)
            build_result = subprocess.run(
                ["docker", "build", "-t", image_tag, "--target", "run", "."],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=self.BUILD_TIMEOUT,
            )

            if build_result.returncode != 0:
                return {
                    "status": "build_error",
                    "error": build_result.stderr[-1000:] if build_result.stderr else "Build failed",
                }

            # Start container in background with port mapping
            # --stop-timeout ensures graceful shutdown
            run_result = subprocess.run(
                [
                    "docker", "run", "-d",
                    "--name", container_name,
                    "-p", f"{port}:8000",
                    "--stop-timeout", "5",
                    image_tag,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if run_result.returncode != 0:
                return {
                    "status": "error",
                    "error": run_result.stderr[-500:] if run_result.stderr else "Container start failed",
                }

            container_id = run_result.stdout.strip()[:12]

            # Track active preview
            SandboxRunner._active_previews[bundle.bundle_id] = {
                "container_id": container_id,
                "container_name": container_name,
                "port": port,
                "image_tag": image_tag,
                "started_at": time.monotonic(),
            }

            # Schedule auto-stop (fire-and-forget background cleanup)
            self._schedule_auto_stop(bundle.bundle_id, container_name, image_tag)

            return {
                "status": "running",
                "url": f"http://localhost:{port}",
                "port": port,
                "container_id": container_id,
                "bundle_id": bundle.bundle_id,
                "ttl_seconds": self.PREVIEW_TTL,
                "health_url": f"http://localhost:{port}/health",
                "docs_url": f"http://localhost:{port}/docs",
            }

        except Exception as e:
            logger.exception("Preview start failed")
            return {"status": "error", "error": str(e)}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def stop_preview(self, bundle_id):
        """Stop a running preview container."""
        info = SandboxRunner._active_previews.pop(bundle_id, None)
        if not info:
            return
        try:
            subprocess.run(
                ["docker", "stop", info["container_name"]],
                capture_output=True, timeout=15,
            )
            subprocess.run(
                ["docker", "rm", info["container_name"]],
                capture_output=True, timeout=15,
            )
            subprocess.run(
                ["docker", "rmi", info["image_tag"]],
                capture_output=True, timeout=15,
            )
            logger.info("Stopped preview container %s (port %s)", info["container_name"], info["port"])
        except Exception as e:
            logger.debug("Preview cleanup failed: %s", e)

    def _find_available_port(self):
        """Find an available port in the preview range."""
        used_ports = {v["port"] for v in SandboxRunner._active_previews.values()}
        for port in range(self.PREVIEW_PORT_START, self.PREVIEW_PORT_END + 1):
            if port not in used_ports:
                return port
        return None

    def _schedule_auto_stop(self, bundle_id, container_name, image_tag):
        """Schedule auto-stop after TTL using a background thread."""
        import threading

        def _auto_stop():
            time.sleep(self.PREVIEW_TTL)
            if bundle_id in SandboxRunner._active_previews:
                logger.info("Auto-stopping preview %s after %ss TTL", bundle_id, self.PREVIEW_TTL)
                self.stop_preview(bundle_id)

        t = threading.Thread(target=_auto_stop, daemon=True)
        t.start()
