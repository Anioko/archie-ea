"""Malformed picker limits must not reach PostgreSQL as negative LIMITs."""

from types import SimpleNamespace

from flask import Flask
import pytest
from sqlalchemy import column


@pytest.mark.parametrize("raw,want", [("-1", 1), ("0", 1), ("abc", 25), ("", 25),
                                       ("1.5", 25), ("99999999999999999999", 100), ("7", 7)])
@pytest.mark.parametrize("filters", [{}, {"q": "Fixture"}, {"types": "ApplicationComponent"},
                                     {"type": "application_component", "layer": "application"}])
def test_registered_elements_route_returns_bounded_page(monkeypatch, raw, want, filters):
    from app.api import archimate_generation_routes as module
    from app.modules.architecture.services import archimate_core_service as service_module

    class ElementQuery:
        size = None
        def filter(self, *criteria):
            return self
        def order_by(self, *columns):
            return self
        def filter_by(self, **criteria):
            return self
        def limit(self, size):
            self.size = size
            return self
        def all(self):
            if self.size is not None and self.size < 0:
                raise ValueError("LIMIT must not be negative")
            return [SimpleNamespace(id=index, name=f"Fixture {index}", type="ApplicationComponent",
                                    layer="application", description="Fixture")
                    for index in range(min(self.size, 120) if self.size is not None else 120)]

    monkeypatch.setattr(module, "ArchiMateElement", SimpleNamespace(
        query=ElementQuery(), name=column("name"), type=column("type"), layer=column("layer")))
    monkeypatch.setattr(service_module, "ArchiMateElement", module.ArchiMateElement)
    # Exercise the real typed-query method; its constructor's generation engine
    # is unrelated to read-only pagination and does not need initializing.
    service = service_module.ArchiMateService.__new__(service_module.ArchiMateService)
    monkeypatch.setattr(module, "_archimate_service", lambda: service)
    app = Flask(__name__)
    app.config.update(TESTING=True, LOGIN_DISABLED=True)
    app.register_blueprint(module.archimate_generation_bp)
    response = app.test_client().get("/api/archimate/elements", query_string={"limit": raw, **filters})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["count"] == want
    assert len(payload["data"]) == want
    assert payload["data"][0]["name"] == "Fixture 0"
