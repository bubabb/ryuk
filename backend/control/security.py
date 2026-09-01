from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


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


def resolve_secret_ref(value: str) -> str:
    """Resolve a supported locator at the deployment adapter boundary."""
    provider, separator, reference = value.partition(":")
    if separator != ":":
        raise ValueError("Secret references use the '<provider>:<reference>' format.")
    secret_ref = SecretRef(provider, reference)
    if secret_ref.provider != "env":
        raise ValueError("Unsupported secret reference provider.")
    secret = os.environ.get(secret_ref.reference)
    if not secret:
        raise ValueError("The referenced secret is unavailable.")
    return secret
