from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.quest_diff_schema import AddOp, DropOp, QuestDiff, UpdateOp

from runner.providers import (
    AllProvidersFailed,
    ClaudeCliProvider,
    GenerationRequest,
    ProviderError,
    ProviderOutputError,
    ProviderUnavailable,
    RawCompletion,
)
from runner.providers.base import Provider, run_with_fallback

FIXTURES = Path(__file__).parent / "fixtures" / "claude_cli"
REQUEST = GenerationRequest(
    job=JobName.daily_am,
    system="You are the Questboard planner. Propose diffs only.",
    prompt="Current quests: ...",
    timeout_s=30,
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


class FakeRun:
    """Stands in for subprocess.run; replays fixture stdouts in order and records calls."""

    def __init__(self, *stdouts: str, returncode: int = 0, raises: Exception | None = None):
        self.stdouts = list(stdouts)
        self.returncode = returncode
        self.raises = raises
        self.calls: list[dict[str, Any]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append({"cmd": cmd, **kwargs})
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdouts.pop(0), "")


def provider(run: FakeRun) -> ClaudeCliProvider:
    return ClaudeCliProvider(executable="claude", run=run)


def test_structured_output_validates_as_quest_diff() -> None:
    run = FakeRun(fixture("quest_diff_structured.json"))
    result = provider(run).generate(REQUEST, QuestDiff)

    assert result.provider is ProviderName.claude_cli
    assert result.attempts == 1
    assert [type(op.root) for op in result.output.ops] == [AddOp, UpdateOp, DropOp]
    add = result.output.ops[0].root
    assert isinstance(add, AddOp)
    assert add.quest.persona.root == "coach"
    assert result.usage is not None
    assert (result.usage.input, result.usage.output) == (1587, 92)


def test_command_disables_tools_and_keeps_prompt_off_argv() -> None:
    run = FakeRun(fixture("quest_diff_structured.json"))
    provider(run).generate(REQUEST, QuestDiff)

    call = run.calls[0]
    cmd = call["cmd"]
    assert cmd[:4] == ["claude", "-p", "--output-format", "json"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in cmd
    assert '"QuestDiff"' in cmd[cmd.index("--json-schema") + 1]
    assert call["input"] == REQUEST.prompt
    assert REQUEST.prompt not in cmd
    assert call["timeout"] == 30


def test_falls_back_to_fenced_result_text() -> None:
    run = FakeRun(fixture("quest_diff_result_text.json"))
    result = provider(run).generate(REQUEST, QuestDiff)
    assert len(result.output.ops) == 3


def test_invalid_output_is_retried_once_with_errors() -> None:
    run = FakeRun(fixture("quest_diff_invalid.json"), fixture("quest_diff_structured.json"))
    result = provider(run).generate(REQUEST, QuestDiff)

    assert result.attempts == 2
    assert result.usage is not None and result.usage.output == 184
    retry_prompt = run.calls[1]["input"]
    assert retry_prompt.startswith(REQUEST.prompt)
    assert "ops.0.add.reason: Field required" in retry_prompt
    assert "ops.0.add.quest.priority: Input should be less than or equal to 3" in retry_prompt
    # Validation errors never echo model output back.
    assert "Pay the power bill" not in retry_prompt


def test_invalid_twice_raises_output_error() -> None:
    run = FakeRun(fixture("quest_diff_invalid.json"), fixture("quest_diff_invalid.json"))
    with pytest.raises(ProviderOutputError):
        provider(run).generate(REQUEST, QuestDiff)
    assert len(run.calls) == 2


def test_cli_error_envelope_raises() -> None:
    run = FakeRun(fixture("error_max_turns.json"))
    with pytest.raises(ProviderError, match="error_max_turns"):
        provider(run).generate(REQUEST, QuestDiff)


def test_nonzero_exit_raises_without_stderr() -> None:
    run = FakeRun("", returncode=1)
    with pytest.raises(ProviderError, match="exited with code 1"):
        provider(run).generate(REQUEST, QuestDiff)


def test_timeout_raises() -> None:
    run = FakeRun(raises=subprocess.TimeoutExpired("claude", 30))
    with pytest.raises(ProviderError, match="timed out"):
        provider(run).generate(REQUEST, QuestDiff)


def test_missing_binary_is_unavailable() -> None:
    run = FakeRun(raises=FileNotFoundError())
    with pytest.raises(ProviderUnavailable):
        provider(run).generate(REQUEST, QuestDiff)
    assert not ClaudeCliProvider(executable="definitely-not-claude-xyz").is_available()


class StaticProvider(Provider):
    name = ProviderName.ollama

    def __init__(self, available: bool, stdout: str | None = None):
        self.available = available
        self.stdout = stdout

    def is_available(self) -> bool:
        return self.available

    def _complete(self, request: GenerationRequest, schema: dict[str, Any]) -> RawCompletion:
        assert self.stdout is not None
        from runner.providers.claude_cli import parse_envelope

        return parse_envelope(self.stdout)


class AvailableCli(ClaudeCliProvider):
    def is_available(self) -> bool:
        return True


def test_fallback_moves_to_next_provider_on_error() -> None:
    failing = AvailableCli(run=FakeRun(fixture("error_max_turns.json")))
    backup = StaticProvider(True, fixture("quest_diff_structured.json"))
    result = run_with_fallback([failing, backup], REQUEST, QuestDiff)
    assert result.provider is ProviderName.ollama


def test_fallback_skips_unavailable_and_reports_all_failures() -> None:
    down = StaticProvider(False)
    failing = AvailableCli(run=FakeRun(fixture("error_max_turns.json")))
    with pytest.raises(AllProvidersFailed) as info:
        run_with_fallback([down, failing], REQUEST, QuestDiff)
    assert [name for name, _ in info.value.failures] == [
        ProviderName.ollama,
        ProviderName.claude_cli,
    ]
    assert isinstance(info.value.failures[0][1], ProviderUnavailable)


def test_schema_sent_to_cli_is_strict_json_schema() -> None:
    from runner.providers.base import output_schema

    schema = output_schema(QuestDiff)
    assert "discriminator" not in json.dumps(schema)
    assert schema["$defs"]["QuestOp"]["oneOf"]


def test_semantic_check_failures_are_retried_with_the_problems() -> None:
    run = FakeRun(fixture("quest_diff_structured.json"), fixture("quest_diff_structured.json"))
    calls = []

    def check(diff: QuestDiff) -> list[str]:
        calls.append(diff)
        return ["ops.1: quest_id is not an open quest"] if len(calls) == 1 else []

    result = provider(run).generate(REQUEST, QuestDiff, check)
    assert result.attempts == 2
    assert "ops.1: quest_id is not an open quest" in run.calls[1]["input"]
