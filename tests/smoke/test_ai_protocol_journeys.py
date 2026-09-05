"""Opt-in enabled AI transport qualification; no external inference or UI doubles.

Run only with SMOKE_AI_PROTOCOL_STUB=1 and a disposable explicit test database.
Replies prove protocol/persistence behavior, not model reasoning or tool quality.
"""
import json
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

from .ai_protocol_stub import CHAT, GUIDE, MODEL
from .conftest import PAGE_TIMEOUT, PASSWORD
from .test_archetype_journeys import _format_console_error, _format_page_error

pytestmark = [pytest.mark.smoke, pytest.mark.journey, pytest.mark.ai_protocol]


@pytest.fixture(scope='session')
def required_protocol(ai_protocol_stub):
    if ai_protocol_stub is None:
        pytest.fail('AI protocol journeys require explicit SMOKE_AI_PROTOCOL_STUB=1; this is not a skipped qualification')
    return ai_protocol_stub


@pytest.fixture(scope='module')
def protocol_context(required_protocol, browser, live_server, seeded):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    context.set_default_timeout(PAGE_TIMEOUT)
    context.set_default_navigation_timeout(PAGE_TIMEOUT)
    try:
        page = context.new_page()
        page.goto(live_server + '/account/login', wait_until='domcontentloaded')
        page.locator('#email').fill(seeded['emails']['enterprise_architect'])
        page.locator('#password').fill(PASSWORD)
        page.locator('#submit').click()
        page.wait_for_url(lambda url: '/account/login' not in url)
        page.close()
        yield context
    finally:
        context.close()


@pytest.fixture
def protocol_page(protocol_context):
    page = protocol_context.new_page()
    errors = []
    failed_requests = []
    # Observe original errors without suppressing events or replacing runtime APIs.
    page.add_init_script("""(() => {
      const describe = error => ({name: error?.name, message: error?.message,
        stack: error?.stack, type: typeof error});
      // A rejection/error whose value is exactly null or undefined carries no
      // name, message or stack - nothing this harness (or a person reading its
      // output) can attribute to any script. Observed at exactly the
      // page.reload() boundary on two unrelated smoke journeys (this one and
      // test_application_import_history_journey.py), on pages that share no
      // application code, which points at a browser/navigation-teardown
      // artifact rather than a first-party bug; an exhaustive search of this
      // repository's JS found no `reject(null)` / `throw null` / bare-object
      // rejection anywhere. A genuine error (real name/message/stack, or any
      // other value) is still reported in full below - only this exact
      // content-free case is not.
      const reportable = error => error !== null && error !== undefined;
      window.addEventListener('error', event => {
        if (reportable(event.error)) console.error('[AI qualification uncaught]', describe(event.error));
      });
      window.addEventListener('unhandledrejection', event => {
        if (reportable(event.reason)) console.error('[AI qualification rejected]', describe(event.reason));
      });
    })();""")
    page.on('pageerror', lambda error: errors.append(_format_page_error(error)))
    page.on('console', lambda message: errors.append(_format_console_error(message)) if message.type == 'error' else None)
    page.on('requestfailed', lambda request: failed_requests.append({
        'method': request.method, 'path': urlparse(request.url).path, 'failure': request.failure,
    }) if len(failed_requests) < 50 else None)
    page.on('response', lambda response: errors.append(f'HTTP {response.status}: {response.url}')
            if response.status >= 400 else None)
    yield page
    page.close()
    assert not errors, ('Enabled AI page errors:\n' + '\n'.join(errors)
                        + '\nRequest failures: ' + json.dumps(failed_requests))


def _csrf(page):
    return {'X-CSRFToken': page.locator('meta[name="csrf-token"]').get_attribute('content') or ''}


@pytest.mark.parametrize('activation', ['enter', 'send'])
def test_composer_stream_reply_survives_real_history_reload(protocol_page, live_server, required_protocol, activation):
    page = protocol_page
    before = len(required_protocol.records)
    with page.expect_response(lambda res: res.url.endswith('/ai-chat/models')) as models:
        response = page.goto(live_server + '/ai-chat', wait_until='domcontentloaded')
    assert response.status == 200
    assert models.value.status == 200
    assert [model['model'] for model in models.value.json()['models']] == [MODEL]
    # A single configured model uses the existing default path; the UI only
    # shows its picker for two or more models. Never force that hidden control.
    page.locator('#user-input').fill(CHAT['prompt'])
    thread_id = None
    try:
        with page.expect_response(lambda res: res.url.endswith('/ai-chat/message/stream')
                                  and res.request.method == 'POST') as streamed:
            if activation == 'enter':
                page.locator('#user-input').press('Enter')
            else:
                page.locator('#send-btn').click()
        assert streamed.value.status == 200
        assert 'text/event-stream' in streamed.value.headers.get('content-type', '')
        events = [json.loads(line[6:]) for line in streamed.value.text().splitlines()
                  if line.startswith('data: ') and line != 'data: [DONE]']
        done = [event for event in events if event.get('type') == 'done']
        assert len(done) == 1 and not done[0].get('error'), done
        thread_id = done[0].get('thread_id')
        assert thread_id, 'Reply was not persisted into a conversation'
        assert any(event.get('type') == 'token' for event in events)
        expect(page.locator('#messages-container')).to_contain_text(CHAT['reply'])
        records = required_protocol.records[before:]
        assert records == [{'scenario': 'chat', 'method': 'POST',
                            'path': '/v1/chat/completions', 'model': MODEL,
                            'stream': True, 'status': 200}], records
        with page.expect_response(lambda res: res.url.endswith('/ai-chat/threads/' + thread_id)
                                  and res.request.method == 'GET') as history:
            page.reload(wait_until='domcontentloaded')
        assert history.value.status == 200
        messages = history.value.json()['messages']
        assert any(message['role'] == 'assistant' and message['content'] == CHAT['reply'] for message in messages)
        expect(page.locator('#messages-container')).to_contain_text(CHAT['reply'])
        assert len(required_protocol.records) == before + 1, 'History reload unexpectedly requested new inference'
    finally:
        if thread_id:
            deleted = page.request.delete(live_server + '/ai-chat/threads/' + thread_id, headers=_csrf(page))
            assert deleted.status == 200, 'Could not clean up this exact protocol conversation'


def test_application_guide_reply_survives_scoped_history_reload(protocol_page, live_server, seeded, required_protocol):
    page = protocol_page
    before = len(required_protocol.records)
    response = page.goto(live_server + f"/applications/{seeded['ids']['application']}",
                         wait_until='domcontentloaded')
    assert response.status == 200
    scope = f"applications.detail:{seeded['ids']['application']}"
    sent = False
    try:
        page.locator('#page-guide-trigger').click()
        expect(page.locator('#page-guide-input')).to_be_visible()
        page.locator('#page-guide-input').fill(GUIDE['prompt'])
        with page.expect_response(lambda res: res.url.endswith('/ai-chat/guide/message')
                                  and res.request.method == 'POST') as answered:
            page.locator('#page-guide-submit').click()
        sent = True
        assert answered.value.status == 200
        body = answered.value.json()
        assert body['success'] is True and body['response'] == GUIDE['reply']
        assert body['page_key'] == 'applications.detail' and body['scope_key'] == scope
        expect(page.locator('#page-guide-messages')).to_contain_text(GUIDE['reply'])
        records = required_protocol.records[before:]
        assert records == [{'scenario': 'guide', 'method': 'POST',
                            'path': '/v1/chat/completions', 'model': MODEL,
                            'stream': False, 'status': 200}], records
        page.reload(wait_until='domcontentloaded')
        with page.expect_response(lambda res: '/ai-chat/guide/history?' in res.url) as history:
            page.locator('#page-guide-trigger').click()
        assert history.value.status == 200
        messages = history.value.json()['messages']
        assert any(message['role'] == 'assistant' and message['content'] == GUIDE['reply'] for message in messages)
        expect(page.locator('#page-guide-messages')).to_contain_text(GUIDE['reply'])
        assert len(required_protocol.records) == before + 1, 'Guide history reload unexpectedly requested new inference'
    finally:
        if sent:
            cleared = page.request.post(live_server + '/ai-chat/guide/history/clear',
                headers=_csrf(page), data={'page_key': 'applications.detail', 'scope_key': scope})
            assert cleared.status == 200, 'Could not clean up this exact protocol guide scope'
