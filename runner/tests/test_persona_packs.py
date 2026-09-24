"""Every persona pack in personas/ must satisfy the pack contract (CLAUDE.md "Persona packs")."""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path

import pytest
import yaml
from questboard_schema.fallback_lines_schema import FallbackLines
from questboard_schema.persona_line_schema import Trigger
from questboard_schema.persona_pack_schema import PersonaPack

PERSONAS = Path(__file__).resolve().parents[2] / "personas"
PACKS = sorted(p for p in PERSONAS.iterdir() if p.is_dir())
BUILT_IN = {"coach", "teacher", "mom", "quartermaster"}
PLACEHOLDERS = {"time_left", "streak", "days_carried", "actual_vs_estimate", "next_quest"}


def png_size(path: Path) -> tuple[int, int, int]:
    """(width, height, colour type) from the IHDR chunk."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    width, height, _, colour = struct.unpack(">IIBB", data[16:26])
    return width, height, colour


def test_built_in_packs_present() -> None:
    assert {p.name for p in PACKS} >= BUILT_IN


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.name)
def test_pack_manifest(pack: Path) -> None:
    manifest = PersonaPack.model_validate(yaml.safe_load((pack / "persona.yaml").read_text()))
    assert manifest.slug.root == pack.name
    assert (pack / "system.md").read_text().strip()


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.name)
def test_fallback_lines_cover_every_trigger(pack: Path) -> None:
    lines = FallbackLines.model_validate(
        json.loads((pack / "lines.fallback.json").read_text())
    ).lines
    for trigger in Trigger:
        mine = [line for line in lines if line.trigger == trigger]
        assert len(mine) >= 2, f"{pack.name}: {trigger.value} needs 2+ lines"
        # With no runtime values available the app still needs something to say.
        assert any("{" not in line.text for line in mine), (
            f"{pack.name}: {trigger.value} needs a line without placeholders"
        )
    for line in lines:
        unknown = set(re.findall(r"\{(\w+)\}", line.text)) - PLACEHOLDERS
        assert not unknown, f"{pack.name}: unknown placeholders {unknown} in {line.text!r}"


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.name)
def test_sprite_and_portrait(pack: Path) -> None:
    # Sprite is mandatory (invariant 7): five 32x32 frames, RGBA.
    assert png_size(pack / "assets" / "sprite.png") == (160, 32, 6)
    assert png_size(pack / "assets" / "portrait.png") == (16, 16, 6)
