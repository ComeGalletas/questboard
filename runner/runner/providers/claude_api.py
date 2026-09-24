"""claude-api provider: the Messages API with structured output (`output_config.format`).

No tools are sent (invariant 3). Unsupported JSON Schema constraints are moved into
descriptions by `anthropic.transform_schema`; the base class still validates them locally.
Server-side refusal fallbacks are on (`fallbacks: "default"`), so a safety decline is retried
on Anthropic's recommended model inside the same call. Credentials come from the SDK's usual
chain (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN or an `ant auth login` profile).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

import anthropic
from questboard_schema.common_schema import ProviderName
from questboard_schema.llm_run_schema import TokenUsage

from runner.providers.base import (
    GenerationRequest,
    Provider,
    ProviderError,
    ProviderUnavailable,
    RawCompletion,
)

DEFAULT_MODEL = "claude-opus-5"
MAX_TOKENS = 16000  # non-streaming; plenty for a day's diffs + dialogue bundle
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _has_credentials() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return (config_home / "anthropic").is_dir()  # `ant auth login` profile store


class ClaudeApiProvider(Provider):
    name: ClassVar[ProviderName] = ProviderName.claude_api

    def __init__(self, model: str = DEFAULT_MODEL, client: anthropic.Anthropic | None = None):
        self.model = model
        self._client = client

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            # Retries are the scheduler's job (backoff across ticks); fail fast here.
            self._client = anthropic.Anthropic(max_retries=1)
        return self._client

    def is_available(self) -> bool:
        return self._client is not None or _has_credentials()

    def _complete(self, request: GenerationRequest, schema: dict[str, Any]) -> RawCompletion:
        try:
            response = self._get_client().beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=request.system,
                messages=[{"role": "user", "content": request.prompt}],
                output_config={
                    "format": {"type": "json_schema", "schema": anthropic.transform_schema(schema)}
                },
                betas=[FALLBACK_BETA],
                fallbacks="default",
                timeout=request.timeout_s,
            )
        # Messages name the failure class only: API error bodies can quote the request.
        except anthropic.APIConnectionError:
            raise ProviderUnavailable("cannot reach the Claude API") from None
        except anthropic.AuthenticationError:
            raise ProviderUnavailable("Claude API credentials rejected") from None
        except anthropic.RateLimitError:
            raise ProviderError("rate limited (429)") from None
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"API error {exc.status_code}") from None

        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise ProviderError(f"refused ({category or 'unspecified'})")
        if response.stop_reason == "max_tokens":
            raise ProviderError("hit max_tokens before finishing")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise ProviderError("response had no text block")
        usage = response.usage
        return RawCompletion(
            data=text,
            usage=TokenUsage(
                input=(usage.input_tokens or 0)
                + (usage.cache_read_input_tokens or 0)
                + (usage.cache_creation_input_tokens or 0),
                output=usage.output_tokens or 0,
            ),
        )
