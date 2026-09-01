from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from backend.control.admission import AdmissionController, QuotaPolicy
from backend.control.observability import ControlEvent
from backend.control.records import ExecutionRecord, SQLiteExecutionRecordStore
from backend.control.security import (
    APIKeyRecord,
    Principal,
    Role,
    authenticate_api_key,
    authorize,
)

_LOGGER = logging.getLogger("ryuk.control")


class ExecutionRecordWriter(Protocol):
    def put(self, record: ExecutionRecord) -> None: ...


@dataclass(frozen=True, slots=True)
class ControlPlaneFailure(Exception):
    status_code: int
    code: str
    message: str


class AdmissionPermit:
    def __init__(self, controller: AdmissionController, tenant_id: str) -> None:
        self._controller = controller
        self.tenant_id = tenant_id
        self._released = False

    def release(self) -> None:
        if not self._released:
            self._controller.release(self.tenant_id)
            self._released = True


class APIControlPlane:
    """Shared fail-closed API authentication and admission boundary."""

    def __init__(
        self,
        api_keys: dict[str, APIKeyRecord],
        admission: AdmissionController,
        records: ExecutionRecordWriter | None = None,
    ) -> None:
        self.api_keys = api_keys
        self.admission = admission
        self.records = records

    def authenticate(self, authorization: str | None) -> Principal:
        if authorization is None:
            raise ControlPlaneFailure(
                401, "authentication_required", "Authentication required."
            )
        scheme, separator, value = authorization.partition(" ")
        if separator != " " or scheme.casefold() != "bearer" or not value.strip():
            raise ControlPlaneFailure(
                401, "invalid_credentials", "Invalid credentials."
            )
        principal = authenticate_api_key(value.strip(), self.api_keys)
        if principal is None:
            raise ControlPlaneFailure(
                401, "invalid_credentials", "Invalid credentials."
            )
        return principal

    def require_role(self, principal: Principal, role: Role) -> None:
        if not authorize(principal, tenant_id=principal.tenant_id, role=role):
            raise ControlPlaneFailure(403, "forbidden", "Operation not permitted.")

    def admit(self, principal: Principal, estimated_tokens: int) -> AdmissionPermit:
        if not self.admission.admit(principal.tenant_id, estimated_tokens):
            raise ControlPlaneFailure(429, "quota_exceeded", "Request quota exceeded.")
        return AdmissionPermit(self.admission, principal.tenant_id)

    def record(self, record: ExecutionRecord) -> None:
        if self.records is not None:
            self.records.put(record)

    def emit(
        self,
        event_name: str,
        tenant_id: str,
        request_id: str | None,
        attributes: dict[str, object],
    ) -> None:
        event = ControlEvent(
            event_name,
            tenant_id,
            request_id,
            datetime.now(UTC),
            attributes,
        )
        _LOGGER.info(
            "control_event",
            extra={
                "event_name": event.event_name,
                "tenant_id": event.tenant_id,
                "request_id": event.request_id,
                "attributes": event.safe_attributes(),
            },
        )

    def close(self) -> None:
        if isinstance(self.records, SQLiteExecutionRecordStore):
            self.records.close()


def load_api_control(
    config_path: Path | None,
    record_path: Path | None,
) -> APIControlPlane:
    """Load hashed identities and quotas from server-owned configuration."""
    if config_path is None:
        return APIControlPlane({}, AdmissionController({}))

    document = json.loads(config_path.read_text(encoding="utf-8"))
    keys: dict[str, APIKeyRecord] = {}
    for item in document.get("api_keys", []):
        principal = Principal(
            principal_id=item["principal_id"],
            tenant_id=item["tenant_id"],
            roles=frozenset(Role(value) for value in item["roles"]),
        )
        record = APIKeyRecord(
            key_id=item["key_id"],
            salt=item["salt"],
            digest=item["digest"],
            principal=principal,
            expires_at=_optional_datetime(item.get("expires_at")),
            revoked_at=_optional_datetime(item.get("revoked_at")),
        )
        if record.key_id in keys:
            raise ValueError("API key identifiers must be unique.")
        keys[record.key_id] = record

    policies = {
        tenant_id: QuotaPolicy(
            requests_per_minute=value["requests_per_minute"],
            concurrent_requests=value["concurrent_requests"],
            tokens_per_minute=value["tokens_per_minute"],
        )
        for tenant_id, value in document.get("quotas", {}).items()
    }
    records = (
        SQLiteExecutionRecordStore(record_path)
        if record_path is not None
        else None
    )
    return APIControlPlane(keys, AdmissionController(policies), records)


def _optional_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None
