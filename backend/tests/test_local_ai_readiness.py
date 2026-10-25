"""Readiness means the local runtime and selected model are present, without a key."""
from unittest.mock import AsyncMock

import httpx
import pytest


@pytest.mark.parametrize('payload,ready', [
    ({'models': [{'name': 'qwen3:4b-q4_K_M'}]}, True),
    ({'models': [{'model': 'qwen3:4b-q4_K_M'}]}, True),
    ({'models': [{'name': 'another-model'}]}, False),
    ({'models': []}, False),
    ({'models': 'invalid'}, False),
])
def test_local_config_checks_selected_model_without_credentials(client, application, monkeypatch, payload, ready):
    settings = application.state.settings
    settings.ai_mode = 'ollama'
    settings.openai_api_key = None
    response = httpx.Response(200, json=payload, request=httpx.Request('GET', 'http://127.0.0.1:11434/api/tags'))
    get = AsyncMock(return_value=response)
    monkeypatch.setattr(httpx.AsyncClient, 'get', get)
    result = client.get('/api/buddy/config')
    assert result.status_code == 200
    assert result.json() == {'mode': 'ollama', 'name': 'Way', 'max_message_length': 2000,
                             'ai_ready': ready, 'setup_required': not ready}
    get.assert_awaited_once_with('http://127.0.0.1:11434/api/tags')


def test_missing_local_runtime_is_reported_without_remote_fallback(client, application, monkeypatch):
    application.state.settings.ai_mode = 'ollama'
    get = AsyncMock(side_effect=httpx.ConnectError('private-test-detail'))
    monkeypatch.setattr(httpx.AsyncClient, 'get', get)
    result = client.get('/api/buddy/config')
    assert result.status_code == 200
    assert result.json()['mode'] == 'ollama'
    assert result.json()['ai_ready'] is False
    assert result.json()['setup_required'] is True
    assert 'private-test-detail' not in result.text
