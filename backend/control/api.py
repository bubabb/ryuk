from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from backend.control.admission import (
    AdmissionController,
    QuotaPolicy,
    RedisAdmissionController,
)
from backend.control.observability import ControlEvent
from backend.control.records import (
    ExecutionRecord,
    PostgreSQLExecutionRecordStore,
    SQLiteExecutionRecordStore,
)
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


class AdmissionCoordinator(Protocol):
    @property
    def configured_tenants(self) -> frozenset[str]: ...

    def admit(self, tenant_id: str, estimated_tokens: int) -> bool: ...

    def release(self, tenant_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class ControlPlaneFailure(Exception):
    status_code: int
    code: str
    message: str


class AdmissionPermit:
    def __init__(self, controller: AdmissionCoordinator, tenant_id: str) -> None:
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
        admission: AdmissionCoordinator,
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

    def require_role(
        self,
        principal: Principal,
        role: Role,
        *,
        tenant_id: str | None = None,
    ) -> None:
        target_tenant = principal.tenant_id if tenant_id is None else tenant_id
        if not authorize(principal, tenant_id=target_tenant, role=role):
            raise ControlPlaneFailure(403, "forbidden", "Operation not permitted.")

    def verify_production_ready(self, *, now: datetime | None = None) -> None:
        """Refuse production traffic unless every control-plane guard is usable."""
        current = datetime.now(UTC) if now is None else now
        active_records = [
            record
            for record in self.api_keys.values()
            if record.revoked_at is None
            and (record.expires_at is None or current < record.expires_at)
        ]
        if not active_records:
            raise RuntimeError("Production requires at least one active API key.")

        credential_tenants = {
            record.principal.tenant_id for record in active_records
        }
        missing_quotas = credential_tenants - self.admission.configured_tenants
        if missing_quotas:
            raise RuntimeError(
                "Production requires quota policies for every credential tenant."
            )

        if self.records is None:
            raise RuntimeError("Production requires a durable execution-record store.")
        health = getattr(self.records, "health", None)
        if health is None:
            raise RuntimeError("Production execution-record store has no health check.")
        status = health()
        if (
            not status.get("ready")
            or not status.get("durable")
            or not status.get("distributed")
        ):
            raise RuntimeError("Production execution-record store is not ready.")

        admission_health = getattr(self.admission, "health", None)
        if admission_health is None:
            raise RuntimeError("Production admission coordinator has no health check.")
        admission_status = admission_health()
        if not admission_status.get("ready") or not admission_status.get(
            "distributed"
        ):
            raise RuntimeError("Production admission coordinator is not ready.")

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
        for resource in (self.records, self.admission):
            close = getattr(resource, "close", None)
            if close is not None:
                close()


def load_api_control(
    config_path: Path | None,
    record_path: Path | None,
    *,
    database_url: str = "",
    redis_url: str = "",
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
    admission: AdmissionCoordinator = (
        RedisAdmissionController(policies, redis_url=redis_url)
        if redis_url.strip()
        else AdmissionController(policies)
    )
    records: ExecutionRecordWriter | None
    try:
        if database_url.strip():
            records = PostgreSQLExecutionRecordStore(database_url)
        elif record_path is not None:
            records = SQLiteExecutionRecordStore(record_path)
        else:
            records = None
    except Exception:
        close = getattr(admission, "close", None)
        if close is not None:
            close()
        raise
    return APIControlPlane(keys, admission, records)


def _optional_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None
