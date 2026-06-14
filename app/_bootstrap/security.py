"""
Security headers and middleware — called after extensions init.
"""

import os
import re
import secrets
import time


# Compiled regex: matches <script followed by whitespace or > (actual HTML script tags)
_SCRIPT_TAG_RE = re.compile(r"<script(?=[\s>])", re.IGNORECASE)


def init_security(app):
    """Register security headers and guardrails."""

    @app.before_request
    def generate_csp_nonce():
        """Generate a unique CSP nonce per request for script-src."""
        from flask import g

        g.csp_nonce = secrets.token_urlsafe(32)

    @app.context_processor
    def inject_csp_nonce():
        """Expose csp_nonce to all templates (for manual use if needed)."""
        from flask import g

        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.after_request
    def add_security_headers(response):
        from flask import g

        nonce = getattr(g, "csp_nonce", "")

        # Inject nonce into all <script> tags in HTML responses (including error pages)
        if response.content_type and "text/html" in response.content_type:
            data = response.get_data(as_text=True)
            if nonce:
                data = _SCRIPT_TAG_RE.sub(f'<script nonce="{nonce}"', data)
            response.set_data(data)
            # set_data stores uncompressed — remove stale encoding/length headers
            response.headers.pop("Content-Encoding", None)
            response.headers.pop("Content-Length", None)

        # Standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        if getattr(g, "allow_framing", False):
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        else:
            response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "same-origin"

        # Content-Security-Policy
        # Development: permissive — allow CDN scripts (Alpine.js, Lucide, DOMPurify) + unsafe-inline
        # Production: nonce-based strict policy
        # NOTE: 'strict-dynamic' must NOT be used in dev — it overrides CDN host allowlists
        # and blocks Alpine.js/Lucide/DOMPurify which are loaded from unpkg/jsdelivr without nonces.
        from flask import current_app as _app

        if _app.debug:
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
                "https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
                "https://d3js.org https://cdn.segment.com https://www.google-analytics.com "
                "https://esm.sh",
                "style-src 'self' 'unsafe-inline' "
                "https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
                "https://fonts.googleapis.com",
                "font-src 'self' data: https://fonts.googleapis.com https://fonts.gstatic.com https://cdn.jsdelivr.net",
                "connect-src 'self' https://unpkg.com https://cdn.jsdelivr.net https://cdn.segment.com https://www.google-analytics.com https://esm.sh ws://localhost:* wss://localhost:*",
                "img-src 'self' data: blob: https://api.qrserver.com",
                "frame-src 'self' https://snack.expo.dev",
                "object-src 'none'",
                "report-uri /api/csp-report",
            ]
        else:
            csp_directives = [
                "default-src 'self'",
                f"script-src 'self' 'nonce-{nonce}' 'unsafe-eval' 'strict-dynamic' "
                "https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
                "https://d3js.org https://cdn.segment.com https://www.google-analytics.com "
                "https://esm.sh",  # CodeMirror 6 ES module imports
                "style-src 'self' 'unsafe-inline' "
                "https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
                "https://fonts.googleapis.com",
                "font-src 'self' data: https://fonts.googleapis.com https://fonts.gstatic.com https://cdn.jsdelivr.net",
                "connect-src 'self' https://cdn.jsdelivr.net https://unpkg.com https://cdn.segment.com https://www.google-analytics.com "
                "https://esm.sh",  # CodeMirror 6 ES module imports
                "img-src 'self' data: blob: https://api.qrserver.com",
                "frame-src 'self' https://snack.expo.dev",
                "object-src 'none'",
                "report-uri /api/csp-report",
            ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Cache-Control headers (T-033) — vary by content type
        if response.content_type:
            ct = response.content_type
            request_path = ""
            try:
                from flask import request as _req

                request_path = _req.path
            except RuntimeError:
                pass

            if request_path.startswith("/static/"):
                # Fingerprinted static assets: cache aggressively (1 year)
                response.headers["Cache-Control"] = (
                    "public, max-age=31536000, immutable"
                )
            elif "text/html" in ct:
                # HTML pages: always revalidate
                response.headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
            elif "application/json" in ct or request_path.startswith("/api/"):
                # API responses: never cache
                response.headers["Cache-Control"] = "no-store"

        return response

    # Wire MetricsCollector to request pipeline for automatic tracking
    try:
        from flask import g, request as flask_request
        from app.core.observability.metrics import metrics_collector

        @app.before_request
        def _metrics_start():
            g._metrics_start = time.monotonic()

        @app.after_request
        def _metrics_record(response):
            start = getattr(g, "_metrics_start", None)
            if start is not None:
                duration_ms = (time.monotonic() - start) * 1000
                metrics_collector.record(
                    flask_request.endpoint, response.status_code, duration_ms
                )
            return response

        app.logger.info("MetricsCollector wired to request pipeline")
    except Exception as e:
        app.logger.warning(f"MetricsCollector wiring failed (non-critical): {e}")

    # Batch import configuration (kept — used by import routes)
    app.config["MAX_CONCURRENT_BATCH_JOBS"] = 3
    app.config["BATCH_COMMIT_FAILURE_THRESHOLD"] = 0.5
    app.config["BATCH_RECOVERY_ENABLED"] = True
    app.config["BATCH_PROCESSING_TIMEOUT_MINUTES"] = 30
    app.config["BATCH_JOB_TIMEOUT_HOURS"] = 24

    # Initialize guardrails for AI safety
    try:
        from app.guardrails import GuardrailEnforcement

        _guardrail = GuardrailEnforcement(app)  # noqa: F841
        app.logger.info("Guardrail enforcement initialized successfully")
    except Exception as e:
        app.logger.warning(f"Guardrail initialization failed (non-critical): {e}")

    # Seed default AI prompt templates (non-critical)
    try:
        from app.services.ai_prompt_seeder import seed_default_ai_prompt_templates

        with app.app_context():
            seed_default_ai_prompt_templates()
        app.logger.info("AI prompt templates seeded (if missing).")
    except Exception as e:
        app.logger.warning(f"AI prompt seeding failed (non-critical): {e}")

    # DEV bootstrap for vendor catalog dev surface (dev only)
    try:
        if os.environ.get("DEV_VEND_CATALOG", "0") == "1":
            from app.extensions.vendor_catalog_bootstrap import bootstrap_vendor_catalog

            bootstrap_vendor_catalog(app)
            app.logger.info(
                "[DEV] Vendor Catalog bootstrap executed (DEV_VEND_CATALOG)"
            )
        else:
            app.logger.info(
                "[DEV] Vendor Catalog bootstrap skipped (DEV_VEND_CATALOG not set)"
            )
    except Exception as e:
        app.logger.warning(f"[DEV] Vendor Catalog bootstrap failed: {e}")
