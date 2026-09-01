from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ControlEvent:
    event_name: str
    tenant_id: str
    request_id: str | None
    occurred_at: datetime
    attributes: dict[str, Any]

    def safe_attributes(self) -> dict[str, Any]:
        blocked = {"prompt", "output", "api_key", "authorization", "secret"}
        return {
            key: value
            for key, value in self.attributes.items()
            if key.casefold() not in blocked
        }
