"""ollama provider: a local model with schema-constrained output (`format: <JSON Schema>`).

Skipped when the PC is on battery below 30 % or under high CPU load (CLAUDE.md scheduler
guards), so a local model never drains the laptop or stalls the user's work.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

import httpx
import psutil
from questboard_schema.common_schema import ProviderName
from questboard_schema.llm_run_schema import TokenUsage

from runner.providers.base import (
    GenerationRequest,
    Provider,
    ProviderError,
    ProviderUnavailable,
    RawCompletion,
)

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_URL = "http://127.0.0.1:11434"
MIN_BATTERY = 30.0
MAX_CPU = 85.0


def machine_ok() -> bool:
    """False on battery below MIN_BATTERY %, or when the CPU is busy."""
    battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    if battery is not None and not battery.power_plugged and battery.percent < MIN_BATTERY:
        return False
    return psutil.cpu_percent(interval=0.5) < MAX_CPU


class OllamaProvider(Provider):
    name: ClassVar[ProviderName] = ProviderName.ollama

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_URL,
        client: httpx.Client | None = None,
        machine_check: Callable[[], bool] = machine_ok,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client()
        self._machine_check = machine_check

    def is_available(self) -> bool:
        if not self._machine_check():
            return False
        try:
            tags = self._client.get(f"{self.base_url}/api/tags", timeout=2.0)
            tags.raise_for_status()
        except httpx.HTTPError:
            return False
        names = {m.get("name") for m in tags.json().get("models", [])}
        return self.model in names or f"{self.model}:latest" in names

    def _complete(self, request: GenerationRequest, schema: dict[str, Any]) -> RawCompletion:
        body = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            "options": {"temperature": 0.4},
        }
        try:
            resp = self._client.post(
                f"{self.base_url}/api/chat", json=body, timeout=request.timeout_s
            )
        except httpx.TimeoutException:
            raise ProviderError(f"timed out after {request.timeout_s:.0f}s") from None
        except httpx.HTTPError:
            raise ProviderUnavailable("cannot reach ollama") from None
        if resp.status_code != 200:
            raise ProviderError(f"ollama returned {resp.status_code}")
        try:
            data = resp.json()
            content = data["message"]["content"]
        except (ValueError, KeyError, TypeError):
            raise ProviderError("unexpected ollama response shape") from None
        return RawCompletion(
            data=content,
            usage=TokenUsage(
                input=int(data.get("prompt_eval_count") or 0),
                output=int(data.get("eval_count") or 0),
            ),
        )
