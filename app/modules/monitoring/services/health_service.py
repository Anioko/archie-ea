"""
Health check service — encapsulates all health probe logic.

Extracted from app/routes/health_routes.py to enforce thin-route pattern.
Each check returns a standardized dict with: status, response_time_ms, message.

PRD-003: Probes now run concurrently with 1-second per-probe timeout.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from typing import Any, Dict, Tuple

from flask import current_app
from sqlalchemy import text

from app.extensions import db

# Maximum time (seconds) any single health probe may take.
_PROBE_TIMEOUT = 1.0


class HealthService:
    """Runs health probes against system components.

    All public methods return a dict conforming to::

        {
            "status":           "healthy" | "degraded" | "unhealthy" | "not_configured",
            "response_time_ms": float | None,
            "message":          str,
            "last_checked":     str (ISO-8601),
            ...extra keys specific to the probe
        }
    """

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    @staticmethod
    def check_database() -> Dict[str, Any]:
        """Check database connectivity and response time."""
        start = time.time()
        try:
            db.session.execute(text("SELECT 1"))  # tenant-exempt: health check
            db.session.commit()
            elapsed = (time.time() - start) * 1000
            return {
                "status": "healthy",
                "response_time_ms": round(elapsed, 2),
                "message": "Database connection successful",
                "last_checked": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            current_app.logger.error(f"Database health check failed: {exc}")
            return {
                "status": "unhealthy",
                "response_time_ms": None,
                "message": f"Database connection failed: {exc}",
                "last_checked": datetime.utcnow().isoformat(),
            }

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    @staticmethod
    def check_storage() -> Dict[str, Any]:
        """Check file-system access for the uploads directory."""
        start = time.time()
        try:
            upload_folder = current_app.config.get(
                "UPLOAD_FOLDER",
                os.path.join(current_app.root_path, "uploads", "documents"),
            )
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder, exist_ok=True)

            test_file = os.path.join(upload_folder, ".health_check")
            with open(test_file, "w") as fh:
                fh.write("health check")
            os.remove(test_file)

            elapsed = (time.time() - start) * 1000
            return {
                "status": "healthy",
                "response_time_ms": round(elapsed, 2),
                "message": "Storage access successful",
                "upload_folder": upload_folder,
                "last_checked": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            current_app.logger.error(f"Storage health check failed: {exc}")
            return {
                "status": "unhealthy",
                "response_time_ms": None,
                "message": f"Storage access failed: {exc}",
                "last_checked": datetime.utcnow().isoformat(),
            }

    # ------------------------------------------------------------------
    # Cache (Redis)
    # ------------------------------------------------------------------
    @staticmethod
    def check_cache() -> Dict[str, Any]:
        """Check Redis/cache connectivity and response time."""
        start = time.time()
        try:
            import redis as redis_lib

            redis_url = current_app.config.get("REDIS_URL") or current_app.config.get(
                "RQ_DEFAULT_URL"
            )
            if not redis_url:
                return {
                    "status": "not_configured",
                    "response_time_ms": None,
                    "message": "Redis URL not configured",
                    "last_checked": datetime.utcnow().isoformat(),
                }

            r = redis_lib.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
            r.ping()
            elapsed = (time.time() - start) * 1000
            return {
                "status": "healthy",
                "response_time_ms": round(elapsed, 2),
                "message": "Redis connection successful",
                "last_checked": datetime.utcnow().isoformat(),
            }
        except ImportError:
            return {
                "status": "not_available",
                "response_time_ms": None,
                "message": "Redis library not installed",
                "last_checked": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            current_app.logger.error(f"Cache health check failed: {exc}")
            return {
                "status": "unhealthy",
                "response_time_ms": None,
                "message": f"Redis connection failed: {exc}",
                "last_checked": datetime.utcnow().isoformat(),
            }

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------
    @staticmethod
    def check_llm() -> Dict[str, Any]:
        """Check LLM provider configuration status."""
        start = time.time()
        try:
            from app.services.feature_flag_service import FeatureFlagService

            llm_info = FeatureFlagService.get_configured_provider_info()
            elapsed = (time.time() - start) * 1000

            if llm_info["configured"]:
                return {
                    "status": "healthy",
                    "response_time_ms": round(elapsed, 2),
                    "message": "LLM provider configured",
                    "provider": llm_info.get("provider"),
                    "model": llm_info.get("model"),
                    "last_checked": datetime.utcnow().isoformat(),
                }
            return {
                "status": "degraded",
                "response_time_ms": round(elapsed, 2),
                "message": "LLM provider not configured",
                "provider": None,
                "model": None,
                "last_checked": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            current_app.logger.error(f"LLM health check failed: {exc}")
            return {
                "status": "unhealthy",
                "response_time_ms": None,
                "message": f"LLM check failed: {exc}",
                "last_checked": datetime.utcnow().isoformat(),
            }

    # ------------------------------------------------------------------
    # External services
    # ------------------------------------------------------------------
    @staticmethod
    def check_external_services() -> Dict[str, Dict[str, str]]:
        """Check external service availability."""
        services: Dict[str, Dict[str, str]] = {}
        try:
            from app.services.feature_flag_service import FeatureFlagService

            ai_enabled = FeatureFlagService.is_ai_enabled()
            services["ai_features"] = {
                "status": "enabled" if ai_enabled else "disabled",
                "message": (
                    "AI features are available"
                    if ai_enabled
                    else "AI features disabled - LLM not configured"
                ),
            }
        except Exception as exc:
            services["ai_features"] = {"status": "error", "message": str(exc)}
        return services

    # ------------------------------------------------------------------
    # Vendor subsystem
    # ------------------------------------------------------------------
    @staticmethod
    def check_vendors() -> Dict[str, Any]:
        """Check vendor subsystem health."""
        start = time.time()
        try:
            result = db.session.execute(  # tenant-exempt: health check
                text("SELECT COUNT(*), MAX(updated_at) FROM vendor_organizations")  # tenant-exempt
            ).fetchone()

            vendor_count = result[0] if result else 0
            last_update = result[1] if result and result[1] else None
            elapsed = (time.time() - start) * 1000

            status = "healthy"
            message = f"Vendor subsystem operational ({vendor_count} vendors)"
            if vendor_count == 0:
                status = "degraded"
                message = "No vendors in database - seed data may be needed"

            return {
                "status": status,
                "response_time_ms": round(elapsed, 2),
                "vendor_count": vendor_count,
                "last_update": last_update.isoformat() if last_update else None,
                "message": message,
                "last_checked": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            current_app.logger.error(f"Vendor health check failed: {exc}")
            return {
                "status": "unhealthy",
                "response_time_ms": None,
                "error": str(exc),
                "message": "Vendor subsystem check failed",
                "last_checked": datetime.utcnow().isoformat(),
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _timeout_result(name: str) -> Dict[str, Any]:
        """Return a standardised result for a probe that exceeded its timeout."""
        return {
            "status": "timeout",
            "response_time_ms": round(_PROBE_TIMEOUT * 1000, 2),
            "message": f"{name} probe exceeded {_PROBE_TIMEOUT}s timeout",
            "last_checked": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Aggregated
    # ------------------------------------------------------------------
    @classmethod
    def full_check(cls) -> Tuple[Dict[str, Any], int]:
        """Run all probes concurrently and return an aggregated health report.

        Each probe is given at most ``_PROBE_TIMEOUT`` seconds.  If it does
        not finish in time its result is reported as ``"timeout"`` rather
        than blocking the entire response.

        Returns:
            (payload_dict, http_status_code)
        """
        start = time.time()
        app = current_app._get_current_object()  # noqa: WPS437 — needed for thread safety

        probes = {
            "database": cls.check_database,
            "storage": cls.check_storage,
            "cache": cls.check_cache,
            "llm": cls.check_llm,
            "external_services": cls.check_external_services,
        }

        results: Dict[str, Any] = {}

        def _run_probe(name, fn):
            """Execute a probe inside the Flask application context."""
            with app.app_context():
                return name, fn()

        with ThreadPoolExecutor(max_workers=len(probes)) as pool:
            futures = {
                pool.submit(_run_probe, name, fn): name
                for name, fn in probes.items()
            }
            for future in futures:
                name = futures[future]
                try:
                    _, result = future.result(timeout=_PROBE_TIMEOUT)
                    results[name] = result
                except FuturesTimeoutError:
                    results[name] = cls._timeout_result(name)
                except Exception as exc:
                    results[name] = {
                        "status": "unhealthy",
                        "response_time_ms": None,
                        "message": f"Probe error: {exc}",
                        "last_checked": datetime.utcnow().isoformat(),
                    }

        db_health = results["database"]
        storage_health = results["storage"]
        cache_health = results["cache"]
        llm_health = results["llm"]

        critical = [db_health, storage_health]
        all_components = critical + [llm_health]
        cache_status = cache_health["status"]

        if (
            any(c["status"] == "unhealthy" for c in critical)
            or cache_status == "unhealthy"
        ):
            overall_status = "unhealthy"
            http_status = 503
        elif any(c["status"] in ("degraded", "timeout") for c in all_components):
            overall_status = "degraded"
            http_status = 200
        elif any(c["status"] == "unhealthy" for c in all_components):
            overall_status = "unhealthy"
            http_status = 503
        else:
            overall_status = "healthy"
            http_status = 200

        elapsed = (time.time() - start) * 1000

        payload = {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": round(elapsed, 2),
            "version": app.config.get("VERSION", "unknown"),
            "components": results,
        }
        return payload, http_status
