"""Application-audit list/CSV contract; database cases use shared rollback fixtures."""
import csv
import io
import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin


@pytest.mark.parametrize('query', [
    'status=not-a-status', 'date_from=2026-02-30', 'date_to=2026-2-01',
    'date_from=2026-02-02&date_to=2026-02-01', 'date_to=9999-12-31',
    'page=0', 'page=bad', 'per_page=501', 'format=pdf',
])
def test_invalid_history_query_is_rejected_before_database_access(query):
    from app.application_mgmt.import_routes import get_import_history

    application = Flask(__name__)
    application.secret_key = 'disposable-history-validation'
    manager = LoginManager(application)

    class User(UserMixin):
        id = 41

    manager.user_loader(lambda _: User())
    application.add_url_rule('/applications/import-history', view_func=get_import_history)
    with application.test_client() as client:
        with client.session_transaction() as session:
            session['_user_id'] = '41'
        response = client.get('/applications/import-history?' + query)
    assert response.status_code == 400, response.get_json()
    assert response.get_json()['error']


@pytest.mark.parametrize('value,want', [
    ('=1+1', "'=1+1"), ('+1+1', "'+1+1"), ('-1+1', "'-1+1"), ('@SUM(A1)', "'@SUM(A1)"),
    ('  =1+1', "'  =1+1"), (' \t+1+1', "' \t+1+1"), ('\r-1+1', "'\r-1+1"),
    ('\t@SUM(A1)', "'\t@SUM(A1)"), ('\tplain text', "'\tplain text"),
    ('\rplain text', "'\rplain text"), ('ordinary.csv', 'ordinary.csv'),
])
def test_csv_formula_protection_preserves_text_and_numeric_counts(monkeypatch, value, want):
    from app.application_mgmt.import_routes import get_import_history
    from app.models import application_import_history as models
    from sqlalchemy import column

    row = SimpleNamespace(id=701, file_name=value, imported_at=datetime(2026, 2, 1),
        imported_by_name='Fixture owner', import_source='csv', status='completed',
        total_records=4, records_created=3, records_updated=1, records_skipped=0, records_failed=0)

    class Query:
        def order_by(self, *_):
            return self

        def yield_per(self, _):
            return iter([row])

    # Only persistence is doubled; the production route builds the actual CSV.
    monkeypatch.setattr(models, 'ApplicationImportHistory', SimpleNamespace(
        query=Query(), imported_at=column('imported_at'), id=column('id')))
    application = Flask(__name__)
    application.secret_key = 'disposable-history-export'
    manager = LoginManager(application)

    class User(UserMixin):
        id = 41

    manager.user_loader(lambda _: User())
    application.add_url_rule('/history', view_func=get_import_history)
    with application.test_client() as client:
        with client.session_transaction() as session:
            session['_user_id'] = '41'
        response = client.get('/history?format=csv')
    assert response.status_code == 200
    data = list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig'))))
    assert data[0]['File name'] == want
    assert data[0]['Created'] == '3'
    assert data[0]['Updated'] == '1'
    assert data[0]['Skipped'] == '0'


def test_application_audit_filters_pagination_csv_and_tenant_scope(
    app, db_session, make_org, client, login_as
):
    from app.models.application_import_history import ApplicationImportHistory
    from app.models.user import User

    org_a, org_b = make_org('history-a'), make_org('history-b')
    users = []
    for org in (org_a, org_b, org_a):
        user = User(email=f'history-{uuid.uuid4().hex}@example.com', confirmed=True,
                    organization_id=org.id, enterprise_role='enterprise_architect')
        db_session.add(user)
        users.append(user)
    db_session.flush()
    user_ids = [user.id for user in users]
    dates = [datetime(2026, 2, 1), datetime(2026, 2, 28, 23, 59, 59, 999999), datetime(2026, 3, 1)]
    rows = []
    for index, timestamp in enumerate(dates):
        row = ApplicationImportHistory(organization_id=org_a.id,
            imported_by_id=user_ids[2] if index == 0 else user_ids[0],
            imported_by_name='Fixture owner', file_name=f'fixture-{index}.csv',
            import_source='csv', status='partial', imported_at=timestamp,
            total_records=5, records_created=2, records_updated=1, records_skipped=0,
            records_failed=2, error_details='["Invalid fixture record"]')
        db_session.add(row)
        rows.append(row)
    foreign = ApplicationImportHistory(organization_id=org_b.id, imported_by_id=user_ids[1],
        file_name='foreign.csv', import_source='csv', status='partial', imported_at=dates[0])
    db_session.add(foreign)
    db_session.flush()
    ids = [row.id for row in rows]
    db_session.commit()
    db_session.expunge_all()
    login_as(client, user_ids[0])
    query = {'status': 'partial', 'date_from': '2026-02-01', 'date_to': '2026-02-28',
             'per_page': 1, 'page': 1}
    first = client.get('/dashboard/applications/import-history', query_string=query)
    assert first.status_code == 200
    data = first.get_json()
    assert data['total'] == 2
    assert data['pages'] == 2
    assert [row['id'] for row in data['history']] == [ids[1]]
    assert data['history'][0]['records_created'] == 2
    assert data['history'][0]['errors'] == ['Invalid fixture record']
    assert data['history'][0]['imported_at'].endswith('Z')
    second = client.get('/dashboard/applications/import-history', query_string=dict(query, page=2))
    assert [row['id'] for row in second.get_json()['history']] == [ids[0]]
    exported = client.get('/dashboard/applications/import-history', query_string=dict(query, format='csv'))
    assert exported.status_code == 200
    assert 'attachment' in exported.headers['Content-Disposition']
    exported_rows = list(csv.DictReader(io.StringIO(exported.data.decode('utf-8-sig'))))
    assert [row['File name'] for row in exported_rows] == ['fixture-1.csv', 'fixture-0.csv']
    assert all(row['Created'] == '2' and row['Updated'] == '1' for row in exported_rows)
    login_as(client, user_ids[1])
    other = client.get('/dashboard/applications/import-history', query_string=query)
    assert [row['file_name'] for row in other.get_json()['history']] == ['foreign.csv']
