"""Actual PostgreSQL BatchJob list filtering, pagination and ownership isolation.

All synthetic rows use the shared rollback fixture. No import, retry, export or
rollback endpoint is invoked; no production database is used.
"""

import os
import uuid
from datetime import datetime

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Batch history integration requires explicit TEST_DATABASE_URL",
)


@pytest.fixture
def batch_history(db_session, make_org):
    from app.models.batch_processing import BatchJob, BatchJobStatus, BatchJobType
    from app.models.user import Permission, Role, User

    assert db_session.get_bind().dialect.name == "postgresql"
    assert db_session.get_bind(mapper=BatchJob) is db_session.get_bind()
    assert db_session.get_bind().in_transaction()
    org, other_org = make_org("batch-history"), make_org("batch-foreign")
    suffix = uuid.uuid4().hex
    role = Role(name="Batch history reader " + suffix, permissions=Permission.GENERAL)
    db_session.add(role)

    def user(label, organization):
        row = User(email=f"batch-{label}-{suffix}@example.com", role=role,
                   organization_id=organization.id, confirmed=True,
                   enterprise_role="enterprise_architect")
        db_session.add(row)
        db_session.flush()
        return row

    owner = user("owner", org)
    colleague = user("colleague", org)
    foreign = user("foreign", other_org)

    def job(name, timestamp, status=BatchJobStatus.COMPLETED, creator=None):
        row = BatchJob(
            job_name=name, job_type=BatchJobType.AI_IMPORT, status=status,
            created_by_id=(creator or owner).id, created_at=timestamp,
            total_items=4, processed_items=4, successful_items=3, failed_items=1,
            progress_percentage=100,
        )
        db_session.add(row)
        db_session.flush()
        return row

    job("before", datetime(2025, 12, 31, 23, 59, 59, 999999))
    job("start", datetime(2026, 1, 1))
    job("middle", datetime(2026, 1, 10, 12))
    job("failed", datetime(2026, 1, 15), BatchJobStatus.FAILED)
    job("end", datetime(2026, 1, 31, 23, 59, 59, 999999))
    job("after", datetime(2026, 2, 1))
    job("colleague-private", datetime(2026, 1, 20), creator=colleague)
    job("foreign-private", datetime(2026, 1, 20), creator=foreign)
    return owner, job


@pytest.mark.parametrize("filters,expected", [
    ({}, ["after", "end", "failed", "middle", "start", "before"]),
    ({"status": "failed"}, ["failed"]),
    ({"date_from": "2026-01-01"}, ["after", "end", "failed", "middle", "start"]),
    ({"date_to": "2026-01-31"}, ["end", "failed", "middle", "start", "before"]),
    ({"date_from": "2026-01-01", "date_to": "2026-01-31"},
     ["end", "failed", "middle", "start"]),
    ({"date_from": "2026-01-01", "date_to": "2026-01-01"}, ["start"]),
    ({"status": "COMPLETED", "date_from": "2026-01-01", "date_to": "2026-01-31"},
     ["end", "middle", "start"]),
    ({"status": "", "date_from": "", "date_to": ""},
     ["after", "end", "failed", "middle", "start", "before"]),
    ({"date_from": "2027-01-01"}, []),
])
def test_persisted_filters_and_owner_scope(batch_history, client, login_as, filters, expected):
    owner, _ = batch_history
    login_as(client, owner)
    response = client.get("/api/import-history", query_string=filters)
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    assert [row["job_name"] for row in data["jobs"]] == expected
    assert data["total"] == len(expected)
    assert all(row["job_type"] == "ai_import" for row in data["jobs"])
    assert all(isinstance(row["progress"], (int, float)) for row in data["jobs"])


@pytest.mark.parametrize("page,expected", [(1, ["end"]), (2, ["middle"]), (4, [])])
def test_filter_before_pagination_and_true_total(batch_history, client, login_as, page, expected):
    owner, _ = batch_history
    login_as(client, owner)
    response = client.get("/api/import-history", query_string={
        "status": "completed", "date_from": "2026-01-01", "date_to": "2026-01-31",
        "page": page, "per_page": 1,
    })
    assert response.status_code == 200
    data = response.get_json()
    assert [row["job_name"] for row in data["jobs"]] == expected
    assert data["total"] == 3
    assert data["page"] == page
    assert data["per_page"] == 1


@pytest.mark.parametrize("status", [
    "pending", "running", "paused", "completed", "failed", "cancelled", "recovering",
])
def test_each_real_postgres_enum_status_is_filterable(batch_history, client, login_as, status):
    from app.models.batch_processing import BatchJobStatus

    owner, make_job = batch_history
    make_job("enum-probe", datetime(2026, 3, 1), BatchJobStatus(status))
    login_as(client, owner)
    response = client.get("/api/import-history", query_string={
        "status": status, "date_from": "2026-03-01", "date_to": "2026-03-01",
    })
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    assert [row["job_name"] for row in data["jobs"]] == ["enum-probe"]
    assert data["jobs"][0]["status"] == status


def test_timestamp_ties_paginate_stably(batch_history, client, login_as):
    owner, make_job = batch_history
    earlier = make_job("tie-first", datetime(2026, 4, 1))
    later = make_job("tie-second", datetime(2026, 4, 1))
    seen = []
    for page in (1, 2):
        login_as(client, owner)
        response = client.get("/api/import-history", query_string={
            "date_from": "2026-04-01", "date_to": "2026-04-01",
            "per_page": 1, "page": page,
        })
        assert response.status_code == 200
        assert response.get_json()["total"] == 2
        seen.extend(row["id"] for row in response.get_json()["jobs"])
    assert seen == [later.id, earlier.id]
