"""Provider interface shared by claude-cli, ollama and claude-api.

Every provider returns the same structured output (CLAUDE.md invariant 6). The base class owns
parsing and schema validation so providers only have to move text in and out: a response that
fails validation is retried once with the validation errors appended, then the provider gives up
and `run_with_fallback` moves on to the next provider in the configured order.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError
from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.llm_run_schema import TokenUsage

_FENCE = re.compile(r"^\s*```(?:json)?\s*\n(.*?)\n\s*```\s*$", re.DOTALL)
_MAX_ERRORS_IN_RETRY = 10
# Pydantic emits OpenAPI's `discriminator`; strict JSON Schema validators (claude --json-schema)
# reject it. Local validation still uses it through the Pydantic model.
_NON_STANDARD_KEYWORDS = frozenset({"discriminator"})
_SCHEMA_MAPS = frozenset({"properties", "$defs", "definitions", "patternProperties"})


type Check[T] = Callable[[T], list[str]]
"""Semantic rules beyond the schema; returns human-readable problems (no data values)."""


class ProviderError(Exception):
    """A provider could not produce a usable response. Messages never include prompt text."""


class ProviderUnavailable(ProviderError):
    """The provider is not reachable right now (binary missing, daemon down, no network)."""


class ProviderOutputError(ProviderError):
    """The provider answered, but the output did not validate after the retry."""


class AllProvidersFailed(ProviderError):
    def __init__(self, failures: Sequence[tuple[ProviderName, ProviderError]]):
        self.failures = list(failures)
        detail = "; ".join(f"{name.value}: {err}" for name, err in self.failures)
        super().__init__(
            f"all providers failed ({detail})" if detail else "no providers configured"
        )


@dataclass(frozen=True)
class GenerationRequest:
    job: JobName
    system: str
    prompt: str
    timeout_s: float = 300.0


@dataclass(frozen=True)
class RawCompletion:
    """What a provider returns before validation: a JSON string, or already-parsed JSON."""

    data: Any
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class ProviderResult[T: BaseModel]:
    provider: ProviderName
    output: T
    attempts: int
    usage: TokenUsage | None = None
    retry_errors: list[str] = field(default_factory=list)


class Provider(ABC):
    name: ClassVar[ProviderName]

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap reachability check used by the scheduler guards."""

    @abstractmethod
    def _complete(self, request: GenerationRequest, schema: dict[str, Any]) -> RawCompletion:
        """Send one request and return the raw response. Raise ProviderError on failure."""

    def generate[T: BaseModel](
        self,
        request: GenerationRequest,
        output_model: type[T],
        check: Check[T] | None = None,
    ) -> ProviderResult[T]:
        """Schema-validate the output, then run `check` (semantic rules). Either kind of
        failure is retried once with the errors appended to the prompt."""
        schema = output_schema(output_model)
        usage: TokenUsage | None = None
        retry_errors: list[str] = []
        current = request
        for attempt in (1, 2):
            raw = self._complete(current, schema)
            usage = _add_usage(usage, raw.usage)
            try:
                output = output_model.model_validate(_parse_json(raw.data))
            except (ValueError, ValidationError) as exc:
                retry_errors = _describe(exc)
                current = _with_retry_hint(request, retry_errors)
                continue
            problems = check(output) if check else []
            if problems:
                retry_errors = problems[:_MAX_ERRORS_IN_RETRY]
                current = _with_retry_hint(request, retry_errors)
                continue
            return ProviderResult(
                provider=self.name,
                output=output,
                attempts=attempt,
                usage=usage,
                retry_errors=retry_errors,
            )
        raise ProviderOutputError(
            f"output failed validation after retry ({len(retry_errors)} errors)"
        )


def run_with_fallback[T: BaseModel](
    providers: Sequence[Provider],
    request: GenerationRequest,
    output_model: type[T],
    check: Check[T] | None = None,
) -> ProviderResult[T]:
    """Try each provider in order; skip unreachable ones; return the first valid result."""
    failures: list[tuple[ProviderName, ProviderError]] = []
    for provider in providers:
        if not provider.is_available():
            failures.append((provider.name, ProviderUnavailable("not available")))
            continue
        try:
            return provider.generate(request, output_model, check)
        except ProviderError as exc:
            failures.append((provider.name, exc))
    raise AllProvidersFailed(failures)


def output_schema(output_model: type[BaseModel]) -> dict[str, Any]:
    """Self-contained, standard JSON Schema for a model, as sent to providers."""
    return _strip_non_standard(output_model.model_json_schema())


def _strip_non_standard(node: Any) -> Any:
    if isinstance(node, list):
        return [_strip_non_standard(item) for item in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _NON_STANDARD_KEYWORDS:
            continue
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            out[key] = {name: _strip_non_standard(sub) for name, sub in value.items()}
        else:
            out[key] = _strip_non_standard(value)
    return out


def _parse_json(data: Any) -> Any:
    if not isinstance(data, str):
        return data
    match = _FENCE.match(data)
    text = match.group(1) if match else data
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"response is not valid JSON: {exc.msg}") from None


def _describe(exc: Exception) -> list[str]:
    if isinstance(exc, ValidationError):
        # include_input=False: never echo model output (which may contain PII) into logs/prompts.
        return [
            f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors(include_input=False, include_url=False)
        ][:_MAX_ERRORS_IN_RETRY]
    return [str(exc)]


def _with_retry_hint(request: GenerationRequest, errors: list[str]) -> GenerationRequest:
    hint = "\n".join(f"- {e}" for e in errors)
    prompt = (
        f"{request.prompt}\n\n"
        "Your previous answer did not match the required JSON schema:\n"
        f"{hint}\n"
        "Return only corrected JSON that matches the schema."
    )
    return GenerationRequest(
        job=request.job, system=request.system, prompt=prompt, timeout_s=request.timeout_s
    )


def _add_usage(total: TokenUsage | None, more: TokenUsage | None) -> TokenUsage | None:
    if more is None:
        return total
    if total is None:
        return more
    return TokenUsage(input=total.input + more.input, output=total.output + more.output)
