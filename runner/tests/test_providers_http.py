"""claude-api and ollama providers against recorded responses (no network, no keys)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic
import httpx
import httpx2
import pytest
from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.quest_diff_schema import QuestDiff

from runner.providers import GenerationRequest, ProviderError, ProviderUnavailable
from runner.providers.claude_api import ClaudeApiProvider
from runner.providers.ollama import OllamaProvider

FIX = Path(__file__).parent / "fixtures"
REQUEST = GenerationRequest(
    job=JobName.daily_am, system="Planner. Diffs only.", prompt="Current quests: ...", timeout_s=30
)


def load(path: str) -> dict[str, Any]:
    return json.loads((FIX / path).read_text())


# -- claude-api ---------------------------------------------------------------------------


def claude(responses: list[Any], seen: list[httpx2.Request]) -> ClaudeApiProvider:
    queue = list(responses)

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        status, body = item
        return httpx2.Response(status, json=body)

    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return ClaudeApiProvider(client=client)


def test_claude_api_returns_validated_diff_and_sends_structured_output_request() -> None:
    seen: list[httpx2.Request] = []
    result = claude([(200, load("claude_api/quest_diff.json"))], seen).generate(REQUEST, QuestDiff)

    assert result.provider is ProviderName.claude_api
    assert len(result.output.ops) == 3
    assert (result.usage.input, result.usage.output) == (2000, 340)
    body = json.loads(seen[0].content)
    assert body["model"] == "claude-opus-5"
    assert body["system"] == REQUEST.system
    assert body["messages"] == [{"role": "user", "content": REQUEST.prompt}]
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["fallbacks"] == "default"
    assert "tools" not in body  # the model proposes; it never acts
    assert "server-side-fallback-2026-07-01" in seen[0].headers["anthropic-beta"]
    # Constraints the API can't enforce are moved out of the schema (validated locally).
    assert '"maxLength"' not in json.dumps(body["output_config"]["format"]["schema"])


def test_claude_api_refusal_and_truncation_are_errors() -> None:
    with pytest.raises(ProviderError, match=r"refused \(cyber\)"):
        claude([(200, load("claude_api/refusal.json"))], []).generate(REQUEST, QuestDiff)
    with pytest.raises(ProviderError, match="max_tokens"):
        claude([(200, load("claude_api/max_tokens.json"))], []).generate(REQUEST, QuestDiff)


@pytest.mark.parametrize(
    ("status", "exc", "message"),
    [
        (429, ProviderError, "rate limited"),
        (500, ProviderError, "API error 500"),
        (401, ProviderUnavailable, "credentials rejected"),
    ],
)
def test_claude_api_http_errors_never_echo_bodies(status, exc, message) -> None:
    body = {"type": "error", "error": {"type": "x", "message": "PERSON_7 was in the prompt"}}
    with pytest.raises(exc, match=message) as info:
        claude([(status, body)], []).generate(REQUEST, QuestDiff)
    assert "PERSON_7" not in str(info.value)


def test_claude_api_connection_error_is_unavailable() -> None:
    with pytest.raises(ProviderUnavailable):
        claude([httpx2.ConnectError("down")], []).generate(REQUEST, QuestDiff)


# -- ollama -------------------------------------------------------------------------------


def ollama(handler, machine_ok: bool = True, model: str = "qwen3:8b") -> OllamaProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaProvider(model=model, client=client, machine_check=lambda: machine_ok)


def ollama_handler(seen: list[httpx.Request], chat: dict[str, Any] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=load("ollama/tags.json"))
        if request.url.path == "/api/chat":
            return httpx.Response(200, json=chat or load("ollama/chat_quest_diff.json"))
        return httpx.Response(404)

    return handler


def test_ollama_constrains_output_with_the_schema() -> None:
    seen: list[httpx.Request] = []
    provider = ollama(ollama_handler(seen))
    assert provider.is_available()
    result = provider.generate(REQUEST, QuestDiff)
    assert result.provider is ProviderName.ollama
    assert (result.usage.input, result.usage.output) == (900, 260)
    body = json.loads(seen[-1].content)
    assert body["model"] == "qwen3:8b"
    assert body["stream"] is False
    assert body["format"]["title"] == "QuestDiff"
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_ollama_availability_guards() -> None:
    assert not ollama(ollama_handler([]), machine_ok=False).is_available()  # battery / load
    assert not ollama(ollama_handler([]), model="mistral").is_available()  # model not pulled
    assert ollama(ollama_handler([]), model="llama3.1").is_available()  # ":latest" tag

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    assert not ollama(down).is_available()
    with pytest.raises(ProviderUnavailable):
        ollama(down).generate(REQUEST, QuestDiff)


def test_ollama_bad_json_is_retried_once_then_fails() -> None:
    bad = {"message": {"content": "sure! here are your quests"}, "done": True}
    provider = ollama(ollama_handler([], chat=bad))
    with pytest.raises(ProviderError, match="failed validation"):
        provider.generate(REQUEST, QuestDiff)
