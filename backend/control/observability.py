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
        # Only scalar operational fields are permitted. Unknown fields and all
        # containers are dropped, including nested payloads under benign keys.
        allowed_strings = {
            "deployment_id",
            "operation",
            "status",
            "failure_code",
            "path",
            "required_role",
        }
        allowed_counts = {"estimated_tokens", "deployment_count"}
        return {
            key: value
            for key, value in self.attributes.items()
            if (
                key in allowed_strings
                and isinstance(value, str)
                and len(value) <= 256
                and not any(ord(char) < 32 for char in value)
            )
            or (key in allowed_counts and type(value) is int and value >= 0)
        }
