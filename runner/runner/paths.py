"""Per-machine locations for runner state (lock file now; vault and logs later)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("QUESTBOARD_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Questboard"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Questboard"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "questboard"
