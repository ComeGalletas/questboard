"""claude-cli provider: `claude -p --output-format json --json-schema ...` as a subprocess.

The model gets no tools and no MCP servers (invariant 3: the LLM proposes, it never acts). The
prompt goes over stdin so it never shows up in the process list. One call at a time
(single-flight); the scheduler owns retries across runs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from collections.abc import Callable
from typing import Any, ClassVar

from questboard_schema.common_schema import ProviderName
from questboard_schema.llm_run_schema import TokenUsage

from runner.providers.base import (
    GenerationRequest,
    Provider,
    ProviderError,
    ProviderUnavailable,
    RawCompletion,
)

Run = Callable[..., subprocess.CompletedProcess[str]]

_single_flight = threading.Lock()


class ClaudeCliProvider(Provider):
    name: ClassVar[ProviderName] = ProviderName.claude_cli

    def __init__(
        self,
        executable: str = "claude",
        model: str | None = None,
        run: Run = subprocess.run,
    ) -> None:
        self.executable = executable
        self.model = model
        self._run = run

    def is_available(self) -> bool:
        return shutil.which(self.executable) is not None

    def build_command(self, request: GenerationRequest, schema: dict[str, Any]) -> list[str]:
        cmd = [
            self.executable,
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema, separators=(",", ":")),
            "--system-prompt",
            request.system,
            "--tools",
            "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]
        if self.model:
            cmd += ["--model", self.model]
        return cmd

    def _complete(self, request: GenerationRequest, schema: dict[str, Any]) -> RawCompletion:
        cmd = self.build_command(request, schema)
        with _single_flight:
            try:
                proc = self._run(
                    cmd,
                    input=request.prompt,
                    capture_output=True,
                    text=True,
                    timeout=request.timeout_s,
                    check=False,
                )
            except FileNotFoundError:
                raise ProviderUnavailable(f"{self.executable} not found") from None
            except subprocess.TimeoutExpired:
                raise ProviderError(f"timed out after {request.timeout_s:.0f}s") from None
        # stderr is not surfaced: it can echo prompt fragments.
        if proc.returncode != 0:
            raise ProviderError(f"exited with code {proc.returncode}")
        return parse_envelope(proc.stdout)


def parse_envelope(stdout: str) -> RawCompletion:
    """Parse the `--output-format json` result envelope."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        raise ProviderError("stdout is not a JSON envelope") from None
    if not isinstance(envelope, dict) or envelope.get("type") != "result":
        raise ProviderError("unexpected envelope shape")
    if envelope.get("is_error") or envelope.get("subtype") != "success":
        raise ProviderError(f"cli reported error: {envelope.get('subtype', 'unknown')}")

    data = envelope.get("structured_output")
    if data is None:
        data = envelope.get("result")
    if data is None:
        raise ProviderError("envelope has no result")
    return RawCompletion(data=data, usage=_usage(envelope.get("usage")))


def _usage(raw: Any) -> TokenUsage | None:
    if not isinstance(raw, dict):
        return None
    try:
        return TokenUsage(
            input=int(raw.get("input_tokens", 0))
            + int(raw.get("cache_read_input_tokens", 0))
            + int(raw.get("cache_creation_input_tokens", 0)),
            output=int(raw.get("output_tokens", 0)),
        )
    except (TypeError, ValueError):
        return None
