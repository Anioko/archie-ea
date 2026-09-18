"""T-001 acceptance criteria 14 and 16: non-fatal registration, nothing mounted.

Deliberately does NOT call ``create_app()`` a second time in this process:
``tests/test_boot_health.py`` documents that a second boot raises "can no
longer be called on the blueprint" for an unrelated blueprint
(``app/modules/codegen/services/sap_importer.py`` attaches routes after
registration), which would make this file's result depend on run order
rather than on the behaviour under test. Instead this exercises
``app._bootstrap.blueprints._register_intelligence`` directly against a
minimal stub app object — the same try/except path a real boot runs through,
without re-invoking ``create_app()``.

Mapping:
    14 -> test_registration_succeeds_when_module_is_importable,
          test_registration_is_non_fatal_when_import_is_forced_to_raise
    16 -> test_register_mounts_no_blueprint_and_no_route
"""

from __future__ import annotations

import sys


class _StubLogger:
    def __init__(self):
        self.warnings = []
        self.infos = []

    def warning(self, msg, *args):
        self.warnings.append(msg % args if args else msg)

    def error(self, msg, *args):
        self.warnings.append(msg % args if args else msg)

    def info(self, msg, *args):
        self.infos.append(msg % args if args else msg)


class _StubApp:
    def __init__(self):
        self.blueprints = {}
        self.logger = _StubLogger()

    def register_blueprint(self, bp, **kwargs):
        self.blueprints[bp.name] = bp


def test_register_mounts_no_blueprint_and_no_route():
    """T-001 mounts nothing: register(app) is a placeholder for T-003/T-004."""
    from app.modules.intelligence import register

    stub = _StubApp()
    register(stub)
    assert stub.blueprints == {}


def test_registration_succeeds_when_module_is_importable():
    sys.modules.pop("app.modules.intelligence", None)  # force a fresh import
    from app._bootstrap.blueprints import _register_intelligence

    stub = _StubApp()
    _register_intelligence(stub)

    assert stub.blueprints == {}, "T-001 mounts nothing yet"
    assert stub.logger.warnings == [], "a clean import/register must not warn"
    assert any("intelligence" in msg.lower() for msg in stub.logger.infos)


def test_registration_is_non_fatal_when_import_is_forced_to_raise(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.modules.intelligence", None)
    from app._bootstrap.blueprints import _register_intelligence

    stub = _StubApp()
    _register_intelligence(stub)  # must not raise

    assert stub.blueprints == {}
    assert any("intelligence" in msg.lower() for msg in stub.logger.warnings), (
        "a forced import failure must be logged as a warning, not swallowed silently"
    )
