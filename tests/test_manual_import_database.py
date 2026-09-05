"""Real PostgreSQL manual-import boundary and ownership regressions.

Only explicit TEST_DATABASE_URL is used; shared db_session rolls back every row.
"""
import json
import os
from types import SimpleNamespace
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get('TEST_DATABASE_URL'),
    reason='Manual import requires an explicit disposable PostgreSQL TEST_DATABASE_URL',
)
@pytest.fixture(params=['/dashboard/applications/import-manual', '/applications/import-manual'])
def import_path(request):
    return request.param


@pytest.fixture
def batch(db_session, make_org):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.user import Permission, Role, User

    assert db_session.get_bind().dialect.name == 'postgresql'
    assert db_session.get_bind().in_transaction()
    suffix = uuid.uuid4().hex
    owner, foreign = make_org('manual-owner'), make_org('manual-foreign')
    role = Role(name='Manual import writer ' + suffix, permissions=Permission.GENERAL)
    user = User(email=f'manual-{suffix}@example.com', role=role, confirmed=True,
                organization_id=owner.id, enterprise_role='application_manager')
    db_session.add_all([role, user])
    rows = [ApplicationComponent(name=f'Manual {index} {suffix}', description='Original',
                                 organization_id=organization.id)
            for index, organization in enumerate((owner, owner, foreign))]
    db_session.add_all(rows)
    # Commit (RELEASE SAVEPOINT under the shared fixture) so a handler's
    # db.session.rollback() unwinds only its own writes, not this fixture's
    # rows; the outer connection transaction still discards everything.
    db_session.commit()
    return SimpleNamespace(user=user, org_id=owner.id, foreign_org_id=foreign.id,
                           ids=[row.id for row in rows], names=[row.name for row in rows],
                           mirrors=[row.archimate_element_id for row in rows], suffix=suffix)


def snapshot(db_session, batch):
    """Table reads avoid request-tenant filters and identity-map false positives."""
    from sqlalchemy import select
    from app.models.application_portfolio import ApplicationComponent
    from app.models.application_import_history import ApplicationImportHistory
    from app.models.archimate_core import ArchiMateElement

    result = {}
    for model in (ApplicationComponent, ApplicationImportHistory, ArchiMateElement):
        table = model.__table__
        result[table.name] = [dict(row) for row in db_session.execute(
            select(table).where(table.c.organization_id.in_([batch.org_id, batch.foreign_org_id]))
            .order_by(table.c.id)).mappings()]
    from app.models.import_audit import ImportSessionLog
    table = ImportSessionLog.__table__
    result['import_audit_log'] = [dict(row) for row in db_session.execute(
        select(table).where(table.c.user_id == batch.user.id).order_by(table.c.id)).mappings()]
    return result


@pytest.mark.parametrize('mode', ['merge', 'update', 'skip', 'duplicate'])
@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('attack', ['foreign_org', 'primary_key', 'same_mirror', 'foreign_mirror',
                                   'audit', 'relationship'])
def test_protected_fields_cannot_mutate_rows(batch, db_session, client, login_as, mode, existing, attack, import_path):
    payload = {'name': batch.names[0] if existing else 'New ' + batch.suffix}
    payload.update({
        'foreign_org': {'organization_id': batch.foreign_org_id},
        'primary_key': {'id': 2147483647},
        'same_mirror': {'archimate_element_id': batch.mirrors[1]},
        'foreign_mirror': {'archimate_element_id': batch.mirrors[2]},
        'audit': {'deleted_at': '2026-01-01'},
        'relationship': {'organization': {'id': batch.foreign_org_id}},
    }[attack])
    before = snapshot(db_session, batch)
    login_as(client, batch.user)
    response = client.post(import_path, json={'applications': [payload], 'duplicate_mode': mode})
    assert response.status_code == 400, response.get_json()
    assert response.get_json()['error']
    assert snapshot(db_session, batch) == before


@pytest.mark.parametrize('invalid', [None, [], 'text', {'name': []}, {'name': True},
                                    {'name': 'B', 'description': {}},
                                    {'name': 'B', 'application_code': 'a', 'app_id': 'b'}])
def test_invalid_later_row_never_commits_valid_prefix(batch, db_session, client, login_as, invalid, import_path):
    before = snapshot(db_session, batch)
    login_as(client, batch.user)
    response = client.post(import_path, json={'applications': [{'name': 'New ' + batch.suffix}, invalid]})
    assert response.status_code == 400
    assert snapshot(db_session, batch) == before


def test_create_then_ui_merge_preserves_ownership_and_mirror(batch, db_session, client, login_as, import_path):
    name, code = 'New ' + batch.suffix, 'APP-' + batch.suffix
    before = snapshot(db_session, batch)
    login_as(client, batch.user)
    response = client.post(import_path, json={'applications': [{
        'name': name, 'app_id': code, 'component_type': 'ERP',
        'deployment_status': 'planned', 'description': 'First description'}]})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['created'] == 1
    created = snapshot(db_session, batch)
    row = next(row for row in created['application_components'] if row['name'] == name)
    assert row['organization_id'] == batch.org_id
    assert row['application_code'] == code
    mirror = next(element for element in created['archimate_elements']
                  if element['id'] == row['archimate_element_id'])
    assert mirror['organization_id'] == batch.org_id
    assert mirror['id'] not in batch.mirrors
    assert len(created['archimate_elements']) == len(before['archimate_elements']) + 1
    login_as(client, batch.user)
    response = client.post(import_path, json={'applications': [{'name': name, 'description': 'Changed'}],
                                      'duplicate_mode': 'update'})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['updated'] == 1
    assert response.get_json()['created'] == 0
    merged = snapshot(db_session, batch)
    updated = next(item for item in merged['application_components'] if item['id'] == row['id'])
    assert updated['organization_id'] == batch.org_id
    assert updated['archimate_element_id'] == mirror['id']
    assert updated['description'] == 'Changed'
    assert updated['application_code'] == code
    assert len(merged['archimate_elements']) == len(created['archimate_elements'])
    history = merged['application_import_history'][-1]
    assert history['organization_id'] == batch.org_id
    assert json.loads(history['import_settings'])['linked_applications']['updated_ids'] == [row['id']]


@pytest.mark.parametrize('mode', ['merge', 'skip', 'duplicate'])
def test_legitimate_duplicate_modes(batch, db_session, client, login_as, mode, import_path):
    before = snapshot(db_session, batch)
    login_as(client, batch.user)
    response = client.post(import_path, json={'applications': [{'name': batch.names[0], 'description': 'Changed'}],
                                      'duplicate_mode': mode})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()[{'merge': 'updated', 'skip': 'skipped', 'duplicate': 'created'}[mode]] == 1
    after = snapshot(db_session, batch)
    row = next(row for row in after['application_components'] if row['id'] == batch.ids[0])
    assert row['description'] == ('Changed' if mode == 'merge' else 'Original')
    assert row['organization_id'] == batch.org_id
    assert row['archimate_element_id'] == batch.mirrors[0]
    assert len(after['application_components']) == len(before['application_components']) + (mode == 'duplicate')


@pytest.mark.parametrize('mode', ['merge', 'update', 'skip', 'duplicate'])
def test_duplicate_names_in_one_batch_honor_selected_mode(batch, db_session, client, login_as, mode, import_path):
    name = 'In-batch ' + batch.suffix
    before = snapshot(db_session, batch)
    login_as(client, batch.user)
    response = client.post(import_path, json={'applications': [
        {'name': name, 'description': 'First'}, {'name': name, 'description': 'Second'},
    ], 'duplicate_mode': mode})
    assert response.status_code == 200, response.get_json()
    expected_count = 2 if mode == 'duplicate' else 1
    assert response.get_json()['created'] == expected_count
    assert response.get_json()['updated'] == (1 if mode in ('merge', 'update') else 0)
    assert response.get_json()['skipped'] == (1 if mode == 'skip' else 0)
    after = snapshot(db_session, batch)
    rows = [row for row in after['application_components'] if row['name'] == name]
    assert len(rows) == expected_count
    assert [row['description'] for row in rows] == (
        ['First', 'Second'] if mode == 'duplicate' else ['First'] if mode == 'skip' else ['Second'])
    assert all(row['organization_id'] == batch.org_id for row in rows)
    assert len(after['archimate_elements']) == len(before['archimate_elements']) + expected_count
    links = json.loads(after['application_import_history'][-1]['import_settings'])['linked_applications']
    assert links['created_ids'] == [row['id'] for row in rows]
    assert links['updated_ids'] == []


def test_rich_manual_dates_numbers_booleans_and_both_audits(batch, db_session, client, login_as):
    from datetime import date
    from sqlalchemy import select
    from app.models.import_audit import ImportSessionLog

    login_as(client, batch.user)
    response = client.post('/applications/import-manual', json={'date_format': 'dmy', 'applications': [{
        'name': batch.names[0], 'implementation_date': '05/09/2026', 'user_count': '12',
        'license_cost': 100.25, 'encryption_at_rest': False, 'notes': 'Import note',
        'last_backup_date': 'not a date',
    }]})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['skipped_fields'][0]['field'] == 'last_backup_date'
    after = snapshot(db_session, batch)
    row = next(row for row in after['application_components'] if row['id'] == batch.ids[0])
    assert row['implementation_date'] == date(2026, 9, 5)
    assert row['user_count'] == 12
    assert row['license_cost'] == 100.25
    assert row['encryption_at_rest'] is False
    assert row['notes'] == 'Import note'
    history = after['application_import_history'][-1]
    assert history['records_updated'] == 1
    assert history['organization_id'] == batch.org_id
    table = ImportSessionLog.__table__
    audits = db_session.execute(select(table).where(table.c.user_id == batch.user.id)).mappings().all()
    assert len(audits) == 1
    assert audits[0]['session_id']
    assert audits[0]['import_source'] == 'unified_applications'
    assert audits[0]['operation_type'] == 'import'
    assert audits[0]['records_updated'] == 1
    assert audits[0]['detailed_changes']


@pytest.mark.parametrize('existing', [True, False])
def test_audit_failure_rolls_back_actual_application_writes(batch, db_session, client, login_as, monkeypatch, existing):
    from app.modules.applications.routes import import_sophisticated_routes

    def unavailable_audit(**kwargs):
        raise RuntimeError('Synthetic audit failure')

    monkeypatch.setattr(import_sophisticated_routes, 'ImportSessionLog', unavailable_audit)
    before = snapshot(db_session, batch)
    login_as(client, batch.user)
    response = client.post('/applications/import-manual', json={'applications': [{
        'name': batch.names[0] if existing else 'New ' + batch.suffix,
        'description': 'Must not persist',
    }]})
    assert response.status_code == 500
    assert response.get_json()['success'] is False
    assert snapshot(db_session, batch) == before
