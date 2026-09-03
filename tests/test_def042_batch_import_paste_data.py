"""DEF-042, Capgemini dry-run: the Batch Import "Paste Data" tab posts raw
CSV text as a `paste_data` form field with no `file` part at all (the
preview/cost-estimate step is entirely client-side JS parsing the same
text) -- POST /api/batch-import/jobs unconditionally required `file` in
request.files and always answered 400 "No file provided" for this path.

Fixing that surfaced a second, pre-existing bug hit by BOTH paths:
BatchImportService.estimate_cost() reads self.cost_per_app_base /
cost_capability_mapping / cost_process_classification, none of which were
ever assigned anywhere -- every job creation, file upload included, raised
AttributeError. Both tests below exercise the full create_job() path.
"""

import io

import pytest


@pytest.mark.usefixtures("db_session")
def test_create_job_via_paste_data_succeeds(app, db_session, make_org, tenant_ctx):
    from app.models.user import User
    from app.models.batch_import import BatchImportJob

    org = make_org("def042-batch-paste")
    with tenant_ctx(org.id):
        user = User(email=f"def042-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.post(
                "/api/batch-import/jobs",
                data={
                    "name": "ZZ-VERIFY paste import",
                    "archimate_mode": "quick",
                    "batch_size": "20",
                    "ai_generation": "false",
                    "auto_commit": "false",
                    "source_type": "paste",
                    "paste_data": "name,description,vendor,technology\n"
                                  "ZZ-VERIFY App,test app,Acme,Python\n",
                },
                content_type="multipart/form-data",
            )
            body = resp.get_data(as_text=True)
            assert resp.status_code in (200, 201), body
            assert "No file provided" not in body

            data = resp.get_json()
            assert data.get("success") is not False
            job_id = data.get("job_id") or (data.get("data") or {}).get("id") or (data.get("job") or {}).get("id")
            assert job_id is not None
            job = db_session.get(BatchImportJob, job_id)
            assert job is not None


@pytest.mark.usefixtures("db_session")
def test_create_job_via_file_upload_still_works(app, db_session, make_org, tenant_ctx):
    """The file-upload path hit the same estimate_cost() AttributeError as
    the paste path -- confirm it's fixed too, not just the paste branch."""
    from app.models.user import User
    from app.models.batch_import import BatchImportJob

    org = make_org("def042-batch-file")
    with tenant_ctx(org.id):
        user = User(email=f"def042file-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            csv_bytes = b"name,description,vendor,technology\nZZ-VERIFY App2,test app,Acme,Python\n"
            resp = c.post(
                "/api/batch-import/jobs",
                data={
                    "name": "ZZ-VERIFY file import",
                    "archimate_mode": "quick",
                    "batch_size": "20",
                    "ai_generation": "false",
                    "auto_commit": "false",
                    "source_type": "file",
                    "file": (io.BytesIO(csv_bytes), "zz_verify.csv"),
                },
                content_type="multipart/form-data",
            )
            body = resp.get_data(as_text=True)
            assert resp.status_code in (200, 201), body
            assert "cost_per_app_base" not in body

            data = resp.get_json()
            assert data.get("success") is not False
            job_id = data.get("job_id") or (data.get("data") or {}).get("id") or (data.get("job") or {}).get("id")
            assert job_id is not None
            job = db_session.get(BatchImportJob, job_id)
            assert job is not None
