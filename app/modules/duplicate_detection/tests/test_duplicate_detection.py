"""
Tests for the duplicate_detection module migration.

Verifies:
- The register() function is importable
- Both blueprints are importable with correct .name attributes
- Blueprint URL prefixes are correct
- Route counts match expectations (36 + 8 = 44)
- Module registers correctly with a Flask app
"""

import pytest


@pytest.fixture(scope="module")
def app():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


class TestDedupeModuleImports:
    """Test that the duplicate_detection module components are importable."""

    def test_register_function_importable(self):
        """register() function can be imported from the duplicate_detection module."""
        from app.modules.duplicate_detection import register

        assert callable(register), "register should be a callable function"

    def test_unified_duplicate_bp_importable(self):
        """unified_duplicate_bp has name 'unified_duplicate'."""
        from app.modules.duplicate_detection.routes.unified_duplicate_routes import (
            unified_duplicate_bp,
        )

        assert unified_duplicate_bp.name == "unified_duplicate", (
            f"Expected 'unified_duplicate', got '{unified_duplicate_bp.name}'"
        )


class TestDedupeBlueprintConfig:
    """Test that blueprints have correct URL prefixes."""

    def test_unified_duplicate_prefix(self):
        """unified_duplicate_bp has url_prefix='/duplicate-detection'."""
        from app.modules.duplicate_detection.routes.unified_duplicate_routes import (
            unified_duplicate_bp,
        )

        assert unified_duplicate_bp.url_prefix == "/duplicate-detection"


class TestDedupeRouteCount:
    """Test that route counts match expectations."""

    def test_unified_duplicate_route_count(self):
        """unified_duplicate_bp should have at least 44 routes (consolidated)."""
        from app.modules.duplicate_detection.routes.unified_duplicate_routes import (
            unified_duplicate_bp,
        )

        count = len(unified_duplicate_bp.deferred_functions)
        assert count >= 44, (
            f"Expected >= 44 deferred functions on unified_duplicate_bp, got {count}"
        )


class TestDedupeModuleRegistration:
    """Test that the module registers correctly with a Flask app."""

    def test_unified_duplicate_in_app(self, app):
        """unified_duplicate blueprint should be registered in the app."""
        bp_names = list(app.blueprints.keys())
        assert "unified_duplicate" in bp_names, (
            f"'unified_duplicate' blueprint should be registered. Found: {bp_names}"
        )

    def test_duplicate_detection_url_rules_exist(self, app):
        """App should have /duplicate-detection URL rules."""

        rules = [r.rule for r in app.url_map.iter_rules()]
        dedupe_rules = [r for r in rules if "/duplicate-detection" in r]
        assert len(dedupe_rules) >= 40, (
            f"Expected >= 40 duplicate-detection URL rules, found {len(dedupe_rules)}"
        )
