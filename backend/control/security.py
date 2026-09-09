from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

import httpx


class Role(StrEnum):
    INFERENCE = "inference"
    OPERATOR = "operator"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class Principal:
    principal_id: str
    tenant_id: str
    roles: frozenset[Role]

    def __post_init__(self) -> None:
        if (
            not self.principal_id.strip()
            or not self.tenant_id.strip()
            or not self.roles
        ):
            raise ValueError("Principal identity and roles are required.")


@dataclass(frozen=True, slots=True)
class APIKeyRecord:
    key_id: str
    salt: str
    digest: str
    principal: Principal
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        for value in (self.expires_at, self.revoked_at):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() is None
            ):
                raise ValueError("API key lifecycle timestamps require timezone data.")


def issue_api_key(
    principal: Principal, *, expires_at: datetime | None = None
) -> tuple[str, APIKeyRecord]:
    # Hex avoids the underscore delimiter used by the serialized key format.
    key_id = secrets.token_hex(12)
    secret = secrets.token_urlsafe(32)
    salt = secrets.token_hex(16)
    digest = _digest(secret, salt)
    return f"ryuk_{key_id}_{secret}", APIKeyRecord(
        key_id, salt, digest, principal, expires_at=expires_at
    )


def authenticate_api_key(
    value: str,
    records: dict[str, APIKeyRecord],
    *,
    now: datetime | None = None,
) -> Principal | None:
    parts = value.split("_", 2)
    if len(parts) != 3 or parts[0] != "ryuk":
        return None
    record = records.get(parts[1])
    if record is None or not hmac.compare_digest(
        _digest(parts[2], record.salt), record.digest
    ):
        return None
    current = datetime.now(UTC) if now is None else now
    if record.revoked_at is not None or (
        record.expires_at is not None and current >= record.expires_at
    ):
        return None
    return record.principal


def authorize(principal: Principal, *, tenant_id: str, role: Role) -> bool:
    """Deny cross-tenant and ungranted function access by default."""
    return principal.tenant_id == tenant_id and (
        role in principal.roles or Role.ADMIN in principal.roles
    )


def _digest(secret: str, salt: str) -> str:
    return hashlib.scrypt(
        secret.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1
    ).hex()


@dataclass(frozen=True, slots=True)
class SecretRef:
    provider: str
    reference: str

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.reference.strip():
            raise ValueError("Secret references must not be blank.")
        if any(
            marker in self.reference.casefold()
            for marker in ("secret=", "token=", "password=")
        ):
            raise ValueError("SecretRef stores a locator, never secret material.")


class SecretManager(Protocol):
    def resolve(self, reference: str) -> str: ...


class EnvironmentSecretManager:
    def resolve(self, reference: str) -> str:
        secret = os.environ.get(reference)
        if not secret:
            raise ValueError("The referenced secret is unavailable.")
        return secret


class VaultSecretManager:
    """Resolve one field from a Vault KV response without retaining the value."""

    def __init__(
        self,
        address: str,
        *,
        token_env: str = "VAULT_TOKEN",
        client: httpx.Client | None = None,
    ) -> None:
        if not address.startswith("https://"):
            raise ValueError("Vault requires an HTTPS address.")
        self._address = address.rstrip("/")
        token = os.environ.get(token_env)
        if not token:
            raise ValueError("The Vault authentication token is unavailable.")
        self._token = token
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=5.0,
        )

    def resolve(self, reference: str) -> str:
        path, separator, field = reference.partition("#")
        if separator != "#" or not path.strip() or not field.strip():
            raise ValueError("Vault references use the '<path>#<field>' format.")
        response = self._client.get(
            f"{self._address}/v1/{path.lstrip('/')}",
            headers={"X-Vault-Token": self._token},
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            data = data["data"]
        secret = data.get(field) if isinstance(data, dict) else None
        if not isinstance(secret, str) or not secret:
            raise ValueError("The referenced Vault secret field is unavailable.")
        return secret

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def resolve_secret_ref(
    value: str,
    *,
    managers: dict[str, SecretManager] | None = None,
) -> str:
    """Resolve a locator through an explicitly configured secret manager."""
    provider, separator, reference = value.partition(":")
    if separator != ":":
        raise ValueError("Secret references use the '<provider>:<reference>' format.")
    secret_ref = SecretRef(provider, reference)
    available = managers or {"env": EnvironmentSecretManager()}
    manager = available.get(secret_ref.provider)
    if manager is None:
        raise ValueError("Unsupported secret reference provider.")
    return manager.resolve(secret_ref.reference)
