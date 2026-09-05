"""Real guards/routes and Flask-Login; persistence/inference are explicit doubles.

No app factory, database or provider requests. The separate database module uses
the shared rollback fixtures to verify actual scoped rows and deletion.
"""
from types import SimpleNamespace

import pytest
from flask_login import UserMixin

from tests.test_availability_response_contracts import _bare_app

CONTEXT = {'page_key': 'applications.detail', 'scope_key': 'applications.detail:32'}
OPERATIONS = ['history', 'clear', 'message']


@pytest.fixture
def policy(monkeypatch):
    from app.models.audit_log import AuditLog
    from app.modules.ai_chat.services.page_guide_service import PageGuideService

    app = _bare_app(login_disabled=False)
    app.config.update(AI_PAGE_GUIDE_ENABLED=True, RATE_LIMITING_ENABLED=False)

    class User(UserMixin):
        id = 42
        email = 'guide-policy@example.test'
        role_name = 'user'

    app.login_manager.user_loader(lambda user_id: User() if user_id == '42' else None)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = '42'
        session['_fresh'] = True
    calls = []
    audits = []

    def history(self, page_key, scope_key):
        calls.append(('history', self.user_id, page_key, scope_key))
        return [{'role': 'assistant', 'content': 'Saved fixture record'}]

    def clear(self, page_key, scope_key):
        calls.append(('clear', self.user_id, page_key, scope_key))
        return {'success': True, 'cleared_count': 1}

    def answer(self, **kwargs):
        calls.append(('message', self.user_id, kwargs['page_key'], kwargs['scope_key']))
        return {'success': True, 'response': 'Inference boundary fixture'}

    monkeypatch.setattr(PageGuideService, 'get_history', history)
    monkeypatch.setattr(PageGuideService, 'clear_history', clear)
    monkeypatch.setattr(PageGuideService, 'answer_message', answer)
    monkeypatch.setattr(AuditLog, 'log', lambda **kwargs: audits.append(kwargs))
    return SimpleNamespace(app=app, client=client, calls=calls, audits=audits)


def request_operation(client, operation, payload=None):
    data = CONTEXT if payload is None else payload
    if operation == 'history':
        return client.get('/ai-chat/guide/history', query_string=data)
    if operation == 'clear':
        return client.post('/ai-chat/guide/history/clear', json=data)
    return client.post('/ai-chat/guide/message', json={**data, 'message': 'Guide this page.'})


def forbid_resolver(monkeypatch):
    from app.services.llm_service import LLMService

    def forbidden():
        raise AssertionError('History/policy path must not resolve a provider')

    monkeypatch.setattr(LLMService, '_get_configured_provider', staticmethod(forbidden))


@pytest.mark.parametrize('operation', OPERATIONS)
@pytest.mark.parametrize('guide,chat', [(False, None), (False, True), (True, False)])
def test_explicit_policy_denial_blocks_all_without_provider_lookup(policy, monkeypatch, operation, guide, chat):
    policy.app.config.update(AI_PAGE_GUIDE_ENABLED=guide, AI_CHAT_ENABLED=chat)
    forbid_resolver(monkeypatch)
    response = request_operation(policy.client, operation)
    assert response.status_code == 503
    assert response.get_json()['message'] == 'The page guide is not enabled.'
    assert policy.calls == []


@pytest.mark.parametrize('chat', [None, True])
@pytest.mark.parametrize('operation', ['history', 'clear'])
def test_saved_records_work_without_any_provider_lookup(policy, monkeypatch, chat, operation):
    policy.app.config['AI_CHAT_ENABLED'] = chat
    forbid_resolver(monkeypatch)
    response = request_operation(policy.client, operation)
    assert response.status_code == 200
    assert policy.calls == [(operation, 42, 'applications.detail', 'applications.detail:32')]
    body = response.get_json()
    if operation == 'history':
        assert body['messages'][0]['content'] == 'Saved fixture record'
    else:
        assert body['cleared_count'] == 1
        assert policy.audits[0]['action'] == 'clear_page_guide_history'
    assert body['page_key'] == CONTEXT['page_key']
    assert body['scope_key'] == CONTEXT['scope_key']
    from app.modules.ai_chat.services.page_guide_service import PageGuideService
    with policy.app.app_context():
        assert PageGuideService.is_enabled() is True  # context/layout still exposes history


@pytest.mark.parametrize('chat', [None, True])
@pytest.mark.parametrize('configured', [False, True])
def test_generation_always_requires_provider_even_with_chat_override(policy, monkeypatch, chat, configured):
    from app.services.llm_service import LLMService
    policy.app.config['AI_CHAT_ENABLED'] = chat
    resolutions = []

    def resolver():
        resolutions.append(True)
        if not configured:
            raise ValueError('No provider fixture')
        return 'fixture-provider', 'fixture-model'

    monkeypatch.setattr(LLMService, '_get_configured_provider', staticmethod(resolver))
    response = request_operation(policy.client, 'message')
    assert resolutions
    if configured:
        assert response.status_code == 200
        assert policy.calls == [('message', 42, 'applications.detail', 'applications.detail:32')]
        assert response.get_json()['response'] == 'Inference boundary fixture'
        assert policy.audits[0]['action'] == 'page_guide_message'
    else:
        assert response.status_code == 503
        assert response.get_json()['error'] == 'service_unavailable'
        assert response.get_json()['feature'] == 'chat'
        assert policy.calls == []


@pytest.mark.parametrize('operation', OPERATIONS)
def test_unauthenticated_requests_never_reach_provider_or_history(policy, monkeypatch, operation):
    forbid_resolver(monkeypatch)
    response = request_operation(policy.app.test_client(), operation)
    assert response.status_code == 401
    assert policy.calls == []


@pytest.mark.parametrize('operation', ['history', 'clear'])
@pytest.mark.parametrize('payload', [{}, {'page_key': 'not.registered', 'scope_key': 'global'}])
def test_history_validation_and_registry_still_apply_without_provider(policy, monkeypatch, operation, payload):
    forbid_resolver(monkeypatch)
    response = request_operation(policy.client, operation, payload)
    assert response.status_code == 400
    assert policy.calls == []
