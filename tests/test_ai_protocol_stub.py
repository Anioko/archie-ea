"""Test-only protocol fixture exercised through the real OpenAI HTTP client."""
from concurrent.futures import ThreadPoolExecutor
import os
import socket
import subprocess
import sys

import httpx
from openai import AuthenticationError, BadRequestError, OpenAI
import pytest

from tests.smoke.ai_protocol_stub import AIProtocolStub, CHAT, GUIDE, MODEL, TOKEN


def test_sdk_nonstreaming_guide_response_and_usage_cross_loopback():
    with AIProtocolStub() as stub:
        with OpenAI(api_key=TOKEN, base_url=stub.base_url, max_retries=0,
                    http_client=httpx.Client(trust_env=False)) as client:
            response = client.chat.completions.create(
                model=MODEL, messages=[{'role': 'user', 'content': GUIDE['prompt']}])
        assert response.choices[0].message.content == GUIDE['reply']
        assert response.usage.prompt_tokens == 12
        assert response.usage.completion_tokens == 8
        assert stub.records == [{'scenario': 'guide', 'method': 'POST',
                                 'path': '/v1/chat/completions', 'model': MODEL,
                                 'stream': False, 'status': 200}]


def test_sdk_streaming_chat_chunks_are_real_sse_and_finish():
    with AIProtocolStub() as stub:
        with OpenAI(api_key=TOKEN, base_url=stub.base_url, max_retries=0,
                    http_client=httpx.Client(trust_env=False)) as client:
            with client.chat.completions.create(model=MODEL, stream=True,
                    messages=[{'role': 'user', 'content': CHAT['prompt']}]) as stream:
                chunks = list(stream)
        assert ''.join(chunk.choices[0].delta.content or '' for chunk in chunks) == CHAT['reply']
        assert len([chunk for chunk in chunks if chunk.choices[0].delta.content]) >= 2
        assert chunks[-1].choices[0].finish_reason == 'stop'
        assert stub.records[0]['scenario'] == 'chat'
        assert stub.records[0]['stream'] is True


@pytest.mark.parametrize('message,model,stream', [
    ('Unknown prompt must not get an invented answer', 'ci-protocol-stub-v1', False),
    ('ARCHIE_CI_GUIDE_PROTOCOL_V1: Explain this fixture page.', 'unexpected-model', False),
    ('ARCHIE_CI_CHAT_PROTOCOL_V1: Confirm this transport fixture.', 'ci-protocol-stub-v1', False),
])
def test_unrecognized_request_fails_at_actual_sdk_boundary(message, model, stream):
    with AIProtocolStub() as stub:
        with OpenAI(api_key=TOKEN, base_url=stub.base_url, max_retries=0,
                    http_client=httpx.Client(trust_env=False)) as client:
            with pytest.raises(BadRequestError):
                client.chat.completions.create(model=model, stream=stream,
                    messages=[{'role': 'user', 'content': message}])
        assert stub.records[0]['status'] == 400


def test_child_environment_isolated_without_changing_parent():
    source = {'OPENAI_API_KEY': 'not-a-real-source-key', 'ANTHROPIC_API_KEY': 'not-real',
              'OPENAI_API_KEY_2': 'not-real', 'OPENROUTER_API_KEY_SECONDARY': 'not-real',
              'AZURE_OPENAI_API_KEY': 'not-real', 'LLM_API_KEY': 'not-real',
              'NO_PROXY': 'existing.internal'}
    before = dict(source)
    with AIProtocolStub() as stub:
        child = stub.child_environment(source)
        assert child['OPENAI_API_KEY'] == TOKEN
        assert child['OPENAI_BASE_URL'] == stub.base_url
    assert source == before
    for name in source:
        if 'API_KEY' in name and name != 'OPENAI_API_KEY':
            assert child[name] == ''
    assert child['PYTHON_DOTENV_DISABLED'] == '1'
    assert child['AI_PAGE_GUIDE_ENABLED'] == 'true'
    assert '127.0.0.1' in child['NO_PROXY']
    assert os.environ['OPENAI_API_KEY'] == ''


def test_real_sdk_child_uses_only_injected_loopback_environment():
    code = (
        'import sys; from openai import OpenAI; '
        'client = OpenAI(max_retries=0, timeout=5); '
        # Check before any network I/O, so a regression cannot contact a provider.
        'assert str(client.base_url) == sys.argv[1] + "/"; '
        'result = client.chat.completions.create(model=sys.argv[2], '
        'messages=[{"role":"user","content":sys.argv[3]}]); '
        'print(result.choices[0].message.content); client.close()'
    )
    with AIProtocolStub() as stub:
        result = subprocess.run([sys.executable, '-c', code, stub.base_url, MODEL, GUIDE['prompt']],
                                env=stub.child_environment(os.environ), capture_output=True,
                                text=True, timeout=30, check=True)
        assert result.stdout.strip() == GUIDE['reply']
        assert stub.records[0]['status'] == 200


def test_wrong_auth_and_unknown_routes_are_not_healthy_responses():
    with AIProtocolStub() as stub:
        with OpenAI(api_key='wrong-test-token', base_url=stub.base_url, max_retries=0,
                    http_client=httpx.Client(trust_env=False)) as client:
            with pytest.raises(AuthenticationError):
                client.chat.completions.create(model=MODEL,
                    messages=[{'role': 'user', 'content': GUIDE['prompt']}])
        with httpx.Client(trust_env=False) as client:
            response = client.get(stub.base_url + '/models')
            assert response.status_code == 404
        assert [record['status'] for record in stub.records] == [401, 404]
        assert all('prompt' not in record and 'authorization' not in record for record in stub.records)


def test_concurrent_requests_have_independent_ledger_and_socket_closes():
    def request(base):
        with OpenAI(api_key=TOKEN, base_url=base, max_retries=0,
                    http_client=httpx.Client(trust_env=False)) as client:
            return client.chat.completions.create(model=MODEL,
                messages=[{'role': 'user', 'content': GUIDE['prompt']}]).choices[0].message.content

    with AIProtocolStub() as stub:
        port = stub.port
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(request, [stub.base_url] * 4)) == [GUIDE['reply']] * 4
        assert len(stub.records) == 4
        assert all(record['status'] == 200 for record in stub.records)
        snapshot = stub.records
        snapshot.clear()
        assert len(stub.records) == 4
    with socket.socket() as connection:
        connection.settimeout(1)
        assert connection.connect_ex(('127.0.0.1', port)) != 0
