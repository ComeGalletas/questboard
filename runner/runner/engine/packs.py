"""Persona packs as the runner sees them: validated manifest + voice (system.md) + digest.

`inspect_pack` checks a pack against the contract in CLAUDE.md ("Persona packs") and returns
errors (the pack is not loaded) and warnings (it loads, degraded). Built-in and custom packs go
through the same checks. Sprite is mandatory; a sheet with fewer than five frames loads, and the
app shows idle for the missing states (invariant 7). A pack cannot change schema, escalation caps
or quiet-hour rules: persona.yaml has a closed schema and everything else is voice text.

Problems name files and fields, never file contents.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError
from questboard_schema.fallback_lines_schema import FallbackLines
from questboard_schema.persona_digest_schema import PersonaDigest
from questboard_schema.persona_line_schema import Trigger
from questboard_schema.persona_pack_schema import PersonaPack

from runner.engine.validators import PLACEHOLDERS, pii_problem
from runner.paths import data_dir

log = logging.getLogger("questboard.runner")

VOICE_CAP = 1200  # chars of system.md per persona in prompts
DIGEST_CAP = 900  # chars of the rendered digest per persona in prompts
FRAME = 32
PORTRAIT = 16
STATES = ("idle", "talk", "happy", "concerned", "sleep")
SIZE_LIMITS = {  # bytes
    "sprite.png": 256 * 1024,
    "portrait.png": 64 * 1024,
    "model.glb": 8 * 1024 * 1024,
}
CONTEXT_SUFFIXES = {".md", ".txt"}
CONTEXT_FILE_CAP = 16 * 1024
CONTEXT_CAP = 48 * 1024  # total bytes of context/ read per pack
_PNG = b"\x89PNG\r\n\x1a\n"


def default_dir() -> Path:
    override = os.environ.get("QUESTBOARD_PERSONAS_DIR")
    return Path(override) if override else Path(__file__).resolve().parents[3] / "personas"


def default_digests_dir() -> Path:
    return data_dir() / "digests"


@dataclass(frozen=True)
class Pack:
    manifest: PersonaPack
    voice: str
    dir: Path | None = None
    frames: int = len(STATES)  # sprite frames present; missing states fall back to idle
    has_model: bool = False
    context_hash: str | None = None  # None when the pack has no context/
    digest: PersonaDigest | None = None

    @property
    def slug(self) -> str:
        return self.manifest.slug.root


@dataclass
class PackReport:
    dir: Path
    pack: Pack | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_packs(root: Path | None = None, digests: Path | None = None) -> list[Pack]:
    """Valid packs only; rejected packs are logged (names and counts, no contents)."""
    packs = []
    for report in inspect_packs(root, digests):
        if report.pack is None:
            log.warning("persona pack %s rejected (%d errors)", report.dir.name, len(report.errors))
        else:
            packs.append(report.pack)
    return packs


def inspect_packs(root: Path | None = None, digests: Path | None = None) -> list[PackReport]:
    root = root or default_dir()
    digests = digests or default_digests_dir()
    dirs = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    return [inspect_pack(d, digests) for d in dirs]


def inspect_pack(pack_dir: Path, digests: Path | None = None) -> PackReport:
    report = PackReport(pack_dir)
    manifest = _manifest(pack_dir, report)
    voice = _voice(pack_dir, report)
    _fallback_lines(pack_dir, report)
    frames = _sprite(pack_dir, report)
    _portrait(pack_dir, report)
    has_model = _model(pack_dir, report)
    context_hash = _context_hash(pack_dir)
    if report.errors or manifest is None:
        return report
    digest = _cached_digest(digests, manifest.slug.root) if context_hash and digests else None
    report.pack = Pack(manifest, voice, pack_dir, frames, has_model, context_hash, digest)
    return report


# -- checks -------------------------------------------------------------------------------------


def _manifest(pack_dir: Path, report: PackReport) -> PersonaPack | None:
    path = pack_dir / "persona.yaml"
    if not path.is_file():
        report.errors.append("persona.yaml: missing")
        return None
    try:
        manifest = PersonaPack.model_validate(yaml.safe_load(path.read_text()))
    except yaml.YAMLError:
        report.errors.append("persona.yaml: not valid YAML")
        return None
    except ValidationError as exc:
        report.errors += [f"persona.yaml: {e}" for e in _describe(exc)]
        return None
    if manifest.slug.root != pack_dir.name:
        report.errors.append("persona.yaml: slug must match the folder name")
    return manifest


def _voice(pack_dir: Path, report: PackReport) -> str:
    path = pack_dir / "system.md"
    text = path.read_text().strip() if path.is_file() else ""
    if not text:
        report.errors.append("system.md: missing or empty")
    elif len(text) > VOICE_CAP:
        report.warnings.append(f"system.md: longer than {VOICE_CAP} chars; the rest is ignored")
    return text[:VOICE_CAP]


def _fallback_lines(pack_dir: Path, report: PackReport) -> None:
    path = pack_dir / "lines.fallback.json"
    if not path.is_file():
        report.errors.append("lines.fallback.json: missing")
        return
    try:
        lines = FallbackLines.model_validate(json.loads(path.read_text())).lines
    except json.JSONDecodeError:
        report.errors.append("lines.fallback.json: not valid JSON")
        return
    except ValidationError as exc:
        report.errors += [f"lines.fallback.json: {e}" for e in _describe(exc)]
        return
    for i, line in enumerate(lines):
        unknown = set(re.findall(r"\{(\w+)\}", line.text)) - PLACEHOLDERS
        if unknown:
            report.errors.append(f"lines.fallback.json: lines.{i} unknown placeholder(s)")
        if pii_problem(line.text):
            report.errors.append(f"lines.fallback.json: lines.{i} {pii_problem(line.text)}")
    for trigger in Trigger:
        mine = [line for line in lines if line.trigger == trigger]
        # With no runtime values the app still needs something to say for every trigger.
        if not any("{" not in line.text for line in mine):
            report.errors.append(
                f"lines.fallback.json: {trigger.value} needs a line without placeholders"
            )
        elif len(mine) < 2:
            report.warnings.append(f"lines.fallback.json: {trigger.value} has only one line")


def _sprite(pack_dir: Path, report: PackReport) -> int:
    path = pack_dir / "assets" / "sprite.png"
    if not path.is_file():
        report.errors.append("assets/sprite.png: missing (the sprite is mandatory)")
        return 0
    if not _within_limit(path, report, error=True):
        return 0
    size = png_size(path)
    if size is None:
        report.errors.append("assets/sprite.png: not a PNG")
        return 0
    width, height = size
    if height != FRAME or width % FRAME or width == 0:
        report.errors.append(
            f"assets/sprite.png: must be a row of {FRAME}x{FRAME} frames (got {width}x{height})"
        )
        return 0
    frames = width // FRAME
    if frames < len(STATES):
        missing = ", ".join(STATES[frames:])
        report.warnings.append(f"assets/sprite.png: no {missing} frame(s); idle is shown instead")
    elif frames > len(STATES):
        report.warnings.append(f"assets/sprite.png: frames after {STATES[-1]} are ignored")
    return min(frames, len(STATES))


def _portrait(pack_dir: Path, report: PackReport) -> None:
    path = pack_dir / "assets" / "portrait.png"
    if not path.is_file():
        report.warnings.append("assets/portrait.png: missing; no portrait is shown")
        return
    if not _within_limit(path, report, error=False):
        return
    if png_size(path) != (PORTRAIT, PORTRAIT):
        report.warnings.append(f"assets/portrait.png: should be {PORTRAIT}x{PORTRAIT}")


def _model(pack_dir: Path, report: PackReport) -> bool:
    path = pack_dir / "assets" / "model.glb"
    if not path.is_file():
        return False
    if not _within_limit(path, report, error=False):
        return False  # 3D is optional: the sprite is used instead
    if path.read_bytes()[:4] != b"glTF":
        report.warnings.append("assets/model.glb: not a binary glTF; the sprite is used instead")
        return False
    return True


def _within_limit(path: Path, report: PackReport, error: bool) -> bool:
    limit = SIZE_LIMITS[path.name]
    if path.stat().st_size <= limit:
        return True
    problem = f"assets/{path.name}: larger than {limit // 1024} KB"
    if error:
        report.errors.append(problem)
    else:
        report.warnings.append(f"{problem}; ignored")
    return False


def png_size(path: Path) -> tuple[int, int] | None:
    """(width, height) from the IHDR chunk, or None if the file is not a PNG."""
    head = path.read_bytes()[:24]
    if len(head) < 24 or head[:8] != _PNG or head[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def _describe(exc: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}"
        for e in exc.errors(include_input=False, include_url=False)
    ][:10]


# -- context/ and digests ------------------------------------------------------------------------


def context_files(pack_dir: Path) -> list[Path]:
    """Text files under context/, sorted; symlinks are never followed out of the pack."""
    root = pack_dir / "context"
    if not root.is_dir() or root.is_symlink():
        return []
    return sorted(
        p
        for p in root.rglob("*")
        if p.suffix.lower() in CONTEXT_SUFFIXES and p.is_file() and not p.is_symlink()
    )


def read_context(pack_dir: Path) -> str:
    """context/ as one text, each file capped and the total capped (CONTEXT_CAP)."""
    parts, total = [], 0
    for path in context_files(pack_dir):
        text = path.read_bytes()[:CONTEXT_FILE_CAP].decode("utf-8", errors="ignore").strip()
        chunk = f"### {path.relative_to(pack_dir / 'context').as_posix()}\n{text}"
        if total + len(chunk) > CONTEXT_CAP:
            chunk = chunk[: CONTEXT_CAP - total]
        parts.append(chunk)
        total += len(chunk)
        if total >= CONTEXT_CAP:
            break
    return "\n\n".join(parts)


def _context_hash(pack_dir: Path) -> str | None:
    text = read_context(pack_dir)
    return hashlib.sha256(text.encode()).hexdigest() if text else None


def _cached_digest(digests: Path, slug: str) -> PersonaDigest | None:
    cached = read_cached_digest(digests, slug)
    return cached[1] if cached else None


def read_cached_digest(digests: Path, slug: str) -> tuple[str, PersonaDigest] | None:
    """(context hash it was made from, digest), or None when there is no usable cache."""
    path = digests / f"{slug}.json"
    try:
        data = json.loads(path.read_text())
        return data["context_hash"], PersonaDigest.model_validate(data["digest"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_cached_digest(digests: Path, slug: str, context_hash: str, digest: PersonaDigest):
    digests.mkdir(parents=True, exist_ok=True)
    data = {"context_hash": context_hash, "digest": digest.model_dump(mode="json")}
    tmp = digests / f".{slug}.json.tmp"
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
    tmp.replace(digests / f"{slug}.json")


def render_digest(digest: PersonaDigest) -> str:
    parts = [f"Voice: {digest.voice}"]
    if digest.do:
        parts.append("Do: " + "; ".join(d.root for d in digest.do))
    if digest.dont:
        parts.append("Don't: " + "; ".join(d.root for d in digest.dont))
    if digest.sample_lines:
        parts.append("Sample lines: " + " / ".join(f'"{s.root}"' for s in digest.sample_lines))
    return "\n".join(parts)[:DIGEST_CAP]
