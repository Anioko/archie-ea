"""Real authenticated BatchJob list route with a disclosed query boundary double.

These verify HTTP/JSON validation and emitted predicates; PostgreSQL execution
and tenant/user visibility are covered separately in the database module.
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin


@pytest.fixture
def batch_api(monkeypatch):
    from app.api import import_history_routes as routes
    from app.models.batch_processing import BatchJob, BatchJobStatus, BatchJobType

    job = SimpleNamespace(
        id=701, job_name="Mapped enum fixture", job_type=BatchJobType.AI_IMPORT,
        status=BatchJobStatus.COMPLETED, total_items=4, processed_items=4,
        successful_items=4, failed_items=0, created_at=None, completed_at=None,
        progress_percentage=Decimal("100.00"),
    )
    state = SimpleNamespace(predicates=[], filters={}, queried=False, job=job, total=43)

    class Query:
        def filter_by(self, **kwargs):
            state.queried = True
            state.filters.update(kwargs)
            return self

        def filter(self, *predicates):
            state.predicates.extend(predicates)
            return self

        def order_by(self, *_):
            return self

        def paginate(self, **kwargs):
            state.pagination = kwargs
            return SimpleNamespace(items=[job], total=state.total)

    monkeypatch.setattr(routes, "BatchJob", SimpleNamespace(
        query=Query(), created_at=BatchJob.created_at, id=BatchJob.id,
    ))
    monkeypatch.setattr(routes, "BatchProcessingService", lambda: None)
    application = Flask(__name__)
    application.secret_key = "disposable-test-only"
    manager = LoginManager(application)

    class User(UserMixin):
        id = 41

    manager.user_loader(lambda _: User())
    application.register_blueprint(routes.import_history_bp)
    with application.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = "41"
            session["_fresh"] = True
        yield client, state


def test_endpoint_serializes_real_batch_job_enums_without_database(batch_api):
    client, state = batch_api
    response = client.get("/api/import-history?per_page=1&page=2")
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["jobs"][0]["status"] == "completed"
    assert body["jobs"][0]["job_type"] == "ai_import"
    assert body["jobs"][0]["progress"] == 100
    assert body["total"] == 43
    assert body["page"] == 2
    assert body["per_page"] == 1
    assert state.filters["created_by_id"] == 41


def test_unknown_progress_is_not_reported_as_measured_zero(batch_api):
    client, state = batch_api
    state.job.progress_percentage = None
    response = client.get("/api/import-history")
    assert response.status_code == 200
    assert response.get_json()["jobs"][0]["progress"] is None


@pytest.mark.parametrize("status", ["completed", "COMPLETED", " Completed "])
def test_status_converted_to_mapped_enum(batch_api, status):
    from app.models.batch_processing import BatchJobStatus

    client, state = batch_api
    response = client.get("/api/import-history", query_string={"status": status})
    assert response.status_code == 200
    assert state.filters["status"] is BatchJobStatus.COMPLETED


@pytest.mark.parametrize("filters", [
    {"status": "partial"}, {"status": "invented"},
    {"date_from": "2026-02-30"}, {"date_to": "2026-13-01"},
    {"date_from": "2026-1-01"}, {"date_to": "20260905"},
    {"date_to": "2026-09-05T12:00:00Z"}, {"date_from": "not-a-date"},
    {"date_from": "2026-09-06", "date_to": "2026-09-05"},
    {"date_to": "9999-12-31"},
])
def test_invalid_filter_is_400_before_query(batch_api, filters):
    client, state = batch_api
    response = client.get("/api/import-history", query_string=filters)
    assert response.status_code == 400, response.get_json()
    assert response.get_json()["success"] is False
    assert response.get_json()["error"]
    assert state.queried is False


def test_date_predicates_cover_complete_utc_days(batch_api):
    client, state = batch_api
    response = client.get("/api/import-history", query_string={
        "date_from": "2026-01-01", "date_to": "2026-01-31",
    })
    assert response.status_code == 200
    assert len(state.predicates) == 2
    start, end = state.predicates
    assert str(start).startswith("batch_jobs.created_at >=")
    assert list(start.compile().params.values()) == [datetime(2026, 1, 1)]
    assert str(end).startswith("batch_jobs.created_at <")
    assert list(end.compile().params.values()) == [datetime(2026, 2, 1)]


def test_unauthenticated_request_cannot_query_history(batch_api):
    client, state = batch_api
    with client.session_transaction() as session:
        session.clear()
    response = client.get("/api/import-history")
    assert response.status_code == 401
    assert state.queried is False
