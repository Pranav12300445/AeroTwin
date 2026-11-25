"""Groq client: request shape, key handling and failure fallbacks (HTTP mocked at the transport)."""

import json

import httpx
import pytest

from app.agents import llm_client
from app.config import Settings


@pytest.fixture
def groq(monkeypatch):
    """Route the client's httpx traffic to a handler; returns state with .requests and .handler."""
    state = type("S", (), {})()
    state.requests = []
    state.handler = lambda request: httpx.Response(
        200, json={"choices": [{"message": {"content": '{"summary": "ok"}'}}]})

    def handle(request):
        state.requests.append(request)
        return state.handler(request)

    real = httpx.AsyncClient
    monkeypatch.setattr(llm_client.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    return state


def use_settings(monkeypatch, **kw):
    monkeypatch.setattr(llm_client, "get_settings", lambda: Settings(_env_file=None, **kw))


@pytest.mark.parametrize("key", ["", "gsk_PASTE_YOUR_KEY_HERE"])
async def test_no_usable_key_returns_empty_without_calling_api(groq, monkeypatch, key):
    use_settings(monkeypatch, groq_api_key=key)
    assert await llm_client.ask_llm("sys", "user") == ""
    assert groq.requests == []


async def test_success_returns_message_content(groq, monkeypatch):
    use_settings(monkeypatch, groq_api_key="gsk_test")
    assert await llm_client.ask_llm("sys", "user") == '{"summary": "ok"}'


async def test_request_shape(groq, monkeypatch):
    use_settings(monkeypatch, groq_api_key="gsk_test", groq_model="some/model")
    await llm_client.ask_llm("SYSTEM TEXT", "USER TEXT")

    req = groq.requests[0]
    body = json.loads(req.content)
    assert req.method == "POST"
    assert str(req.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer gsk_test"
    assert body["model"] == "some/model"
    assert body["messages"] == [
        {"role": "system", "content": "SYSTEM TEXT"},
        {"role": "user", "content": "USER TEXT"},
    ]
    assert body["temperature"] == 0.3
    assert body["max_tokens"] >= 1000  # reasoning models need headroom beyond the visible answer


async def test_default_model_is_not_a_retired_one(monkeypatch):
    # llama-3.1-70b-versatile and llama-3.3-70b-versatile were shut down by Groq
    model = Settings(_env_file=None).groq_model
    assert model not in {"llama-3.1-70b-versatile", "llama-3.3-70b-versatile"}


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_http_errors_fall_back_to_empty(groq, monkeypatch, status):
    use_settings(monkeypatch, groq_api_key="gsk_test")
    groq.handler = lambda request: httpx.Response(status, json={"error": "nope"})
    assert await llm_client.ask_llm("s", "u") == ""


async def test_network_error_falls_back_to_empty(groq, monkeypatch):
    use_settings(monkeypatch, groq_api_key="gsk_test")

    def boom(request):
        raise httpx.ConnectError("unreachable")

    groq.handler = boom
    assert await llm_client.ask_llm("s", "u") == ""


@pytest.mark.parametrize("payload", [{"choices": []}, {}, {"choices": [{"message": {"content": None}}]}])
async def test_unexpected_response_shape_falls_back_to_empty(groq, monkeypatch, payload):
    use_settings(monkeypatch, groq_api_key="gsk_test")
    groq.handler = lambda request: httpx.Response(200, json=payload)
    assert await llm_client.ask_llm("s", "u") == ""
