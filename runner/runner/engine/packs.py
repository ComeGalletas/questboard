"""Persona packs as the runner sees them: manifest + voice (system.md), for prompts and checks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from questboard_schema.persona_pack_schema import PersonaPack

VOICE_CAP = 1200  # chars of system.md per persona in prompts (context/ digests come later)


def default_dir() -> Path:
    override = os.environ.get("QUESTBOARD_PERSONAS_DIR")
    return Path(override) if override else Path(__file__).resolve().parents[3] / "personas"


@dataclass(frozen=True)
class Pack:
    manifest: PersonaPack
    voice: str

    @property
    def slug(self) -> str:
        return self.manifest.slug.root


def load_packs(root: Path | None = None) -> list[Pack]:
    root = root or default_dir()
    packs = []
    for pack_dir in sorted(p for p in root.iterdir() if (p / "persona.yaml").is_file()):
        manifest = PersonaPack.model_validate(
            yaml.safe_load((pack_dir / "persona.yaml").read_text())
        )
        system = pack_dir / "system.md"
        voice = system.read_text().strip()[:VOICE_CAP] if system.is_file() else ""
        packs.append(Pack(manifest, voice))
    return packs
