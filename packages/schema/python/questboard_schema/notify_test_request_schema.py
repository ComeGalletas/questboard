# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from . import common_schema


class NotifyTestRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    kind: common_schema.NotificationKind
