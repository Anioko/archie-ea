"""Application import controls must work under the strict CSP in every browser."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_drop_zone_uses_external_event_listeners_not_inline_handlers():
    template = (
        ROOT / "app" / "templates" / "application_mgmt" / "application_import_modal.html"
    ).read_text(encoding="utf-8")
    script = (
        ROOT / "app" / "static" / "js" / "application_mgmt" / "application_import.js"
    ).read_text(encoding="utf-8")

    for attribute in ("ondragover=", "ondragleave=", "ondrop="):
        assert attribute not in template
    for event in ("dragover", "dragleave", "drop"):
        assert f"addEventListener('{event}'" in script
