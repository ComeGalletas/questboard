"""Machine-local runner settings (not user toggles; those live in the `config` row).

Read from QUESTBOARD_SUPABASE_URL / QUESTBOARD_SUPABASE_ANON_KEY, else from runner.json in the
data dir. The anon key is public by design (RLS guards the data); the session lives in the
OS keychain, never in this file.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from runner.paths import data_dir


class SettingsMissing(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_anon_key: str

    @classmethod
    def load(cls) -> Settings:
        url = os.environ.get("QUESTBOARD_SUPABASE_URL")
        key = os.environ.get("QUESTBOARD_SUPABASE_ANON_KEY")
        path = data_dir() / "runner.json"
        if not (url and key) and path.exists():
            saved = json.loads(path.read_text())
            url = url or saved.get("supabase_url")
            key = key or saved.get("supabase_anon_key")
        if not (url and key):
            raise SettingsMissing(
                "set QUESTBOARD_SUPABASE_URL and QUESTBOARD_SUPABASE_ANON_KEY, "
                f"or run `python -m runner login` to write {path}"
            )
        return cls(url, key)

    def save(self) -> None:
        path = data_dir() / "runner.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"supabase_url": self.supabase_url, "supabase_anon_key": self.supabase_anon_key}
            )
        )
