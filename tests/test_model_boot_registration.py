"""Cold-boot model-registration contracts.

Gunicorn workers can serve concurrent requests immediately after the app
factory returns.  Models whose relationships use string targets must therefore
be fully registered before that point; a request-time partial import can poison
SQLAlchemy's mapper registry for the lifetime of the worker.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def test_vendor_catalogue_models_are_registered_during_cold_boot():
    """The app factory must register the complete vendor catalogue graph."""

    script = textwrap.dedent(
        """
        import app.models
        from app import db

        registry = db.Model.registry._class_registry
        required = {
            "VendorProductFamily",
            "VendorProductDetail",
            "VendorProductAlias",
        }
        missing = sorted(required.difference(registry))
        if missing:
            raise SystemExit(f"models missing after create_app: {missing}")
        """
    )
    env = os.environ.copy()
    env["APP_FAST_INIT"] = "0"
    env["FLASK_CONFIG"] = "testing"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_vendor_mapping_uses_the_canonical_application_product_aggregate(monkeypatch):
    """Legacy service inputs must be translated onto the canonical mapping."""

    from app.models.vendor import vendor_product as model_module
    from app.modules.vendors.services import vendor_product_service as service_module

    created = []

    class FakeMapping:
        query = SimpleNamespace(
            filter_by=lambda **criteria: SimpleNamespace(first=lambda: None)
        )

        def __init__(self, **values):
            self.id = 42
            self.__dict__.update(values)
            created.append(self)

    fake_session = SimpleNamespace(
        add=lambda mapping: None,
        commit=lambda: None,
        rollback=lambda: None,
    )
    monkeypatch.setattr(model_module, "ApplicationVendorProductMapping", FakeMapping)
    monkeypatch.setattr(service_module, "db", SimpleNamespace(session=fake_session))

    result = service_module.VendorProductService().create_vendor_product_mapping(
        application_id=11,
        vendor_product_id=22,
        confidence_score=0.91,
        mapping_method="ai_extracted",
        deployment_type="Production",
        version_deployed="2026.3",
        license_type="enterprise",
        user_id=7,
    )

    assert result == {"success": True, "mapping_id": 42, "confidence_score": 0.91}
    mapping = created[0]
    assert mapping.application_component_id == 11
    assert mapping.vendor_product_id == 22
    assert mapping.product_version == "2026.3"
    assert mapping.deployment_model == "production"
    assert (
        mapping.mapping_notes
        == '{"confidence_score": 0.91, "created_by_id": 7, '
        '"license_type": "enterprise", "mapping_method": "ai_extracted"}'
    )
