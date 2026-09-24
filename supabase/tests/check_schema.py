"""Cross-checks the migrated database against packages/schema.

- Every text enum CHECK constraint lists exactly the values of the matching schema enum.
- public.default_config() validates against the generated Config model.

Usage (from runner/): uv run python ../supabase/tests/check_schema.py
Connection comes from the usual PG* environment variables.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from questboard_schema.config_schema import Config

SCHEMAS = Path(__file__).resolve().parents[2] / "packages" / "schema" / "schemas"


def load(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text())


common = load("common")["$defs"]
quest = load("quest")["properties"]
llm_run = load("llm_run")["properties"]
line = load("persona_line")["properties"]
record = load("extracted_record")["properties"]
goal = load("config")["$defs"]["Goal"]["properties"]
proposal = load("quest_proposal")["properties"]

EXPECTED: dict[tuple[str, str], list[str]] = {
    ("quests", "cadence"): common["Cadence"]["enum"],
    ("quests", "category"): common["Category"]["enum"],
    ("quests", "status"): quest["status"]["enum"],
    ("quests", "source"): quest["source"]["enum"],
    ("llm_runs", "job"): common["JobName"]["enum"],
    ("llm_runs", "slot"): llm_run["slot"]["anyOf"][0]["enum"],
    ("llm_runs", "trigger"): llm_run["trigger"]["enum"],
    ("llm_runs", "status"): llm_run["status"]["enum"],
    ("llm_runs", "provider_used"): common["ProviderName"]["enum"],
    ("persona_lines", "trigger"): line["trigger"]["enum"],
    ("persona_lines", "condition"): line["condition"]["enum"],
    ("extracted_records", "category"): common["Category"]["enum"],
    ("extracted_records", "kind"): record["kind"]["enum"],
    ("senders", "category"): common["Category"]["enum"],
    ("goals", "horizon"): goal["horizon"]["enum"],
    ("quest_proposals", "op"): proposal["op"]["enum"],
    ("quest_proposals", "status"): proposal["status"]["enum"],
}

CONSTRAINTS_SQL = """
select c.relname, a.attname, pg_get_constraintdef(k.oid)
from pg_constraint k
join pg_class c on c.oid = k.conrelid
join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
join pg_attribute a on a.attrelid = c.oid and a.attnum = k.conkey[1]
where k.contype = 'c' and cardinality(k.conkey) = 1
"""


def psql(sql: str) -> list[list[str]]:
    out = subprocess.run(
        ["psql", "-X", "-qAt", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [row.split("\t") for row in out.splitlines() if row]


def main() -> int:
    actual: dict[tuple[str, str], list[str]] = {}
    for table, column, definition in psql(CONSTRAINTS_SQL):
        if "ANY (ARRAY[" in definition:
            actual[(table, column)] = re.findall(r"'([^']*)'::text", definition)

    errors = []
    for key, expected in EXPECTED.items():
        got = actual.get(key)
        if got is None:
            errors.append(f"{key[0]}.{key[1]}: no enum CHECK constraint")
        elif sorted(got) != sorted(expected):
            missing = sorted(set(expected) - set(got))
            extra = sorted(set(got) - set(expected))
            errors.append(f"{key[0]}.{key[1]}: missing {missing}, extra {extra}")

    (default_config,) = psql("select public.default_config()")[0]
    try:
        Config.model_validate_json(default_config)
    except ValueError as exc:
        errors.append(f"default_config() does not validate: {exc}")

    for err in errors:
        print(f"schema drift: {err}", file=sys.stderr)
    if not errors:
        print(f"schema check passed ({len(EXPECTED)} enums, default config)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
